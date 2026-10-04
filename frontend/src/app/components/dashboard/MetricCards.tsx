import { Activity, CheckCircle2, Clock } from "lucide-react";
import type { AK } from "../../types";

const CARD_STYLE = { background: "var(--card)", border: "1px solid var(--line)" } as const;

function IconBox({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="w-7 h-7 rounded-md flex items-center justify-center"
      style={{ background: "color-mix(in srgb, var(--ink) 6%, transparent)" }}
    >
      {children}
    </div>
  );
}

export function MetricCards({ keys }: { keys: AK[] }) {
  const total = keys.length;
  const active = keys.filter((k) => k.status === "active").length;
  const cool = keys.filter((k) => k.status === "cooldown").length;
  const req = keys.reduce((a, k) => a + k.used, 0);
  const capacity = keys.reduce((a, k) => a + k.limit, 0);
  const pct = capacity > 0 ? Math.min(100, (req / capacity) * 100) : 0;
  const pctLabel = pct > 0 && pct < 1 ? "<1%" : `${Math.round(pct)}%`;

  // Цвет — только когда есть что сигнализировать.
  const usageColor = pct >= 90 ? "var(--bad)" : pct >= 70 ? "var(--warn)" : "var(--ink)";
  const barColor = pct >= 90 ? "var(--bad)" : pct >= 70 ? "var(--warn)" : "var(--accent)";
  const activeColor = total > 0 && active === 0 ? "var(--bad)" : active < total ? "var(--warn)" : "var(--ink)";

  return (
    <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr_1fr] gap-4">
      <div className="rounded-lg p-5" style={CARD_STYLE}>
        <div className="flex items-center justify-between mb-4">
          <span className="text-[13px] text-ink-2 font-medium">Today's usage</span>
          <IconBox><Activity size={14} color="var(--ink-3)" /></IconBox>
        </div>
        <div className="flex items-baseline gap-2 mb-4">
          <span className="text-3xl font-mono font-medium leading-none" style={{ color: usageColor }}>{req.toLocaleString()}</span>
          <span className="text-[13px] font-mono text-ink-3">/ {capacity.toLocaleString()} requests</span>
          <span className="ml-auto text-[13px] font-mono text-ink-3">{pctLabel}</span>
        </div>
        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "color-mix(in srgb, var(--ink) 10%, transparent)" }}>
          <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: barColor }} />
        </div>
      </div>

      <div className="rounded-lg p-5" style={CARD_STYLE}>
        <div className="flex items-center justify-between mb-4">
          <span className="text-[13px] text-ink-2 font-medium">Active keys</span>
          <IconBox><CheckCircle2 size={14} color="var(--ink-3)" /></IconBox>
        </div>
        <div className="text-3xl font-mono font-medium leading-none mb-4" style={{ color: activeColor }}>{active}<span className="text-ink-3">/{total}</span></div>
        <div className="text-[13px] text-ink-3">{total === 0 ? "No keys yet" : active === total ? "All keys healthy" : `${total - active} unavailable`}</div>
      </div>

      <div className="rounded-lg p-5" style={CARD_STYLE}>
        <div className="flex items-center justify-between mb-4">
          <span className="text-[13px] text-ink-2 font-medium">In cooldown</span>
          <IconBox><Clock size={14} color="var(--ink-3)" /></IconBox>
        </div>
        <div className="text-3xl font-mono font-medium leading-none mb-4" style={{ color: cool > 0 ? "var(--warn)" : "var(--ink)" }}>{cool}</div>
        <div className="text-[13px] text-ink-3">{cool === 0 ? "No rate limits hit" : "Waiting for reset"}</div>
      </div>
    </div>
  );
}
