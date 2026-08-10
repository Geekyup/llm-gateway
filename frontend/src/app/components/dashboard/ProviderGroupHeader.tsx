import { providerMeta } from "../../lib/domain";
import type { AK } from "../../types";

export function ProviderGroupHeader({ provider, keys }: { provider: string; keys: AK[] }) {
  const meta = providerMeta(provider);
  const activeCount = keys.filter((k) => k.status === "active").length;
  const total = keys.length;
  const allHealthy = activeCount === total;

  return (
    <div className="flex items-center justify-between gap-2 px-3 py-2" style={{ background: "rgba(255,255,255,0.02)" }}>
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: meta.color }} />
        <span className="text-xs font-medium" style={{ color: "#D4D4D8" }}>{meta.name}</span>
        <span className="text-[11px] text-zinc-600">{total}</span>
      </div>
      <span className="text-[11px] font-mono" style={{ color: allHealthy ? "#00D68F" : "#F59E0B" }}>
        {activeCount}/{total}
      </span>
    </div>
  );
}