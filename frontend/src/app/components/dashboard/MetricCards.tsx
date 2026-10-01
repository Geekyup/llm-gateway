import { KeyRound, CheckCircle2, Clock } from "lucide-react";
import type { AK } from "../../types";
import { alpha } from "../../lib/domain";

export function MetricCards({ keys }: { keys: AK[] }) {
  const total = keys.length;
  const active = keys.filter((k) => k.status === "active").length;
  const cool = keys.filter((k) => k.status === "cooldown").length;
  const req = keys.reduce((a, k) => a + k.used, 0);
  const capacity = keys.reduce((a, k) => a + k.limit, 0);
  const pct = capacity > 0 ? Math.min(100, (req / capacity) * 100) : 0;
  const usageColor = pct >= 90 ? "var(--bad)" : pct >= 70 ? "var(--warn)" : "var(--accent)";

  const smallCards = [
    { label: "Active Keys",      val: `${active}/${total}`, color: "var(--accent)", Icon: CheckCircle2 },
    { label: "In Cooldown",      val: String(cool),         color: "var(--warn)", Icon: Clock        },
  ] as const;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-[1.6fr_1fr_1fr] gap-3">
      <div
        className="rounded-lg p-4 duration-300"
        style={{ background: "var(--card)", border: "1px solid color-mix(in srgb, var(--ink) 10%, transparent)" }}
      >
        <div className="flex items-center justify-between mb-3">
          <span className="text-[12px] text-ink-3 font-medium">Today's Usage</span>
          <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: alpha(usageColor, 8) }}>
            <KeyRound size={12} color={usageColor} />
          </div>
        </div>
        <div className="flex items-baseline gap-1.5 mb-3">
          <span className="text-2xl font-mono font-medium" style={{ color: usageColor }}>{req.toLocaleString()}</span>
          <span className="text-xs font-mono text-ink-3">/ {capacity.toLocaleString()} requests</span>
        </div>
        <div className="h-[3px] rounded-full overflow-hidden" style={{ background: "color-mix(in srgb, var(--ink) 10%, transparent)" }}>
          <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: usageColor }} />
        </div>
      </div>

      {smallCards.map((c, i) => (
        <div
          key={c.label}
          className="rounded-lg p-4 transition-transform duration-200"
          style={{
            background: "var(--card)",
            border: "1px solid color-mix(in srgb, var(--ink) 10%, transparent)",
            animationDuration: "300ms",
            animationDelay: `${(i + 1) * 40}ms`,
            animationFillMode: "backwards",
          }}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-[12px] text-ink-3 font-medium">{c.label}</span>
            <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: alpha(c.color, 8) }}>
              <c.Icon size={12} color={c.color} />
            </div>
          </div>
          <span className="text-2xl font-mono font-medium" style={{ color: "var(--ink)" }}>{c.val}</span>
        </div>
      ))}
    </div>
  );
}