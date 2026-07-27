import { KeyRound, Edit2, Power } from "lucide-react";
import { SBadge } from "../atoms/SBadge";
import { PBadge } from "../atoms/PBadge";
import { UBar } from "../atoms/UBar";
import { rel, cd } from "../../lib/format";
import type { AK, PF } from "../../types";

export function KeysTable({ keys, filter, onFilter, onSelect, onEdit, onToggle, now }: {
  keys: AK[]; filter: PF; onFilter: (f: PF) => void; now: number;
  onSelect: (id: string) => void; onEdit: (id: string) => void; onToggle: (id: string) => void;
}) {
  const filtered = filter === "all" ? keys : keys.filter(k => k.provider === filter);

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.06)" }}>
      <div className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: "#0F0F11" }}>
        <span className="text-xs font-medium text-zinc-400">API Keys</span>
        <div className="flex gap-1">
          {(["all", "gemini"] as PF[]).map(f => (
            <button key={f} onClick={() => onFilter(f)}
              className="px-2.5 py-1 rounded-md text-[11px] font-medium capitalize transition-all"
              style={{
                color: filter === f ? "#ECECF0" : "#52525B",
                background: filter === f ? "rgba(255,255,255,0.08)" : "transparent",
                border: filter === f ? "1px solid rgba(255,255,255,0.1)" : "1px solid transparent",
              }}>
              {f}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="px-4 py-16 text-center" style={{ background: "#111113" }}>
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <KeyRound size={18} color="#3F3F46" />
            </div>
            <p className="text-sm text-zinc-500">No keys found</p>
            <p className="text-xs text-zinc-600">Add your first API key to get started</p>
          </div>
        </div>
      ) : (
        <>
          {/* Mobile: stacked cards */}
          <div className="sm:hidden" style={{ background: "#111113" }}>
            {filtered.map((k, i) => (
              <div key={k.id} className="px-4 py-3.5 active:bg-white/[0.02]"
                style={{ borderBottom: i < filtered.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none" }}
                onClick={() => onSelect(k.id)}>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-zinc-200 leading-none truncate">{k.label}</div>
                    <div className="text-[11px] font-mono text-zinc-600 mt-1">{k.masked}</div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0" onClick={e => e.stopPropagation()}>
                    <button onClick={() => onEdit(k.id)}
                      className="p-1.5 rounded-md transition-colors hover:bg-white/5" title="Edit">
                      <Edit2 size={13} color="#71717A" />
                    </button>
                    <button onClick={() => onToggle(k.id)}
                      className="p-1.5 rounded-md transition-colors hover:bg-white/5"
                      title={k.status === "disabled" ? "Enable" : "Disable"}>
                      <Power size={13} color={k.status === "disabled" ? "#ECECF0" : "#71717A"} />
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-2 mb-2.5">
                  <PBadge provider={k.provider} />
                  <SBadge status={k.status} />
                </div>
                <UBar used={k.used} limit={k.limit} status={k.status} />
                <div className="flex items-center justify-between mt-2.5">
                  <span className="text-[11px] text-zinc-600">
                    Last used: <span className="font-mono text-zinc-500">{k.lastUsed ? rel(k.lastUsed, now) : "—"}</span>
                  </span>
                  {k.cooldownUntil ? (
                    <span className="text-[11px] font-mono" style={{ color: "#F59E0B" }}>
                      {cd(k.cooldownUntil, now)}
                    </span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          {/* Desktop / tablet: table */}
          <div className="hidden sm:block overflow-x-auto" style={{ background: "#111113" }}>
            <table className="w-full min-w-[760px]">
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                  {["Label", "Provider", "Status", "Usage", "Cooldown", "Last Used", ""].map((h, i) => (
                    <th key={i}
                      className="px-4 py-2.5 text-left text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((k, i) => (
                  <tr key={k.id} className="group cursor-pointer"
                    style={{ borderBottom: i < filtered.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none" }}
                    onClick={() => onSelect(k.id)}
                    onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.02)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-zinc-200 leading-none">{k.label}</div>
                      <div className="text-[11px] font-mono text-zinc-600 mt-1">{k.masked}</div>
                    </td>
                    <td className="px-4 py-3"><PBadge provider={k.provider} /></td>
                    <td className="px-4 py-3"><SBadge status={k.status} /></td>
                    <td className="px-4 py-3"><UBar used={k.used} limit={k.limit} status={k.status} /></td>
                    <td className="px-4 py-3">
                      {k.cooldownUntil ? (
                        <span className="text-xs font-mono" style={{ color: "#F59E0B" }}>
                          {cd(k.cooldownUntil, now)}
                        </span>
                      ) : (
                        <span className="text-xs text-zinc-700">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-mono text-zinc-500">
                        {k.lastUsed ? rel(k.lastUsed, now) : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={e => e.stopPropagation()}>
                        <button onClick={() => onEdit(k.id)}
                          className="p-1.5 rounded-md transition-colors hover:bg-white/5" title="Edit">
                          <Edit2 size={13} color="#71717A" />
                        </button>
                        <button onClick={() => onToggle(k.id)}
                          className="p-1.5 rounded-md transition-colors hover:bg-white/5"
                          title={k.status === "disabled" ? "Enable" : "Disable"}>
                          <Power size={13} color={k.status === "disabled" ? "#ECECF0" : "#71717A"} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
