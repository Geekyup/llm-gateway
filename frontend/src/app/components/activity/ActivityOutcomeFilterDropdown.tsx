import { useEffect, useRef, useState } from "react";
import { ChevronDown, CheckCircle2, ListFilter } from "lucide-react";
import { OUTCOME_META, outcomeMeta, alpha } from "../../lib/domain";
import { DropdownPortal } from "../shared/DropdownPortal";

const OUTCOME_OPTIONS: { value: string; label: string }[] = [
  { value: "success", label: "Success" },
  { value: "rate_limited", label: "Rate limited" },
  { value: "exhausted", label: "Exhausted" },
  { value: "error", label: "Error" },
];

export function ActivityOutcomeFilterDropdown({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t)) return;
      if (menuRef.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  const active = value !== "";
  const meta = active ? outcomeMeta(value) : null;
  const fullLabel = active ? OUTCOME_OPTIONS.find((o) => o.value === value)?.label ?? meta!.text : "All outcomes";
  const dotColor = active ? meta!.color : "var(--ink-3)";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[12px] rounded-md px-2 py-1 outline-none transition-colors hover:brightness-125"
        style={{
          color: "var(--ink)",
          background: active ? meta!.bg : "color-mix(in srgb, var(--ink) 6%, transparent)",
          border: `1px solid ${active ? alpha(meta!.color, 22) : "color-mix(in srgb, var(--ink) 8.4%, transparent)"}`,
        }}
      >
        {active ? (
          <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dotColor }} />
        ) : (
          <ListFilter size={11} color={dotColor} className="shrink-0" />
        )}
        {fullLabel}
        <ChevronDown
          size={11}
          color="var(--ink-3)"
          className="shrink-0"
          style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }}
        />
      </button>

      <DropdownPortal anchorRef={ref} open={open} align="right">
        <div
          ref={menuRef}
          className="min-w-[150px] rounded-lg shadow-lg duration-150 overflow-hidden"
          style={{ background: "var(--field)", border: "1px solid color-mix(in srgb, var(--ink) 10.2%, transparent)" }}
        >
          <button
            onClick={() => { onChange(""); setOpen(false); }}
            className="group w-full flex items-center justify-between gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-ink/10"
            style={{ background: !active ? "color-mix(in srgb, var(--ink) 4.2%, transparent)" : "transparent" }}
          >
            <span
              className="transition-colors group-hover:!text-[var(--ink)]"
              style={{ color: !active ? "var(--ink)" : "var(--ink-2)" }}
            >
              All outcomes
            </span>
            {!active && <CheckCircle2 size={13} color="var(--ink)" className="shrink-0" />}
          </button>
          {OUTCOME_OPTIONS.map((o) => {
            const isSelected = value === o.value;
            const m = OUTCOME_META[o.value];
            return (
              <button
                key={o.value}
                onClick={() => { onChange(o.value); setOpen(false); }}
                className="group w-full flex items-center justify-between gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-ink/10"
                style={{ background: isSelected ? "color-mix(in srgb, var(--ink) 4.2%, transparent)" : "transparent" }}
              >
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: m.color }} />
                  <span
                    className="transition-colors group-hover:!text-[var(--ink)]"
                    style={{ color: isSelected ? "var(--ink)" : "var(--ink-2)" }}
                  >
                    {o.label}
                  </span>
                </span>
                {isSelected && <CheckCircle2 size={13} color="var(--ink)" className="shrink-0" />}
              </button>
            );
          })}
        </div>
      </DropdownPortal>
    </div>
  );
}