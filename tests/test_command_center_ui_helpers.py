from __future__ import annotations

from datetime import datetime, timedelta

from apps.web.command_center_helpers import (
    action_label,
    filter_queue_items,
    risk_badge_text,
    sla_badge_text,
    sort_queue_items,
    status_class,
)


def test_status_and_action_mappings():
    assert status_class("NEW") == "status-new"
    assert status_class("IN_PROGRESS") == "status-in-progress"
    assert status_class("ESCALATED") == "status-escalated"
    assert action_label("start_work") == "Start Work"
    assert action_label("auto_resolve") == "Auto Resolve"


def test_filter_and_sort_prioritizes_breach_priority_risk():
    now = datetime.now()
    items = [
        {
            "request_id": 1,
            "status": "READY",
            "priority": "P2",
            "risk_level": "LOW",
            "created_at": (now - timedelta(hours=5)).isoformat(timespec="seconds"),
            "sla_resolution_due_at": (now + timedelta(hours=5)).isoformat(
                timespec="seconds"
            ),
        },
        {
            "request_id": 2,
            "status": "IN_PROGRESS",
            "priority": "P1",
            "risk_level": "MEDIUM",
            "created_at": (now - timedelta(hours=4)).isoformat(timespec="seconds"),
            "sla_resolution_due_at": (now - timedelta(hours=1)).isoformat(
                timespec="seconds"
            ),
        },
        {
            "request_id": 3,
            "status": "READY",
            "priority": "P0",
            "risk_level": "HIGH",
            "created_at": (now - timedelta(hours=3)).isoformat(timespec="seconds"),
            "sla_resolution_due_at": (now + timedelta(hours=10)).isoformat(
                timespec="seconds"
            ),
        },
    ]

    ready_items = filter_queue_items(items, "READY")
    assert {item["request_id"] for item in ready_items} == {1, 3}

    sorted_items = sort_queue_items(items, now=now)
    assert sorted_items[0]["request_id"] == 2
    assert sorted_items[1]["request_id"] == 3


def test_sla_and_risk_badges():
    now = datetime.now()
    breached = {
        "sla_resolution_due_at": (now - timedelta(minutes=5)).isoformat(
            timespec="seconds"
        ),
        "risk_level": "HIGH",
    }
    future_due = {
        "sla_resolution_due_at": (now + timedelta(hours=6)).isoformat(timespec="seconds"),
        "risk_level": "LOW",
    }

    assert sla_badge_text(breached, now=now) == "SLA Breached"
    assert "SLA" in sla_badge_text(future_due, now=now)
    assert risk_badge_text(breached) == "Risk HIGH"
