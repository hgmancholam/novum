"""LLM prompts for ReAct loop (IP-25 Phase E T-25-E-03)."""

REACT_THOUGHT_PROMPT = """You are a research agent performing abductive reasoning to answer a complex question.

## Current Question
{question}

## Active Hypotheses
{hypotheses}

## Interaction History
{history}

## Your Task
Think carefully about what information you need next to evaluate the hypotheses. Consider:
- Which hypothesis needs more evidence?
- What specific facts would confirm or refute a hypothesis?
- Are there gaps in your understanding that need filling?

Generate a single, focused thought about your next reasoning step (1-2 sentences).
"""

REACT_ACTION_PROMPT = """Based on your thought, select the best action to take next.

## Available Actions
1. **search**: Query sources (web/Wikipedia) for information
2. **deep_fetch**: Retrieve full content from a specific URL
3. **evaluate_hypothesis**: Mark a hypothesis as confirmed or refuted based on gathered evidence
4. **finish**: Complete the reasoning loop (use when ready for synthesis or when stuck)

## Current Context
Question: {question}
Active Hypotheses: {hypotheses}
Your Thought: {thought}

## Guidelines
- Use **search** when you need new information
- Use **deep_fetch** when you found a promising source but need full content
- Use **evaluate_hypothesis** only when you have strong evidence
- Use **finish** when you've evaluated enough or reached the step limit

Choose the most appropriate action and provide required parameters.
"""

REACT_HISTORY_SUMMARIZATION_PROMPT = """Summarize the ReAct loop history below into a concise paragraph (≤200 tokens) preserving key findings.

## History to Summarize
{history_text}

## Requirements
- Preserve key evidence discovered
- Note which hypotheses were evaluated and their verdicts
- Highlight critical insights or contradictions
- Omit redundant details

Generate a summary paragraph that captures the essence of this reasoning sequence.
"""
