"""
Required-field validation tests covering all Validators methods.

Tests positive cases (valid input) and negative cases (missing, empty,
out-of-range, and malformed values) for every validator.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from hr_agent.utils.validation import (
    ValidationResult,
    Validators,
    sanitize_for_logging,
    sanitize_user_input,
)


# ── Email ────────────────────────────────────────────────────────────────────


class TestValidateEmail:
    def test_valid_email(self):
        r = Validators.validate_email("Alice@Acme.COM")
        assert r.is_valid
        assert r.sanitized_value == "alice@acme.com"

    def test_empty_email_rejected(self):
        assert not Validators.validate_email("").is_valid

    def test_none_coerced_empty(self):
        # None should be caught as falsy
        assert not Validators.validate_email(None).is_valid  # type: ignore[arg-type]

    def test_too_long_email_rejected(self):
        long_email = "a" * 250 + "@b.com"
        assert not Validators.validate_email(long_email).is_valid

    def test_invalid_format_rejected(self):
        assert not Validators.validate_email("not-an-email").is_valid

    def test_whitespace_stripped(self):
        r = Validators.validate_email("  user@x.com  ")
        assert r.is_valid
        assert r.sanitized_value == "user@x.com"


# ── Date ─────────────────────────────────────────────────────────────────────


class TestValidateDate:
    def test_valid_date(self):
        r = Validators.validate_date("2026-03-15")
        assert r.is_valid
        assert r.sanitized_value == date(2026, 3, 15)

    def test_empty_date_rejected(self):
        assert not Validators.validate_date("").is_valid

    def test_wrong_format_rejected(self):
        assert not Validators.validate_date("15/03/2026").is_valid

    def test_invalid_day_rejected(self):
        assert not Validators.validate_date("2026-02-30").is_valid


# ── Date Range ───────────────────────────────────────────────────────────────


class TestValidateDateRange:
    def test_valid_future_range(self):
        start = (date.today() + timedelta(days=1)).isoformat()
        end = (date.today() + timedelta(days=5)).isoformat()
        r = Validators.validate_date_range(start, end)
        assert r.is_valid

    def test_end_before_start_rejected(self):
        start = (date.today() + timedelta(days=5)).isoformat()
        end = (date.today() + timedelta(days=1)).isoformat()
        r = Validators.validate_date_range(start, end)
        assert not r.is_valid
        assert "after" in r.error_message

    def test_past_start_rejected(self):
        start = (date.today() - timedelta(days=5)).isoformat()
        end = (date.today() + timedelta(days=1)).isoformat()
        r = Validators.validate_date_range(start, end)
        assert not r.is_valid
        assert "past" in r.error_message

    def test_past_allowed_when_flag_set(self):
        start = (date.today() - timedelta(days=5)).isoformat()
        end = date.today().isoformat()
        r = Validators.validate_date_range(start, end, allow_past=True)
        assert r.is_valid

    def test_exceeds_max_range_rejected(self):
        start = (date.today() + timedelta(days=1)).isoformat()
        end = (date.today() + timedelta(days=400)).isoformat()
        r = Validators.validate_date_range(start, end)
        assert not r.is_valid
        assert "exceed" in r.error_message


# ── Employee ID ──────────────────────────────────────────────────────────────


class TestValidateEmployeeId:
    def test_valid_id(self):
        r = Validators.validate_employee_id(42)
        assert r.is_valid
        assert r.sanitized_value == 42

    def test_none_rejected(self):
        assert not Validators.validate_employee_id(None).is_valid

    def test_zero_rejected(self):
        assert not Validators.validate_employee_id(0).is_valid

    def test_negative_rejected(self):
        assert not Validators.validate_employee_id(-1).is_valid

    def test_too_large_rejected(self):
        assert not Validators.validate_employee_id(1_000_000).is_valid

    def test_string_coerced(self):
        r = Validators.validate_employee_id("123")
        assert r.is_valid
        assert r.sanitized_value == 123

    def test_non_numeric_rejected(self):
        assert not Validators.validate_employee_id("abc").is_valid


# ── Year ─────────────────────────────────────────────────────────────────────


class TestValidateYear:
    def test_valid_year(self):
        r = Validators.validate_year(2025)
        assert r.is_valid
        assert r.sanitized_value == 2025

    def test_none_defaults_to_current(self):
        r = Validators.validate_year(None)
        assert r.is_valid
        assert r.sanitized_value == datetime.now().year

    def test_below_min_rejected(self):
        assert not Validators.validate_year(2019).is_valid

    def test_above_max_rejected(self):
        assert not Validators.validate_year(2031).is_valid

    def test_non_numeric_rejected(self):
        assert not Validators.validate_year("abc").is_valid


# ── Days ─────────────────────────────────────────────────────────────────────


class TestValidateDays:
    def test_valid_days(self):
        r = Validators.validate_days(5)
        assert r.is_valid
        assert r.sanitized_value == 5.0

    def test_rounds_to_half_day(self):
        r = Validators.validate_days(2.74)
        assert r.is_valid
        assert r.sanitized_value == 2.5

    def test_none_rejected(self):
        assert not Validators.validate_days(None).is_valid

    def test_below_min_rejected(self):
        assert not Validators.validate_days(0.1).is_valid

    def test_above_max_rejected(self):
        assert not Validators.validate_days(31).is_valid

    def test_non_numeric_rejected(self):
        assert not Validators.validate_days("xyz").is_valid


# ── Search Query ─────────────────────────────────────────────────────────────


class TestValidateSearchQuery:
    def test_valid_query(self):
        r = Validators.validate_search_query("John Doe")
        assert r.is_valid

    def test_empty_rejected(self):
        assert not Validators.validate_search_query("").is_valid

    def test_too_short_rejected(self):
        assert not Validators.validate_search_query("a").is_valid

    def test_too_long_rejected(self):
        assert not Validators.validate_search_query("a" * 201).is_valid

    def test_sql_injection_chars_stripped(self):
        r = Validators.validate_search_query("John'; DROP TABLE--")
        assert r.is_valid
        assert ";" not in r.sanitized_value
        assert "'" not in r.sanitized_value


# ── Reason ───────────────────────────────────────────────────────────────────


class TestValidateReason:
    def test_valid_reason(self):
        r = Validators.validate_reason("Family vacation")
        assert r.is_valid

    def test_empty_when_not_required(self):
        r = Validators.validate_reason(None, required=False)
        assert r.is_valid

    def test_empty_when_required_rejected(self):
        r = Validators.validate_reason(None, required=True)
        assert not r.is_valid

    def test_too_long_rejected(self):
        r = Validators.validate_reason("x" * 501)
        assert not r.is_valid


# ── Department ───────────────────────────────────────────────────────────────


class TestValidateDepartment:
    def test_valid_department(self):
        r = Validators.validate_department("Engineering")
        assert r.is_valid

    def test_case_insensitive(self):
        r = Validators.validate_department("engineering")
        assert r.is_valid
        assert r.sanitized_value == "Engineering"

    def test_empty_rejected(self):
        assert not Validators.validate_department("").is_valid

    def test_invalid_department_rejected(self):
        r = Validators.validate_department("Custodial")
        assert not r.is_valid
        assert "Valid options" in r.error_message


# ── Limit ────────────────────────────────────────────────────────────────────


class TestValidateLimit:
    def test_none_uses_default(self):
        r = Validators.validate_limit(None)
        assert r.sanitized_value == 10

    def test_clamps_to_max(self):
        r = Validators.validate_limit(200)
        assert r.sanitized_value == 100

    def test_clamps_to_min(self):
        r = Validators.validate_limit(0)
        assert r.sanitized_value == 1

    def test_non_numeric_uses_default(self):
        r = Validators.validate_limit("abc")
        assert r.sanitized_value == 10


# ── Sanitize for Logging ────────────────────────────────────────────────────


class TestSanitizeForLogging:
    def test_redacts_sensitive_fields(self):
        data = {"name": "Alice", "salary": 80000, "password": "secret123"}
        result = sanitize_for_logging(data)
        assert result["name"] == "Alice"
        assert result["salary"] == "[REDACTED]"
        assert result["password"] == "[REDACTED]"

    def test_handles_nested_dicts(self):
        data = {"user": {"ssn": "123-45-6789", "name": "Bob"}}
        result = sanitize_for_logging(data)
        assert result["user"]["ssn"] == "[REDACTED]"
        assert result["user"]["name"] == "Bob"

    def test_handles_lists(self):
        data = {"items": [{"token": "abc"}, {"token": "def"}]}
        result = sanitize_for_logging(data)
        assert all(item["token"] == "[REDACTED]" for item in result["items"])

    def test_case_insensitive_fields(self):
        data = {"API_KEY": "key123"}
        result = sanitize_for_logging(data)
        assert result["API_KEY"] == "[REDACTED]"


# ── Sanitize User Input ─────────────────────────────────────────────────────


class TestSanitizeUserInput:
    def test_removes_control_chars(self):
        result = sanitize_user_input("Hello\x00World")
        assert "\x00" not in result

    def test_normalizes_whitespace(self):
        result = sanitize_user_input("  Hello   World  ")
        assert result == "Hello World"

    def test_truncates_long_input(self):
        result = sanitize_user_input("a" * 2000, max_length=100)
        assert len(result) <= 104  # 100 + "..."

    def test_empty_returns_empty(self):
        assert sanitize_user_input("") == ""
