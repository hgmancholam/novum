// Hand-mirrored from backend/app/health/models.py (BRD-27 §4.4).
// Kept manually because scripts/export_types.py is scoped to event types.

export type ServiceStatus = "ok" | "degraded" | "down" | "disabled" | "no_key";

export type ServiceCategory = "llm" | "search" | "knowledge" | "storage";

export interface ServiceHealth {
  id: string;
  name: string;
  category: ServiceCategory;
  status: ServiceStatus;
  latency_ms: number | null;
  message: string | null;
  checked_at: string;
  [extra: string]: unknown;
}

export interface HealthSnapshot {
  checked_at: string;
  cached: boolean;
  services: ServiceHealth[];
  [extra: string]: unknown;
}
