import { STATUS_META } from "../../lib/domain";
import type { Status } from "../../types";

export function UsageBar({ used, limit, status }: { used: number; limit: number; status: Status }) {
  const pct = limit > 0 ? Math.min(100, Math.max(0, (used / limit) * 100)) : 0;
  const color =
    status === "active"
      ? pct >= 90
        ? "var(--bad)"
        : pct >= 70
          ? "var(--warn)"
          : "var(--accent)"
      : STATUS_META[status].color;
  return (
    <div className="min-w-[140px]">
      <div className="flex items-baseline gap-1 mb-1.5 font-mono text-[13px]">
        <span className={used > 0 ? "text-ink" : "text-ink-3"}>{used.toLocaleString()}</span>
        <span className="text-ink-4">/ {limit.toLocaleString()}</span>
      </div>
      <div
        className="h-1 rounded-full overflow-hidden"
        style={{ background: "color-mix(in srgb, var(--ink) 10%, transparent)" }}
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}
