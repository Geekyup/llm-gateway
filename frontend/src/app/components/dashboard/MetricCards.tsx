import { KeyRound, CheckCircle2, Clock } from "lucide-react";
import type { AK } from "../../types";

export function MetricCards({ keys }: { keys: AK[] }) {
  const total = keys.length;
  const active = keys.filter((k) => k.status === "active").length;
  const cool = keys.filter((k) => k.status === "cooldown").length;
  const req = keys.reduce((a, k) => a + k.used, 0);
  const capacity = keys.reduce((a, k) => a + k.limit, 0);
  const pct = capacity > 0 ? Math.min(100, (req / capacity) * 100) : 0;
  const usageColor = pct >= 90 ? "#EF4444" : pct >= 70 ? "#F59E0B" : "#00D68F";

  const smallCards = [
    { label: "Active Keys",      val: `${active}/${total}`, color: "#00D68F", Icon: CheckCircle2 },
    { label: "In Cooldown",      val: String(cool),         color: "#F59E0B", Icon: Clock        },
  ] as const;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-[1.6fr_1fr_1fr] gap-3">
      <div
        className="rounded-xl p-4 animate-in fade-in slide-in-from-bottom-1 duration-300"
        style={{ background: "#111113", border: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium">Today's Usage</span>
          <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: `${usageColor}14` }}>
            <KeyRound size={12} color={usageColor} />
          </div>
        </div>
        <div className="flex items-baseline gap-1.5 mb-3">
          <span className="text-2xl font-mono font-medium" style={{ color: usageColor }}>{req.toLocaleString()}</span>
          <span className="text-xs font-mono text-zinc-600">/ {capacity.toLocaleString()} requests</span>
        </div>
        <div className="h-[3px] rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
          <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: usageColor }} />
        </div>
      </div>

      {smallCards.map((c, i) => (
        <div
          key={c.label}
          className="rounded-xl p-4 transition-transform duration-200 hover:-translate-y-0.5 animate-in fade-in slide-in-from-bottom-1"
          style={{
            background: "#111113",
            border: "1px solid rgba(255,255,255,0.06)",
            animationDuration: "300ms",
            animationDelay: `${(i + 1) * 40}ms`,
            animationFillMode: "backwards",
          }}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium">{c.label}</span>
            <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: `${c.color}14` }}>
              <c.Icon size={12} color={c.color} />
            </div>
          </div>
          <span className="text-2xl font-mono font-medium" style={{ color: "#ECECF0" }}>{c.val}</span>
        </div>
      ))}
    </div>
  );
}