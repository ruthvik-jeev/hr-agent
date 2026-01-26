"""
Services Module - Business Logic Layer

Contains all business services and tool implementations.
Services use repositories for data access and provide the main interface for the agent.
"""

from .base import (
    EmployeeService,
    HolidayService,
    CompensationService,
    CompanyService,
    get_employee_service,
    get_holiday_service,
    get_compensation_service,
    get_company_service,
)
from .tools import (
    search_employee,
    get_employee_basic,
    get_employee_tenure,
    get_manager,
    get_direct_reports,
    get_manager_chain,
    get_team_overview,
    get_department_directory,
    get_org_chart,
    get_holiday_balance,
    get_holiday_requests,
    submit_holiday_request,
    cancel_holiday_request,
    get_pending_approvals,
    approve_holiday_request,
    reject_holiday_request,
    get_team_calendar,
    get_compensation,
    get_salary_history,
    get_team_compensation_summary,
    get_company_policies,
    get_policy_details,
    get_company_holidays,
    get_announcements,
    get_upcoming_events,
)
from .tool_registry import (
    ToolRegistry,
    ToolDefinition,
    ToolParameter,
    ToolCategory,
    get_tool_registry,
)

# LangChain tools (import separately to avoid breaking existing code)
from . import langchain_tools

__all__ = [
    # Services
    "EmployeeService",
    "HolidayService",
    "CompensationService",
    "CompanyService",
    "get_employee_service",
    "get_holiday_service",
    "get_compensation_service",
    "get_company_service",
    # Tool Functions (legacy)
    "search_employee",
    "get_employee_basic",
    "get_employee_tenure",
    "get_manager",
    "get_direct_reports",
    "get_manager_chain",
    "get_team_overview",
    "get_department_directory",
    "get_org_chart",
    "get_holiday_balance",
    "get_holiday_requests",
    "submit_holiday_request",
    "cancel_holiday_request",
    "get_pending_approvals",
    "approve_holiday_request",
    "reject_holiday_request",
    "get_team_calendar",
    "get_compensation",
    "get_salary_history",
    "get_team_compensation_summary",
    "get_company_policies",
    "get_policy_details",
    "get_company_holidays",
    "get_announcements",
    "get_upcoming_events",
    # Tool Registry
    "ToolRegistry",
    "ToolDefinition",
    "ToolParameter",
    "ToolCategory",
    "get_tool_registry",
    # LangChain tools module
    "langchain_tools",
]
