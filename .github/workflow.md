# Agentic Workflow — Novum Development

> Visual representation of the orchestrated development workflow. See [workflow.yaml](workflow.yaml) for the formal definition.

---

## 1. Phase & Step Quick Reference

### 1.1 Phases Overview

| ID | Phase | Agent | Description |
|----|-------|-------|-------------|
| **F0** | IDLE | — | Waiting for new requirement |
| **F1** | ANALYZE | BSA | Requirements analysis and documentation |
| **F2** | PLAN | Orchestrator | Implementation planning |
| **F3** | IMPLEMENT | Coder | Code implementation and testing |
| **F4** | REVIEW | Reviewer | Quality evaluation and scoring |
| **F5** | COMPLETE | — | Approved, finalize documentation |
| **F6** | ESCALATE | — | Max iterations reached, manual review |

### 1.2 All Steps by Phase

| Step ID | Phase | Action | Description |
|---------|-------|--------|-------------|
| **F1.S1** | ANALYZE | `read_memory_bank` | Read project context, knowledge index, lessons learned |
| **F1.S2** | ANALYZE | `analyze_requirement` | Parse and classify incoming requirement |
| **F1.S3** | ANALYZE | `generate_brd` | Create Business Requirements Document |
| **F1.S4** | ANALYZE | `generate_user_stories` | Create user stories with acceptance criteria |
| **F1.S5** | ANALYZE | `sync_to_github` | Sync documentation to GitHub (if MCP available) |
| **F1.S6** | ANALYZE | `update_memory_bank` | Update decisions history and knowledge index |
| **F2.S1** | PLAN | `read_memory_bank` | Read project context and generated BRD/stories |
| **F2.S2** | PLAN | `create_implementation_plan` | Break down user stories into tasks |
| **F2.S3** | PLAN | `update_memory_bank` | Record planning decisions |
| **F3.S1** | IMPLEMENT | `read_memory_bank` | Read implementation plan, architecture, conventions |
| **F3.S2** | IMPLEMENT | `implement_code` | Write production code following standards |
| **F3.S3** | IMPLEMENT | `generate_unit_tests` | Create unit tests (backend/frontend) |
| **F3.S4** | IMPLEMENT | `update_memory_bank` | Record implementation decisions |
| **F4.S1** | REVIEW | `read_memory_bank` | Read implementation plan and criteria |
| **F4.S2** | REVIEW | `evaluate_code` | Review code against quality standards |
| **F4.S3** | REVIEW | `assign_score` | Calculate weighted score (1-10) |
| **F4.S4** | REVIEW | `generate_review_report` | Create detailed review report |
| **F4.S5** | REVIEW | `update_memory_bank` | Record review decisions |
| **F5.S1** | COMPLETE | `finalize_documentation` | Update all relevant documentation |
| **F5.S2** | COMPLETE | `update_memory_bank` | Final decisions history update |
| **F5.S3** | COMPLETE | `notify_completion` | Notify user of success |
| **F6.S1** | ESCALATE | `create_escalation_report` | Document iteration attempts and blockers |
| **F6.S2** | ESCALATE | `notify_manual_review` | Alert user for manual intervention |
| **F6.S3** | ESCALATE | `update_memory_bank` | Record escalation in lessons learned |

---

## 2. Agents Overview

| Agent | Role | Primary Outputs |
|-------|------|-----------------|
| **Orchestrator** | Workflow controller | Implementation plans, task coordination |
| **BSA** | Requirements analyst | BRDs, User Stories |
| **Coder** | Implementation | Code, Unit Tests |
| **Reviewer** | Quality assurance | Review reports, Scores |

---

## 3. Main Workflow Diagram

