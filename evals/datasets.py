"""
Evaluation Datasets

Comprehensive test cases for evaluating the HR agent across all capabilities.
Each case defines:
- The user context (who is asking)
- The query
- Expected tools to be called
- Expected content in the answer
- Whether authorization should allow/deny
"""

from dataclasses import dataclass, field
from .metrics import EvalCategory, EvalDifficulty


@dataclass
class EvalCase:
    """A single evaluation test case."""

    id: str
    category: EvalCategory
    difficulty: EvalDifficulty
    user_email: str
    query: str
    expected_tools: list[str]
    expected_answer_contains: list[str]
    expected_answer_not_contains: list[str] = field(default_factory=list)
    should_be_denied: bool = False  # For authorization tests
    description: str = ""
    # New: Allow multiple acceptable tool patterns
    alternate_tools: list[list[str]] = field(default_factory=list)
    # New: Allow flexible answer matching (any of these patterns)
    alternate_answer_contains: list[list[str]] = field(default_factory=list)


@dataclass
class EvalDataset:
    """Collection of evaluation cases."""

    name: str
    cases: list[EvalCase]

    def filter_by_category(self, category: EvalCategory) -> "EvalDataset":
        return EvalDataset(
            name=f"{self.name}_{category.value}",
            cases=[c for c in self.cases if c.category == category],
        )

    def filter_by_difficulty(self, difficulty: EvalDifficulty) -> "EvalDataset":
        return EvalDataset(
            name=f"{self.name}_{difficulty.value}",
            cases=[c for c in self.cases if c.difficulty == difficulty],
        )


# ============================================================================
# TEST USERS
# ============================================================================
# alex.kim@acme.com - Regular employee (ID: 201)
# sam.nguyen@acme.com - Manager with direct reports (ID: 200)
# mina.patel@acme.com - HR with full access (ID: 110)


# ============================================================================
# EVALUATION CASES
# ============================================================================

