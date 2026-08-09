import { STATUS_META } from "../../lib/domain";
import type { Status } from "../../types";

export function StatusBadge({ status }: { status: Status }) {
  const s = STATUS_META[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-mono font-medium whitespace-nowrap transition-colors duration-300"
      style={{ color: s.color, background: s.bg, border: `1px solid ${s.bd}` }}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full shrink-0 transition-colors duration-300 ${status === "active" ? "animate-pulse" : ""}`}
        style={{ background: s.color }}
      />
      {s.text}
    </span>
  );
}
