"""
HR Agent v2.0 - Redesigned Architecture

Key Improvements:
1. Human-in-the-loop confirmation for sensitive actions
2. Policy-as-code authorization engine
3. Response summarization to manage context window
4. Conversation memory for multi-turn context
5. Better error handling with graceful retries
6. API-ready design pattern
"""

import json
import uuid
from datetime import datetime
from typing import Callable, Any

from .llm import chat
from .policy_engine import (
    get_policy_engine,
    PolicyContext,
    requires_confirmation,
    get_confirmation_message,
)
from .memory import get_memory_store, ConversationSession
from .response_utils import prepare_tool_response
from ..domain.models import AgentAction as Action
from ..services import get_employee_service
from ..services import tools


# ============================================================================
# TOOL CATEGORIES
# ============================================================================


# Available tools with categories
TOOL_CATEGORIES = {
    "employee_info": [
        "search_employee",
        "get_employee_basic",
        "get_employee_tenure",
    ],
    "organization": [
        "get_manager",
        "get_direct_reports",
        "get_manager_chain",
        "get_team_overview",
        "get_department_directory",
        "get_org_chart",
    ],
    "time_off": [
        "get_holiday_balance",
        "get_holiday_requests",
        "submit_holiday_request",
        "cancel_holiday_request",
        "get_pending_approvals",
        "approve_holiday_request",
        "reject_holiday_request",
        "get_team_calendar",
    ],
    "compensation": [
        "get_compensation",
        "get_salary_history",
        "get_team_compensation_summary",
    ],
    "company_info": [
        "get_company_policies",
        "get_policy_details",
        "get_company_holidays",
        "get_announcements",
        "get_upcoming_events",
    ],
    "meta": [
        "final_answer",
        "confirm_action",
        "cancel_action",
    ],
}

AVAILABLE_TOOLS = [
    tool for tools_list in TOOL_CATEGORIES.values() for tool in tools_list
]

# Queries that require tool calls - patterns that indicate factual HR data requests
FACTUAL_QUERY_PATTERNS = [
    # Employee info
    "job title",
    "my title",
    "position",
    "role",
    "hire date",
    "joined",
    "start date",
    "tenure",
    "how long",
    "years",
    "employee",
    "who is",
    "find",
    "employee id",
    "my id",
    # Organization
    "manager",
    "report to",
    "reports to",
    "boss",
    "supervisor",
    "direct report",
    "team member",
    "who works for",
    "who works in",
    "department",
    "org chart",
    "chain of command",
    "overview",
    "my team",
    # Time off
    "vacation",
    "pto",
    "time off",
    "holiday",
    "leave",
    "balance",
    "days left",
    "remaining",
    "request",
    "approve",
    "pending",
    "calendar",
    "schedule",
    # Compensation
    "salary",
    "compensation",
    "pay",
    "bonus",
    "raise",
    # Company info
    "policy",
    "policies",
    "announcement",
    "event",
    "phone number",
    "contact",
    # Performance
    "performance",
    "rating",
    "review",
]


def _requires_tool_call(query: str) -> bool:
    """Check if a query requires a tool call to answer (factual HR data)."""
    query_lower = query.lower()
    return any(pattern in query_lower for pattern in FACTUAL_QUERY_PATTERNS)


