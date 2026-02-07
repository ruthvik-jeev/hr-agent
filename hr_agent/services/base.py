"""
Service Layer - Business Logic

This layer contains all business logic and uses repositories for data access.
Services are the main interface that tools/agent should use.

Benefits:
- Business logic is separated from data access
- Easy to test with mock repositories
- Clear, readable operations without SQL
"""

from datetime import datetime, date
from ..repositories import (
    get_employee_repo,
    get_holiday_repo,
    get_compensation_repo,
    get_company_repo,
)


# ============================================================================
# EMPLOYEE SERVICE
# ============================================================================


class EmployeeService:
    """Service for employee and organization operations."""

    def __init__(self):
        self.repo = get_employee_repo()

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search employees by name, email, or title."""
        return self.repo.search(query, limit)

    def get_basic_info(self, employee_id: int) -> dict | None:
        """Get basic employee information."""
        return self.repo.get_by_id(employee_id)

    def get_tenure(self, employee_id: int) -> dict | None:
        """Get employee tenure information."""
        return self.repo.get_tenure(employee_id)

    def get_manager(self, employee_id: int) -> dict | None:
        """Get the direct manager of an employee."""
        return self.repo.get_manager(employee_id)

    def get_direct_reports(self, manager_id: int) -> list[dict]:
        """Get all direct reports for a manager."""
        return self.repo.get_direct_reports(manager_id)

    def get_manager_chain(self, employee_id: int, max_depth: int = 6) -> list[dict]:
        """Get the full management chain up to CEO."""
        return self.repo.get_manager_chain(employee_id, max_depth)

    def get_team_overview(self, manager_id: int) -> dict:
        """Get a summary of a manager's team."""
        return self.repo.get_team_overview(manager_id)

    def get_department_directory(self, department: str) -> list[dict]:
        """Get all employees in a department."""
        return self.repo.get_department_members(department)

    def get_org_chart(self, root_id: int | None = None, max_depth: int = 3) -> dict:
        """Get organizational chart."""
        return self.repo.get_org_chart(root_id, max_depth)

    def get_cost_center(self, employee_id: int) -> str | None:
        """Get employee's cost center."""
        return self.repo.get_cost_center(employee_id)

    def get_requester_context(self, user_email: str) -> dict:
        """Get full context for a requester (used by agent)."""
        emp_id = self.repo.get_employee_id_by_email(user_email)
        if emp_id is None:
            raise ValueError(f"No employee found for email: {user_email}")

        role = self.repo.get_role_by_email(user_email)
        emp = self.repo.get_by_id(emp_id)
        name = emp["preferred_name"] if emp else "Unknown"

        direct_reports = []
        if role in ("MANAGER", "HR"):
            direct_reports = self.repo.get_direct_report_ids(emp_id)

        return {
            "user_email": user_email,
            "employee_id": emp_id,
            "name": name,
            "role": role,
            "direct_reports": direct_reports,
        }


# ============================================================================
# HOLIDAY SERVICE
# ============================================================================


