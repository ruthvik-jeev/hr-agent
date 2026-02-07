"""
Security Module

Production security features:
- Rate limiting
- Request throttling
- Audit logging
- Input sanitization
"""

import time
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


# ============================================================================
# RATE LIMITING
# ============================================================================


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10  # Max requests in a 1-second burst


class RateLimiter:
    """
    Token bucket rate limiter.

    In production, use Redis for distributed rate limiting across multiple instances.
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._buckets: dict[str, dict] = defaultdict(self._create_bucket)

    def _create_bucket(self) -> dict:
        return {
            "tokens": self.config.burst_limit,
            "last_update": time.time(),
            "minute_count": 0,
            "minute_start": time.time(),
            "hour_count": 0,
            "hour_start": time.time(),
        }

    def is_allowed(self, key: str) -> tuple[bool, dict]:
        """
        Check if a request is allowed for the given key (e.g., user_id or IP).

        Returns:
            (allowed: bool, info: dict with rate limit details)
        """
        bucket = self._buckets[key]
        now = time.time()

        # Refill tokens based on time passed
        time_passed = now - bucket["last_update"]
        bucket["tokens"] = min(
            self.config.burst_limit,
            bucket["tokens"] + time_passed * (self.config.requests_per_minute / 60),
        )
        bucket["last_update"] = now

        # Reset minute counter if needed
        if now - bucket["minute_start"] >= 60:
            bucket["minute_count"] = 0
            bucket["minute_start"] = now

        # Reset hour counter if needed
        if now - bucket["hour_start"] >= 3600:
            bucket["hour_count"] = 0
            bucket["hour_start"] = now

        # Check limits
        info = {
            "tokens_remaining": int(bucket["tokens"]),
            "minute_remaining": self.config.requests_per_minute
            - bucket["minute_count"],
            "hour_remaining": self.config.requests_per_hour - bucket["hour_count"],
        }

        if bucket["tokens"] < 1:
            return False, {**info, "reason": "burst_limit_exceeded"}

        if bucket["minute_count"] >= self.config.requests_per_minute:
            return False, {**info, "reason": "minute_limit_exceeded"}

        if bucket["hour_count"] >= self.config.requests_per_hour:
            return False, {**info, "reason": "hour_limit_exceeded"}

        # Consume token and increment counters
        bucket["tokens"] -= 1
        bucket["minute_count"] += 1
        bucket["hour_count"] += 1

        return True, info


# ============================================================================
# AUDIT LOGGING
# ============================================================================


class AuditAction(Enum):
    """Types of auditable actions."""

    LOGIN = "login"
    LOGOUT = "logout"
    VIEW_DATA = "view_data"
    MODIFY_DATA = "modify_data"
    DELETE_DATA = "delete_data"
    EXPORT_DATA = "export_data"
    POLICY_DENIED = "policy_denied"
    ADMIN_ACTION = "admin_action"
    SENSITIVE_ACCESS = "sensitive_access"


@dataclass
class AuditEntry:
    """A single audit log entry."""

    timestamp: datetime
    action: AuditAction
    user_email: str
    resource_type: str
    resource_id: str | None
    details: dict
    ip_address: str | None = None
    user_agent: str | None = None
    success: bool = True

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "user_email": self.user_email,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "success": self.success,
        }


class AuditLogger:
    """
    Audit logger for compliance and security monitoring.

    In production:
    - Write to immutable storage (append-only database, S3, etc.)
    - Send to SIEM systems (Splunk, Datadog, etc.)
    - Implement tamper detection
    """

    def __init__(self):
        self._entries: list[AuditEntry] = []

    def log(
        self,
        action: AuditAction,
        user_email: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        success: bool = True,
    ):
        """Log an audit entry."""
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            action=action,
            user_email=user_email,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
        )
        self._entries.append(entry)

        # In production, also write to persistent storage
        # self._persist_entry(entry)

    def log_sensitive_access(
        self,
        user_email: str,
        data_type: str,
        target_employee_id: int | None = None,
        action_name: str = "view",
    ):
        """Convenience method for logging access to sensitive data."""
        self.log(
            action=AuditAction.SENSITIVE_ACCESS,
            user_email=user_email,
            resource_type=data_type,
            resource_id=str(target_employee_id) if target_employee_id else None,
            details={"action_name": action_name},
        )

    def log_policy_denial(
        self,
        user_email: str,
        action: str,
        target: str | None = None,
        reason: str | None = None,
    ):
        """Log when a policy denies access."""
        self.log(
            action=AuditAction.POLICY_DENIED,
            user_email=user_email,
            resource_type="policy",
            details={"attempted_action": action, "target": target, "reason": reason},
            success=False,
        )

    def get_entries(
        self,
        user_email: str | None = None,
        action: AuditAction | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query audit entries."""
        entries = self._entries

        if user_email:
            entries = [e for e in entries if e.user_email == user_email]
        if action:
            entries = [e for e in entries if e.action == action]
        if since:
            entries = [e for e in entries if e.timestamp >= since]

        return entries[-limit:]


# ============================================================================
# SENSITIVE DATA HANDLING
# ============================================================================


class SensitiveDataType(Enum):
    """Types of sensitive data that require special handling."""

    COMPENSATION = "compensation"
    SSN = "ssn"
    BANK_ACCOUNT = "bank_account"
    MEDICAL = "medical"
    PERFORMANCE = "performance"
    DISCIPLINARY = "disciplinary"


# Actions that access sensitive data
SENSITIVE_ACTIONS = {
    "get_compensation": SensitiveDataType.COMPENSATION,
    "get_salary_history": SensitiveDataType.COMPENSATION,
    "get_team_compensation_summary": SensitiveDataType.COMPENSATION,
    "get_performance_review": SensitiveDataType.PERFORMANCE,
}


def is_sensitive_action(action: str) -> bool:
    """Check if an action accesses sensitive data."""
    return action in SENSITIVE_ACTIONS


def get_sensitive_data_type(action: str) -> SensitiveDataType | None:
    """Get the type of sensitive data accessed by an action."""
    return SENSITIVE_ACTIONS.get(action)


# ============================================================================
# DATA MASKING
# ============================================================================


def mask_email(email: str) -> str:
    """Mask an email address for logging."""
    if not email or "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def mask_salary(amount: float) -> str:
    """Mask a salary amount for logging."""
    magnitude = len(str(int(amount))) - 1
    return f"${10 ** magnitude:,.0f}-{10 ** (magnitude + 1):,.0f}"


def hash_for_logging(value: str) -> str:
    """Create a one-way hash for logging sensitive values."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]


# ============================================================================
# SINGLETONS
# ============================================================================

rate_limiter = RateLimiter()
audit_logger = AuditLogger()
