import { useEffect, useMemo, useState } from "react";
import { BarChart3, Loader2 } from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import type { LR } from "../../types";
import { providerMeta } from "../../lib/domain";
import { api, type MonitorRange, type TimeseriesBucket } from "../../lib/api";

const MUTED = "#52525B";
const GRID = "rgba(255,255,255,0.04)";
const ACCENT = "#00D68F";
const MSK_TZ = "Europe/Moscow";

const Y_AXIS_WIDTH = 30;

const BUCKET_COUNT = 15;
const BUCKET_MS = 120_000;

const RANGE_OPTIONS: { value: MonitorRange; label: string }[] = [
  { value: "30m", label: "30m" },
  { value: "6h", label: "6h" },
  { value: "24h", label: "24h" },
];


const REMOTE_REFRESH_MS = 60_000;

function fmtMsk(ts: number, includeDate: boolean): string {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: MSK_TZ,
    ...(includeDate ? { day: "2-digit", month: "2-digit" } : {}),
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(ts);
}

interface Bucket {
  label: string;
  fullTime: string;
  ts: number;
  count: number;
  p50: number;
  providers: Record<string, number>;
}

function bucketRequests(reqs: LR[], now: number): Bucket[] {
  const buckets: Bucket[] = [];
  const start = now - BUCKET_COUNT * BUCKET_MS;

  for (let i = 0; i < BUCKET_COUNT; i++) {
    const bucketStart = start + i * BUCKET_MS;
    const bucketEnd = bucketStart + BUCKET_MS;
    const inBucket = reqs.filter((r) => r.ts >= bucketStart && r.ts < bucketEnd);

    const latencies = inBucket.map((r) => r.latency).sort((a, b) => a - b);
    const p50 = latencies.length
      ? latencies[Math.floor(latencies.length / 2)]
      : 0;

    const providers: Record<string, number> = {};
    for (const r of inBucket) {
      providers[r.provider] = (providers[r.provider] ?? 0) + 1;
    }

    const isNow = i === BUCKET_COUNT - 1;
    buckets.push({
      label: fmtMsk(bucketStart, false),
      fullTime: isNow ? `${fmtMsk(bucketStart, false)} MSK - now` : `${fmtMsk(bucketStart, false)} MSK`,
      ts: bucketStart,
      count: inBucket.length,
      p50,
      providers,
    });
  }

  return buckets;
}

function fromRemoteBuckets(remote: TimeseriesBucket[], range: MonitorRange): Bucket[] {
  const includeDate = range === "24h";
  const last = remote.length - 1;
  return remote.map((b, i) => ({
    label: fmtMsk(b.ts, includeDate),
    fullTime: i === last ? `${fmtMsk(b.ts, includeDate)} MSK - now` : `${fmtMsk(b.ts, includeDate)} MSK`,
    ts: b.ts,
    count: b.count,
    p50: b.p50 ?? 0,
    providers: b.providers,
  }));
}

function tooltipStyle() {
  return {
    background: "#141416",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 6,
    padding: "8px 10px",
    fontSize: 11,
    fontFamily: "inherit",
  } as const;
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-2">
      <BarChart3 size={20} className="text-zinc-700" strokeWidth={1.5} />
      <span className="text-[11px] text-zinc-600">{message}</span>
    </div>
  );
}

function LoadingChart() {
  return (
    <div className="h-full flex items-center justify-center">
      <Loader2 size={16} className="animate-spin text-zinc-700" />
    </div>
  );
}

function ChartCard({
  title,
  value,
  unit,
  children,
}: {
  title: string;
  value: string | number;
  unit?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-[10px] p-3.5"
      style={{ background: "#111113", border: "1px solid rgba(255,255,255,0.06)" }}
    >
      <div className="flex items-baseline justify-between mb-2.5">
        <span className="text-[10px] text-zinc-500 uppercase tracking-wider">{title}</span>
        <span className="text-[15px] font-medium text-zinc-100">
          {value}
          {unit && <span className="text-[10px] text-zinc-600 font-normal"> {unit}</span>}
        </span>
      </div>
      <div className="h-[220px] sm:h-[240px]">{children}</div>
    </div>
  );
}

