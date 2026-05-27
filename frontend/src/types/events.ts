// Auto-generated from Pydantic models — DO NOT EDIT
// Source: scripts/export_types.py (BRD-02)
// Generated: 2026-05-27T05:41:38.024438+00:00

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type StopReason =
  | "judge_confirmed"
  | "honest_unanswerable"
  | "honest_contradiction"
  | "honest_ambiguous"
  | "stopped_by_budget"
  | "user_cancelled"
  | "errored";

export type QuestionType =
  | "factual"
  | "comparative"
  | "definitional"
  | "state_of_art"
  | "causal";

export type OutputFormat =
  | "prose"
  | "structured";

export type EvidencePolarity =
  | "supports"
  | "contradicts"
  | "neutral";

export type SourceType =
  | "tavily"
  | "wikipedia";

export type EventType =
  | "QuestionAsked"
  | "QuestionNormalized"
  | "PlanCreated"
  | "PlanCritiqued"
  | "PlanRevised"
  | "ToolCalled"
  | "EvidenceAdded"
  | "ClaimCovered"
  | "ClaimUncoverable"
  | "SourceFailed"
  | "AmbiguityDetected"
  | "ContradictionDetected"
  | "ContradictionResolved"
  | "UserContextChallenged"
  | "JudgeRuled"
  | "ConfidenceMismatch"
  | "AgentErrored"
  | "ResumedAfterError"
  | "ResumedAfterCancel"
  | "Stopped";

// ---------------------------------------------------------------------------
// Forkable events (RF-03): user-selectable branch points.
// ---------------------------------------------------------------------------

export const FORKABLE_EVENTS: readonly EventType[] = ["PlanCreated", "AmbiguityDetected", "ContradictionDetected", "JudgeRuled", "Stopped"] as const;

// ---------------------------------------------------------------------------
// JSON Schema for runtime validation
// ---------------------------------------------------------------------------

