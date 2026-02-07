"""DeepEval-based evaluation runner.

Goal: make it easier to iterate on evals than our custom console runner by using
DeepEval for batching, reporting, and optional LLM-graded metrics.

This runner treats each EvalCase as a DeepEval test case.

Notes:
- "Deterministic" checks (tool selection, authorization) are handled locally.
- "Answer quality" can be graded via DeepEval metrics (optional), but by default
  we keep it lightweight and only run deterministic checks.

Usage examples:
  python -m evals.deepeval_runner --dataset generated-1000 --sample 100 --seed 7

If you want LLM-graded metrics, set OPENAI_API_KEY (or your DeepEval-supported
provider env vars) and pass --llm-metrics.
"""

from __future__ import annotations

import argparse
import random
import re
import os
import json
from dataclasses import dataclass
from typing import Iterable

from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric, ToxicityMetric
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase

from evals.datasets import EvalDataset, get_default_dataset
from evals.metrics import EvalCategory
from hr_agent.configs.config import get_langfuse_client


# --- Import datasets lazily to avoid loading big modules unless requested


def _load_dataset(name: str) -> EvalDataset:
    if name == "generated-1000":
        from evals.generated_dataset_1000 import GENERATED_DATASET_1000

        return GENERATED_DATASET_1000
    if name == "default":
        return get_default_dataset()
    raise ValueError(f"Unknown dataset: {name}")


def _is_access_denied(response: str) -> bool:
    denial_phrases = [
        "access denied",
        "not authorized",
        "don't have permission",
        "cannot access",
        "restricted",
        "only hr",
        "not allowed",
        "you do not have",
        "you don't have access",
        "permission denied",
        "i can't share",
        "can't provide",
        "cannot provide",
        "you do not have permission",
        "you are not authorized",
        "your own",
        "only.*your",
    ]
    return any(re.search(p, response or "", re.IGNORECASE) for p in denial_phrases)


def _tool_selection_ok(expected: list[str], actual: list[str]) -> bool:
    if not expected:
        # If nothing expected, we don't fail for tool calls here (deterministic only).
        return True
    return bool(set(expected) & set(actual))


@dataclass
class CaseOutcome:
    case_id: str
    category: str
    passed: bool
    reason: str


