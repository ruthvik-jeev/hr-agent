# HR Agent Architecture

> **Enterprise-grade HR Assistant powered by LangChain, LangGraph, and LangSmith**

---

## 🏗️ High-Level Architecture

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#1e3a5f',
    'primaryTextColor': '#ffffff',
    'primaryBorderColor': '#0d2137',
    'lineColor': '#3d5a80',
    'secondaryColor': '#e8f4f8',
    'tertiaryColor': '#f0f4f8',
    'background': '#ffffff',
    'mainBkg': '#ffffff',
    'nodeBorder': '#3d5a80',
    'clusterBkg': '#f7f9fc',
    'clusterBorder': '#3d5a80',
    'titleColor': '#1e3a5f',
    'edgeLabelBackground': '#ffffff'
  }
}}%%

flowchart TB
    subgraph CLIENTS["CLIENT LAYER"]
        direction LR
        WEB["Web UI<br/>Streamlit"]
        CLI["CLI<br/>Rich Terminal"]
        API["REST API<br/>FastAPI"]
        SLACK["Integrations<br/>Slack/Teams"]
    end

    subgraph CORE["LANGGRAPH ORCHESTRATION"]
        direction TB
        
        subgraph WORKFLOW["Agent Workflow"]
            AGENT["Agent Node<br/>LLM Decision Making"]
            AUTH["Auth Check<br/>Policy Engine"]
            TOOLS["Tool Execution<br/>LangChain Tools"]
        end
        
        STATE[("State<br/>Messages, Context")]
        CHECKPOINT[("Checkpoint<br/>Memory Saver")]
    end

    subgraph SERVICES["BUSINESS LAYER"]
        direction LR
        EMP["Employee<br/>Service"]
        HOL["Holiday<br/>Service"]
        COMP["Compensation<br/>Service"]
        ORG["Company<br/>Service"]
    end

    subgraph DATA["DATA LAYER"]
        REPO["Repositories<br/>SQLAlchemy"]
        DB[("Database<br/>SQLite/PostgreSQL")]
    end

    subgraph INFRA["INFRASTRUCTURE"]
        direction LR
        CONFIG["Config"]
        TRACE["LangSmith<br/>Tracing"]
        SEC["Security"]
        OBS["Metrics"]
    end

    CLIENTS --> CORE
    AGENT --> AUTH
    AUTH -->|allowed| TOOLS
    AUTH -->|denied| AGENT
    TOOLS --> AGENT
    STATE -.-> WORKFLOW
    CHECKPOINT -.-> STATE
    CORE --> SERVICES
    SERVICES --> REPO
    REPO --> DB
    INFRA -.-> CORE
    TRACE -.-> AGENT

    style CLIENTS fill:#e8f4f8,stroke:#3d5a80,stroke-width:2px
    style CORE fill:#f0f4f8,stroke:#1e3a5f,stroke-width:3px
    style SERVICES fill:#e8f4f8,stroke:#3d5a80,stroke-width:2px
    style DATA fill:#f7f9fc,stroke:#3d5a80,stroke-width:2px
    style INFRA fill:#f0f4f8,stroke:#6b7280,stroke-width:2px
```

---

## 🔄 LangGraph Workflow

The agent follows a **ReAct pattern** with policy-based authorization:

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#1e3a5f',
    'primaryTextColor': '#ffffff',
    'primaryBorderColor': '#0d2137',
    'lineColor': '#3d5a80',
    'secondaryColor': '#e8f4f8',
    'tertiaryColor': '#f0f4f8',
    'background': '#ffffff'
  }
}}%%

stateDiagram-v2
    [*] --> Agent: User Query

    Agent --> CheckTools: Has Tool Calls?
    
    state CheckTools <<choice>>
    CheckTools --> Authorization: Yes
    CheckTools --> [*]: No (Final Response)

    state Authorization {
        [*] --> PolicyEngine
        PolicyEngine --> Allowed: Permitted
        PolicyEngine --> Denied: Forbidden
        Allowed --> [*]
        Denied --> [*]
    }

    Authorization --> ToolExecution: Allowed
    Authorization --> Agent: Denied (Error Message)
    
    state ToolExecution {
        [*] --> Execute
        Execute --> CollectResults
        CollectResults --> [*]
    }

    ToolExecution --> Agent: Results
    
    note right of Agent
        LLM processes messages
        and decides next action
    end note
    
    note right of Authorization
        Policy engine validates
        permissions per tool call
    end note
```

