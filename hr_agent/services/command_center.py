"""
Command center service - queue workflow and triage business rules.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import re
from typing import Any

from ..configs.config import settings, get_normalized_llm_base_url
from ..domain.models import Priority, QueueSource, QueueStatus, RequestType, RiskLevel
from ..repositories import get_command_center_repo, get_employee_repo


class CommandCenterService:
    """Business logic for the HR command center workflow."""

    TRIAGE_ROLES = {"HR", "MANAGER"}
    ALLOWED_STATUSES = {status.value for status in QueueStatus}
    ALLOWED_TRANSITIONS = {
        QueueStatus.NEW.value: {
            QueueStatus.NEEDS_INFO.value,
            QueueStatus.READY.value,
            QueueStatus.IN_PROGRESS.value,
            QueueStatus.ESCALATED.value,
            QueueStatus.RESOLVED.value,
        },
        QueueStatus.NEEDS_INFO.value: {
            QueueStatus.READY.value,
            QueueStatus.ESCALATED.value,
        },
        QueueStatus.READY.value: {
            QueueStatus.NEEDS_INFO.value,
            QueueStatus.IN_PROGRESS.value,
            QueueStatus.RESOLVED.value,
            QueueStatus.ESCALATED.value,
        },
        QueueStatus.IN_PROGRESS.value: {
            QueueStatus.NEEDS_INFO.value,
            QueueStatus.RESOLVED.value,
            QueueStatus.ESCALATED.value,
        },
        QueueStatus.ESCALATED.value: {
            QueueStatus.IN_PROGRESS.value,
            QueueStatus.RESOLVED.value,
        },
        QueueStatus.RESOLVED.value: {
            QueueStatus.IN_PROGRESS.value,
        },
    }

    SLA_HOURS = {
        Priority.P0.value: (2, 24),
        Priority.P1.value: (8, 72),
        Priority.P2.value: (24, 120),
    }

    CLASSIFICATION_RULES = [
        {
            "request_type": RequestType.PAYROLL_QUERY.value,
            "request_subtype": "PAYROLL_DISCREPANCY",
            "keywords": {
                "payroll",
                "salary",
                "payslip",
                "pay slip",
                "not paid",
                "underpaid",
                "deduction",
                "wrong pay",
            },
        },
        {
            "request_type": RequestType.LEAVE_PROBLEM.value,
            "request_subtype": "LEAVE_CORRECTION",
            "keywords": {
                "leave",
                "pto",
                "vacation",
                "holiday request",
                "time off",
                "leave balance",
                "sick day",
            },
        },
        {
            "request_type": RequestType.CLAIMS.value,
            "request_subtype": "CLAIM_REIMBURSEMENT",
            "keywords": {
                "claim",
                "reimburse",
                "expense",
                "receipt",
                "medical claim",
                "insurance claim",
            },
        },
        {
            "request_type": RequestType.ONBOARDING_OFFBOARDING.value,
            "request_subtype": "ONBOARDING_TASK",
            "keywords": {
                "onboarding",
                "new joiner",
                "new hire",
                "probation",
                "orientation",
            },
        },
        {
            "request_type": RequestType.ONBOARDING_OFFBOARDING.value,
            "request_subtype": "OFFBOARDING_TASK",
            "keywords": {
                "offboarding",
                "exit",
                "resignation",
                "termination",
                "last working day",
            },
        },
        {
            "request_type": RequestType.POLICY_QUESTION.value,
            "request_subtype": "POLICY_FAQ",
            "keywords": {
                "policy",
                "guideline",
                "rule",
                "remote work",
                "benefit",
                "holiday policy",
                "code of conduct",
            },
        },
        {
            "request_type": RequestType.ESCALATION.value,
            "request_subtype": "GENERAL_ESCALATION",
            "keywords": {
                "escalate",
                "complaint",
                "urgent",
                "critical",
                "sensitive",
                "risk",
                "manager issue",
            },
        },
    ]

    REQUIRED_FIELDS_BY_SUBTYPE = {
        "LEAVE_CORRECTION": ["leave_dates"],
        "PAYROLL_DISCREPANCY": ["pay_period", "details"],
        "CLAIM_REIMBURSEMENT": ["claim_id", "details"],
        "ONBOARDING_TASK": ["employee_name_or_id", "details"],
        "OFFBOARDING_TASK": ["employee_name_or_id", "details"],
        "GENERAL_ESCALATION": ["details"],
        "POLICY_FAQ": [],
    }

    HIGH_RISK_KEYWORDS = {
        "harassment",
        "discrimination",
        "legal",
        "lawsuit",
        "fraud",
        "security breach",
        "data leak",
        "retaliation",
        "compliance",
        "threat",
    }

    HR_KEYWORDS = {
        "leave",
        "pto",
        "vacation",
        "payroll",
        "pay period",
        "salary",
        "payslip",
        "benefit",
        "policy",
        "claim",
        "onboarding",
        "offboarding",
        "resignation",
        "termination",
        "hr",
        "human resources",
        "manager",
        "escalate",
        "harassment",
        "retaliation",
        "legal",
    }

    def __init__(self):
        self.repo = get_command_center_repo()
        self.employee_repo = get_employee_repo()

    def ingest_user_turn(
        self,
        requester_employee_id: int,
        requester_email: str,
        thread_id: str,
        message: str,
        source: str = QueueSource.AUTO.value,
        source_ref: str | None = None,
    ) -> dict:
        """Ingest user prompt into the command-center queue."""
        text = (message or "").strip()
        if not text:
            return {"success": False, "queued": False, "error": "Empty message."}

        latest_open = self.repo.find_latest_open_for_thread(requester_email, thread_id)
        if latest_open and latest_open["status"] == QueueStatus.NEEDS_INFO.value:
            updated = self._merge_slot_fields(
                queue_item=latest_open,
                incoming_text=text,
                actor_employee_id=requester_employee_id,
            )
            if updated:
                return {
                    "success": True,
                    "queued": True,
                    "updated": True,
                    "request_id": latest_open["request_id"],
                    "status": updated["status"],
                }

        if source == QueueSource.AUTO.value and not self._is_hr_related(text):
            return {"success": True, "queued": False, "reason": "Not HR-related."}

        classification = self._classify_message(text)
        if classification is None and source == QueueSource.MANUAL_ESCALATION.value:
            classification = {
                "request_type": RequestType.ESCALATION.value,
                "request_subtype": "GENERAL_ESCALATION",
                "classifier_source": "rule_manual",
                "confidence": 0.8,
            }
        if classification is None:
            return {"success": True, "queued": False, "reason": "Not classifiable."}

        priority, risk_level, risk_reason = self._score_priority_and_risk(
            text, classification["request_type"]
        )
        first_due, resolution_due = self._calculate_sla_due_at(priority)
        collected_fields = self._extract_slot_values(text)
        required_fields = self.REQUIRED_FIELDS_BY_SUBTYPE.get(
            classification["request_subtype"], ["details"]
        )
        missing_fields = [
            key for key in required_fields if not collected_fields.get(key)
        ]

        status, next_action = self._determine_initial_state(
            source=source,
            request_type=classification["request_type"],
            risk_level=risk_level,
            missing_fields=missing_fields,
        )

        queue_id = self.repo.create(
            requester_employee_id=requester_employee_id,
            requester_email=requester_email,
            thread_id=thread_id,
            source=source,
            source_ref=source_ref,
            source_message_excerpt=self._short_text(text, 240),
            request_type=classification["request_type"],
            request_subtype=classification["request_subtype"],
            classifier_source=classification["classifier_source"],
            classifier_confidence=classification["confidence"],
            priority=priority,
            risk_level=risk_level,
            status=status,
            next_action=next_action,
            sla_first_response_due_at=first_due,
            sla_resolution_due_at=resolution_due,
            required_fields=required_fields,
            collected_fields=collected_fields,
            missing_fields=missing_fields,
            notes=risk_reason,
        )

        # Sensitive/risky requests are handed off with a ticket stub.
        if risk_level == RiskLevel.HIGH.value and status != QueueStatus.RESOLVED.value:
            ticket_ref = self._ticket_ref(queue_id)
            self.repo.update_request(
                queue_id,
                {
                    "status": QueueStatus.ESCALATED.value,
                    "next_action": "start_work",
                    "ticket_ref": ticket_ref,
                    "escalated_at": datetime.now().isoformat(timespec="seconds"),
                    "escalation_reason": "sensitive_or_risky",
                },
            )
            status = QueueStatus.ESCALATED.value

        return {
            "success": True,
            "queued": True,
            "updated": False,
            "request_id": queue_id,
            "status": status,
        }

    def list_requests(
        self, viewer_email: str, status: str | None = None, limit: int = 100
    ) -> list[dict]:
        """List queue items for viewer scope."""
        role = self.employee_repo.get_role_by_email(viewer_email)
        if status and status not in self.ALLOWED_STATUSES:
            return []

        if role == "HR":
            rows = self.repo.list_for_hr(status=status, limit=limit)
        elif role == "MANAGER":
            viewer = self.employee_repo.get_by_email(viewer_email) or {}
            rows = self.repo.list_for_manager(
                manager_employee_id=int(viewer.get("employee_id") or 0),
                status=status,
                limit=limit,
            )
        else:
            rows = self.repo.list_for_requester(
                requester_email=viewer_email, status=status, limit=limit
            )
        return [self._normalize_row(row) for row in rows]

    def list_counts(self, viewer_email: str) -> dict[str, int]:
        """Return aggregate queue metrics for the viewer."""
        role = self.employee_repo.get_role_by_email(viewer_email)
        if role == "HR":
            return self.repo.list_counts_for_scope("hr")
        if role == "MANAGER":
            viewer = self.employee_repo.get_by_email(viewer_email) or {}
            return self.repo.list_counts_for_scope(
                "manager", scope_value=int(viewer.get("employee_id") or 0)
            )
        return self.repo.list_counts_for_scope("requester", scope_value=viewer_email)

    def get_available_actions(self, viewer_email: str, item: dict) -> list[str]:
        """Compute available safe actions for UI action rendering."""
        role = self.employee_repo.get_role_by_email(viewer_email)
        if role not in self.TRIAGE_ROLES:
            return []

        status = item.get("status")
        actions: list[str] = []
        if status in {QueueStatus.NEW.value, QueueStatus.READY.value}:
            actions.extend(["start_work", "escalate_ticket"])
        elif status == QueueStatus.NEEDS_INFO.value:
            actions.append("escalate_ticket")
        elif status == QueueStatus.IN_PROGRESS.value:
            actions.extend(["resolve", "escalate_ticket"])
        elif status == QueueStatus.ESCALATED.value:
            actions.extend(["start_work", "resolve"])
        elif status == QueueStatus.RESOLVED.value:
            actions.append("reopen")

        if (
            status == QueueStatus.READY.value
            and item.get("request_type") == RequestType.POLICY_QUESTION.value
            and item.get("risk_level") == RiskLevel.LOW.value
        ):
            actions.insert(0, "auto_resolve")
        return actions

    def execute_safe_action(
        self,
        viewer_email: str,
        actor_employee_id: int,
        request_id: int,
        action: str,
    ) -> dict:
        """Execute a safe workflow action."""
        item = self.repo.get_by_id(request_id)
        if not item:
            return {"success": False, "error": "Queue item not found."}

        role = self.employee_repo.get_role_by_email(viewer_email)
        if role not in self.TRIAGE_ROLES:
            return {"success": False, "error": "Only HR/Manager can triage requests."}

        if not self._can_view_item(viewer_email, item, role):
            return {"success": False, "error": "Not authorized for this request."}

        if action == "start_work":
            return self._transition_with_validation(
                item=item,
                actor_employee_id=actor_employee_id,
                new_status=QueueStatus.IN_PROGRESS.value,
                next_action="resolve",
            )
        if action in {"resolve", "auto_resolve"}:
            return self._transition_with_validation(
                item=item,
                actor_employee_id=actor_employee_id,
                new_status=QueueStatus.RESOLVED.value,
                next_action=None,
            )
        if action == "reopen":
            return self._transition_with_validation(
                item=item,
                actor_employee_id=actor_employee_id,
                new_status=QueueStatus.IN_PROGRESS.value,
                next_action="resolve",
            )
        if action == "escalate_ticket":
            if item["status"] == QueueStatus.RESOLVED.value:
                return {
                    "success": False,
                    "error": "Cannot escalate a resolved request.",
                }
            ticket_ref = item.get("ticket_ref") or self._ticket_ref(item["request_id"])
            ok = self.repo.update_request(
                item["request_id"],
                {
                    "status": QueueStatus.ESCALATED.value,
                    "next_action": "start_work",
                    "ticket_ref": ticket_ref,
                    "escalated_at": datetime.now().isoformat(timespec="seconds"),
                    "escalation_reason": "manual_triage",
                    "last_actor_employee_id": actor_employee_id,
                },
            )
            if not ok:
                return {"success": False, "error": "Failed to escalate request."}
            return {"success": True, "ticket_ref": ticket_ref}

        return {"success": False, "error": f"Unsupported action: {action}"}

    def _transition_with_validation(
        self,
        item: dict,
        actor_employee_id: int,
        new_status: str,
        next_action: str | None,
    ) -> dict:
        current_status = item["status"]
        allowed_next = self.ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed_next:
            return {
                "success": False,
                "error": f"Invalid transition: {current_status} -> {new_status}.",
            }
        ok = self.repo.transition_status(
            queue_id=item["request_id"],
            new_status=new_status,
            next_action=next_action,
            actor_employee_id=actor_employee_id,
        )
        if not ok:
            return {"success": False, "error": "Failed to update request."}
        return {"success": True}

    # ── Assignment ───────────────────────────────────────────────────────

    def assign_request(
        self,
        viewer_email: str,
        actor_employee_id: int,
        request_id: int,
        assignee_employee_id: int,
    ) -> dict:
        """Assign or reassign a request to an HR/Manager user."""
        item = self.repo.get_by_id(request_id)
        if not item:
            return {"success": False, "error": "Queue item not found."}

        role = self.employee_repo.get_role_by_email(viewer_email)
        if role not in self.TRIAGE_ROLES:
            return {"success": False, "error": "Only HR/Manager can assign requests."}

        if not self._can_view_item(viewer_email, item, role):
            return {"success": False, "error": "Not authorized for this request."}

        ok = self.repo.update_request(
            request_id,
            {
                "assigned_to_employee_id": assignee_employee_id,
                "last_actor_employee_id": actor_employee_id,
            },
        )
        if not ok:
            return {"success": False, "error": "Failed to assign request."}
        return {"success": True}

    # ── Priority change ──────────────────────────────────────────────────

    def change_priority(
        self,
        viewer_email: str,
        actor_employee_id: int,
        request_id: int,
        new_priority: str,
    ) -> dict:
        """Manually change the priority of a request."""
        valid_priorities = {p.value for p in Priority}
        if new_priority not in valid_priorities:
            return {
                "success": False,
                "error": f"Invalid priority. Must be one of: {', '.join(sorted(valid_priorities))}",
            }

        item = self.repo.get_by_id(request_id)
        if not item:
            return {"success": False, "error": "Queue item not found."}

        role = self.employee_repo.get_role_by_email(viewer_email)
        if role not in self.TRIAGE_ROLES:
            return {"success": False, "error": "Only HR/Manager can change priority."}

        if not self._can_view_item(viewer_email, item, role):
            return {"success": False, "error": "Not authorized for this request."}

        # Recalculate SLA based on new priority
        first_response_h, resolution_h = self.SLA_HOURS.get(
            new_priority, self.SLA_HOURS[Priority.P2.value]
        )
        created_at = datetime.fromisoformat(item["created_at"])
        new_sla_first = (created_at + timedelta(hours=first_response_h)).isoformat(
            timespec="seconds"
        )
        new_sla_resolution = (created_at + timedelta(hours=resolution_h)).isoformat(
            timespec="seconds"
        )

        ok = self.repo.update_request(
            request_id,
            {
                "priority": new_priority,
                "sla_first_response_due_at": new_sla_first,
                "sla_resolution_due_at": new_sla_resolution,
                "last_actor_employee_id": actor_employee_id,
            },
        )
        if not ok:
            return {"success": False, "error": "Failed to update priority."}
        return {"success": True}

    def _can_view_item(self, viewer_email: str, item: dict, role: str) -> bool:
        if role == "HR":
            return True
        if role == "MANAGER":
            viewer = self.employee_repo.get_by_email(viewer_email) or {}
            manager_id = viewer.get("employee_id")
            if not manager_id:
                return False
            target_id = int(item["requester_employee_id"])
            return target_id == manager_id or self.employee_repo.is_direct_report(
                int(manager_id), target_id
            )
        return item["requester_email"] == viewer_email

    def _merge_slot_fields(
        self, queue_item: dict, incoming_text: str, actor_employee_id: int
    ) -> dict | None:
        new_values = self._extract_slot_values(incoming_text)
        if not new_values:
            return None
        collected = dict(queue_item.get("collected_fields_json", {}))
        required = list(queue_item.get("required_fields_json", []))
        changed = False
        for key, value in new_values.items():
            if value and collected.get(key) != value:
                collected[key] = value
                changed = True
        if not changed:
            return None

        missing = [key for key in required if not collected.get(key)]
        new_status = (
            QueueStatus.READY.value if not missing else QueueStatus.NEEDS_INFO.value
        )
        next_action = "start_work" if not missing else "collect_missing_fields"
        ok = self.repo.update_request(
            queue_item["request_id"],
            {
                "collected_fields_json": json.dumps(collected),
                "missing_fields_json": json.dumps(missing),
                "status": new_status,
                "next_action": next_action,
                "last_actor_employee_id": actor_employee_id,
            },
        )
        if not ok:
            return None
        return {
            "status": new_status,
            "missing_fields": missing,
            "collected_fields": collected,
        }

    def _determine_initial_state(
        self,
        source: str,
        request_type: str,
        risk_level: str,
        missing_fields: list[str],
    ) -> tuple[str, str | None]:
        if source == QueueSource.MANUAL_ESCALATION.value:
            return QueueStatus.NEW.value, "start_work"
        if missing_fields:
            return QueueStatus.NEEDS_INFO.value, "collect_missing_fields"
        if self._can_auto_resolve(request_type=request_type, risk_level=risk_level):
            return QueueStatus.RESOLVED.value, None
        if risk_level == RiskLevel.HIGH.value:
            return QueueStatus.READY.value, "escalate_ticket"
        return QueueStatus.READY.value, "start_work"

    def _can_auto_resolve(self, request_type: str, risk_level: str) -> bool:
        return (
            request_type == RequestType.POLICY_QUESTION.value
            and risk_level == RiskLevel.LOW.value
        )

    def _classify_message(self, text: str) -> dict | None:
        lower_text = text.lower()
        best_rule: dict[str, Any] | None = None
        best_score = 0

        for rule in self.CLASSIFICATION_RULES:
            score = sum(1 for keyword in rule["keywords"] if keyword in lower_text)
            if score > best_score:
                best_score = score
                best_rule = rule

        if not best_rule:
            if not self._is_hr_related(lower_text):
                return None
            fallback = {
                "request_type": RequestType.ESCALATION.value,
                "request_subtype": "GENERAL_ESCALATION",
                "classifier_source": "rule",
                "confidence": 0.45,
            }
            llm_result = self._classify_with_llm(lower_text, fallback)
            return llm_result or fallback

        confidence = min(0.6 + (best_score * 0.12), 0.9)
        result = {
            "request_type": best_rule["request_type"],
            "request_subtype": best_rule["request_subtype"],
            "classifier_source": "rule",
            "confidence": confidence,
        }

        if confidence < 0.7:
            llm_result = self._classify_with_llm(lower_text, result)
            if llm_result:
                return llm_result
        return result

    def _classify_with_llm(self, text: str, fallback: dict) -> dict | None:
        if not settings.llm_api_key:
            return None

        try:
            from langchain_openai import ChatOpenAI
        except Exception:
            return None

        try:
            base_url = get_normalized_llm_base_url()
            if base_url:
                llm = ChatOpenAI(
                    model=settings.llm_model,
                    api_key=settings.llm_api_key,
                    base_url=base_url,
                    temperature=0,
                )
            else:
                llm = ChatOpenAI(
                    model=settings.llm_model,
                    api_key=settings.llm_api_key,
                    temperature=0,
                )
            prompt = (
                "Classify this HR request and return JSON only with keys: "
                "request_type, request_subtype, confidence. "
                "Allowed request_type values: POLICY_QUESTION, LEAVE_PROBLEM, "
                "PAYROLL_QUERY, CLAIMS, ONBOARDING_OFFBOARDING, ESCALATION. "
                f"Text: {text}"
            )
            response = llm.invoke(prompt).content
            parsed = json.loads(response)
            request_type = str(parsed.get("request_type") or "")
            request_subtype = str(parsed.get("request_subtype") or "")
            confidence = float(parsed.get("confidence") or 0)
            if request_type not in {item.value for item in RequestType}:
                return None
            if not request_subtype:
                return None
            if confidence <= 0:
                confidence = fallback["confidence"]
            return {
                "request_type": request_type,
                "request_subtype": request_subtype,
                "classifier_source": "llm",
                "confidence": min(max(confidence, 0.0), 1.0),
            }
        except Exception:
            return None

    def _score_priority_and_risk(
        self, text: str, request_type: str
    ) -> tuple[str, str, str]:
        lower = text.lower()
        risk = RiskLevel.LOW.value
        priority = Priority.P2.value
        reason = "Default policy priority/risk."

        if request_type == RequestType.PAYROLL_QUERY.value:
            priority = Priority.P1.value
            risk = RiskLevel.MEDIUM.value
            reason = "Payroll queries are medium operational risk."
            if any(
                marker in lower
                for marker in ("not paid", "underpaid", "missing salary", "wrong pay")
            ):
                priority = Priority.P0.value
                risk = RiskLevel.HIGH.value
                reason = "Payroll discrepancy with potential critical impact."
        elif request_type in (
            RequestType.LEAVE_PROBLEM.value,
            RequestType.CLAIMS.value,
            RequestType.ONBOARDING_OFFBOARDING.value,
            RequestType.ESCALATION.value,
        ):
            priority = Priority.P1.value
            risk = RiskLevel.MEDIUM.value
            reason = "Operational HR workflow request."

        if any(keyword in lower for keyword in self.HIGH_RISK_KEYWORDS):
            priority = Priority.P0.value
            risk = RiskLevel.HIGH.value
            reason = "Sensitive/risky request keywords detected."
        elif any(urgent in lower for urgent in ("urgent", "asap", "immediately")):
            if priority == Priority.P2.value:
                priority = Priority.P1.value
            reason = "Urgency marker detected."

        return priority, risk, reason

    def _calculate_sla_due_at(self, priority: str) -> tuple[str, str]:
        first_hours, resolution_hours = self.SLA_HOURS.get(
            priority, self.SLA_HOURS[Priority.P2.value]
        )
        now = datetime.now()
        first_due = now + timedelta(hours=first_hours)
        resolution_due = now + timedelta(hours=resolution_hours)
        return (
            first_due.isoformat(timespec="seconds"),
            resolution_due.isoformat(timespec="seconds"),
        )

    def _extract_slot_values(self, text: str) -> dict[str, str]:
        values: dict[str, str] = {}
        lower = text.lower()
        if len(text.strip()) >= 15:
            values["details"] = text.strip()

        date_match = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
        if date_match:
            values["leave_dates"] = ", ".join(date_match[:2])

        month_match = re.search(r"\b(20\d{2}[-/](0[1-9]|1[0-2]))\b", text)
        if month_match:
            values["pay_period"] = month_match.group(1)

        claim_match = re.search(
            r"\b(claim|case|ticket)\s*#?\s*([A-Za-z0-9-]+)\b", lower
        )
        if claim_match:
            values["claim_id"] = claim_match.group(2).upper()

        employee_match = re.search(r"\bemployee\s*(id)?\s*#?\s*(\d+)\b", lower)
        if employee_match:
            values["employee_name_or_id"] = employee_match.group(2)

        return values

    def _normalize_row(self, row: dict) -> dict:
        normalized = dict(row)
        normalized["required_fields"] = list(row.get("required_fields_json", []))
        normalized["collected_fields"] = dict(row.get("collected_fields_json", {}))
        normalized["missing_fields"] = list(row.get("missing_fields_json", []))
        due = normalized.get("sla_resolution_due_at")
        if due:
            try:
                normalized["is_overdue"] = datetime.fromisoformat(due) <= datetime.now()
            except ValueError:
                normalized["is_overdue"] = False
        else:
            normalized["is_overdue"] = False
        return normalized

    def _is_hr_related(self, text: str) -> bool:
        lower = text.lower()
        return any(keyword in lower for keyword in self.HR_KEYWORDS)

    def _short_text(self, text: str, max_len: int) -> str:
        clean = (text or "").strip()
        if len(clean) <= max_len:
            return clean
        return clean[: max_len - 1].rstrip() + "..."

    def _ticket_ref(self, request_id: int) -> str:
        date_part = datetime.now().strftime("%Y%m%d")
        return f"HR-TKT-{date_part}-{request_id:06d}"


_command_center_service: CommandCenterService | None = None


def get_command_center_service() -> CommandCenterService:
    """Singleton accessor for command center service."""
    global _command_center_service
    if _command_center_service is None:
        _command_center_service = CommandCenterService()
    return _command_center_service
