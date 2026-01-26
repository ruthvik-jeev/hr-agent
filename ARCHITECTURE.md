# Architecture

This document describes the technical architecture of the HR Agent, built on LangChain, LangGraph, and LangSmith.

---

## System Overview

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                              HR AGENT SYSTEM                                  ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   ┌─────────────────────────────────────────────────────────────────────┐    ║
║   │                        CLIENT LAYER                                  │    ║
║   │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐               │    ║
║   │   │ Web UI  │  │  CLI    │  │  REST   │  │  Slack  │               │    ║
║   │   │Streamlit│  │         │  │  API    │  │  Bot    │               │    ║
║   │   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘               │    ║
║   └────────┼────────────┼───────────┼────────────┼──────────────────────┘    ║
║            │            │           │            │                            ║
║            └────────────┴─────┬─────┴────────────┘                            ║
║                               ▼                                               ║
║   ┌─────────────────────────────────────────────────────────────────────┐    ║
║   │                     LANGGRAPH AGENT                                  │    ║
║   │                                                                      │    ║
║   │   ┌──────────┐    ┌────────────┐    ┌──────────┐                    │    ║
║   │   │  AGENT   │───►│ CHECK_AUTH │───►│  TOOLS   │                    │    ║
║   │   │  (LLM)   │    │  (Policy)  │    │(Execute) │                    │    ║
║   │   └────▲─────┘    └─────┬──────┘    └────┬─────┘                    │    ║
║   │        │                │ denied         │                          │    ║
║   │        │                ▼                │                          │    ║
║   │        │          [Error Msg]            │                          │    ║
║   │        └─────────────────────────────────┘                          │    ║
║   └─────────────────────────────────────────────────────────────────────┘    ║
║                               │                                               ║
║                               ▼                                               ║
║   ┌─────────────────────────────────────────────────────────────────────┐    ║
║   │                      SERVICE LAYER                                   │    ║
║   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │    ║
║   │   │  Employee    │  │   Holiday    │  │ Compensation │              │    ║
║   │   │  Service     │  │   Service    │  │   Service    │              │    ║
║   │   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │    ║
║   └──────────┼─────────────────┼─────────────────┼───────────────────────┘    ║
║              │                 │                 │                            ║
║              └─────────────────┼─────────────────┘                            ║
║                                ▼                                              ║
║   ┌─────────────────────────────────────────────────────────────────────┐    ║
║   │                    REPOSITORY LAYER                                  │    ║
║   │                      (SQLAlchemy)                                    │    ║
║   └────────────────────────────┬────────────────────────────────────────┘    ║
║                                │                                              ║
║                                ▼                                              ║
║   ┌─────────────────────────────────────────────────────────────────────┐    ║
║   │                       DATABASE                                       │    ║
║   │                       (SQLite)                                       │    ║
║   └─────────────────────────────────────────────────────────────────────┘    ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## LangGraph Workflow

The agent is implemented as a **LangGraph StateGraph** with three main nodes:

### Nodes

| Node | Purpose |
|------|---------|
| `agent` | Calls LLM with tools, decides next action |
| `check_auth` | Validates permissions via policy engine |
| `tools` | Executes LangChain tools, returns results |

### State Schema

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_email: str
    user_id: int
    user_role: str  # employee, manager, hr, finance
    pending_confirmation: dict | None
    tools_called: list[str]
    current_date: str
```

### Routing Logic

```python
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Route based on whether LLM requested tool calls."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"

def check_auth_result(state: AgentState) -> Literal["execute", "agent"]:
    """Route based on authorization result."""
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage):
        content = json.loads(last_message.content)
        if content.get("error") == "Access Denied":
            return "agent"  # Let LLM explain the denial
    return "execute"
```

---

## Directory Structure

```
src/hr_agent/
├── __init__.py              # Main package exports
├── seed.py                  # Database seeding
│
├── core/                    # 🧠 Agent Orchestration
│   ├── __init__.py
│   ├── langgraph_agent.py   # ✨ Primary LangGraph agent
│   ├── agent.py             # Legacy custom agent
│   ├── policy_engine.py     # Authorization engine
│   ├── memory.py            # Conversation memory
│   ├── llm.py               # LLM integration
│   └── response_utils.py    # Response formatting
│
├── domain/                  # 📋 Domain Models
│   ├── __init__.py
│   └── models.py            # Pydantic models, enums
│
├── services/                # 💼 Business Logic
│   ├── __init__.py
│   ├── langchain_tools.py   # ✨ LangChain tool definitions
│   ├── base.py              # Service classes
│   ├── tools.py             # Legacy tool wrappers
│   └── tool_registry.py     # Declarative tool definitions
│
├── repositories/            # 💾 Data Access
│   ├── __init__.py
│   ├── base.py              # Base repository
│   ├── employee.py
│   ├── holiday.py
│   ├── compensation.py
│   └── company.py
│
├── api/                     # 🌐 REST API
│   ├── __init__.py
│   ├── server.py            # FastAPI app
│   └── cli.py               # CLI interface
│
├── infrastructure/          # ⚙️ Cross-Cutting Concerns
│   ├── __init__.py
│   ├── config.py            # Settings + LangSmith config
│   ├── db.py                # Database engine
│   ├── registry.py          # Dependency injection
│   └── ...
│
└── policies/                # 📜 Policy Configuration
    ├── __init__.py
    └── policies.yaml        # Authorization rules