---

## 📊 State Management

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#1e3a5f',
    'primaryTextColor': '#ffffff',
    'primaryBorderColor': '#0d2137',
    'lineColor': '#3d5a80'
  }
}}%%

classDiagram
    class AgentState {
        +Sequence~BaseMessage~ messages
        +str user_email
        +int user_id
        +str user_role
        +dict pending_confirmation
        +list~str~ tools_called
        +str current_date
    }
    
    class BaseMessage {
        <<interface>>
        +str content
        +str type
    }
    
    class HumanMessage {
        +str content
        +type = "human"
    }
    
    class AIMessage {
        +str content
        +list~ToolCall~ tool_calls
        +type = "ai"
    }
    
    class ToolMessage {
        +str content
        +str tool_call_id
        +type = "tool"
    }
    
    BaseMessage <|-- HumanMessage
    BaseMessage <|-- AIMessage
    BaseMessage <|-- ToolMessage
    AgentState *-- BaseMessage
```

---

## 🛠️ Tool Architecture

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#1e3a5f',
    'primaryTextColor': '#ffffff',
    'primaryBorderColor': '#0d2137',
    'lineColor': '#3d5a80'
  }
}}%%

flowchart LR
    subgraph TOOLS["LangChain Tools - 25 Total"]
        direction TB
        
        subgraph EMP_TOOLS["Employee & Org"]
            T1["search_employee"]
            T2["get_employee_basic"]
            T3["get_manager"]
            T4["get_direct_reports"]
            T5["get_org_chart"]
        end
        
        subgraph HOL_TOOLS["Time Off"]
            T6["get_holiday_balance"]
            T7["submit_holiday_request"]
            T8["approve_holiday_request"]
            T9["get_team_calendar"]
        end
        
        subgraph COMP_TOOLS["Compensation"]
            T10["get_compensation"]
            T11["get_salary_history"]
            T12["get_team_compensation_summary"]
        end
        
        subgraph COMPANY_TOOLS["Company"]
            T13["get_company_policies"]
            T14["get_company_holidays"]
            T15["get_announcements"]
        end
    end
    
    subgraph ACCESS["Access Control"]
        OPEN["Open Access"]
        CONFIRM["Requires Confirmation"]
        RESTRICT["Role-Based"]
    end
    
    EMP_TOOLS --> OPEN
    HOL_TOOLS --> CONFIRM
    COMP_TOOLS --> RESTRICT

    style TOOLS fill:#f0f4f8,stroke:#1e3a5f,stroke-width:2px
    style ACCESS fill:#f7f9fc,stroke:#3d5a80,stroke-width:2px
    style EMP_TOOLS fill:#e8f4f8,stroke:#3d5a80
    style HOL_TOOLS fill:#e8f4f8,stroke:#3d5a80
    style COMP_TOOLS fill:#e8f4f8,stroke:#3d5a80
    style COMPANY_TOOLS fill:#e8f4f8,stroke:#3d5a80
```

---

## 🔐 Authorization Flow

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#1e3a5f',
    'primaryTextColor': '#ffffff',
    'primaryBorderColor': '#0d2137',
    'lineColor': '#3d5a80',
    'actorLineColor': '#3d5a80',
    'signalColor': '#1e3a5f',
    'signalTextColor': '#1e3a5f'
  }
}}%%

sequenceDiagram
    autonumber
    participant U as User
    participant A as Agent
    participant P as Policy Engine
    participant T as Tool
    participant D as Database

    U->>A: "What is John's salary?"
    A->>A: Decide: get_compensation(john_id)
    A->>P: Check: Can user view John's salary?
    
    alt User is John OR HR/Finance
        P-->>A: Allowed
        A->>T: Execute get_compensation
        T->>D: Query salary data
        D-->>T: Salary: $95,000
        T-->>A: Return result
        A-->>U: "John's salary is $95,000"
    else Unauthorized
        P-->>A: Denied
        A-->>U: "Access denied: Cannot view salary"
    end
```