def _get_suggested_tool(query: str) -> str | None:
    """Suggest which tool should be called based on the query."""
    query_lower = query.lower()

    # Contact/phone/CEO info - use search first (check early)
    if any(
        p in query_lower
        for p in ["phone number", "contact info", "phone", "ceo's", "ceo contact"]
    ):
        return "search_employee"

    # Salary/raise patterns - check early
    if any(
        p in query_lower
        for p in ["next raise", "raise", "salary history", "salary changes"]
    ):
        return "get_salary_history"

    # Team compensation (often restricted)
    if any(
        p in query_lower
        for p in [
            "salary of everyone",
            "team salary",
            "department salary",
            "team compensation",
        ]
    ):
        return "get_team_compensation_summary"

    # Employee info patterns
    if any(
        p in query_lower
        for p in [
            "job title",
            "my title",
            "position",
            "role",
            "email",
            "department",
            "employee id",
            "my id",
            "id number",
        ]
    ):
        return "get_employee_basic"
    if any(
        p in query_lower
        for p in [
            "hire date",
            "joined",
            "start date",
            "tenure",
            "how long",
            "years worked",
            "years have i",
            "been employed",
        ]
    ):
        return "get_employee_tenure"

    # Search patterns - must check before other patterns
    if any(p in query_lower for p in ["find", "search"]) or (
        "who is" in query_lower and "manager" not in query_lower
    ):
        return "search_employee"

    # Compensation - check early to catch "salary" queries about others
    if any(
        p in query_lower
        for p in ["salary", "compensation", "pay", "how much do i make"]
    ):
        return "get_compensation"

    # Organization patterns
    if any(
        p in query_lower
        for p in [
            "reports to me",
            "report to me",
            "who reports",
            "direct report",
            "my team",
        ]
    ):
        return "get_direct_reports"
    if any(
        p in query_lower
        for p in [
            "team overview",
            "overview of my team",
            "my team overview",
            "overview of the team",
        ]
    ):
        return "get_team_overview"
    if (
        any(p in query_lower for p in ["manager", "report to", "boss", "supervisor"])
        and "direct" not in query_lower
        and "reports to me" not in query_lower
    ):
        return "get_manager"
    if any(
        p in query_lower for p in ["chain of command", "reporting line", "hierarchy"]
    ):
        return "get_manager_chain"
    if any(p in query_lower for p in ["department", "who works in"]):
        return "get_department_directory"

    # Time off patterns
    if any(
        p in query_lower
        for p in [
            "balance",
            "days left",
            "remaining",
            "how many vacation",
            "how many pto",
            "pto balance",
            "vacation days",
            "days do i have",
        ]
    ):
        return "get_holiday_balance"
    if any(
        p in query_lower
        for p in [
            "my request",
            "my holiday",
            "my vacation request",
            "time off request",
            "holiday request",
            "show my",
        ]
    ):
        return "get_holiday_requests"
    if any(
        p in query_lower
        for p in ["pending approval", "to approve", "approve request", "leave request"]
    ):
        return "get_pending_approvals"
    if any(
        p in query_lower
        for p in [
            "team calendar",
            "team off",
            "who is off",
            "team vacation",
            "team taking time off",
        ]
    ):
        return "get_team_calendar"

    # Company info patterns
    if any(
        p in query_lower
        for p in ["policies", "policy list", "company policies", "all policies"]
    ):
        return "get_company_policies"
    if any(
        p in query_lower
        for p in [
            "company holiday",
            "office closed",
            "holiday calendar",
            "holidays this year",
        ]
    ):
        return "get_company_holidays"
    if "announcement" in query_lower:
        return "get_announcements"

    # Performance - use employee basic as fallback
    if any(p in query_lower for p in ["performance", "rating", "review"]):
        return "get_employee_basic"

    return None


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

SYSTEM_PROMPT = """You are an intelligent HR assistant for ACME Corporation. You help employees with HR-related questions and tasks.

Current Date: {current_date}

**CRITICAL: You have NO knowledge of employee data, organizational structure, PTO balances, or any HR information. You MUST use tools to retrieve ALL factual information. NEVER make up or guess any data.**

**Response Format:**
You MUST respond with valid JSON matching this schema:
{{
  "action": "<tool_name>",
  "employee_query": "string|null",
  "target_employee_id": "int|null",
  "year": "int|null",
  "month": "int|null",
  "start_date": "YYYY-MM-DD|null",
  "end_date": "YYYY-MM-DD|null",
  "days": "float|null",
  "reason": "string|null",
  "request_id": "int|null",
  "policy_id": "int|null",
  "department": "string|null",
  "limit": "int|null",
  "page": "int|null",
  "confirm": "bool|null",
  "answer": "string|null"
}}

**Available Tools:**

📋 EMPLOYEE INFO:
- search_employee: Find employees by name/email/title → use employee_query
- get_employee_basic: Get employee details → use target_employee_id
- get_employee_tenure: Get hire date/tenure → use target_employee_id

🏢 ORGANIZATION:
- get_manager: Get someone's manager → use target_employee_id
- get_direct_reports: List direct reports → use target_employee_id
- get_manager_chain: Full chain to CEO → use target_employee_id
- get_team_overview: Team summary → use target_employee_id (manager)
- get_department_directory: List dept employees → use department
- get_org_chart: Org structure → optional target_employee_id

🏖️ TIME OFF:
- get_holiday_balance: PTO balance → use target_employee_id, year
- get_holiday_requests: List requests → use target_employee_id, year
- submit_holiday_request: Request time off → start_date, end_date, days, reason
- cancel_holiday_request: Cancel request → request_id
- get_pending_approvals: Requests to approve (managers) → no params
- approve_holiday_request: Approve request → request_id
- reject_holiday_request: Reject request → request_id, reason
- get_team_calendar: Team time off → year, month (optional)

💰 COMPENSATION (Restricted):
- get_compensation: Salary details → target_employee_id
- get_salary_history: Salary changes → target_employee_id
- get_team_compensation_summary: Team salaries (HR only) → target_employee_id

📢 COMPANY INFO:
- get_company_policies: List all policies
- get_policy_details: Full policy → policy_id
- get_company_holidays: Holiday calendar → year
- get_announcements: Recent news → limit (optional)
- get_upcoming_events: Upcoming events

🔄 ACTIONS:
- final_answer: Give response → use answer field (ONLY after retrieving data from tools)
- confirm_action: Confirm a pending action → confirm=true
- cancel_action: Cancel a pending action → confirm=false

**Guidelines:**
1. When user says "my" or "I", use their employee_id from context
2. To find someone by name, use search_employee first
3. Year defaults to current year if not specified
4. For sensitive actions (submitting/canceling requests, approvals), the system will ask for confirmation
5. Always provide helpful, concise responses
6. If access denied, explain what the user CAN do instead
7. Use page parameter for large result sets

**MANDATORY TOOL USAGE - You MUST call the appropriate tool FIRST for these queries:**
- Job title, employee info → get_employee_basic
- Hire date, tenure, how long worked → get_employee_tenure  
- Manager info → get_manager
- Direct reports, team members → get_direct_reports
- Department employees → get_department_directory
- PTO/vacation balance → get_holiday_balance
- Holiday/vacation requests → get_holiday_requests
- Pending approvals → get_pending_approvals
- Team calendar/time off → get_team_calendar
- Salary/compensation → get_compensation
- Company policies → get_company_policies
- Company holidays → get_company_holidays

**NEVER use final_answer for factual HR queries without first calling the appropriate tool. If you don't have tool results in the conversation, you MUST call a tool first.**

**Important:** Always respond with valid JSON only. No markdown, no explanation outside the JSON."""


