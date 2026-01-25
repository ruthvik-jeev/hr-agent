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
"""

# Core
from .core.agent import HRAgent

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

# Tool Registry
from .services.tool_registry import get_tool_registry, ToolRegistry, ToolDefinition

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
    "HRAgent",
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
    # Tool Registry
    "get_tool_registry",
    "ToolRegistry",
    "ToolDefinition",
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
