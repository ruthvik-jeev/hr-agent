"""
Tool Registry - Declarative Tool Definitions

This module provides a centralized, declarative way to define tools,
eliminating the need for separate tool function wrappers and manual
parameter mapping.

Features:
- Declarative tool definitions with metadata
- Automatic parameter mapping from Action schema
- Category-based organization
- Introspection for LLM prompts
"""

from dataclasses import dataclass, field
from typing import Callable, Any
from enum import Enum


class ToolCategory(str, Enum):
    """Tool categories for organization and filtering."""

    EMPLOYEE_INFO = "employee_info"
    ORGANIZATION = "organization"
    TIME_OFF = "time_off"
    COMPENSATION = "compensation"
    COMPANY_INFO = "company_info"
    META = "meta"


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""

    name: str
    param_type: type
    description: str
    required: bool = True
    default: Any = None
    # Maps from Action field name to this parameter
    action_field: str | None = None


@dataclass
class ToolDefinition:
    """
    Complete definition of an HR tool.

    This eliminates the need for:
    1. Separate wrapper functions in tools.py
    2. Manual parameter mapping in agent.py
    3. Multiple tool lists (TOOL_CATEGORIES, AVAILABLE_TOOLS, etc.)
    """

    name: str
    description: str
    category: ToolCategory
    handler: Callable[..., Any]
    parameters: list[ToolParameter] = field(default_factory=list)
    requires_auth: bool = True
    sensitive: bool = False  # If True, masks data in logs

    def get_param_mapping(self) -> dict[str, str]:
        """Get mapping from Action fields to handler parameters."""
        return {
            param.action_field or param.name: param.name for param in self.parameters
        }


