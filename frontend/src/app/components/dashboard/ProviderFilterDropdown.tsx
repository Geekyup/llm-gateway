import { useEffect, useRef, useState } from "react";
import { ChevronDown, CheckCircle2, Plug } from "lucide-react";
import { PROVIDER_META, alpha } from "../../lib/domain";
import type { PF, Provider } from "../../types";
import { DropdownPortal } from "../shared/DropdownPortal";
import { ProviderIcon } from "../shared/ProviderIcon";

export function ProviderFilterDropdown({ filter, onFilter }: { filter: PF; onFilter: (f: PF) => void }) {
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

  const options: PF[] = ["all", ...(Object.keys(PROVIDER_META) as Provider[])];
  const active = filter !== "all";
  const fullLabel = active ? PROVIDER_META[filter].name : "All providers";
  const shortLabel = active ? PROVIDER_META[filter].name : "Provider";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-2.5 py-1 rounded-md text-[12px] font-medium transition-all whitespace-nowrap hover:brightness-125"
        style={{
          color: "var(--ink)",
          background: active ? PROVIDER_META[filter].bg : "color-mix(in srgb, var(--ink) 6%, transparent)",
          border: `1px solid ${active ? alpha(PROVIDER_META[filter].color, 22) : "color-mix(in srgb, var(--ink) 8.4%, transparent)"}`,
        }}
      >
        {active ? <ProviderIcon provider={filter} size={12} className="shrink-0" /> : <Plug size={12} color="var(--ink-3)" className="shrink-0" />}
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
            const meta = f === "all" ? null : PROVIDER_META[f];
            return (
              <button
                key={f}
                onClick={() => { onFilter(f); setOpen(false); }}
                className="group w-full flex items-center justify-between gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-ink/10"
                style={{ background: isSelected ? "color-mix(in srgb, var(--ink) 4.2%, transparent)" : "transparent" }}
              >
                <span className="flex items-center gap-1.5">
                  {f === "all" ? <Plug size={12} color="var(--ink-3)" className="shrink-0" /> : <ProviderIcon provider={f} size={12} className="shrink-0" />}
                  <span
                    className="transition-colors group-hover:!text-[var(--ink)]"
                    style={{ color: isSelected ? "var(--ink)" : "var(--ink-2)" }}
                  >
                    {f === "all" ? "All" : meta!.name}
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