```mermaid
flowchart TD
    subgraph F0["F0: IDLE 🚀"]
        A[/"📥 Receive Requirement"/]
    end

    subgraph F1["F1: ANALYZE 📋"]
        B["🔍 BSA Agent"]
        B1["F1.S1: Read Memory Bank"]
        B2["F1.S2: Analyze Requirement"]
        B3["F1.S3: Generate BRD"]
        B4["F1.S4: Create User Stories"]
        B5["F1.S5: Sync to GitHub"]
        B6["F1.S6: Update Memory Bank"]
        
        B --> B1 --> B2 --> B3 --> B4 --> B5 --> B6
    end

    subgraph F2["F2: PLAN 📝"]
        C["🎯 Orchestrator"]
        C1["F2.S1: Read Memory Bank"]
        C2["F2.S2: Create Implementation Plan"]
        C3["F2.S3: Update Memory Bank"]
        
        C --> C1 --> C2 --> C3
    end

    subgraph F3["F3: IMPLEMENT 💻"]
        D["👨‍💻 Coder Agent"]
        D1["F3.S1: Read Memory Bank"]
        D2["F3.S2: Implement Code"]
        D3["F3.S3: Generate Unit Tests"]
        D4["F3.S4: Update Memory Bank"]
        
        D --> D1 --> D2 --> D3 --> D4
    end

    subgraph F4["F4: REVIEW 🔎"]
        E["📊 Reviewer Agent"]
        E1["F4.S1: Read Memory Bank"]
        E2["F4.S2: Evaluate Code"]
        E3["F4.S3: Assign Score"]
        E4["F4.S4: Generate Report"]
        E5["F4.S5: Update Memory Bank"]
        
        E --> E1 --> E2 --> E3 --> E4 --> E5
    end

    subgraph GATE["🔀 Quality Gate"]
        F{{"Score ≥ 9?"}}
    end

    subgraph ITER["🔄 Iteration Check"]
        G{{"Iterations < 5?"}}
    end

    subgraph F5["F5: COMPLETE ✅"]
        H["F5.S1: Finalize Documentation"]
        I["F5.S2-S3: Update & Notify"]
    end

    subgraph F6["F6: ESCALATE ⚠️"]
        J["F6.S1: Create Escalation Report"]
        K["F6.S2-S3: Notify & Update"]
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

    style F0 fill:#e1f5fe,stroke:#01579b
    style F1 fill:#fff3e0,stroke:#e65100
    style F2 fill:#f3e5f5,stroke:#4a148c
    style F3 fill:#e8f5e9,stroke:#1b5e20
    style F4 fill:#fce4ec,stroke:#880e4f
    style F5 fill:#c8e6c9,stroke:#2e7d32
    style F6 fill:#ffcdd2,stroke:#b71c1c
```

---

## 4. Agent Interaction Sequence

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
        Note over O,B: F1: ANALYZE Phase
        O->>B: Delegate Analysis
        B->>M: F1.S1: Read Context
        B->>B: F1.S2-S3: Analyze & Generate BRD
        B->>B: F1.S4: Create User Stories
        B->>G: F1.S5: Sync Documentation
        B->>M: F1.S6: Update Memory
        B->>O: Analysis Complete
    end

    rect rgb(243, 229, 245)
        Note over O: F2: PLAN Phase
        O->>M: F2.S1: Read Context
        O->>O: F2.S2: Create Implementation Plan
        O->>M: F2.S3: Update Memory
    end

    loop Max 5 Iterations
        rect rgb(232, 245, 233)
            Note over O,C: F3: IMPLEMENT Phase
            O->>C: Assign Implementation
            C->>M: F3.S1: Read Context
            C->>C: F3.S2: Implement Code
            C->>C: F3.S3: Generate Tests
            C->>M: F3.S4: Update Memory
            C->>O: Implementation Ready
        end

        rect rgb(252, 228, 236)
            Note over O,R: F4: REVIEW Phase
            O->>R: Request Review
            R->>M: F4.S1: Read Context
            R->>R: F4.S2: Evaluate Code
            R->>R: F4.S3: Assign Score
            R->>R: F4.S4: Generate Report
            R->>M: F4.S5: Update Memory
            R->>O: Score: X/10
        end

        alt Score >= 9 → F5
            O->>U: ✅ F5: Implementation Approved
        else Score < 9 AND Iterations < 5 → F3
            O->>C: Revise with Feedback (back to F3)
        else Score < 9 AND Iterations >= 5 → F6
            O->>U: ⚠️ F6: Escalate to Manual Review
        end
    end
```

---

## 5. Memory Protocol Flow

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

## 6. Skills Distribution

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

## 7. Quality Gate Decision Tree (F4)

```mermaid
flowchart TD
    A["F3.S4: Code Submitted"] --> B{"F4: Score Evaluation"}
    
    B --> C["Code Quality<br/>25%"]
    B --> D["Test Coverage<br/>20%"]
    B --> E["Architecture<br/>20%"]
    B --> F["Documentation<br/>15%"]
    B --> G["Security<br/>10%"]
    B --> H["Performance<br/>10%"]
    
    C & D & E & F & G & H --> I["F4.S3: Calculate Total Score"]
    
    I --> J{{"Score ≥ 9?"}}
    
    J -->|"✅ Yes"| K["F5: Approved"]
    J -->|"❌ No"| L{{"Iteration < 5?"}}
    
    L -->|"Yes"| M["→ F3: Return to Coder<br/>with Feedback"]
    L -->|"No"| N["→ F6: Escalate to<br/>Manual Review"]

    style K fill:#c8e6c9,stroke:#2e7d32
    style N fill:#ffcdd2,stroke:#b71c1c
    style M fill:#fff9c4,stroke:#f9a825
```

---

## 8. File Output Structure

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
        B["BSA (F1)"] --> BRD
        B --> US
        O["Orchestrator (F2)"] --> IP
        R["Reviewer (F4)"] --> REV
        C["Coder (F3)"] --> UT
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
