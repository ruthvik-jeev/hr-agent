"""
Evaluation Logger

Provides structured, colorful logging for evaluation runs.
Supports different verbosity levels and output formats.
"""

import sys
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict


# =========================================================================
# Data Models
# =========================================================================


class LogLevel(Enum):
    """Log verbosity levels."""

    QUIET = 0  # Only final summary
    NORMAL = 1  # Progress + summary
    VERBOSE = 2  # Progress + details + summary
    DEBUG = 3  # Everything including responses

    def __ge__(self, other):
        if isinstance(other, LogLevel):
            return self.value >= other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, LogLevel):
            return self.value > other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, LogLevel):
            return self.value <= other.value
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, LogLevel):
            return self.value < other.value
        return NotImplemented


@dataclass
class LogRecord:
    """A structured record for a log event."""

    level: LogLevel
    event: str  # e.g., 'run_start', 'case_end', 'summary'
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    error: Exception | None = None


# =========================================================================
# Formatting
# =========================================================================


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    # Background
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def supports_color() -> bool:
    """Check if terminal supports colors."""
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


class LogFormatter:
    """Base class for log formatters."""

    def format(self, record: LogRecord) -> None:
        """Format and print a log record."""
        raise NotImplementedError


class ConsoleFormatter(LogFormatter):
    """Formats log records for colorful console output."""

    def __init__(self, use_color: bool = True):
        self.use_color = use_color and supports_color()

    def format(self, record: LogRecord) -> None:
        """Format and print a log record to the console."""
        handler = getattr(self, f"_handle_{record.event}", self._handle_default)
        handler(record)

    def _c(self, text: str, color: str) -> str:
        """Apply color if enabled."""
        if self.use_color:
            return f"{color}{text}{Colors.RESET}"
        return text

    def _bold(self, text: str) -> str:
        return self._c(text, Colors.BOLD)

    def _dim(self, text: str) -> str:
        return self._c(text, Colors.DIM)

    def _success(self, text: str) -> str:
        return self._c(text, Colors.GREEN)

    def _error(self, text: str) -> str:
        return self._c(text, Colors.RED)

    def _warning(self, text: str) -> str:
        return self._c(text, Colors.YELLOW)

    def _info(self, text: str) -> str:
        return self._c(text, Colors.CYAN)

    def _highlight(self, text: str) -> str:
        return self._c(text, Colors.MAGENTA)

    def _handle_default(self, record: LogRecord):
        """Default handler for unknown events."""
        if record.message:
            print(f"[{record.event}] {record.message}")

    def _handle_run_start(self, record: LogRecord):
        """Log the start of an evaluation run."""
        data = record.data
        start_time = data["start_time"]
        print()
        print(self._bold("=" * 70))
        print(self._bold("  🧪 HR AGENT EVALUATION RUN"))
        print(self._bold("=" * 70))
        print()
        print(f"  📋 Dataset:    {self._info(data['dataset_name'])}")
        print(f"  📊 Test Cases: {self._info(str(data['total_cases']))}")
        print(
            f"  ⚡ Mode:       {self._info('Parallel' if data['parallel'] else 'Sequential')}"
        )
        print(f"  🕐 Started:    {self._dim(start_time.strftime('%Y-%m-%d %H:%M:%S'))}")
        print()
        print(self._bold("-" * 70))
        print()

    def _handle_run_end(self, record: LogRecord):
        """Log the end of an evaluation run with summary."""
        metrics = record.data["metrics"]
        duration = record.data["duration"]

        print()
        print(self._bold("=" * 70))
        print(self._bold("  📊 EVALUATION RESULTS"))
        print(self._bold("=" * 70))
        print()

        # Overall metrics
        pass_rate = metrics.pass_rate * 100
        pass_color = (
            Colors.GREEN
            if pass_rate >= 80
            else (Colors.YELLOW if pass_rate >= 60 else Colors.RED)
        )

        print(f"  {self._bold('Overall Results')}")
        print(f"  {'-' * 40}")
        print(f"  Total Cases:      {metrics.total_cases}")
        print(
            f"  Passed:           {self._c(f'{metrics.passed_cases}', pass_color)} / {metrics.total_cases}"
        )
        print(f"  Pass Rate:        {self._c(f'{pass_rate:.1f}%', pass_color)}")
        print()

        # Accuracy metrics
        print(f"  {self._bold('Accuracy Metrics')}")
        print(f"  {'-' * 40}")
        self._print_metric("Tool Selection", metrics.tool_selection_accuracy * 100)
        self._print_metric("Answer Quality", metrics.answer_accuracy * 100)
        self._print_metric("Authorization", metrics.authorization_compliance * 100)
        print()

        # Performance metrics
        print(f"  {self._bold('Performance')}")
        print(f"  {'-' * 40}")
        print(f"  Avg Latency:      {metrics.avg_latency_ms:.0f}ms")
        print(f"  Median (p50):     {metrics.p50_latency_ms:.0f}ms")
        print(f"  95th Percentile:  {metrics.p95_latency_ms:.0f}ms")
        print(f"  Avg Steps:        {metrics.avg_steps:.2f}")
        print(f"  Total Duration:   {duration:.1f}s")
        print()

        # By category
        print(f"  {self._bold('Results by Category')}")
        print(f"  {'-' * 40}")
        for cat, cat_metrics in metrics.by_category().items():
            self._print_summary_line(
                cat.value,
                cat_metrics.pass_rate,
                cat_metrics.passed_cases,
                cat_metrics.total_cases,
            )
        print()

        # By difficulty
        print(f"  {self._bold('Results by Difficulty')}")
        print(f"  {'-' * 40}")
        for diff, diff_metrics in metrics.by_difficulty().items():
            self._print_summary_line(
                diff.value,
                diff_metrics.pass_rate,
                diff_metrics.passed_cases,
                diff_metrics.total_cases,
            )
        print()

        # Failed cases
        failed = [r for r in metrics.results if not r.passed]
        if failed:
            print(f"  {self._bold(self._error('Failed Cases'))}")
            print(f"  {'-' * 40}")
            for r in failed[:10]:
                print(f"  {self._error('✗')} [{r.case_id}] {r.query[:45]}...")
                if r.error:
                    print(f"    {self._dim('Error:')} {r.error}")
                elif record.level >= LogLevel.VERBOSE:
                    print(f"    {self._dim('Expected tools:')} {r.expected_tools}")
                    print(f"    {self._dim('Actual tools:')}   {r.tools_called}")
            if len(failed) > 10:
                print(f"  {self._dim(f'... and {len(failed) - 10} more failures')}")
            print()

        # Final verdict
        print(self._bold("=" * 70))
        if pass_rate >= 80:
            print(self._success(f"  ✅ EVALUATION PASSED ({pass_rate:.1f}% pass rate)"))
        else:
            print(self._error(f"  ❌ EVALUATION FAILED ({pass_rate:.1f}% pass rate)"))
        print(self._bold("=" * 70))
        print()

    def _print_summary_line(self, name: str, pass_rate: float, passed: int, total: int):
        pct = pass_rate * 100
        bar = self._progress_bar(pct, width=20)
        color = (
            Colors.GREEN if pct == 100 else (Colors.YELLOW if pct >= 80 else Colors.RED)
        )
        print(f"  {name:20} {bar} {self._c(f'{pct:5.1f}%', color)} ({passed}/{total})")

    def _print_metric(self, name: str, value: float):
        """Print a metric with color coding."""
        color = (
            Colors.GREEN
            if value >= 90
            else (Colors.YELLOW if value >= 70 else Colors.RED)
        )
        print(f"  {name:18} {self._c(f'{value:.1f}%', color)}")

    def _progress_bar(self, percentage: float, width: int = 20) -> str:
        """Create a text progress bar."""
        filled = int(width * percentage / 100)
        empty = width - filled

        if self.use_color:
            color = (
                Colors.GREEN
                if percentage == 100
                else (Colors.YELLOW if percentage >= 80 else Colors.RED)
            )
            bar = f"{color}{'█' * filled}{Colors.DIM}{'░' * empty}{Colors.RESET}"
        else:
            bar = f"[{'#' * filled}{'-' * empty}]"

        return bar

    def _handle_case_start(self, record: LogRecord):
        """Log the start of a test case."""
        data = record.data
        case = data["case"]
        progress = f"[{data['current']}/{data['total']}]"
        query = case.query

        if data["level"] >= LogLevel.VERBOSE:
            print(f"{self._dim(progress)} {self._info(case.id)}")
            print(f"  {self._dim('Category:')}   {case.category.value}")
            print(f"  {self._dim('Difficulty:')} {case.difficulty.value}")
            print(
                f"  {self._dim('Query:')}      {query[:60]}{'...' if len(query) > 60 else ''}"
            )
        else:
            print(
                f"{self._dim(progress)} {case.id}: {query[:50]}...",
                end=" ",
                flush=True,
            )

    def _handle_case_end(self, record: LogRecord):
        """Log the result of a test case."""
        result = record.data["result"]

        if result.passed:
            status = self._success("✅ PASS")
        else:
            status = self._error("❌ FAIL")

        latency = f"{result.latency_ms:.0f}ms"
        steps = f"{result.num_steps} steps"

        if record.data["level"] >= LogLevel.VERBOSE:
            print(f"  {self._dim('Status:')}     {status}")
            print(f"  {self._dim('Latency:')}    {latency}")
            print(f"  {self._dim('Steps:')}      {steps}")
            print(f"  {self._dim('Tools:')}      {result.tools_called}")

            if record.data["level"] >= LogLevel.DEBUG:
                print(f"  {self._dim('Response:')}   {result.actual_response[:200]}...")

            if not result.passed:
                if result.error:
                    print(f"  {self._error('Error:')}      {result.error}")
                else:
                    print(f"  {self._warning('Expected:')}   {result.expected_tools}")
                    print(f"  {self._warning('Got:')}        {result.tools_called}")
        print()

    def _handle_info(self, record: LogRecord):
        print(f"{self._info('ℹ')} {record.message}")

    def _handle_success(self, record: LogRecord):
        print(f"{self._success('✓')} {record.message}")

    def _handle_warning(self, record: LogRecord):
        print(f"{self._warning('⚠')} {record.message}")

    def _handle_error(self, record: LogRecord):
        print(f"{self._error('✗')} {record.message}")

    def _handle_debug(self, record: LogRecord):
        print(f"{self._dim('[DEBUG]')} {record.message}")

    def _handle_save_results(self, record: LogRecord):
        print(
            f"{self._info('📁')} Results saved to {self._highlight(record.data['path'])}"
        )


