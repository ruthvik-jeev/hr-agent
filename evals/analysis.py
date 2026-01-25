"""
HR Agent Evaluation Analysis

Generate visualizations and detailed analysis of evaluation results.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any

try:
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    plt: Any = None  # type: ignore[no-redef]

from .metrics import EvalMetrics, EvalResult, EvalCategory, EvalDifficulty


def load_results(results_dir: str = "eval_results") -> list[EvalResult]:
    """Load results from the most recent evaluation run."""
    results_path = Path(results_dir)
    if not results_path.exists():
        return []

    # Find most recent results file
    result_files = list(results_path.glob("eval_results_*.json"))
    if not result_files:
        return []

    latest = max(result_files, key=lambda p: p.stat().st_mtime)

    with open(latest) as f:
        data = json.load(f)

    results = []
    for r in data:
        results.append(
            EvalResult(
                case_id=r["case_id"],
                category=EvalCategory(r["category"]),
                difficulty=EvalDifficulty(r["difficulty"]),
                query=r["query"],
                expected_tools=r["expected_tools"],
                expected_answer_contains=[],  # Not stored
                passed=r["passed"],
                tool_selection_correct=r["tool_selection_correct"],
                answer_correct=r["answer_correct"],
                authorization_correct=r["authorization_correct"],
                num_steps=r["num_steps"],
                latency_ms=r["latency_ms"],
                tools_called=r["tools_called"],
                error=r.get("error"),
            )
        )

    return results


def generate_report(metrics: EvalMetrics, output_dir: str = "eval_results") -> str:
    """Generate a comprehensive HTML report."""

    summary = metrics.summary()

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>HR Agent Evaluation Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .metric-card {{ background: white; border-radius: 8px; padding: 20px;
                       margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }}
        .metric {{ text-align: center; }}
        .metric-value {{ font-size: 36px; font-weight: bold; color: #007bff; }}
        .metric-label {{ color: #666; margin-top: 5px; }}
        .pass {{ color: #28a745; }}
        .fail {{ color: #dc3545; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: white; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        tr:hover {{ background: #f5f5f5; }}
        .progress {{ background: #e9ecef; border-radius: 4px; height: 20px; overflow: hidden; }}
        .progress-bar {{ height: 100%; background: #007bff; transition: width 0.3s; }}
        .status {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
        .status-pass {{ background: #d4edda; color: #155724; }}
        .status-fail {{ background: #f8d7da; color: #721c24; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 HR Agent Evaluation Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <h2>📊 Overall Metrics</h2>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value {'pass' if summary['pass_rate'] >= 80 else 'fail'}">{summary['pass_rate']}%</div>
                <div class="metric-label">Pass Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{summary['tool_selection_accuracy']}%</div>
                <div class="metric-label">Tool Selection Accuracy</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{summary['answer_accuracy']}%</div>
                <div class="metric-label">Answer Accuracy</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{summary['authorization_compliance']}%</div>
                <div class="metric-label">Authorization Compliance</div>
            </div>
        </div>

        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value">{summary['avg_latency_ms']:.0f}ms</div>
                <div class="metric-label">Avg Latency</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{summary['p50_latency_ms']:.0f}ms</div>
                <div class="metric-label">P50 Latency</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{summary['p95_latency_ms']:.0f}ms</div>
                <div class="metric-label">P95 Latency</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{summary['avg_steps']}</div>
                <div class="metric-label">Avg Steps</div>
            </div>
        </div>

        <h2>📁 Results by Category</h2>
        <table>
            <tr>
                <th>Category</th>
                <th>Pass Rate</th>
                <th>Passed/Total</th>
                <th>Avg Latency</th>
            </tr>
    """

    for cat, cat_metrics in metrics.by_category().items():
        html += f"""
            <tr>
                <td>{cat.value}</td>
                <td>
                    <div class="progress">
                        <div class="progress-bar" style="width: {cat_metrics.pass_rate*100}%"></div>
                    </div>
                    {cat_metrics.pass_rate*100:.1f}%
                </td>
                <td>{cat_metrics.passed_cases}/{cat_metrics.total_cases}</td>
                <td>{cat_metrics.avg_latency_ms:.0f}ms</td>
            </tr>
        """

    html += """
        </table>

        <h2>📈 Results by Difficulty</h2>
        <table>
            <tr>
                <th>Difficulty</th>
                <th>Pass Rate</th>
                <th>Passed/Total</th>
                <th>Avg Steps</th>
            </tr>
    """

    for diff, diff_metrics in metrics.by_difficulty().items():
        html += f"""
            <tr>
                <td>{diff.value}</td>
                <td>
                    <div class="progress">
                        <div class="progress-bar" style="width: {diff_metrics.pass_rate*100}%"></div>
                    </div>
                    {diff_metrics.pass_rate*100:.1f}%
                </td>
                <td>{diff_metrics.passed_cases}/{diff_metrics.total_cases}</td>
                <td>{diff_metrics.avg_steps:.2f}</td>
            </tr>
        """

    html += """
        </table>

        <h2>📋 Detailed Results</h2>
        <table>
            <tr>
                <th>Case ID</th>
                <th>Query</th>
                <th>Status</th>
                <th>Tools</th>
                <th>Latency</th>
                <th>Steps</th>
            </tr>
    """

    for r in metrics.results:
        status_class = "status-pass" if r.passed else "status-fail"
        status_text = "✅ Pass" if r.passed else "❌ Fail"
        html += f"""
            <tr>
                <td>{r.case_id}</td>
                <td>{r.query[:60]}{'...' if len(r.query) > 60 else ''}</td>
                <td><span class="status {status_class}">{status_text}</span></td>
                <td>{', '.join(r.tools_called[:3])}{'...' if len(r.tools_called) > 3 else ''}</td>
                <td>{r.latency_ms:.0f}ms</td>
                <td>{r.num_steps}</td>
            </tr>
        """

    html += """
        </table>

        <h2>❌ Failed Cases</h2>
        <table>
            <tr>
                <th>Case ID</th>
                <th>Query</th>
                <th>Expected Tools</th>
                <th>Actual Tools</th>
                <th>Error</th>
            </tr>
    """

    failed = [r for r in metrics.results if not r.passed]
    for r in failed:
        html += f"""
            <tr>
                <td>{r.case_id}</td>
                <td>{r.query}</td>
                <td>{', '.join(r.expected_tools)}</td>
                <td>{', '.join(r.tools_called)}</td>
                <td>{r.error or 'Answer validation failed'}</td>
            </tr>
        """

    if not failed:
        html += "<tr><td colspan='5'>No failures! 🎉</td></tr>"

    html += """
        </table>
    </div>
</body>
</html>
    """

    # Save report
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(
        output_dir, f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    )
    with open(report_path, "w") as f:
        f.write(html)

    return report_path


