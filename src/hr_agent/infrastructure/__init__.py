"""
Infrastructure Module - Cross-Cutting Concerns

Contains configuration, database, observability, security, error handling,
and other infrastructure components.
"""

from .config import settings, Settings
from .db import get_engine
from .registry import registry, AppRegistry
from .errors import (
    HRAgentError,
    AuthorizationError,
    ValidationError,
    ResourceNotFoundError,
    ExternalServiceError,
    LLMError,
    RateLimitError,
    retry_with_backoff,
    CircuitBreaker,
)
from .observability import logger, metrics, tracer
from .security import rate_limiter, audit_logger, AuditAction
from .validation import Validators, ValidationResult
from .decorators import (
    log_execution,
    timed,
    validate_params,
    require_not_none,
    cache_result,
    deprecated,
    rate_limit,
    sanitize_output,
)

__all__ = [
    # Config
    "settings",
    "Settings",
    # Database
    "get_engine",
    # Registry
    "registry",
    "AppRegistry",
    # Errors
    "HRAgentError",
    "AuthorizationError",
    "ValidationError",
    "ResourceNotFoundError",
    "ExternalServiceError",
    "LLMError",
    "RateLimitError",
    "retry_with_backoff",
    "CircuitBreaker",
    # Observability
    "logger",
    "metrics",
    "tracer",
    # Security
    "rate_limiter",
    "audit_logger",
    "AuditAction",
    # Validation
    "Validators",
    "ValidationResult",
    # Decorators
    "log_execution",
    "timed",
    "validate_params",
    "require_not_none",
    "cache_result",
    "deprecated",
    "rate_limit",
    "sanitize_output",
]
