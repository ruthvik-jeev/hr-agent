#!/usr/bin/env python
"""
HR Agent Evaluation Script

Run comprehensive evaluations of the HR agent and generate reports.

Usage:
    python run_evals.py                    # Run full evaluation (original agent)
    python run_evals.py --langgraph        # Run with LangGraph agent
    python run_evals.py --quick            # Run quick subset
    python run_evals.py --category auth    # Run specific category
    python run_evals.py --parallel         # Run in parallel
    python run_evals.py --verbose          # Show detailed output
    python run_evals.py --debug            # Show debug output including responses
"""

import argparse
import sys
import os

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.dirname(__file__))

from evals.runner import EvalRunner
from evals.datasets import (
    get_default_dataset,
    get_quick_dataset,
    EvalDataset,
    HR_EVAL_CASES,
)
from evals.metrics import EvalCategory, EvalDifficulty
from evals.logger import LogLevel


def main():
    parser = argparse.ArgumentParser(
        description="Run HR Agent Evaluations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_evals.py                     Run full evaluation suite (original agent)
  python run_evals.py --langgraph         Run with LangGraph agent
  python run_evals.py --quick             Run quick test (easy cases only)
  python run_evals.py --category auth     Run authorization tests only
  python run_evals.py --verbose           Show detailed test output
  python run_evals.py --debug             Show full debug output with responses
  python run_evals.py --quiet             Only show final summary
        """,
    )

    # Agent selection
    agent_group = parser.add_argument_group("Agent Selection")
    agent_group.add_argument(
        "--langgraph",
        action="store_true",
        help="Use LangGraph-based agent instead of original",
    )

    # Dataset selection
    dataset_group = parser.add_argument_group("Dataset Selection")
    dataset_group.add_argument(
        "--quick", action="store_true", help="Run quick subset (easy cases only)"
    )
    dataset_group.add_argument(
        "--category",
        type=str,
        choices=[c.value for c in EvalCategory],
        help="Run specific category",
    )
    dataset_group.add_argument(
        "--difficulty",
        type=str,
        choices=[d.value for d in EvalDifficulty],
        help="Run specific difficulty level",
    )

    # Execution options
    exec_group = parser.add_argument_group("Execution Options")
    exec_group.add_argument(
        "--parallel", action="store_true", help="Run tests in parallel"
    )

    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--quiet", "-q", action="store_true", help="Minimal output (only final summary)"
    )
    output_group.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output (show test details)",
    )
    output_group.add_argument(
        "--debug", "-d", action="store_true", help="Debug output (show full responses)"
    )
    output_group.add_argument(
        "--no-color", action="store_true", help="Disable colorized output"
    )

    args = parser.parse_args()

    # Determine log level
    if args.debug:
        log_level = LogLevel.DEBUG
    elif args.verbose:
        log_level = LogLevel.VERBOSE
    elif args.quiet:
        log_level = LogLevel.QUIET
    else:
        log_level = LogLevel.NORMAL

    # Select and filter dataset
    if args.quick:
        dataset = get_quick_dataset()
    elif args.category:
        dataset = EvalDataset(
            name=f"Category: {args.category}",
            cases=[
                case for case in HR_EVAL_CASES if case.category.value == args.category
            ],
        )
    elif args.difficulty:
        dataset = EvalDataset(
            name=f"Difficulty: {args.difficulty}",
            cases=[
                case
                for case in HR_EVAL_CASES
                if case.difficulty.value == args.difficulty
            ],
        )
    else:
        dataset = get_default_dataset()

    if not dataset.cases:
        print("No test cases found for the selected criteria.")
        sys.exit(0)

    # Determine agent type
    agent_type = "langgraph" if args.langgraph else "original"

    # Initialize and run the evaluation
    runner = EvalRunner(
        dataset=dataset,
        parallel=args.parallel,
        log_level=log_level,
        agent_type=agent_type,
    )

    metrics = runner.run()

    # Save results
    # save_eval_results(metrics)

    # Exit with a status code indicating success or failure
    if metrics.pass_rate < 0.8:  # 80% threshold
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
