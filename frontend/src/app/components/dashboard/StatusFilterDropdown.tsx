import { useEffect, useRef, useState } from "react";
import { ChevronDown, CheckCircle2, ListFilter } from "lucide-react";
import { STATUS_META } from "../../lib/domain";
import type { SF, Status } from "../../types";
import { DropdownPortal } from "../shared/DropdownPortal";

export function StatusFilterDropdown({ filter, onFilter }: { filter: SF; onFilter: (f: SF) => void }) {
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

  const options: SF[] = ["all", ...(Object.keys(STATUS_META) as Status[])];
  const active = filter !== "all";
  const fullLabel = active ? STATUS_META[filter].text : "All statuses";
  const shortLabel = active ? STATUS_META[filter].text : "Status";
  const dotColor = active ? STATUS_META[filter].color : "var(--ink-3)";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-2.5 py-1 rounded-md text-[12px] font-medium transition-all whitespace-nowrap hover:brightness-125"
        style={{
          color: "var(--ink)",
          background: active ? STATUS_META[filter].bg : "color-mix(in srgb, var(--ink) 6%, transparent)",
          border: `1px solid ${active ? STATUS_META[filter].bd : "color-mix(in srgb, var(--ink) 8.4%, transparent)"}`,
        }}
      >
        {active ? (
          <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dotColor }} />
        ) : (
          <ListFilter size={12} color={dotColor} className="shrink-0" />
        )}
        <span className="sm:hidden">{shortLabel}</span>
        <span className="hidden sm:inline">{fullLabel}</span>
        <ChevronDown size={11} color="var(--ink-3)" className="shrink-0" style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }} />
      </button>

      <DropdownPortal anchorRef={ref} open={open} align="right">
        <div
          ref={menuRef}
          className="min-w-[140px] rounded-lg shadow-lg duration-150 overflow-hidden"
          style={{ background: "var(--field)", border: "1px solid color-mix(in srgb, var(--ink) 10.2%, transparent)" }}
        >
          {options.map((f) => {
            const isSelected = filter === f;
            const meta = f === "all" ? null : STATUS_META[f];
            return (
              <button
                key={f}
                onClick={() => { onFilter(f); setOpen(false); }}
                className="group w-full flex items-center justify-between gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-ink/10"
                style={{ background: isSelected ? "color-mix(in srgb, var(--ink) 4.2%, transparent)" : "transparent" }}
              >
                <span
                  className="transition-colors group-hover:!text-[var(--ink)]"
                  style={{ color: isSelected ? "var(--ink)" : "var(--ink-2)" }}
                >
                  {f === "all" ? "All" : meta!.text}
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