# ============================================================================
# REQUESTER CONTEXT
# ============================================================================


def get_requester_context(user_email: str) -> dict:
    """Get the requester's context including role and permissions."""
    return get_employee_service().get_requester_context(user_email)


# ============================================================================
# TOOL EXECUTOR
# ============================================================================


class ToolExecutor:
    """Executes tools and returns results."""

    def __init__(self, session: ConversationSession):
        self.session = session
        self.tool_handlers = self._map_tool_handlers()

    def execute(self, action: Action) -> Any:
        """Execute a tool and return the result."""
        if not action.action or action.action not in self.tool_handlers:
            return {"error": f"Unknown action: {action.action}"}

        handler = self.tool_handlers[action.action]
        action_params = action.model_dump(exclude_none=True)

        requester_context = get_requester_context(self.session.user_email)

        policy_engine = get_policy_engine()
        policy_ctx = PolicyContext(
            requester_id=int(requester_context.get("employee_id", 0)),
            requester_email=str(requester_context.get("user_email", "")),
            requester_role=str(requester_context.get("role", "employee")),
            action=action.action,
            target_id=action_params.get("target_employee_id"),
            extra={"session": self.session},
        )

        if not policy_engine.is_allowed(policy_ctx):
            return {
                "error": "Access Denied",
                "message": f"You don't have permission to perform '{action.action}'.",
            }

        if requires_confirmation(action.action):
            if not action_params.get("confirm"):
                confirmation_message = get_confirmation_message(
                    action.action, action_params
                )
                self.session.set_pending_confirmation(
                    action.action, action_params, confirmation_message
                )
                return {
                    "confirmation_required": True,
                    "message": confirmation_message,
                }
            else:
                self.session.clear_pending_confirmation()

        try:
            # Map action parameters to tool function parameters
            tool_params = self._get_tool_params(action, requester_context)
            result = handler(**tool_params)
            return result
        except (ValueError, TypeError, KeyError) as e:
            return {"error": f"Error executing tool {action.action}: {e}"}

    def _get_tool_params(self, action: Action, requester_context: dict) -> dict:
        """Map action parameters to the appropriate tool function parameters."""
        # Get the requester's employee_id for self-referencing queries
        requester_id = requester_context.get("employee_id")

        # Base parameters from action
        params = {}

        # Handle different tools with their expected parameters
        if action.action == "search_employee":
            params["query"] = action.employee_query or ""
            if action.limit:
                params["limit"] = action.limit
        elif action.action in [
            "get_employee_basic",
            "get_employee_tenure",
            "get_manager",
            "get_direct_reports",
            "get_manager_chain",
            "get_team_overview",
            "get_compensation",
            "get_salary_history",
        ]:
            # Use target_employee_id if provided, otherwise use requester's own ID
            params["employee_id"] = action.target_employee_id or requester_id
        elif action.action == "get_department_directory":
            params["department"] = action.department or ""
        elif action.action == "get_org_chart":
            params["root_employee_id"] = action.target_employee_id
        elif action.action == "get_holiday_balance":
            params["employee_id"] = action.target_employee_id or requester_id
            params["year"] = action.year or datetime.now().year
        elif action.action == "get_holiday_requests":
            params["employee_id"] = action.target_employee_id or requester_id
            params["year"] = action.year or datetime.now().year
        elif action.action == "submit_holiday_request":
            params["employee_id"] = requester_id
            params["start_date"] = action.start_date
            params["end_date"] = action.end_date
            params["days"] = action.days
            params["reason"] = action.reason
        elif action.action == "cancel_holiday_request":
            params["employee_id"] = requester_id
            params["request_id"] = action.request_id
        elif action.action == "get_pending_approvals":
            params["manager_employee_id"] = requester_id
        elif action.action == "approve_holiday_request":
            params["manager_employee_id"] = requester_id
            params["request_id"] = action.request_id
        elif action.action == "reject_holiday_request":
            params["manager_employee_id"] = requester_id
            params["request_id"] = action.request_id
            params["reason"] = action.reason
        elif action.action == "get_team_calendar":
            params["manager_employee_id"] = requester_id
            params["year"] = action.year or datetime.now().year
            if action.month:
                params["month"] = action.month
        elif action.action == "get_team_compensation_summary":
            params["manager_employee_id"] = action.target_employee_id or requester_id
        elif action.action == "get_company_policies":
            pass  # No parameters needed
        elif action.action == "get_policy_details":
            params["policy_id"] = action.policy_id
        elif action.action == "get_company_holidays":
            params["year"] = action.year or datetime.now().year
        elif action.action == "get_announcements":
            if action.limit:
                params["limit"] = action.limit
        elif action.action == "get_upcoming_events":
            pass  # Uses default days_ahead

        return params

    def _map_tool_handlers(self) -> dict[str, Callable]:
        """Map tool names to their handler functions."""
        return {
            "search_employee": tools.search_employee,
            "get_employee_basic": tools.get_employee_basic,
            "get_employee_tenure": tools.get_employee_tenure,
            "get_manager": tools.get_manager,
            "get_direct_reports": tools.get_direct_reports,
            "get_manager_chain": tools.get_manager_chain,
            "get_team_overview": tools.get_team_overview,
            "get_department_directory": tools.get_department_directory,
            "get_org_chart": tools.get_org_chart,
            "get_holiday_balance": tools.get_holiday_balance,
            "get_holiday_requests": tools.get_holiday_requests,
            "submit_holiday_request": tools.submit_holiday_request,
            "cancel_holiday_request": tools.cancel_holiday_request,
            "get_pending_approvals": tools.get_pending_approvals,
            "approve_holiday_request": tools.approve_holiday_request,
            "reject_holiday_request": tools.reject_holiday_request,
            "get_team_calendar": tools.get_team_calendar,
            "get_compensation": tools.get_compensation,
            "get_salary_history": tools.get_salary_history,
            "get_team_compensation_summary": tools.get_team_compensation_summary,
            "get_company_policies": tools.get_company_policies,
            "get_policy_details": tools.get_policy_details,
            "get_company_holidays": tools.get_company_holidays,
            "get_announcements": tools.get_announcements,
            "get_upcoming_events": tools.get_upcoming_events,
        }


