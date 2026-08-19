import { Sparkles, Route, Zap, KeyRound } from "lucide-react";
import type { ApiKeyRead } from "./api";
import type { AK, Provider, Status } from "../types";

export function toAK(k: ApiKeyRead): AK {
  return {
    id: String(k.id),
    label: k.label,
    provider: k.provider,
    status: k.status,
    masked: `#${k.id}`,
    used: k.requests_today,
    limit: k.daily_limit,
    model: k.model,
    cooldownUntil: k.cooldown_until ? new Date(k.cooldown_until).getTime() : undefined,
    lastUsed: k.last_used_at ? new Date(k.last_used_at).getTime() : undefined,
    created: new Date(k.created_at).getTime(),
    updated: new Date(k.updated_at).getTime(),
  };
}

export const STATUS_META: Record<Status, { text: string; color: string; bg: string; bd: string }> = {
  active:    { text: "Active",    color: "#00D68F", bg: "rgba(0,214,143,0.08)",  bd: "rgba(0,214,143,0.22)"  },
  cooldown:  { text: "Cooldown",  color: "#F59E0B", bg: "rgba(245,158,11,0.08)", bd: "rgba(245,158,11,0.22)" },
  exhausted: { text: "Exhausted", color: "#EF4444", bg: "rgba(239,68,68,0.08)",  bd: "rgba(239,68,68,0.22)"  },
  disabled:  { text: "Disabled",  color: "#52525B", bg: "rgba(82,82,91,0.08)",   bd: "rgba(82,82,91,0.18)"   },
};

export const PROVIDER_META: Record<string, { name: string; color: string; bg: string; Icon: typeof Sparkles }> = {
  gemini:     { name: "Gemini",     color: "#4F8EF7", bg: "rgba(79,142,247,0.1)",  Icon: Sparkles },
  openrouter: { name: "OpenRouter", color: "#A78BFA", bg: "rgba(167,139,250,0.1)", Icon: Route    },
  groq:       { name: "Groq",       color: "#F97316", bg: "rgba(249,115,22,0.1)",  Icon: Zap      },
};

export function providerMeta(provider: string) {
  return PROVIDER_META[provider] ?? { name: provider, color: "#71717A", bg: "rgba(113,113,122,0.1)", Icon: KeyRound };
}

export const PROVIDER_NAMES: Record<Provider, { name: string; Icon: typeof Sparkles }> = {
  gemini:     { name: "Gemini",     Icon: Sparkles },
  openrouter: { name: "OpenRouter", Icon: Route    },
  groq:       { name: "Groq",       Icon: Zap      },
};

export const OUTCOME_META: Record<string, { text: string; color: string; bg: string }> = {
  success:            { text: "success",            color: "#00D68F", bg: "rgba(0,214,143,0.1)" },
  rate_limited:       { text: "rate limited",        color: "#F59E0B", bg: "rgba(245,158,11,0.1)" },
  exhausted:          { text: "exhausted",           color: "#F59E0B", bg: "rgba(245,158,11,0.1)" },
  no_keys:            { text: "no keys",             color: "#EF4444", bg: "rgba(239,68,68,0.1)" },
  upstream_exhausted: { text: "upstream exhausted",  color: "#EF4444", bg: "rgba(239,68,68,0.1)" },
  error:              { text: "error",               color: "#EF4444", bg: "rgba(239,68,68,0.1)" },
};

export function outcomeMeta(outcome: string) {
  return OUTCOME_META[outcome] ?? { text: outcome, color: "#71717A", bg: "rgba(113,113,122,0.1)" };
}

export function rel(ts: number, now: number): string {
  const d = now - ts;
  if (d < 60000)    return `${Math.floor(d / 1000)}s ago`;
  if (d < 3600000)  return `${Math.floor(d / 60000)}m ago`;
  if (d < 86400000) return `${Math.floor(d / 3600000)}h ago`;
  return `${Math.floor(d / 86400000)}d ago`;
}

export function cd(until: number, now: number): string {
  const d = until - now;
  if (d <= 0) return "Ready";
  const h = Math.floor(d / 3600000);
  const m = Math.floor((d % 3600000) / 60000);
  const s = Math.floor((d % 60000) / 1000);
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  return `${m}:${String(s).padStart(2, "0")}`;
}
