from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text

from hr_agent.configs.config import settings
from hr_agent.repositories.command_center import CommandCenterRepository
from hr_agent.services.command_center import CommandCenterService


class _TestCommandCenterRepository(CommandCenterRepository):
    def __init__(self, engine):
        self._engine = engine

    def _get_engine(self):
        return self._engine


class _FakeEmployeeRepo:
    def __init__(self):
        self.role_by_email = {
            "hr.user@acme.com": "HR",
            "manager.user@acme.com": "MANAGER",
            "emp.one@acme.com": "EMPLOYEE",
            "emp.two@acme.com": "EMPLOYEE",
        }
        self.employee_id_by_email = {
            "hr.user@acme.com": 110,
            "manager.user@acme.com": 900,
            "emp.one@acme.com": 201,
            "emp.two@acme.com": 202,
        }
        self.direct_reports = {900: {201}}

    def get_role_by_email(self, email: str) -> str:
        return self.role_by_email.get(email, "EMPLOYEE")

    def get_by_email(self, email: str) -> dict | None:
        employee_id = self.employee_id_by_email.get(email)
        if employee_id is None:
            return None
        return {"employee_id": employee_id, "email": email}

    def is_direct_report(self, manager_id: int, employee_id: int) -> bool:
        return employee_id in self.direct_reports.get(manager_id, set())


def _build_engine(tmp_path: Path):
    db_path = tmp_path / "command_center_test.db"
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
        con.execute(
            text(
                """
                CREATE TABLE manager_reports (
                  manager_employee_id INTEGER NOT NULL,
                  report_employee_id INTEGER NOT NULL,
                  PRIMARY KEY (manager_employee_id, report_employee_id)
                )
                """
            )
        )
        con.execute(
            text(
                """
                INSERT INTO manager_reports(manager_employee_id, report_employee_id)
                VALUES (900, 201)
                """
            )
        )
    return engine


def _build_service(tmp_path: Path) -> tuple[CommandCenterService, _TestCommandCenterRepository]:
    repo = _TestCommandCenterRepository(_build_engine(tmp_path))
    service = CommandCenterService()
    service.repo = repo
    service.employee_repo = _FakeEmployeeRepo()
    return service, repo


def test_rule_classification_priority_and_sla_defaults(tmp_path: Path):
    service, _repo = _build_service(tmp_path)

    classification = service._classify_message(
        "My payroll is wrong and I was not paid this month."
    )
    assert classification is not None
    assert classification["request_type"] == "PAYROLL_QUERY"
    assert classification["request_subtype"] == "PAYROLL_DISCREPANCY"

    priority, risk, _reason = service._score_priority_and_risk(
        "I was not paid correctly", "PAYROLL_QUERY"
    )
    assert priority == "P0"
    assert risk == "HIGH"

    first_due, resolution_due = service._calculate_sla_due_at("P0")
    first_dt = datetime.fromisoformat(first_due)
    resolution_dt = datetime.fromisoformat(resolution_due)
    assert first_dt > datetime.now()
    assert resolution_dt > first_dt


def test_llm_fallback_gating_and_rule_default(tmp_path: Path, monkeypatch):
    service, _repo = _build_service(tmp_path)

    original_key = settings.llm_api_key
    try:
        settings.llm_api_key = ""
        fallback = service._classify_message("Need help from human resources.")
        assert fallback is not None
        assert fallback["classifier_source"] == "rule"

        settings.llm_api_key = "dummy-key"
        monkeypatch.setattr(
            service,
            "_classify_with_llm",
            lambda text, default: {
                "request_type": "ESCALATION",
                "request_subtype": "GENERAL_ESCALATION",
                "classifier_source": "llm",
                "confidence": 0.88,
            },
        )
        classified = service._classify_message("Need help from human resources.")
        assert classified is not None
        assert classified["classifier_source"] == "llm"
    finally:
        settings.llm_api_key = original_key


def test_hybrid_intake_slot_filling_needs_info_to_ready(tmp_path: Path):
    service, repo = _build_service(tmp_path)

    first = service.ingest_user_turn(
        requester_employee_id=201,
        requester_email="emp.one@acme.com",
        thread_id="thread-1",
        message="My payroll is wrong.",
        source="AUTO",
    )
    assert first["success"] is True
    assert first["queued"] is True
    assert first["status"] == "NEEDS_INFO"

    second = service.ingest_user_turn(
        requester_employee_id=201,
        requester_email="emp.one@acme.com",
        thread_id="thread-1",
        message="It is for pay period 2026-02.",
        source="AUTO",
    )
    assert second["success"] is True
    assert second["queued"] is True
    assert second["updated"] is True
    assert second["status"] == "READY"
    assert second["request_id"] == first["request_id"]

    row = repo.get_by_id(first["request_id"])
    assert row is not None
    assert row["status"] == "READY"
    assert row["missing_fields_json"] == []


