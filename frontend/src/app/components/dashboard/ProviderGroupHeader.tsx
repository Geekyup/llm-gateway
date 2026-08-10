import { providerMeta } from "../../lib/domain";
import type { AK } from "../../types";

export function ProviderGroupHeader({ provider, keys }: { provider: string; keys: AK[] }) {
  const meta = providerMeta(provider);
  const activeCount = keys.filter((k) => k.status === "active").length;
  const total = keys.length;
  const allHealthy = activeCount === total;

  return (
    <div className="flex items-center justify-between gap-2 px-4 py-2" style={{ background: "rgba(255,255,255,0.015)" }}>
      <div className="flex items-center gap-2">
        <meta.Icon size={13} color={meta.color} />
        <span className="text-xs font-medium" style={{ color: "#D4D4D8" }}>{meta.name}</span>
        <span className="text-[11px] text-zinc-600">
          {total} {total === 1 ? "key" : "keys"}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-[11px] font-mono" style={{ color: allHealthy ? "#00D68F" : "#F59E0B" }}>
          {activeCount}/{total} active
        </span>
        <div className="w-12 h-1 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.08)" }}>
          <div
            className="h-full transition-all duration-300"
            style={{ width: `${total ? (activeCount / total) * 100 : 0}%`, background: allHealthy ? "#00D68F" : "#F59E0B" }}
          />
        </div>
      </div>
    </div>
  );
}