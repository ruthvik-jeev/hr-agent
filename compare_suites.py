#!/usr/bin/env python
"""
Compare Test Suites Performance

Runs Suite 1, Suite 2, and Suite 3, then compares the results side by side.

Usage:
    python compare_suites.py              # Run all suites and compare
    python compare_suites.py --verbose    # With detailed output
    python compare_suites.py --suite1     # Run only suite 1
    python compare_suites.py --suite2     # Run only suite 2
    python compare_suites.py --suite3     # Run only suite 3
    python compare_suites.py --smoke      # Run quick smoke test
    python compare_suites.py --save       # Save results to JSON
"""

import argparse
import sys
import os
import json
from datetime import datetime

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.dirname(__file__))

from evals.runner import EvalRunner
from evals.test_suites import (
    get_suite_1,
    get_suite_2,
    get_suite_3,
    get_quick_smoke_test,
)
from evals.logger import LogLevel
from evals.metrics import EvalMetrics


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_metrics(name: str, metrics: EvalMetrics):
    """Print metrics for a single suite."""
    print(f"\n📊 {name}")
    print("-" * 50)
    print(f"  Total Cases:           {metrics.total_cases}")
    print(f"  Passed:                {metrics.passed_cases} / {metrics.total_cases}")
    print(f"  Pass Rate:             {metrics.pass_rate * 100:.1f}%")
    print(f"  Tool Selection:        {metrics.tool_selection_accuracy * 100:.1f}%")
    print(f"  Answer Accuracy:       {metrics.answer_accuracy * 100:.1f}%")
    print(f"  Authorization:         {metrics.authorization_compliance * 100:.1f}%")
    print(f"  Avg Latency:           {metrics.avg_latency_ms:.0f}ms")
    print(f"  Error Rate:            {metrics.error_rate * 100:.1f}%")

    # By category
    print("\n  By Category:")
    for cat, cat_metrics in metrics.by_category().items():
        bar = "█" * int(cat_metrics.pass_rate * 10) + "░" * (
            10 - int(cat_metrics.pass_rate * 10)
        )
        print(
            f"    {cat.value:20} [{bar}] {cat_metrics.pass_rate * 100:5.1f}% ({cat_metrics.passed_cases}/{cat_metrics.total_cases})"
        )

    # By difficulty
    print("\n  By Difficulty:")
    for diff, diff_metrics in metrics.by_difficulty().items():
        bar = "█" * int(diff_metrics.pass_rate * 10) + "░" * (
            10 - int(diff_metrics.pass_rate * 10)
        )
        print(
            f"    {diff.value:20} [{bar}] {diff_metrics.pass_rate * 100:5.1f}% ({diff_metrics.passed_cases}/{diff_metrics.total_cases})"
        )


def print_comparison(suite1_metrics: EvalMetrics, suite2_metrics: EvalMetrics):
    """Print side-by-side comparison of two suites."""
    print_header("📈 SUITE COMPARISON")

    def delta_str(v1: float, v2: float, is_latency: bool = False) -> str:
        """Format delta with color indication."""
        diff = v2 - v1
        if is_latency:
            # For latency, lower is better
            if diff < 0:
                return f"↓ {abs(diff):.1f} (better)"
            elif diff > 0:
                return f"↑ {diff:.1f} (worse)"
            else:
                return "→ 0 (same)"
        else:
            # For accuracy, higher is better
            if diff > 0:
                return f"↑ {diff:.1f}% (better)"
            elif diff < 0:
                return f"↓ {abs(diff):.1f}% (worse)"
            else:
                return "→ 0% (same)"

    print(f"\n{'Metric':<25} {'Suite 1':>15} {'Suite 2':>15} {'Delta':>20}")
    print("-" * 75)

    print(
        f"{'Total Cases':<25} {suite1_metrics.total_cases:>15} {suite2_metrics.total_cases:>15}"
    )
    print(
        f"{'Pass Rate':<25} {suite1_metrics.pass_rate * 100:>14.1f}% {suite2_metrics.pass_rate * 100:>14.1f}% {delta_str(suite1_metrics.pass_rate * 100, suite2_metrics.pass_rate * 100):>20}"
    )
    print(
        f"{'Tool Selection':<25} {suite1_metrics.tool_selection_accuracy * 100:>14.1f}% {suite2_metrics.tool_selection_accuracy * 100:>14.1f}% {delta_str(suite1_metrics.tool_selection_accuracy * 100, suite2_metrics.tool_selection_accuracy * 100):>20}"
    )
    print(
        f"{'Answer Accuracy':<25} {suite1_metrics.answer_accuracy * 100:>14.1f}% {suite2_metrics.answer_accuracy * 100:>14.1f}% {delta_str(suite1_metrics.answer_accuracy * 100, suite2_metrics.answer_accuracy * 100):>20}"
    )
    print(
        f"{'Authorization':<25} {suite1_metrics.authorization_compliance * 100:>14.1f}% {suite2_metrics.authorization_compliance * 100:>14.1f}% {delta_str(suite1_metrics.authorization_compliance * 100, suite2_metrics.authorization_compliance * 100):>20}"
    )
    print(
        f"{'Avg Latency (ms)':<25} {suite1_metrics.avg_latency_ms:>15.0f} {suite2_metrics.avg_latency_ms:>15.0f} {delta_str(suite1_metrics.avg_latency_ms, suite2_metrics.avg_latency_ms, is_latency=True):>20}"
    )
    print(
        f"{'Error Rate':<25} {suite1_metrics.error_rate * 100:>14.1f}% {suite2_metrics.error_rate * 100:>14.1f}% {delta_str(suite1_metrics.error_rate * 100, suite2_metrics.error_rate * 100):>20}"
    )


