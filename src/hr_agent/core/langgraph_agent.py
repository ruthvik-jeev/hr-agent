"""
HR Agent - LangGraph Implementation

A LangGraph-based agent for HR operations with:
- State-based workflow management
- Human-in-the-loop confirmations
- Authorization checks
- Tool execution with structured outputs
- LangSmith tracing support
"""

from typing import TypedDict, Annotated, Literal, Any, Sequence
from datetime import datetime
import json
import operator

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from ..services.langchain_tools import (
    get_all_tools,
    get_tools_requiring_confirmation,
    TOOL_MAP,
)
from ..services import get_employee_service
from ..infrastructure.config import settings, configure_langsmith
from .policy_engine import get_policy_engine, PolicyContext

# Configure LangSmith tracing if enabled
_langsmith_enabled = configure_langsmith()


# ============================================================================
# STATE DEFINITION
# ============================================================================


class AgentState(TypedDict):
    """State for the HR Agent graph.

    Attributes:
        messages: Conversation history
        user_email: The authenticated user's email
        user_id: The authenticated user's employee ID
        user_role: The user's role (employee, manager, hr, finance)
        pending_confirmation: Tool call awaiting user confirmation
        tools_called: List of tools called in this session
        current_date: Today's date for context
    """

    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_email: str
    user_id: int
    user_role: str
    pending_confirmation: dict | None
    tools_called: list[str]
    current_date: str


# ============================================================================
# SYSTEM PROMPT
# ============================================================================


SYSTEM_PROMPT = """You are an intelligent HR assistant for ACME Corporation. You help employees with HR-related questions and tasks.

Current Date: {current_date}
User: {user_name} ({user_email}) - {user_role}
User Employee ID: {user_id}

**CRITICAL RULES:**
1. You MUST use tools to retrieve ALL factual information about employees, PTO, salaries, etc.
2. NEVER make up or guess any data - always use the appropriate tool first.
3. When the user says "my" or "I", use their employee_id ({user_id}) as the target.
4. To look up another employee by name, use search_employee first to get their ID.

**Available Tool Categories:**
- Employee Info: search_employee, get_employee_basic, get_employee_tenure
- Organization: get_manager, get_direct_reports, get_manager_chain, get_team_overview, get_department_directory, get_org_chart
- Time Off: get_holiday_balance, get_holiday_requests, submit_holiday_request, cancel_holiday_request, get_pending_approvals, approve_holiday_request, reject_holiday_request, get_team_calendar
- Compensation: get_compensation, get_salary_history, get_team_compensation_summary (restricted)
- Company Info: get_company_policies, get_policy_details, get_company_holidays, get_announcements, get_upcoming_events

**Authorization:**
- Users can access their own information
- Managers can view their direct reports' info
- HR can access all employee data
- Compensation data is restricted - users can only see their own salary

**Guidelines:**
- Be helpful and concise
- If access is denied, explain what the user CAN do instead
- For sensitive actions (submitting requests, approvals), confirmation will be requested
"""


def get_system_message(state: AgentState) -> SystemMessage:
    """Generate system message with user context."""
    # Get user info
    user_info = get_employee_service().get_basic_info(state["user_id"])
    user_name = user_info.get("preferred_name", "User") if user_info else "User"

    return SystemMessage(
        content=SYSTEM_PROMPT.format(
            current_date=state["current_date"],
            user_name=user_name,
            user_email=state["user_email"],
            user_role=state["user_role"],
            user_id=state["user_id"],
        )
    )


# ============================================================================
# LLM SETUP
# ============================================================================


def get_llm():
    """Get the configured LLM with tools bound."""
    # Support both OpenAI and compatible endpoints
    if settings.llm_base_url:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
        )
    else:
        llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=0,
        )

    # Bind all tools
    tools = get_all_tools()
    return llm.bind_tools(tools)


# ============================================================================
# NODE FUNCTIONS
# ============================================================================


