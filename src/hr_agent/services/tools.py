"""
HR Tools - Agent Tool Functions

Clean, focused tool implementations for HR operations.
These tools delegate to the service layer for business logic.
Authorization is handled by the policy engine in the agent layer.

Design:
- Tools are thin wrappers around services
- No direct SQL queries - all data access goes through services
- Each tool function can be easily tested with mocked services
"""

from .base import (
    get_employee_service,
    get_holiday_service,
    get_compensation_service,
    get_company_service,
)


# ============================================================================
# EMPLOYEE SEARCH & INFO TOOLS
# ============================================================================


def search_employee(query: str, limit: int = 10) -> list[dict]:
    """Search employees by name, email, or title."""
    return get_employee_service().search(query, limit)


def get_employee_basic(employee_id: int) -> dict | None:
    """Get basic employee information."""
    return get_employee_service().get_basic_info(employee_id)


def get_employee_cost_center(employee_id: int) -> str | None:
    """Get employee's cost center."""
    return get_employee_service().get_cost_center(employee_id)


def get_employee_tenure(employee_id: int) -> dict | None:
    """Get employee tenure information (hire date, years of service)."""
    return get_employee_service().get_tenure(employee_id)


# ============================================================================
# ORGANIZATION STRUCTURE TOOLS
# ============================================================================


def get_manager(employee_id: int) -> dict | None:
    """Get the direct manager of an employee."""
    return get_employee_service().get_manager(employee_id)


def get_direct_reports(manager_employee_id: int) -> list[dict]:
    """Get all direct reports for a manager."""
    return get_employee_service().get_direct_reports(manager_employee_id)


def get_manager_chain(employee_id: int, max_depth: int = 6) -> list[dict]:
    """Get the full management chain up to CEO."""
    return get_employee_service().get_manager_chain(employee_id, max_depth)


def get_team_overview(manager_employee_id: int) -> dict:
    """Get a summary of a manager's team including headcount and departments."""
    return get_employee_service().get_team_overview(manager_employee_id)


def get_department_directory(department: str) -> list[dict]:
    """Get all employees in a department."""
    return get_employee_service().get_department_directory(department)


def get_org_chart(root_employee_id: int | None = None, max_depth: int = 3) -> dict:
    """Get organizational chart starting from an employee (or CEO if not specified)."""
    return get_employee_service().get_org_chart(root_employee_id, max_depth)


# ============================================================================
# HOLIDAY / TIME-OFF TOOLS
# ============================================================================


def get_holiday_balance(employee_id: int, year: int) -> dict:
    """Get holiday/PTO balance for an employee for a specific year."""
    return get_holiday_service().get_balance(employee_id, year)


def get_holiday_requests(employee_id: int, year: int) -> list[dict]:
    """Get all holiday requests for an employee for a specific year."""
    return get_holiday_service().get_requests(employee_id, year)


def submit_holiday_request(
    employee_id: int,
    start_date: str,
    end_date: str,
    days: float,
    reason: str | None = None,
) -> dict:
    """Submit a new holiday/PTO request."""
    return get_holiday_service().submit_request(
        employee_id, start_date, end_date, days, reason
    )


def cancel_holiday_request(employee_id: int, request_id: int) -> dict:
    """Cancel a pending or approved holiday request."""
    return get_holiday_service().cancel_request(employee_id, request_id)


def get_pending_approvals(manager_employee_id: int) -> list[dict]:
    """Get all pending holiday requests for a manager's direct reports."""
    return get_holiday_service().get_pending_approvals(manager_employee_id)


def approve_holiday_request(manager_employee_id: int, request_id: int) -> dict:
    """Approve a holiday request (manager only)."""
    return get_holiday_service().approve_request(manager_employee_id, request_id)


def reject_holiday_request(
    manager_employee_id: int, request_id: int, reason: str | None = None
) -> dict:
    """Reject a holiday request (manager only)."""
    return get_holiday_service().reject_request(manager_employee_id, request_id, reason)


def get_team_calendar(
    manager_employee_id: int, year: int, month: int | None = None
) -> list[dict]:
    """Get approved time off for the team (manager view)."""
    return get_holiday_service().get_team_calendar(manager_employee_id, year, month)


# ============================================================================
# COMPENSATION TOOLS
# ============================================================================


def get_compensation(employee_id: int) -> dict | None:
    """Get compensation details for an employee."""
    return get_compensation_service().get_compensation(employee_id)


def get_salary_history(employee_id: int) -> list[dict]:
    """Get salary history for an employee."""
    return get_compensation_service().get_salary_history(employee_id)


def get_team_compensation_summary(manager_employee_id: int) -> dict:
    """Get compensation summary for a manager's team (HR/Finance only)."""
    return get_compensation_service().get_team_summary(manager_employee_id)


# ============================================================================
# COMPANY POLICIES & INFO
# ============================================================================


def get_company_policies() -> list[dict]:
    """Get list of company policies."""
    return get_company_service().get_policies()


def get_policy_details(policy_id: int) -> dict | None:
    """Get full details of a company policy."""
    return get_company_service().get_policy_details(policy_id)


def get_company_holidays(year: int) -> list[dict]:
    """Get company-observed holidays for a year."""
    return get_company_service().get_holidays(year)


# ============================================================================
# ANNOUNCEMENTS & EVENTS
# ============================================================================


def get_announcements(limit: int = 10) -> list[dict]:
    """Get recent company announcements."""
    return get_company_service().get_announcements(limit)


def get_upcoming_events(days_ahead: int = 30) -> list[dict]:
    """Get upcoming company events."""
    return get_company_service().get_upcoming_events(days_ahead)
