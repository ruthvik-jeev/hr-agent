#!/usr/bin/env python
"""
Compare HR Agent Implementations

Run evaluations on both the original and LangGraph agents and compare results.

Usage:
    python compare_agents.py                  # Compare on quick dataset
    python compare_agents.py --full           # Compare on full dataset
    python compare_agents.py --verbose        # Show detailed output
    python compare_agents.py --save           # Save comparison results
"""

import argparse
import json
import os
from datetime import datetime
import sys

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.dirname(__file__))

from evals.runner import EvalRunner, AgentType
from evals.datasets import get_default_dataset, get_quick_dataset
from evals.logger import LogLevel


def run_comparison(
    dataset_name: str = "quick", verbose: bool = False, save: bool = False
):
    """Run evaluation with both agents and compare results."""

    # Get dataset
    if dataset_name == "full":
        dataset = get_default_dataset()
    else:
        dataset = get_quick_dataset()

    # Determine log level
    log_level = LogLevel.VERBOSE if verbose else LogLevel.NORMAL

    results = {}

    print("=" * 70)
    print("  🔬 HR AGENT COMPARISON")
    print("=" * 70)
    print(f"  Dataset: {dataset.name} ({len(dataset.cases)} cases)")
    print("=" * 70)

    for agent_type in ["original", "langgraph"]:
        print(f"\n{'=' * 70}")
        print(f"  Running with {agent_type.upper()} Agent")
        print("=" * 70)

        runner = EvalRunner(
            dataset=dataset,
            parallel=False,
            log_level=log_level,
            agent_type=agent_type,  # type: ignore
        )

        metrics = runner.run()

        results[agent_type] = {
            "pass_rate": metrics.pass_rate,
            "tool_selection_accuracy": metrics.tool_selection_accuracy,
            "answer_accuracy": metrics.answer_accuracy,
            "authorization_compliance": metrics.authorization_compliance,
            "avg_latency_ms": metrics.avg_latency_ms,
            "p50_latency_ms": metrics.p50_latency_ms,
            "p95_latency_ms": metrics.p95_latency_ms,
            "avg_steps": metrics.avg_steps,
            "total_cases": len(metrics.results),
            "passed_cases": len([r for r in metrics.results if r.passed]),
            "failed_cases": [r.case_id for r in metrics.results if not r.passed],
        }

    # Print comparison
    print("\n")
    print("=" * 70)
    print("  📊 COMPARISON RESULTS")
    print("=" * 70)

    metrics_to_compare = [
        ("Pass Rate", "pass_rate", True, "%"),
        ("Tool Selection", "tool_selection_accuracy", True, "%"),
        ("Answer Accuracy", "answer_accuracy", True, "%"),
        ("Authorization", "authorization_compliance", True, "%"),
        ("Avg Latency", "avg_latency_ms", False, "ms"),
        ("P50 Latency", "p50_latency_ms", False, "ms"),
        ("P95 Latency", "p95_latency_ms", False, "ms"),
        ("Avg Steps", "avg_steps", False, ""),
    ]

    print(f"\n  {'Metric':<20} {'Original':>15} {'LangGraph':>15} {'Winner':>12}")
    print("  " + "-" * 64)

    for name, key, higher_better, unit in metrics_to_compare:
        orig = results["original"][key]
        lg = results["langgraph"][key]

        if unit == "%":
            orig_str = f"{orig * 100:.1f}%"
            lg_str = f"{lg * 100:.1f}%"
        elif unit == "ms":
            orig_str = f"{orig:.0f}ms"
            lg_str = f"{lg:.0f}ms"
        else:
            orig_str = f"{orig:.2f}"
            lg_str = f"{lg:.2f}"

        # Determine winner
        if higher_better:
            winner = "Original" if orig > lg else ("LangGraph" if lg > orig else "Tie")
        else:
            winner = "Original" if orig < lg else ("LangGraph" if lg < orig else "Tie")

        print(f"  {name:<20} {orig_str:>15} {lg_str:>15} {winner:>12}")

    # Print failed cases comparison
    print(f"\n  Failed Cases:")
    print(f"  " + "-" * 64)
    print(
        f"  {'Original:':<15} {', '.join(results['original']['failed_cases']) or 'None'}"
    )
    print(
        f"  {'LangGraph:':<15} {', '.join(results['langgraph']['failed_cases']) or 'None'}"
    )

    print("\n" + "=" * 70)

    # Save results if requested
    if save:
        os.makedirs("eval_results", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        comparison = {
            "timestamp": timestamp,
            "dataset": dataset.name,
            "total_cases": len(dataset.cases),
            "results": results,
        }

        filepath = os.path.join("eval_results", f"agent_comparison_{timestamp}.json")
        with open(filepath, "w") as f:
            json.dump(comparison, f, indent=2, default=str)
        print(f"\n  📁 Results saved to: {filepath}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Compare HR Agent Implementations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Run on full dataset instead of quick",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output for each test",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save comparison results to file",
    )

    args = parser.parse_args()

    dataset_name = "full" if args.full else "quick"
    run_comparison(dataset_name=dataset_name, verbose=args.verbose, save=args.save)


if __name__ == "__main__":
    main()
