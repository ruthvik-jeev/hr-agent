"""
Company Repository - Policies, holidays, announcements, events
"""

from .base import BaseRepository


class CompanyRepository(BaseRepository):
    """Repository for company-wide information."""

    # ========== POLICIES ==========

    def get_policies(self) -> list[dict]:
        """Get list of active company policies."""
        return self._execute_query(
            """SELECT policy_id, title, category, summary, effective_date
               FROM company_policy WHERE status = 'ACTIVE'
               ORDER BY category, title"""
        )

    def get_policy_by_id(self, policy_id: int) -> dict | None:
        """Get full details of a company policy."""
        return self._execute_query_one(
            """SELECT policy_id, title, category, summary, full_text, effective_date, last_updated
               FROM company_policy WHERE policy_id=:p""",
            {"p": policy_id},
        )

    # ========== HOLIDAYS ==========

    def get_holidays(self, year: int) -> list[dict]:
        """Get company-observed holidays for a year."""
        return self._execute_query(
            """SELECT holiday_date, name, is_paid
               FROM company_holiday WHERE substr(holiday_date,1,4) = :yyyy
               ORDER BY holiday_date""",
            {"yyyy": str(year)},
        )

    # ========== ANNOUNCEMENTS ==========

    def get_announcements(self, limit: int = 10) -> list[dict]:
        """Get recent company announcements."""
        return self._execute_query(
            """SELECT announcement_id, title, summary, category, posted_by, posted_at
               FROM announcement
               WHERE expires_at IS NULL OR expires_at > datetime('now')
               ORDER BY posted_at DESC LIMIT :lim""",
            {"lim": limit},
        )

    # ========== EVENTS ==========

    def get_upcoming_events(self, days_ahead: int = 30) -> list[dict]:
        """Get upcoming company events."""
        return self._execute_query(
            """SELECT event_id, title, event_date, event_time, location, description
               FROM company_event
               WHERE event_date >= date('now') AND event_date <= date('now', '+' || :days || ' days')
               ORDER BY event_date, event_time""",
            {"days": days_ahead},
        )

    # ========== FINANCE ACCESS ==========

    def has_cost_center_access(self, user_email: str, cost_center: str) -> bool:
        """Check if finance user has access to cost center."""
        result = self._execute_scalar(
            """SELECT 1 FROM finance_cost_center_access
               WHERE user_email=:u AND cost_center=:cc""",
            {"u": user_email, "cc": cost_center},
        )
        return result is not None
