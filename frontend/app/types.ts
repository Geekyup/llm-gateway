// ─── Shared UI types ────────────────────────────────────────────────────────
export type Status = "active" | "cooldown" | "exhausted" | "disabled";
export type Provider = "gemini";
export type View = "dashboard" | "monitor" | "access";
export type PF = "all" | Provider;

export interface AK {
  id: string; label: string; provider: Provider; status: Status;
  masked: string; used: number; limit: number;
  cooldownUntil?: number; lastUsed?: number; created: number; updated: number;
}

export interface LR {
  id: string; provider: string; keyLabel: string;
  code: number; latency: number; ts: number;
  chain?: { label: string; code: number }[];
}

export interface FormState { label: string; provider: Provider; rawKey: string; limit: string }
