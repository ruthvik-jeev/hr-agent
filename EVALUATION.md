# Evaluation Framework

<div align="center">

![Tests](https://img.shields.io/badge/Test_Cases-40+-1e3a5f?style=for-the-badge)
![Pass Rate](https://img.shields.io/badge/Target-≥90%25-3d5a80?style=for-the-badge)
![Coverage](https://img.shields.io/badge/Categories-6-5c7999?style=for-the-badge)

**Comprehensive evaluation system for measuring accuracy, tool usage, and authorization compliance**

</div>

---

## 🚀 Quick Start

```bash
# Quick evaluation (10 cases, ~30 seconds)
python run_evals.py --quick --verbose

# Full evaluation
python run_evals.py --verbose

# Filter by category
python run_evals.py --category time_off
```

---

## 📊 Evaluation Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e8f4f8', 'primaryTextColor': '#1e3a5f', 'primaryBorderColor': '#1e3a5f', 'lineColor': '#3d5a80', 'secondaryColor': '#f0f4f8', 'tertiaryColor': '#f7f9fc', 'nodeTextColor': '#1e3a5f', 'textColor': '#1e3a5f'}}}%%

flowchart TB
    subgraph RUNNER["Evaluation Runner"]
        direction TB
        LOAD["Load Test Cases"]
        EXEC["Execute Agent"]
        SCORE["Score Results"]
        REPORT["Generate Report"]
        
        LOAD --> EXEC --> SCORE --> REPORT
    end
    
    subgraph METRICS["Metrics"]
        direction LR
        M1["Pass Rate"]
        M2["Tool Accuracy"]
        M3["Answer Quality"]
        M4["Authorization"]
        M5["Latency"]
    end
    
    subgraph CASES["Test Suites"]
        direction TB
        S1["Suite 1<br/>Basic (16)"]
        S2["Suite 2<br/>Advanced (16)"]
        S3["Suite 3<br/>Edge Cases (12)"]
    end
    
    CASES --> RUNNER
    RUNNER --> METRICS
    
    style RUNNER fill:#f0f4f8,stroke:#1e3a5f,stroke-width:2px,color:#1e3a5f
    style METRICS fill:#e8f4f8,stroke:#3d5a80,stroke-width:2px,color:#1e3a5f
    style CASES fill:#f7f9fc,stroke:#3d5a80,stroke-width:2px,color:#1e3a5f
```

---

## 📏 Evaluation Metrics

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e8f4f8', 'primaryTextColor': '#1e3a5f', 'primaryBorderColor': '#1e3a5f', 'secondaryColor': '#f0f4f8', 'tertiaryColor': '#f7f9fc', 'pie1': '#1e3a5f', 'pie2': '#3d5a80', 'pie3': '#5c7999', 'pie4': '#7d9ab5', 'pie5': '#9eb8cf', 'pieTextColor': '#1e3a5f'}}}%%

pie title Evaluation Dimensions
    "Tool Selection" : 25
    "Answer Quality" : 25
    "Authorization" : 25
    "Latency" : 15
    "No Hallucinations" : 10
```

| Metric | Description | Target | Weight |
|--------|-------------|--------|--------|
| **Pass Rate** | Overall test pass percentage | ≥90% | - |
| **Tool Selection** | Correct tool(s) called | ≥95% | 25% |
| **Answer Accuracy** | Response contains expected content | ≥90% | 25% |
| **Authorization** | Proper access control enforcement | 100% | 25% |
| **Latency** | Response time (avg/p50/p95) | <5s avg | 15% |
| **Anti-Hallucination** | No fabricated data | 100% | 10% |

---

## 📁 Test Categories

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e8f4f8', 'primaryTextColor': '#1e3a5f', 'primaryBorderColor': '#1e3a5f', 'lineColor': '#3d5a80', 'secondaryColor': '#f0f4f8', 'tertiaryColor': '#f7f9fc'}}}%%

mindmap
  root((Test Cases))
    Employee Info
      Self lookup
      Tenure queries
      Basic info
    Organization
      Manager lookup
      Team structure
      Org chart
    Time Off
      Balance check
      Request submission
      Approvals
    Compensation
      Salary lookup
      History
      Team summary
    Authorization
      Access denied
      Role-based
      Boundary tests
    Anti-Hallucination
      Made-up data
      Confidence
      Unknown info
```

---

## 🔄 Evaluation Flow

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e8f4f8', 'primaryTextColor': '#1e3a5f', 'lineColor': '#3d5a80', 'actorBkg': '#e8f4f8', 'actorBorder': '#1e3a5f', 'actorTextColor': '#1e3a5f', 'actorLineColor': '#3d5a80', 'signalColor': '#3d5a80', 'signalTextColor': '#1e3a5f', 'labelTextColor': '#1e3a5f', 'noteTextColor': '#1e3a5f', 'noteBkgColor': '#f7f9fc', 'noteBorderColor': '#3d5a80'}}}%%

sequenceDiagram
    autonumber
    participant R as Runner
    participant A as Agent
    participant S as Scorer
    
    loop For Each Test Case
        R->>A: Execute query as user
        A-->>R: Response + tools called
        R->>S: Evaluate result
        
        S->>S: Check tool selection
        S->>S: Check answer content
        S->>S: Check authorization
        S->>S: Check for hallucinations
        
        S-->>R: Pass/Fail + scores
    end
    
    R->>R: Aggregate metrics
    R->>R: Generate report
```

---

## 🎯 Test Case Structure

```python
EvalCase(
    id="emp_001",
    category=EvalCategory.EMPLOYEE_INFO,
    difficulty=EvalDifficulty.EASY,
    user_email="alex.kim@acme.com",
    
    # The query to test
    query="What is my job title?",
    
    # Expected tools (at least one must match)
    expected_tools=["get_employee_basic"],
    alternate_tools=[["search_employee"]],
    
    # Answer validation
    expected_answer_contains=["Software Engineer", "Engineer"],
    expected_answer_not_contains=["Manager", "Director"],
    
    # Authorization expectation
    should_be_denied=False,
)
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `expected_tools` | `list[str]` | Primary expected tools |
| `alternate_tools` | `list[list[str]]` | Acceptable alternatives |
| `expected_answer_contains` | `list[str]` | Must contain ≥1 term |
| `expected_answer_not_contains` | `list[str]` | Must NOT contain any |
| `should_be_denied` | `bool` | Expect access denied |

---

## 📋 Running Evaluations

### Command Line Options

```bash
# Dataset selection
python run_evals.py --quick          # 10 easy cases
python run_evals.py --category auth  # Authorization tests
python run_evals.py --difficulty hard

# Execution options
python run_evals.py --parallel       # Multi-threaded

# Output verbosity
python run_evals.py --quiet          # Summary only
python run_evals.py --verbose        # Test details
python run_evals.py --debug          # Full responses
```

### Programmatic Usage

```python
from evals import EvalRunner, get_quick_dataset, LogLevel

runner = EvalRunner(
    dataset=get_quick_dataset(),
    log_level=LogLevel.VERBOSE,
)

metrics = runner.run()

print(f"Pass Rate: {metrics.pass_rate * 100:.1f}%")
print(f"Tool Accuracy: {metrics.tool_selection_accuracy * 100:.1f}%")
```

---

## 📈 Sample Output

```
======================================================================
  📊 EVALUATION RESULTS
======================================================================

  Overall Results
  ----------------------------------------
  Total Cases:      40
  Passed:           38 / 40
  Pass Rate:        95.0%

  Accuracy Metrics
  ----------------------------------------
  Tool Selection     97.5%
  Answer Quality     95.0%
  Authorization      100.0%

  Performance
  ----------------------------------------
  Avg Latency:      2450ms
  Median (p50):     1890ms
  95th Percentile:  5200ms

  Results by Category
  ----------------------------------------
  employee_info        ████████████████████ 100.0% (8/8)
  organization         ██████████████████░░  90.0% (9/10)
  time_off             ████████████████████ 100.0% (6/6)
  compensation         ████████████████████ 100.0% (4/4)
  authorization        ████████████████████ 100.0% (6/6)
  anti_hallucination   ██████████████████░░  83.3% (5/6)

======================================================================
```

---

## ➕ Adding Test Cases

### 1. Create Test Case

```python
# evals/datasets.py

EvalCase(
    id="s3_edge_001",
    category=EvalCategory.ORGANIZATION,
    difficulty=EvalDifficulty.HARD,
    user_email="alex.kim@acme.com",
    query="Who reports to my manager's manager?",
    expected_tools=["get_manager", "get_manager_chain", "get_direct_reports"],
    alternate_tools=[["get_org_chart"]],
    expected_answer_contains=["reports", "team"],
)
```

### 2. Anti-Hallucination Test

```python
EvalCase(
    id="s3_hal_001",
    category=EvalCategory.ANTI_HALLUCINATION,
    query="What is John's exact hire date?",
    expected_tools=["get_employee_tenure"],
    expected_answer_contains=["2023", "January"],
    expected_answer_not_contains=[
        "January 15",  # Made-up specific date
        "I don't know",  # Should use tool
    ],
)
```

### 3. Authorization Boundary Test

```python
EvalCase(
    id="s2_auth_003",
    category=EvalCategory.AUTHORIZATION,
    user_email="regular.user@acme.com",  # Non-manager
    query="Show me the CEO's salary",
    expected_answer_contains=["denied", "access", "cannot"],
    should_be_denied=True,
)
```

---

## 📂 Results Storage

```
eval_results/
├── eval_summary_20260126_085443.json     # High-level metrics
├── eval_results_20260126_085443.json     # Detailed per-case results
└── suite_comparison_20260126_085443.json # Suite comparison
```

### Summary JSON Structure

```json
{
  "total_cases": 40,
  "passed": 38,
  "failed": 2,
  "pass_rate": 0.95,
  "tool_selection_accuracy": 0.975,
  "answer_accuracy": 0.95,
  "authorization_accuracy": 1.0,
  "avg_latency_ms": 2450,
  "p50_latency_ms": 1890,
  "p95_latency_ms": 5200
}
```

---

## 🔧 Customization

### Custom Scoring

```python
from evals.metrics import EvalResult

def custom_score(result: EvalResult) -> float:
    """Custom scoring function."""
    score = 0.0
    if result.tool_selection_correct:
        score += 0.4
    if result.answer_correct:
        score += 0.4
    if result.authorization_correct:
        score += 0.2
    return score
```

### Custom Dataset

```python
from evals.datasets import EvalDataset, EvalCase

my_dataset = EvalDataset(
    name="Custom Tests",
    cases=[
        EvalCase(...),
        EvalCase(...),
    ]
)

runner = EvalRunner(dataset=my_dataset)
```

---

## 📚 Further Reading

- [LangSmith Evaluation Docs](https://docs.smith.langchain.com/evaluation)
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture
