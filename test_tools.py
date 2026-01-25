"""
Comprehensive test script for the HR Agent v2.0

Tests:
- All tool functions
- Policy engine authorization
- Conversation memory
- Response utilities
"""

import sys

sys.path.insert(0, "src")

from hr_agent.seed import seed_if_needed
from hr_agent.services import tools
from hr_agent.core.agent import get_requester_context
from hr_agent.core.policy_engine import get_policy_engine, PolicyContext
from hr_agent.core.memory import get_memory_store
from hr_agent.core.response_utils import paginate, summarize_employees


def test_tools():
    """Test all tool functions."""
    print("=" * 70)
    print("🔧 TESTING TOOL FUNCTIONS")
    print("=" * 70)

    # Employee & Org Tools
    print("\n📋 Employee & Organization Tools")
    print("-" * 40)

    results = tools.search_employee("engineer")
    print(f"✅ search_employee: Found {len(results)} engineers")

    emp = tools.get_employee_basic(201)
    assert emp is not None, "Employee not found"
    print(f"✅ get_employee_basic: {emp['preferred_name']} - {emp['title']}")

    tenure = tools.get_employee_tenure(201)
    assert tenure is not None, "Tenure not found"
    print(f"✅ get_employee_tenure: {tenure['years_of_service']} years")

    mgr = tools.get_manager(201)
    assert mgr is not None, "Manager not found"
    print(f"✅ get_manager: {mgr['preferred_name']}")

    reports = tools.get_direct_reports(200)
    print(f"✅ get_direct_reports: {len(reports)} reports")

    chain = tools.get_manager_chain(201)
    print(f"✅ get_manager_chain: {len(chain)} levels")

    overview = tools.get_team_overview(200)
    print(f"✅ get_team_overview: {overview['total_direct_reports']} members")

    directory = tools.get_department_directory("Engineering")
    print(f"✅ get_department_directory: {len(directory)} in Engineering")

    org = tools.get_org_chart(max_depth=2)
    print(f"✅ get_org_chart: Root is {org.get('preferred_name', 'N/A')}")

    # Holiday Tools
    print("\n🏖️ Holiday & Time-Off Tools")
    print("-" * 40)

    balance = tools.get_holiday_balance(201, 2026)
    print(f"✅ get_holiday_balance: {balance['remaining']} days remaining")

    requests = tools.get_holiday_requests(201, 2026)
    print(f"✅ get_holiday_requests: {len(requests)} requests")

    approvals = tools.get_pending_approvals(200)
    print(f"✅ get_pending_approvals: {len(approvals)} pending")

    calendar = tools.get_team_calendar(200, 2026)
    print(f"✅ get_team_calendar: {len(calendar)} approved")

    # Compensation Tools
    print("\n💰 Compensation Tools")
    print("-" * 40)

    comp = tools.get_compensation(201)
    assert comp is not None, "Compensation not found"
    print(f"✅ get_compensation: {comp['currency']} {comp['base_salary']}")

    history = tools.get_salary_history(201)
    print(f"✅ get_salary_history: {len(history)} records")

    summary = tools.get_team_compensation_summary(200)
    print(f"✅ get_team_compensation_summary: {summary['team_size']} members")

    # Company Info Tools
    print("\n📢 Company Info Tools")
    print("-" * 40)

    policies = tools.get_company_policies()
    print(f"✅ get_company_policies: {len(policies)} policies")

    if policies:
        policy = tools.get_policy_details(policies[0]["policy_id"])
        if policy:
            print(f"✅ get_policy_details: {policy['title']}")

    holidays = tools.get_company_holidays(2026)
    print(f"✅ get_company_holidays: {len(holidays)} holidays")

    announcements = tools.get_announcements()
    print(f"✅ get_announcements: {len(announcements)} announcements")

    events = tools.get_upcoming_events()
    print(f"✅ get_upcoming_events: {len(events)} events")


