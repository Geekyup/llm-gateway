import { ArrowRight } from "lucide-react";
import type { LR } from "../../types";
import { ProviderBadge } from "../shared/ProviderBadge";
import { MonitorCharts } from "./MonitorCharts";

export function LiveMonitor({ reqs, now }: { reqs: LR[]; now: number }) {
  return (
    <div>
      <MonitorCharts reqs={reqs} now={now} />

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center justify-between px-4 py-2.5" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: "#0F0F11" }}>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: "#00D68F", boxShadow: "0 0 6px rgba(0,214,143,0.7)" }} />
            <span className="text-xs font-medium text-zinc-400">Live Request Feed</span>
          </div>
          <span className="text-[11px] font-mono text-zinc-600">{reqs.length} captured</span>
        </div>

        <div style={{ background: "#111113" }}>
        <div
          className="hidden sm:grid px-4 py-2 min-w-0"
          style={{ gridTemplateColumns: "72px 88px minmax(0,1fr) 52px 64px 56px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}
        >
          {["Time", "Provider", "Key / Chain", "Status", "Tokens", "Latency"].map((h) => (
            <span key={h} className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">{h}</span>
          ))}
        </div>

        {reqs.map((r, i) => {
          const cColor = r.code === 200 ? "#00D68F" : r.code === 429 ? "#F59E0B" : "#EF4444";
          const isNewest = i === 0;
          return (
            <div key={r.id} className={isNewest ? "animate-in fade-in slide-in-from-top-2 duration-300 ease-out" : undefined}>
              <div className="sm:hidden px-4 py-2.5" style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2 min-w-0">
                    <ProviderBadge provider={r.provider} />
                    <span className="text-[11px] font-mono text-zinc-300 truncate">{r.keyLabel}</span>
                  </div>
                  <span className="text-[11px] font-mono px-1.5 py-0.5 rounded shrink-0" style={{ color: cColor, background: `${cColor}12`, border: `1px solid ${cColor}22` }}>
                    {r.code}
                  </span>
                </div>
                {r.chain && r.chain.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-nowrap overflow-x-auto mb-1.5">
                    {r.chain.map((c, i) => (
                      <div key={`${c.label}-${c.code}-${i}`} className="flex items-center gap-1.5 shrink-0">
                        <span className="text-[11px] font-mono text-zinc-500 truncate max-w-[100px]">{c.label}</span>
                        <span className="text-[11px] font-mono px-1 py-0.5 rounded shrink-0" style={{ color: "#F59E0B", background: "rgba(245,158,11,0.1)" }}>{c.code}</span>
                        <ArrowRight size={10} color="#3F3F46" className="shrink-0" />
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono text-zinc-600">
                    {new Date(r.ts).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </span>
                  <div className="flex items-center gap-2">
                    {r.totalTokens != null && (
                      <span className="text-[11px] font-mono text-zinc-500">{r.totalTokens.toLocaleString()} tok</span>
                    )}
                    <span className="text-[11px] font-mono text-zinc-600">{r.latency}ms</span>
                  </div>
                </div>
              </div>

              <div
                className="hidden sm:grid items-center px-4 py-2.5 transition-colors min-w-0"
                style={{ gridTemplateColumns: "72px 88px minmax(0,1fr) 52px 64px 56px", borderBottom: "1px solid rgba(255,255,255,0.03)" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.015)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <span className="text-[11px] font-mono text-zinc-600">
                  {new Date(r.ts).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                </span>
                <ProviderBadge provider={r.provider} />
                <div className="flex items-center gap-1.5 min-w-0 overflow-x-auto">
                  {r.chain?.map((c, i) => (
                    <div key={`${c.label}-${c.code}-${i}`} className="flex items-center gap-1.5 shrink-0">
                      <span className="text-[11px] font-mono text-zinc-500 truncate max-w-[100px]">{c.label}</span>
                      <span className="text-[11px] font-mono px-1 py-0.5 rounded shrink-0" style={{ color: "#F59E0B", background: "rgba(245,158,11,0.1)" }}>{c.code}</span>
                      <ArrowRight size={10} color="#3F3F46" className="shrink-0" />
                    </div>
                  ))}
                  <span className="text-[11px] font-mono text-zinc-300 truncate">{r.keyLabel}</span>
                </div>
                <span className="text-[11px] font-mono px-1.5 py-0.5 rounded justify-self-start" style={{ color: cColor, background: `${cColor}12`, border: `1px solid ${cColor}22` }}>
                  {r.code}
                </span>
                <span className="text-[11px] font-mono text-zinc-500">
                  {r.totalTokens != null ? r.totalTokens.toLocaleString() : "—"}
                </span>
                <span className="text-[11px] font-mono text-zinc-600 justify-self-end">{r.latency}ms</span>
              </div>
            </div>
          );
        })}
        </div>
      </div>
    </div>
  );
}