```

---

## LangChain Tools

All tools are defined using LangChain's `@tool` decorator with Pydantic schemas:

```python
# services/langchain_tools.py

from langchain_core.tools import tool
from pydantic import BaseModel, Field

class SearchEmployeeInput(BaseModel):
    """Input for searching employees."""
    query: str = Field(description="Name or email to search for")

@tool(args_schema=SearchEmployeeInput)
def search_employee(query: str) -> list[dict]:
    """Search for employees by name or email.
    
    Returns a list of matching employees with their basic info.
    Use this when the user asks about someone by name.
    """
    return get_employee_service().search(query)
```

### Tool Categories

| Category | Tools | Access |
|----------|-------|--------|
| **Read-Only** | `get_employee_basic`, `get_manager`, `get_holiday_balance` | Open |
| **Confirmation Required** | `submit_holiday_request`, `cancel_holiday_request` | Human-in-the-loop |
| **Restricted** | `get_compensation`, `get_team_compensation_summary` | Role-based |

---

## Policy Engine

Authorization is handled by a declarative policy engine:

### Policy Rules (YAML)

```yaml
# policies/policies.yaml
- name: self_access
  effect: allow
  conditions:
    - requester_id == target_id

- name: manager_access
  effect: allow
  conditions:
    - requester_is_manager_of(target_id)

- name: hr_full_access
  effect: allow
  conditions:
    - requester_role == 'hr'

- name: compensation_restricted
  effect: deny
  actions: [get_compensation, get_salary_history]
  conditions:
    - requester_id != target_id
    - requester_role not in ['hr', 'finance']
```

### Runtime Check

```python
def check_authorization(state: AgentState) -> dict:
    """Check if the requested tool call is authorized."""
    policy_engine = get_policy_engine()
    
    for tool_call in last_message.tool_calls:
        ctx = PolicyContext(
            requester_id=state["user_id"],
            requester_email=state["user_email"],
            requester_role=state["user_role"],
            action=tool_call["name"],
            target_id=tool_args.get("employee_id"),
        )
        
        if not policy_engine.is_allowed(ctx):
            return {"messages": [ToolMessage(content="Access Denied", ...)]}
    
    return {}
```

---

## LangSmith Integration

Tracing is enabled via environment variables:

```python
# infrastructure/config.py

def configure_langsmith():
    """Configure LangSmith tracing if enabled."""
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        return True
    return False
```

### Enabling Tracing

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=ls-...
export LANGSMITH_PROJECT=hr-agent

python run_evals.py --langgraph
```

---

## Evaluation Framework

The evaluation system tests both agent implementations:

```python
# evals/runner.py

class EvalRunner:
    def __init__(
        self,
        dataset: EvalDataset,
        agent_type: AgentType = "langgraph",  # or "original"
        ...
    ):
        self.agent_type = agent_type
    
    def _run_single_case(self, case: EvalCase) -> EvalResult:
        if self.agent_type == "langgraph":
            agent = HRAgentLangGraph(case.user_email)
        else:
            agent = HRAgent(case.user_email)
        
        response = agent.chat(case.query)
        ...
```

### Test Categories

| Suite | Focus | Cases |
|-------|-------|-------|
| Suite 1 | Basic functionality | 16 |
| Suite 2 | Advanced & edge cases | 16 |
| Suite 3 | Regression & robustness | 12 |

---

## Key Design Decisions

### 1. LangGraph over Custom Agent Loop

**Why**: LangGraph provides:
- Visual workflow debugging
- Built-in state management
- Easier human-in-the-loop patterns
- Better integration with LangSmith

### 2. LangChain Tools over Custom Tool Definitions

**Why**: LangChain tools provide:
- Pydantic schema validation
- Automatic docstring extraction for LLM
- Standardized invocation interface
- Type safety

### 3. Policy-as-Code Authorization

**Why**: YAML policies provide:
- Declarative, auditable rules
- Easy modification without code changes
- Clear separation of business logic and security

### 4. Dual Agent Support

**Why**: Keeping both implementations allows:
- A/B comparison testing
- Gradual migration
- Fallback option

---

## Import Examples

```python
# Primary agent (LangGraph)
from hr_agent.core import HRAgentLangGraph

# LangChain tools
from hr_agent.services.langchain_tools import get_all_tools, TOOL_MAP

# Policy engine
from hr_agent.core import PolicyEngine, get_policy_engine

# Services
from hr_agent.services import get_employee_service

# Configuration
from hr_agent.infrastructure import settings, configure_langsmith
```
