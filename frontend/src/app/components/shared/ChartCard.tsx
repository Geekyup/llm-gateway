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
      style={{ background: "var(--card)", border: "1px solid color-mix(in srgb, var(--ink) 10%, transparent)" }}
    >
      <div className="flex items-baseline justify-between mb-2.5">
        <span className="text-[12px] text-ink-3">{title}</span>
        <span className="text-[15px] font-medium text-ink">
          {value}
          {unit && <span className="text-[12px] text-ink-3 font-normal"> {unit}</span>}
        </span>
      </div>
      <div className="h-[220px] sm:h-[240px]">{children}</div>
      {footer && <div className="flex justify-end mt-2.5">{footer}</div>}
    </div>
  );
}
