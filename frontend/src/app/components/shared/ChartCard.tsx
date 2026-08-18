import type { ReactNode } from "react";

export function ChartCard({
  title,
  value,
  unit,
  children,
  footer,
}: {
  title: string;
  value: string | number;
  unit?: string;
  children: ReactNode;
  footer?: ReactNode;
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
      {footer && <div className="flex justify-end mt-2.5">{footer}</div>}
    </div>
  );
}
