# Architecture

Technical architecture of the HR Agent built on LangChain, LangGraph, and LangSmith.

## System Overview

The agent uses a LangGraph StateGraph workflow:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   AGENT     │────►│  CHECK_AUTH  │────►│    TOOLS    │
│   (LLM)     │     │  (Policy)    │     │  (Execute)  │
└──────▲──────┘     └──────┬───────┘     └──────┬──────┘
       │                   │ denied             │
       │                   ▼                    │
       │            [Return Error]              │
       └────────────────────────────────────────┘
```

## Agent State

```python
class AgentState(TypedDict):
    messages: Sequence[BaseMessage]  # Conversation history
    user_email: str                  # Authenticated user
    user_id: int                     # Employee ID
    user_role: str                   # employee/manager/hr/finance
    tools_called: list[str]          # Tools used
```

## Directory Structure

```
src/hr_agent/
├── core/                    # Agent Logic
│   ├── langgraph_agent.py   # Primary LangGraph agent
│   ├── policy_engine.py     # Authorization
│   └── memory.py            # Conversation state
│
├── services/                # Business Logic
│   ├── langchain_tools.py   # LangChain tool definitions
│   └── base.py              # Service classes
│
├── repositories/            # Data Access
├── api/                     # REST API
├── infrastructure/          # Config & Utils
└── policies/                # Authorization Rules (YAML)
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Workflow | LangGraph StateGraph |
| Tools | LangChain @tool |
| LLM | OpenAI GPT-4o |
| Tracing | LangSmith |
| Database | SQLAlchemy + SQLite |
| API | FastAPI |
| UI | Streamlit |

## LangSmith Integration

Enable tracing:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=ls-...
```