def test_policy_engine():
    """Test the policy-as-code authorization engine."""
    print("\n" + "=" * 70)
    print("🔐 TESTING POLICY ENGINE")
    print("=" * 70)

    engine = get_policy_engine()

    # Test cases
    tests = [
        {
            "name": "Employee viewing own compensation",
            "context": PolicyContext(
                requester_id=201,
                requester_email="alex.kim@acme.com",
                requester_role="EMPLOYEE",
                target_id=201,
                action="get_compensation",
            ),
            "expected": True,
        },
        {
            "name": "Employee viewing other's compensation",
            "context": PolicyContext(
                requester_id=201,
                requester_email="alex.kim@acme.com",
                requester_role="EMPLOYEE",
                target_id=202,
                action="get_compensation",
            ),
            "expected": False,
        },
        {
            "name": "HR viewing any compensation",
            "context": PolicyContext(
                requester_id=204,
                requester_email="mina.patel@acme.com",
                requester_role="HR",
                target_id=201,
                action="get_compensation",
            ),
            "expected": True,
        },
        {
            "name": "Manager viewing direct report info",
            "context": PolicyContext(
                requester_id=200,
                requester_email="sam.nguyen@acme.com",
                requester_role="MANAGER",
                target_id=201,
                action="get_employee_basic",
            ),
            "expected": True,
        },
        {
            "name": "Employee viewing company policies",
            "context": PolicyContext(
                requester_id=201,
                requester_email="alex.kim@acme.com",
                requester_role="EMPLOYEE",
                target_id=None,
                action="get_company_policies",
            ),
            "expected": True,
        },
    ]

    for test in tests:
        result = engine.is_allowed(test["context"])
        status = "✅" if result == test["expected"] else "❌"
        print(f"{status} {test['name']}: {result}")


def test_memory():
    """Test conversation memory."""
    print("\n" + "=" * 70)
    print("🧠 TESTING CONVERSATION MEMORY")
    print("=" * 70)

    store = get_memory_store()
    session = store.get_or_create_session("test-123", "alex.kim@acme.com")

    session.add_turn("user", "Who is my manager?")
    session.add_turn("assistant", "Your manager is Sam Nguyen.")
    session.add_turn("user", "What is their email?")

    print(f"✅ Created session with {len(session.turns)} turns")
    print(f"✅ Recent messages: {len(session.get_messages_for_llm())} messages")

    session.set_pending_confirmation(
        "submit_holiday", {"days": 5}, "Confirm 5 days off?"
    )
    print(f"✅ Pending confirmation: {session.has_pending_confirmation()}")

    session.clear_pending_confirmation()
    print(f"✅ Cleared confirmation: {not session.has_pending_confirmation()}")

    store.delete_session("test-123")
    print("✅ Session deleted")


def test_response_utils():
    """Test response summarization utilities."""
    print("\n" + "=" * 70)
    print("📊 TESTING RESPONSE UTILITIES")
    print("=" * 70)

    # Test pagination
    items = list(range(100))
    page1 = paginate(items, page=1, page_size=10)
    print(
        f"✅ Pagination: Page 1 has {len(page1.items)} items, total {page1.total_count}"
    )
    print(f"   Has more: {page1.has_more}, Total pages: {page1.total_pages}")

    # Test employee summarization
    employees = [
        {"employee_id": i, "preferred_name": f"Employee {i}", "title": "Engineer"}
        for i in range(20)
    ]
    summary = summarize_employees(employees, max_items=5)
    print(
        f"✅ Employee summary: {summary['count']} total, showing {summary.get('shown', summary['count'])}"
    )


def test_requester_context():
    """Test requester context retrieval."""
    print("\n" + "=" * 70)
    print("👤 TESTING REQUESTER CONTEXT")
    print("=" * 70)

    users = [
        ("alex.kim@acme.com", "EMPLOYEE"),
        ("sam.nguyen@acme.com", "MANAGER"),
        ("mina.patel@acme.com", "HR"),
    ]

    for email, expected_role in users:
        ctx = get_requester_context(email)
        status = "✅" if ctx["role"] == expected_role else "❌"
        print(
            f"{status} {email}: ID={ctx['employee_id']}, Role={ctx['role']}, Reports={len(ctx['direct_reports'])}"
        )


def main():
    print("\n" + "=" * 70)
    print("HR AGENT v2.0 - COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    # Seed database
    print("\n📦 Seeding database...")
    seed_if_needed()
    print("✅ Database ready!")

    # Run all tests
    test_tools()
    test_policy_engine()
    test_memory()
    test_response_utils()
    test_requester_context()

    print("\n" + "=" * 70)
    print("✅ ALL TESTS COMPLETED!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
