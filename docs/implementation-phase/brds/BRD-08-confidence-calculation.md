# BRD-08: Confidence Calculation Engine

**Document ID:** BRD-08
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 9 of 19

---

## 1. Executive Summary

Implement the confidence calculation engine per RF-12: `final_confidence = min(S, J)` where S is structural confidence and J is judge confidence. This BRD covers the formula components, source independence scoring (RF-15), and confidence mismatch detection.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-12 | Confidence formula min(S, J) | Complete |
| RF-15 | Source independence (diversity) | Complete |
| RF-15 | Confidence mismatch detection | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| BRD-02, BRD-07 | BRD-09 |

---

## 4. Technical Specification

### 4.1 File Structure

```
backend/
  app/
    confidence/
      __init__.py
      calculator.py       # Main calculation logic
      structural.py       # Structural components (S)
      diversity.py        # Source diversity scoring
      mismatch.py         # S/J mismatch detection
```

### 4.2 Confidence Formula

```
final_confidence = min(S, J)

where:
  S = 0.35·C_coverage + 0.30·C_agreement + 0.20·C_diversity + 0.15·C_no_conflict
  
  C_coverage   = |covered_claims| / |total_claims|
  C_agreement  = weighted_agreement_score  
  C_diversity  = source_diversity_score
  C_no_conflict = 1 - (contradictions / evidence_count)
  
  J = judge.confidence (from JudgeVerdict)
```

### 4.3 Structural Calculator

#### backend/app/confidence/structural.py

```python
"""Structural confidence calculation (S component)."""

from dataclasses import dataclass
from app.agent.run_state import RunState, EvidenceItem
from app.domain.confidence import StructuralConfidence


@dataclass
class StructuralWeights:
    """Weights for structural confidence components."""

    coverage: float = 0.35
    agreement: float = 0.30
    diversity: float = 0.20
    no_conflict: float = 0.15


def calculate_coverage(state: RunState) -> float:
    """Calculate claim coverage ratio.
    
    C_coverage = |covered_claims| / |total_claims|
    """
    if not state.sub_claims:
        return 0.0
    return len(state.covered_claims) / len(state.sub_claims)


def calculate_agreement(evidence: list[EvidenceItem]) -> float:
    """Calculate evidence agreement score.
    
    Agreement = proportion of evidence with 'supports' polarity,
    weighted by confidence.
    """
    if not evidence:
        return 0.0

    total_weight = sum(e.confidence for e in evidence)
    if total_weight == 0:
        return 0.0

    supporting_weight = sum(
        e.confidence for e in evidence if e.polarity == "supports"
    )

    return supporting_weight / total_weight


def calculate_diversity(evidence: list[EvidenceItem]) -> float:
    """Calculate source diversity score (RF-15).
    
    Diversity rewards evidence from multiple independent sources.
    Score based on unique domains.
    """
    if not evidence:
        return 0.0

    # Extract unique domains
    domains = set()
    for e in evidence:
        # Simple domain extraction
        url = e.source_url
        if "://" in url:
            url = url.split("://")[1]
        domain = url.split("/")[0].replace("www.", "")
        domains.add(domain)

    # Score based on number of unique domains
    # 1 domain = 0.3, 2 = 0.5, 3 = 0.7, 4+ = 0.9, 5+ = 1.0
    n = len(domains)
    if n >= 5:
        return 1.0
    if n >= 4:
        return 0.9
    if n >= 3:
        return 0.7
    if n >= 2:
        return 0.5
    return 0.3


def calculate_no_conflict(state: RunState) -> float:
    """Calculate absence of contradictions.
    
    C_no_conflict = 1 - (contradictions / max(evidence_count, 1))
    """
    evidence_count = len(state.evidence)
    contradiction_count = len(state.contradictions)

    if evidence_count == 0:
        return 1.0  # No evidence = no conflict

    conflict_ratio = contradiction_count / evidence_count
    return max(0.0, 1.0 - conflict_ratio)


def calculate_structural_confidence(
    state: RunState,
    weights: StructuralWeights | None = None,
) -> StructuralConfidence:
    """Calculate full structural confidence.
    
    Returns StructuralConfidence with all components and final score.
    """
    if weights is None:
        weights = StructuralWeights()

    coverage = calculate_coverage(state)
    agreement = calculate_agreement(state.evidence)
    diversity = calculate_diversity(state.evidence)
    no_conflict = calculate_no_conflict(state)

    return StructuralConfidence(
        coverage=coverage,
        agreement=agreement,
        diversity=diversity,
        no_conflict=no_conflict,
    )
```

### 4.4 Main Calculator

#### backend/app/confidence/calculator.py