HR_EVAL_CASES = [
    # =========================================================================
    # EMPLOYEE INFO - Basic employee lookups
    # =========================================================================
    EvalCase(
        id="emp_001",
        category=EvalCategory.EMPLOYEE_INFO,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="What is my job title?",
        expected_tools=["get_employee_basic"],
        expected_answer_contains=["Software Engineer"],
        description="Self info - job title",
    ),
    EvalCase(
        id="emp_002",
        category=EvalCategory.EMPLOYEE_INFO,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="When did I join the company?",
        expected_tools=["get_employee_tenure"],
        expected_answer_contains=["202"],  # hire date contains 202x year
        description="Self info - hire date",
    ),
    EvalCase(
        id="emp_003",
        category=EvalCategory.EMPLOYEE_INFO,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="How long have I worked here?",
        expected_tools=["get_employee_tenure"],
        expected_answer_contains=["year"],
        description="Self info - tenure",
    ),
    EvalCase(
        id="emp_004",
        category=EvalCategory.EMPLOYEE_INFO,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="alex.kim@acme.com",
        query="Find Bob in the company",
        expected_tools=["search_employee"],
        alternate_tools=[
            ["get_department_directory"],
            ["get_employee_basic"],
        ],  # Alternative approaches
        expected_answer_contains=["Bob"],
        description="Search employee by name",
    ),
    EvalCase(
        id="emp_005",
        category=EvalCategory.EMPLOYEE_INFO,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="alex.kim@acme.com",
        query="Who works as a Product Manager?",
        expected_tools=["search_employee"],
        alternate_tools=[["get_department_directory"]],
        expected_answer_contains=["Product Manager"],
        description="Search employee by title",
    ),
    # =========================================================================
    # ORGANIZATION - Manager and team structure
    # =========================================================================
    EvalCase(
        id="org_001",
        category=EvalCategory.ORGANIZATION,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="Who is my manager?",
        expected_tools=["get_manager"],
        expected_answer_contains=["Sam"],
        description="Get own manager",
    ),
    EvalCase(
        id="org_002",
        category=EvalCategory.ORGANIZATION,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="alex.kim@acme.com",
        query="Show me the chain of command above me",
        expected_tools=["get_manager_chain"],
        expected_answer_contains=["Sam", "Jordan"],  # Manager and CEO
        description="Manager chain to CEO",
    ),
    EvalCase(
        id="org_003",
        category=EvalCategory.ORGANIZATION,
        difficulty=EvalDifficulty.EASY,
        user_email="sam.nguyen@acme.com",
        query="Who are my direct reports?",
        expected_tools=["get_direct_reports"],
        alternate_tools=[["get_team_overview"]],
        expected_answer_contains=["Alex"],
        description="Manager viewing direct reports",
    ),
    EvalCase(
        id="org_004",
        category=EvalCategory.ORGANIZATION,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="sam.nguyen@acme.com",
        query="Give me an overview of my team",
        expected_tools=["get_team_overview"],
        expected_answer_contains=["Engineering"],
        alternate_answer_contains=[["report"], ["team"], ["member"]],
        description="Team overview for manager",
    ),
    EvalCase(
        id="org_005",
        category=EvalCategory.ORGANIZATION,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="Who works in the Engineering department?",
        expected_tools=["get_department_directory"],
        expected_answer_contains=["Engineering"],
        description="Department directory",
    ),
    EvalCase(
        id="org_006",
        category=EvalCategory.ORGANIZATION,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="alex.kim@acme.com",
        query="Show me the org chart",
        expected_tools=["get_org_chart"],
        expected_answer_contains=[
            "org"
        ],  # More flexible - response mentions organization/org chart
        alternate_answer_contains=[["chart"], ["structure"], ["hierarchy"], ["report"]],
        description="Organization chart",
    ),
    # =========================================================================
    # TIME OFF - Holiday and PTO
    # =========================================================================
    EvalCase(
        id="pto_001",
        category=EvalCategory.TIME_OFF,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="How many vacation days do I have left?",
        expected_tools=["get_holiday_balance"],
        expected_answer_contains=["day"],
        alternate_answer_contains=[["remaining"], ["left"], ["balance"], ["available"]],
        description="PTO balance check",
    ),
    EvalCase(
        id="pto_002",
        category=EvalCategory.TIME_OFF,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="Show me my holiday requests for this year",
        expected_tools=["get_holiday_requests"],
        expected_answer_contains=["request"],
        alternate_answer_contains=[["vacation"], ["time off"], ["PTO"], ["no request"]],
        description="View own holiday requests",
    ),
    EvalCase(
        id="pto_003",
        category=EvalCategory.TIME_OFF,
        difficulty=EvalDifficulty.EASY,
        user_email="sam.nguyen@acme.com",
        query="Do I have any vacation requests to approve?",
        expected_tools=["get_pending_approvals"],
        expected_answer_contains=["pending"],
        alternate_answer_contains=[["no pending"], ["approve"], ["request"], ["team"]],
        description="Manager pending approvals",
    ),
    EvalCase(
        id="pto_004",
        category=EvalCategory.TIME_OFF,
        difficulty=EvalDifficulty.EASY,
        user_email="sam.nguyen@acme.com",
        query="Show me when my team is off this year",
        expected_tools=["get_team_calendar"],
        expected_answer_contains=["team"],
        alternate_answer_contains=[
            ["schedule"],
            ["time off"],
            ["vacation"],
            ["calendar"],
        ],
        description="Team calendar view",
    ),
    EvalCase(
        id="pto_005",
        category=EvalCategory.TIME_OFF,
        difficulty=EvalDifficulty.HARD,
        user_email="alex.kim@acme.com",
        query="I want to take March 10-14 off for vacation, that's 5 days",
        expected_tools=["submit_holiday_request"],
        alternate_tools=[
            ["get_holiday_balance"],
            ["get_holiday_requests"],
        ],  # Agent may check balance first
        expected_answer_contains=["March"],
        alternate_answer_contains=[
            ["request"],
            ["vacation"],
            ["submit"],
            ["confirm"],
            ["day"],
        ],
        description="Submit PTO request (confirmation flow)",
    ),
    # =========================================================================
    # COMPENSATION - Salary and pay
    # =========================================================================
    EvalCase(
        id="comp_001",
        category=EvalCategory.COMPENSATION,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="What is my salary?",
        expected_tools=["get_compensation"],
        expected_answer_contains=["EUR"],
        alternate_answer_contains=[["salary"], ["compensation"], ["annual"], ["year"]],
        description="View own salary",
    ),
    EvalCase(
        id="comp_002",
        category=EvalCategory.COMPENSATION,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="Show me my salary history",
        expected_tools=["get_salary_history"],
        expected_answer_contains=["history"],
        alternate_answer_contains=[["salary"], ["change"], ["previous"]],
        description="View own salary history",
    ),
    EvalCase(
        id="comp_003",
        category=EvalCategory.COMPENSATION,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="alex.kim@acme.com",
        query="What is my bonus target?",
        expected_tools=["get_compensation"],
        expected_answer_contains=["bonus"],
        alternate_answer_contains=[["target"], ["%"], ["percent"]],
        description="View bonus target",
    ),
    # =========================================================================
    # COMPANY INFO - Policies, holidays, announcements
    # =========================================================================
    EvalCase(
        id="info_001",
        category=EvalCategory.COMPANY_INFO,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="What company policies do we have?",
        expected_tools=["get_company_policies"],
        expected_answer_contains=["polic"],
        description="List company policies",
    ),
    EvalCase(
        id="info_002",
        category=EvalCategory.COMPANY_INFO,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="alex.kim@acme.com",
        query="What is the remote work policy?",
        expected_tools=["get_company_policies", "get_policy_details"],
        alternate_tools=[["get_company_policies"]],
        expected_answer_contains=["remote"],
        description="Specific policy details",
    ),
    EvalCase(
        id="info_003",
        category=EvalCategory.COMPANY_INFO,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="What are the company holidays this year?",
        expected_tools=["get_company_holidays"],
        expected_answer_contains=["holiday"],
        alternate_answer_contains=[["day"], ["off"]],
        description="Company holiday calendar",
    ),
    EvalCase(
        id="info_004",
        category=EvalCategory.COMPANY_INFO,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="Any recent company announcements?",
        expected_tools=["get_announcements"],
        expected_answer_contains=["announcement"],
        alternate_answer_contains=[["news"], ["update"]],
        description="Recent announcements",
    ),
    EvalCase(
        id="info_005",
        category=EvalCategory.COMPANY_INFO,
        difficulty=EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query="What events are coming up?",
        expected_tools=["get_upcoming_events"],
        expected_answer_contains=["event"],
        alternate_answer_contains=[["upcoming"], ["schedule"]],
        description="Upcoming events",
    ),
    # =========================================================================
    # AUTHORIZATION - Access control tests
    # =========================================================================
    EvalCase(
        id="auth_001",
        category=EvalCategory.AUTHORIZATION,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="alex.kim@acme.com",
        query="What is Sam's salary?",
        expected_tools=["search_employee", "get_compensation"],
        alternate_tools=[["get_compensation"], ["search_employee"]],
        expected_answer_contains=["HR"],  # Response should mention HR for authorization
        alternate_answer_contains=[
            ["denied"],
            ["permission"],
            ["authorized"],
            ["cannot"],
            ["not allowed"],
            ["sorry"],
            ["only"],
        ],
        expected_answer_not_contains=["80000"],  # Don't reveal the actual salary
        should_be_denied=True,
        description="Employee cannot view other's salary",
    ),
    EvalCase(
        id="auth_002",
        category=EvalCategory.AUTHORIZATION,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="mina.patel@acme.com",
        query="What is Alex's salary?",
        expected_tools=["search_employee", "get_compensation"],
        alternate_tools=[["get_compensation"]],
        expected_answer_contains=["EUR"],
        alternate_answer_contains=[["salary"], ["compensation"]],
        should_be_denied=False,
        description="HR can view anyone's salary",
    ),
    EvalCase(
        id="auth_003",
        category=EvalCategory.AUTHORIZATION,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="alex.kim@acme.com",
        query="Show me the team compensation summary",
        expected_tools=["get_team_compensation_summary"],
        alternate_tools=[["get_team_overview"], ["get_compensation"]],
        expected_answer_contains=["denied"],
        alternate_answer_contains=[
            ["access"],
            ["permission"],
            ["authorized"],
            ["cannot"],
            ["manager"],
            ["HR"],
        ],
        should_be_denied=True,
        description="Employee cannot view team compensation",
    ),
    EvalCase(
        id="auth_004",
        category=EvalCategory.AUTHORIZATION,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="mina.patel@acme.com",  # HR
        query="Show me salary history for Alex",
        expected_tools=["search_employee", "get_salary_history"],
        alternate_tools=[["get_salary_history"]],
        expected_answer_contains=["history"],
        alternate_answer_contains=[["salary"], ["Alex"]],
        should_be_denied=False,
        description="HR can view salary history",
    ),
    # =========================================================================
    # MULTI-TURN - Conversation context tests
    # =========================================================================
    EvalCase(
        id="multi_001",
        category=EvalCategory.MULTI_TURN,
        difficulty=EvalDifficulty.HARD,
        user_email="alex.kim@acme.com",
        query="Find Bob",  # First turn - search
        expected_tools=["search_employee"],
        alternate_tools=[["get_department_directory"]],
        expected_answer_contains=["Bob"],
        description="Multi-turn: Search (turn 1)",
    ),
    # =========================================================================
    # EDGE CASES - Unusual inputs and error handling
    # =========================================================================
    EvalCase(
        id="edge_001",
        category=EvalCategory.EDGE_CASES,
        difficulty=EvalDifficulty.HARD,
        user_email="alex.kim@acme.com",
        query="asdfghjkl",  # Gibberish
        expected_tools=[],  # Should handle gracefully
        expected_answer_contains=["understand"],
        alternate_answer_contains=[
            ["help"],
            ["rephrase"],
            ["clarify"],
            ["sorry"],
            ["not sure"],
            ["what"],
        ],
        description="Gibberish input",
    ),
    EvalCase(
        id="edge_002",
        category=EvalCategory.EDGE_CASES,
        difficulty=EvalDifficulty.HARD,
        user_email="alex.kim@acme.com",
        query="Find employee with ID 99999",  # Non-existent
        expected_tools=["get_employee_basic"],
        alternate_tools=[["search_employee"]],
        expected_answer_contains=["99999"],  # Should acknowledge the ID
        alternate_answer_contains=[
            ["not found"],
            ["no employee"],
            ["doesn't exist"],
            ["couldn't find"],
            ["can't"],
            ["invalid"],
            ["sorry"],
        ],
        description="Non-existent employee",
    ),
    EvalCase(
        id="edge_003",
        category=EvalCategory.EDGE_CASES,
        difficulty=EvalDifficulty.HARD,
        user_email="alex.kim@acme.com",
        query="What was my salary in 1990?",  # Invalid year
        expected_tools=["get_salary_history"],
        alternate_tools=[["get_compensation"]],
        expected_answer_contains=["no"],
        alternate_answer_contains=[
            ["history"],
            ["record"],
            ["before"],
            ["1990"],
            ["data"],
        ],
        description="Invalid date range",
    ),
    EvalCase(
        id="edge_004",
        category=EvalCategory.EDGE_CASES,
        difficulty=EvalDifficulty.MEDIUM,
        user_email="alex.kim@acme.com",
        query="",  # Empty query
        expected_tools=[],
        expected_answer_contains=["help"],
        alternate_answer_contains=[["assist"], ["what"], ["how can"]],
        description="Empty query",
    ),
]


def get_default_dataset() -> EvalDataset:
    """Get the default HR evaluation dataset."""
    return EvalDataset(name="hr_eval_v1", cases=HR_EVAL_CASES)


def get_quick_dataset() -> EvalDataset:
    """Get a smaller dataset for quick testing."""
    quick_cases = [c for c in HR_EVAL_CASES if c.difficulty == EvalDifficulty.EASY][:10]
    return EvalDataset(name="hr_eval_quick", cases=quick_cases)


def get_auth_dataset() -> EvalDataset:
    """Get authorization-focused test cases."""
    auth_cases = [c for c in HR_EVAL_CASES if c.category == EvalCategory.AUTHORIZATION]
    return EvalDataset(name="hr_eval_auth", cases=auth_cases)
