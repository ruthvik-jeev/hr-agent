"""
Response Summarization and Pagination

Utilities for summarizing large tool responses and handling pagination
to avoid overwhelming the LLM context window.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class PaginatedResult:
    """A paginated result set."""

    items: list[Any]
    total_count: int
    page: int
    page_size: int
    has_more: bool

    @property
    def total_pages(self) -> int:
        return (self.total_count + self.page_size - 1) // self.page_size

    def to_dict(self) -> dict:
        return {
            "items": self.items,
            "total_count": self.total_count,
            "page": self.page,
            "page_size": self.page_size,
            "has_more": self.has_more,
            "total_pages": self.total_pages,
        }


def paginate(items: list[Any], page: int = 1, page_size: int = 10) -> PaginatedResult:
    """Paginate a list of items."""
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]

    return PaginatedResult(
        items=page_items,
        total_count=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
    )


# ========== RESPONSE SUMMARIZERS ==========


def summarize_employees(employees: list[dict], max_items: int = 5) -> dict:
    """Summarize a list of employees for LLM consumption."""
    total = len(employees)

    if total == 0:
        return {"summary": "No employees found.", "count": 0}

    if total == 1:
        emp = employees[0]
        return {
            "summary": f"Found 1 employee: {emp.get('preferred_name', 'Unknown')} ({emp.get('title', 'Unknown title')})",
            "count": 1,
            "employees": employees,
        }

    # Show first few, summarize rest
    shown = employees[:max_items]
    names = [e.get("preferred_name", "Unknown") for e in shown]

    if total <= max_items:
        return {
            "summary": f"Found {total} employees: {', '.join(names)}",
            "count": total,
            "employees": employees,
        }

    return {
        "summary": f"Found {total} employees. Showing first {max_items}: {', '.join(names)}. Use pagination to see more.",
        "count": total,
        "shown": max_items,
        "employees": shown,
        "has_more": True,
    }


def summarize_holiday_requests(requests: list[dict]) -> dict:
    """Summarize holiday requests."""
    if not requests:
        return {"summary": "No holiday requests found.", "count": 0}

    by_status = {}
    total_days = 0
    for req in requests:
        status = req.get("status", "UNKNOWN")
        by_status[status] = by_status.get(status, 0) + 1
        if status in ("APPROVED", "PENDING"):
            total_days += req.get("days", 0)

    status_str = ", ".join(f"{v} {k.lower()}" for k, v in by_status.items())

    return {
        "summary": f"Found {len(requests)} requests ({status_str}). Total days: {total_days}",
        "count": len(requests),
        "by_status": by_status,
        "total_days_booked": total_days,
        "requests": requests,
    }


def summarize_compensation(comp: dict) -> dict:
    """Summarize compensation data (with masking option)."""
    if not comp:
        return {"summary": "No compensation data available."}

    return {
        "summary": f"Base salary: {comp.get('currency', 'USD')} {comp.get('base_salary', 0):,.2f}, "
        f"Bonus target: {comp.get('bonus_target_pct', 0)}%, "
        f"Total target comp: {comp.get('currency', 'USD')} {comp.get('total_target_compensation', 0):,.2f}",
        "data": comp,
    }


def summarize_team_overview(overview: dict) -> dict:
    """Summarize a team overview."""
    if "error" in overview:
        return overview

    manager = overview.get("manager", {})
    total = overview.get("total_direct_reports", 0)
    by_dept = overview.get("by_department", {})

    dept_summary = ", ".join(f"{len(v)} in {k}" for k, v in by_dept.items())

    return {
        "summary": f"Manager: {manager.get('preferred_name', 'Unknown')} has {total} direct reports ({dept_summary})",
        "data": overview,
    }


def summarize_org_chart(org: dict, _depth: int = 0) -> dict:
    """Summarize an org chart (limit depth for context)."""
    if not org:
        return {"summary": "No org chart data."}

    def count_nodes(node: dict) -> int:
        count = 1
        for child in node.get("direct_reports", []):
            count += count_nodes(child)
        return count

    total_nodes = count_nodes(org)
    root_name = org.get("preferred_name", "Unknown")

    return {
        "summary": f"Org chart starting from {root_name} with {total_nodes} total employees",
        "root": root_name,
        "total_employees": total_nodes,
        "data": org,
    }


# ========== TOKEN ESTIMATION ==========


def estimate_tokens(obj: Any) -> int:
    """Estimate the number of tokens in an object (rough approximation)."""
    import json

    try:
        text = json.dumps(obj)
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4
    except (TypeError, ValueError):
        return 0


def should_summarize(obj: Any, token_limit: int = 1000) -> bool:
    """Check if an object should be summarized based on estimated tokens."""
    return estimate_tokens(obj) > token_limit


# ========== SMART RESPONSE HANDLER ==========


def prepare_tool_response(tool_name: str, result: Any, token_limit: int = 1500) -> dict:
    """
    Prepare a tool response for the LLM, summarizing if necessary.

    Returns a response with a 'summary' field for the LLM and optionally
    truncated 'data' to fit within token limits.
    """
    if isinstance(result, dict) and "error" in result:
        return result

    # Route to appropriate summarizer
    summarizers = {
        "search_employee": lambda r: summarize_employees(r.get("results", [])),
        "get_direct_reports": lambda r: summarize_employees(
            r.get("direct_reports", [])
        ),
        "get_department_directory": lambda r: summarize_employees(
            r.get("employees", []) if isinstance(r, dict) else r
        ),
        "get_holiday_requests": lambda r: summarize_holiday_requests(
            r.get("requests", [])
        ),
        "get_compensation": summarize_compensation,
        "get_team_overview": summarize_team_overview,
        "get_org_chart": summarize_org_chart,
    }

    if tool_name in summarizers and should_summarize(result, token_limit):
        try:
            return summarizers[tool_name](result)
        except (KeyError, TypeError):
            pass  # Fall through to default handling

    # Check if we need to truncate
    if should_summarize(result, token_limit):
        return {
            "summary": f"Result contains {estimate_tokens(result)} estimated tokens. Data may be truncated.",
            "data": result,
            "truncated": True,
        }

    return result
