import type { ApiKeyRead, RequestEvent as ApiRequestEvent } from "./api";
import type { AK, LR } from "../types";

// ─── Mapping between backend schema and UI view-model ─────────────────────────
export function toAK(k: ApiKeyRead): AK {
  return {
    id: String(k.id),
    label: k.label,
    provider: k.provider,
    status: k.status,
    masked: `#${k.id}`,
    used: k.requests_today,
    limit: k.daily_limit,
    cooldownUntil: k.cooldown_until ? new Date(k.cooldown_until).getTime() : undefined,
    lastUsed: k.last_used_at ? new Date(k.last_used_at).getTime() : undefined,
    created: new Date(k.created_at).getTime(),
    updated: new Date(k.updated_at).getTime(),
  };
}

export function toLR(e: ApiRequestEvent): LR {
  return {
    id: `${e.request_id}-${e.attempt}`,
    provider: e.provider,
    keyLabel: e.key_label ?? "—",
    code: e.upstream_status ?? (e.outcome === "no_keys" ? 503 : 0),
    latency: e.latency_ms ?? 0,
    ts: new Date(e.timestamp).getTime(),
  };
}