export const EventSchema = {
  "$defs": {
    "AgentErroredEvent": {
      "additionalProperties": true,
      "description": "Unrecoverable error during execution.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "AgentErrored",
          "default": "AgentErrored",
          "title": "Type",
          "type": "string"
        },
        "error_type": {
          "title": "Error Type",
          "type": "string"
        },
        "error_message": {
          "title": "Error Message",
          "type": "string"
        },
        "stack_trace": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Stack Trace"
        },
        "recoverable": {
          "title": "Recoverable",
          "type": "boolean"
        },
        "recovery_suggestion": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Recovery Suggestion"
        }
      },
      "required": [
        "error_type",
        "error_message",
        "recoverable"
      ],
      "title": "AgentErroredEvent",
      "type": "object"
    },
    "AmbiguityDetectedEvent": {
      "additionalProperties": true,
      "description": "Question ambiguity detected (RF-04).",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "AmbiguityDetected",
          "default": "AmbiguityDetected",
          "title": "Type",
          "type": "string"
        },
        "ambiguous_phrase": {
          "title": "Ambiguous Phrase",
          "type": "string"
        },
        "possible_interpretations": {
          "items": {
            "type": "string"
          },
          "title": "Possible Interpretations",
          "type": "array"
        },
        "clarification_needed": {
          "title": "Clarification Needed",
          "type": "string"
        }
      },
      "required": [
        "ambiguous_phrase",
        "possible_interpretations",
        "clarification_needed"
      ],
      "title": "AmbiguityDetectedEvent",
      "type": "object"
    },
    "AnswerSection": {
      "additionalProperties": true,
      "description": "Section of a structured answer.",
      "properties": {
        "heading": {
          "title": "Heading",
          "type": "string"
        },
        "content": {
          "title": "Content",
          "type": "string"
        }
      },
      "required": [
        "heading",
        "content"
      ],
      "title": "AnswerSection",
      "type": "object"
    },
    "Citation": {
      "additionalProperties": true,
      "description": "Citation reference in the answer.",
      "properties": {
        "id": {
          "title": "Id",
          "type": "integer"
        },
        "url": {
          "title": "Url",
          "type": "string"
        },
        "title": {
          "title": "Title",
          "type": "string"
        }
      },
      "required": [
        "id",
        "url",
        "title"
      ],
      "title": "Citation",
      "type": "object"
    },
    "ClaimCoveredEvent": {
      "additionalProperties": true,
      "description": "Sub-claim has sufficient evidence.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "ClaimCovered",
          "default": "ClaimCovered",
          "title": "Type",
          "type": "string"
        },
        "claim_id": {
          "title": "Claim Id",
          "type": "string"
        },
        "claim_text": {
          "title": "Claim Text",
          "type": "string"
        },
        "evidence_ids": {
          "items": {
            "format": "uuid",
            "type": "string"
          },
          "title": "Evidence Ids",
          "type": "array"
        },
        "coverage_rationale": {
          "title": "Coverage Rationale",
          "type": "string"
        }
      },
      "required": [
        "claim_id",
        "claim_text",
        "evidence_ids",
        "coverage_rationale"
      ],
      "title": "ClaimCoveredEvent",
      "type": "object"
    },
    "ClaimUncoverableEvent": {
      "additionalProperties": true,
      "description": "Sub-claim cannot be answered with available sources.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "ClaimUncoverable",
          "default": "ClaimUncoverable",
          "title": "Type",
          "type": "string"
        },
        "claim_id": {
          "title": "Claim Id",
          "type": "string"
        },
        "claim_text": {
          "title": "Claim Text",
          "type": "string"
        },
        "reason": {
          "title": "Reason",
          "type": "string"
        },
        "attempted_sources": {
          "items": {
            "$ref": "#/$defs/SourceType"
          },
          "title": "Attempted Sources",
          "type": "array"
        }
      },
      "required": [
        "claim_id",
        "claim_text",
        "reason",
        "attempted_sources"
      ],
      "title": "ClaimUncoverableEvent",
      "type": "object"
    },
    "ConfidenceMismatchEvent": {
      "additionalProperties": true,
      "description": "S and J diverge significantly (RF-15).",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "ConfidenceMismatch",
          "default": "ConfidenceMismatch",
          "title": "Type",
          "type": "string"
        },
        "structural_confidence": {
          "title": "Structural Confidence",
          "type": "number"
        },
        "judge_confidence": {
          "title": "Judge Confidence",
          "type": "number"
        },
        "divergence": {
          "title": "Divergence",
          "type": "number"
        },
        "trust_flag": {
          "title": "Trust Flag",
          "type": "string"
        }
      },
      "required": [
        "structural_confidence",
        "judge_confidence",
        "divergence",
        "trust_flag"
      ],
      "title": "ConfidenceMismatchEvent",
      "type": "object"
    },
    "ContradictionDetectedEvent": {
      "additionalProperties": true,
      "description": "Irreconcilable source conflict (RF-04).",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "ContradictionDetected",
          "default": "ContradictionDetected",
          "title": "Type",
          "type": "string"
        },
        "claim_id": {
          "title": "Claim Id",
          "type": "string"
        },
        "source_a": {
          "$ref": "#/$defs/ContradictionSource"
        },
        "source_b": {
          "$ref": "#/$defs/ContradictionSource"
        },
        "nature_of_conflict": {
          "title": "Nature Of Conflict",
          "type": "string"
        }
      },
      "required": [
        "claim_id",
        "source_a",
        "source_b",
        "nature_of_conflict"
      ],
      "title": "ContradictionDetectedEvent",
      "type": "object"
    },
    "ContradictionResolvedEvent": {
      "additionalProperties": true,
      "description": "Contradiction resolved through additional evidence.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "ContradictionResolved",
          "default": "ContradictionResolved",
          "title": "Type",
          "type": "string"
        },
        "original_contradiction_id": {
          "format": "uuid",
          "title": "Original Contradiction Id",
          "type": "string"
        },
        "resolution": {
          "title": "Resolution",
          "type": "string"
        },
        "winning_source": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Winning Source"
        },
        "rationale": {
          "title": "Rationale",
          "type": "string"
        }
      },
      "required": [
        "original_contradiction_id",
        "resolution",
        "rationale"
      ],
      "title": "ContradictionResolvedEvent",
      "type": "object"
    },
    "ContradictionSource": {
      "additionalProperties": true,
      "description": "A source involved in a contradiction.",
      "properties": {
        "url": {
          "title": "Url",
          "type": "string"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "claim": {
          "title": "Claim",
          "type": "string"
        }
      },
      "required": [
        "url",
        "title",
        "claim"
      ],
      "title": "ContradictionSource",
      "type": "object"
    },
    "EvidenceAddedEvent": {
      "additionalProperties": true,
      "description": "Evidence collected from a source.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "EvidenceAdded",
          "default": "EvidenceAdded",
          "title": "Type",
          "type": "string"
        },
        "source_type": {
          "$ref": "#/$defs/SourceType"
        },
        "source_url": {
          "title": "Source Url",
          "type": "string"
        },
        "source_title": {
          "title": "Source Title",
          "type": "string"
        },
        "extracted_text": {
          "title": "Extracted Text",
          "type": "string"
        },
        "polarity": {
          "$ref": "#/$defs/EvidencePolarity"
        },
        "target_claim_id": {
          "title": "Target Claim Id",
          "type": "string"
        },
        "confidence": {
          "title": "Confidence",
          "type": "number"
        }
      },
      "required": [
        "source_type",
        "source_url",
        "source_title",
        "extracted_text",
        "polarity",
        "target_claim_id",
        "confidence"
      ],
      "title": "EvidenceAddedEvent",
      "type": "object"
    },
    "EvidencePolarity": {
      "description": "Polarity of evidence toward a claim.",
      "enum": [
        "supports",
        "contradicts",
        "neutral"
      ],
      "title": "EvidencePolarity",
      "type": "string"
    },
    "JudgeRuledEvent": {
      "additionalProperties": true,
      "description": "Judge LLM evaluation (RF-12).",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "JudgeRuled",
          "default": "JudgeRuled",
          "title": "Type",
          "type": "string"
        },
        "judge_model": {
          "title": "Judge Model",
          "type": "string"
        },
        "judge_confidence": {
          "title": "Judge Confidence",
          "type": "number"
        },
        "structural_confidence": {
          "title": "Structural Confidence",
          "type": "number"
        },
        "final_confidence": {
          "title": "Final Confidence",
          "type": "number"
        },
        "threshold": {
          "title": "Threshold",
          "type": "number"
        },
        "passed": {
          "title": "Passed",
          "type": "boolean"
        },
        "rationale": {
          "title": "Rationale",
          "type": "string"
        },
        "suggested_improvements": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Suggested Improvements"
        }
      },
      "required": [
        "judge_model",
        "judge_confidence",
        "structural_confidence",
        "final_confidence",
        "threshold",
        "passed",
        "rationale"
      ],
      "title": "JudgeRuledEvent",
      "type": "object"
    },
    "PlanCreatedEvent": {
      "additionalProperties": true,
      "description": "Initial plan with sub-claims decomposition.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "PlanCreated",
          "default": "PlanCreated",
          "title": "Type",
          "type": "string"
        },
        "sub_claims": {
          "items": {
            "$ref": "#/$defs/SubClaim"
          },
          "title": "Sub Claims",
          "type": "array"
        },
        "rationale": {
          "title": "Rationale",
          "type": "string"
        }
      },
      "required": [
        "sub_claims",
        "rationale"
      ],
      "title": "PlanCreatedEvent",
      "type": "object"
    },
    "PlanCritiquedEvent": {
      "additionalProperties": true,
      "description": "Plan critic evaluation (RF-14).",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "PlanCritiqued",
          "default": "PlanCritiqued",
          "title": "Type",
          "type": "string"
        },
        "critique": {
          "title": "Critique",
          "type": "string"
        },
        "issues": {
          "items": {
            "type": "string"
          },
          "title": "Issues",
          "type": "array"
        },
        "suggested_changes": {
          "items": {
            "type": "string"
          },
          "title": "Suggested Changes",
          "type": "array"
        },
        "acceptable": {
          "title": "Acceptable",
          "type": "boolean"
        }
      },
      "required": [
        "critique",
        "issues",
        "suggested_changes",
        "acceptable"
      ],
      "title": "PlanCritiquedEvent",
      "type": "object"
    },
    "PlanRevisedEvent": {
      "additionalProperties": true,
      "description": "Plan updated after critique.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "PlanRevised",
          "default": "PlanRevised",
          "title": "Type",
          "type": "string"
        },
        "previous_sub_claims": {
          "items": {
            "$ref": "#/$defs/SubClaim"
          },
          "title": "Previous Sub Claims",
          "type": "array"
        },
        "new_sub_claims": {
          "items": {
            "$ref": "#/$defs/SubClaim"
          },
          "title": "New Sub Claims",
          "type": "array"
        },
        "revision_rationale": {
          "title": "Revision Rationale",
          "type": "string"
        },
        "attempt_number": {
          "title": "Attempt Number",
          "type": "integer"
        }
      },
      "required": [
        "previous_sub_claims",
        "new_sub_claims",
        "revision_rationale",
        "attempt_number"
      ],
      "title": "PlanRevisedEvent",
      "type": "object"
    },
    "QuestionAskedEvent": {
      "additionalProperties": true,
      "description": "Initial question submitted by user.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "QuestionAsked",
          "default": "QuestionAsked",
          "title": "Type",
          "type": "string"
        },
        "question": {
          "title": "Question",
          "type": "string"
        },
        "user_context": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "User Context"
        },
        "detected_question_type": {
          "anyOf": [
            {
              "$ref": "#/$defs/QuestionType"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "question"
      ],
      "title": "QuestionAskedEvent",
      "type": "object"
    },
    "QuestionNormalizedEvent": {
      "additionalProperties": true,
      "description": "Grammar/typo normalization of the user's question.\n\nEmitted right after :class:`QuestionAskedEvent` and before the classifier\nso the UI can show immediate feedback (\u201cBuscando informaci\u00f3n sobre\u2026\u201d)\neven when the original input had typos or informal phrasing. Downstream\nLLM steps use ``normalized_question`` instead of the raw input.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "QuestionNormalized",
          "default": "QuestionNormalized",
          "title": "Type",
          "type": "string"
        },
        "original_question": {
          "title": "Original Question",
          "type": "string"
        },
        "normalized_question": {
          "title": "Normalized Question",
          "type": "string"
        },
        "was_corrected": {
          "title": "Was Corrected",
          "type": "boolean"
        },
        "language": {
          "title": "Language",
          "type": "string"
        }
      },
      "required": [
        "original_question",
        "normalized_question",
        "was_corrected",
        "language"
      ],
      "title": "QuestionNormalizedEvent",
      "type": "object"
    },
    "QuestionType": {
      "description": "Supported question types (RF-06).",
      "enum": [
        "factual",
        "comparative",
        "definitional",
        "state_of_art",
        "causal"
      ],
      "title": "QuestionType",
      "type": "string"
    },
    "ResumedAfterCancelEvent": {
      "additionalProperties": true,
      "description": "Run resumed after user cancellation.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "ResumedAfterCancel",
          "default": "ResumedAfterCancel",
          "title": "Type",
          "type": "string"
        },
        "cancel_event_id": {
          "format": "uuid",
          "title": "Cancel Event Id",
          "type": "string"
        },
        "resume_point": {
          "title": "Resume Point",
          "type": "string"
        }
      },
      "required": [
        "cancel_event_id",
        "resume_point"
      ],
      "title": "ResumedAfterCancelEvent",
      "type": "object"
    },
    "ResumedAfterErrorEvent": {
      "additionalProperties": true,
      "description": "Run resumed after an error.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "ResumedAfterError",
          "default": "ResumedAfterError",
          "title": "Type",
          "type": "string"
        },
        "original_error_event_id": {
          "format": "uuid",
          "title": "Original Error Event Id",
          "type": "string"
        },
        "resume_point": {
          "title": "Resume Point",
          "type": "string"
        }
      },
      "required": [
        "original_error_event_id",
        "resume_point"
      ],
      "title": "ResumedAfterErrorEvent",
      "type": "object"
    },
    "SourceFailedEvent": {
      "additionalProperties": true,
      "description": "Source plugin returned an error.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "SourceFailed",
          "default": "SourceFailed",
          "title": "Type",
          "type": "string"
        },
        "source_type": {
          "$ref": "#/$defs/SourceType"
        },
        "query": {
          "title": "Query",
          "type": "string"
        },
        "error_message": {
          "title": "Error Message",
          "type": "string"
        },
        "recoverable": {
          "title": "Recoverable",
          "type": "boolean"
        }
      },
      "required": [
        "source_type",
        "query",
        "error_message",
        "recoverable"
      ],
      "title": "SourceFailedEvent",
      "type": "object"
    },
    "SourceType": {
      "description": "Source plugin identifiers.",
      "enum": [
        "tavily",
        "wikipedia"
      ],
      "title": "SourceType",
      "type": "string"
    },
    "StopReason": {
      "description": "Terminal states for a run (RF-01).\n\nThese are guarantees, not errors:\n- 4 honest stops (judge_confirmed, honest_*)\n- 1 budget safety net\n- 1 user action\n- 1 error state",
      "enum": [
        "judge_confirmed",
        "honest_unanswerable",
        "honest_contradiction",
        "honest_ambiguous",
        "stopped_by_budget",
        "user_cancelled",
        "errored"
      ],
      "title": "StopReason",
      "type": "string"
    },
    "StoppedEvent": {
      "additionalProperties": true,
      "description": "Terminal event with final answer or honest stop.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "Stopped",
          "default": "Stopped",
          "title": "Type",
          "type": "string"
        },
        "stop_reason": {
          "$ref": "#/$defs/StopReason"
        },
        "answer_prose": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Answer Prose"
        },
        "answer_sections": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/AnswerSection"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Answer Sections"
        },
        "citations": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/Citation"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Citations"
        },
        "honest_explanation": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Honest Explanation"
        },
        "total_tokens": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Total Tokens"
        },
        "total_duration_seconds": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Total Duration Seconds"
        }
      },
      "required": [
        "stop_reason"
      ],
      "title": "StoppedEvent",
      "type": "object"
    },
    "SubClaim": {
      "additionalProperties": true,
      "description": "A sub-claim in the research plan.",
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "text": {
          "title": "Text",
          "type": "string"
        },
        "status": {
          "default": "pending",
          "enum": [
            "pending",
            "covered",
            "uncoverable"
          ],
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "id",
        "text"
      ],
      "title": "SubClaim",
      "type": "object"
    },
    "ToolCalledEvent": {
      "additionalProperties": true,
      "description": "Search tool invocation.",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "ToolCalled",
          "default": "ToolCalled",
          "title": "Type",
          "type": "string"
        },
        "source_type": {
          "$ref": "#/$defs/SourceType"
        },
        "query": {
          "title": "Query",
          "type": "string"
        },
        "query_intent": {
          "title": "Query Intent",
          "type": "string"
        },
        "target_claim_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Target Claim Id"
        }
      },
      "required": [
        "source_type",
        "query",
        "query_intent"
      ],
      "title": "ToolCalledEvent",
      "type": "object"
    },
    "UserContextChallengedEvent": {
      "additionalProperties": true,
      "description": "User context contradicts evidence (RF-07).",
      "properties": {
        "id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        },
        "run_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Run Id"
        },
        "step_index": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Step Index"
        },
        "parent_event_id": {
          "anyOf": [
            {
              "format": "uuid",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Parent Event Id"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "type": {
          "const": "UserContextChallenged",
          "default": "UserContextChallenged",
          "title": "Type",
          "type": "string"
        },
        "user_context_claim": {
          "title": "User Context Claim",
          "type": "string"
        },
        "contradicting_evidence": {
          "title": "Contradicting Evidence",
          "type": "string"
        },
        "source_url": {
          "title": "Source Url",
          "type": "string"
        }
      },
      "required": [
        "user_context_claim",
        "contradicting_evidence",
        "source_url"
      ],
      "title": "UserContextChallengedEvent",
      "type": "object"
    }
  },
  "discriminator": {
    "mapping": {
      "AgentErrored": "#/$defs/AgentErroredEvent",
      "AmbiguityDetected": "#/$defs/AmbiguityDetectedEvent",
      "ClaimCovered": "#/$defs/ClaimCoveredEvent",
      "ClaimUncoverable": "#/$defs/ClaimUncoverableEvent",
      "ConfidenceMismatch": "#/$defs/ConfidenceMismatchEvent",
      "ContradictionDetected": "#/$defs/ContradictionDetectedEvent",
      "ContradictionResolved": "#/$defs/ContradictionResolvedEvent",
      "EvidenceAdded": "#/$defs/EvidenceAddedEvent",
      "JudgeRuled": "#/$defs/JudgeRuledEvent",
      "PlanCreated": "#/$defs/PlanCreatedEvent",
      "PlanCritiqued": "#/$defs/PlanCritiquedEvent",
      "PlanRevised": "#/$defs/PlanRevisedEvent",
      "QuestionAsked": "#/$defs/QuestionAskedEvent",
      "QuestionNormalized": "#/$defs/QuestionNormalizedEvent",
      "ResumedAfterCancel": "#/$defs/ResumedAfterCancelEvent",
      "ResumedAfterError": "#/$defs/ResumedAfterErrorEvent",
      "SourceFailed": "#/$defs/SourceFailedEvent",
      "Stopped": "#/$defs/StoppedEvent",
      "ToolCalled": "#/$defs/ToolCalledEvent",
      "UserContextChallenged": "#/$defs/UserContextChallengedEvent"
    },
    "propertyName": "type"
  },
  "oneOf": [
    {
      "$ref": "#/$defs/QuestionAskedEvent"
    },
    {
      "$ref": "#/$defs/QuestionNormalizedEvent"
    },
    {
      "$ref": "#/$defs/PlanCreatedEvent"
    },
    {
      "$ref": "#/$defs/PlanCritiquedEvent"
    },
    {
      "$ref": "#/$defs/PlanRevisedEvent"
    },
    {
      "$ref": "#/$defs/ToolCalledEvent"
    },
    {
      "$ref": "#/$defs/EvidenceAddedEvent"
    },
    {
      "$ref": "#/$defs/ClaimCoveredEvent"
    },
    {
      "$ref": "#/$defs/ClaimUncoverableEvent"
    },
    {
      "$ref": "#/$defs/SourceFailedEvent"
    },
    {
      "$ref": "#/$defs/AmbiguityDetectedEvent"
    },
    {
      "$ref": "#/$defs/ContradictionDetectedEvent"
    },
    {
      "$ref": "#/$defs/ContradictionResolvedEvent"
    },
    {
      "$ref": "#/$defs/UserContextChallengedEvent"
    },
    {
      "$ref": "#/$defs/JudgeRuledEvent"
    },
    {
      "$ref": "#/$defs/ConfidenceMismatchEvent"
    },
    {
      "$ref": "#/$defs/AgentErroredEvent"
    },
    {
      "$ref": "#/$defs/ResumedAfterErrorEvent"
    },
    {
      "$ref": "#/$defs/ResumedAfterCancelEvent"
    },
    {
      "$ref": "#/$defs/StoppedEvent"
    }
  ]
} as const;

// ---------------------------------------------------------------------------
// Event union (informational — concrete interfaces live in the JSON schema).
// Use `EventType` for narrowing and `EventSchema` for runtime validation.
// ---------------------------------------------------------------------------
//
// Event =
//     QuestionAskedEvent
//   | QuestionNormalizedEvent
//   | PlanCreatedEvent
//   | PlanCritiquedEvent
//   | PlanRevisedEvent
//   | ToolCalledEvent
//   | EvidenceAddedEvent
//   | ClaimCoveredEvent
//   | ClaimUncoverableEvent
//   | SourceFailedEvent
//   | AmbiguityDetectedEvent
//   | ContradictionDetectedEvent
//   | ContradictionResolvedEvent
//   | UserContextChallengedEvent
//   | JudgeRuledEvent
//   | ConfidenceMismatchEvent
//   | AgentErroredEvent
//   | ResumedAfterErrorEvent
//   | ResumedAfterCancelEvent
//   | StoppedEvent
//   ;
