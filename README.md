# HR Agent

<div align="center">

![LangChain](https://img.shields.io/badge/LangChain-0.3+-1e3a5f?style=for-the-badge&logo=langchain&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Stateful-3d5a80?style=for-the-badge)
![LangSmith](https://img.shields.io/badge/LangSmith-Tracing-5c7999?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)

**A production-ready HR assistant demonstrating best practices in LLM agent design**

[Quick Start](#-quick-start) • [Architecture](#-architecture) • [Features](#-key-features) • [Evaluation](#-evaluation)

</div>

---

## 🚀 Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd hr-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your LLM API key

# Run the Web UI
streamlit run app.py
```

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🔄 **LangGraph Workflow** | Stateful agent with conditional routing and checkpointing |
| 🛠️ **LangChain Tools** | 25 HR tools with Pydantic validation |
| 📊 **LangSmith Tracing** | Full observability, debugging, and experiment tracking |
| 🔐 **Policy Authorization** | Declarative YAML-based access control |
| 🧪 **Evaluation Framework** | 40+ test cases with automated scoring |

---

## 🏗️ Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e8f4f8', 'primaryTextColor': '#1e3a5f', 'primaryBorderColor': '#3d5a80', 'lineColor': '#3d5a80', 'secondaryColor': '#f0f4f8', 'tertiaryColor': '#f7f9fc', 'nodeTextColor': '#1e3a5f', 'textColor': '#1e3a5f', 'mainBkg': '#e8f4f8', 'nodeBkg': '#e8f4f8', 'clusterBkg': '#f7f9fc'}}}%%

flowchart TB
    subgraph CLIENT["Clients"]
        WEB["Web UI"]
        CLI["CLI"]
        API["REST API"]
    end
    
    subgraph AGENT["LangGraph Agent"]
        direction LR
        LLM["Agent<br/>Node"] --> AUTH["Auth<br/>Check"]
        AUTH -->|allowed| TOOLS["Tool<br/>Execution"]
        AUTH -->|denied| LLM
        TOOLS --> LLM
    end
    
    subgraph SERVICES["Services"]
        direction LR
        S1["Employee"]
        S2["Holiday"]
        S3["Compensation"]
    end
    
    subgraph DATA["Data"]
        DB[("Database")]
    end
    
    CLIENT --> AGENT
    AGENT --> SERVICES
    SERVICES --> DATA
    
    style CLIENT fill:#e8f4f8,stroke:#3d5a80,color:#1e3a5f
    style AGENT fill:#f0f4f8,stroke:#3d5a80,stroke-width:3px,color:#1e3a5f
    style SERVICES fill:#e8f4f8,stroke:#3d5a80,color:#1e3a5f
    style DATA fill:#f7f9fc,stroke:#6b7280,color:#1e3a5f
```

### How It Works

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e8f4f8', 'primaryTextColor': '#1e3a5f', 'primaryBorderColor': '#3d5a80', 'lineColor': '#3d5a80', 'actorBkg': '#e8f4f8', 'actorBorder': '#3d5a80', 'actorTextColor': '#1e3a5f', 'actorLineColor': '#3d5a80', 'signalColor': '#3d5a80', 'signalTextColor': '#1e3a5f', 'labelTextColor': '#1e3a5f', 'noteTextColor': '#1e3a5f', 'noteBkgColor': '#f7f9fc', 'noteBorderColor': '#3d5a80'}}}%%

sequenceDiagram
    participant U as User
    participant A as Agent
    participant P as Policy
    participant T as Tools
    participant D as Database

    U->>A: "What's my holiday balance?"
    A->>A: Decide: get_holiday_balance
    A->>P: Check authorization
    P-->>A: Allowed
    A->>T: Execute tool
    T->>D: Query data
    D-->>T: 15 days remaining
    T-->>A: Result
    A-->>U: "You have 15 vacation days left"
```

---

## 📁 Project Structure

```
hr-agent/
├── 📄 app.py                    # Streamlit Web UI
├── 📄 run_evals.py              # Evaluation runner
│
├── 📁 src/hr_agent/
│   ├── 📁 core/
│   │   ├── langgraph_agent.py   # LangGraph workflow
│   │   └── policy_engine.py     # Authorization
│   │
│   ├── 📁 services/
│   │   ├── langchain_tools.py   # 25 LangChain tools
│   │   └── base.py              # Service classes
│   │
│   ├── 📁 repositories/         # Data access layer
│   ├── 📁 api/                  # REST API (FastAPI)
│   └── 📁 policies/             # YAML auth rules
│
└── 📁 evals/                    # Evaluation framework
```

---

## 🧪 Evaluation

```bash
# Quick test (10 cases)
python run_evals.py --quick --verbose

# Full evaluation
python run_evals.py

# Filter by category
python run_evals.py --category time_off
```

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
  Tool Selection     97.5%
  Answer Quality     95.0%
  Authorization      100.0%
======================================================================
```

---

## 🛠️ Available Tools

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e8f4f8', 'primaryTextColor': '#1e3a5f', 'primaryBorderColor': '#3d5a80', 'lineColor': '#3d5a80', 'secondaryColor': '#f0f4f8', 'tertiaryColor': '#f7f9fc', 'nodeTextColor': '#1e3a5f'}}}%%

mindmap
  root((HR Tools))
    Employee
      search_employee
      get_employee_basic
      get_employee_tenure
    Organization
      get_manager
      get_direct_reports
      get_org_chart
      get_department_directory
    Time Off
      get_holiday_balance
      submit_holiday_request
      get_pending_approvals
      get_team_calendar
    Compensation
      get_compensation
      get_salary_history
    Company
      get_company_policies
      get_announcements
      get_company_holidays
```

---

## ⚙️ Configuration

```bash
# .env

# LLM Provider
LLM_PROVIDER=openai_compatible
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

# Optional: LangSmith Tracing
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=hr-agent
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical architecture, diagrams, design decisions |
| [EVALUATION.md](EVALUATION.md) | Evaluation framework, metrics, test cases |

---

## 📄 License

MIT
