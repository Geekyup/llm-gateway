import type { AK } from "../../types";
import { cd } from "../../lib/domain";

const CARD_STYLE = { background: "var(--card)", border: "1px solid color-mix(in srgb, var(--ink) 6%, transparent)" } as const;

function formatPercent(pct: number): string {
  if (pct > 0 && pct < 10) return `${pct.toFixed(1)}%`;
  return `${Math.round(pct)}%`;
}

function CardHeader({ label, hint, hintColor }: { label: string; hint?: string; hintColor?: string }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <span className="text-[12px] text-ink-3 font-medium">{label}</span>
      {hint && (
        <span className="text-[12px] font-mono" style={{ color: hintColor ?? "var(--ink-3)" }}>
          {hint}
        </span>
      )}
    </div>
  );
}

export function MetricCards({ keys, now }: { keys: AK[]; now: number }) {
  const total = keys.length;
  const active = keys.filter((k) => k.status === "active").length;
  const cooling = keys.filter((k) => k.status === "cooldown");
  const req = keys.reduce((a, k) => a + k.used, 0);
  const capacity = keys.reduce((a, k) => a + k.limit, 0);
  const pct = capacity > 0 ? Math.min(100, (req / capacity) * 100) : 0;

  const usageColor = pct >= 90 ? "var(--bad)" : pct >= 70 ? "var(--warn)" : "var(--ink)";
  const usageValueColor = req === 0 ? "var(--ink-3)" : usageColor;

  const inactive = total - active;
  const nextReady = cooling
    .map((k) => k.cooldownUntil)
    .filter((t): t is number => t !== undefined)
    .sort((a, b) => a - b)[0];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-[1.6fr_1fr_1fr] gap-3">
      <div className="rounded-lg p-4 duration-300" style={CARD_STYLE}>
        <CardHeader label="Today's Usage" hint={formatPercent(pct)} />
        <div className="flex items-baseline gap-1.5 mb-3">
          <span className="text-2xl font-mono font-medium" style={{ color: usageValueColor }}>{req.toLocaleString()}</span>
          <span className="text-xs font-mono text-ink-3">/ {capacity.toLocaleString()} requests</span>
        </div>
        <div className="h-[3px] rounded-full overflow-hidden" style={{ background: "color-mix(in srgb, var(--ink) 6%, transparent)" }}>
          <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: usageColor }} />
        </div>
      </div>

      <div className="rounded-lg p-4" style={{ ...CARD_STYLE, animationDuration: "300ms", animationDelay: "40ms", animationFillMode: "backwards" }}>
        <CardHeader
          label="Active Keys"
          hint={total === 0 ? undefined : inactive === 0 ? "all healthy" : `${inactive} not active`}
          hintColor={inactive > 0 ? "var(--warn)" : undefined}
        />
        <span className="text-2xl font-mono font-medium" style={{ color: total === 0 ? "var(--ink-3)" : "var(--ink)" }}>
          {active}/{total}
        </span>
      </div>

      <div className="rounded-lg p-4" style={{ ...CARD_STYLE, animationDuration: "300ms", animationDelay: "80ms", animationFillMode: "backwards" }}>
        <CardHeader
          label="In Cooldown"
          hint={nextReady !== undefined ? `next in ${cd(nextReady, now)}` : undefined}
          hintColor="var(--warn)"
        />
        <span className="text-2xl font-mono font-medium" style={{ color: cooling.length === 0 ? "var(--ink-3)" : "var(--warn)" }}>
          {cooling.length}
        </span>
      </div>
    </div>
  );
}
