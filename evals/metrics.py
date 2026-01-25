"""
Evaluation Metrics and Result Types

Defines the metrics we track and the structure of evaluation results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import statistics


class EvalCategory(str, Enum):
    """Categories of evaluation tests."""

    EMPLOYEE_INFO = "employee_info"
    ORGANIZATION = "organization"
    TIME_OFF = "time_off"
    COMPENSATION = "compensation"
    COMPANY_INFO = "company_info"
    AUTHORIZATION = "authorization"
    MULTI_TURN = "multi_turn"
    EDGE_CASES = "edge_cases"


class EvalDifficulty(str, Enum):
    """Difficulty levels for test cases."""

    EASY = "easy"  # Direct questions, single tool
    MEDIUM = "medium"  # Requires reasoning or multiple tools
    HARD = "hard"  # Complex multi-step, ambiguous, or edge cases


@dataclass
class EvalResult:
    """Result of a single evaluation case."""

    case_id: str
    category: EvalCategory
    difficulty: EvalDifficulty
    query: str
    expected_tools: list[str]
    expected_answer_contains: list[str]

    # Measured values
    passed: bool = False
    actual_response: str = ""
    tools_called: list[str] = field(default_factory=list)
    tool_selection_correct: bool = False
    answer_correct: bool = False
    authorization_correct: bool = True

    # Performance metrics
    num_steps: int = 0
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    # Error tracking
    error: str | None = None

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "case_id": self.case_id,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "query": self.query,
            "passed": self.passed,
            "tool_selection_correct": self.tool_selection_correct,
            "answer_correct": self.answer_correct,
            "authorization_correct": self.authorization_correct,
            "num_steps": self.num_steps,
            "latency_ms": self.latency_ms,
            "tools_called": self.tools_called,
            "expected_tools": self.expected_tools,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class EvalMetrics:
    """Aggregated metrics across all evaluation results."""

    results: list[EvalResult] = field(default_factory=list)

    # Computed metrics
    @property
    def total_cases(self) -> int:
        return len(self.results)

    @property
    def passed_cases(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def pass_rate(self) -> float:
        """Overall pass rate (0-1)."""
        if not self.results:
            return 0.0
        return self.passed_cases / self.total_cases

    @property
    def tool_selection_accuracy(self) -> float:
        """Rate of correct tool selection (0-1)."""
        if not self.results:
            return 0.0
        return (
            sum(1 for r in self.results if r.tool_selection_correct) / self.total_cases
        )

    @property
    def answer_accuracy(self) -> float:
        """Rate of correct answers (0-1)."""
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.answer_correct) / self.total_cases

    @property
    def authorization_compliance(self) -> float:
        """Rate of correct authorization behavior (0-1)."""
        if not self.results:
            return 0.0
        return (
            sum(1 for r in self.results if r.authorization_correct) / self.total_cases
        )

    @property
    def avg_latency_ms(self) -> float:
        """Average latency in milliseconds."""
        if not self.results:
            return 0.0
        return statistics.mean(r.latency_ms for r in self.results)

    @property
    def p50_latency_ms(self) -> float:
        """Median latency in milliseconds."""
        if not self.results:
            return 0.0
        return statistics.median(r.latency_ms for r in self.results)

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile latency in milliseconds."""
        if not self.results:
            return 0.0
        latencies = sorted(r.latency_ms for r in self.results)
        idx = int(len(latencies) * 0.95)
        return latencies[min(idx, len(latencies) - 1)]

    @property
    def avg_steps(self) -> float:
        """Average number of agent steps."""
        if not self.results:
            return 0.0
        return statistics.mean(r.num_steps for r in self.results)

    @property
    def error_rate(self) -> float:
        """Rate of errors (0-1)."""
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.error) / self.total_cases

    def by_category(self) -> dict[EvalCategory, "EvalMetrics"]:
        """Group results by category."""
        grouped: dict[EvalCategory, list[EvalResult]] = {}
        for r in self.results:
            grouped.setdefault(r.category, []).append(r)
        return {cat: EvalMetrics(results=rs) for cat, rs in grouped.items()}

    def by_difficulty(self) -> dict[EvalDifficulty, "EvalMetrics"]:
        """Group results by difficulty."""
        grouped: dict[EvalDifficulty, list[EvalResult]] = {}
        for r in self.results:
            grouped.setdefault(r.difficulty, []).append(r)
        return {diff: EvalMetrics(results=rs) for diff, rs in grouped.items()}

    def summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "pass_rate": round(self.pass_rate * 100, 1),
            "tool_selection_accuracy": round(self.tool_selection_accuracy * 100, 1),
            "answer_accuracy": round(self.answer_accuracy * 100, 1),
            "authorization_compliance": round(self.authorization_compliance * 100, 1),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "p50_latency_ms": round(self.p50_latency_ms, 1),
            "p95_latency_ms": round(self.p95_latency_ms, 1),
            "avg_steps": round(self.avg_steps, 2),
            "error_rate": round(self.error_rate * 100, 1),
        }

    def detailed_report(self) -> str:
        """Generate a detailed text report."""
        lines = [
            "=" * 70,
            "HR AGENT EVALUATION REPORT",
            "=" * 70,
            "",
            "📊 OVERALL METRICS",
            "-" * 40,
            f"Total Test Cases:        {self.total_cases}",
            f"Passed:                  {self.passed_cases} ({self.pass_rate*100:.1f}%)",
            f"Tool Selection Accuracy: {self.tool_selection_accuracy*100:.1f}%",
            f"Answer Accuracy:         {self.answer_accuracy*100:.1f}%",
            f"Authorization Compliance:{self.authorization_compliance*100:.1f}%",
            f"Error Rate:              {self.error_rate*100:.1f}%",
            "",
            "⏱️ LATENCY",
            "-" * 40,
            f"Average:                 {self.avg_latency_ms:.0f}ms",
            f"Median (p50):            {self.p50_latency_ms:.0f}ms",
            f"95th percentile:         {self.p95_latency_ms:.0f}ms",
            "",
            "🔧 EFFICIENCY",
            "-" * 40,
            f"Average Steps:           {self.avg_steps:.2f}",
            "",
        ]

        # By category
        lines.append("📁 BY CATEGORY")
        lines.append("-" * 40)
        for cat, metrics in self.by_category().items():
            lines.append(
                f"  {cat.value:20} {metrics.pass_rate*100:5.1f}% ({metrics.passed_cases}/{metrics.total_cases})"
            )
        lines.append("")

        # By difficulty
        lines.append("📈 BY DIFFICULTY")
        lines.append("-" * 40)
        for diff, metrics in self.by_difficulty().items():
            lines.append(
                f"  {diff.value:20} {metrics.pass_rate*100:5.1f}% ({metrics.passed_cases}/{metrics.total_cases})"
            )
        lines.append("")

        # Failed cases
        failed = [r for r in self.results if not r.passed]
        if failed:
            lines.append("❌ FAILED CASES")
            lines.append("-" * 40)
            for r in failed[:10]:  # Show first 10 failures
                lines.append(f"  [{r.case_id}] {r.query[:50]}...")
                if r.error:
                    lines.append(f"    Error: {r.error}")
                else:
                    lines.append(
                        f"    Expected tools: {r.expected_tools}, Got: {r.tools_called}"
                    )
            if len(failed) > 10:
                lines.append(f"  ... and {len(failed) - 10} more failures")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)
