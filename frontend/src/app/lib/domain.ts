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
    pingMs: k.last_ping_ms ?? undefined,
    pingAt: k.last_ping_at ? new Date(k.last_ping_at).getTime() : undefined,
    created: new Date(k.created_at).getTime(),
    updated: new Date(k.updated_at).getTime(),
  };
}

export const STATUS_META: Record<Status, { text: string; color: string; bg: string; bd: string }> = {
  active:    { text: "Active",    color: "var(--ok)", bg: "color-mix(in srgb, var(--ok) 8%, transparent)",  bd: "color-mix(in srgb, var(--ok) 22%, transparent)"  },
  cooldown:  { text: "Cooldown",  color: "var(--warn)", bg: "color-mix(in srgb, var(--warn) 8%, transparent)", bd: "color-mix(in srgb, var(--warn) 22%, transparent)" },
  exhausted: { text: "Exhausted", color: "var(--bad)", bg: "color-mix(in srgb, var(--bad) 8%, transparent)",  bd: "color-mix(in srgb, var(--bad) 22%, transparent)"  },
  disabled:  { text: "Disabled",  color: "var(--ink-4)", bg: "color-mix(in srgb, var(--ink-4) 8%, transparent)",   bd: "color-mix(in srgb, var(--ink-4) 18%, transparent)"   },
};

export function alpha(color: string, percent: number): string {
  return `color-mix(in srgb, ${color} ${percent}%, transparent)`;
}

export function pingMeta(ms: number | undefined): { text: string; color: string } {
  if (ms === undefined) return { text: "—", color: "var(--ink-4)" };
  const text = `${ms} ms`;
  if (ms < 300) return { text, color: "var(--ok)" };
  if (ms < 1000) return { text, color: "var(--warn)" };
  return { text, color: "var(--bad)" };
}

export const PROVIDER_META: Record<string, { name: string; color: string; bg: string }> = {
  gemini:     { name: "Gemini",     color: "#2F6FD6", bg: "rgba(79,142,247,0.1)"  },
  openrouter: { name: "OpenRouter", color: "#7C5CD6", bg: "rgba(167,139,250,0.1)" },
  groq:       { name: "Groq",       color: "#D9611A", bg: "rgba(249,115,22,0.1)"  },
};

export function providerMeta(provider: string) {
  return PROVIDER_META[provider] ?? { name: provider, color: "var(--ink-3)", bg: "color-mix(in srgb, var(--ink-3) 10%, transparent)" };
}

export const PROVIDER_NAMES: Record<Provider, { name: string }> = {
  gemini:     { name: "Gemini"     },
  openrouter: { name: "OpenRouter" },
  groq:       { name: "Groq"       },
};

export const OUTCOME_META: Record<string, { text: string; color: string; bg: string }> = {
  success:            { text: "success",            color: "var(--ok)", bg: "color-mix(in srgb, var(--ok) 10%, transparent)" },
  rate_limited:       { text: "rate limited",        color: "var(--warn)", bg: "color-mix(in srgb, var(--warn) 10%, transparent)" },
  exhausted:          { text: "exhausted",           color: "var(--warn)", bg: "color-mix(in srgb, var(--warn) 10%, transparent)" },
  no_keys:            { text: "no keys",             color: "var(--bad)", bg: "color-mix(in srgb, var(--bad) 10%, transparent)" },
  upstream_exhausted: { text: "upstream exhausted",  color: "var(--bad)", bg: "color-mix(in srgb, var(--bad) 10%, transparent)" },
  error:              { text: "error",               color: "var(--bad)", bg: "color-mix(in srgb, var(--bad) 10%, transparent)" },
};

export function outcomeMeta(outcome: string) {
  return OUTCOME_META[outcome] ?? { text: outcome, color: "var(--ink-3)", bg: "color-mix(in srgb, var(--ink-3) 10%, transparent)" };
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