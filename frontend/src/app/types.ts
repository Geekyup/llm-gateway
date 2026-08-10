export type Status = "active" | "cooldown" | "exhausted" | "disabled";
export type Provider = "gemini" | "openrouter" | "groq";
export type View = "dashboard" | "monitor" | "playground" | "access";
export type PF = "all" | Provider;
export type SF = "all" | Status;

export interface AK {
  id: string;
  label: string;
  provider: Provider;
  status: Status;
  masked: string;
  used: number;
  limit: number;
  model: string | null;
  cooldownUntil?: number;
  lastUsed?: number;
  created: number;
  updated: number;
}

export interface LR {
  id: string;
  provider: string;
  keyLabel: string;
  code: number;
  latency: number;
  ts: number;
  chain?: { label: string; code: number }[];
  totalTokens: number | null;
}

export interface FormState {
  label: string;
  provider: Provider;
  rawKey: string;
  limit: string;
  model: string;
}