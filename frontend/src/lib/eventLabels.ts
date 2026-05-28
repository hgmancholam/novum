/**
 * Friendly labels for the 20 event types emitted by the agent.
 *
 * Two related maps:
 *
 * - `EVENT_LABELS` — short noun phrase used in the trace timeline
 *   (e.g. "Plan" instead of "PlanCreated").
 * - `EVENT_ACTIVITIES` — present-continuous activity used in the live
 *   "researching" indicator (e.g. "Drafting a plan" while `PlanCreated`
 *   is the latest event).
 *
 * Both are keyed by the raw `EventType` string so unknown values (e.g.
 * future event types not yet generated into `types/events.ts`) fall back
 * to the raw type. See ui-prototype.md §7 (microcopy).
 */

import type { EventType } from "@/types/events";

export const EVENT_LABELS: Record<EventType, string> = {
  QuestionAsked: "Pregunta",
  QuestionNormalized: "Pregunta replanteada",
  QuestionClassified: "Tipo de pregunta",
  PlanCreated: "Plan de búsqueda",
  PlanCritiqued: "Revisión del plan",
  PlanRevised: "Plan ajustado",
  ToolCalled: "Búsqueda",
  EvidenceAdded: "Evidencia",
  ClaimCovered: "Afirmación cubierta",
  ClaimUncoverable: "Afirmación sin evidencia",
  SourceFailed: "Fuente no disponible",
  AmbiguityDetected: "Ambigüedad",
  ContradictionDetected: "Contradicción",
  ContradictionResolved: "Contradicción resuelta",
  UserContextChallenged: "Contexto cuestionado",
  PriorRunHintReplayed: "Resultado reutilizado",
  JudgeRuled: "Veredicto del juez",
  ConfidenceMismatch: "Inconsistencia en la confianza",
  AgentErrored: "Error del agente",
  ResumedAfterError: "Retomado tras error",
  ResumedAfterCancel: "Retomado tras cancelación",
  Stopped: "Listo",
  SaturationDetected: "Saturación",
  JudgeProviderDegraded: "Juez degradado",
  DeepFetchPerformed: "Lectura profunda",
};

export const EVENT_ACTIVITIES: Record<EventType, string> = {
  QuestionAsked: "Recibí tu pregunta",
  QuestionNormalized: "Reescribiendo la pregunta para entenderla mejor",
  QuestionClassified: "Analizando de qué se trata",
  PlanCreated: "Vamos a construir el plan de búsqueda",
  PlanCritiqued: "Revisando el plan antes de seguir",
  PlanRevised: "Replanteando el enfoque",
  ToolCalled: "Buscando en la web",
  EvidenceAdded: "Leyendo lo que encontré",
  ClaimCovered: "Marcando una afirmación como cubierta",
  ClaimUncoverable: "Identificando vacíos de información",
  SourceFailed: "Reintentando una fuente",
  AmbiguityDetected: "Detectando ambigüedad en la pregunta",
  ContradictionDetected: "Encontré información contradictoria",
  ContradictionResolved: "Reconciliando lo que dicen las fuentes",
  UserContextChallenged: "Necesito un poco más de contexto",
  PriorRunHintReplayed: "Recuperando una respuesta anterior",
  JudgeRuled: "Evaluando si la respuesta es suficiente",
  ConfidenceMismatch: "Revisando los niveles de confianza",
  AgentErrored: "Recuperándome de un error",
  ResumedAfterError: "Retomando desde donde quedé",
  ResumedAfterCancel: "Retomando desde donde quedé",
  Stopped: "Cerrando todo",
  SaturationDetected: "Detectando saturación",
  JudgeProviderDegraded: "Cambiando el juez de respaldo",
  DeepFetchPerformed: "Leyendo la página completa",
};

export function getEventLabel(type: string): string {
  return EVENT_LABELS[type as EventType] ?? type;
}

export function getEventActivity(type: string | undefined): string {
  if (type === undefined || type === "") {
    return "Trabajando en ello";
  }
  return EVENT_ACTIVITIES[type as EventType] ?? "Trabajando en ello";
}

/**
 * Enhanced narrative for feed display (IP-24) — returns a richer natural-language
 * phrase than EVENT_ACTIVITIES. Falls back to getEventActivity for unmapped types.
 *
 * Uses `Record<string, unknown>` to avoid coupling to backend event payload shape.
 */
export function getEventNarrative(
  type: EventType,
  payload: Record<string, unknown>,
): string {
  switch (type) {
    case "ToolCalled": {
      const query = payload["query"];
      if (typeof query === "string" && query.length > 0) {
        return `Busqué en la web: "${query}"`;
      }
      return "Busqué en la web";
    }
    case "EvidenceAdded": {
      const title = payload["source_title"];
      const url = payload["source_url"];
      if (typeof title === "string" && typeof url === "string") {
        try {
          const hostname = new URL(url).hostname.replace(/^www\./, "");
          return `Leí "${title}" (${hostname})`;
        } catch {
          return `Leí "${title}"`;
        }
      }
      return "Leí una fuente";
    }
    case "JudgeRuled": {
      const confidence = payload["final_confidence"];
      if (typeof confidence === "number") {
        return `Veredicto del juez: confianza ${confidence.toFixed(2)}`;
      }
      return "El juez evaluó la respuesta";
    }
    case "Stopped": {
      const stopReason = payload["stop_reason"];
      if (typeof stopReason === "string") {
        return `Terminé — ${stopReason}`;
      }
      return "Terminé";
    }
    default:
      return getEventActivity(type);
  }
}
