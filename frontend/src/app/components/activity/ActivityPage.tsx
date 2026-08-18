import { useEffect, useState } from "react";
import {
  api,
  type ActivityRange,
  type ActivitySummary,
  type DailyOutcomeBucket,
  type LatencyPercentileBucket,
  type TokensByProviderBucket,
  type TopModelEntry,
} from "../../lib/api";
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

export function ActivityPage() {
  const [range, setRange] = useState<ActivityRange>("7d");

  const [summary, setSummary] = useState<ActivitySummary | null>(null);
  const [dailyBuckets, setDailyBuckets] = useState<DailyOutcomeBucket[]>([]);
  const [latencyBuckets, setLatencyBuckets] = useState<LatencyPercentileBucket[]>([]);
  const [tokenBuckets, setTokenBuckets] = useState<TokensByProviderBucket[]>([]);
  const [topModels, setTopModels] = useState<TopModelEntry[]>([]);
  const [loadingCharts, setLoadingCharts] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoadingCharts(true);

    Promise.allSettled([
      api.activitySummary(range),
      api.activityDailyTimeseries(range),
      api.activityLatencyPercentiles(range),
      api.activityTokensByProvider(range),
      api.activityTopModels(range, 8),
    ]).then(([s, d, l, t, m]) => {
      if (cancelled) return;
      if (s.status === "fulfilled") setSummary(s.value);
      if (d.status === "fulfilled") setDailyBuckets(d.value.buckets);
      if (l.status === "fulfilled") setLatencyBuckets(l.value.buckets);
      if (t.status === "fulfilled") setTokenBuckets(t.value.buckets);
      if (m.status === "fulfilled") setTopModels(m.value.models);
      setLoadingCharts(false);
    });

    return () => {
      cancelled = true;
    };
  }, [range]);

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

      <ActivityLogTable range={range} />
    </div>
  );
}
