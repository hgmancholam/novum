// Auto-generated from Pydantic models — DO NOT EDIT
// Source: scripts/export_types.py (BRD-02)
// Generated: 2026-05-28T01:25:24.366529+00:00

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type StopReason =
  | "judge_confirmed"
  | "stopped_by_budget"
  | "user_cancelled"
  | "errored";

export type QuestionType =
  | "factual"
  | "comparative"
  | "definitional"
  | "state_of_art"
  | "causal"
  | "predictive_future"
  | "subjective_opinion"
  | "personal_private";

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
  | "QuestionClassified"
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
  | "PriorRunHintReplayed"
  | "JudgeRuled"
  | "ConfidenceMismatch"
  | "SaturationDetected"
  | "JudgeProviderDegraded"
  | "AgentErrored"
  | "ResumedAfterError"
  | "ResumedAfterCancel"
  | "Stopped";

export type ComplexityHint =
  | "trivial"
  | "standard"
  | "deep";

// ---------------------------------------------------------------------------
// Forkable events (RF-03): user-selectable branch points.
// ---------------------------------------------------------------------------

export const FORKABLE_EVENTS: readonly EventType[] = ["PlanCreated", "AmbiguityDetected", "ContradictionDetected", "JudgeRuled", "Stopped"] as const;

// ---------------------------------------------------------------------------
// Structured answer payload (RF-10, BRD-16)
// Source: app/domain/structured.py
// ---------------------------------------------------------------------------

export interface KeyValueRow {
  key: string;
  value: string;
}

export interface ParagraphBlock {
  type: "paragraph";
  text: string;
}

export interface KeyValueBlock {
  type: "keyValue";
  title?: string | null;
  rows: KeyValueRow[];
}

export interface StepsBlock {
  type: "steps";
  title?: string | null;
  items: string[];
}

export interface KeyPointsBlock {
  type: "keyPoints";
  title?: string | null;
  items: string[];
}

export interface MermaidBlock {
  type: "mermaid";
  title?: string | null;
  diagram: string;
}

export interface MarkdownBlock {
  type: "markdown";
  text: string;
}

export type StructuredBlock =
  | ParagraphBlock
  | KeyValueBlock
  | StepsBlock
  | KeyPointsBlock
  | MermaidBlock
  | MarkdownBlock;

