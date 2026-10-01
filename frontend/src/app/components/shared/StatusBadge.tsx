import { STATUS_META } from "../../lib/domain";
import type { Status } from "../../types";

export function StatusBadge({ status, cooldownText }: { status: Status; cooldownText?: string }) {
  const s = STATUS_META[status];
  return (
    <span className="inline-flex items-center gap-2 text-[13px] whitespace-nowrap text-ink-2">
      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: s.color }} />
      {s.text.toLowerCase()}
      {status === "cooldown" && cooldownText && <span className="font-mono text-ink-3">{cooldownText}</span>}
    </span>
  );
}
