# HR Agent

<div align="center">

![LangChain](https://img.shields.io/badge/LangChain-0.3+-1e3a5f?style=for-the-badge&logo=langchain&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Stateful-3d5a80?style=for-the-badge)
![Langfuse](https://img.shields.io/badge/Langfuse-Tracing-5c7999?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![uv](https://img.shields.io/badge/uv-Package_Manager-DE5FE9?style=for-the-badge)

**A production-ready HR assistant demonstrating best practices in LLM agent design**

[Quick Start](#-quick-start) • [Architecture](#-architecture) • [Features](#-key-features) • [Evaluation](#-evaluation)

</div>

---

## 🚀 Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd hr-agent

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies with uv
uv sync

# Configure
cp .env.example .env
# Edit .env with your LLM API key

# Run the Web UI
uv run streamlit run apps/web/app.py

# Or run the API server
uv run uvicorn apps.api.server:app --reload
```

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🔄 **LangGraph Workflow** | Stateful agent with conditional routing and message history |
| 🛠️ **LangChain Tools** | 25 HR tools with Pydantic validation |
| 📊 **Langfuse Tracing** | Full observability, debugging, and experiment tracking |
| 🔐 **Policy Authorization** | Declarative YAML-based access control (safe evaluators, no eval()) |
| 🧪 **Evaluation Framework** | 40+ test cases with automated scoring |
| ⚡ **Modern Tooling** | uv for fast dependency management, hatchling for packaging |

---

## 🏗️ Architecture

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart TB
    subgraph CLIENT["🖥️ Clients"]
        WEB["Web UI"]
        CLI["CLI"]
        API["REST API"]
    end
    
    subgraph AGENT["🤖 LangGraph Agent"]
        direction LR
        LLM["Agent Node"] --> AUTH["Auth Check"]
        AUTH -->|allowed| TOOLS["Tool Execution"]
        AUTH -->|denied| LLM
        TOOLS --> LLM
    end
    
    subgraph SERVICES["⚙️ Services"]
        direction LR
        S1["Employee"]
        S2["Holiday"]
        S3["Compensation"]
    end
    
    subgraph DATA["💾 Data"]
        DB[("Database")]
    end
    
    CLIENT --> AGENT
    AGENT --> SERVICES
    SERVICES --> DATA
```

### How It Works

```mermaid
%%{init: {'theme': 'neutral'}}%%
sequenceDiagram
    participant U as 👤 User
    participant A as 🤖 Agent
    participant P as 🔐 Policy
    participant T as 🛠️ Tools
    participant D as 💾 Database

    U->>A: "What's my holiday balance?"
    A->>A: Decide: get_holiday_balance
    A->>P: Check authorization
    P-->>A: ✅ Allowed
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
├── 📁 apps/
│   ├── web/                     # Streamlit Web UI
│   └── api/                     # FastAPI server
│
├── 📁 hr_agent/
│   ├── agent/                   # LangGraph workflow
│   ├── policies/                # Authorization + YAML rules
│   ├── tools/                   # LangChain tool wrappers
│   ├── services/                # Business logic
│   ├── repositories/            # Data access layer
│   ├── configs/                 # Configuration
│   ├── tracing/                 # Observability
│   └── utils/                   # Cross-cutting utilities
│
├── 📁 evals/                    # Evaluation framework
└── 📁 docs/                     # Architecture and evaluation docs
```

---

## 🧪 Evaluation

```bash
# Quick test (10 cases)
python evals/runners/run_evals.py --quick --verbose

# Full evaluation
python evals/runners/run_evals.py

# Filter by category
python evals/runners/run_evals.py --category time_off
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
%%{init: {'theme': 'neutral'}}%%
mindmap
  root((🛠️ HR Tools))
    👤 Employee
      search_employee
      get_employee_basic
      get_employee_tenure
    🏢 Organization
      get_manager
      get_direct_reports
      get_org_chart
      get_department_directory
    🏖️ Time Off
      get_holiday_balance
      submit_holiday_request
      get_pending_approvals
      get_team_calendar
    💰 Compensation
      get_compensation
      get_salary_history
    📋 Company
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

# Optional: Langfuse Observability (free tier available)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Langfuse eval tracing
# Eval runs are tagged with metadata like run_type=eval and eval_dataset=<name>

```

### Using uv

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --group dev

# Run commands
uv run streamlit run apps/web/app.py
uv run pytest
uv run ruff check .
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
