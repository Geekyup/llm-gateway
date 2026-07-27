import { S } from "../../lib/constants";
import type { Status } from "../../types";

export function UBar({ used, limit, status }: { used: number; limit: number; status: Status }) {
  const pct = Math.min(100, (used / limit) * 100);
  const color = S[status].color;
  return (
    <div className="min-w-[140px]">
      <div className="flex justify-between mb-1.5">
        <span className="text-[11px] font-mono text-zinc-300">{used.toLocaleString()}</span>
        <span className="text-[11px] font-mono text-zinc-600">/ {limit.toLocaleString()}</span>
      </div>
      <div className="h-[3px] rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color, boxShadow: pct > 80 ? `0 0 8px ${color}60` : "none" }} />
      </div>
    </div>
  );
}
