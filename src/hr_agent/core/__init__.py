"""
Core Module - LangGraph Agent Orchestration

Contains the LangGraph-based agent with:
- Stateful workflow with checkpointing
- Policy-based authorization
- Human-in-the-loop confirmation
- LangSmith tracing integration
"""

# LangGraph Agent
from .langgraph_agent import HRAgentLangGraph, run_hr_agent

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

__all__ = [
    # Agent (LangGraph)
    "HRAgentLangGraph",
    "run_hr_agent",
    # Policy Engine
    "PolicyEngine",
    "PolicyContext",
    "PolicyRule",
    "PolicyResult",
    "get_policy_engine",
    "requires_confirmation",
    "get_confirmation_message",
]