```python
"""Main confidence calculation engine."""

from app.agent.run_state import RunState
from app.confidence.structural import calculate_structural_confidence
from app.confidence.mismatch import detect_mismatch, MismatchResult
from app.domain.confidence import ConfidenceResult, StructuralConfidence


class ConfidenceCalculator:
    """Calculate final confidence using min(S, J) formula."""

    def __init__(self, threshold: float = 0.7) -> None:
        self.threshold = threshold

    def calculate(
        self,
        state: RunState,
        judge_confidence: float,
    ) -> ConfidenceResult:
        """Calculate final confidence.
        
        Args:
            state: Current run state with evidence
            judge_confidence: J from judge evaluation
            
        Returns:
            ConfidenceResult with all components
        """
        # Calculate structural confidence S
        structural = calculate_structural_confidence(state)
        s_score = structural.score

        # Final = min(S, J)
        final = min(s_score, judge_confidence)

        # Check if passes threshold
        passed = final >= self.threshold

        return ConfidenceResult(
            structural=structural,
            judge=judge_confidence,
            final=final,
            threshold=self.threshold,
            passed=passed,
        )

    def check_sufficient(
        self,
        state: RunState,
    ) -> bool:
        """Check if evidence is sufficient to proceed to judging.
        
        Called before expensive judge LLM call.
        Returns True if structural signals suggest readiness.
        """
        structural = calculate_structural_confidence(state)
        
        # Minimum thresholds for proceeding
        return (
            structural.coverage >= 0.6  # At least 60% claims covered
            and structural.agreement >= 0.5  # Majority supporting
            and structural.no_conflict >= 0.7  # Few contradictions
        )
```

### 4.5 Mismatch Detection

#### backend/app/confidence/mismatch.py

```python
"""Confidence mismatch detection (RF-15)."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MismatchResult:
    """Result of mismatch detection."""

    has_mismatch: bool
    structural: float
    judge: float
    divergence: float
    trust_flag: Optional[str]


def detect_mismatch(
    structural: float,
    judge: float,
    threshold: float = 0.2,
) -> MismatchResult:
    """Detect significant divergence between S and J.
    
    If |S - J| > threshold, flag for user attention.
    
    Args:
        structural: S score
        judge: J score
        threshold: Divergence threshold (default 0.2)
        
    Returns:
        MismatchResult with trust flag if mismatch detected
    """
    divergence = abs(structural - judge)
    has_mismatch = divergence > threshold

    trust_flag: Optional[str] = None
    if has_mismatch:
        if structural > judge:
            trust_flag = (
                f"Structural metrics ({structural:.0%}) exceed judge assessment "
                f"({judge:.0%}). Judge may have identified issues not captured "
                f"in automated scoring."
            )
        else:
            trust_flag = (
                f"Judge assessment ({judge:.0%}) exceeds structural metrics "
                f"({structural:.0%}). Evidence may be stronger than coverage "
                f"metrics suggest."
            )

    return MismatchResult(
        has_mismatch=has_mismatch,
        structural=structural,
        judge=judge,
        divergence=divergence,
        trust_flag=trust_flag,
    )
```

### 4.6 Package Exports

#### backend/app/confidence/__init__.py

```python
"""Confidence calculation package."""

from app.confidence.calculator import ConfidenceCalculator
from app.confidence.structural import (
    calculate_structural_confidence,
    calculate_coverage,
    calculate_agreement,
    calculate_diversity,
    calculate_no_conflict,
)
from app.confidence.mismatch import detect_mismatch, MismatchResult

__all__ = [
    "ConfidenceCalculator",
    "calculate_structural_confidence",
    "calculate_coverage",
    "calculate_agreement",
    "calculate_diversity",
    "calculate_no_conflict",
    "detect_mismatch",
    "MismatchResult",
]
```

---

## 5. Acceptance Criteria

### AC-01: Coverage Calculation Correct
```gherkin
Given 3 sub-claims with 2 covered
When I calculate coverage
Then coverage = 2/3 ≈ 0.67
```

### AC-02: Diversity Rewards Multiple Sources
```gherkin
Given evidence from wikipedia.org and example.com
When I calculate diversity
Then diversity = 0.5 (2 sources)
Given evidence from 5 different domains
Then diversity = 1.0
```

### AC-03: Final Uses min(S, J)
```gherkin
Given S = 0.8 and J = 0.6
When I calculate final confidence
Then final = 0.6 (min)
Given S = 0.5 and J = 0.9
Then final = 0.5 (min)
```

### AC-04: Mismatch Detected When Divergent
```gherkin
Given S = 0.85 and J = 0.55
When I detect mismatch with threshold 0.2
Then has_mismatch = True
  And trust_flag explains the divergence
```

### AC-05: Threshold Gating Works
```gherkin
Given threshold = 0.7 and final = 0.75
When I check passed
Then passed = True
Given final = 0.65
Then passed = False
```

---

## 6. Implementation Checklist

- [ ] Create `backend/app/confidence/__init__.py`
- [ ] Create `backend/app/confidence/structural.py`
- [ ] Create `backend/app/confidence/calculator.py`
- [ ] Create `backend/app/confidence/mismatch.py`
- [ ] Write unit tests for each component
- [ ] Write integration tests with sample RunState
- [ ] Verify formula matches RF-12 specification

## 7. Testing Strategy

| Test Type | Tool | Target | Coverage |
|-----------|------|--------|----------|
| Unit | pytest | Each calculation function | 100% |
| Unit | pytest | Edge cases (no evidence, etc.) | 100% |
| Integration | pytest | Full calculation flow | 100% |

## 8. Environment Variables

_None required._

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Formula tweaking needed | Low | Med | Weights configurable |
| Diversity gaming | Low | Low | Domain normalization |
| Division by zero | High | Low | Guard clauses |

## 10. Out of Scope

- Adaptive threshold (user sets manually)
- Historical calibration
- Per-question-type weights
