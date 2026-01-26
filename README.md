# HR Agent

A production-ready HR assistant built with **LangChain**, **LangGraph**, and **LangSmith**. Demonstrates best practices in LLM-based agent design with policy-based authorization and comprehensive evaluation.

## Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd hr-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set your API key
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Run the Web UI
streamlit run app.py
```

## Key Features

| Capability | Description |
|------------|-------------|
| **LangGraph Workflow** | State-based agent with conditional routing |
| **LangChain Tools** | 25+ HR tools with Pydantic schemas |
| **LangSmith Tracing** | Full observability and experiment tracking |
| **Policy Authorization** | Declarative YAML-based access control |
| **Evaluation Framework** | Built-in testing with 40+ test cases |

## Architecture

```
╔═══════════════════════════════════════════════════════════════╗
║                    LANGGRAPH WORKFLOW                         ║
║                                                               ║
║   ┌─────────┐    ┌────────────┐    ┌─────────┐               ║
║   │  AGENT  │───►│ CHECK_AUTH │───►│  TOOLS  │               ║
║   │  (LLM)  │    │  (Policy)  │    │(Execute)│               ║
║   └────▲────┘    └─────┬──────┘    └────┬────┘               ║
║        │               │ denied         │                     ║
║        │               ▼                │                     ║
║        │         [Error Msg]            │                     ║
║        └────────────────────────────────┘                     ║
╚═══════════════════════════════════════════════════════════════╝
```

## Running Evaluations

```bash
# Quick test (10 cases)
python run_evals.py --quick

# Full evaluation
python run_evals.py --verbose

# Compare agents
python compare_agents.py --save
```

## Project Structure

```
hr-agent/
├── app.py                    # Streamlit Web UI
├── run_evals.py              # Evaluation runner
├── compare_agents.py         # Agent comparison
│
├── src/hr_agent/
│   ├── core/
│   │   ├── langgraph_agent.py   # LangGraph workflow (primary)
│   │   ├── policy_engine.py     # Authorization
│   │   └── memory.py            # Conversation state
│   │
│   ├── services/
│   │   ├── langchain_tools.py   # LangChain tools
│   │   └── base.py              # Service classes
│   │
│   ├── repositories/            # Data access
│   ├── api/                     # REST API
│   └── policies/                # Auth rules (YAML)
│
└── evals/                       # Evaluation framework
```

## Configuration

```bash
# .env
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

# Optional: LangSmith
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=ls-...
```

## Available Tools

| Category | Tools |
|----------|-------|
| **Employee** | `search_employee`, `get_employee_basic`, `get_employee_tenure` |
| **Organization** | `get_manager`, `get_direct_reports`, `get_org_chart` |
| **Time Off** | `get_holiday_balance`, `submit_holiday_request`, `get_pending_approvals` |
| **Compensation** | `get_compensation`, `get_salary_history` |
| **Company** | `get_company_policies`, `get_announcements` |

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture details
- [EVALUATION.md](EVALUATION.md) - Evaluation framework guide

## License

MIT
