# Example Questions for Testing the Research Agent

The progression below moves from:
- simple factual retrieval,
- to ambiguity handling,
- to contradiction analysis,
- to multi-step reasoning,
- to uncertainty management,
- to open-ended research synthesis.

---

# 1. Trivial Fact Retrieval

## Question
```text
What is the capital of Japan?
```

## What this tests
- Basic retrieval
- Ability to stop quickly
- Avoiding unnecessary searches

## Expected behavior
The agent should:
- Find a reliable source quickly
- Determine confidence is extremely high
- Stop almost immediately

---

# 2. Simple Comparative Research

## Question
```text
Is PostgreSQL or MongoDB better for a small SaaS application?
```

## What this tests
- Comparison reasoning
- Criteria generation
- Structured synthesis

## Expected behavior
The agent should:
- Define evaluation dimensions
- Compare tradeoffs
- Recognize context dependency
- Avoid absolute answers

---

# 3. Ambiguous Question Handling

## Question
```text
What is the best programming language?
```

## What this tests
- Ambiguity detection
- Clarification reasoning
- Multi-dimensional evaluation

## Expected behavior
The agent should recognize:
- “Best” is undefined
- Different criteria produce different answers
- The question lacks context

Good behavior:

```text
The question is ambiguous because “best” depends on:
- Performance
- Developer productivity
- Ecosystem
- Learning curve
- Scalability
```

---

# 4. Contradictory Sources

## Question
```text
Is intermittent fasting healthy?
```

## What this tests
- Contradiction handling
- Evidence weighting
- Source quality evaluation

## Expected behavior
The agent should:
- Detect disagreement between studies
- Prioritize stronger evidence
- Explain uncertainty clearly

Good behavior:

```text
Some studies report metabolic benefits,
while others indicate risks for certain populations.
Current evidence is promising but not universally conclusive.
```

---

# 5. Sparse or Weak Information

## Question
```text
What are the long-term risks of AI-generated code in enterprise systems?
```

## What this tests
- Handling incomplete evidence
- Synthesizing emerging knowledge
- Avoiding hallucinations

## Expected behavior
The agent should:
- Acknowledge limited long-term data
- Combine industry reports and expert opinions
- Clearly separate evidence from speculation

---

# 6. Multi-Step Technical Research

## Question
```text
Should a high-scale AI platform use event-driven architecture or synchronous microservices?
```

## What this tests
- Architecture reasoning
- Multi-factor analysis
- Complex tradeoffs

## Expected behavior
The agent should evaluate:
- Scalability
- Latency
- Reliability
- Operational complexity
- Observability
- Cost
- Team maturity

The answer should NOT be binary.

---

# 7. Deep Research With Dynamic Stopping

## Question
```text
What is the most promising approach for long-term memory in autonomous AI agents?
```

## What this tests
- Iterative research depth
- Dynamic stopping decisions
- Research planning
- Technical synthesis

## Expected behavior
The agent should:
- Compare vector memory, graph memory, episodic memory, hybrid systems
- Identify active research areas
- Detect unresolved problems
- Decide when evidence is sufficient

This is close to the actual spirit of the challenge.

---

# 8. Open-Ended Complex Research Problem

## Question
```text
Could AI systems realistically replace mid-level software engineers within the next 10 years?
```

## What this tests
- Open-ended reasoning
- Economic analysis
- Technological forecasting
- Contradictory evidence
- Uncertainty modeling
- Multi-domain synthesis

## Expected behavior
The agent should analyze:
- Current AI capabilities
- Productivity trends
- Industry adoption
- Economic incentives
- Regulatory concerns
- Human oversight requirements
- Historical technology displacement patterns

The system should NOT produce a simplistic yes/no answer.

A strong answer would include:
- Confidence estimation
- Multiple scenarios
- Explicit uncertainty
- Contradictions between experts
- Clear explanation of assumptions

---

# What Makes These Questions Valuable

These questions progressively test:

| Capability | Example |
|---|---|
| Fast stopping | Capital of Japan |
| Comparative reasoning | PostgreSQL vs MongoDB |
| Ambiguity handling | Best programming language |
| Contradiction handling | Intermittent fasting |
| Sparse evidence | AI-generated code risks |
| Multi-factor architecture reasoning | Event-driven vs synchronous |
| Dynamic research depth | AI memory systems |
| Open-ended synthesis | Replacing software engineers |

---

# What Interviewers Will Likely Observe During These Runs

They will pay attention to:

- How the agent decomposes the problem
- Whether searches are purposeful
- Whether evidence quality is evaluated
- Whether contradictions are detected
- Whether uncertainty is acknowledged
- Whether the stop decision is defendable
- Whether the reasoning trace is inspectable
- Whether the system avoids fake certainty

The quality of the reasoning process matters more than the final answer itself.