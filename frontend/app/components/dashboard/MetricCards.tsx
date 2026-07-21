import { KeyRound, CheckCircle2, Zap, Clock } from "lucide-react";
import type { AK } from "../../types";

export function MetricCards({ keys }: { keys: AK[] }) {
  const total  = keys.length;
  const active = keys.filter(k => k.status === "active").length;
  const cool   = keys.filter(k => k.status === "cooldown").length;
  const req    = keys.reduce((a, k) => a + k.used, 0);

  const cards = [
    { label: "Total Keys",       val: String(total),           color: "#71717A", Icon: KeyRound,      glow: false },
    { label: "Active Keys",      val: String(active),          color: "#00D68F", Icon: CheckCircle2,  glow: true  },
    { label: "Requests Today",   val: req.toLocaleString(),    color: "#4F8EF7", Icon: Zap,           glow: false },
    { label: "Keys in Cooldown", val: String(cool),            color: "#F59E0B", Icon: Clock,         glow: false },
  ] as const;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map(c => (
        <div key={c.label} className="rounded-xl p-4"
          style={{
            background: "#111113",
            border: "1px solid rgba(255,255,255,0.06)",
            boxShadow: c.glow ? "0 0 24px rgba(0,214,143,0.05)" : "none",
          }}>
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium">{c.label}</span>
            <div className="w-6 h-6 rounded-md flex items-center justify-center"
              style={{ background: `${c.color}14` }}>
              <c.Icon size={12} color={c.color} />
            </div>
          </div>
          <span className="text-2xl font-mono font-medium" style={{ color: c.glow ? c.color : "#ECECF0" }}>
            {c.val}
          </span>
        </div>
      ))}
    </div>
  );
}
