"""
HR Agent v2.0 - A production-ready HR assistant

Architecture (Reorganized):
- core/: Agent orchestration, policy engine, memory, LLM
- domain/: Models, schemas, and enums
- services/: Business logic layer and tool implementations
- repositories/: Data access layer (SQL abstraction)
- api/: FastAPI REST endpoints
- infrastructure/: Config, database, observability, security, errors
- policies/: YAML policy configurations

Supports both:
- Original HRAgent (custom implementation)
- HRAgentLangGraph (LangChain/LangGraph-based)
"""

# Core - Original Agent
from .core.agent import HRAgent

# Core - LangGraph Agent
from .core.langgraph_agent import HRAgentLangGraph, run_hr_agent

# Services
from .services import (
    get_employee_service,
    get_holiday_service,
    get_compensation_service,
    get_company_service,
    EmployeeService,
    HolidayService,
    CompensationService,
    CompanyService,
)

# Tool Registry (Legacy)
from .services.tool_registry import get_tool_registry, ToolRegistry, ToolDefinition

# LangChain Tools
from .services.langchain_tools import get_all_tools as get_hr_tools

# Domain Models
from .domain.models import (
    UserRole,
    HolidayRequestStatus,
    AgentAction,
    ChatRequest,
    ChatResponse,
    UserContext,
)

# Infrastructure
from .infrastructure.registry import registry, AppRegistry
from .infrastructure.errors import (
    HRAgentError,
    AuthorizationError,
    ValidationError,
    ResourceNotFoundError,
)

__all__ = [
    # Agents
    "HRAgent",  # Original
    "HRAgentLangGraph",  # LangGraph-based
    "run_hr_agent",  # LangGraph runner
    # Services
    "get_employee_service",
    "get_holiday_service",
    "get_compensation_service",
    "get_company_service",
    "EmployeeService",
    "HolidayService",
    "CompensationService",
    "CompanyService",
    # Registry
    "registry",
    "AppRegistry",
    # Tool Registry (Legacy)
    "get_tool_registry",
    "ToolRegistry",
    "ToolDefinition",
    # LangChain Tools
    "get_hr_tools",
    # Models
    "UserRole",
    "HolidayRequestStatus",
    "AgentAction",
    "ChatRequest",
    "ChatResponse",
    "UserContext",
    # Errors
    "HRAgentError",
    "AuthorizationError",
    "ValidationError",
    "ResourceNotFoundError",
]
