import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, Tooltip, ResponsiveContainer } from "recharts";
import { X, Loader2, Stethoscope, RefreshCw, Power, Trash2 } from "lucide-react";
import { api } from "../../lib/api";
import { usePolling } from "../../lib/usePolling";
import { STATUS_META, PROVIDER_META, rel, cd } from "../../lib/domain";
import type { AK } from "../../types";
import { StatusBadge } from "../shared/StatusBadge";
import { ProviderBadge } from "../shared/ProviderBadge";
import { UsageCircle } from "../shared/UsageCircle";

export function KeyDetailDrawer({
  keyData,
  now,
  onClose,
  onDisable,
  onReset,
  onDelete,
  onCheck,
  checking,
  resetting,
}: {
  keyData: AK;
  now: number;
  onClose: () => void;
  onDisable: () => void;
  onReset: () => void;
  onDelete: () => void;
  onCheck: () => void;
  checking: boolean;
  resetting: boolean;
}) {
  const s = STATUS_META[keyData.status];
  const [chartMode, setChartMode] = useState<"requests" | "tokens">("requests");
  const [chartData, setChartData] = useState<{ h: string; r: number }[] | null>(null);
  const [chartError, setChartError] = useState(false);
  const [tokenData, setTokenData] = useState<{ h: string; r: number; prompt: number; completion: number }[] | null>(null);
  const [tokenError, setTokenError] = useState(false);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setChartData(null);
    setChartError(false);
    setTokenData(null);
    setTokenError(false);
    setChartMode("requests");
    api.hourlyUsage(Number(keyData.id))
      .then((res) => {
        if (cancelled) return;
        setChartData(res.points.map((p) => ({ h: `${p.hour}h`, r: p.requests })));
      })
      .catch(() => {
        if (!cancelled) setChartError(true);
      });
    return () => { cancelled = true; };
  }, [keyData.id]);

  useEffect(() => {
    if (chartMode !== "tokens" || tokenData !== null || tokenError) return;
    let cancelled = false;
    api.hourlyTokenUsage(Number(keyData.id))
      .then((res) => {
        if (cancelled) return;
        setTokenData(res.points.map((p) => ({ h: `${p.hour}h`, r: p.total_tokens, prompt: p.prompt_tokens, completion: p.completion_tokens })));
      })
      .catch(() => {
        if (!cancelled) setTokenError(true);
      });
    return () => { cancelled = true; };
  }, [chartMode, keyData.id, tokenData, tokenError]);

  
  usePolling(() => {
    if (chartMode === "requests") {
      api.hourlyUsage(Number(keyData.id))
        .then((res) => setChartData(res.points.map((p) => ({ h: `${p.hour}h`, r: p.requests }))))
        .catch(() => {});
    } else {
      api.hourlyTokenUsage(Number(keyData.id))
        .then((res) => setTokenData(res.points.map((p) => ({ h: `${p.hour}h`, r: p.total_tokens, prompt: p.prompt_tokens, completion: p.completion_tokens }))))
        .catch(() => {});
    }
  }, 20000);

  const meta = [
    { label: "Provider",   val: PROVIDER_META[keyData.provider].name, mono: false },
    { label: "Model",      val: keyData.model ?? "Any (unpinned)", mono: true },
    { label: "Masked Key", val: keyData.masked, mono: true },
    { label: "Created",    val: new Date(keyData.created).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }), mono: false },
    { label: "Updated",    val: new Date(keyData.updated).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }), mono: false },
    { label: "Last Used",  val: keyData.lastUsed ? rel(keyData.lastUsed, now) : "—", mono: false },
    { label: "Cooldown",   val: keyData.cooldownUntil ? cd(keyData.cooldownUntil, now) : "—", mono: true },
  ];

  return (
    <>
      <div className="fixed inset-0 z-40 animate-in fade-in duration-200" onClick={onClose} style={{ background: "rgba(0,0,0,0.5)", backdropFilter: "blur(2px)" }} />
      <aside
        className="fixed right-0 top-0 bottom-0 z-50 w-full sm:w-96 flex flex-col overflow-y-auto thin-scrollbar animate-in slide-in-from-right duration-300 ease-out"
        style={{ background: "#111113", borderLeft: "1px solid rgba(255,255,255,0.07)", boxShadow: "-24px 0 60px rgba(0,0,0,0.4)" }}
      >
        <div className="flex items-start justify-between p-5" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">{keyData.label}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[11px] font-mono text-zinc-600">{keyData.masked}</span>
              <ProviderBadge provider={keyData.provider} />
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg transition-colors hover:bg-white/5 shrink-0 mt-0.5">
            <X size={16} color="#52525B" />
          </button>
        </div>

        <div className="p-5 space-y-5 flex-1">
          <div className="flex items-center gap-4">
            <UsageCircle used={keyData.used} limit={keyData.limit} color={s.color} />
            <div className="space-y-3">
              <StatusBadge status={keyData.status} />
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
            <div className="flex items-center justify-between mb-2.5">
              <p className="text-[10px] text-zinc-600 uppercase tracking-widest font-semibold">
                {chartMode === "requests" ? "Hourly Usage Today" : "Hourly Tokens Today"}
              </p>
              <div className="flex gap-0.5 rounded-md p-0.5" style={{ background: "rgba(255,255,255,0.03)" }}>
                {(["requests", "tokens"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setChartMode(m)}
                    className="px-2 py-0.5 rounded text-[10px] font-medium transition-all"
                    style={{ color: chartMode === m ? "#ECECF0" : "#52525B", background: chartMode === m ? "rgba(255,255,255,0.07)" : "transparent" }}
                  >
                    {m === "requests" ? "Requests" : "Tokens"}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ height: 88 }} className="flex items-center justify-center">
              {chartMode === "requests" ? (
                chartError ? (
                  <p className="text-[11px] text-zinc-600">Couldn't load usage data</p>
                ) : chartData === null ? (
                  <Loader2 size={16} className="animate-spin" color="#52525B" />
                ) : chartData.every((p) => p.r === 0) ? (
                  <p className="text-[11px] text-zinc-600">No requests yet today</p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 4, right: 0, left: -32, bottom: 0 }}>
                      <defs>
                        <linearGradient id="agrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={s.color} stopOpacity={0.22} />
                          <stop offset="95%" stopColor={s.color} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis
                        dataKey="h"
                        padding={{ left: 0, right: 0 }}
                        tick={{ fontSize: 9, fill: "#52525B", fontFamily: "JetBrains Mono, monospace" }}
                        tickLine={false}
                        axisLine={false}
                        interval={3}
                      />
                      <Tooltip
                        contentStyle={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }}
                        labelStyle={{ color: "#71717A" }}
                        itemStyle={{ color: s.color }}
                        formatter={(v: number) => [v.toLocaleString(), "req"]}
                      />
                      <Area type="monotone" dataKey="r" stroke={s.color} strokeWidth={1.5} fill="url(#agrad)" dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                )
              ) : tokenError ? (
                <p className="text-[11px] text-zinc-600">Couldn't load token data</p>
              ) : tokenData === null ? (
                <Loader2 size={16} className="animate-spin" color="#52525B" />
              ) : tokenData.every((p) => p.r === 0) ? (
                <p className="text-[11px] text-zinc-600">No token usage yet today</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={tokenData} margin={{ top: 4, right: 0, left: -32, bottom: 0 }}>
                    <defs>
                      <linearGradient id="tgrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#A78BFA" stopOpacity={0.22} />
                        <stop offset="95%" stopColor="#A78BFA" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="h"
                      padding={{ left: 0, right: 0 }}
                      tick={{ fontSize: 9, fill: "#52525B", fontFamily: "JetBrains Mono, monospace" }}
                      tickLine={false}
                      axisLine={false}
                      interval={3}
                    />
                    <Tooltip
                      contentStyle={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }}
                      labelStyle={{ color: "#71717A" }}
                      formatter={(v: number, name: string, p: { payload?: { prompt: number; completion: number } }) => {
                        if (name !== "r") return [v, name];
                        const pt = p.payload;
                        return [
                          pt ? `${v.toLocaleString()} (${pt.prompt.toLocaleString()} in / ${pt.completion.toLocaleString()} out)` : v.toLocaleString(),
                          "tokens",
                        ];
                      }}
                    />
                    <Area type="monotone" dataKey="r" stroke="#A78BFA" strokeWidth={1.5} fill="url(#tgrad)" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.06)" }}>
            {meta.map((m, i) => (
              <div
                key={m.label}
                className="flex items-center justify-between px-3.5 py-2.5"
                style={{
                  borderBottom: i < meta.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none",
                  background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.01)",
                }}
              >
                <span className="text-[11px] text-zinc-600">{m.label}</span>
                <span className={`text-[11px] text-zinc-300 ${m.mono ? "font-mono" : ""}`}>{m.val}</span>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <button
              onClick={onCheck}
              disabled={checking}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.97] disabled:active:scale-100 disabled:opacity-50"
              style={{ background: "rgba(0,214,143,0.08)", color: "#00D68F", border: "1px solid rgba(0,214,143,0.16)" }}
            >
              {checking ? <Loader2 size={12} className="animate-spin" /> : <Stethoscope size={12} />}
              {checking ? "Checking..." : "Test Key"}
            </button>
            <button
              onClick={onReset}
              disabled={resetting}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.97] disabled:active:scale-100 disabled:opacity-50"
              style={{ background: "rgba(79,142,247,0.08)", color: "#4F8EF7", border: "1px solid rgba(79,142,247,0.16)" }}
            >
              {resetting ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              {resetting ? "Resetting..." : "Reset Cooldown"}
            </button>
            <button
              onClick={onDisable}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.97]"
              style={{ background: "rgba(255,255,255,0.04)", color: "#71717A", border: "1px solid rgba(255,255,255,0.07)" }}
            >
              <Power size={12} />
              {keyData.status === "disabled" ? "Enable Key" : "Disable Key"}
            </button>
            <button
              onClick={onDelete}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.97]"
              style={{ background: "rgba(239,68,68,0.07)", color: "#EF4444", border: "1px solid rgba(239,68,68,0.16)" }}
            >
              <Trash2 size={12} /> Delete Key
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