function RangeSwitch({ value, onChange }: { value: MonitorRange; onChange: (r: MonitorRange) => void }) {
  return (
    <div
      className="inline-flex items-center rounded-lg p-0.5 self-start"
      style={{ background: "#111113", border: "1px solid rgba(255,255,255,0.06)" }}
      role="group"
      aria-label="Chart time range"
    >
      {RANGE_OPTIONS.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            aria-pressed={active}
            className="px-3 py-1 rounded-md text-[11px] font-medium font-mono transition-colors"
            style={
              active
                ? { background: "rgba(0,214,143,0.12)", color: ACCENT }
                : { background: "transparent", color: "#71717A" }
            }
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export function MonitorCharts({ reqs, now }: { reqs: LR[]; now: number }) {
  const [range, setRange] = useState<MonitorRange>("30m");
  const [remoteBuckets, setRemoteBuckets] = useState<TimeseriesBucket[] | null>(null);
  const [remoteLoading, setRemoteLoading] = useState(false);

  useEffect(() => {
    if (range === "30m") {
      setRemoteBuckets(null);
      return;
    }
    let cancelled = false;

    async function load() {
      setRemoteLoading(true);
      try {
        const res = await api.timeseries(range);
        if (!cancelled) setRemoteBuckets(res.buckets);
      } catch {
        // keep showing the last successful fetch rather than clearing the chart
      } finally {
        if (!cancelled) setRemoteLoading(false);
      }
    }

    load();
    const id = setInterval(load, REMOTE_REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [range]);

  const liveBuckets = useMemo(() => bucketRequests(reqs, now), [reqs, now]);
  const buckets = useMemo(
    () => (range === "30m" ? liveBuckets : remoteBuckets ? fromRemoteBuckets(remoteBuckets, range) : []),
    [range, liveBuckets, remoteBuckets]
  );
  const isLoadingRemote = range !== "30m" && remoteBuckets === null && remoteLoading;

  const providersPresent = useMemo(() => {
    const set = new Set<string>();
    for (const b of buckets) for (const p of Object.keys(b.providers)) set.add(p);
    return set.size ? Array.from(set) : ["gemini", "groq", "openrouter"];
  }, [buckets]);

  const providerChartData = useMemo(
    () =>
      buckets.map((b) => {
        const row: Record<string, number | string> = { label: b.label, fullTime: b.fullTime };
        for (const p of providersPresent) row[p] = b.providers[p] ?? 0;
        return row;
      }),
    [buckets, providersPresent]
  );

  const current = buckets[buckets.length - 1];
  const currentReq = current?.count ?? 0;
  const currentP50 = current?.p50 || buckets.slice().reverse().find((b) => b.p50 > 0)?.p50 || 0;
  const totalReqInWindow = buckets.reduce((acc, b) => acc + b.count, 0);
  const hasData = totalReqInWindow > 0;

  const busiest = providersPresent
    .slice()
    .sort((a, b) => {
      const sum = (p: string) => buckets.reduce((acc, bkt) => acc + (bkt.providers[p] ?? 0), 0);
      return sum(b) - sum(a);
    })[0];
  const grays = ["#71717A", "#3F3F46", "#A1A1AA", "#27272A"];
  let grayIdx = 0;
  const providerColor = (p: string) => (p === busiest ? ACCENT : grays[grayIdx++ % grays.length]);

  const emptyMessage =
    range === "30m"
      ? "No requests in the last 30 min"
      : range === "6h"
      ? "No requests in the last 6 hours"
      : "No requests in the last 24 hours";

  const reqUnit = range === "30m" ? "now" : "last bucket";

  return (
    <div className="grid gap-3 mb-3">
      <RangeSwitch value={range} onChange={setRange} />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <ChartCard title="Requests / min" value={currentReq} unit={reqUnit}>
          {isLoadingRemote ? (
            <LoadingChart />
          ) : hasData ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={buckets} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: MUTED, fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} width={Y_AXIS_WIDTH} allowDecimals={false} />
                <Tooltip
                  contentStyle={tooltipStyle()}
                  labelStyle={{ color: MUTED, marginBottom: 2 }}
                  itemStyle={{ color: "#ECECF0" }}
                  formatter={(v: number) => [`${v} req`, ""]}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.fullTime ?? ""}
                  cursor={{ stroke: "rgba(255,255,255,0.1)" }}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke={ACCENT}
                  strokeWidth={1.5}
                  fill={ACCENT}
                  fillOpacity={0.08}
                  dot={false}
                  activeDot={{ r: 4, fill: ACCENT, stroke: "#0A0A0B", strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart message={emptyMessage} />
          )}
        </ChartCard>

        <ChartCard title="Latency p50" value={currentP50 || "--"} unit="ms">
          {isLoadingRemote ? (
            <LoadingChart />
          ) : hasData ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={buckets} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: MUTED, fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} width={Y_AXIS_WIDTH} allowDecimals={false} />
                <Tooltip
                  contentStyle={tooltipStyle()}
                  labelStyle={{ color: MUTED, marginBottom: 2 }}
                  itemStyle={{ color: "#ECECF0" }}
                  formatter={(v: number) => [`${v} ms`, ""]}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.fullTime ?? ""}
                  cursor={{ stroke: "rgba(255,255,255,0.1)" }}
                />
                <Area
                  type="monotone"
                  dataKey="p50"
                  stroke={ACCENT}
                  strokeWidth={1.5}
                  fill={ACCENT}
                  fillOpacity={0.08}
                  dot={false}
                  activeDot={{ r: 4, fill: ACCENT, stroke: "#0A0A0B", strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart message="No latency data yet" />
          )}
        </ChartCard>
      </div>

      <ChartCard title="Requests by provider" value={totalReqInWindow} unit="total">
        <div className="flex items-center justify-end gap-3.5 mb-1.5 -mt-1">
          {providersPresent.map((p) => {
            const meta = providerMeta(p);
            return (
              <span key={p} className="flex items-center gap-1.5 text-[11px] text-zinc-400">
                <span className="w-1.5 h-1.5 rounded-[2px]" style={{ background: providerColor(p) }} />
                {meta.name}
              </span>
            );
          })}
        </div>
        {isLoadingRemote ? (
          <LoadingChart />
        ) : hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={providerChartData} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: MUTED, fontSize: 9 }}
                axisLine={false}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} width={Y_AXIS_WIDTH} allowDecimals={false} />
              <Tooltip
                contentStyle={tooltipStyle()}
                labelStyle={{ color: MUTED, marginBottom: 2 }}
                itemStyle={{ color: "#ECECF0" }}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.fullTime ?? ""}
                cursor={{ fill: "rgba(255,255,255,0.03)" }}
              />
              {providersPresent.map((p) => (
                <Bar
                  key={p}
                  dataKey={p}
                  stackId="providers"
                  fill={providerColor(p)}
                  name={providerMeta(p).name}
                  radius={p === providersPresent[providersPresent.length - 1] ? [2, 2, 0, 0] : undefined}
                  maxBarSize={22}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <EmptyChart message={emptyMessage} />
        )}
      </ChartCard>
    </div>
  );
}