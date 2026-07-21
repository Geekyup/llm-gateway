import { useEffect } from "react";
import { X, RefreshCw, Power, Trash2 } from "lucide-react";
import { AreaChart, Area, XAxis, Tooltip, ResponsiveContainer } from "recharts";
import { SBadge } from "../atoms/SBadge";
import { PBadge } from "../atoms/PBadge";
import { CircP } from "../atoms/CircP";
import { S, P } from "../../lib/constants";
import { makeHourly, rel, cd } from "../../lib/format";
import type { AK } from "../../types";

export function KeyDetailDrawer({ keyData, now, onClose, onDisable, onReset, onDelete }: {
  keyData: AK; now: number;
  onClose: () => void; onDisable: () => void; onReset: () => void; onDelete: () => void;
}) {
  const s = S[keyData.status];
  const chartData = makeHourly(keyData.used);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const meta = [
    { label: "Provider",   val: P[keyData.provider].name,                                           mono: false },
    { label: "Masked Key", val: keyData.masked,                                                      mono: true  },
    { label: "Created",    val: new Date(keyData.created).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }), mono: false },
    { label: "Updated",    val: new Date(keyData.updated).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }), mono: false },
    { label: "Last Used",  val: keyData.lastUsed ? rel(keyData.lastUsed, now) : "—",                mono: false },
    { label: "Cooldown",   val: keyData.cooldownUntil ? cd(keyData.cooldownUntil, now) : "—",       mono: true  },
  ];

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose}
        style={{ background: "rgba(0,0,0,0.5)", backdropFilter: "blur(2px)" }} />
      <aside className="fixed right-0 top-0 bottom-0 z-50 w-full sm:w-96 flex flex-col overflow-y-auto"
        style={{ background: "#111113", borderLeft: "1px solid rgba(255,255,255,0.07)", boxShadow: "-24px 0 60px rgba(0,0,0,0.4)" }}>
        <div className="flex items-start justify-between p-5"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">{keyData.label}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[11px] font-mono text-zinc-600">{keyData.masked}</span>
              <PBadge provider={keyData.provider} />
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg transition-colors hover:bg-white/5 shrink-0 mt-0.5">
            <X size={16} color="#52525B" />
          </button>
        </div>

        <div className="p-5 space-y-5 flex-1">
          <div className="flex items-center gap-4">
            <CircP used={keyData.used} limit={keyData.limit} color={s.color} />
            <div className="space-y-3">
              <SBadge status={keyData.status} />
              <div>
                <p className="text-[11px] text-zinc-600 mb-0.5">Daily quota</p>
                <p className="text-sm font-mono text-zinc-200">{keyData.limit.toLocaleString()} req</p>
              </div>
              <div>
                <p className="text-[11px] text-zinc-600 mb-0.5">Remaining</p>
                <p className="text-sm font-mono" style={{ color: s.color }}>
                  {Math.max(0, keyData.limit - keyData.used).toLocaleString()} req
                </p>
              </div>
            </div>
          </div>

          <div>
            <p className="text-[10px] text-zinc-600 mb-2.5 uppercase tracking-widest font-semibold">Hourly Usage Today</p>
            <div style={{ height: 88 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 4, right: 0, left: -32, bottom: 0 }}>
                  <defs>
                    <linearGradient id="agrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={s.color} stopOpacity={0.22} />
                      <stop offset="95%" stopColor={s.color} stopOpacity={0}    />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="h"
                    tick={{ fontSize: 9, fill: "#52525B", fontFamily: "JetBrains Mono, monospace" }}
                    tickLine={false} axisLine={false} interval={3} />
                  <Tooltip
                    contentStyle={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }}
                    labelStyle={{ color: "#71717A" }} itemStyle={{ color: s.color }}
                    formatter={(v: number) => [v.toLocaleString(), "req"]} />
                  <Area type="monotone" dataKey="r" stroke={s.color} strokeWidth={1.5}
                    fill="url(#agrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.06)" }}>
            {meta.map((m, i) => (
              <div key={m.label} className="flex items-center justify-between px-3.5 py-2.5"
                style={{
                  borderBottom: i < meta.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none",
                  background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.01)",
                }}>
                <span className="text-[11px] text-zinc-600">{m.label}</span>
                <span className={`text-[11px] text-zinc-300 ${m.mono ? "font-mono" : ""}`}>{m.val}</span>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <button onClick={onReset}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-colors"
              style={{ background: "rgba(79,142,247,0.08)", color: "#4F8EF7", border: "1px solid rgba(79,142,247,0.16)" }}>
              <RefreshCw size={12} /> Reset Cooldown
            </button>
            <button onClick={onDisable}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-colors"
              style={{ background: "rgba(255,255,255,0.04)", color: "#71717A", border: "1px solid rgba(255,255,255,0.07)" }}>
              <Power size={12} />
              {keyData.status === "disabled" ? "Enable Key" : "Disable Key"}
            </button>
            <button onClick={onDelete}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-colors"
              style={{ background: "rgba(239,68,68,0.07)", color: "#EF4444", border: "1px solid rgba(239,68,68,0.16)" }}>
              <Trash2 size={12} /> Delete Key
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
