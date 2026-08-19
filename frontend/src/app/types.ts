export type Status = "active" | "cooldown" | "exhausted" | "disabled";
export type Provider = "gemini" | "openrouter" | "groq";
export type View = "dashboard" | "activity" | "playground" | "access";
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

export interface FormState {
  label: string;
  provider: Provider;
  rawKey: string;
  limit: string;
  model: string;
}