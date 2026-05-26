# Agentic Workflow — Novum Development

> Visual representation of the orchestrated development workflow. See [workflow.yaml](workflow.yaml) for the formal definition.

---

## 1. Workflow Overview

The Novum development workflow is an orchestrated agentic system with four specialized agents:

| Agent | Role | Primary Outputs |
|-------|------|-----------------|
| **Orchestrator** | Workflow controller | Implementation plans, task coordination |
| **BSA** | Requirements analyst | BRDs, User Stories |
| **Coder** | Implementation | Code, Unit Tests |
| **Reviewer** | Quality assurance | Review reports, Scores |

---

## 2. Main Workflow Diagram

```mermaid
flowchart TD
    subgraph INIT["🚀 Initialization"]
        A[/"📥 Receive Requirement"/]
    end

    subgraph ANALYSIS["📋 Analysis Phase"]
        B["🔍 BSA Agent"]
        B1["Read Memory Bank"]
        B2["Analyze Requirement"]
        B3["Generate BRD"]
        B4["Create User Stories"]
        B5["Sync to GitHub"]
        B6["Update Memory Bank"]
        
        B --> B1 --> B2 --> B3 --> B4 --> B5 --> B6
    end

    subgraph PLANNING["📝 Planning Phase"]
        C["🎯 Orchestrator"]
        C1["Read Memory Bank"]
        C2["Create Implementation Plan"]
        C3["Update Memory Bank"]
        
        C --> C1 --> C2 --> C3
    end

    subgraph IMPLEMENTATION["💻 Implementation Phase"]
        D["👨‍💻 Coder Agent"]
        D1["Read Memory Bank"]
        D2["Implement Code"]
        D3["Generate Unit Tests"]
        D4["Update Memory Bank"]
        
        D --> D1 --> D2 --> D3 --> D4
    end

    subgraph REVIEW["🔎 Review Phase"]
        E["📊 Reviewer Agent"]
        E1["Read Memory Bank"]
        E2["Evaluate Code"]
        E3["Assign Score"]
        E4["Generate Report"]
        E5["Update Memory Bank"]
        
        E --> E1 --> E2 --> E3 --> E4 --> E5
    end

    subgraph DECISION{"🔀 Quality Gate"}
        F{{"Score ≥ 9?"}}
    end

    subgraph ITERATION{"🔄 Iteration Check"}
        G{{"Iterations < 5?"}}
    end

    subgraph COMPLETION["✅ Completion"]
        H["✨ Implementation Approved"]
        I["📝 Finalize Documentation"]
    end

    subgraph ESCALATION["⚠️ Escalation"]
        J["🚨 Max Iterations Reached"]
        K["👤 Manual Review Required"]
    end

    A --> B
    B6 --> C
    C3 --> D
    D4 --> E
    E5 --> F
    
    F -->|"✅ Yes"| H
    F -->|"❌ No"| G
    
    G -->|"✅ Yes"| D
    G -->|"❌ No"| J
    
    H --> I
    J --> K

    style INIT fill:#e1f5fe,stroke:#01579b
    style ANALYSIS fill:#fff3e0,stroke:#e65100
    style PLANNING fill:#f3e5f5,stroke:#4a148c
    style IMPLEMENTATION fill:#e8f5e9,stroke:#1b5e20
    style REVIEW fill:#fce4ec,stroke:#880e4f
    style COMPLETION fill:#c8e6c9,stroke:#2e7d32
    style ESCALATION fill:#ffcdd2,stroke:#b71c1c
```

---

## 3. Agent Interaction Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant B as BSA Agent
    participant C as Coder Agent
    participant R as Reviewer Agent
    participant M as Memory Bank
    participant G as GitHub

    U->>O: Submit Requirement
    
    rect rgb(255, 243, 224)
        Note over O,B: Analysis Phase
        O->>B: Delegate Analysis
        B->>M: Read Context
        B->>B: Analyze & Generate BRD
        B->>B: Create User Stories
        B->>G: Sync Documentation
        B->>M: Update Memory
        B->>O: Analysis Complete
    end

    rect rgb(243, 229, 245)
        Note over O: Planning Phase
        O->>M: Read Context
        O->>O: Create Implementation Plan
        O->>M: Update Memory
    end

    loop Max 5 Iterations
        rect rgb(232, 245, 233)
            Note over O,C: Implementation Phase
            O->>C: Assign Implementation
            C->>M: Read Context
            C->>C: Implement Code
            C->>C: Generate Tests
            C->>M: Update Memory
            C->>O: Implementation Ready
        end

        rect rgb(252, 228, 236)
            Note over O,R: Review Phase
            O->>R: Request Review
            R->>M: Read Context
            R->>R: Evaluate Code
            R->>R: Assign Score
            R->>M: Update Memory
            R->>O: Score: X/10
        end

        alt Score >= 9
            O->>U: ✅ Implementation Approved
        else Score < 9 AND Iterations < 5
            O->>C: Revise with Feedback
        else Score < 9 AND Iterations >= 5
            O->>U: ⚠️ Escalate to Manual Review
        end
    end
