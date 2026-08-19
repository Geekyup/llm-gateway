import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  type ActivityRange,
  type ActivitySummary,
  type DailyOutcomeBucket,
  type LatencyPercentileBucket,
  type TokensByProviderBucket,
  type TopModelEntry,
} from "../../lib/api";
import { usePolling } from "../../lib/usePolling";
import { RangeSwitch } from "../shared/RangeSwitch";
import { ActivitySummaryCards } from "./ActivitySummaryCards";
import {
  RequestsByOutcomeChart,
  LatencyPercentilesChart,
  TokensByProviderChart,
  TopModelsChart,
} from "./ActivityCharts";
import { ActivityLogTable } from "./ActivityLogTable";

const RANGE_OPTIONS: { value: ActivityRange; label: string }[] = [
  { value: "24h", label: "24h" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
];

const POLL_INTERVAL_MS = 20000;

export function ActivityPage() {
  const [range, setRange] = useState<ActivityRange>("7d");

  const [summary, setSummary] = useState<ActivitySummary | null>(null);
  const [dailyBuckets, setDailyBuckets] = useState<DailyOutcomeBucket[]>([]);
  const [latencyBuckets, setLatencyBuckets] = useState<LatencyPercentileBucket[]>([]);
  const [tokenBuckets, setTokenBuckets] = useState<TokensByProviderBucket[]>([]);
  const [topModels, setTopModels] = useState<TopModelEntry[]>([]);
  const [loadingCharts, setLoadingCharts] = useState(true);
  const [logRefreshTick, setLogRefreshTick] = useState(0);

  const rangeRef = useRef(range);
  rangeRef.current = range;

  const loadCharts = useCallback(async (opts: { showLoading: boolean }) => {
    if (opts.showLoading) setLoadingCharts(true);
    const r = rangeRef.current;

    const [s, d, l, t, m] = await Promise.allSettled([
      api.activitySummary(r),
      api.activityDailyTimeseries(r),
      api.activityLatencyPercentiles(r),
      api.activityTokensByProvider(r),
      api.activityTopModels(r, 8),
    ]);

    if (rangeRef.current !== r) return;
    if (s.status === "fulfilled") setSummary(s.value);
    if (d.status === "fulfilled") setDailyBuckets(d.value.buckets);
    if (l.status === "fulfilled") setLatencyBuckets(l.value.buckets);
    if (t.status === "fulfilled") setTokenBuckets(t.value.buckets);
    if (m.status === "fulfilled") setTopModels(m.value.models);
    if (opts.showLoading) setLoadingCharts(false);
  }, []);

  useEffect(() => {
    loadCharts({ showLoading: true });
  }, [range, loadCharts]);

  usePolling(() => {
    loadCharts({ showLoading: false });
    setLogRefreshTick((n) => n + 1);
  }, POLL_INTERVAL_MS);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-zinc-300">Activity</h2>
        <RangeSwitch value={range} onChange={setRange} options={RANGE_OPTIONS} label="Activity time range" />
      </div>

      <ActivitySummaryCards summary={summary} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <RequestsByOutcomeChart buckets={dailyBuckets} loading={loadingCharts} />
        <LatencyPercentilesChart buckets={latencyBuckets} loading={loadingCharts} />
        <TokensByProviderChart buckets={tokenBuckets} loading={loadingCharts} />
        <TopModelsChart models={topModels} loading={loadingCharts} />
      </div>

      <ActivityLogTable range={range} refreshSignal={logRefreshTick} />
    </div>
  );
}

