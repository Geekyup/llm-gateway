import { useMemo, useState } from "react";
import { KeyRound, Loader2, Stethoscope, Edit2, Power, Search, LayoutGrid } from "lucide-react";
import { rel, cd, pingMeta } from "../../lib/domain";
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
    <div className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--line)" }}>
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-2 px-4 py-3" style={{ borderBottom: "1px solid var(--line)", background: "var(--sidebar)" }}>
        <span className="flex items-center gap-2 text-sm font-semibold text-ink shrink-0">API keys<span className="text-[12px] font-mono font-normal text-ink-3 px-1.5 py-0.5 rounded" style={{ background: "color-mix(in srgb, var(--ink) 7%, transparent)" }}>{keys.length}</span></span>
        <div className="flex items-center gap-2 min-w-0 flex-wrap sm:flex-nowrap">
          <div className="relative hidden sm:block">
            <Search size={12} color="var(--ink-4)" className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search keys..."
              className="text-[13px] rounded-md pl-7 pr-2.5 py-1.5 outline-none w-[170px] focus:w-[220px] transition-all"
              style={{ color: "var(--ink)", background: "color-mix(in srgb, var(--ink) 6%, transparent)", border: "1px solid color-mix(in srgb, var(--ink) 8.4%, transparent)" }}
            />
          </div>
          <ProviderFilterDropdown filter={filter} onFilter={onFilter} />
          <StatusFilterDropdown filter={statusFilter} onFilter={onStatusFilter} />
          <button
            onClick={() => setGrouped((g) => !g)}
            className="flex items-center justify-center gap-1.5 h-[30px] px-2 rounded-md transition-all text-[13px] font-medium"
            style={{
              background: grouped ? "color-mix(in srgb, var(--accent) 12%, transparent)" : "color-mix(in srgb, var(--ink) 6%, transparent)",
              border: `1px solid ${grouped ? "color-mix(in srgb, var(--accent) 28%, transparent)" : "color-mix(in srgb, var(--ink) 8.4%, transparent)"}`,
            }}
            title={grouped ? "Show flat list" : "Group by provider"}
            aria-label={grouped ? "Show flat list" : "Group by provider"}
          >
            <LayoutGrid size={13} color={grouped ? "var(--accent)" : "var(--ink-3)"} />
            <span className="hidden sm:inline" style={{ color: grouped ? "var(--accent)" : "var(--ink-2)" }}>Group</span>
          </button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="px-4 py-16 text-center" style={{ background: "var(--card)" }}>
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: "color-mix(in srgb, var(--ink) 3%, transparent)", border: "1px solid var(--line)" }}>
              <KeyRound size={18} color="var(--ink-4)" />
            </div>
            <p className="text-sm text-ink-3">No keys found</p>
            <p className="text-[13px] text-ink-3">
              {keys.length === 0 ? "Add your first API key to get started" : "Try a different search or filter"}
            </p>
          </div>
        </div>
      ) : (
        <>
          <div ref={mobileFlipRef} className="sm:hidden" style={{ background: "var(--card)" }}>
            {grouped
              ? (
                <div className="flex flex-col gap-2 p-2.5">
                  {groups.map((g) => (
                    <div key={g.provider} className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--line)", background: "var(--sidebar)" }}>
                      <ProviderGroupHeader provider={g.provider} keys={g.items} />
                      <div className="divide-y divide-ink/[0.03]" style={{ borderTop: "1px solid var(--line)" }}>
                        {g.items.map((k) => (
                          <MobileKeyRow key={k.id} k={k} now={now} checkingIds={checkingIds} onSelect={onSelect} onEdit={onEdit} onToggle={onToggle} onCheck={onCheck} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )
              : (
                <div className="divide-y divide-ink/[0.03]">
                  {orderedRows.map((k) => (
                    <MobileKeyRow key={k.id} k={k} now={now} checkingIds={checkingIds} onSelect={onSelect} onEdit={onEdit} onToggle={onToggle} onCheck={onCheck} />
                  ))}
                </div>
              )}
          </div>

          <div ref={desktopFlipRef} className="hidden sm:block" style={{ background: grouped ? "transparent" : "var(--card)" }}>
            {grouped ? (
              <div className="flex flex-col gap-2.5 p-2.5">
                {groups.map((g) => (
                  <div key={g.provider} className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--line)", background: "var(--sidebar)" }}>
                    <ProviderGroupHeader provider={g.provider} keys={g.items} />
                    <div className="overflow-x-auto" style={{ borderTop: "1px solid var(--line)" }}>
                      <table className="w-full min-w-[760px]" style={{ tableLayout: "fixed" }}>
                        <ColumnWidths />
                        <tbody className="divide-y divide-ink/[0.03]">
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
                    <tr style={{ borderBottom: "1px solid color-mix(in srgb, var(--ink) 4.2%, transparent)" }}>
                      {["Label", "Provider", "Status", "Usage", "Ping", "Last Used", ""].map((h, i) => (
                        <th key={i} className="px-4 py-2.5 text-left text-[13px] font-medium text-ink-3">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink/[0.03]">
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
      <col style={{ width: "26%" }} />
      <col style={{ width: "11%" }} />
      <col style={{ width: "13%" }} />
      <col style={{ width: "18%" }} />
      <col style={{ width: "9%" }} />
      <col style={{ width: "11%" }} />
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
    <div data-flip-id={k.id} className="px-4 py-3.5 transition-colors active:bg-ink/[0.03] cursor-pointer" onClick={() => onSelect(k.id)}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <div className="text-sm font-medium text-ink leading-tight truncate">{k.label}</div>
          <div className="text-[13px] font-mono text-ink-3 mt-1 truncate">
            {k.masked}
            {k.model && <span className="text-ink-2"> · {k.model}</span>}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => onCheck(k.id)} disabled={checkingIds.has(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-ink/5 disabled:opacity-50" title="Test key">
            {checkingIds.has(k.id) ? <Loader2 size={13} color="var(--ink-3)" className="animate-spin" /> : <Stethoscope size={13} color="var(--ink-3)" />}
          </button>
          <button onClick={() => onEdit(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-ink/5" title="Edit">
            <Edit2 size={13} color="var(--ink-3)" />
          </button>
          <button onClick={() => onToggle(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-ink/5" title={k.status === "disabled" ? "Enable" : "Disable"}>
            <Power size={13} color={k.status === "disabled" ? "var(--ink)" : "var(--ink-3)"} />
          </button>
        </div>
      </div>
      <div className="flex items-center gap-2 mb-2.5">
        <ProviderBadge provider={k.provider} />
        <StatusBadge status={k.status} />
      </div>
      <UsageBar used={k.used} limit={k.limit} status={k.status} />
      <div className="flex items-center justify-between mt-2.5">
        <span className="text-[13px] text-ink-3">
          Ping: <span className="font-mono" style={{ color: pingMeta(k.pingMs).color }}>{pingMeta(k.pingMs).text}</span>
          <span className="text-ink-4"> · </span>
          Last used: <span className="font-mono text-ink-3">{k.lastUsed ? rel(k.lastUsed, now) : "—"}</span>
        </span>
        {k.cooldownUntil ? (
          <span className="text-[13px] font-mono" style={{ color: "var(--warn)" }}>
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
    <tr data-flip-id={k.id} className="group cursor-pointer transition-colors hover:bg-ink/[0.02]" onClick={() => onSelect(k.id)}>
      <td className="px-4 py-3.5 min-w-0">
        <div className="text-sm font-medium text-ink leading-tight truncate">{k.label}</div>
        <div className="text-[13px] font-mono text-ink-3 mt-1 truncate">
          {k.masked}
          {k.model && <span className="text-ink-2"> · {k.model}</span>}
        </div>
      </td>
      <td className="px-4 py-3.5"><ProviderBadge provider={k.provider} /></td>
      <td className="px-4 py-3.5">
        <StatusBadge status={k.status} cooldownText={k.cooldownUntil ? cd(k.cooldownUntil, now) : undefined} />
      </td>
      <td className="px-4 py-3.5"><UsageBar used={k.used} limit={k.limit} status={k.status} /></td>
      <td className="px-4 py-3.5">
        <span
          className="text-[13px] font-mono"
          style={{ color: pingMeta(k.pingMs).color }}
          title={k.pingAt ? `Checked ${rel(k.pingAt, now)}` : "Not checked yet"}
        >
          {pingMeta(k.pingMs).text}
        </span>
      </td>
      <td className="px-4 py-3.5">
        <span className="text-[13px] font-mono text-ink-3">{k.lastUsed ? rel(k.lastUsed, now) : "—"}</span>
      </td>
      <td className="px-4 py-3.5">
        <div className="flex items-center gap-1 opacity-50 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => onCheck(k.id)} disabled={checkingIds.has(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-ink/5 disabled:opacity-50" title="Test key">
            {checkingIds.has(k.id) ? <Loader2 size={13} color="var(--ink-3)" className="animate-spin" /> : <Stethoscope size={13} color="var(--ink-3)" />}
          </button>
          <button onClick={() => onEdit(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-ink/5" title="Edit">
            <Edit2 size={13} color="var(--ink-3)" />
          </button>
          <button onClick={() => onToggle(k.id)} className="p-1.5 rounded-md transition-colors hover:bg-ink/5" title={k.status === "disabled" ? "Enable" : "Disable"}>
            <Power size={13} color={k.status === "disabled" ? "var(--ink)" : "var(--ink-3)"} />
          </button>
        </div>
      </td>
    </tr>
  );
}