"""
Domain Module - Models and Schemas

Contains all Pydantic models, enums, and API schemas used throughout the application.
"""

from .models import (
    # Enums
    UserRole,
    HolidayRequestStatus,
    EscalationStatus,
    HRRequestStatus,
    HRRequestPriority,
    HRRequestRiskLevel,
    PolicyEffect,
    # Domain Models
    Employee,
    Manager,
    HolidayBalance,
    HolidayRequest,
    Compensation,
    CompanyPolicy,
    CompanyHoliday,
    Announcement,
    TeamOverview,
    HRRequest,
    HRRequestEvent,
    # API Schemas
    UserContext,
    AgentAction,
    ChatRequest,
    ChatResponse,
    SessionInfo,
    HealthResponse,
    ErrorResponse,
    # Policy Models
    PolicyContext,
    PolicyResult,
)

__all__ = [
    # Enums
    "UserRole",
    "HolidayRequestStatus",
    "EscalationStatus",
    "HRRequestStatus",
    "HRRequestPriority",
    "HRRequestRiskLevel",
    "PolicyEffect",
    # Domain Models
    "Employee",
    "Manager",
    "HolidayBalance",
    "HolidayRequest",
    "Compensation",
    "CompanyPolicy",
    "CompanyHoliday",
    "Announcement",
    "TeamOverview",
    "HRRequest",
    "HRRequestEvent",
    # API Schemas
    "UserContext",
    "AgentAction",
    "ChatRequest",
    "ChatResponse",
    "SessionInfo",
    "HealthResponse",
    "ErrorResponse",
    # Policy Models
    "PolicyContext",
    "PolicyResult",
]