class ToolRegistry:
    """
    Central registry for all HR tools.

    Usage:
        registry = ToolRegistry()
        registry.register(tool_def)

        # Get tool by name
        tool = registry.get("search_employee")

        # Execute with automatic parameter mapping
        result = registry.execute("search_employee", action, context)
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._by_category: dict[ToolCategory, list[str]] = {
            cat: [] for cat in ToolCategory
        }

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        self._tools[tool.name] = tool
        if tool.name not in self._by_category[tool.category]:
            self._by_category[tool.category].append(tool.name)

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool definition by name."""
        return self._tools.get(name)

    def get_all(self) -> list[ToolDefinition]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_by_category(self, category: ToolCategory) -> list[ToolDefinition]:
        """Get all tools in a category."""
        return [self._tools[name] for name in self._by_category[category]]

    def get_tool_names(self) -> list[str]:
        """Get all tool names."""
        return list(self._tools.keys())

    def get_categories(self) -> dict[str, list[str]]:
        """Get tools organized by category."""
        return {cat.value: names for cat, names in self._by_category.items()}

    def execute(
        self,
        tool_name: str,
        action_params: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:
        """
        Execute a tool with automatic parameter mapping.

        Args:
            tool_name: Name of the tool to execute
            action_params: Parameters from the Action model (may include extra fields)
            context: Execution context (requester_id, etc.)

        Returns:
            Tool execution result
        """
        tool = self.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")

        # Build handler kwargs from action params and context
        kwargs = {}
        for param in tool.parameters:
            # Check action_field first, then param name
            source_field = param.action_field or param.name

            # Special handling for common patterns
            if source_field == "_requester_id":
                kwargs[param.name] = context.get("requester_id")
            elif source_field == "_current_year":
                from datetime import datetime

                kwargs[param.name] = action_params.get("year") or datetime.now().year
            elif source_field in action_params:
                value = action_params[source_field]
                if value is not None or not param.required:
                    kwargs[param.name] = value if value is not None else param.default
            elif param.required and param.default is None:
                # Check if there's a fallback to requester context
                if (
                    param.name == "employee_id"
                    and "target_employee_id" not in action_params
                ):
                    kwargs[param.name] = context.get("requester_id")
                else:
                    raise ValueError(f"Missing required parameter: {param.name}")
            else:
                kwargs[param.name] = param.default

        return tool.handler(**kwargs)

    def generate_prompt_section(self) -> str:
        """Generate the tools section for the LLM system prompt."""
        sections = []

        category_icons = {
            ToolCategory.EMPLOYEE_INFO: "📋",
            ToolCategory.ORGANIZATION: "🏢",
            ToolCategory.TIME_OFF: "🏖️",
            ToolCategory.COMPENSATION: "💰",
            ToolCategory.COMPANY_INFO: "📢",
            ToolCategory.META: "🔄",
        }

        for category in ToolCategory:
            tools = self.get_by_category(category)
            if not tools:
                continue

            icon = category_icons.get(category, "📌")
            title = category.value.upper().replace("_", " ")
            sections.append(f"{icon} {title}:")

            for tool in tools:
                params_str = ", ".join(
                    f"{p.action_field or p.name}" + ("?" if not p.required else "")
                    for p in tool.parameters
                )
                sections.append(f"- {tool.name}: {tool.description}")
                if params_str:
                    sections.append(f"  Parameters: {params_str}")

        return "\n".join(sections)


def create_default_registry() -> ToolRegistry:
    """Create and populate the default tool registry."""
    from .base import (
        get_employee_service,
        get_holiday_service,
        get_compensation_service,
        get_company_service,
    )

    registry = ToolRegistry()

    # ========== EMPLOYEE INFO TOOLS ==========

    registry.register(
        ToolDefinition(
            name="search_employee",
            description="Find employees by name/email/title",
            category=ToolCategory.EMPLOYEE_INFO,
            handler=lambda query, limit=10: get_employee_service().search(query, limit),
            parameters=[
                ToolParameter(
                    "query", str, "Search query", action_field="employee_query"
                ),
                ToolParameter("limit", int, "Max results", required=False, default=10),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_employee_basic",
            description="Get employee details",
            category=ToolCategory.EMPLOYEE_INFO,
            handler=lambda employee_id: get_employee_service().get_basic_info(
                employee_id
            ),
            parameters=[
                ToolParameter(
                    "employee_id",
                    int,
                    "Target employee ID",
                    action_field="target_employee_id",
                ),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_employee_tenure",
            description="Get hire date/tenure",
            category=ToolCategory.EMPLOYEE_INFO,
            handler=lambda employee_id: get_employee_service().get_tenure(employee_id),
            parameters=[
                ToolParameter(
                    "employee_id",
                    int,
                    "Target employee ID",
                    action_field="target_employee_id",
                ),
            ],
        )
    )

    # ========== ORGANIZATION TOOLS ==========

    registry.register(
        ToolDefinition(
            name="get_manager",
            description="Get someone's manager",
            category=ToolCategory.ORGANIZATION,
            handler=lambda employee_id: get_employee_service().get_manager(employee_id),
            parameters=[
                ToolParameter(
                    "employee_id",
                    int,
                    "Target employee ID",
                    action_field="target_employee_id",
                ),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_direct_reports",
            description="List direct reports",
            category=ToolCategory.ORGANIZATION,
            handler=lambda manager_employee_id: get_employee_service().get_direct_reports(
                manager_employee_id
            ),
            parameters=[
                ToolParameter(
                    "manager_employee_id",
                    int,
                    "Manager ID",
                    action_field="target_employee_id",
                ),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_manager_chain",
            description="Full chain to CEO",
            category=ToolCategory.ORGANIZATION,
            handler=lambda employee_id: get_employee_service().get_manager_chain(
                employee_id
            ),
            parameters=[
                ToolParameter(
                    "employee_id",
                    int,
                    "Target employee ID",
                    action_field="target_employee_id",
                ),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_team_overview",
            description="Team summary",
            category=ToolCategory.ORGANIZATION,
            handler=lambda manager_id: get_employee_service().get_team_overview(
                manager_id
            ),
            parameters=[
                ToolParameter(
                    "manager_id", int, "Manager ID", action_field="target_employee_id"
                ),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_department_directory",
            description="List dept employees",
            category=ToolCategory.ORGANIZATION,
            handler=lambda department: get_employee_service().get_department_directory(
                department
            ),
            parameters=[
                ToolParameter("department", str, "Department name"),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_org_chart",
            description="Org structure",
            category=ToolCategory.ORGANIZATION,
            handler=lambda root_employee_id=None: get_employee_service().get_org_chart(
                root_employee_id
            ),
            parameters=[
                ToolParameter(
                    "root_employee_id",
                    int,
                    "Root employee ID",
                    required=False,
                    action_field="target_employee_id",
                ),
            ],
        )
    )

    # ========== TIME OFF TOOLS ==========

    registry.register(
        ToolDefinition(
            name="get_holiday_balance",
            description="PTO balance",
            category=ToolCategory.TIME_OFF,
            handler=lambda employee_id, year: get_holiday_service().get_balance(
                employee_id, year
            ),
            parameters=[
                ToolParameter(
                    "employee_id",
                    int,
                    "Target employee ID",
                    action_field="target_employee_id",
                ),
                ToolParameter("year", int, "Year", action_field="_current_year"),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_holiday_requests",
            description="List requests",
            category=ToolCategory.TIME_OFF,
            handler=lambda employee_id, year: get_holiday_service().get_requests(
                employee_id, year
            ),
            parameters=[
                ToolParameter(
                    "employee_id",
                    int,
                    "Target employee ID",
                    action_field="target_employee_id",
                ),
                ToolParameter("year", int, "Year", action_field="_current_year"),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="submit_holiday_request",
            description="Request time off",
            category=ToolCategory.TIME_OFF,
            handler=lambda employee_id, start_date, end_date, days, reason=None: get_holiday_service().submit_request(
                employee_id, start_date, end_date, days, reason
            ),
            parameters=[
                ToolParameter(
                    "employee_id", int, "Employee ID", action_field="_requester_id"
                ),
                ToolParameter("start_date", str, "Start date (YYYY-MM-DD)"),
                ToolParameter("end_date", str, "End date (YYYY-MM-DD)"),
                ToolParameter("days", float, "Number of days"),
                ToolParameter("reason", str, "Reason", required=False),
            ],
            sensitive=True,
        )
    )

    registry.register(
        ToolDefinition(
            name="cancel_holiday_request",
            description="Cancel request",
            category=ToolCategory.TIME_OFF,
            handler=lambda employee_id, request_id: get_holiday_service().cancel_request(
                employee_id, request_id
            ),
            parameters=[
                ToolParameter(
                    "employee_id", int, "Employee ID", action_field="_requester_id"
                ),
                ToolParameter("request_id", int, "Request ID"),
            ],
            sensitive=True,
        )
    )

    registry.register(
        ToolDefinition(
            name="get_pending_approvals",
            description="Requests to approve (managers)",
            category=ToolCategory.TIME_OFF,
            handler=lambda manager_employee_id: get_holiday_service().get_pending_approvals(
                manager_employee_id
            ),
            parameters=[
                ToolParameter(
                    "manager_employee_id",
                    int,
                    "Manager ID",
                    action_field="_requester_id",
                ),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="approve_holiday_request",
            description="Approve request",
            category=ToolCategory.TIME_OFF,
            handler=lambda manager_employee_id, request_id: get_holiday_service().approve_request(
                manager_employee_id, request_id
            ),
            parameters=[
                ToolParameter(
                    "manager_employee_id",
                    int,
                    "Manager ID",
                    action_field="_requester_id",
                ),
                ToolParameter("request_id", int, "Request ID"),
            ],
            sensitive=True,
        )
    )

    registry.register(
        ToolDefinition(
            name="reject_holiday_request",
            description="Reject request",
            category=ToolCategory.TIME_OFF,
            handler=lambda manager_employee_id, request_id, reason=None: get_holiday_service().reject_request(
                manager_employee_id, request_id, reason
            ),
            parameters=[
                ToolParameter(
                    "manager_employee_id",
                    int,
                    "Manager ID",
                    action_field="_requester_id",
                ),
                ToolParameter("request_id", int, "Request ID"),
                ToolParameter("reason", str, "Rejection reason", required=False),
            ],
            sensitive=True,
        )
    )

    registry.register(
        ToolDefinition(
            name="get_team_calendar",
            description="Team time off",
            category=ToolCategory.TIME_OFF,
            handler=lambda manager_employee_id, year, month=None: get_holiday_service().get_team_calendar(
                manager_employee_id, year, month
            ),
            parameters=[
                ToolParameter(
                    "manager_employee_id",
                    int,
                    "Manager ID",
                    action_field="_requester_id",
                ),
                ToolParameter("year", int, "Year", action_field="_current_year"),
                ToolParameter("month", int, "Month", required=False),
            ],
        )
    )

    # ========== COMPENSATION TOOLS ==========

    registry.register(
        ToolDefinition(
            name="get_compensation",
            description="Salary details",
            category=ToolCategory.COMPENSATION,
            handler=lambda employee_id: get_compensation_service().get_compensation(
                employee_id
            ),
            parameters=[
                ToolParameter(
                    "employee_id",
                    int,
                    "Target employee ID",
                    action_field="target_employee_id",
                ),
            ],
            sensitive=True,
        )
    )

    registry.register(
        ToolDefinition(
            name="get_salary_history",
            description="Salary changes",
            category=ToolCategory.COMPENSATION,
            handler=lambda employee_id: get_compensation_service().get_salary_history(
                employee_id
            ),
            parameters=[
                ToolParameter(
                    "employee_id",
                    int,
                    "Target employee ID",
                    action_field="target_employee_id",
                ),
            ],
            sensitive=True,
        )
    )

    registry.register(
        ToolDefinition(
            name="get_team_compensation_summary",
            description="Team salaries (HR only)",
            category=ToolCategory.COMPENSATION,
            handler=lambda manager_employee_id: get_compensation_service().get_team_summary(
                manager_employee_id
            ),
            parameters=[
                ToolParameter(
                    "manager_employee_id",
                    int,
                    "Manager ID",
                    action_field="target_employee_id",
                ),
            ],
            sensitive=True,
        )
    )

    # ========== COMPANY INFO TOOLS ==========

    registry.register(
        ToolDefinition(
            name="get_company_policies",
            description="List all policies",
            category=ToolCategory.COMPANY_INFO,
            handler=lambda: get_company_service().get_policies(),
            parameters=[],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_policy_details",
            description="Full policy",
            category=ToolCategory.COMPANY_INFO,
            handler=lambda policy_id: get_company_service().get_policy_details(
                policy_id
            ),
            parameters=[
                ToolParameter("policy_id", int, "Policy ID"),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_company_holidays",
            description="Holiday calendar",
            category=ToolCategory.COMPANY_INFO,
            handler=lambda year: get_company_service().get_holidays(year),
            parameters=[
                ToolParameter("year", int, "Year", action_field="_current_year"),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_announcements",
            description="Recent news",
            category=ToolCategory.COMPANY_INFO,
            handler=lambda limit=10: get_company_service().get_announcements(limit),
            parameters=[
                ToolParameter("limit", int, "Max results", required=False, default=10),
            ],
        )
    )

    registry.register(
        ToolDefinition(
            name="get_upcoming_events",
            description="Upcoming events",
            category=ToolCategory.COMPANY_INFO,
            handler=lambda: get_company_service().get_upcoming_events(),
            parameters=[],
        )
    )

    return registry


# Singleton instance
_tool_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get the singleton tool registry."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = create_default_registry()
    return _tool_registry
