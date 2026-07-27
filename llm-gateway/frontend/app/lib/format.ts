// ─── Display formatting helpers ─────────────────────────────────────────────
const HOURLY_W = [0,0,0,0,0,0.3,0.8,1.5,2,2.5,2.8,2.6,2.2,2,1.8,1.5,1.2,0.9,0.6,0.3,0.1,0,0,0];

export function makeHourly(total: number) {
  const sum = HOURLY_W.reduce((a, b) => a + b, 0);
  return HOURLY_W.map((w, i) => ({ h: `${i}h`, r: Math.round((w / sum) * total) }));
}

export function rel(ts: number, now: number) {
  const d = now - ts;
  if (d < 60000)   return `${Math.floor(d / 1000)}s ago`;
  if (d < 3600000) return `${Math.floor(d / 60000)}m ago`;
  if (d < 86400000)return `${Math.floor(d / 3600000)}h ago`;
  return `${Math.floor(d / 86400000)}d ago`;
}

export function cd(until: number, now: number) {
  const d = until - now;
  if (d <= 0) return "Ready";
  const h = Math.floor(d / 3600000);
  const m = Math.floor((d % 3600000) / 60000);
  const s = Math.floor((d % 60000) / 1000);
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  return `${m}:${String(s).padStart(2, "0")}`;
}
