"""
Core Module - Agent Orchestration

Contains both agent implementations:
- HRAgent: Original custom implementation
- HRAgentLangGraph: LangChain/LangGraph-based implementation

Also includes policy engine, memory management, and LLM integration.
"""

# Original Agent
from .agent import HRAgent, ToolExecutor, get_requester_context, run_agent

# LangGraph Agent
from .langgraph_agent import HRAgentLangGraph, run_hr_agent as run_langgraph_agent

# Domain model (aliased for backward compatibility)
from ..domain.models import AgentAction as Action

# Policy Engine
from .policy_engine import (
    PolicyEngine,
    PolicyContext,
    PolicyRule,
    PolicyResult,
    get_policy_engine,
    requires_confirmation,
    get_confirmation_message,
)

# Memory
from .memory import (
    MemoryStore,
    ConversationSession,
    ConversationTurn,
    get_memory_store,
)

# LLM
from .llm import chat

# Response Utils
from .response_utils import prepare_tool_response

__all__ = [
    # Agent (Original)
    "HRAgent",
    "Action",
    "ToolExecutor",
    "get_requester_context",
    "run_agent",
    # Agent (LangGraph)
    "HRAgentLangGraph",
    "run_langgraph_agent",
    # Policy Engine
    "PolicyEngine",
    "PolicyContext",
    "PolicyRule",
    "PolicyResult",
    "get_policy_engine",
    "requires_confirmation",
    "get_confirmation_message",
    # Memory
    "MemoryStore",
    "ConversationSession",
    "ConversationTurn",
    "get_memory_store",
    # LLM
    "chat",
    # Response Utils
    "prepare_tool_response",
]
