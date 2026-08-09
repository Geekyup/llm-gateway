export function UsageCircle({ used, limit, color }: { used: number; limit: number; color: string }) {
  const r = 48;
  const circ = 2 * Math.PI * r;
  const pct = limit > 0 ? Math.min(1, Math.max(0, used / limit)) : 0;
  const dash = pct * circ;
  return (
    <div className="relative inline-flex items-center justify-center shrink-0">
      <svg width={120} height={120} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={60} cy={60} r={r} fill="none" strokeWidth={7} stroke="rgba(255,255,255,0.05)" />
        <circle
          cx={60}
          cy={60}
          r={r}
          fill="none"
          strokeWidth={7}
          stroke={color}
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 6px ${color}70)`, transition: "stroke-dasharray 0.5s ease" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-xl font-mono font-medium" style={{ color }}>
          {Math.round(pct * 100)}%
        </span>
        <span className="text-[10px] text-zinc-600 font-mono">used</span>
      </div>
    </div>
  );
}