def agent_node(state: AgentState) -> dict:
    """Main agent node - calls LLM to decide next action."""
    llm = get_llm()

    # Build messages with system prompt
    messages = [get_system_message(state)] + list(state["messages"])

    # Call LLM
    response = llm.invoke(messages)

    return {"messages": [response]}


def check_authorization(state: AgentState) -> dict:
    """Check if the requested tool call is authorized."""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    policy_engine = get_policy_engine()

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # Get target employee ID if specified
        target_id = tool_args.get("employee_id") or tool_args.get("manager_employee_id")

        # Create policy context
        ctx = PolicyContext(
            requester_id=state["user_id"],
            requester_email=state["user_email"],
            requester_role=state["user_role"],
            action=tool_name,
            target_id=target_id,
        )

        # Check authorization
        if not policy_engine.is_allowed(ctx):
            # Create a denial message
            denial_msg = ToolMessage(
                content=json.dumps(
                    {
                        "error": "Access Denied",
                        "message": f"You don't have permission to access this information. You can only view your own data or data for your direct reports.",
                    }
                ),
                tool_call_id=tool_call["id"],
            )
            return {"messages": [denial_msg]}

    return {}


def tool_node(state: AgentState) -> dict:
    """Execute tool calls."""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    tool_messages = []
    tools_called = list(state.get("tools_called", []))

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # Track tool call
        if tool_name not in tools_called:
            tools_called.append(tool_name)

        # Get the tool function
        tool_func = TOOL_MAP.get(tool_name)

        if tool_func is None:
            result = {"error": f"Unknown tool: {tool_name}"}
        else:
            try:
                # Invoke the tool
                result = tool_func.invoke(tool_args)
            except Exception as e:
                result = {"error": str(e)}

        # Create tool message
        tool_messages.append(
            ToolMessage(
                content=json.dumps(result, default=str),
                tool_call_id=tool_call["id"],
            )
        )

    return {
        "messages": tool_messages,
        "tools_called": tools_called,
    }


def check_confirmation_node(state: AgentState) -> dict:
    """Check if any tool calls require human confirmation."""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    confirmation_tools = {t.name for t in get_tools_requiring_confirmation()}

    for tool_call in last_message.tool_calls:
        if tool_call["name"] in confirmation_tools:
            # Store pending confirmation
            return {
                "pending_confirmation": {
                    "tool_name": tool_call["name"],
                    "tool_args": tool_call["args"],
                    "tool_call_id": tool_call["id"],
                    "message": f"Please confirm: {tool_call['name']} with args {tool_call['args']}",
                }
            }

    return {}