def test_sensitive_manual_escalation_creates_ticket_stub(tmp_path: Path):
    service, repo = _build_service(tmp_path)

    result = service.ingest_user_turn(
        requester_employee_id=202,
        requester_email="emp.two@acme.com",
        thread_id="thread-2",
        message="I need to report harassment and legal retaliation.",
        source="MANUAL_ESCALATION",
        source_ref="esc-11",
    )

    assert result["success"] is True
    assert result["queued"] is True
    assert result["status"] == "ESCALATED"

    row = repo.get_by_id(result["request_id"])
    assert row is not None
    assert row["source"] == "MANUAL_ESCALATION"
    assert row["ticket_ref"] is not None
    assert str(row["ticket_ref"]).startswith("HR-TKT-")


def test_visibility_scope_and_prioritized_ordering(tmp_path: Path):
    service, repo = _build_service(tmp_path)

    high_priority = service.ingest_user_turn(
        requester_employee_id=201,
        requester_email="emp.one@acme.com",
        thread_id="thread-3",
        message="Urgent payroll issue: I was not paid for 2026-02.",
        source="AUTO",
    )
    low_priority = service.ingest_user_turn(
        requester_employee_id=202,
        requester_email="emp.two@acme.com",
        thread_id="thread-4",
        message="What is the remote work policy?",
        source="AUTO",
    )
    assert high_priority["queued"] is True
    assert low_priority["queued"] is True

    repo.update_request(
        int(low_priority["request_id"]),
        {
            "status": "IN_PROGRESS",
            "sla_resolution_due_at": (
                datetime.now() - timedelta(hours=1)
            ).isoformat(timespec="seconds"),
        },
    )

    hr_rows = service.list_requests("hr.user@acme.com")
    assert len(hr_rows) == 2
    assert hr_rows[0]["request_id"] == low_priority["request_id"]

    manager_rows = service.list_requests("manager.user@acme.com")
    assert len(manager_rows) == 1
    assert manager_rows[0]["requester_email"] == "emp.one@acme.com"

    employee_rows = service.list_requests("emp.two@acme.com")
    assert len(employee_rows) == 1
    assert employee_rows[0]["requester_email"] == "emp.two@acme.com"


def test_safe_action_transitions_and_invalid_transition(tmp_path: Path):
    service, repo = _build_service(tmp_path)

    created = service.ingest_user_turn(
        requester_employee_id=201,
        requester_email="emp.one@acme.com",
        thread_id="thread-5",
        message="Please escalate this onboarding issue.",
        source="MANUAL_ESCALATION",
    )
    queue_id = int(created["request_id"])

    start = service.execute_safe_action(
        viewer_email="hr.user@acme.com",
        actor_employee_id=110,
        request_id=queue_id,
        action="start_work",
    )
    assert start["success"] is True

    resolve = service.execute_safe_action(
        viewer_email="hr.user@acme.com",
        actor_employee_id=110,
        request_id=queue_id,
        action="resolve",
    )
    assert resolve["success"] is True

    reopen = service.execute_safe_action(
        viewer_email="hr.user@acme.com",
        actor_employee_id=110,
        request_id=queue_id,
        action="reopen",
    )
    assert reopen["success"] is True

    needs_info = service.ingest_user_turn(
        requester_employee_id=201,
        requester_email="emp.one@acme.com",
        thread_id="thread-6",
        message="Payroll issue.",
        source="AUTO",
    )
    invalid = service.execute_safe_action(
        viewer_email="hr.user@acme.com",
        actor_employee_id=110,
        request_id=int(needs_info["request_id"]),
        action="resolve",
    )
    assert invalid["success"] is False
    assert "Invalid transition" in invalid["error"]

    unauthorized = service.execute_safe_action(
        viewer_email="manager.user@acme.com",
        actor_employee_id=900,
        request_id=int(needs_info["request_id"]),
        action="escalate_ticket",
    )
    assert unauthorized["success"] is True

    outsider = service.execute_safe_action(
        viewer_email="emp.two@acme.com",
        actor_employee_id=202,
        request_id=int(needs_info["request_id"]),
        action="start_work",
    )
    assert outsider["success"] is False

    out_of_scope = service.ingest_user_turn(
        requester_employee_id=202,
        requester_email="emp.two@acme.com",
        thread_id="thread-7",
        message="I have a payroll discrepancy for 2026-03.",
        source="AUTO",
    )
    manager_denied = service.execute_safe_action(
        viewer_email="manager.user@acme.com",
        actor_employee_id=900,
        request_id=int(out_of_scope["request_id"]),
        action="start_work",
    )
    assert manager_denied["success"] is False

    row = repo.get_by_id(queue_id)
    assert row is not None
    assert row["status"] == "IN_PROGRESS"