# ============================================================================
# HR AGENT
# ============================================================================


class HRAgent:
    """The main HR agent class."""

    def __init__(self, user_email: str, session_id: str | None = None):
        self.user_email = user_email
        self.session_id = session_id or str(uuid.uuid4())
        self.memory_store = get_memory_store()
        self.session = self.memory_store.get_or_create_session(
            self.session_id, self.user_email
        )
        self.requester_context = get_requester_context(user_email)
        self.tool_executor = ToolExecutor(self.session)

    def chat(self, query: str) -> str:
        """Main entry point for a user query."""
        self.session.add_turn("user", query)

        if self.session.has_pending_confirmation():
            if query.lower().strip() in ["yes", "y", "confirm"]:
                if self.session.pending_confirmation:
                    pending_action = self.session.pending_confirmation["action"]
                    pending_params = self.session.pending_confirmation["params"]
                    pending_params["confirm"] = True
                    action = Action(action=pending_action, **pending_params)
                    result = self.tool_executor.execute(action)
                    response_data = prepare_tool_response(action.action, result)
                    response = (
                        json.dumps(response_data)
                        if isinstance(response_data, dict)
                        else str(response_data)
                    )
                    self.session.clear_pending_confirmation()
                    self.session.add_turn("assistant", response)
                    return response
            else:
                self.session.clear_pending_confirmation()
                response = "Action canceled."
                self.session.add_turn("assistant", response)
                return response

        return self.chat_multi_turn(query)

    def chat_multi_turn(self, query: str, max_turns: int = 5) -> str:
        current_query = query
        is_first_turn = True
        for _ in range(max_turns):
            response_str, action, _result = self.chat_single_turn(
                current_query, is_first_turn=is_first_turn
            )
            is_first_turn = (
                False  # After first iteration, it's no longer the first turn
            )

            # Track the tool call in session context
            if action.action != "final_answer":
                tools_called = self.session.get_context("tools_called") or []
                tools_called.append(action.action)
                self.session.update_context("tools_called", tools_called)

            if action.action == "final_answer":
                return response_str

            tool_response_summary = f"Tool result for '{action.action}': {response_str}"
            self.session.add_turn("user", tool_response_summary)
            current_query = (
                "Based on the last tool result, what is the next step or final answer?"
            )

        return "I seem to be having trouble resolving your request. Please try rephrasing or contact support."

    def chat_single_turn(
        self, query: str, is_first_turn: bool = True
    ) -> tuple[str, Action, Any]:
        prompt = self._construct_prompt(query)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": query},
        ]
        llm_response = chat(messages)
        self.session.add_turn("assistant", llm_response)

        try:
            action_data = json.loads(llm_response)
            action = Action(**action_data)
        except (json.JSONDecodeError, TypeError):
            action = Action(action="final_answer", answer=llm_response)

        # ANTI-HALLUCINATION: If this is the first turn and the query requires
        # factual data, but LLM tried to use final_answer, force tool usage
        if (
            is_first_turn
            and action.action == "final_answer"
            and _requires_tool_call(query)
        ):
            suggested_tool = _get_suggested_tool(query)
            if suggested_tool:
                # Force the correct tool call instead of allowing hallucinated answer
                action = Action(
                    action=suggested_tool,
                    target_employee_id=self.requester_context.get("employee_id"),
                    year=datetime.now().year,
                )
                # Execute the forced tool call
                result = self.tool_executor.execute(action)
                response_data = prepare_tool_response(action.action, result)
                response_str = json.dumps(response_data)
                return response_str, action, result

        if action.action == "final_answer":
            return (
                action.answer or "I am sorry, I cannot provide an answer.",
                action,
                {"result": action.answer},
            )

        result = self.tool_executor.execute(action)

        if action.action == "search_employee" and result:
            self.session.update_context("last_search", True)
            if isinstance(result, list) and len(result) == 1:
                self.session.update_context("target_employee", result[0])
        elif action.action == "final_answer":
            self.session.update_context("last_search", None)
            self.session.update_context("target_employee", None)

        response_data = prepare_tool_response(action.action, result)
        response_str = json.dumps(response_data)

        return response_str, action, result

    def _construct_prompt(self, _query: str) -> str:
        """Construct the prompt for the LLM. Query param reserved for future use."""
        history = self.session.get_messages_for_llm()

        context_vars = {
            "user_employee_id": self.requester_context.get("employee_id"),
            "user_role": self.requester_context.get("role"),
            "target_employee": self.session.get_context("target_employee"),
            "last_search": self.session.get_context("last_search"),
            "current_date": datetime.now().strftime("%Y-%m-%d"),
        }
        context_str = json.dumps(context_vars, indent=2)

        return f"""{SYSTEM_PROMPT.format(current_date=context_vars['current_date'])}

**Conversation Context:**
{context_str}

**Conversation History:**
{json.dumps(history, indent=2)}
"""

    def _construct_final_prompt(self, original_query: str, tool_response: str) -> str:
        return f"""You are an HR assistant. Based on the user's request and the result from a tool, provide a clear and concise final answer.

**Original Request:** {original_query}
**Tool Result:** {tool_response}

Respond in JSON with action: "final_answer" and the answer in the "answer" field.
"""


# ============================================================================
# HELPER FUNCTION
# ============================================================================


def run_agent(user_email: str, question: str) -> str:
    """Run the HR agent with a single query and return the answer.

    Args:
        user_email: The email of the user making the request.
        question: The question to ask the agent.

    Returns:
        The agent's answer as a string.
    """
    agent = HRAgent(user_email)
    return agent.chat(question)
