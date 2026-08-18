import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import type { ActivitySummary } from "../../lib/api";

function Delta({ curr, prev, invert = false }: { curr: number; prev: number; invert?: boolean }) {
  if (prev === 0 && curr === 0) {
    return (
      <span className="flex items-center gap-1 text-[11px] text-zinc-600">
        <Minus size={10} /> flat
      </span>
    );
  }
  if (prev === 0) {
    return (
      <span className="flex items-center gap-1 text-[11px]" style={{ color: "#00D68F" }}>
        <ArrowUp size={10} /> new
      </span>
    );
  }
  const pct = ((curr - prev) / prev) * 100;
  const rounded = Math.round(pct);
  if (rounded === 0) {
    return (
      <span className="flex items-center gap-1 text-[11px] text-zinc-600">
        <Minus size={10} /> flat
      </span>
    );
  }
  const good = invert ? rounded < 0 : rounded > 0;
  const color = good ? "#00D68F" : "#EF4444";
  const Icon = rounded > 0 ? ArrowUp : ArrowDown;
  return (
    <span className="flex items-center gap-1 text-[11px]" style={{ color }}>
      <Icon size={10} /> {Math.abs(rounded)}% vs prev
    </span>
  );
}

function estimateCostUsd(totalTokens: number): number {
  // Rough blended estimate across providers, ~$1.70 per 1M tokens — for a directional sense only.
  return (totalTokens / 1_000_000) * 1.7;
}

export function ActivitySummaryCards({ summary }: { summary: ActivitySummary | null }) {
  const cards = [
    {
      label: "Total requests",
      value: summary ? summary.total_requests.toLocaleString() : "—",
      delta: summary ? <Delta curr={summary.total_requests} prev={summary.prev_total_requests} /> : null,
    },
    {
      label: "Success rate",
      value: summary ? `${summary.success_rate.toFixed(1)}%` : "—",
      delta: summary ? <Delta curr={summary.success_rate} prev={summary.prev_success_rate} /> : null,
    },
    {
      label: "Latency p50 / p95",
      value: summary
        ? `${summary.latency_p50 != null ? Math.round(summary.latency_p50) : "—"} / ${
            summary.latency_p95 != null ? `${(summary.latency_p95 / 1000).toFixed(1)}s` : "—"
          }`
        : "—",
      delta: summary && summary.latency_p95 != null ? (
        <Delta curr={summary.latency_p95} prev={summary.prev_latency_p95 ?? 0} invert />
      ) : null,
    },
    {
      label: "Tokens used",
      value: summary ? formatCompact(summary.total_tokens) : "—",
      delta: summary ? (
        <span className="text-[11px] text-zinc-600">~${estimateCostUsd(summary.total_tokens).toFixed(2)} est.</span>
      ) : null,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((c) => (
        <div
          key={c.label}
          className="rounded-xl p-4"
          style={{ background: "#111113", border: "1px solid rgba(255,255,255,0.06)" }}
        >
          <div className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium mb-2">{c.label}</div>
          <div className="text-2xl font-mono font-medium text-zinc-100 mb-1.5">{c.value}</div>
          {c.delta}
        </div>
      ))}
    </div>
  );
}

function formatCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