def test_assign_and_reassign_permissions(tmp_path: Path):
    service, repo = _build_service(tmp_path)

    created = service.ingest_user_turn(
        requester_employee_id=201,
        requester_email="emp.one@acme.com",
        thread_id="thread-8",
        message="Please escalate this onboarding issue.",
        source="MANUAL_ESCALATION",
    )
    queue_id = int(created["request_id"])

    assigned = service.assign_request(
        viewer_email="hr.user@acme.com",
        actor_employee_id=110,
        request_id=queue_id,
        assignee_employee_id=111,
    )
    assert assigned["success"] is True
    row = repo.get_by_id(queue_id)
    assert row is not None
    assert row["assigned_to_employee_id"] == 111
    assert row["last_actor_employee_id"] == 110

    reassigned = service.assign_request(
        viewer_email="manager.user@acme.com",
        actor_employee_id=900,
        request_id=queue_id,
        assignee_employee_id=112,
    )
    assert reassigned["success"] is True
    row = repo.get_by_id(queue_id)
    assert row is not None
    assert row["assigned_to_employee_id"] == 112
    assert row["last_actor_employee_id"] == 900

    out_of_scope = service.ingest_user_turn(
        requester_employee_id=202,
        requester_email="emp.two@acme.com",
        thread_id="thread-9",
        message="Need payroll correction for 2026-03.",
        source="AUTO",
    )
    manager_denied = service.assign_request(
        viewer_email="manager.user@acme.com",
        actor_employee_id=900,
        request_id=int(out_of_scope["request_id"]),
        assignee_employee_id=113,
    )
    assert manager_denied["success"] is False
    assert "Not authorized" in manager_denied["error"]

    employee_denied = service.assign_request(
        viewer_email="emp.two@acme.com",
        actor_employee_id=202,
        request_id=queue_id,
        assignee_employee_id=114,
    )
    assert employee_denied["success"] is False
    assert "HR/Manager" in employee_denied["error"]


def test_change_priority_recalculates_sla_and_checks_permissions(tmp_path: Path):
    service, repo = _build_service(tmp_path)

    created = service.ingest_user_turn(
        requester_employee_id=201,
        requester_email="emp.one@acme.com",
        thread_id="thread-10",
        message="Leave correction needed for 2026-04-10.",
        source="AUTO",
    )
    queue_id = int(created["request_id"])

    before = repo.get_by_id(queue_id)
    assert before is not None
    created_at = datetime.fromisoformat(before["created_at"])

    changed = service.change_priority(
        viewer_email="hr.user@acme.com",
        actor_employee_id=110,
        request_id=queue_id,
        new_priority="P0",
    )
    assert changed["success"] is True

    after = repo.get_by_id(queue_id)
    assert after is not None
    assert after["priority"] == "P0"
    assert after["last_actor_employee_id"] == 110
    assert after["sla_first_response_due_at"] == (
        created_at + timedelta(hours=2)
    ).isoformat(timespec="seconds")
    assert after["sla_resolution_due_at"] == (
        created_at + timedelta(hours=24)
    ).isoformat(timespec="seconds")

    invalid_priority = service.change_priority(
        viewer_email="hr.user@acme.com",
        actor_employee_id=110,
        request_id=queue_id,
        new_priority="P9",
    )
    assert invalid_priority["success"] is False
    assert "Invalid priority" in invalid_priority["error"]

    out_of_scope = service.ingest_user_turn(
        requester_employee_id=202,
        requester_email="emp.two@acme.com",
        thread_id="thread-11",
        message="Need payroll correction for 2026-05.",
        source="AUTO",
    )
    manager_denied = service.change_priority(
        viewer_email="manager.user@acme.com",
        actor_employee_id=900,
        request_id=int(out_of_scope["request_id"]),
        new_priority="P0",
    )
    assert manager_denied["success"] is False
    assert "Not authorized" in manager_denied["error"]

    employee_denied = service.change_priority(
        viewer_email="emp.two@acme.com",
        actor_employee_id=202,
        request_id=queue_id,
        new_priority="P1",
    )
    assert employee_denied["success"] is False
    assert "HR/Manager" in employee_denied["error"]


def test_auto_resolve_action_availability_and_execution(tmp_path: Path):
    service, repo = _build_service(tmp_path)

    now = datetime.now().isoformat(timespec="seconds")
    queue_id = repo.create(
        requester_employee_id=201,
        requester_email="emp.one@acme.com",
        thread_id="thread-12",
        source="AUTO",
        source_ref=None,
        source_message_excerpt="What is the remote work policy?",
        request_type="POLICY_QUESTION",
        request_subtype="POLICY_FAQ",
        classifier_source="rule",
        classifier_confidence=0.9,
        priority="P2",
        risk_level="LOW",
        status="READY",
        next_action="auto_resolve",
        sla_first_response_due_at=now,
        sla_resolution_due_at=now,
        required_fields=[],
        collected_fields={"details": "remote work policy"},
        missing_fields=[],
    )

    item = service.repo.get_by_id(queue_id)
    assert item is not None
    actions = service.get_available_actions("hr.user@acme.com", item)
    assert "auto_resolve" in actions

    result = service.execute_safe_action(
        viewer_email="hr.user@acme.com",
        actor_employee_id=110,
        request_id=queue_id,
        action="auto_resolve",
    )
    assert result["success"] is True
    updated = repo.get_by_id(queue_id)
    assert updated is not None
    assert updated["status"] == "RESOLVED"