class DatabricksLLM(DeepEvalBaseLLM):
    def __init__(self, model: str, api_url: str, api_key: str):
        self.model = model
        self.api_url = api_url
        self.api_key = api_key

    def generate(self, prompt: str, **kwargs) -> str:
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = requests.post(
                self.api_url, headers=headers, json=payload, timeout=60
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[DatabricksLLM error: {e}]"

    def load_model(self):
        # Not needed for remote API
        return self

    async def a_generate(self, prompt: str, **kwargs) -> str:
        # Not used in this runner
        raise NotImplementedError("Async generate not implemented")

    def get_model_name(self) -> str:
        return self.model


def run_deepeval(
    dataset: EvalDataset,
    sample: int = 0,
    seed: int = 7,
    sample_offset: int = 0,
    use_llm_metrics: bool = True,
    refusal_metric: bool = True,
    faithfulness_metric: bool = True,
    relevance_metric: bool = True,
    toxicity_metric: bool = False,
    grader_model: str = "",
    grader_api_url: str = "",
    grader_api_key: str = "",
    faithfulness_threshold: float = 0.5,
    relevance_threshold: float = 0.5,
    refusal_threshold: float = 0.5,
    toxicity_threshold: float = 0.5,
    export_json: str = "",
    batch_grading: bool = False,  # Placeholder for future batch grading
) -> list[CaseOutcome]:
    from hr_agent.agent.langgraph_agent import HRAgentLangGraph

    cases = list(dataset.cases)
    if sample:
        rng = random.Random(seed)
        rng.shuffle(cases)
        cases = cases[sample_offset : sample_offset + sample]

    # Set up Databricks LLM grader
    if use_llm_metrics:
        model = grader_model or os.environ.get(
            "GRADER_MODEL", "databricks-qwen3-next-80b-a3b-instruct"
        )
        api_url = grader_api_url or os.environ.get(
            "GRADER_API_URL",
            "https://YOUR-DATABRICKS-URL/serving-endpoint/YOUR-ENDPOINT/invocations",
        )
        api_key = grader_api_key or os.environ.get("GRADER_API_KEY", "")
        llm = DatabricksLLM(model, api_url, api_key)

        # Metrics
        metrics = []
        if faithfulness_metric:
            metrics.append(FaithfulnessMetric(model=llm))
        if toxicity_metric:
            metrics.append(ToxicityMetric())
    else:
        metrics = []

    outcomes: list[CaseOutcome] = []
    export_data = []

    # TODO: If batch_grading and Databricks API supports it, implement batch grading here.
    # For now, grading is per-case.

    for c in cases:
        trace_metadata = {
            "run_type": "eval",
            "eval_dataset": dataset.name,
            "eval_case_id": c.id,
            "eval_category": c.category.value,
            "eval_difficulty": c.difficulty.value,
        }
        eval_session_id = f"eval_{c.id}"
        agent = HRAgentLangGraph(
            c.user_email,
            session_id=eval_session_id,
            trace_metadata=trace_metadata,
        )
        response = agent.chat(c.query)
        tools_called = getattr(agent, "tools_called", [])

        # Deterministic checks
        tool_ok = _tool_selection_ok(c.expected_tools or [], tools_called)
        auth_ok = True
        if getattr(c, "should_be_denied", False):
            auth_ok = _is_access_denied(response)

        # LLM-graded metrics
        llm_pass = True
        metric_scores = {}
        metric_results = {}
        if use_llm_metrics and metrics:
            tc = LLMTestCase(
                input=c.query,
                actual_output=response,
                expected_output="",
                context=[
                    f"case_id={c.id}",
                    f"category={c.category.value}",
                    f"expected_tools={c.expected_tools}",
                    f"tools_called={tools_called}",
                ],
            )
            for m in metrics:
                try:
                    result = m.measure(tc)
                    metric_scores[m.__class__.__name__] = getattr(result, "score", None)
                    # Threshold logic per metric
                    if isinstance(m, FaithfulnessMetric):
                        metric_results["faithfulness"] = (
                            getattr(result, "score", 1.0) >= faithfulness_threshold
                        )
                    elif isinstance(m, ToxicityMetric):
                        metric_results["toxicity"] = (
                            getattr(result, "score", 0.0) >= toxicity_threshold
                        )
                except Exception as e:
                    metric_scores[m.__class__.__name__] = f"error: {e}"
                    metric_results[m.__class__.__name__] = False
            # Pass if all metrics pass
            llm_pass = all(metric_results.get(k, True) for k in metric_results)

        passed = tool_ok and auth_ok and llm_pass

        if not tool_ok:
            reason = "tool_selection"
        elif not auth_ok:
            reason = "authorization"
        elif not llm_pass:
            reason = "llm_metric"
        else:
            reason = "pass"

        outcomes.append(
            CaseOutcome(
                case_id=c.id,
                category=c.category.value,
                passed=passed,
                reason=reason,
            )
        )
        export_data.append(
            {
                "case_id": c.id,
                "category": c.category.value,
                "passed": passed,
                "reason": reason,
                "query": c.query,
                "response": response,
                "tools_called": tools_called,
                "expected_tools": c.expected_tools,
                "should_be_denied": getattr(c, "should_be_denied", False),
                "metric_scores": metric_scores,
                "metric_results": metric_results,
            }
        )

        client = get_langfuse_client()
        if client:
            metadata = {
                "eval_dataset": dataset.name,
                "eval_case_id": c.id,
                "eval_category": c.category.value,
                "eval_difficulty": c.difficulty.value,
            }
            client.create_score(
                name="eval_pass",
                value=1.0 if passed else 0.0,
                data_type="BOOLEAN",
                session_id=eval_session_id,
                metadata=metadata,
            )
            client.create_score(
                name="eval_tool_selection",
                value=1.0 if tool_ok else 0.0,
                data_type="BOOLEAN",
                session_id=eval_session_id,
                metadata=metadata,
            )
            client.create_score(
                name="eval_authorization",
                value=1.0 if auth_ok else 0.0,
                data_type="BOOLEAN",
                session_id=eval_session_id,
                metadata=metadata,
            )
            if use_llm_metrics:
                client.create_score(
                    name="eval_answer_quality",
                    value=1.0 if llm_pass else 0.0,
                    data_type="BOOLEAN",
                    session_id=eval_session_id,
                    metadata=metadata,
                )

    if export_json:
        with open(export_json, "w") as f:
            json.dump(export_data, f, indent=2)
        print(f"Exported eval results to {export_json}")

    client = get_langfuse_client()
    if client:
        try:
            client.flush()
        except Exception:
            pass

    return outcomes


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run HR Agent evals with DeepEval")
    parser.add_argument(
        "--dataset",
        default="generated-1000",
        choices=["generated-1000", "default"],
        help="Which dataset to run",
    )
    parser.add_argument("--sample", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--sample-offset", type=int, default=0)
    parser.add_argument(
        "--faithfulness-threshold",
        type=float,
        default=0.5,
        help="Faithfulness metric threshold",
    )
    parser.add_argument(
        "--relevance-threshold",
        type=float,
        default=0.5,
        help="Relevance metric threshold",
    )
    parser.add_argument(
        "--refusal-threshold", type=float, default=0.5, help="Refusal metric threshold"
    )
    parser.add_argument(
        "--toxicity-threshold",
        type=float,
        default=0.5,
        help="Toxicity metric threshold",
    )
    parser.add_argument(
        "--export-json",
        type=str,
        default=None,
        help="Export failed cases and metrics to JSON file",
    )
    parser.add_argument(
        "--batch-grading",
        action="store_true",
        help="Enable batch grading if supported (TODO)",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    dataset = _load_dataset(args.dataset)
    outcomes = run_deepeval(
        dataset=dataset,
        sample=args.sample,
        seed=args.seed,
        sample_offset=args.sample_offset,
        faithfulness_threshold=args.faithfulness_threshold,
        relevance_threshold=args.relevance_threshold,
        refusal_threshold=args.refusal_threshold,
        toxicity_threshold=args.toxicity_threshold,
        export_json=args.export_json,
        batch_grading=args.batch_grading,
    )

    total = len(outcomes)
    passed = sum(1 for o in outcomes if o.passed)
    by_reason: dict[str, int] = {}
    for o in outcomes:
        by_reason[o.reason] = by_reason.get(o.reason, 0) + 1

    print(f"Dataset: {dataset.name}")
    print(f"Cases: {total}")
    print(f"Passed: {passed}/{total} ({(passed/total*100 if total else 0):.1f}%)")
    print("By reason:")
    for k in sorted(by_reason, key=lambda x: (-by_reason[x], x)):
        print(f"  {k}: {by_reason[k]}")

    # Print failed IDs for quick triage
    failed = [o.case_id for o in outcomes if not o.passed]
    if failed:
        print("Failed case_ids:")
        for cid in failed[:50]:
            print(" ", cid)
        if len(failed) > 50:
            print(f"  ... and {len(failed) - 50} more")

    # Return non-zero if there are failures
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
