"""
HR Agent v2.0 - A production-ready HR assistant

Built with LangChain/LangGraph/LangSmith stack:
- LangGraph: Stateful agent workflow with checkpointing
- LangChain: Tool definitions and LLM integration
- LangSmith: Tracing and observability

Architecture:
- core/: LangGraph agent and policy engine
- domain/: Models, schemas, and enums
- services/: Business logic and LangChain tools
- repositories/: Data access layer
- api/: FastAPI REST endpoints
- infrastructure/: Config, database, observability
- policies/: YAML policy configurations
"""

# LangGraph Agent
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
    get_all_tools,
)

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
    # Agent
    "HRAgentLangGraph",
    "run_hr_agent",
    # Services
    "get_employee_service",
    "get_holiday_service",
    "get_compensation_service",
    "get_company_service",
    "EmployeeService",
    "HolidayService",
    "CompensationService",
    "CompanyService",
    # Tools
    "get_all_tools",
    # Registry
    "registry",
    "AppRegistry",
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
