import { BarChart3, Loader2 } from "lucide-react";

export const CHART_MUTED = "var(--ink-4)";
export const CHART_GRID = "color-mix(in srgb, var(--ink) 7%, transparent)";
export const CHART_ACCENT = "var(--accent)";
export const CHART_Y_AXIS_WIDTH = 30;

export function tooltipStyle() {
  return {
    background: "var(--card)",
    border: "1px solid color-mix(in srgb, var(--ink) 14%, transparent)",
    borderRadius: 6,
    padding: "8px 10px",
    fontSize: 11,
    fontFamily: "inherit",
  } as const;
}

export function EmptyChart({ message }: { message: string }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-2">
      <BarChart3 size={20} className="text-ink-4" strokeWidth={1.5} />
      <span className="text-[12px] text-ink-3">{message}</span>
    </div>
  );
}

export function LoadingChart() {
  return (
    <div className="h-full flex items-center justify-center">
      <Loader2 size={16} className="animate-spin text-ink-4" />
    </div>
  );
}