class HolidayService:
    """Service for holiday/time-off operations."""

    def __init__(self):
        self.repo = get_holiday_repo()

    def get_balance(self, employee_id: int, year: int) -> dict:
        """Get holiday balance for an employee."""
        return self.repo.get_balance(employee_id, year)

    def get_requests(self, employee_id: int, year: int) -> list[dict]:
        """Get all holiday requests for an employee."""
        return self.repo.get_requests(employee_id, year)

    def submit_request(
        self,
        employee_id: int,
        start_date: str,
        end_date: str,
        days: float,
        reason: str | None = None,
    ) -> dict:
        """Submit a new holiday request."""
        # Validate dates
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}

        if end < start:
            return {"success": False, "error": "End date must be after start date."}
        if start < date.today():
            return {"success": False, "error": "Cannot request time off in the past."}

        # Check balance
        balance = self.get_balance(employee_id, start.year)
        if balance["remaining"] < days:
            return {
                "success": False,
                "error": f"Insufficient balance. You have {balance['remaining']} days remaining but requested {days} days.",
            }

        # Check for overlapping requests
        if self.repo.has_overlapping_request(employee_id, start_date, end_date):
            return {
                "success": False,
                "error": "You already have a request overlapping these dates.",
            }

        # Create request
        request_id = self.repo.create_request(
            employee_id, start_date, end_date, days, reason
        )

        return {
            "success": True,
            "request_id": request_id,
            "message": f"Holiday request submitted for {days} days ({start_date} to {end_date}). Status: PENDING.",
        }

    def cancel_request(self, employee_id: int, request_id: int) -> dict:
        """Cancel a holiday request."""
        request = self.repo.get_request_by_id(request_id)

        if not request or request["employee_id"] != employee_id:
            return {
                "success": False,
                "error": "Request not found or doesn't belong to you.",
            }

        if request["status"] == "CANCELLED":
            return {"success": False, "error": "This request is already cancelled."}
        if request["status"] == "REJECTED":
            return {"success": False, "error": "Cannot cancel a rejected request."}

        start = datetime.strptime(request["start_date"], "%Y-%m-%d").date()
        if start < date.today():
            return {"success": False, "error": "Cannot cancel past time off."}

        self.repo.update_request_status(request_id, "CANCELLED")

        return {
            "success": True,
            "message": f"Holiday request {request_id} has been cancelled.",
        }

    def get_pending_approvals(self, manager_id: int) -> list[dict]:
        """Get pending requests for a manager's direct reports."""
        return self.repo.get_pending_for_manager(manager_id)

    def approve_request(self, manager_id: int, request_id: int) -> dict:
        """Approve a holiday request."""
        request = self.repo.get_request_for_approval(manager_id, request_id)

        if not request:
            return {
                "success": False,
                "error": "Request not found or you're not the manager.",
            }
        if request["status"] != "PENDING":
            return {
                "success": False,
                "error": f"Request is already {request['status']}.",
            }

        self.repo.update_request_status(request_id, "APPROVED", manager_id)

        return {
            "success": True,
            "message": f"Holiday request for {request['preferred_name']} has been approved.",
        }

    def reject_request(
        self, manager_id: int, request_id: int, reason: str | None = None
    ) -> dict:
        """Reject a holiday request."""
        request = self.repo.get_request_for_approval(manager_id, request_id)

        if not request:
            return {
                "success": False,
                "error": "Request not found or you're not the manager.",
            }
        if request["status"] != "PENDING":
            return {
                "success": False,
                "error": f"Request is already {request['status']}.",
            }

        self.repo.update_request_status(request_id, "REJECTED", manager_id, reason)

        return {
            "success": True,
            "message": f"Holiday request for {request['preferred_name']} has been rejected.",
        }

    def get_team_calendar(
        self, manager_id: int, year: int, month: int | None = None
    ) -> list[dict]:
        """Get approved time off for the team."""
        return self.repo.get_team_calendar(manager_id, year, month)


# ============================================================================
# COMPENSATION SERVICE
# ============================================================================


class CompensationService:
    """Service for compensation operations."""

    def __init__(self):
        self.repo = get_compensation_repo()

    def get_compensation(self, employee_id: int) -> dict | None:
        """Get compensation details for an employee."""
        return self.repo.get_by_employee(employee_id)

    def get_salary_history(self, employee_id: int) -> list[dict]:
        """Get salary history for an employee."""
        return self.repo.get_salary_history(employee_id)

    def get_team_summary(self, manager_id: int) -> dict:
        """Get compensation summary for a manager's team."""
        return self.repo.get_team_summary(manager_id)


# ============================================================================
# COMPANY SERVICE
# ============================================================================


class CompanyService:
    """Service for company-wide information."""

    def __init__(self):
        self.repo = get_company_repo()

    def get_policies(self) -> list[dict]:
        """Get list of company policies."""
        return self.repo.get_policies()

    def get_policy_details(self, policy_id: int) -> dict | None:
        """Get full details of a company policy."""
        return self.repo.get_policy_by_id(policy_id)

    def get_holidays(self, year: int) -> list[dict]:
        """Get company holidays for a year."""
        return self.repo.get_holidays(year)

    def get_announcements(self, limit: int = 10) -> list[dict]:
        """Get recent announcements."""
        return self.repo.get_announcements(limit)

    def get_upcoming_events(self, days_ahead: int = 30) -> list[dict]:
        """Get upcoming company events."""
        return self.repo.get_upcoming_events(days_ahead)


# ============================================================================
# SERVICE SINGLETONS
# ============================================================================

_employee_service: EmployeeService | None = None
_holiday_service: HolidayService | None = None
_compensation_service: CompensationService | None = None
_company_service: CompanyService | None = None


def get_employee_service() -> EmployeeService:
    global _employee_service
    if _employee_service is None:
        _employee_service = EmployeeService()
    return _employee_service


def get_holiday_service() -> HolidayService:
    global _holiday_service
    if _holiday_service is None:
        _holiday_service = HolidayService()
    return _holiday_service


def get_compensation_service() -> CompensationService:
    global _compensation_service
    if _compensation_service is None:
        _compensation_service = CompensationService()
    return _compensation_service


def get_company_service() -> CompanyService:
    global _company_service
    if _company_service is None:
        _company_service = CompanyService()
    return _company_service
