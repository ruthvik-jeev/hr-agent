"""
Holiday Repository - Time-off and leave management data access
"""

from datetime import datetime
from sqlalchemy import text
from .base import BaseRepository


class HolidayRepository(BaseRepository):
    """Repository for holiday/time-off data."""

    # ========== BALANCE & ENTITLEMENTS ==========

    def get_balance(self, employee_id: int, year: int) -> dict:
        """Get holiday balance for an employee."""
        ent = self._execute_query_one(
            """SELECT entitlement_days, carried_over_days
               FROM holiday_entitlement
               WHERE employee_id=:e AND year=:y""",
            {"e": employee_id, "y": year},
        )

        if not ent:
            return {
                "year": year,
                "entitled": 0.0,
                "carried": 0.0,
                "approved_taken": 0.0,
                "pending": 0.0,
                "remaining": 0.0,
            }

        approved = (
            self._execute_scalar(
                """SELECT COALESCE(SUM(days),0)
               FROM holiday_request
               WHERE employee_id=:e AND status='APPROVED' AND substr(start_date,1,4)=:yyyy""",
                {"e": employee_id, "yyyy": str(year)},
            )
            or 0
        )

        pending = (
            self._execute_scalar(
                """SELECT COALESCE(SUM(days),0)
               FROM holiday_request
               WHERE employee_id=:e AND status='PENDING' AND substr(start_date,1,4)=:yyyy""",
                {"e": employee_id, "yyyy": str(year)},
            )
            or 0
        )

        entitled = float(ent["entitlement_days"])
        carried = float(ent["carried_over_days"])

        return {
            "year": year,
            "entitled": entitled,
            "carried": carried,
            "approved_taken": float(approved),
            "pending": float(pending),
            "remaining": entitled + carried - float(approved) - float(pending),
        }

    # ========== REQUESTS ==========

    def get_requests(self, employee_id: int, year: int) -> list[dict]:
        """Get all holiday requests for an employee."""
        return self._execute_query(
            """SELECT request_id, start_date, end_date, days, status, reason,
                      requested_at, reviewed_by, reviewed_at
               FROM holiday_request
               WHERE employee_id=:e AND substr(start_date,1,4)=:yyyy
               ORDER BY start_date""",
            {"e": employee_id, "yyyy": str(year)},
        )

    def get_request_by_id(self, request_id: int) -> dict | None:
        """Get a specific holiday request."""
        return self._execute_query_one(
            """SELECT request_id, employee_id, start_date, end_date, days,
                      status, reason, requested_at
               FROM holiday_request WHERE request_id=:r""",
            {"r": request_id},
        )

    def has_overlapping_request(
        self, employee_id: int, start_date: str, end_date: str
    ) -> bool:
        """Check if there's an overlapping request."""
        result = self._execute_scalar(
            """SELECT request_id FROM holiday_request
               WHERE employee_id=:e AND status IN ('PENDING', 'APPROVED')
               AND NOT (end_date < :start OR start_date > :end)""",
            {"e": employee_id, "start": start_date, "end": end_date},
        )
        return result is not None

    def create_request(
        self,
        employee_id: int,
        start_date: str,
        end_date: str,
        days: float,
        reason: str | None = None,
    ) -> int:
        """Create a new holiday request. Returns request ID."""
        return self._execute_insert(
            """INSERT INTO holiday_request
               (employee_id, start_date, end_date, days, status, reason, requested_at)
               VALUES (:e, :start, :end, :days, 'PENDING', :reason, :now)""",
            {
                "e": employee_id,
                "start": start_date,
                "end": end_date,
                "days": days,
                "reason": reason,
                "now": datetime.now().isoformat(),
            },
        )

    def update_request_status(
        self,
        request_id: int,
        status: str,
        reviewer_id: int | None = None,
        reason: str | None = None,
    ) -> bool:
        """Update request status. Returns True if updated."""
        eng = self._get_engine()
        with eng.begin() as con:
            if status in ("APPROVED", "REJECTED"):
                con.execute(
                    text(
                        """UPDATE holiday_request
                           SET status=:status, reviewed_by=:reviewer, reviewed_at=:now,
                               rejection_reason=:reason
                           WHERE request_id=:r"""
                    ),
                    {
                        "r": request_id,
                        "status": status,
                        "reviewer": reviewer_id,
                        "now": datetime.now().isoformat(),
                        "reason": reason if status == "REJECTED" else None,
                    },
                )
            else:
                con.execute(
                    text(
                        "UPDATE holiday_request SET status=:status WHERE request_id=:r"
                    ),
                    {"r": request_id, "status": status},
                )
        return True

    # ========== MANAGER VIEWS ==========

    def get_pending_for_manager(self, manager_id: int) -> list[dict]:
        """Get pending requests for a manager's direct reports."""
        return self._execute_query(
            """SELECT hr.request_id, hr.employee_id, e.preferred_name,
                      hr.start_date, hr.end_date, hr.days, hr.reason, hr.requested_at
               FROM holiday_request hr
               JOIN employee e ON e.employee_id = hr.employee_id
               JOIN manager_reports mr ON mr.report_employee_id = hr.employee_id
               WHERE mr.manager_employee_id = :m AND hr.status = 'PENDING'
               ORDER BY hr.requested_at""",
            {"m": manager_id},
        )

    def get_request_for_approval(self, manager_id: int, request_id: int) -> dict | None:
        """Get a request that this manager can approve."""
        return self._execute_query_one(
            """SELECT hr.request_id, hr.employee_id, hr.status, e.preferred_name
               FROM holiday_request hr
               JOIN employee e ON e.employee_id = hr.employee_id
               JOIN manager_reports mr ON mr.report_employee_id = hr.employee_id
               WHERE hr.request_id = :r AND mr.manager_employee_id = :m""",
            {"r": request_id, "m": manager_id},
        )

    def get_team_calendar(
        self, manager_id: int, year: int, month: int | None = None
    ) -> list[dict]:
        """Get approved time off for team."""
        date_filter = (
            f"substr(hr.start_date,1,7) = '{year:04d}-{month:02d}'"
            if month
            else f"substr(hr.start_date,1,4) = '{year}'"
        )

        return self._execute_query(
            f"""SELECT hr.request_id, hr.employee_id, e.preferred_name,
                       hr.start_date, hr.end_date, hr.days, hr.status
                FROM holiday_request hr
                JOIN employee e ON e.employee_id = hr.employee_id
                JOIN manager_reports mr ON mr.report_employee_id = hr.employee_id
                WHERE mr.manager_employee_id = :m AND hr.status = 'APPROVED' AND {date_filter}
                ORDER BY hr.start_date""",
            {"m": manager_id},
        )
