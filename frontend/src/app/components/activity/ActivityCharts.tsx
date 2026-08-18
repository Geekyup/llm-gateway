import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { providerMeta } from "../../lib/domain";
import type {
  DailyOutcomeBucket,
  LatencyPercentileBucket,
  TokensByProviderBucket,
  TopModelEntry,
} from "../../lib/api";
import { ChartCard } from "../shared/ChartCard";
import {
  CHART_MUTED as MUTED,
  CHART_GRID as GRID,
  CHART_Y_AXIS_WIDTH as Y_AXIS_WIDTH,
  tooltipStyle,
  EmptyChart,
  LoadingChart,
} from "../shared/chartHelpers";

const SUCCESS_COLOR = "#00D68F";
const RATE_LIMITED_COLOR = "#F59E0B";
const ERROR_COLOR = "#EF4444";
const P50_COLOR = "#4F8EF7";
const P95_COLOR = "#F59E0B";
const P99_COLOR = "#EF4444";

function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", timeZone: "UTC" }).format(d);
}

export function RequestsByOutcomeChart({ buckets, loading }: { buckets: DailyOutcomeBucket[]; loading: boolean }) {
  const data = buckets.map((b) => ({ ...b, label: shortDate(b.date) }));
  const total = buckets.reduce((a, b) => a + b.success + b.rate_limited + b.error, 0);
  const hasData = total > 0;

  return (
    <ChartCard title="Requests by day" value={total.toLocaleString()} unit="total">
      {loading ? (
        <LoadingChart />
      ) : hasData ? (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="label" tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} width={Y_AXIS_WIDTH} allowDecimals={false} />
            <Tooltip
              contentStyle={tooltipStyle()}
              labelStyle={{ color: MUTED, marginBottom: 2 }}
              itemStyle={{ color: "#ECECF0" }}
              cursor={{ fill: "rgba(255,255,255,0.03)" }}
            />
            <Bar dataKey="success" stackId="o" fill={SUCCESS_COLOR} name="Success" maxBarSize={28} />
            <Bar dataKey="rate_limited" stackId="o" fill={RATE_LIMITED_COLOR} name="Rate limited" maxBarSize={28} />
            <Bar dataKey="error" stackId="o" fill={ERROR_COLOR} name="Error" radius={[2, 2, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <EmptyChart message="No requests in this period" />
      )}
    </ChartCard>
  );
}

export function LatencyPercentilesChart({ buckets, loading }: { buckets: LatencyPercentileBucket[]; loading: boolean }) {
  const data = buckets.map((b) => ({ ...b, label: shortDate(b.date) }));
  const hasData = buckets.some((b) => b.p50 != null || b.p95 != null || b.p99 != null);
  const latest = [...buckets].reverse().find((b) => b.p50 != null);

  return (
    <ChartCard title="Latency p50 / p95 / p99" value={latest?.p50 != null ? Math.round(latest.p50) : "—"} unit="ms">
      {loading ? (
        <LoadingChart />
      ) : hasData ? (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="label" tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} width={Y_AXIS_WIDTH} allowDecimals={false} />
            <Tooltip
              contentStyle={tooltipStyle()}
              labelStyle={{ color: MUTED, marginBottom: 2 }}
              itemStyle={{ color: "#ECECF0" }}
              formatter={(v: number) => [`${Math.round(v)} ms`, ""]}
              cursor={{ stroke: "rgba(255,255,255,0.1)" }}
            />
            <Line type="monotone" dataKey="p50" stroke={P50_COLOR} strokeWidth={1.5} dot={false} name="p50" connectNulls />
            <Line type="monotone" dataKey="p95" stroke={P95_COLOR} strokeWidth={1.5} dot={false} name="p95" connectNulls />
            <Line type="monotone" dataKey="p99" stroke={P99_COLOR} strokeWidth={1.5} dot={false} name="p99" connectNulls />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <EmptyChart message="No latency data yet" />
      )}
    </ChartCard>
  );
}

const PROVIDER_COLORS = ["#4F8EF7", "#00D68F", "#A78BFA", "#F97316", "#71717A"];

export function TokensByProviderChart({ buckets, loading }: { buckets: TokensByProviderBucket[]; loading: boolean }) {
  const providers = Array.from(new Set(buckets.flatMap((b) => Object.keys(b.providers))));
  const data = buckets.map((b) => {
    const row: Record<string, number | string> = { label: shortDate(b.date) };
    for (const p of providers) row[p] = b.providers[p] ?? 0;
    return row;
  });
  const total = buckets.reduce((a, b) => a + Object.values(b.providers).reduce((x, y) => x + y, 0), 0);
  const hasData = total > 0;

  return (
    <ChartCard title="Tokens by provider" value={formatCompact(total)} unit="tokens">
      {loading ? (
        <LoadingChart />
      ) : hasData ? (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="label" tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
            <YAxis tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} width={Y_AXIS_WIDTH} allowDecimals={false} />
            <Tooltip
              contentStyle={tooltipStyle()}
              labelStyle={{ color: MUTED, marginBottom: 2 }}
              itemStyle={{ color: "#ECECF0" }}
              cursor={{ fill: "rgba(255,255,255,0.03)" }}
            />
            {providers.map((p, i) => (
              <Bar
                key={p}
                dataKey={p}
                stackId="tokens"
                fill={PROVIDER_COLORS[i % PROVIDER_COLORS.length]}
                name={providerMeta(p).name}
                radius={i === providers.length - 1 ? [2, 2, 0, 0] : undefined}
                maxBarSize={28}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <EmptyChart message="No token usage in this period" />
      )}
    </ChartCard>
  );
}

export function TopModelsChart({ models, loading }: { models: TopModelEntry[]; loading: boolean }) {
  const data = models.map((m) => ({ ...m, label: m.model }));
  const hasData = models.length > 0;

  return (
    <ChartCard title="Top models" value={models.length} unit="models">
      {loading ? (
        <LoadingChart />
      ) : hasData ? (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 12, left: 4, bottom: 0 }}>
            <CartesianGrid stroke={GRID} horizontal={false} />
            <XAxis type="number" tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} allowDecimals={false} />
            <YAxis
              type="category"
              dataKey="label"
              tick={{ fill: MUTED, fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              width={110}
            />
            <Tooltip
              contentStyle={tooltipStyle()}
              labelStyle={{ color: MUTED, marginBottom: 2 }}
              itemStyle={{ color: "#ECECF0" }}
              formatter={(v: number) => [`${v} req`, ""]}
              cursor={{ fill: "rgba(255,255,255,0.03)" }}
            />
            <Bar dataKey="requests" fill="#4F8EF7" radius={[0, 2, 2, 0]} maxBarSize={16} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <EmptyChart message="No model usage in this period" />
      )}
    </ChartCard>
  );
}

function formatCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