# =========================================================================
# Logger
# =========================================================================


class EvalLogger:
    """
    Structured logger for evaluation runs.

    Orchestrates logging by creating LogRecords and passing them to a formatter.
    """

    def __init__(
        self,
        level: LogLevel = LogLevel.NORMAL,
        formatter: LogFormatter | None = None,
        use_color: bool = True,
    ):
        self.level = level
        self.formatter = formatter or ConsoleFormatter(use_color=use_color)
        self.start_time: datetime | None = None
        self.current_case_num: int = 0
        self.total_cases: int = 0

    def _log(self, record: LogRecord):
        """Log a record if its level is high enough."""
        if self.level >= record.level:
            self.formatter.format(record)

    def start_run(self, dataset_name: str, total_cases: int, parallel: bool = False):
        """Log the start of an evaluation run."""
        self.start_time = datetime.now()
        self.total_cases = total_cases
        self.current_case_num = 0
        self._log(
            LogRecord(
                level=LogLevel.NORMAL,
                event="run_start",
                data={
                    "dataset_name": dataset_name,
                    "total_cases": total_cases,
                    "parallel": parallel,
                    "start_time": self.start_time,
                },
            )
        )

    def end_run(self, metrics: Any):
        """Log the end of an evaluation run with summary."""
        duration = (
            (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        )
        self._log(
            LogRecord(
                level=LogLevel.QUIET,
                event="run_end",
                data={"metrics": metrics, "duration": duration, "level": self.level},
            )
        )

    def start_case(self, case: Any):
        """Log the start of a test case."""
        self.current_case_num += 1
        self._log(
            LogRecord(
                level=LogLevel.NORMAL,
                event="case_start",
                data={
                    "case": case,
                    "current": self.current_case_num,
                    "total": self.total_cases,
                    "level": self.level,
                },
            )
        )

    def end_case(self, result: Any):
        """Log the result of a test case."""
        self._log(
            LogRecord(
                level=LogLevel.NORMAL,
                event="case_end",
                data={"result": result, "level": self.level},
            )
        )

    def info(self, message: str):
        """Log an info message."""
        self._log(LogRecord(level=LogLevel.NORMAL, event="info", message=message))

    def success(self, message: str):
        """Log a success message."""
        self._log(LogRecord(level=LogLevel.NORMAL, event="success", message=message))

    def warning(self, message: str):
        """Log a warning message."""
        self._log(LogRecord(level=LogLevel.NORMAL, event="warning", message=message))

    def error(self, message: str):
        """Log an error message."""
        self._log(LogRecord(level=LogLevel.QUIET, event="error", message=message))

    def debug(self, message: str):
        """Log a debug message."""
        self._log(LogRecord(level=LogLevel.DEBUG, event="debug", message=message))

    def save_results(self, path: str):
        """Log that results were saved."""
        self._log(
            LogRecord(level=LogLevel.NORMAL, event="save_results", data={"path": path})
        )
