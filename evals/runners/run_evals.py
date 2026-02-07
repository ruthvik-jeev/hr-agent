#!/usr/bin/env python
"""
HR Agent Evaluation Script

Run comprehensive evaluations of the HR agent and generate reports.
Uses LangGraph-based agent.

Usage:
    python evals/runners/run_evals.py                    # Run full evaluation
    python evals/runners/run_evals.py --quick            # Run quick subset
    python evals/runners/run_evals.py --category auth    # Run specific category
    python evals/runners/run_evals.py --parallel         # Run in parallel
    python evals/runners/run_evals.py --verbose          # Show detailed output
    python evals/runners/run_evals.py --debug            # Show debug output including responses
"""

import argparse
import sys
import os

# Add paths
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, repo_root)

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
        description="Run HR Agent Evaluations (LangGraph)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python evals/runners/run_evals.py                     Run full evaluation suite
  python evals/runners/run_evals.py --quick             Run quick test (easy cases only)
  python evals/runners/run_evals.py --category auth     Run authorization tests only
  python evals/runners/run_evals.py --parallel          Run tests in parallel
  python evals/runners/run_evals.py --verbose           Show detailed test output
  python evals/runners/run_evals.py --debug             Show full debug output including responses
  python evals/runners/run_evals.py --generated-1000    Run synthetic 1000-case dataset (if generated)
        """,
    )

    # Dataset selection
    dataset_group = parser.add_argument_group("Dataset Selection")
    dataset_group.add_argument(
        "--quick", action="store_true", help="Run quick subset (easy cases only)"
    )
    dataset_group.add_argument(
        "--generated-1000",
        action="store_true",
        help="Run the generated 1000-case synthetic dataset (evals/generated_dataset_1000.py)",
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
    exec_group.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="Max parallel workers (lower values reduce QPS / 429 errors)",
    )
    exec_group.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Max retries for transient provider 429/QPS errors",
    )
    exec_group.add_argument(
        "--retry-base-delay",
        type=float,
        default=1.0,
        help="Base delay seconds for exponential backoff (429/QPS)",
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

    # Limit option
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of cases (0 = all). Useful for quick smoke tests.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Randomly sample N cases (0 = no sampling). Applied after filters.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed for --sample.",
    )
    parser.add_argument(
        "--sample-offset",
        type=int,
        default=0,
        help="Offset into the shuffled list when using --sample (enables disjoint batches).",
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
    if args.generated_1000:
        from evals.generated_dataset_1000 import GENERATED_DATASET_1000

        dataset = GENERATED_DATASET_1000
    elif args.quick:
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

    # Limit the number of cases if --limit is specified
    if getattr(args, "limit", 0):
        dataset = EvalDataset(
            name=f"{dataset.name}_limit_{args.limit}",
            cases=dataset.cases[: args.limit],
        )

    # Random sampling for quicker, more representative runs
    if getattr(args, "sample", 0):
        import random

        rng = random.Random(args.seed)
        shuffled = list(dataset.cases)
        rng.shuffle(shuffled)

        start = max(0, args.sample_offset)
        end = min(len(shuffled), start + args.sample)
        batch = shuffled[start:end]

        dataset = EvalDataset(
            name=f"{dataset.name}_sample_{len(batch)}_seed_{args.seed}_offset_{start}",
            cases=batch,
        )

    if not dataset.cases:
        print("No test cases found for the selected criteria.")
        sys.exit(0)

    # Initialize and run the evaluation
    runner = EvalRunner(
        dataset=dataset,
        parallel=args.parallel,
        max_workers=args.max_workers,
        log_level=log_level,
        max_retries=args.max_retries,
        retry_base_delay_s=args.retry_base_delay,
    )

    metrics = runner.run()

    # Exit with a status code indicating success or failure
    if metrics.pass_rate < 0.8:  # 80% threshold
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
