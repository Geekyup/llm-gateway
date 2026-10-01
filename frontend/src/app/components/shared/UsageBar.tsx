import { STATUS_META } from "../../lib/domain";
import type { Status } from "../../types";

const SLOTS = 16;

export function UsageBar({ used, limit, status }: { used: number; limit: number; status: Status }) {
  const pct = limit > 0 ? Math.min(100, Math.max(0, (used / limit) * 100)) : 0;
  const filled = Math.round((pct / 100) * SLOTS);
  const color =
    status === "active"
      ? pct >= 90
        ? "var(--bad)"
        : pct >= 70
          ? "var(--warn)"
          : "var(--ink)"
      : STATUS_META[status].color;
  return (
    <div className="min-w-[140px]">
      <div className="flex justify-between mb-1.5">
        <span className="text-[12px] font-mono text-ink">{used.toLocaleString()}</span>
        <span className="text-[12px] font-mono text-ink-3">/ {limit.toLocaleString()}</span>
      </div>
      <div className="flex gap-[2px] h-[10px]" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
        {Array.from({ length: SLOTS }).map((_, i) => (
          <span
            key={i}
            className="flex-1"
            style={{ background: i < filled ? color : "color-mix(in srgb, var(--ink) 12%, transparent)" }}
          />
        ))}
      </div>
    </div>
  );
}
