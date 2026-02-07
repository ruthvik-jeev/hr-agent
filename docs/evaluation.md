# HR Agent Evaluation Framework

> Comprehensive testing methodology for LLM agent quality, authorization correctness, and tool selection accuracy.

## Table of Contents

- [Overview](#overview)
- [Running Evaluations](#running-evaluations)
- [Test Categories](#test-categories)
- [Metrics](#metrics)
- [Sample Test Cases](#sample-test-cases)
- [Interpreting Results](#interpreting-results)

---

## Overview

The HR Agent evaluation framework tests:

1. **Tool Selection**: Does the agent choose the correct tools?
2. **Authorization**: Does the policy engine enforce rules correctly?
3. **Answer Quality**: Are responses accurate and helpful?
4. **Edge Cases**: How does the agent handle ambiguous or invalid requests?

### Evaluation Philosophy

- **Deterministic where possible**: Authorization and tool selection are deterministic
- **LLM-judged where needed**: Answer quality uses GPT-4 as a judge
- **Real-world scenarios**: Test cases based on actual HR workflows

---

## Running Evaluations

### Quick Start

```bash
# Run 10 quick test cases
uv run python evals/runners/run_evals.py --quick --verbose

# Run full evaluation suite (40+ cases)
uv run python evals/runners/run_evals.py

# Filter by category
uv run python evals/runners/run_evals.py --category time_off
uv run python evals/runners/run_evals.py --category authorization

# Save results to file
uv run python evals/runners/run_evals.py --output results.json
```

### Using deepeval (Alternative)

```bash
# Run with deepeval framework
uv run python evals/deepeval_runner.py
```

### Langfuse Tracing for Evals

If Langfuse is enabled, eval runs are tagged with metadata so you can filter them easily.

Example filters:
- `run_type=eval`
- `eval_dataset=default` (or your dataset name)
- `eval_case_id=time_off_001`
- `eval_category=time_off`
- `eval_difficulty=easy`

### Langfuse Dashboard (Eval Metrics)

To build a dashboard in Langfuse using the eval scores, use the **Scores** view and add these filters:

- `name` starts with `eval_`
- `metadata.eval_dataset = <your dataset name>`
- (optional) `metadata.run_type = eval`

Recommended charts:

- **Pass rate**: `eval_pass` → AVG
- **Tool selection**: `eval_tool_selection` → AVG
- **Answer quality**: `eval_answer_quality` → AVG
- **Authorization**: `eval_authorization` → AVG
- **Latency**: `eval_latency_ms` → P50/P95
- **Steps**: `eval_steps` → AVG

Save the dashboard as **HR Agent Eval Metrics** for reuse.

---

## Test Categories

### 1. Employee Information (`category: employee_info`)

**Purpose**: Test basic employee lookup and profile retrieval.

**Example Cases**:
- "Who is Alex Kim?"
- "What department does Sarah Chen work in?"
- "How long has Jordan Taylor been with the company?"

**Expected Behavior**:
- ✅ Uses `search_employee` to find by name
- ✅ Uses `get_employee_basic` for profile details
- ✅ Uses `get_employee_tenure` for service duration
- ✅ Returns accurate info from database

---

### 2. Time Off Management (`category: time_off`)

**Purpose**: Test holiday request submission, balance checking, and approvals.

**Example Cases**:
- "What's my holiday balance?" (self-access)
- "Submit a holiday request for Dec 20-27" (action execution)
- "Approve request #123" (manager action)
- "Show me my team's upcoming time off" (manager view)

**Expected Behavior**:
- ✅ Self-access to own balance allowed
- ✅ Cross-user balance denied (unless manager)
- ✅ Manager can approve direct reports only
- ✅ Validates date ranges and balance availability

---

### 3. Authorization (`category: authorization`)

**Purpose**: Verify policy enforcement across all access patterns.

**Test Scenarios**:

| Scenario | Requester | Target | Action | Expected |
|----------|-----------|--------|--------|----------|
| Self-view salary | Employee (ID=1) | Self (ID=1) | `get_compensation` | ✅ Allow |
| Cross-view salary | Employee (ID=1) | Other (ID=2) | `get_compensation` | ❌ Deny |
| HR view salary | HR (ID=10) | Any | `get_compensation` | ✅ Allow |
| Manager approve | Manager | Direct report | `approve_holiday_request` | ✅ Allow |
| Manager approve | Manager | Non-report | `approve_holiday_request` | ❌ Deny |
| Company holidays | Anyone | None | `get_company_holidays` | ✅ Allow |

**Implementation**:
```python
def test_authorization():
    engine = PolicyEngine()

    # Test: Employee cannot view other's salary
    ctx = PolicyContext(
        requester_id=1,
        requester_email="alex@acme.com",
        requester_role="EMPLOYEE",
        target_id=2,
        action="get_compensation",
    )
    result = engine.is_allowed(ctx)
    assert result is False, "Cross-user salary access should be denied"
```

---

### 4. Organization Structure (`category: org_structure`)

**Purpose**: Test org chart navigation and hierarchy queries.

**Example Cases**:
- "Who is my manager?"
- "Show me the org chart for Engineering"
- "Who are Jordan's direct reports?"

**Expected Behavior**:
- ✅ Uses `get_manager` for manager lookup
- ✅ Uses `get_direct_reports` for subordinates
- ✅ Uses `get_org_chart` for department hierarchy
- ✅ Handles circular references gracefully

---

### 5. Compensation (`category: compensation`)

**Purpose**: Test salary info access with strict authorization.

**Example Cases**:
- "What's my salary?" (self-access)
- "Show me Sarah's compensation history" (HR only)
- "Get team compensation summary" (HR only)

**Expected Behavior**:
- ✅ Self-access always allowed
- ✅ HR can view anyone's compensation
- ✅ Managers cannot view direct report salaries (unless policy changed)
- ❌ Regular employees blocked from cross-user access

---

### 6. Edge Cases (`category: edge_cases`)

**Purpose**: Test error handling and ambiguous requests.

**Example Cases**:
- "Submit holiday for invalid dates" → Error handling
- "Who is XYZ?" (non-existent employee) → Graceful "not found"
- "Approve request #999" (non-existent) → Error message
- "What's the weather?" (off-topic) → Polite decline

**Expected Behavior**:
- ✅ Validates input parameters
- ✅ Returns helpful error messages
- ✅ Doesn't hallucinate data
- ✅ Stays in domain (HR topics only)

---

## Metrics

### 1. Tool Selection Accuracy

**Formula**: `(Correct tools selected) / (Total test cases) × 100%`

**Scoring**:
- ✅ **Correct**: Agent selects expected tool(s)
- ❌ **Incorrect**: Agent selects wrong tool or no tool

**Example**:
```python
{
    "query": "What's my holiday balance?",
    "expected_tools": ["get_holiday_balance"],
    "actual_tools": ["get_holiday_balance"],
    "correct": True
}
```

### 2. Authorization Correctness

**Formula**: `(Correct allow/deny decisions) / (Total auth checks) × 100%`

**Scoring**:
- ✅ **Correct**: Policy decision matches expected outcome
- ❌ **Incorrect**: Allowed when should deny, or vice versa

**Target**: **100%** (deterministic, must be perfect)

### 3. Answer Quality

**Formula**: LLM-as-judge scoring on 1-5 scale

**Criteria**:
- **Accuracy**: Does answer match ground truth?
- **Completeness**: All relevant info included?
- **Clarity**: Easy to understand?
- **Helpfulness**: Actionable information?

**Scoring**:
```python
{
    "query": "What's my holiday balance?",
    "response": "You have 15 vacation days remaining for 2024.",
    "ground_truth": "15 days",
    "score": 5,  # Perfect match
    "explanation": "Accurate, complete, and clear"
}
```

### 4. Overall Pass Rate

**Formula**: `(Passed tests) / (Total tests) × 100%`

**Pass Criteria**:
- Tool selection: Correct
- Authorization: Correct (if applicable)
- Answer quality: Score ≥ 4

**Target**: ≥ **95%** pass rate

---

## Sample Test Cases

### Test Case 1: Self Holiday Balance

```yaml
id: "time_off_001"
category: "time_off"
query: "What's my holiday balance for 2024?"
user_email: "alex.kim@acme.com"
expected:
  tools: ["get_holiday_balance"]
  authorization: "allowed"
  answer_contains: ["15", "days", "2024"]
ground_truth: "15 vacation days remaining"
```

**Expected Flow**:
1. Agent calls `get_holiday_balance(employee_id=1, year=2024)`
2. Policy check: `is_self` → ✅ Allowed
3. Tool returns: `{"entitlement": 25, "used": 10, "remaining": 15}`
4. Agent responds: "You have 15 vacation days remaining for 2024."

---

### Test Case 2: Cross-User Salary Access (Deny)

```yaml
id: "auth_002"
category: "authorization"
query: "What's Sarah Chen's salary?"
user_email: "alex.kim@acme.com"  # Regular employee
expected:
  tools: ["get_compensation"]
  authorization: "denied"
  answer_contains: ["cannot", "permission", "access"]
ground_truth: "Access denied (not self, not HR)"
```

**Expected Flow**:
1. Agent calls `get_compensation(employee_id=2)`  # Sarah's ID
2. Policy check: `is_self` → False, `is_hr` → False → ❌ Denied
3. Agent responds: "I don't have permission to access other employees' compensation information."

---

### Test Case 3: Manager Approve Direct Report

```yaml
id: "time_off_005"
category: "time_off"
query: "Approve holiday request #42"
user_email: "jordan.taylor@acme.com"  # Manager
expected:
  tools: ["approve_holiday_request"]
  authorization: "allowed"
  answer_contains: ["approved", "request", "42"]
ground_truth: "Request approved successfully"
```

**Expected Flow**:
1. Agent calls `approve_holiday_request(request_id=42)`
2. Policy check: `is_manager and is_direct_report` → ✅ Allowed
3. Tool updates database
4. Agent responds: "Holiday request #42 has been approved."

---

## Interpreting Results

### Sample Output

```
======================================================================
  📊 EVALUATION RESULTS
======================================================================
  Total Cases:      40
  Passed:           38 / 40
  Pass Rate:        95.0%

  Accuracy Metrics
  ----------------------------------------
  Tool Selection     97.5%  (39/40)
  Answer Quality     95.0%  (38/40)
  Authorization      100.0% (40/40)

  Failed Cases
  ----------------------------------------
  - employee_info_008: Selected wrong tool (get_employee_basic instead of search_employee)
  - edge_case_003: Answer quality score 3/5 (incomplete response)
======================================================================
```

### What Good Looks Like

| Metric | Minimum | Target | Excellent |
|--------|---------|--------|-----------|
| **Tool Selection** | 90% | 95% | 98% |
| **Authorization** | 100% | 100% | 100% |
| **Answer Quality** | 85% | 90% | 95% |
| **Overall Pass Rate** | 90% | 95% | 98% |

---

## Debugging Failed Tests

### 1. Tool Selection Failure

**Symptom**: Agent selects wrong tool

**Debugging**:
```bash
# Run with verbose logging
uv run python evals/runners/run_evals.py --verbose --case employee_info_008
```

**Common Causes**:
- Ambiguous query wording
- Tool description unclear
- Multiple valid tools (need to pick best one)

**Fix**: Improve tool descriptions or system prompt

---

### 2. Authorization Failure

**Symptom**: Incorrect allow/deny decision

**Debugging**:
```python
# Test policy directly
from hr_agent.policies.policy_engine import PolicyEngine, PolicyContext

engine = PolicyEngine()
ctx = PolicyContext(
    requester_id=1,
    requester_email="alex@acme.com",
    requester_role="EMPLOYEE",
    target_id=2,
    action="get_compensation",
)
result = engine.is_allowed(ctx)
print(f"Decision: {result}")
```

**Common Causes**:
- Missing rule in `policies.yaml`
- Wrong condition evaluation
- Action not in rule's `actions` list

**Fix**: Add/update YAML rules

---

### 3. Answer Quality Failure

**Symptom**: LLM response score < 4

**Debugging**:
```bash
# Check actual response
uv run python evals/runners/run_evals.py --verbose --case time_off_003
```

**Common Causes**:
- Tool returned incomplete data
- LLM hallucinated details
- Response too verbose or too brief

**Fix**: Improve system prompt or tool output format

---

## Adding New Test Cases

### Step 1: Define Test Case

```python
# evals/test_cases.py

TEST_CASES = [
    {
        "id": "custom_001",
        "category": "time_off",
        "query": "Cancel my holiday request for next week",
        "user_email": "alex.kim@acme.com",
        "expected": {
            "tools": ["cancel_holiday_request"],
            "authorization": "allowed",
            "answer_contains": ["cancelled", "request"]
        },
        "ground_truth": "Holiday request cancelled successfully"
    }
]
```

### Step 2: Run Evaluation

```bash
uv run python evals/runners/run_evals.py --case custom_001 --verbose
```

### Step 3: Review Results

```
Test: custom_001
  Tool Selection: ✅ PASS (selected cancel_holiday_request)
  Authorization:  ✅ PASS (allowed)
  Answer Quality: ✅ PASS (score: 5/5)

Overall: ✅ PASSED
```

---

## Continuous Integration

### GitHub Actions Example

```yaml
name: Evaluations
on: [push, pull_request]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: astral-sh/setup-uv@v1
      - run: uv sync
      - run: uv run python evals/runners/run_evals.py --output results.json
        env:
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
      - run: |
          pass_rate=$(jq '.pass_rate' results.json)
          if [ $(echo "$pass_rate < 95" | bc) -eq 1 ]; then
            echo "Pass rate below 95%: $pass_rate"
            exit 1
          fi
```

---

## Best Practices

1. **Test Real Scenarios**: Base cases on actual user queries
2. **Cover All Roles**: Test as employee, manager, HR, finance
3. **Test Boundaries**: Edge cases reveal the most bugs
4. **Automate**: Run evals in CI/CD pipeline
5. **Track Over Time**: Monitor pass rate trends
6. **Update Regularly**: Add new cases as features are added

---

## References

- [LangChain Evaluation Guide](https://python.langchain.com/docs/guides/evaluation/)
- [DeepEval Documentation](https://docs.confident-ai.com/)
- [LLM-as-Judge Paper](https://arxiv.org/abs/2306.05685)
