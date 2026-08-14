import { useMemo } from "react";
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

const MUTED = "#52525B";
const GRID = "rgba(255,255,255,0.04)";
const ACCENT = "#00D68F";
const MSK_TZ = "Europe/Moscow";

const BUCKET_COUNT = 15;
const BUCKET_MS = 120_000; 

function fmtMsk(ts: number): string {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: MSK_TZ,
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
      label: fmtMsk(bucketStart),
      fullTime: isNow ? `${fmtMsk(bucketStart)} MSK - now` : `${fmtMsk(bucketStart)} MSK`,
      ts: bucketStart,
      count: inBucket.length,
      p50,
      providers,
    });
  }

  return buckets;
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
    <div className="h-full flex items-center justify-center">
      <span className="text-[11px] text-zinc-600">{message}</span>
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
      <div className="h-[100px]">{children}</div>
    </div>
  );
}

export function MonitorCharts({ reqs, now }: { reqs: LR[]; now: number }) {
  const buckets = useMemo(() => bucketRequests(reqs, now), [reqs, now]);

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
  const grays = ["#3F3F46", "#27272A", "#52525B"];
  let grayIdx = 0;
  const providerColor = (p: string) => (p === busiest ? ACCENT : grays[grayIdx++ % grays.length]);

  return (
    <div className="grid gap-3 mb-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <ChartCard title="Requests / min" value={currentReq} unit="now">
          {hasData ? (
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
                <YAxis tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} width={24} allowDecimals={false} />
                <Tooltip
                  contentStyle={tooltipStyle()}
                  labelStyle={{ color: MUTED, marginBottom: 2 }}
                  itemStyle={{ color: "#ECECF0" }}
                  formatter={(v: number) => [`${v} req/min`, ""]}
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
            <EmptyChart message="No requests in the last 30 min" />
          )}
        </ChartCard>

        <ChartCard title="Latency p50" value={currentP50 || "--"} unit="ms">
          {hasData ? (
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
                <YAxis tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} width={28} allowDecimals={false} />
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

      <div
        className="rounded-[10px] p-3.5"
        style={{ background: "#111113", border: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center justify-between mb-2.5">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Requests by provider</span>
          <div className="flex items-center gap-3.5">
            {providersPresent.map((p) => {
              const meta = providerMeta(p);
              return (
                <span key={p} className="flex items-center gap-1.5 text-[11px] text-zinc-400">
                  <span
                    className="w-1.5 h-1.5 rounded-[2px]"
                    style={{ background: providerColor(p) }}
                  />
                  {meta.name}
                </span>
              );
            })}
          </div>
        </div>
        <div className="h-[90px]">
          {hasData ? (
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
                <YAxis tick={{ fill: MUTED, fontSize: 9 }} axisLine={false} tickLine={false} width={24} allowDecimals={false} />
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
            <EmptyChart message="No requests in the last 30 min" />
          )}
        </div>
      </div>
    </div>
  );
}