def print_failed_cases(name: str, metrics: EvalMetrics, max_show: int = 5):
    """Print failed test cases."""
    failed = [r for r in metrics.results if not r.passed]
    if not failed:
        print(f"\n✅ {name}: All tests passed!")
        return

    print(f"\n❌ {name} Failed Cases ({len(failed)} total):")
    print("-" * 50)
    for r in failed[:max_show]:
        print(f"  [{r.case_id}] {r.query[:50]}...")
        print(f"    Expected: {r.expected_tools}")
        print(f"    Got:      {r.tools_called}")
        if r.error:
            print(f"    Error:    {r.error}")
    if len(failed) > max_show:
        print(f"  ... and {len(failed) - max_show} more failures")


def save_results(metrics_dict: dict[str, EvalMetrics]):
    """Save comparison results to JSON file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = os.path.join(os.path.dirname(__file__), "eval_results")
    os.makedirs(results_dir, exist_ok=True)

    comparison: dict = {
        "timestamp": timestamp,
    }

    suite_names = {
        "suite_1": "Basic Functionality & Anti-Hallucination",
        "suite_2": "Advanced & Edge Cases",
        "suite_3": "Regression & Robustness",
        "smoke": "Quick Smoke Test",
    }

    for key, metrics in metrics_dict.items():
        comparison[key] = {
            "name": suite_names.get(key, key),
            "summary": metrics.summary(),
            "results": [r.to_dict() for r in metrics.results],
        }

    filepath = os.path.join(results_dir, f"suite_comparison_{timestamp}.json")
    with open(filepath, "w") as f:
        json.dump(comparison, f, indent=2, default=str)

    print(f"\n💾 Results saved to: {filepath}")


def print_multi_comparison(metrics_dict: dict[str, EvalMetrics]):
    """Print comparison across all suites."""
    print_header("📈 MULTI-SUITE COMPARISON")

    headers = ["Metric"] + list(metrics_dict.keys())
    print(f"\n{headers[0]:<25}" + "".join(f"{h:>15}" for h in headers[1:]))
    print("-" * (25 + 15 * len(metrics_dict)))

    rows = [
        ("Total Cases", lambda m: str(m.total_cases)),
        ("Pass Rate", lambda m: f"{m.pass_rate * 100:.1f}%"),
        ("Tool Selection", lambda m: f"{m.tool_selection_accuracy * 100:.1f}%"),
        ("Answer Accuracy", lambda m: f"{m.answer_accuracy * 100:.1f}%"),
        ("Authorization", lambda m: f"{m.authorization_compliance * 100:.1f}%"),
        ("Avg Latency (ms)", lambda m: f"{m.avg_latency_ms:.0f}"),
        ("Error Rate", lambda m: f"{m.error_rate * 100:.1f}%"),
    ]

    for row_name, getter in rows:
        values = [getter(m) for m in metrics_dict.values()]
        print(f"{row_name:<25}" + "".join(f"{v:>15}" for v in values))


def main():
    parser = argparse.ArgumentParser(description="Compare HR Agent Test Suites")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--suite1", action="store_true", help="Run only Suite 1")
    parser.add_argument("--suite2", action="store_true", help="Run only Suite 2")
    parser.add_argument("--suite3", action="store_true", help="Run only Suite 3")
    parser.add_argument("--smoke", action="store_true", help="Run quick smoke test")
    parser.add_argument("--all", action="store_true", help="Run all suites")
    parser.add_argument("--save", action="store_true", help="Save results to JSON")
    args = parser.parse_args()

    log_level = LogLevel.VERBOSE if args.verbose else LogLevel.NORMAL

    metrics_dict: dict[str, EvalMetrics] = {}

    # Determine which suites to run
    run_specific = args.suite1 or args.suite2 or args.suite3 or args.smoke
    run_all = args.all or not run_specific

    # Run smoke test
    if args.smoke:
        print_header("🧪 RUNNING SMOKE TEST")
        runner = EvalRunner(dataset=get_quick_smoke_test(), log_level=log_level)
        metrics_dict["smoke"] = runner.run()
        print_metrics("Smoke Test Results", metrics_dict["smoke"])
        print_failed_cases("Smoke Test", metrics_dict["smoke"])

    # Run Suite 1
    if args.suite1 or run_all:
        print_header("🧪 RUNNING SUITE 1: Basic Functionality & Anti-Hallucination")
        runner1 = EvalRunner(dataset=get_suite_1(), log_level=log_level)
        metrics_dict["suite_1"] = runner1.run()
        print_metrics("Suite 1 Results", metrics_dict["suite_1"])
        print_failed_cases("Suite 1", metrics_dict["suite_1"])

    # Run Suite 2
    if args.suite2 or run_all:
        print_header("🧪 RUNNING SUITE 2: Advanced & Edge Cases")
        runner2 = EvalRunner(dataset=get_suite_2(), log_level=log_level)
        metrics_dict["suite_2"] = runner2.run()
        print_metrics("Suite 2 Results", metrics_dict["suite_2"])
        print_failed_cases("Suite 2", metrics_dict["suite_2"])

    # Run Suite 3
    if args.suite3 or run_all:
        print_header("🧪 RUNNING SUITE 3: Regression & Robustness")
        runner3 = EvalRunner(dataset=get_suite_3(), log_level=log_level)
        metrics_dict["suite_3"] = runner3.run()
        print_metrics("Suite 3 Results", metrics_dict["suite_3"])
        print_failed_cases("Suite 3", metrics_dict["suite_3"])

    # Print comparison if multiple suites were run
    if len(metrics_dict) >= 2:
        if "suite_1" in metrics_dict and "suite_2" in metrics_dict:
            print_comparison(metrics_dict["suite_1"], metrics_dict["suite_2"])
        if len(metrics_dict) > 2:
            print_multi_comparison(metrics_dict)

    # Overall assessment
    if metrics_dict:
        print_header("📋 OVERALL ASSESSMENT")

        combined_pass = sum(m.passed_cases for m in metrics_dict.values())
        combined_total = sum(m.total_cases for m in metrics_dict.values())
        combined_rate = (
            combined_pass / combined_total * 100 if combined_total > 0 else 0
        )

        print(
            f"\n  Combined Pass Rate: {combined_pass}/{combined_total} ({combined_rate:.1f}%)"
        )

        if combined_rate >= 90:
            print("  Status: ✅ EXCELLENT - Agent performing well")
        elif combined_rate >= 75:
            print("  Status: ⚠️ GOOD - Some improvements needed")
        elif combined_rate >= 50:
            print("  Status: ⚠️ FAIR - Significant improvements needed")
        else:
            print("  Status: ❌ POOR - Major issues detected")

        # Hallucination check
        avg_tool_accuracy = sum(
            m.tool_selection_accuracy for m in metrics_dict.values()
        ) / len(metrics_dict)
        print(
            f"\n  Hallucination Prevention: {'✅ GOOD' if avg_tool_accuracy >= 0.9 else '⚠️ NEEDS WORK'} ({avg_tool_accuracy * 100:.1f}% tool selection accuracy)"
        )

        if args.save:
            save_results(metrics_dict)

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
