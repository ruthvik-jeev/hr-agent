"""
HR Agent Evaluation Framework

A comprehensive evaluation suite for measuring agent performance across
multiple dimensions: accuracy, efficiency, safety, and quality.

Uses LangGraph-based HRAgentLangGraph.
"""

from .runner import EvalRunner, run_evals
from .metrics import EvalMetrics, EvalResult, EvalCategory, EvalDifficulty
from .datasets import EvalDataset, EvalCase, get_default_dataset, get_quick_dataset
from .logger import EvalLogger, LogLevel

__all__ = [
    "EvalRunner",
    "run_evals",
    "EvalMetrics",
    "EvalResult",
    "EvalCategory",
    "EvalDifficulty",
    "EvalDataset",
    "EvalCase",
    "EvalLogger",
    "LogLevel",
    "get_default_dataset",
    "get_quick_dataset",
]
