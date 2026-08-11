import { useMemo, useState } from "react";
import { KeyRound, Loader2, Stethoscope, Edit2, Power, Search, LayoutGrid } from "lucide-react";
import { rel, cd } from "../../lib/domain";
import type { AK, PF, SF } from "../../types";
import { StatusBadge } from "../shared/StatusBadge";
import { ProviderBadge } from "../shared/ProviderBadge";
import { UsageBar } from "../shared/UsageBar";
import { ProviderFilterDropdown } from "./ProviderFilterDropdown";
import { StatusFilterDropdown } from "./StatusFilterDropdown";
import { ProviderGroupHeader } from "./ProviderGroupHeader";
import { useFlipAnimation } from "../../lib/useFlipAnimation";


const PROVIDER_ORDER = ["gemini", "openrouter", "groq"];

function groupByProvider(list: AK[]): { provider: string; items: AK[] }[] {
  const map = new Map<string, AK[]>();
  for (const k of list) {
    if (!map.has(k.provider)) map.set(k.provider, []);
    map.get(k.provider)!.push(k);
  }
  const providers = [...map.keys()].sort((a, b) => {
    const ai = PROVIDER_ORDER.indexOf(a);
    const bi = PROVIDER_ORDER.indexOf(b);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });
  return providers.map((provider) => ({ provider, items: map.get(provider)! }));
}

