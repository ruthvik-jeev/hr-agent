"""
Policy-as-Code Authorization Engine

A flexible, rule-based authorization system inspired by Open Policy Agent (OPA).
Policies are defined declaratively and can be updated without code changes.
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any
from ..infrastructure.db import get_engine
from sqlalchemy import text


class Effect(Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class PolicyContext:
    """Context for policy evaluation."""

    requester_id: int
    requester_email: str
    requester_role: str
    target_id: int | None = None
    action: str = ""
    resource_type: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class PolicyRule:
    """A single policy rule."""

    name: str
    description: str
    effect: Effect
    condition: Callable[[dict[str, Any]], bool]
    priority: int = 0  # Higher priority rules are evaluated first


@dataclass
class PolicyResult:
    """Result of policy evaluation."""

    allowed: bool
    reason: str
    matched_rule: str | None = None
    requires_confirmation: bool = False
    confirmation_message: str | None = None


class PolicyEngine:
    """
    A policy engine that evaluates authorization rules.

    Rules are evaluated in priority order. The first matching rule determines the outcome.
    If no rules match, the default is DENY.
    """

    def __init__(self, policy_file: Path | None = None):
        self.rules: list[PolicyRule] = []
        self._helpers = {
            "is_direct_report": _is_direct_report,
            "finance_has_cost_center_access": _finance_has_cost_center_access,
        }
        if policy_file is None:
            policy_file = Path(__file__).parent.parent / "policies" / "policies.yaml"
        self._load_rules_from_yaml(policy_file)

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a rule to the policy engine."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: -r.priority)  # Higher priority first

    def is_allowed(self, context: PolicyContext) -> bool:
        """Evaluate all rules against the context."""
        eval_context = {"ctx": context, "helpers": self._helpers}
        for rule in self.rules:
            try:
                result = rule.condition(eval_context)
                if result:
                    return rule.effect == Effect.ALLOW
            except Exception:
                continue  # Skip rules that error

        return False

    def _load_rules_from_yaml(self, policy_file: Path):
        """Load policy rules from a YAML file."""
        try:
            with open(policy_file, "r") as f:
                policy_data = yaml.safe_load(f)
        except (IOError, yaml.YAMLError) as e:
            # In a real app, you'd want more robust error handling/logging
            print(f"Error loading policy file {policy_file}: {e}")
            return

        for rule_data in policy_data.get("rules", []):
            # Create a callable condition from the string expression
            condition_str = rule_data["condition"]

            def make_condition(expr: str):
                """Create a condition function from a string expression."""

                def condition_func(eval_ctx):
                    return eval(expr, {"__builtins__": {}}, eval_ctx)

                return condition_func

            rule = PolicyRule(
                name=rule_data["name"],
                description=rule_data["description"],
                effect=Effect(rule_data["effect"]),
                priority=rule_data.get("priority", 0),
                condition=make_condition(condition_str),
            )
            self.add_rule(rule)


# ========== HELPER FUNCTIONS FOR POLICY CONDITIONS ==========


def _is_direct_report(manager_id: int, employee_id: int | None) -> bool:
    """Check if employee is a direct report of manager."""
    if employee_id is None:
        return False
    eng = get_engine()
    with eng.begin() as con:
        result = con.execute(
            text(
                """SELECT 1 FROM manager_reports
                    WHERE manager_employee_id = :m AND report_employee_id = :e"""
            ),
            {"m": manager_id, "e": employee_id},
        ).scalar_one_or_none()
        return result is not None


def _finance_has_cost_center_access(user_email: str, employee_id: int | None) -> bool:
    """Check if finance user has access to employee's cost center."""
    if employee_id is None:
        return True  # Allow if no specific target
    eng = get_engine()
    with eng.begin() as con:
        cost_center = con.execute(
            text("SELECT cost_center FROM employee WHERE employee_id = :e"),
            {"e": employee_id},
        ).scalar_one_or_none()

        if not cost_center:
            return False

        result = con.execute(
            text(
                """SELECT 1 FROM finance_cost_center_access
                    WHERE user_email = :u AND cost_center = :cc"""
            ),
            {"u": user_email, "cc": cost_center},
        ).scalar_one_or_none()
        return result is not None


# ========== CONFIRMATION REQUIREMENTS ==========

ACTIONS_REQUIRING_CONFIRMATION = {
    "submit_holiday_request": "You're about to submit a holiday request for {days} days from {start_date} to {end_date}. Please confirm.",
    "cancel_holiday_request": "You're about to cancel holiday request #{request_id}. This action cannot be undone. Please confirm.",
    "approve_holiday_request": "You're about to approve holiday request #{request_id}. Please confirm.",
    "reject_holiday_request": "You're about to reject holiday request #{request_id}. Please confirm.",
}


def requires_confirmation(action: str) -> bool:
    """Check if an action requires user confirmation."""
    return action in ACTIONS_REQUIRING_CONFIRMATION


def get_confirmation_message(action: str, params: dict) -> str:
    """Get the confirmation message for an action."""
    template = ACTIONS_REQUIRING_CONFIRMATION.get(action, "Please confirm this action.")
    try:
        return template.format(**params)
    except KeyError:
        return template


# ========== SINGLETON INSTANCE ==========
_policy_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    """Get the singleton policy engine instance."""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine
