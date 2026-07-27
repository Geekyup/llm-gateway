import { S } from "../../lib/constants";
import type { Status } from "../../types";

export function SBadge({ status }: { status: Status }) {
  const s = S[status];
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-mono font-medium whitespace-nowrap"
      style={{ color: s.color, background: s.bg, border: `1px solid ${s.bd}` }}>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${status === "active" ? "animate-pulse" : ""}`}
        style={{ background: s.color }} />
      {s.text}
    </span>
  );
}
