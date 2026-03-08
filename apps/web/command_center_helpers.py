"""
Pure helpers for command-center UI rendering and sorting.
"""

from __future__ import annotations

from datetime import datetime


STATUS_CLASS_MAP = {
    "NEW": "status-new",
    "NEEDS_INFO": "status-needs-info",
    "READY": "status-ready",
    "IN_PROGRESS": "status-in-progress",
    "RESOLVED": "status-resolved",
    "ESCALATED": "status-escalated",
}

ACTION_LABEL_MAP = {
    "start_work": "Start Work",
    "resolve": "Resolve",
    "reopen": "Reopen",
    "auto_resolve": "Auto Resolve",
    "escalate_ticket": "Escalate Ticket",
}

PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}
RISK_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def status_class(status: str) -> str:
    """Map queue status to CSS class."""
    return STATUS_CLASS_MAP.get(status, "status-new")


def action_label(action: str) -> str:
    """Human-readable UI label for safe action."""
    return ACTION_LABEL_MAP.get(action, action.replace("_", " ").title())


def filter_queue_items(items: list[dict], status_filter: str) -> list[dict]:
    """Filter queue rows by selected status."""
    if status_filter == "ALL":
        return list(items)
    return [item for item in items if item.get("status") == status_filter]


def sort_queue_items(items: list[dict], now: datetime | None = None) -> list[dict]:
    """Sort queue rows by SLA breach, priority, risk, and age."""
    now = now or datetime.now()
    return sorted(items, key=lambda item: _sort_key(item, now))


def sla_badge_text(item: dict, now: datetime | None = None) -> str:
    """Build concise SLA badge text for a queue row."""
    now = now or datetime.now()
    due_value = item.get("sla_resolution_due_at")
    if not due_value:
        return "SLA: n/a"
    try:
        due_at = datetime.fromisoformat(str(due_value))
    except ValueError:
        return "SLA: n/a"
    if due_at <= now:
        return "SLA Breached"
    hours_left = int((due_at - now).total_seconds() // 3600)
    if hours_left < 1:
        return "SLA <1h"
    return f"SLA {hours_left}h"


def risk_badge_text(item: dict) -> str:
    """Build concise risk badge text."""
    level = str(item.get("risk_level") or "LOW")
    return f"Risk {level}"


def _sort_key(item: dict, now: datetime) -> tuple[int, int, int, int, str]:
    status = str(item.get("status") or "")
    is_resolved = 1 if status == "RESOLVED" else 0

    due_value = item.get("sla_resolution_due_at")
    is_overdue = 0
    if due_value:
        try:
            due_at = datetime.fromisoformat(str(due_value))
            is_overdue = 0 if due_at <= now and is_resolved == 0 else 1
        except ValueError:
            is_overdue = 1
    else:
        is_overdue = 1

    priority_rank = PRIORITY_RANK.get(str(item.get("priority") or "P2"), 2)
    risk_rank = RISK_RANK.get(str(item.get("risk_level") or "LOW"), 2)
    created_at = str(item.get("created_at") or "")

    return (is_resolved, is_overdue, priority_rank, risk_rank, created_at)
