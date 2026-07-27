import type { Status } from "../types";

// ─── Status / provider style constants ─────────────────────────────────────
export const S: Record<Status, { text: string; color: string; bg: string; bd: string }> = {
  active:    { text: "Active",    color: "#00D68F", bg: "rgba(0,214,143,0.08)",  bd: "rgba(0,214,143,0.22)"  },
  cooldown:  { text: "Cooldown",  color: "#F59E0B", bg: "rgba(245,158,11,0.08)", bd: "rgba(245,158,11,0.22)" },
  exhausted: { text: "Exhausted", color: "#EF4444", bg: "rgba(239,68,68,0.08)",  bd: "rgba(239,68,68,0.22)"  },
  disabled:  { text: "Disabled",  color: "#52525B", bg: "rgba(82,82,91,0.08)",   bd: "rgba(82,82,91,0.18)"   },
};

export const P: Record<string, { name: string; color: string; bg: string }> = {
  gemini: { name: "Gemini", color: "#4F8EF7", bg: "rgba(79,142,247,0.1)"  },
};

export function providerMeta(provider: string) {
  return P[provider] ?? { name: provider, color: "#71717A", bg: "rgba(113,113,122,0.1)" };
}