```

---

## 4. Memory Protocol Flow

```mermaid
flowchart LR
    subgraph MB["📚 Memory Bank"]
        direction TB
        T["📄 Templates"]
        I["🗂️ Indices"]
        L["📝 Logs"]
        C["📏 Conventions"]
        S["📖 Shared Docs"]
    end

    subgraph AGENTS["🤖 Agents"]
        O["Orchestrator"]
        B["BSA"]
        CD["Coder"]
        R["Reviewer"]
    end

    O <-->|"read/write"| MB
    B <-->|"read/write"| MB
    CD <-->|"read/write"| MB
    R <-->|"read/write"| MB

    style MB fill:#fff8e1,stroke:#f57f17
    style AGENTS fill:#e3f2fd,stroke:#1565c0
```

---

## 5. Skills Distribution

```mermaid
mindmap
  root((Skills))
    GitHub MCP
      Issues
      Pull Requests
      Documentation Sync
    UX/Frontend
      React 19
      Tailwind v4
      Accessibility
      Responsive Design
    Database
      PostgreSQL
      Schema Review
      Query Execution
      JSONB Analysis
    Implementation Plan
      Task Breakdown
      Dependencies
      Effort Estimation
    Unit Test Backend
      pytest
      pytest-asyncio
      pytest-httpx
      Coverage
    Unit Test Frontend
      Vitest
      Testing Library
      jest-axe
      MSW
    Memory Protocol
      Read Before Task
      Update After Task
      Templates
      Indices
```

---

## 6. Quality Gate Decision Tree

```mermaid
flowchart TD
    A["Code Submitted"] --> B{"Score Evaluation"}
    
    B --> C["Code Quality<br/>25%"]
    B --> D["Test Coverage<br/>20%"]
    B --> E["Architecture<br/>20%"]
    B --> F["Documentation<br/>15%"]
    B --> G["Security<br/>10%"]
    B --> H["Performance<br/>10%"]
    
    C & D & E & F & G & H --> I["Calculate Total Score"]
    
    I --> J{{"Score ≥ 9?"}}
    
    J -->|"✅ Yes"| K["Approved"]
    J -->|"❌ No"| L{{"Iteration < 5?"}}
    
    L -->|"Yes"| M["Return to Coder<br/>with Feedback"]
    L -->|"No"| N["Escalate to<br/>Manual Review"]

    style K fill:#c8e6c9,stroke:#2e7d32
    style N fill:#ffcdd2,stroke:#b71c1c
    style M fill:#fff9c4,stroke:#f9a825
```

---

## 7. File Output Structure

```mermaid
flowchart TD
    subgraph DOCS["docs/implementation-phase/"]
        BRD["📁 brds/"]
        US["📁 user-stories/"]
        IP["📁 implementation-plans/"]
        REV["📁 reviews/"]
        UT["📁 unit-tests/"]
    end

    subgraph AGENTS["Agents"]
        B["BSA"] --> BRD
        B --> US
        O["Orchestrator"] --> IP
        R["Reviewer"] --> REV
        C["Coder"] --> UT
    end

    style DOCS fill:#e8f5e9,stroke:#2e7d32
```

---

## 8. State Machine

```mermaid
stateDiagram-v2
    [*] --> IDLE
    
    IDLE --> ANALYZE: New Requirement
    
    ANALYZE --> PLAN: BRD & Stories Ready
    
    PLAN --> IMPLEMENT: Plan Created
    
    IMPLEMENT --> REVIEW: Code & Tests Ready
    
    REVIEW --> COMPLETE: Score ≥ 9
    REVIEW --> IMPLEMENT: Score < 9 & iter < 5
    REVIEW --> ESCALATE: Score < 9 & iter ≥ 5
    
    COMPLETE --> [*]
    ESCALATE --> [*]
    
    note right of REVIEW
        Max 5 iterations
        Minimum score: 9/10
    end note
```

---

## 9. Usage

### Starting a New Requirement

1. Open VS Code with GitHub Copilot or Claude Code
2. Invoke the **Orchestrator** agent
3. Provide the requirement or ticket reference
4. The workflow executes automatically

### Monitoring Progress

- Check `docs/implementation-phase/` for generated artifacts
- Review `.github/memory-bank/logs/` for decision history
- Monitor iteration count in review reports

### Quality Standards

- **Minimum Score**: 9/10
- **Max Iterations**: 5
- **Test Coverage**: ≥80% (backend and frontend)
