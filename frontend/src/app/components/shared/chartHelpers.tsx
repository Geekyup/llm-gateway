import { BarChart3, Loader2 } from "lucide-react";

export const CHART_MUTED = "#52525B";
export const CHART_GRID = "rgba(255,255,255,0.04)";
export const CHART_ACCENT = "#00D68F";
export const CHART_Y_AXIS_WIDTH = 30;

export function tooltipStyle() {
  return {
    background: "#141416",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 6,
    padding: "8px 10px",
    fontSize: 11,
    fontFamily: "inherit",
  } as const;
}

export function EmptyChart({ message }: { message: string }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-2">
      <BarChart3 size={20} className="text-zinc-700" strokeWidth={1.5} />
      <span className="text-[11px] text-zinc-600">{message}</span>
    </div>
  );
}

export function LoadingChart() {
  return (
    <div className="h-full flex items-center justify-center">
      <Loader2 size={16} className="animate-spin text-zinc-700" />
    </div>
  );
}
