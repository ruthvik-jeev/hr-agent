"""
Command Center Repository - HR queue data access.
"""

from datetime import datetime
import json

from .base import BaseRepository


class CommandCenterRepository(BaseRepository):
    """Repository for HR command center requests."""

    OPEN_STATUSES = ("NEW", "NEEDS_INFO", "READY", "IN_PROGRESS")

    def create(
        self,
        requester_employee_id: int,
        requester_email: str,
        thread_id: str,
        source: str,
        source_message_excerpt: str,
        request_type: str,
        request_subtype: str,
        classifier_source: str,
        classifier_confidence: float,
        priority: str,
        risk_level: str,
        status: str,
        next_action: str | None,
        required_fields: list[str],
        collected_fields: dict[str, str],
        missing_fields: list[str],
        source_ref: str | None = None,
        sla_first_response_due_at: str | None = None,
        sla_resolution_due_at: str | None = None,
        ticket_ref: str | None = None,
        escalated_at: str | None = None,
        escalation_reason: str | None = None,
        assigned_to_employee_id: int | None = None,
        last_actor_employee_id: int | None = None,
        notes: str | None = None,
    ) -> int:
        """Create a command center queue item and return its ID."""
        now = datetime.now().isoformat(timespec="seconds")
        return self._execute_insert(
            """INSERT INTO hr_command_center_request (
                 requester_employee_id,
                 requester_email,
                 thread_id,
                 source,
                 source_ref,
                 source_message_excerpt,
                 request_type,
                 request_subtype,
                 classifier_source,
                 classifier_confidence,
                 priority,
                 risk_level,
                 status,
                 next_action,
                 sla_first_response_due_at,
                 sla_resolution_due_at,
                 required_fields_json,
                 collected_fields_json,
                 missing_fields_json,
                 ticket_ref,
                 escalated_at,
                 escalation_reason,
                 assigned_to_employee_id,
                 last_actor_employee_id,
                 notes,
                 created_at,
                 updated_at
               ) VALUES (
                 :requester_employee_id,
                 :requester_email,
                 :thread_id,
                 :source,
                 :source_ref,
                 :source_message_excerpt,
                 :request_type,
                 :request_subtype,
                 :classifier_source,
                 :classifier_confidence,
                 :priority,
                 :risk_level,
                 :status,
                 :next_action,
                 :sla_first_response_due_at,
                 :sla_resolution_due_at,
                 :required_fields_json,
                 :collected_fields_json,
                 :missing_fields_json,
                 :ticket_ref,
                 :escalated_at,
                 :escalation_reason,
                 :assigned_to_employee_id,
                 :last_actor_employee_id,
                 :notes,
                 :created_at,
                 :updated_at
               )""",
            {
                "requester_employee_id": requester_employee_id,
                "requester_email": requester_email,
                "thread_id": thread_id,
                "source": source,
                "source_ref": source_ref,
                "source_message_excerpt": source_message_excerpt,
                "request_type": request_type,
                "request_subtype": request_subtype,
                "classifier_source": classifier_source,
                "classifier_confidence": classifier_confidence,
                "priority": priority,
                "risk_level": risk_level,
                "status": status,
                "next_action": next_action,
                "sla_first_response_due_at": sla_first_response_due_at,
                "sla_resolution_due_at": sla_resolution_due_at,
                "required_fields_json": json.dumps(required_fields),
                "collected_fields_json": json.dumps(collected_fields),
                "missing_fields_json": json.dumps(missing_fields),
                "ticket_ref": ticket_ref,
                "escalated_at": escalated_at,
                "escalation_reason": escalation_reason,
                "assigned_to_employee_id": assigned_to_employee_id,
                "last_actor_employee_id": last_actor_employee_id,
                "notes": notes,
                "created_at": now,
                "updated_at": now,
            },
        )

    def get_by_id(self, queue_id: int) -> dict | None:
        """Get a single command center request."""
        row = self._execute_query_one(
            """SELECT *
               FROM hr_command_center_request
               WHERE request_id = :request_id""",
            {"request_id": queue_id},
        )
        return self._deserialize_row(row)

    def find_latest_open_for_thread(
        self, requester_email: str, thread_id: str
    ) -> dict | None:
        """Get the latest open command center item for a thread."""
        row = self._execute_query_one(
            """SELECT *
               FROM hr_command_center_request
               WHERE requester_email = :requester_email
                 AND thread_id = :thread_id
                 AND status IN ('NEW', 'NEEDS_INFO', 'READY', 'IN_PROGRESS')
               ORDER BY updated_at DESC
               LIMIT 1""",
            {"requester_email": requester_email, "thread_id": thread_id},
        )
        return self._deserialize_row(row)

    def list_for_hr(self, status: str | None = None, limit: int = 100) -> list[dict]:
        """List queue items visible to HR users."""
        params: dict[str, str | int] = {"limit": limit}
        filter_clause = ""
        if status:
            filter_clause = " AND status = :status"
            params["status"] = status
        rows = self._execute_query(
            f"""SELECT *
                FROM hr_command_center_request
                WHERE 1=1 {filter_clause}
                ORDER BY
                  CASE WHEN status = 'RESOLVED' THEN 1 ELSE 0 END ASC,
                  CASE
                    WHEN status <> 'RESOLVED'
                      AND sla_resolution_due_at IS NOT NULL
                      AND datetime(sla_resolution_due_at) <= datetime('now')
                    THEN 0 ELSE 1
                  END ASC,
                  CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END ASC,
                  CASE risk_level WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END ASC,
                  datetime(created_at) ASC
                LIMIT :limit""",
            params,
        )
        return [self._deserialize_row(row) for row in rows]

    def list_for_manager(
        self, manager_employee_id: int, status: str | None = None, limit: int = 100
    ) -> list[dict]:
        """List queue items visible to a manager."""
        params: dict[str, str | int] = {
            "manager_employee_id": manager_employee_id,
            "limit": limit,
        }
        filter_clause = ""
        if status:
            filter_clause = " AND r.status = :status"
            params["status"] = status
        rows = self._execute_query(
            f"""SELECT r.*
                FROM hr_command_center_request r
                WHERE (
                  r.requester_employee_id = :manager_employee_id
                  OR EXISTS (
                    SELECT 1
                    FROM manager_reports mr
                    WHERE mr.manager_employee_id = :manager_employee_id
                      AND mr.report_employee_id = r.requester_employee_id
                  )
                ) {filter_clause}
                ORDER BY
                  CASE WHEN r.status = 'RESOLVED' THEN 1 ELSE 0 END ASC,
                  CASE
                    WHEN r.status <> 'RESOLVED'
                      AND r.sla_resolution_due_at IS NOT NULL
                      AND datetime(r.sla_resolution_due_at) <= datetime('now')
                    THEN 0 ELSE 1
                  END ASC,
                  CASE r.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END ASC,
                  CASE r.risk_level WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END ASC,
                  datetime(r.created_at) ASC
                LIMIT :limit""",
            params,
        )
        return [self._deserialize_row(row) for row in rows]

    def list_for_requester(
        self, requester_email: str, status: str | None = None, limit: int = 100
    ) -> list[dict]:
        """List queue items visible to a requester."""
        params: dict[str, str | int] = {
            "requester_email": requester_email,
            "limit": limit,
        }
        filter_clause = ""
        if status:
            filter_clause = " AND status = :status"
            params["status"] = status
        rows = self._execute_query(
            f"""SELECT *
                FROM hr_command_center_request
                WHERE requester_email = :requester_email {filter_clause}
                ORDER BY datetime(created_at) DESC
                LIMIT :limit""",
            params,
        )
        return [self._deserialize_row(row) for row in rows]

    def list_counts_for_scope(
        self, scope: str, scope_value: str | int | None = None
    ) -> dict[str, int]:
        """List aggregate counts by scope (`hr`, `manager`, or `requester`)."""
        where_clause = "1=1"
        params: dict[str, str | int] = {}
        if scope == "manager":
            where_clause = """
                (
                  requester_employee_id = :manager_employee_id
                  OR EXISTS (
                    SELECT 1
                    FROM manager_reports mr
                    WHERE mr.manager_employee_id = :manager_employee_id
                      AND mr.report_employee_id = hr_command_center_request.requester_employee_id
                  )
                )
            """
            params["manager_employee_id"] = int(scope_value or 0)
        elif scope == "requester":
            where_clause = "requester_email = :requester_email"
            params["requester_email"] = str(scope_value or "")

        row = self._execute_query_one(
            f"""SELECT
                  COUNT(*) AS total,
                  SUM(CASE WHEN status='NEW' THEN 1 ELSE 0 END) AS new_count,
                  SUM(CASE WHEN status='NEEDS_INFO' THEN 1 ELSE 0 END) AS needs_info,
                  SUM(CASE WHEN status='READY' THEN 1 ELSE 0 END) AS ready_count,
                  SUM(CASE WHEN status='IN_PROGRESS' THEN 1 ELSE 0 END) AS in_progress,
                  SUM(CASE WHEN status='ESCALATED' THEN 1 ELSE 0 END) AS escalated_count,
                  SUM(CASE WHEN status='RESOLVED' THEN 1 ELSE 0 END) AS resolved_count,
                  SUM(
                    CASE
                      WHEN status <> 'RESOLVED'
                        AND sla_resolution_due_at IS NOT NULL
                        AND datetime(sla_resolution_due_at) <= datetime('now')
                      THEN 1 ELSE 0
                    END
                  ) AS overdue_count
                FROM hr_command_center_request
                WHERE {where_clause}""",
            params,
        )
        if not row:
            return {
                "total": 0,
                "new": 0,
                "needs_info": 0,
                "ready": 0,
                "in_progress": 0,
                "escalated": 0,
                "resolved": 0,
                "overdue": 0,
            }
        return {
            "total": int(row.get("total") or 0),
            "new": int(row.get("new_count") or 0),
            "needs_info": int(row.get("needs_info") or 0),
            "ready": int(row.get("ready_count") or 0),
            "in_progress": int(row.get("in_progress") or 0),
            "escalated": int(row.get("escalated_count") or 0),
            "resolved": int(row.get("resolved_count") or 0),
            "overdue": int(row.get("overdue_count") or 0),
        }

    def update_request(self, queue_id: int, fields: dict[str, object]) -> bool:
        """Update arbitrary request fields."""
        if not fields:
            return False
        columns = []
        params: dict[str, object] = {}
        for key, value in fields.items():
            columns.append(f"{key} = :{key}")
            params[key] = value
        params["request_id"] = queue_id
        params["updated_at"] = datetime.now().isoformat(timespec="seconds")
        set_clause = ", ".join(columns + ["updated_at = :updated_at"])
        rows = self._execute_update(
            f"""UPDATE hr_command_center_request
                SET {set_clause}
                WHERE request_id = :request_id""",
            params,
        )
        return rows > 0

    def transition_status(
        self,
        queue_id: int,
        new_status: str,
        actor_employee_id: int | None,
        next_action: str | None = None,
        notes: str | None = None,
    ) -> bool:
        """Transition queue item status."""
        rows = self._execute_update(
            """UPDATE hr_command_center_request
               SET status = :status,
                   next_action = :next_action,
                   last_actor_employee_id = :last_actor_employee_id,
                   notes = COALESCE(:notes, notes),
                   updated_at = :updated_at
               WHERE request_id = :request_id""",
            {
                "status": new_status,
                "next_action": next_action,
                "last_actor_employee_id": actor_employee_id,
                "notes": notes,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "request_id": queue_id,
            },
        )
        return rows > 0

    def _deserialize_row(self, row: dict | None) -> dict | None:
        """Deserialize JSON columns for application use."""
        if row is None:
            return None
        result = dict(row)
        for col in ("required_fields_json", "missing_fields_json"):
            raw = result.get(col)
            try:
                result[col] = json.loads(raw) if raw else []
            except json.JSONDecodeError:
                result[col] = []
        raw_collected = result.get("collected_fields_json")
        try:
            result["collected_fields_json"] = (
                json.loads(raw_collected) if raw_collected else {}
            )
        except json.JSONDecodeError:
            result["collected_fields_json"] = {}
        return result
