import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Download, Loader2, ListX } from "lucide-react";
import { api, ApiError, getAccessToken, type ActivityLogEntry, type ActivityRange } from "../../lib/api";
import { providerMeta, outcomeMeta } from "../../lib/domain";
import { ActivityProviderFilterDropdown } from "./ActivityProviderFilterDropdown";
import { ActivityOutcomeFilterDropdown } from "./ActivityOutcomeFilterDropdown";

const PAGE_SIZE = 20;

function fmtTime(iso: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Europe/Moscow",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}

export function ActivityLogTable({ range, refreshSignal = 0 }: { range: ActivityRange; refreshSignal?: number }) {
  const [entries, setEntries] = useState<ActivityLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<string>("");
  const [outcome, setOutcome] = useState<string>("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setPage(1);
  }, [range, provider, outcome]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .activityLog({ range, page, pageSize: PAGE_SIZE, provider: provider || null, outcome: outcome || null })
      .then((res) => {
        if (cancelled) return;
        setEntries(res.entries);
        setTotal(res.total);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Failed to load activity log");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [range, page, provider, outcome]);


  useEffect(() => {
    if (refreshSignal === 0) return;
    let cancelled = false;
    api
      .activityLog({ range, page, pageSize: PAGE_SIZE, provider: provider || null, outcome: outcome || null })
      .then((res) => {
        if (cancelled) return;
        setEntries(res.entries);
        setTotal(res.total);
        setError(null);
      })
      .catch(() => {
      });
    return () => {
      cancelled = true;
    };
  }, [refreshSignal]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  async function handleExport() {
    setExporting(true);
    try {
      const url = api.activityLogExportCsvUrl({ range, provider: provider || null, outcome: outcome || null });
      const res = await fetch(url, { headers: { Authorization: `Bearer ${getAccessToken()}` } });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = `activity-${range}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
    } catch {
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="rounded-lg overflow-hidden" style={{ border: "1px solid color-mix(in srgb, var(--ink) 6%, transparent)" }}>
      <div
        className="flex flex-wrap items-center justify-between gap-x-2 gap-y-2 px-4 py-2.5"
        style={{ borderBottom: "1px solid color-mix(in srgb, var(--ink) 4.8%, transparent)", background: "var(--sidebar)" }}
      >
        <span className="text-xs font-medium text-ink-2 shrink-0">Request log</span>
        <div className="flex items-center gap-2 flex-wrap">
          <ActivityProviderFilterDropdown value={provider} onChange={setProvider} />
          <ActivityOutcomeFilterDropdown value={outcome} onChange={setOutcome} />
          <button
            onClick={handleExport}
            disabled={exporting || total === 0}
            className="flex items-center gap-1.5 text-[12px] rounded-md px-2.5 py-1 outline-none disabled:opacity-40 transition-colors"
            style={{ color: "var(--ink)", background: "color-mix(in srgb, var(--ink) 6%, transparent)", border: "1px solid color-mix(in srgb, var(--ink) 8.4%, transparent)" }}
          >
            {exporting ? <Loader2 size={11} className="animate-spin" /> : <Download size={11} />}
            Export CSV
          </button>
        </div>
      </div>

      {error && (
        <div className="px-4 py-3 text-xs" style={{ color: "var(--bad)", background: "color-mix(in srgb, var(--bad) 6%, transparent)" }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16" style={{ background: "var(--card)" }}>
          <Loader2 size={18} className="animate-spin text-ink-4" />
        </div>
      ) : entries.length === 0 ? (
        <div className="px-4 py-16 text-center" style={{ background: "var(--card)" }}>
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: "color-mix(in srgb, var(--ink) 3%, transparent)", border: "1px solid color-mix(in srgb, var(--ink) 6%, transparent)" }}>
              <ListX size={18} color="var(--ink-4)" />
            </div>
            <p className="text-sm text-ink-3">No requests found</p>
            <p className="text-xs text-ink-3">Try a different filter or time range</p>
          </div>
        </div>
      ) : (
        <div className="overflow-x-auto" style={{ background: "var(--card)" }}>
          <table className="w-full min-w-[720px]" style={{ tableLayout: "fixed" }}>
            <colgroup>
              <col style={{ width: "16%" }} />
              <col style={{ width: "13%" }} />
              <col style={{ width: "23%" }} />
              <col style={{ width: "15%" }} />
              <col style={{ width: "13%" }} />
              <col style={{ width: "10%" }} />
              <col style={{ width: "10%" }} />
            </colgroup>
            <thead>
              <tr style={{ borderBottom: "1px solid color-mix(in srgb, var(--ink) 4.2%, transparent)" }}>
                {["Time", "Provider", "Model", "Key", "Outcome", "Latency", "Tokens"].map((h, i) => (
                  <th
                    key={h}
                    className={`px-4 py-2.5 text-[12px] font-semibold text-ink-3 ${i >= 5 ? "text-right" : "text-left"}`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-ink/[0.03]">
              {entries.map((e) => {
                const om = outcomeMeta(e.outcome);
                const pm = providerMeta(e.provider);
                return (
                  <tr key={e.id} className="transition-colors hover:bg-ink/[0.02]">
                    <td className="px-4 py-2.5 text-xs font-mono text-ink-3">{fmtTime(e.timestamp)}</td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs" style={{ color: pm.color }}>{pm.name}</span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-ink-2 truncate" title={e.model ?? undefined}>
                      {e.model ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-xs font-mono text-ink-3 truncate">{e.key_label ?? "—"}</td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs" style={{ color: om.color }}>{om.text}</span>
                    </td>
                    <td className="px-4 py-2.5 text-xs font-mono text-ink-3 text-right">
                      {e.latency_ms != null ? `${e.latency_ms}ms` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-xs font-mono text-ink-3 text-right">
                      {e.total_tokens != null ? e.total_tokens.toLocaleString() : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div
        className="flex items-center justify-center gap-3 px-4 py-2.5"
        style={{ borderTop: "1px solid color-mix(in srgb, var(--ink) 4.8%, transparent)", background: "var(--sidebar)" }}
      >
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page <= 1 || loading}
          className="p-1 rounded-md transition-colors hover:bg-ink/5 disabled:opacity-30"
          aria-label="Previous page"
        >
          <ChevronLeft size={14} color="var(--ink-3)" />
        </button>
        <span className="text-[12px] font-mono text-ink-3">
          Page {page} of {totalPages}
        </span>
        <button
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page >= totalPages || loading}
          className="p-1 rounded-md transition-colors hover:bg-ink/5 disabled:opacity-30"
          aria-label="Next page"
        >
          <ChevronRight size={14} color="var(--ink-3)" />
        </button>
      </div>
    </div>
  );
}
