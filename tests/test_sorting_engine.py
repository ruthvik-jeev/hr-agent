"""
Sorting engine test suite – ≥10 permutations covering:
  • SLA-breached items surface first
  • Priority ranking (P0 > P1 > P2)
  • Risk ranking (HIGH > MEDIUM > LOW)
  • Resolved items sort last
  • Tie-breaking by created_at (oldest first)
  • Combinations of the above dimensions
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from apps.web.command_center_helpers import sort_queue_items

NOW = datetime(2026, 3, 8, 12, 0, 0)


def _item(
    request_id: int,
    *,
    status: str = "READY",
    priority: str = "P1",
    risk_level: str = "MEDIUM",
    created_hours_ago: float = 1.0,
    sla_due_hours: float = 5.0,
) -> dict:
    """Build a minimal queue item dict with sensible defaults."""
    return {
        "request_id": request_id,
        "status": status,
        "priority": priority,
        "risk_level": risk_level,
        "created_at": (NOW - timedelta(hours=created_hours_ago)).isoformat(
            timespec="seconds"
        ),
        "sla_resolution_due_at": (NOW + timedelta(hours=sla_due_hours)).isoformat(
            timespec="seconds"
        ),
    }


def _ids(items: list[dict]) -> list[int]:
    """Extract request_id ordering for easy assertions."""
    return [item["request_id"] for item in items]


# ─── Permutation 1: SLA-breached beats non-breached ──────────────────────────
def test_sla_breached_surfaces_first():
    items = [
        _item(1, sla_due_hours=5),   # not breached
        _item(2, sla_due_hours=-1),  # breached
    ]
    result = sort_queue_items(items, now=NOW)
    assert _ids(result) == [2, 1]


# ─── Permutation 2: P0 > P1 > P2 (same SLA, same risk) ─────────────────────
def test_priority_ordering_p0_p1_p2():
    items = [
        _item(1, priority="P2"),
        _item(2, priority="P0"),
        _item(3, priority="P1"),
    ]
    result = sort_queue_items(items, now=NOW)
    assert _ids(result) == [2, 3, 1]


# ─── Permutation 3: HIGH > MEDIUM > LOW risk (same priority) ────────────────
def test_risk_ordering_high_medium_low():
    items = [
        _item(1, risk_level="LOW"),
        _item(2, risk_level="HIGH"),
        _item(3, risk_level="MEDIUM"),
    ]
    result = sort_queue_items(items, now=NOW)
    assert _ids(result) == [2, 3, 1]


# ─── Permutation 4: Resolved items always sort last ─────────────────────────
def test_resolved_items_sort_last():
    items = [
        _item(1, status="RESOLVED", priority="P0", risk_level="HIGH"),
        _item(2, status="READY", priority="P2", risk_level="LOW"),
    ]
    result = sort_queue_items(items, now=NOW)
    assert _ids(result) == [2, 1]


# ─── Permutation 5: Oldest created_at first among equal items ───────────────
def test_oldest_first_tiebreak():
    items = [
        _item(1, created_hours_ago=1),
        _item(2, created_hours_ago=5),
        _item(3, created_hours_ago=3),
    ]
    result = sort_queue_items(items, now=NOW)
    assert _ids(result) == [2, 3, 1]


# ─── Permutation 6: SLA breach wins over higher priority ────────────────────
def test_sla_breach_beats_high_priority():
    items = [
        _item(1, priority="P0", sla_due_hours=5),   # P0 not breached
        _item(2, priority="P2", sla_due_hours=-2),   # P2 but breached
    ]
    result = sort_queue_items(items, now=NOW)
    assert _ids(result) == [2, 1]


# ─── Permutation 7: SLA breach + priority ordering ──────────────────────────
def test_among_breached_higher_priority_first():
    items = [
        _item(1, priority="P2", sla_due_hours=-1),
        _item(2, priority="P0", sla_due_hours=-3),
        _item(3, priority="P1", sla_due_hours=-2),
    ]
    result = sort_queue_items(items, now=NOW)
    assert _ids(result) == [2, 3, 1]


# ─── Permutation 8: Mixed resolved / active / breached ──────────────────────
def test_mixed_resolved_active_breached():
    items = [
        _item(1, status="RESOLVED", priority="P0", sla_due_hours=-5),
        _item(2, status="READY", priority="P2", sla_due_hours=10),
        _item(3, status="IN_PROGRESS", priority="P1", sla_due_hours=-1),
    ]
    result = sort_queue_items(items, now=NOW)
    # breached active first, then non-breached active, then resolved
    assert _ids(result) == [3, 2, 1]


# ─── Permutation 9: Same priority, risk tiebreak then age ───────────────────
def test_same_priority_risk_then_age_tiebreak():
    items = [
        _item(1, priority="P1", risk_level="LOW", created_hours_ago=2),
        _item(2, priority="P1", risk_level="HIGH", created_hours_ago=1),
        _item(3, priority="P1", risk_level="MEDIUM", created_hours_ago=3),
    ]
    result = sort_queue_items(items, now=NOW)
    assert _ids(result) == [2, 3, 1]


# ─── Permutation 10: Full 5-item ranking test ───────────────────────────────
def test_full_five_item_ranking():
    items = [
        _item(1, status="READY", priority="P2", risk_level="LOW", sla_due_hours=10, created_hours_ago=1),
        _item(2, status="RESOLVED", priority="P0", risk_level="HIGH", sla_due_hours=-10, created_hours_ago=8),
        _item(3, status="IN_PROGRESS", priority="P1", risk_level="MEDIUM", sla_due_hours=-2, created_hours_ago=4),
        _item(4, status="READY", priority="P0", risk_level="HIGH", sla_due_hours=2, created_hours_ago=6),
        _item(5, status="NEEDS_INFO", priority="P0", risk_level="HIGH", sla_due_hours=-1, created_hours_ago=3),
    ]
    result = sort_queue_items(items, now=NOW)
    # Order: breached active (P0 HIGH #5, P1 MED #3), non-breached active (P0 HIGH #4, P2 LOW #1), resolved #2
    assert _ids(result) == [5, 3, 4, 1, 2]


# ─── Permutation 11: Empty list ─────────────────────────────────────────────
def test_empty_list_returns_empty():
    assert sort_queue_items([], now=NOW) == []


# ─── Permutation 12: Single item ────────────────────────────────────────────
def test_single_item_returns_same():
    items = [_item(1)]
    result = sort_queue_items(items, now=NOW)
    assert _ids(result) == [1]


# ─── Permutation 13: All resolved items keep relative order by priority ─────
def test_all_resolved_sorted_by_priority():
    items = [
        _item(1, status="RESOLVED", priority="P2"),
        _item(2, status="RESOLVED", priority="P0"),
        _item(3, status="RESOLVED", priority="P1"),
    ]
    result = sort_queue_items(items, now=NOW)
    assert _ids(result) == [2, 3, 1]


# ─── Permutation 14: Missing SLA (null) sorts after breached ────────────────
def test_missing_sla_sorts_after_breached():
    item_no_sla = _item(1, priority="P1")
    item_no_sla["sla_resolution_due_at"] = None
    item_breached = _item(2, priority="P1", sla_due_hours=-1)

    result = sort_queue_items([item_no_sla, item_breached], now=NOW)
    assert _ids(result) == [2, 1]


# ─── Permutation 15: ESCALATED treated same as active (not last) ────────────
def test_escalated_sorted_as_active():
    items = [
        _item(1, status="RESOLVED", priority="P0"),
        _item(2, status="ESCALATED", priority="P1"),
    ]
    result = sort_queue_items(items, now=NOW)
    assert _ids(result) == [2, 1]