def plot_results(metrics: EvalMetrics, output_dir: str = "eval_results"):
    """Generate visualization plots."""
    if not HAS_MATPLOTLIB:
        print("matplotlib not installed, skipping plots")
        return

    os.makedirs(output_dir, exist_ok=True)

    # 1. Pass rate by category
    _, axes = plt.subplots(2, 2, figsize=(12, 10))

    # Category pass rates
    ax = axes[0, 0]
    by_cat = metrics.by_category()
    cats = list(by_cat.keys())
    rates = [by_cat[c].pass_rate * 100 for c in cats]
    colors = [
        "#28a745" if r >= 80 else "#ffc107" if r >= 60 else "#dc3545" for r in rates
    ]
    ax.barh([c.value for c in cats], rates, color=colors)
    ax.set_xlabel("Pass Rate (%)")
    ax.set_title("Pass Rate by Category")
    ax.set_xlim(0, 100)

    # Difficulty pass rates
    ax = axes[0, 1]
    by_diff = metrics.by_difficulty()
    diffs = list(by_diff.keys())
    rates = [by_diff[d].pass_rate * 100 for d in diffs]
    colors = [
        "#28a745" if r >= 80 else "#ffc107" if r >= 60 else "#dc3545" for r in rates
    ]
    ax.bar([d.value for d in diffs], rates, color=colors)
    ax.set_ylabel("Pass Rate (%)")
    ax.set_title("Pass Rate by Difficulty")
    ax.set_ylim(0, 100)

    # Latency distribution
    ax = axes[1, 0]
    latencies = [r.latency_ms for r in metrics.results]
    ax.hist(latencies, bins=20, color="#007bff", alpha=0.7)
    ax.axvline(
        metrics.avg_latency_ms,
        color="red",
        linestyle="--",
        label=f"Mean: {metrics.avg_latency_ms:.0f}ms",
    )
    ax.axvline(
        metrics.p50_latency_ms,
        color="green",
        linestyle="--",
        label=f"P50: {metrics.p50_latency_ms:.0f}ms",
    )
    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("Count")
    ax.set_title("Latency Distribution")
    ax.legend()

    # Steps distribution
    ax = axes[1, 1]
    steps = [r.num_steps for r in metrics.results]
    ax.hist(
        steps, bins=range(1, max(steps) + 2), color="#6f42c1", alpha=0.7, align="left"
    )
    ax.set_xlabel("Number of Steps")
    ax.set_ylabel("Count")
    ax.set_title("Steps Distribution")

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "eval_plots.png"), dpi=150)
    plt.close()

    print(f"📊 Plots saved to {output_dir}/eval_plots.png")


def compare_runs(results_dir: str = "eval_results") -> dict:
    """Compare multiple evaluation runs over time."""
    results_path = Path(results_dir)
    if not results_path.exists():
        return {}

    summaries = []
    for summary_file in sorted(results_path.glob("eval_summary_*.json")):
        with open(summary_file) as f:
            data = json.load(f)
            # Extract timestamp from filename
            timestamp = summary_file.stem.replace("eval_summary_", "")
            data["timestamp"] = timestamp
            summaries.append(data)

    if len(summaries) < 2:
        return {"message": "Need at least 2 runs to compare"}

    # Compare latest with previous
    latest = summaries[-1]
    previous = summaries[-2]

    comparison = {
        "latest_run": latest["timestamp"],
        "previous_run": previous["timestamp"],
        "changes": {},
    }

    for key in [
        "pass_rate",
        "tool_selection_accuracy",
        "answer_accuracy",
        "avg_latency_ms",
    ]:
        delta = latest[key] - previous[key]
        direction = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        comparison["changes"][key] = {
            "previous": previous[key],
            "latest": latest[key],
            "delta": delta,
            "direction": direction,
        }

    return comparison