export interface StructuredAnswerData {
  summary: string;
  blocks: StructuredBlock[];
}

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
        },
        "error_code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error Code"
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
        },
        "dimensions": {
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
          "title": "Dimensions"
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
    "AnswerKind": {
      "description": "Shape of the answer produced at terminal ``judge_confirmed`` (RF-17).\n\nSelected by ``app.agent.tasks.select_answer_kind`` from\n``(question_type, S, C_coverage, C_agreement, ambiguity_flag)``.\nEach kind carries a soft confidence ceiling (see\n``app.confidence.kind_ceiling``).",
      "enum": [
        "direct",
        "weighted",
        "scenario",
        "tradeoff",
        "ethical_redirect",
        "best_effort"
      ],
      "title": "AnswerKind",
      "type": "string"
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
    "ComplexityHint": {
      "description": "Question complexity classification for planning budget (BRD-22).\n\n- ``trivial``: short factual/definitional queries (\u22648 words) \u2192 1 claim, 1 source, no critique\n- ``standard``: typical questions \u2192 current default budget\n- ``deep``: research-heavy questions (\u226516 words or STATE_OF_ART) \u2192 extra critique pass",
      "enum": [
        "trivial",
        "standard",
        "deep"
      ],
      "title": "ComplexityHint",
      "type": "string"
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
      "description": "Irreconcilable source conflict (RF-04).\n\nWP-2.5 additions (optional, additive): claim, supporting_chunk_ids,\ncontradicting_chunk_ids, round.",
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
        },
        "claim": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Claim"
        },
        "supporting_chunk_ids": {
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
          "title": "Supporting Chunk Ids"
        },
        "contradicting_chunk_ids": {
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
          "title": "Contradicting Chunk Ids"
        },
        "round": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Round"
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
    "JudgeProviderDegradedEvent": {
      "additionalProperties": true,
      "description": "Judge provider failed, fell back to alternate provider (WP-5).",
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
          "const": "JudgeProviderDegraded",
          "default": "JudgeProviderDegraded",
          "title": "Type",
          "type": "string"
        },
        "requested_provider": {
          "title": "Requested Provider",
          "type": "string"
        },
        "fallback_provider": {
          "title": "Fallback Provider",
          "type": "string"
        },
        "error_class": {
          "title": "Error Class",
          "type": "string"
        }
      },
      "required": [
        "requested_provider",
        "fallback_provider",
        "error_class"
      ],
      "title": "JudgeProviderDegradedEvent",
      "type": "object"
    },
    "JudgeRuledEvent": {
      "additionalProperties": true,
      "description": "Judge LLM evaluation (RF-12, WP-3 G5 C_kind_appropriateness, WP-5 extensions).",
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
        },
        "answer_kind": {
          "anyOf": [
            {
              "$ref": "#/$defs/AnswerKind"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "kind_appropriateness": {
          "default": 1.0,
          "title": "Kind Appropriateness",
          "type": "number"
        },
        "coherence": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Coherence"
        },
        "contradictions_detected": {
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
          "title": "Contradictions Detected"
        },
        "missing_evidence": {
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
          "title": "Missing Evidence"
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
    "KeyPointsBlock": {
      "additionalProperties": true,
      "description": "Unordered list of key points / bullets.",
      "properties": {
        "type": {
          "const": "keyPoints",
          "default": "keyPoints",
          "title": "Type",
          "type": "string"
        },
        "title": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Title"
        },
        "items": {
          "items": {
            "type": "string"
          },
          "title": "Items",
          "type": "array"
        }
      },
      "required": [
        "items"
      ],
      "title": "KeyPointsBlock",
      "type": "object"
    },
    "KeyValueBlock": {
      "additionalProperties": true,
      "description": "Key/value table \u2014 for facts, attributes, specs.",
      "properties": {
        "type": {
          "const": "keyValue",
          "default": "keyValue",
          "title": "Type",
          "type": "string"
        },
        "title": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Title"
        },
        "rows": {
          "items": {
            "$ref": "#/$defs/KeyValueRow"
          },
          "title": "Rows",
          "type": "array"
        }
      },
      "required": [
        "rows"
      ],
      "title": "KeyValueBlock",
      "type": "object"
    },
    "KeyValueRow": {
      "additionalProperties": true,
      "properties": {
        "key": {
          "title": "Key",
          "type": "string"
        },
        "value": {
          "title": "Value",
          "type": "string"
        }
      },
      "required": [
        "key",
        "value"
      ],
      "title": "KeyValueRow",
      "type": "object"
    },
    "MarkdownBlock": {
      "additionalProperties": true,
      "description": "Fallback for content that is already richly formatted by the LLM.",
      "properties": {
        "type": {
          "const": "markdown",
          "default": "markdown",
          "title": "Type",
          "type": "string"
        },
        "text": {
          "title": "Text",
          "type": "string"
        }
      },
      "required": [
        "text"
      ],
      "title": "MarkdownBlock",
      "type": "object"
    },
    "MermaidBlock": {
      "additionalProperties": true,
      "description": "Mermaid diagram source (flowchart, sequence, etc.).",
      "properties": {
        "type": {
          "const": "mermaid",
          "default": "mermaid",
          "title": "Type",
          "type": "string"
        },
        "title": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Title"
        },
        "diagram": {
          "title": "Diagram",
          "type": "string"
        }
      },
      "required": [
        "diagram"
      ],
      "title": "MermaidBlock",
      "type": "object"
    },
    "ParagraphBlock": {
      "additionalProperties": true,
      "description": "A plain prose paragraph rendered as styled text.",
      "properties": {
        "type": {
          "const": "paragraph",
          "default": "paragraph",
          "title": "Type",
          "type": "string"
        },
        "text": {
          "title": "Text",
          "type": "string"
        }
      },
      "required": [
        "text"
      ],
      "title": "ParagraphBlock",
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
        },
        "complexity_hint": {
          "anyOf": [
            {
              "$ref": "#/$defs/ComplexityHint"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "expected_experts": {
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
          "title": "Expected Experts"
        },
        "preferred_sources": {
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
          "title": "Preferred Sources"
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
        },
        "complexity_hint": {
          "anyOf": [
            {
              "$ref": "#/$defs/ComplexityHint"
            },
            {
              "type": "null"
            }
          ],
          "default": null
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
    "PriorRunHintReplayedEvent": {
      "additionalProperties": true,
      "description": "Instant-answer cache replay (BRD-22).\n\nEmitted when the orchestrator short-circuits a new run by reusing a\nprior high-confidence result. The new run skips classify/plan/search\nand emits synthetic ``JudgeRuledEvent`` + ``StoppedEvent`` carrying\nthe prior answer payload.",
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
          "const": "PriorRunHintReplayed",
          "default": "PriorRunHintReplayed",
          "title": "Type",
          "type": "string"
        },
        "source_run_id": {
          "format": "uuid",
          "title": "Source Run Id",
          "type": "string"
        },
        "source_final_confidence": {
          "title": "Source Final Confidence",
          "type": "number"
        },
        "source_stop_reason": {
          "$ref": "#/$defs/StopReason"
        },
        "source_answer_kind": {
          "anyOf": [
            {
              "$ref": "#/$defs/AnswerKind"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "normalised_question": {
          "title": "Normalised Question",
          "type": "string"
        },
        "prior_completed_at": {
          "format": "date-time",
          "title": "Prior Completed At",
          "type": "string"
        }
      },
      "required": [
        "source_run_id",
        "source_final_confidence",
        "source_stop_reason",
        "normalised_question",
        "prior_completed_at"
      ],
      "title": "PriorRunHintReplayedEvent",
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
    "QuestionClassifiedEvent": {
      "additionalProperties": true,
      "description": "Question classified with type and complexity hint (BRD-22).\n\nEmitted after normalization and classifier LLM call. Optional fields\n(``complexity_hint``, ``heuristic_signals``) are additive per RF-03;\npre-BRD-22 events lack them and replay tolerates absence.",
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
          "const": "QuestionClassified",
          "default": "QuestionClassified",
          "title": "Type",
          "type": "string"
        },
        "question_type": {
          "$ref": "#/$defs/QuestionType"
        },
        "classifier_confidence": {
          "title": "Classifier Confidence",
          "type": "number"
        },
        "complexity_hint": {
          "anyOf": [
            {
              "$ref": "#/$defs/ComplexityHint"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "heuristic_signals": {
          "anyOf": [
            {
              "additionalProperties": true,
              "type": "object"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Heuristic Signals"
        }
      },
      "required": [
        "question_type",
        "classifier_confidence"
      ],
      "title": "QuestionClassifiedEvent",
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
      "description": "Supported question types (RF-06).\n\nTypes 1\u20135 are the \"answerable\" classes. Types 6\u20138 used to short-circuit\nto ``honest_unanswerable``; per the 2026-05-27 amendment they now route\nto dedicated ``AnswerKind`` templates (predictive_future\u2192SCENARIO,\nsubjective_opinion\u2192TRADEOFF, personal_private\u2192ETHICAL_REDIRECT).",
      "enum": [
        "factual",
        "comparative",
        "definitional",
        "state_of_art",
        "causal",
        "predictive_future",
        "subjective_opinion",
        "personal_private"
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
    "SaturationDetectedEvent": {
      "additionalProperties": true,
      "description": "Novelty-based saturation signal fired (WP-4).\n\nComputed as: novelty = 1 - mean(max_cosine_similarity(chunk_i, prior_corpus))\nover the last k=3 chunks from the current round.",
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
          "const": "SaturationDetected",
          "default": "SaturationDetected",
          "title": "Type",
          "type": "string"
        },
        "round_index": {
          "title": "Round Index",
          "type": "integer"
        },
        "novelty": {
          "title": "Novelty",
          "type": "number"
        },
        "k": {
          "default": 3,
          "title": "K",
          "type": "integer"
        },
        "threshold": {
          "title": "Threshold",
          "type": "number"
        }
      },
      "required": [
        "round_index",
        "novelty",
        "threshold"
      ],
      "title": "SaturationDetectedEvent",
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
    "StepsBlock": {
      "additionalProperties": true,
      "description": "Ordered list of steps / process stages.",
      "properties": {
        "type": {
          "const": "steps",
          "default": "steps",
          "title": "Type",
          "type": "string"
        },
        "title": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Title"
        },
        "items": {
          "items": {
            "type": "string"
          },
          "title": "Items",
          "type": "array"
        }
      },
      "required": [
        "items"
      ],
      "title": "StepsBlock",
      "type": "object"
    },
    "StopRationale": {
      "additionalProperties": true,
      "description": "Structured 'why we stopped' payload (RF-13 / RF-19, WP-3 G2).\n\nAggregates the four signals the challenge spec expects to see on a\nterminal run: evidence quality, source agreement, novelty (information\ngain), and final confidence \u2014 plus the ceiling actually applied and a\nshort human-readable summary from the judge.",
      "properties": {
        "reason": {
          "$ref": "#/$defs/StopReason"
        },
        "triggering_signal": {
          "title": "Triggering Signal",
          "type": "string"
        },
        "summary": {
          "title": "Summary",
          "type": "string"
        },
        "confidence": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Confidence"
        }
      },
      "required": [
        "reason",
        "triggering_signal",
        "summary"
      ],
      "title": "StopRationale",
      "type": "object"
    },
    "StopReason": {
      "description": "Terminal states for a run (RF-01, WP-3 amendment 2026-05-27).\n\nFour terminal states:\n- 1 positive terminal (judge_confirmed with AnswerKind)\n- 1 budget safety net\n- 1 user action\n- 1 error state\n\nThe three ``honest_*`` values were removed in WP-3. Ambiguous/sparse/\ncontradictory questions now route through ``AnswerKind`` selection\n(best_effort, weighted, scenario) inside ``judge_confirmed``.",
      "enum": [
        "judge_confirmed",
        "stopped_by_budget",
        "user_cancelled",
        "errored"
      ],
      "title": "StopReason",
      "type": "string"
    },
    "StoppedEvent": {
      "additionalProperties": true,
      "description": "Terminal event with final answer or budget/error stop.",
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
        "answer_structured": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Answer Structured"
        },
        "answer_structured_data": {
          "anyOf": [
            {
              "$ref": "#/$defs/StructuredAnswerData"
            },
            {
              "type": "null"
            }
          ],
          "default": null
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
        "answer_kind": {
          "anyOf": [
            {
              "$ref": "#/$defs/AnswerKind"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "stop_rationale": {
          "anyOf": [
            {
              "$ref": "#/$defs/StopRationale"
            },
            {
              "type": "null"
            }
          ],
          "default": null
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
    "StructuredAnswerData": {
      "additionalProperties": true,
      "description": "Structured-format answer payload (RF-10).\n\nThe frontend renders each block with native UI components instead of\nparsing markdown. ``summary`` is shown as a headline above the blocks.",
      "properties": {
        "summary": {
          "title": "Summary",
          "type": "string"
        },
        "blocks": {
          "items": {
            "discriminator": {
              "mapping": {
                "keyPoints": "#/$defs/KeyPointsBlock",
                "keyValue": "#/$defs/KeyValueBlock",
                "markdown": "#/$defs/MarkdownBlock",
                "mermaid": "#/$defs/MermaidBlock",
                "paragraph": "#/$defs/ParagraphBlock",
                "steps": "#/$defs/StepsBlock"
              },
              "propertyName": "type"
            },
            "oneOf": [
              {
                "$ref": "#/$defs/ParagraphBlock"
              },
              {
                "$ref": "#/$defs/KeyValueBlock"
              },
              {
                "$ref": "#/$defs/StepsBlock"
              },
              {
                "$ref": "#/$defs/KeyPointsBlock"
              },
              {
                "$ref": "#/$defs/MermaidBlock"
              },
              {
                "$ref": "#/$defs/MarkdownBlock"
              }
            ]
          },
          "title": "Blocks",
          "type": "array"
        }
      },
      "required": [
        "summary"
      ],
      "title": "StructuredAnswerData",
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
        },
        "query_length_tokens": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Query Length Tokens"
        },
        "tavily_days_filter": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Tavily Days Filter"
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
      "JudgeProviderDegraded": "#/$defs/JudgeProviderDegradedEvent",
      "JudgeRuled": "#/$defs/JudgeRuledEvent",
      "PlanCreated": "#/$defs/PlanCreatedEvent",
      "PlanCritiqued": "#/$defs/PlanCritiquedEvent",
      "PlanRevised": "#/$defs/PlanRevisedEvent",
      "PriorRunHintReplayed": "#/$defs/PriorRunHintReplayedEvent",
      "QuestionAsked": "#/$defs/QuestionAskedEvent",
      "QuestionClassified": "#/$defs/QuestionClassifiedEvent",
      "QuestionNormalized": "#/$defs/QuestionNormalizedEvent",
      "ResumedAfterCancel": "#/$defs/ResumedAfterCancelEvent",
      "ResumedAfterError": "#/$defs/ResumedAfterErrorEvent",
      "SaturationDetected": "#/$defs/SaturationDetectedEvent",
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
      "$ref": "#/$defs/QuestionClassifiedEvent"
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
      "$ref": "#/$defs/PriorRunHintReplayedEvent"
    },
    {
      "$ref": "#/$defs/JudgeRuledEvent"
    },
    {
      "$ref": "#/$defs/ConfidenceMismatchEvent"
    },
    {
      "$ref": "#/$defs/SaturationDetectedEvent"
    },
    {
      "$ref": "#/$defs/JudgeProviderDegradedEvent"
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
//   | QuestionClassifiedEvent
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
//   | PriorRunHintReplayedEvent
//   | JudgeRuledEvent
//   | ConfidenceMismatchEvent
//   | SaturationDetectedEvent
//   | JudgeProviderDegradedEvent
//   | AgentErroredEvent
//   | ResumedAfterErrorEvent
//   | ResumedAfterCancelEvent
//   | StoppedEvent
//   ;
