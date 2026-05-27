"""Confidence calculation models (RF-12)."""

from pydantic import BaseModel, ConfigDict, Field


class StructuralConfidence(BaseModel):
    """Structural confidence components.

    WP-3 amendment (2026-05-27):
    S = 0.35·C_coverage + 0.30·C_agreement + 0.20·C_diversity + 0.05·C_no_conflict + 0.10·C_kind_appropriateness

    Weights adjusted: C_no_conflict 0.15→0.05, added C_kind_appropriateness 0.10.
    """

    model_config = ConfigDict(extra="allow")

    coverage: float = Field(..., ge=0.0, le=1.0, description="C_coverage: % of claims covered")
    agreement: float = Field(..., ge=0.0, le=1.0, description="C_agreement: evidence alignment")
    diversity: float = Field(..., ge=0.0, le=1.0, description="C_diversity: source independence")
    no_conflict: float = Field(
        ..., ge=0.0, le=1.0, description="C_no_conflict: absence of contradictions"
    )
    kind_appropriateness: float = Field(
        1.0, ge=0.0, le=1.0, description="C_kind_appropriateness: AnswerKind fits question (WP-3)"
    )

    @property
    def score(self) -> float:
        """Weighted structural score S_raw (WP-3 formula)."""
        return (
            0.35 * self.coverage
            + 0.30 * self.agreement
            + 0.20 * self.diversity
            + 0.05 * self.no_conflict
            + 0.10 * self.kind_appropriateness
        )


class ConfidenceResult(BaseModel):
    """Full confidence calculation result."""

    model_config = ConfigDict(extra="allow")

    structural: StructuralConfidence
    judge: float = Field(..., ge=0.0, le=1.0, description="J: Judge confidence")
    final: float = Field(..., ge=0.0, le=1.0, description="min(S, J)")
    threshold: float = Field(..., ge=0.0, le=1.0, description="User-set threshold")
    passed: bool = Field(..., description="final >= threshold")