export function KeysTable({
  keys,
  filter,
  onFilter,
  statusFilter,
  onStatusFilter,
  onSelect,
  onEdit,
  onToggle,
  onCheck,
  checkingIds,
  now,
}: {
  keys: AK[];
  filter: PF;
  onFilter: (f: PF) => void;
  statusFilter: SF;
  onStatusFilter: (f: SF) => void;
  now: number;
  onSelect: (id: string) => void;
  onEdit: (id: string) => void;
  onToggle: (id: string) => void;
  onCheck: (id: string) => void;
  checkingIds: Set<string>;
}) {
  const [query, setQuery] = useState("");
  const [grouped, setGrouped] = useState(false);
  const q = query.trim().toLowerCase();

  const filtered = keys.filter((k) => {
    if (filter !== "all" && k.provider !== filter) return false;
    if (statusFilter !== "all" && k.status !== statusFilter) return false;
    if (q && !k.label.toLowerCase().includes(q)) return false;
    return true;
  });

  const groups = useMemo(() => groupByProvider(filtered), [filtered]);
  const orderedRows = useMemo(
    () => (grouped ? groups.flatMap((g) => g.items) : filtered),
    [grouped, groups, filtered]
  );

  const mobileFlipRef = useFlipAnimation<HTMLDivElement>(grouped);
  const desktopFlipRef = useFlipAnimation<HTMLDivElement>(grouped);

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.06)" }}>
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-2 px-4 py-2.5" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: "#0F0F11" }}>
        <span className="text-xs font-medium text-zinc-400 shrink-0">API Keys</span>
        <div className="flex items-end gap-2 sm:gap-3 min-w-0 flex-wrap sm:flex-nowrap">
          <div className="relative hidden sm:block mb-[1px]">
            <Search size={12} color="#52525B" className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search keys..."
              className="text-[11px] rounded-md pl-7 pr-2.5 py-1 outline-none w-[150px] focus:w-[190px] transition-all"
              style={{ color: "#ECECF0", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)" }}
            />
          </div>
          <ProviderFilterDropdown filter={filter} onFilter={onFilter} />
          <StatusFilterDropdown filter={statusFilter} onFilter={onStatusFilter} />
          <button
            onClick={() => setGrouped((g) => !g)}
            className="flex items-center justify-center w-[26px] h-[26px] rounded-md transition-all mb-[1px]"
            style={{
              background: grouped ? "rgba(0,214,143,0.12)" : "rgba(255,255,255,0.06)",
              border: `1px solid ${grouped ? "rgba(0,214,143,0.28)" : "rgba(255,255,255,0.08)"}`,
            }}
            title={grouped ? "Show flat list" : "Group by provider"}
            aria-label={grouped ? "Show flat list" : "Group by provider"}
          >
            <LayoutGrid size={13} color={grouped ? "#00D68F" : "#71717A"} />
          </button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="px-4 py-16 text-center" style={{ background: "#111113" }}>
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <KeyRound size={18} color="#3F3F46" />
            </div>
            <p className="text-sm text-zinc-500">No keys found</p>
            <p className="text-xs text-zinc-600">
              {keys.length === 0 ? "Add your first API key to get started" : "Try a different search or filter"}
            </p>
          </div>
        </div>
      ) : (
        <>
          <div ref={mobileFlipRef} className="sm:hidden" style={{ background: "#111113" }}>
            {grouped
              ? (
                <div className="flex flex-col gap-2 p-2.5">
                  {groups.map((g) => (
                    <div key={g.provider} className="rounded-lg overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.07)", background: "#0F0F11" }}>
                      <ProviderGroupHeader provider={g.provider} keys={g.items} />
                      <div className="divide-y divide-white/[0.03]" style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                        {g.items.map((k) => (
                          <MobileKeyRow key={k.id} k={k} now={now} checkingIds={checkingIds} onSelect={onSelect} onEdit={onEdit} onToggle={onToggle} onCheck={onCheck} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )
              : (
                <div className="divide-y divide-white/[0.03]">
                  {orderedRows.map((k) => (
                    <MobileKeyRow key={k.id} k={k} now={now} checkingIds={checkingIds} onSelect={onSelect} onEdit={onEdit} onToggle={onToggle} onCheck={onCheck} />
                  ))}
                </div>
              )}
          </div>

          <div ref={desktopFlipRef} className="hidden sm:block" style={{ background: grouped ? "transparent" : "#111113" }}>
            {grouped ? (
              <div className="flex flex-col gap-2.5 p-2.5">
                {groups.map((g) => (
                  <div key={g.provider} className="rounded-lg overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.07)", background: "#0F0F11" }}>
                    <ProviderGroupHeader provider={g.provider} keys={g.items} />
                    <div className="overflow-x-auto" style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                      <table className="w-full min-w-[760px]" style={{ tableLayout: "fixed" }}>
                        <ColumnWidths />
                        <tbody className="divide-y divide-white/[0.03]">
                          {g.items.map((k) => (
                            <DesktopKeyRow key={k.id} k={k} now={now} checkingIds={checkingIds} onSelect={onSelect} onEdit={onEdit} onToggle={onToggle} onCheck={onCheck} />
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px]" style={{ tableLayout: "fixed" }}>
                  <ColumnWidths />
                  <thead>
                    <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                      {["Label", "Provider", "Status", "Usage", "Last Used", ""].map((h, i) => (
                        <th key={i} className="px-4 py-2.5 text-left text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.03]">
                    {orderedRows.map((k) => (
                      <DesktopKeyRow key={k.id} k={k} now={now} checkingIds={checkingIds} onSelect={onSelect} onEdit={onEdit} onToggle={onToggle} onCheck={onCheck} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function ColumnWidths() {
  return (
    <colgroup>
      <col style={{ width: "30%" }} />
      <col style={{ width: "12%" }} />
      <col style={{ width: "14%" }} />
      <col style={{ width: "20%" }} />
      <col style={{ width: "12%" }} />
      <col style={{ width: "12%" }} />
    </colgroup>
  );
}

function MobileKeyRow({
  k, now, checkingIds, onSelect, onEdit, onToggle, onCheck,
}: {
  k: AK; now: number; checkingIds: Set<string>;
  onSelect: (id: string) => void; onEdit: (id: string) => void; onToggle: (id: string) => void; onCheck: (id: string) => void;
}) {
  return (
    <div data-flip-id={k.id} className="px-4 py-3.5 transition-colors active:bg-white/[0.03] cursor-pointer" onClick={() => onSelect(k.id)}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <div className="text-sm font-medium text-zinc-200 leading-none truncate">{k.label}</div>
          <div className="text-[11px] font-mono text-zinc-600 mt-1 truncate">
            {k.masked}
            {k.model && <span className="text-zinc-700"> · {k.model}</span>}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => onCheck(k.id)} disabled={checkingIds.has(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-white/5 disabled:opacity-50" title="Test key">
            {checkingIds.has(k.id) ? <Loader2 size={13} color="#71717A" className="animate-spin" /> : <Stethoscope size={13} color="#71717A" />}
          </button>
          <button onClick={() => onEdit(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-white/5" title="Edit">
            <Edit2 size={13} color="#71717A" />
          </button>
          <button onClick={() => onToggle(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-white/5" title={k.status === "disabled" ? "Enable" : "Disable"}>
            <Power size={13} color={k.status === "disabled" ? "#ECECF0" : "#71717A"} />
          </button>
        </div>
      </div>
      <div className="flex items-center gap-2 mb-2.5">
        <ProviderBadge provider={k.provider} />
        <StatusBadge status={k.status} />
      </div>
      <UsageBar used={k.used} limit={k.limit} status={k.status} />
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
  );
}

function DesktopKeyRow({
  k, now, checkingIds, onSelect, onEdit, onToggle, onCheck,
}: {
  k: AK; now: number; checkingIds: Set<string>;
  onSelect: (id: string) => void; onEdit: (id: string) => void; onToggle: (id: string) => void; onCheck: (id: string) => void;
}) {
  return (
    <tr data-flip-id={k.id} className="group cursor-pointer transition-colors hover:bg-white/[0.02]" onClick={() => onSelect(k.id)}>
      <td className="px-4 py-3 min-w-0">
        <div className="text-sm font-medium text-zinc-200 leading-none truncate">{k.label}</div>
        <div className="text-[11px] font-mono text-zinc-600 mt-1 truncate">
          {k.masked}
          {k.model && <span className="text-zinc-700"> · {k.model}</span>}
        </div>
      </td>
      <td className="px-4 py-3"><ProviderBadge provider={k.provider} /></td>
      <td className="px-4 py-3">
        <StatusBadge status={k.status} cooldownText={k.cooldownUntil ? cd(k.cooldownUntil, now) : undefined} />
      </td>
      <td className="px-4 py-3"><UsageBar used={k.used} limit={k.limit} status={k.status} /></td>
      <td className="px-4 py-3">
        <span className="text-xs font-mono text-zinc-500">{k.lastUsed ? rel(k.lastUsed, now) : "—"}</span>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => onCheck(k.id)} disabled={checkingIds.has(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-white/5 disabled:opacity-50" title="Test key">
            {checkingIds.has(k.id) ? <Loader2 size={13} color="#71717A" className="animate-spin" /> : <Stethoscope size={13} color="#71717A" />}
          </button>
          <button onClick={() => onEdit(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-white/5" title="Edit">
            <Edit2 size={13} color="#71717A" />
          </button>
          <button onClick={() => onToggle(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-white/5" title={k.status === "disabled" ? "Enable" : "Disable"}>
            <Power size={13} color={k.status === "disabled" ? "#ECECF0" : "#71717A"} />
          </button>
        </div>
      </td>
    </tr>
  );
}