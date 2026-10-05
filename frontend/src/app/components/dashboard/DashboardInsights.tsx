import { useCallback, useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { api, type ActivityLogEntry, type DailyOutcomeBucket } from "../../lib/api";
import { outcomeMeta, providerMeta, rel } from "../../lib/domain";
import { usePolling } from "../../lib/usePolling";
import { RequestsByOutcomeChart } from "../activity/ActivityCharts";
import { LoadingChart } from "../shared/chartHelpers";

const POLL_INTERVAL_MS = 20000;
const LOG_FETCH_SIZE = 100;
const MAX_ISSUES = 6;

export function DashboardInsights({ now, onOpenActivity }: { now: number; onOpenActivity: () => void }) {
  const [buckets, setBuckets] = useState<DailyOutcomeBucket[]>([]);
  const [issues, setIssues] = useState<ActivityLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const [daily, log] = await Promise.allSettled([
      api.activityDailyTimeseries("7d"),
      api.activityLog({ range: "24h", pageSize: LOG_FETCH_SIZE }),
    ]);
    if (daily.status === "fulfilled") setBuckets(daily.value.buckets);
    if (log.status === "fulfilled") {
      setIssues(log.value.entries.filter((e) => e.outcome !== "success").slice(0, MAX_ISSUES));
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  usePolling(load, POLL_INTERVAL_MS);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-[1.6fr_1fr_1fr] gap-3">
      <RequestsByOutcomeChart buckets={buckets} loading={loading} title="Requests, last 7 days" heightClass="h-[180px]" />

      <div
        className="sm:col-span-2 rounded-[10px] p-3.5 flex flex-col"
        style={{ background: "var(--card)", border: "1px solid color-mix(in srgb, var(--ink) 6%, transparent)" }}
      >
        <div className="flex items-baseline justify-between mb-2.5">
          <span className="text-[12px] text-ink-3">Recent issues · last 24h</span>
          <button onClick={onOpenActivity} className="text-[12px] text-ink-3 transition-colors hover:text-ink">
            View activity
          </button>
        </div>

        <div className="flex-1 min-h-[180px]">
          {loading ? (
            <LoadingChart />
          ) : issues.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-2">
              <CheckCircle2 size={20} className="text-ink-4" strokeWidth={1.5} />
              <span className="text-[12px] text-ink-3">No failed or rate-limited requests</span>
            </div>
          ) : (
            <ul className="divide-y divide-ink/[0.04]">
              {issues.map((e) => {
                const om = outcomeMeta(e.outcome);
                const pm = providerMeta(e.provider);
                return (
                  <li key={e.id} className="flex items-center justify-between gap-3 py-2">
                    <div className="min-w-0 flex items-center gap-2.5">
                      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: om.color }} />
                      <div className="min-w-0">
                        <div className="text-[13px] text-ink truncate">
                          <span style={{ color: pm.color }}>{pm.name}</span>
                          <span className="text-ink-3"> · {e.key_label ?? "no key"}</span>
                        </div>
                        {e.model && <div className="text-[12px] font-mono text-ink-3 truncate">{e.model}</div>}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-[12px]" style={{ color: om.color }}>
                        {om.text}
                        {e.upstream_status ? <span className="font-mono"> {e.upstream_status}</span> : null}
                      </div>
                      <div className="text-[12px] font-mono text-ink-3">{rel(new Date(e.timestamp).getTime(), now)}</div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