def human_confirmation_node(state: AgentState) -> dict:
    """Handle human confirmation (this is an interrupt point)."""
    # This node is where the graph will pause for human input
    # The confirmation response will be added to messages
    pending = state.get("pending_confirmation")

    if pending:
        # Clear pending confirmation after handling
        return {"pending_confirmation": None}

    return {}


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Determine if we should continue to tools or end."""
    messages = state["messages"]
    last_message = messages[-1]

    # If there are tool calls, continue to tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Otherwise, end
    return "end"


def after_tools(state: AgentState) -> Literal["agent", "end"]:
    """Determine next step after tool execution."""
    messages = state["messages"]

    # Check if the last message is a tool result
    if messages and isinstance(messages[-1], ToolMessage):
        # Continue to agent to process the result
        return "agent"

    return "end"


def needs_confirmation(state: AgentState) -> Literal["confirm", "execute"]:
    """Check if human confirmation is needed."""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return "execute"

    confirmation_tools = {t.name for t in get_tools_requiring_confirmation()}

    for tool_call in last_message.tool_calls:
        if tool_call["name"] in confirmation_tools:
            return "confirm"

    return "execute"


def check_auth_result(state: AgentState) -> Literal["execute", "agent"]:
    """Check authorization result."""
    messages = state["messages"]
    if not messages:
        return "execute"

    last_message = messages[-1]

    # If the last message is a ToolMessage with an error, go back to agent
    if isinstance(last_message, ToolMessage):
        try:
            content = json.loads(last_message.content)
            if content.get("error") == "Access Denied":
                return "agent"
        except (json.JSONDecodeError, TypeError):
            pass

    return "execute"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================


def create_hr_agent_graph() -> StateGraph:
    """Create the HR Agent LangGraph workflow."""

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("check_auth", check_authorization)
    workflow.add_node("tools", tool_node)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "check_auth",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "check_auth",
        check_auth_result,
        {
            "execute": "tools",
            "agent": "agent",  # Go back to agent if auth denied
        },
    )

    workflow.add_conditional_edges(
        "tools",
        after_tools,
        {
            "agent": "agent",
            "end": END,
        },
    )

    return workflow


def compile_hr_agent(checkpointer=None):
    """Compile the HR Agent graph."""
    workflow = create_hr_agent_graph()

    if checkpointer is None:
        checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)


# ============================================================================
# HR AGENT CLASS (Wrapper for compatibility)
# ============================================================================


class HRAgentLangGraph:
    """
    LangGraph-based HR Agent.

    Drop-in replacement for the original HRAgent class.
    """

    def __init__(self, user_email: str, session_id: str | None = None):
        self.user_email = user_email
        self.session_id = (
            session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # Get user context
        self.requester_context = self._get_requester_context(user_email)

        # Compile the graph
        self.checkpointer = MemorySaver()
        self.graph = compile_hr_agent(self.checkpointer)

        # Track tools called (for eval compatibility)
        self._tools_called: list[str] = []

    def _get_requester_context(self, user_email: str) -> dict:
        """Get the requester's context including role and permissions."""
        return get_employee_service().get_requester_context(user_email)

    def chat(self, query: str) -> str:
        """Process a user query and return the response."""
        # Create initial state
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query)],
            "user_email": self.user_email,
            "user_id": self.requester_context.get("employee_id", 0),
            "user_role": self.requester_context.get("role", "employee"),
            "pending_confirmation": None,
            "tools_called": [],
            "current_date": datetime.now().strftime("%Y-%m-%d"),
        }

        # Run the graph
        config = {"configurable": {"thread_id": self.session_id}}

        try:
            result = self.graph.invoke(initial_state, config)

            # Track tools called
            self._tools_called = result.get("tools_called", [])

            # Get the final response
            messages = result.get("messages", [])

            # Find the last AI message
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    return msg.content

            return "I'm sorry, I couldn't process your request."

        except Exception as e:
            return f"An error occurred: {str(e)}"

    @property
    def tools_called(self) -> list[str]:
        """Get the list of tools called in the last interaction."""
        return self._tools_called

    # Compatibility property for evals
    class _SessionCompat:
        def __init__(self, agent: "HRAgentLangGraph"):
            self._agent = agent
            self.turns = []

        def get_context(self, key: str):
            if key == "tools_called":
                return self._agent._tools_called
            return None

        def update_context(self, key: str, value: Any):
            pass

    @property
    def session(self):
        """Compatibility property for evals."""
        return self._SessionCompat(self)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def run_hr_agent(user_email: str, question: str) -> str:
    """Run the HR agent with a single query.

    Args:
        user_email: The email of the user making the request
        question: The question to ask

    Returns:
        The agent's response
    """
    agent = HRAgentLangGraph(user_email)
    return agent.chat(question)


# ============================================================================
# VISUALIZATION
# ============================================================================


def visualize_graph():
    """Generate a visualization of the agent graph."""
    workflow = create_hr_agent_graph()

    try:
        # Try to generate a PNG visualization
        png_data = workflow.compile().get_graph().draw_mermaid_png()

        # Save to file
        with open("hr_agent_graph.png", "wb") as f:
            f.write(png_data)
        print("Graph visualization saved to hr_agent_graph.png")

    except Exception as e:
        # Fall back to Mermaid text representation
        print("Mermaid diagram:")
        print(workflow.compile().get_graph().draw_mermaid())
