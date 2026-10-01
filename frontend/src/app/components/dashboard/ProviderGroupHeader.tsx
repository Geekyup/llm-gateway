import { providerMeta } from "../../lib/domain";
import type { AK } from "../../types";

export function ProviderGroupHeader({ provider, keys }: { provider: string; keys: AK[] }) {
  const meta = providerMeta(provider);
  const activeCount = keys.filter((k) => k.status === "active").length;
  const total = keys.length;
  const allHealthy = activeCount === total;

  return (
    <div className="flex items-center justify-between gap-2 px-3 py-2" style={{ background: "color-mix(in srgb, var(--ink) 3%, transparent)" }}>
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: meta.color }} />
        <span className="text-xs font-medium" style={{ color: "var(--ink-2)" }}>{meta.name}</span>
        <span className="text-[12px] text-ink-3">{total}</span>
      </div>
      <span className="text-[12px] font-mono" style={{ color: allHealthy ? "var(--accent)" : "var(--warn)" }}>
        {activeCount}/{total}
      </span>
    </div>
  );
}