"""
Exhaustive state machine transition tests for the command center workflow.

Tests all valid transitions and a representative set of invalid transitions
against the CommandCenterService.ALLOWED_TRANSITIONS state machine.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from hr_agent.repositories.command_center import CommandCenterRepository
from hr_agent.services.command_center import CommandCenterService
from hr_agent.domain.models import QueueStatus


# ── Test doubles ─────────────────────────────────────────────────────────────


class _TestRepo(CommandCenterRepository):
    def __init__(self, engine):
        self._engine = engine

    def _get_engine(self):
        return self._engine


class _FakeEmployeeRepo:
    def get_role_by_email(self, email: str) -> str:
        return {"hr@acme.com": "HR"}.get(email, "EMPLOYEE")

    def get_by_email(self, email: str) -> dict | None:
        return {"employee_id": 1, "email": email}

    def is_direct_report(self, manager_id: int, employee_id: int) -> bool:
        return False


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _build_engine(tmp_path: Path):
    db_path = tmp_path / "sm_test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as con:
        con.execute(
            text(
                """
            CREATE TABLE hr_command_center_request (
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


def _insert_request(repo, *, status: str, request_id: int = 1) -> dict:
    """Insert a request row at a given state and return it as a dict."""
    now = datetime.now().isoformat(timespec="seconds")
    sla = (datetime.now() + timedelta(hours=24)).isoformat(timespec="seconds")
    new_id = repo.create(
        requester_employee_id=1,
        requester_email="emp@acme.com",
        thread_id="t-1",
        source="CHAT",
        source_ref=None,
        source_message_excerpt="test request",
        request_type="POLICY_QUESTION",
        request_subtype="GENERAL",
        classifier_source="RULES",
        classifier_confidence=1.0,
        priority="P1",
        risk_level="MEDIUM",
        status=status,
        next_action=None,
        sla_first_response_due_at=sla,
        sla_resolution_due_at=sla,
        required_fields=[],
        collected_fields={},
        missing_fields=[],
    )
    return repo.get_by_id(new_id)


def _build_service(tmp_path: Path) -> CommandCenterService:
    engine = _build_engine(tmp_path)
    repo = _TestRepo(engine)
    svc = CommandCenterService.__new__(CommandCenterService)
    svc.repo = repo
    svc.employee_repo = _FakeEmployeeRepo()
    return svc


# ── Helpers ──────────────────────────────────────────────────────────────────


def _try_transition(svc: CommandCenterService, item: dict, new_status: str) -> dict:
    """Attempt a raw status transition (bypasses action mapping)."""
    return svc._transition_with_validation(
        item=item,
        actor_employee_id=1,
        new_status=new_status,
        next_action=None,
    )


# ============================================================================
# VALID TRANSITIONS – every edge in the state machine
# ============================================================================

ALL_STATUSES = [s.value for s in QueueStatus]

VALID_EDGES = [
    ("NEW", "NEEDS_INFO"),
    ("NEW", "READY"),
    ("NEW", "IN_PROGRESS"),
    ("NEW", "ESCALATED"),
    ("NEW", "RESOLVED"),
    ("NEEDS_INFO", "READY"),
    ("NEEDS_INFO", "ESCALATED"),
    ("READY", "NEEDS_INFO"),
    ("READY", "IN_PROGRESS"),
    ("READY", "RESOLVED"),
    ("READY", "ESCALATED"),
    ("IN_PROGRESS", "NEEDS_INFO"),
    ("IN_PROGRESS", "RESOLVED"),
    ("IN_PROGRESS", "ESCALATED"),
    ("ESCALATED", "IN_PROGRESS"),
    ("ESCALATED", "RESOLVED"),
    ("RESOLVED", "IN_PROGRESS"),
]


@pytest.mark.parametrize(
    "from_status,to_status", VALID_EDGES, ids=[f"{f}->{t}" for f, t in VALID_EDGES]
)
def test_valid_transition_succeeds(from_status, to_status, tmp_path):
    svc = _build_service(tmp_path)
    item = _insert_request(svc.repo, status=from_status)
    result = _try_transition(svc, item, to_status)
    assert (
        result["success"] is True
    ), f"Expected {from_status} -> {to_status} to succeed, got {result}"


# ============================================================================
# INVALID TRANSITIONS – every disallowed edge
# ============================================================================

INVALID_EDGES = []
for src in ALL_STATUSES:
    allowed = CommandCenterService.ALLOWED_TRANSITIONS.get(src, set())
    for dst in ALL_STATUSES:
        if dst != src and dst not in allowed:
            INVALID_EDGES.append((src, dst))


@pytest.mark.parametrize(
    "from_status,to_status", INVALID_EDGES, ids=[f"{f}->{t}" for f, t in INVALID_EDGES]
)
def test_invalid_transition_rejected(from_status, to_status, tmp_path):
    svc = _build_service(tmp_path)
    item = _insert_request(svc.repo, status=from_status)
    result = _try_transition(svc, item, to_status)
    assert result["success"] is False, f"Expected {from_status} -> {to_status} to fail"
    assert "Invalid transition" in result.get("error", "")


# ============================================================================
# SELF-TRANSITIONS – should not be allowed (no identity transitions)
# ============================================================================


@pytest.mark.parametrize("status", ALL_STATUSES, ids=ALL_STATUSES)
def test_self_transition_rejected(status, tmp_path):
    svc = _build_service(tmp_path)
    item = _insert_request(svc.repo, status=status)
    result = _try_transition(svc, item, status)
    assert result["success"] is False


# ============================================================================
# ACTION-BASED TRANSITIONS – via execute_safe_action
# ============================================================================


def test_start_work_transitions_to_in_progress(tmp_path):
    svc = _build_service(tmp_path)
    item = _insert_request(svc.repo, status="NEW")
    result = svc.execute_safe_action("hr@acme.com", 1, item["request_id"], "start_work")
    assert result["success"] is True
    updated = svc.repo.get_by_id(item["request_id"])
    assert updated["status"] == "IN_PROGRESS"


def test_resolve_transitions_to_resolved(tmp_path):
    svc = _build_service(tmp_path)
    item = _insert_request(svc.repo, status="IN_PROGRESS")
    result = svc.execute_safe_action("hr@acme.com", 1, item["request_id"], "resolve")
    assert result["success"] is True
    updated = svc.repo.get_by_id(item["request_id"])
    assert updated["status"] == "RESOLVED"


def test_reopen_transitions_resolved_to_in_progress(tmp_path):
    svc = _build_service(tmp_path)
    item = _insert_request(svc.repo, status="RESOLVED")
    result = svc.execute_safe_action("hr@acme.com", 1, item["request_id"], "reopen")
    assert result["success"] is True
    updated = svc.repo.get_by_id(item["request_id"])
    assert updated["status"] == "IN_PROGRESS"


def test_escalate_ticket_creates_ticket_ref(tmp_path):
    svc = _build_service(tmp_path)
    item = _insert_request(svc.repo, status="NEW")
    result = svc.execute_safe_action(
        "hr@acme.com", 1, item["request_id"], "escalate_ticket"
    )
    assert result["success"] is True
    assert result.get("ticket_ref", "").startswith("HR-TKT-")
    updated = svc.repo.get_by_id(item["request_id"])
    assert updated["status"] == "ESCALATED"


def test_escalate_resolved_request_rejected(tmp_path):
    svc = _build_service(tmp_path)
    item = _insert_request(svc.repo, status="RESOLVED")
    result = svc.execute_safe_action(
        "hr@acme.com", 1, item["request_id"], "escalate_ticket"
    )
    assert result["success"] is False
    assert "Cannot escalate" in result["error"]


def test_employee_cannot_execute_actions(tmp_path):
    svc = _build_service(tmp_path)
    item = _insert_request(svc.repo, status="NEW")
    result = svc.execute_safe_action(
        "emp@acme.com", 1, item["request_id"], "start_work"
    )
    assert result["success"] is False
    assert "HR/Manager" in result["error"]


def test_unsupported_action_rejected(tmp_path):
    svc = _build_service(tmp_path)
    item = _insert_request(svc.repo, status="NEW")
    result = svc.execute_safe_action(
        "hr@acme.com", 1, item["request_id"], "delete_everything"
    )
    assert result["success"] is False
    assert "Unsupported action" in result["error"]
