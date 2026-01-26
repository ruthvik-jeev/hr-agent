# Evaluation Framework

Comprehensive evaluation for the HR Agent.

## Quick Start

```bash
# Quick test (10 cases)
python run_evals.py --quick

# Full evaluation
python run_evals.py --verbose

# Compare agents
python compare_agents.py --save
```

## Metrics

| Metric | Target |
|--------|--------|
| Pass Rate | ≥90% |
| Tool Selection | ≥95% |
| Answer Accuracy | ≥90% |
| Authorization | 100% |

## Test Suites

| Suite | Focus | Cases |
|-------|-------|-------|
| Suite 1 | Basic functionality | 16 |
| Suite 2 | Advanced & edge cases | 16 |
| Suite 3 | Regression & robustness | 12 |

## Running Evaluations

```bash
# With LangGraph agent
python run_evals.py --langgraph --verbose

# Specific category
python run_evals.py --category auth
```

## Agent Comparison

```bash
python compare_agents.py --save
```

Sample output:
```
  Metric               Original    LangGraph    Winner
  Pass Rate               90.0%       100.0%    LangGraph
  Tool Selection         100.0%       100.0%    Tie
```

## Test Case Structure

```python
EvalCase(
    id="emp_001",
    query="What is my job title?",
    expected_tools=["get_employee_basic"],
    expected_answer_contains=["Software Engineer"],
)
```
