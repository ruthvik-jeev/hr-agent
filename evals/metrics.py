"""
Evaluation Metrics and Result Types

Defines the metrics we track and the structure of evaluation results.
Includes quality-gate thresholds used by CI/CD to fail builds on regressions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import statistics


# ── Quality-gate thresholds (PBI DoD §4 / §5) ────────────────────────────────
# Each value is the *minimum* acceptable score (0-1 scale).  The leakage rate
# is the *maximum* (lower is better → zero tolerance).
QUALITY_GATES: dict[str, float] = {
    "pass_rate": 0.80,  # overall eval pass-rate
    "tool_selection_accuracy": 0.85,  # correct tool picked
    "answer_accuracy": 0.80,  # answer contains expected content
    "authorization_compliance": 1.00,  # zero tolerance
    "queue_ordering_accuracy": 0.90,  # sorting engine
    "slot_fill_completion": 0.85,  # required fields gathered
    "escalation_precision": 0.80,  # escalation correct when triggered
    "escalation_recall": 0.80,  # all real escalations caught
    "pii_leakage_rate": 0.00,  # max acceptable – zero tolerance
    "p95_latency_ms": 15_000,  # ≤ 15 s
    "dashboard_load_p95_ms": 3_000,  # ≤ 3 s for UI refresh
}


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
    ESCALATION = "escalation"
    PII_LEAKAGE = "pii_leakage"


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

    # Escalation tracking
    escalation_expected: bool = False
    escalation_triggered: bool = False

    # PII leakage tracking
    pii_leaked: bool = False

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
            "escalation_expected": self.escalation_expected,
            "escalation_triggered": self.escalation_triggered,
            "pii_leaked": self.pii_leaked,
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

    # ── Escalation precision / recall ─────────────────────────────────────
    @property
    def escalation_precision(self) -> float:
        """Of all cases where escalation was triggered, how many were expected?"""
        triggered = [r for r in self.results if r.escalation_triggered]
        if not triggered:
            return 1.0  # nothing triggered → no false positives
        return sum(1 for r in triggered if r.escalation_expected) / len(triggered)

    @property
    def escalation_recall(self) -> float:
        """Of all cases that *should* have escalated, how many actually did?"""
        expected = [r for r in self.results if r.escalation_expected]
        if not expected:
            return 1.0  # nothing expected → recall is vacuously 1
        return sum(1 for r in expected if r.escalation_triggered) / len(expected)

    # ── PII leakage rate ──────────────────────────────────────────────────
    @property
    def pii_leakage_rate(self) -> float:
        """Fraction of responses that leaked PII (0 = no leaks)."""
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.pii_leaked) / self.total_cases

    # ── Quality-gate checker ──────────────────────────────────────────────
    def check_quality_gates(
        self, gates: dict[str, float] | None = None
    ) -> tuple[bool, list[str]]:
        """Check all quality gates and return (passed, list-of-failures).

        Each gate maps a metric name to a threshold.  Metrics ending in
        ``_rate`` or ``_ms`` where lower is better use ≤ comparison;
        everything else uses ≥.

        Returns:
            (all_passed, failures)  where failures is a list of human-readable
            strings describing each breach.
        """
        gates = gates or QUALITY_GATES
        measured: dict[str, float] = {
            "pass_rate": self.pass_rate,
            "tool_selection_accuracy": self.tool_selection_accuracy,
            "answer_accuracy": self.answer_accuracy,
            "authorization_compliance": self.authorization_compliance,
            "escalation_precision": self.escalation_precision,
            "escalation_recall": self.escalation_recall,
            "pii_leakage_rate": self.pii_leakage_rate,
            "p95_latency_ms": self.p95_latency_ms,
        }
        lower_is_better = {
            "pii_leakage_rate",
            "p95_latency_ms",
            "dashboard_load_p95_ms",
        }
        failures: list[str] = []

        for name, threshold in gates.items():
            actual = measured.get(name)
            if actual is None:
                continue  # metric not available yet (e.g. dashboard_load)
            if name in lower_is_better:
                if actual > threshold:
                    failures.append(f"{name}: {actual:.4f} > max {threshold:.4f}")
            else:
                if actual < threshold:
                    failures.append(f"{name}: {actual:.4f} < min {threshold:.4f}")

        return (len(failures) == 0, failures)

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
        all_passed, gate_failures = self.check_quality_gates()
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "pass_rate": round(self.pass_rate * 100, 1),
            "tool_selection_accuracy": round(self.tool_selection_accuracy * 100, 1),
            "answer_accuracy": round(self.answer_accuracy * 100, 1),
            "authorization_compliance": round(self.authorization_compliance * 100, 1),
            "escalation_precision": round(self.escalation_precision * 100, 1),
            "escalation_recall": round(self.escalation_recall * 100, 1),
            "pii_leakage_rate": round(self.pii_leakage_rate * 100, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "p50_latency_ms": round(self.p50_latency_ms, 1),
            "p95_latency_ms": round(self.p95_latency_ms, 1),
            "avg_steps": round(self.avg_steps, 2),
            "error_rate": round(self.error_rate * 100, 1),
            "quality_gates_passed": all_passed,
            "quality_gate_failures": gate_failures,
        }

    def detailed_report(self) -> str:
        """Generate a detailed text report."""
        all_passed, gate_failures = self.check_quality_gates()
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
            f"Escalation Precision:    {self.escalation_precision*100:.1f}%",
            f"Escalation Recall:       {self.escalation_recall*100:.1f}%",
            f"PII Leakage Rate:        {self.pii_leakage_rate*100:.2f}%",
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

        # Quality gates
        gate_status = "PASSED" if all_passed else "FAILED"
        lines.append(f"🚦 QUALITY GATES: {gate_status}")
        lines.append("-" * 40)
        if gate_failures:
            for f in gate_failures:
                lines.append(f"  ✗ {f}")
        else:
            lines.append("  All gates passed.")
        lines.append("")

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
