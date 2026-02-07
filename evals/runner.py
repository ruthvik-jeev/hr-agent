"""
Evaluation Runner

Executes evaluation cases and collects metrics.
Supports parallel execution and detailed logging.
Uses LangGraph-based HRAgentLangGraph.
"""

import json
import time
import re
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from .metrics import EvalResult, EvalMetrics
from .datasets import EvalCase, EvalDataset, get_default_dataset
from .logger import EvalLogger, LogLevel

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hr_agent.agent.langgraph_agent import HRAgentLangGraph
from hr_agent.configs.config import get_langfuse_client


class EvalRunner:
    """
    Runs evaluation cases and collects metrics.

    Features:
    - Parallel execution
    - Detailed logging with multiple verbosity levels
    - Tool call tracking
    - Latency measurement
    - LangGraph agent support
    """

    def __init__(
        self,
        dataset: EvalDataset | None = None,
        parallel: bool = False,
        max_workers: int = 4,
        verbose: bool = True,
        log_level: LogLevel | None = None,
        max_retries: int = 5,
        retry_base_delay_s: float = 1.0,
        batch_tag: str | None = None,
    ):
        self.dataset = dataset or get_default_dataset()
        self.parallel = parallel
        self.max_workers = max_workers
        self.results: list[EvalResult] = []
        self.max_retries = max_retries
        self.retry_base_delay_s = retry_base_delay_s
        self.run_id = datetime.utcnow().strftime("evalrun_%Y%m%d_%H%M%S")
        self.batch_tag = batch_tag

        # Set up logger
        if log_level is not None:
            self.logger = EvalLogger(level=log_level)
        elif verbose:
            self.logger = EvalLogger(level=LogLevel.NORMAL)
        else:
            self.logger = EvalLogger(level=LogLevel.QUIET)

    def run(self) -> EvalMetrics:
        """Run all evaluation cases and return metrics."""
        self.results = []

        self.logger.start_run(
            dataset_name=f"{self.dataset.name} (LangGraph Agent)",
            total_cases=len(self.dataset.cases),
            parallel=self.parallel,
        )

        if self.parallel:
            self._run_parallel()
        else:
            self._run_sequential()

        metrics = EvalMetrics(results=self.results)
        self.logger.end_run(metrics)

        self._log_langfuse_run_summary(metrics)

        return metrics

    def _log_langfuse_case_metrics(self, result: EvalResult, session_id: str) -> None:
        client = get_langfuse_client()
        if not client:
            return

        metadata = {
            "eval_run_id": self.run_id,
            "eval_batch": self.batch_tag or "",
            "eval_dataset": self.dataset.name,
            "eval_case_id": result.case_id,
            "eval_category": result.category.value,
            "eval_difficulty": result.difficulty.value,
        }

        client.create_score(
            name="eval_pass",
            value=1.0 if result.passed else 0.0,
            data_type="BOOLEAN",
            session_id=session_id,
            metadata=metadata,
        )
        client.create_score(
            name="eval_tool_selection",
            value=1.0 if result.tool_selection_correct else 0.0,
            data_type="BOOLEAN",
            session_id=session_id,
            metadata=metadata,
        )
        client.create_score(
            name="eval_answer_quality",
            value=1.0 if result.answer_correct else 0.0,
            data_type="BOOLEAN",
            session_id=session_id,
            metadata=metadata,
        )
        client.create_score(
            name="eval_authorization",
            value=1.0 if result.authorization_correct else 0.0,
            data_type="BOOLEAN",
            session_id=session_id,
            metadata=metadata,
        )
        client.create_score(
            name="eval_latency_ms",
            value=float(result.latency_ms or 0.0),
            data_type="NUMERIC",
            session_id=session_id,
            metadata=metadata,
        )
        client.create_score(
            name="eval_steps",
            value=float(result.num_steps or 0),
            data_type="NUMERIC",
            session_id=session_id,
            metadata=metadata,
        )

    def _log_langfuse_run_summary(self, metrics: EvalMetrics) -> None:
        client = get_langfuse_client()
        if not client:
            return

        session_id = f"eval_run_{self.run_id}"
        metadata = {
            "eval_run_id": self.run_id,
            "eval_batch": self.batch_tag or "",
            "eval_dataset": self.dataset.name,
            "eval_total_cases": metrics.total_cases,
        }

        client.create_score(
            name="eval_pass_rate",
            value=metrics.pass_rate * 100.0,
            data_type="NUMERIC",
            session_id=session_id,
            metadata=metadata,
        )
        client.create_score(
            name="eval_tool_selection_accuracy",
            value=metrics.tool_selection_accuracy * 100.0,
            data_type="NUMERIC",
            session_id=session_id,
            metadata=metadata,
        )
        client.create_score(
            name="eval_answer_accuracy",
            value=metrics.answer_accuracy * 100.0,
            data_type="NUMERIC",
            session_id=session_id,
            metadata=metadata,
        )
        client.create_score(
            name="eval_authorization_compliance",
            value=metrics.authorization_compliance * 100.0,
            data_type="NUMERIC",
            session_id=session_id,
            metadata=metadata,
        )
        client.create_score(
            name="eval_avg_latency_ms",
            value=metrics.avg_latency_ms,
            data_type="NUMERIC",
            session_id=session_id,
            metadata=metadata,
        )
        client.create_score(
            name="eval_p95_latency_ms",
            value=metrics.p95_latency_ms,
            data_type="NUMERIC",
            session_id=session_id,
            metadata=metadata,
        )
        client.create_score(
            name="eval_avg_steps",
            value=metrics.avg_steps,
            data_type="NUMERIC",
            session_id=session_id,
            metadata=metadata,
        )

        # Ensure scores are sent before process exit
        try:
            client.flush()
        except Exception:
            pass

    def _run_sequential(self):
        """Run cases one at a time."""
        for case in self.dataset.cases:
            self.logger.start_case(case)

            result = self._run_single_case(case)
            self.results.append(result)

            self.logger.end_case(result)

    def _run_parallel(self):
        """Run cases in parallel."""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_case = {
                executor.submit(self._run_single_case, case): case
                for case in self.dataset.cases
            }

            # We log start_case here to maintain order, even though execution is parallel
            for case in self.dataset.cases:
                self.logger.start_case(case)

            # Process results as they complete
            completed_results = {}
            for future in as_completed(future_to_case):
                case = future_to_case[future]
                try:
                    result = future.result()
                    completed_results[case.id] = result
                except (RuntimeError, ValueError, TimeoutError) as e:
                    # Create a failed result if the case execution itself fails
                    error_result = self._create_error_result(case, e)
                    completed_results[case.id] = error_result
                    self.logger.error(f"Execution failed for {case.id}: {e}")

            # Log end_case in the original order
            for case in self.dataset.cases:
                result = completed_results.get(case.id)
                if result:
                    self.results.append(result)
                    self.logger.end_case(result)
                else:
                    # This should not happen if logic is correct
                    self.logger.error(f"No result found for case {case.id}")

    def _is_rate_limit_error(self, response_or_error: str) -> bool:
        text = (response_or_error or "").lower()
        return (
            "error code: 429" in text
            or "request_limit_exceeded" in text
            or "rate limit" in text
            or "too many requests" in text
        )

    def _run_single_case(self, case: EvalCase) -> EvalResult:
        """Run a single evaluation case."""
        result = EvalResult(
            case_id=case.id,
            category=case.category,
            difficulty=case.difficulty,
            query=case.query,
            expected_tools=case.expected_tools,
            expected_answer_contains=case.expected_answer_contains,
        )

        try:
            start_time = time.time()

            # Retry loop for transient 429/QPS issues
            last_error: str | None = None
            response: str | None = None
            agent: HRAgentLangGraph | None = None

            eval_session_id = f"eval_{case.id}"
            for attempt in range(self.max_retries + 1):
                try:
                    trace_metadata = {
                        "run_type": "eval",
                        "eval_batch": self.batch_tag or "",
                        "eval_dataset": self.dataset.name,
                        "eval_case_id": case.id,
                        "eval_category": case.category.value,
                        "eval_difficulty": case.difficulty.value,
                    }
                    agent = HRAgentLangGraph(
                        case.user_email,
                        session_id=eval_session_id,
                        trace_metadata=trace_metadata,
                    )
                    response = agent.chat(case.query)

                    # Some providers return rate limit as a *string response*.
                    if isinstance(response, str) and self._is_rate_limit_error(
                        response
                    ):
                        raise RuntimeError(response)

                    break  # success
                except Exception as e:  # noqa: BLE001
                    last_error = str(e)
                    if (
                        not self._is_rate_limit_error(last_error)
                        or attempt >= self.max_retries
                    ):
                        raise

                    # exponential backoff with jitter
                    delay = (self.retry_base_delay_s * (2**attempt)) + random.random()
                    time.sleep(delay)

            end_time = time.time()
            result.latency_ms = (end_time - start_time) * 1000
            result.actual_response = response or ""

            # Extract tool calls
            tools_called = self._extract_tool_calls(agent, case.query) if agent else []
            result.tools_called = tools_called

            # Evaluate tool selection (with alternates)
            result.tool_selection_correct = self._evaluate_tool_selection(
                case.expected_tools, tools_called, getattr(case, "alternate_tools", [])
            )

            # Evaluate answer content (with alternates)
            result.answer_correct = self._evaluate_answer(
                result.actual_response,
                case.expected_answer_contains,
                case.expected_answer_not_contains,
                getattr(case, "alternate_answer_contains", []),
            )

            # Evaluate authorization
            if case.should_be_denied:
                result.authorization_correct = self._check_access_denied(
                    result.actual_response
                )
            else:
                result.authorization_correct = not self._check_access_denied(
                    result.actual_response
                )

            result.num_steps = max(1, len(tools_called))
            result.passed = (
                result.tool_selection_correct
                and result.answer_correct
                and result.authorization_correct
            )

        except (RuntimeError, ValueError, KeyError, TypeError) as e:
            result.error = str(e)
            result.passed = False

        try:
            self._log_langfuse_case_metrics(result, eval_session_id)
        except Exception:
            pass

        return result

    def _create_error_result(self, case: EvalCase, error: Exception) -> EvalResult:
        """Create an EvalResult for a case that failed with an exception."""
        result = EvalResult(
            case_id=case.id,
            category=case.category,
            difficulty=case.difficulty,
            query=case.query,
            expected_tools=case.expected_tools,
            expected_answer_contains=case.expected_answer_contains,
        )
        result.error = str(error)
        result.passed = False
        return result

    def _extract_tool_calls(self, agent: HRAgentLangGraph, query: str) -> list[str]:
        """Extract which tools were called during agent execution."""
        # LangGraph agent stores tools directly
        return agent.tools_called

    def _evaluate_tool_selection(
        self,
        expected: list[str],
        actual: list[str],
        alternates: list[list[str]] | None = None,
    ) -> bool:
        """Check if the right tools were called."""
        alternates = alternates or []

        if not expected and not alternates:
            # No specific tools expected - pass if we got any reasonable response
            return True

        actual_set = set(actual)

        # Check primary expected tools
        if expected:
            expected_set = set(expected)
            # At least one expected tool should be in actual
            if len(expected_set & actual_set) > 0:
                return True

        # Check alternate tool patterns
        for alt_tools in alternates:
            alt_set = set(alt_tools)
            if len(alt_set & actual_set) > 0:
                return True

        return False

    def _evaluate_answer(
        self,
        actual_answer: str,
        expected_to_contain: list[str],
        expected_not_to_contain: list[str],
        alternates: list[list[str]],
    ) -> bool:
        """
        Check if the answer contains expected content.

        Logic:
        1. First check forbidden content - if any found, FAIL
        2. If ANY term from expected_to_contain is found, PASS
        3. If none from expected, check alternates - if ANY alternate list has a match, PASS
        4. If nothing matches, FAIL
        """
        response_lower = actual_answer.lower()
        alternates = alternates or []

        # Check forbidden content first - any match is a fail
        for term in expected_not_to_contain:
            if term.lower() in response_lower:
                return False

        # Check if ANY of the expected terms are present (not ALL)
        if expected_to_contain:
            for term in expected_to_contain:
                if term.lower() in response_lower:
                    return True  # Found at least one expected term

        # If no expected term found, check alternates
        # Each alternate is a list of terms - if ANY term in ANY alternate list matches, pass
        for alt_terms in alternates:
            if isinstance(alt_terms, list):
                for alt in alt_terms:
                    if alt.lower() in response_lower:
                        return True
            elif isinstance(alt_terms, str):
                if alt_terms.lower() in response_lower:
                    return True

        # If expected_to_contain was empty but no forbidden content, pass
        if not expected_to_contain and not alternates:
            return True

        # Nothing matched
        return False

    def _check_access_denied(self, response: str) -> bool:
        """Check if the response indicates access was denied."""
        denial_phrases = [
            "access denied",
            "not authorized",
            "don't have permission",
            "cannot access",
            "restricted",
            "only hr",  # Catch "only HR staff can", "only HR can", etc.
            "not allowed",
            "you do not have",
            "you don't have access",
            "permission denied",
            "i can't share",
            "can't provide",
            "cannot provide",
            "you do not have permission",
            "you are not authorized",
            "access error",
            "error.*access",
            "error.*denied",
            "error.*permission",
            "access.*error",
            "your own",  # "you can only view your own"
            "only.*your",  # "only view your own"
        ]
        return any(
            re.search(phrase, response, re.IGNORECASE) for phrase in denial_phrases
        )


def run_evals(
    dataset: EvalDataset | None = None,
    parallel: bool = False,
    verbose: bool = True,
    log_level: LogLevel | None = None,
    save_results: bool = True,
    output_dir: str = "eval_results",
) -> EvalMetrics:
    """
    Convenience function to run evaluations.

    Args:
        dataset: Dataset to use (default: full HR eval dataset)
        parallel: Run in parallel for speed
        verbose: Print progress (overridden by log_level if specified)
        log_level: Explicit log level (QUIET, NORMAL, VERBOSE, DEBUG)
        save_results: Save results to JSON
        output_dir: Directory for results

    Returns:
        EvalMetrics with all results and statistics
    """
    runner = EvalRunner(
        dataset=dataset,
        parallel=parallel,
        verbose=verbose,
        log_level=log_level,
    )
    metrics = runner.run()

    if save_results:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save summary
        summary_path = os.path.join(output_dir, f"eval_summary_{timestamp}.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(metrics.summary(), f, indent=2)

        # Save detailed results
        results_path = os.path.join(output_dir, f"eval_results_{timestamp}.json")
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in metrics.results], f, indent=2, default=str)

        if log_level != LogLevel.QUIET and (verbose or log_level):
            runner.logger.save_results(output_dir)

    return metrics
