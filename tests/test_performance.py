"""Performance-budget tests (PBI DoD §5).

These are *scaffolding* tests that verify key operations complete within their
SLA budgets.  They run entirely in-process against the real service layer (no
LLM calls) so they are fast and deterministic.

Budgets
-------
* Queue listing:            p95  ≤ 3 000 ms
* Single triage action:     p95  ≤   500 ms
* Sorting 500 items:        p95  ≤   200 ms
* State-machine transition: p95  ≤    50 ms
"""

from __future__ import annotations

import importlib.util
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_module(rel_path: str, module_name: str):
    module_path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _p95(values: list[float]) -> float:
    """Return the 95th-percentile value."""
    s = sorted(values)
    idx = int(len(s) * 0.95)
    return s[min(idx, len(s) - 1)]


# ---------------------------------------------------------------------------
# In-memory DB / repo helpers (avoids singleton contamination)
# ---------------------------------------------------------------------------


def _create_test_engine(tmp_path: Path):
    """Create a fresh SQLite engine with the command-center schema."""
    from hr_agent.repositories.command_center import CommandCenterRepository

    db_path = tmp_path / "perf_test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as con:
        con.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS hr_command_center_request (
              request_id INTEGER PRIMARY KEY,
              requester_employee_id INTEGER NOT NULL,
              requester_email TEXT NOT NULL,
              thread_id TEXT NOT NULL,
              source TEXT NOT NULL,
              source_ref TEXT NULL,
              source_message_excerpt TEXT NOT NULL,
              request_type TEXT NOT NULL,
              request_subtype TEXT NOT NULL,
              classifier_source TEXT NOT NULL,
              classifier_confidence REAL NOT NULL,
              priority TEXT NOT NULL,
              risk_level TEXT NOT NULL,
              status TEXT NOT NULL,
              next_action TEXT NULL,
              sla_first_response_due_at TEXT NULL,
              sla_resolution_due_at TEXT NULL,
              required_fields_json TEXT NOT NULL,
              collected_fields_json TEXT NOT NULL,
              missing_fields_json TEXT NOT NULL,
              ticket_ref TEXT NULL,
              escalated_at TEXT NULL,
              escalation_reason TEXT NULL,
              assigned_to_employee_id INTEGER NULL,
              last_actor_employee_id INTEGER NULL,
              notes TEXT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
        """
            )
        )
    return engine


class _PerfRepo:
    """Thin repo wrapper that delegates to the real repo with a custom engine."""

    def __init__(self, engine):
        from hr_agent.repositories.command_center import CommandCenterRepository

        self._inner = CommandCenterRepository.__new__(CommandCenterRepository)
        self._inner._engine = engine

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _FakeEmployeeRepo:
    def get_role_by_email(self, email: str) -> str:
        return {"hr@acme.com": "HR"}.get(email, "EMPLOYEE")

    def get_by_email(self, email: str) -> dict | None:
        return {"employee_id": 110, "email": email}

    def is_direct_report(self, manager_id: int, employee_id: int) -> bool:
        return False


def _build_service(tmp_path: Path):
    from hr_agent.services.command_center import CommandCenterService

    engine = _create_test_engine(tmp_path)
    repo = _PerfRepo(engine)
    svc = CommandCenterService.__new__(CommandCenterService)
    svc.repo = repo
    svc.employee_repo = _FakeEmployeeRepo()
    return svc, repo


def _seed_item(repo, *, status="NEW", priority="P1", risk="MEDIUM", idx=0):
    """Insert one row directly via the repository."""
    now = datetime.now().isoformat(timespec="seconds")
    sla = (datetime.now() + timedelta(hours=24)).isoformat(timespec="seconds")
    return repo.create(
        requester_employee_id=1000 + idx,
        requester_email=f"user{idx}@acme.com",
        thread_id=f"t-{idx}",
        source="CHAT",
        source_ref=None,
        source_message_excerpt=f"test item {idx}",
        request_type="POLICY_QUESTION",
        request_subtype="GENERAL",
        classifier_source="RULES",
        classifier_confidence=1.0,
        priority=priority,
        risk_level=risk,
        status=status,
        next_action=None,
        sla_first_response_due_at=sla,
        sla_resolution_due_at=sla,
        required_fields=[],
        collected_fields={},
        missing_fields=[],
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def sorting_mod():
    return _load_module("apps/web/command_center_helpers.py", "sort_perf")


# ---------------------------------------------------------------------------
# 1. Queue listing latency (p95 ≤ 3 000 ms)
# ---------------------------------------------------------------------------


def test_queue_listing_p95_under_budget(tmp_path):
    """Fetching the queue 20× should stay under 3 s at p95."""
    svc, repo = _build_service(tmp_path)
    for i in range(10):
        _seed_item(repo, idx=i)

    timings: list[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        svc.list_requests(viewer_email="hr@acme.com")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        timings.append(elapsed_ms)

    p95_val = _p95(timings)
    assert p95_val <= 3_000, f"Queue listing p95 = {p95_val:.1f} ms > 3 000 ms budget"


# ---------------------------------------------------------------------------
# 2. Single triage action latency (p95 ≤ 500 ms)
# ---------------------------------------------------------------------------


def test_triage_action_p95_under_budget(tmp_path):
    """Executing a triage action 20× should stay under 500 ms at p95."""
    svc, repo = _build_service(tmp_path)
    hr_email = "hr@acme.com"
    hr_id = 110

    timings: list[float] = []
    for i in range(20):
        req_id = _seed_item(repo, idx=i)
        t0 = time.perf_counter()
        svc.execute_safe_action(
            viewer_email=hr_email,
            actor_employee_id=hr_id,
            request_id=req_id,
            action="start_work",
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        timings.append(elapsed_ms)

    p95_val = _p95(timings)
    assert p95_val <= 500, f"Triage action p95 = {p95_val:.1f} ms > 500 ms budget"


# ---------------------------------------------------------------------------
# 3. Sorting 500 items (p95 ≤ 200 ms)
# ---------------------------------------------------------------------------


def test_sorting_500_items_p95_under_budget(sorting_mod):
    """Sorting 500 queue items should complete within 200 ms at p95."""
    now = datetime.now(timezone.utc)

    items = []
    for i in range(500):
        priority = ["P0", "P1", "P2"][i % 3]
        risk = ["HIGH", "MEDIUM", "LOW"][i % 3]
        status = "NEW" if i % 5 != 0 else "RESOLVED"
        sla_deadline = (now + timedelta(hours=(i % 48) - 12)).isoformat()
        items.append(
            {
                "request_id": i,
                "priority": priority,
                "risk_level": risk,
                "status": status,
                "sla_deadline": sla_deadline,
                "created_at": (now - timedelta(hours=i)).isoformat(),
            }
        )

    sort_fn = sorting_mod.sort_queue_items

    timings: list[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        sort_fn(list(items))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        timings.append(elapsed_ms)

    p95_val = _p95(timings)
    assert p95_val <= 200, f"Sort-500 p95 = {p95_val:.1f} ms > 200 ms budget"


# ---------------------------------------------------------------------------
# 4. State-machine transition via safe action (p95 ≤ 50 ms)
# ---------------------------------------------------------------------------


def test_state_transition_p95_under_budget(tmp_path):
    """A single transition (start_work) should complete within 50 ms at p95."""
    svc, repo = _build_service(tmp_path)
    hr_email = "hr@acme.com"
    hr_id = 110

    timings: list[float] = []
    for i in range(30):
        req_id = _seed_item(repo, idx=i + 5000)
        t0 = time.perf_counter()
        svc.execute_safe_action(
            viewer_email=hr_email,
            actor_employee_id=hr_id,
            request_id=req_id,
            action="start_work",
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        timings.append(elapsed_ms)

    p95_val = _p95(timings)
    assert p95_val <= 50, f"State transition p95 = {p95_val:.1f} ms > 50 ms budget"


# ---------------------------------------------------------------------------
# 5. Priority change (p95 ≤ 100 ms)
# ---------------------------------------------------------------------------


def test_priority_change_p95_under_budget(tmp_path):
    """Changing priority (with SLA recalculation) under 100 ms at p95."""
    svc, repo = _build_service(tmp_path)
    hr_email = "hr@acme.com"
    hr_id = 110

    timings: list[float] = []
    for i in range(20):
        req_id = _seed_item(repo, priority="P2", idx=i + 6000)
        t0 = time.perf_counter()
        svc.change_priority(
            viewer_email=hr_email,
            actor_employee_id=hr_id,
            request_id=req_id,
            new_priority="P0",
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        timings.append(elapsed_ms)

    p95_val = _p95(timings)
    assert p95_val <= 100, f"Priority change p95 = {p95_val:.1f} ms > 100 ms budget"
