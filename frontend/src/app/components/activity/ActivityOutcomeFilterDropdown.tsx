import { useEffect, useRef, useState } from "react";
import { ChevronDown, CheckCircle2, ListFilter } from "lucide-react";
import { OUTCOME_META, outcomeMeta } from "../../lib/domain";
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
  const dotColor = active ? meta!.color : "#71717A";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[11px] rounded-md px-2 py-1 outline-none transition-colors"
        style={{
          color: "#ECECF0",
          background: active ? meta!.bg : "rgba(255,255,255,0.06)",
          border: `1px solid ${active ? meta!.color + "38" : "rgba(255,255,255,0.08)"}`,
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
          color="#71717A"
          className="shrink-0"
          style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }}
        />
      </button>

      <DropdownPortal anchorRef={ref} open={open} align="right">
        <div
          ref={menuRef}
          className="min-w-[150px] rounded-lg shadow-lg animate-in fade-in slide-in-from-top-1 duration-150 overflow-hidden"
          style={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.1)" }}
        >
          <button
            onClick={() => { onChange(""); setOpen(false); }}
            className="w-full flex items-center justify-between gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-white/5"
            style={{ background: !active ? "rgba(255,255,255,0.04)" : "transparent" }}
          >
            <span style={{ color: !active ? "#ECECF0" : "#A1A1AA" }}>All outcomes</span>
            {!active && <CheckCircle2 size={13} color="#ECECF0" className="shrink-0" />}
          </button>
          {OUTCOME_OPTIONS.map((o) => {
            const isSelected = value === o.value;
            const m = OUTCOME_META[o.value];
            return (
              <button
                key={o.value}
                onClick={() => { onChange(o.value); setOpen(false); }}
                className="w-full flex items-center justify-between gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-white/5"
                style={{ background: isSelected ? "rgba(255,255,255,0.04)" : "transparent" }}
              >
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: m.color }} />
                  <span style={{ color: isSelected ? "#ECECF0" : "#A1A1AA" }}>{o.label}</span>
                </span>
                {isSelected && <CheckCircle2 size={13} color="#ECECF0" className="shrink-0" />}
              </button>
            );
          })}
        </div>
      </DropdownPortal>
    </div>
  );
}
