"""
Core Module - Agent Orchestration

Contains the main agent logic, policy engine, memory management, and LLM integration.
"""

from .agent import HRAgent, ToolExecutor, get_requester_context, run_agent
from ..domain.models import AgentAction as Action
from .policy_engine import (
    PolicyEngine,
    PolicyContext,
    PolicyRule,
    PolicyResult,
    get_policy_engine,
    requires_confirmation,
    get_confirmation_message,
)
from .memory import (
    MemoryStore,
    ConversationSession,
    ConversationTurn,
    get_memory_store,
)
from .llm import chat
from .response_utils import prepare_tool_response

__all__ = [
    # Agent
    "HRAgent",
    "Action",
    "ToolExecutor",
    "get_requester_context",
    "run_agent",
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
