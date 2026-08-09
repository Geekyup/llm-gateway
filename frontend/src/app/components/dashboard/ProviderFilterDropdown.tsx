import { useEffect, useRef, useState } from "react";
import { ChevronDown, CheckCircle2 } from "lucide-react";
import { PROVIDER_META } from "../../lib/domain";
import type { PF, Provider } from "../../types";

export function ProviderFilterDropdown({ filter, onFilter }: { filter: PF; onFilter: (f: PF) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  const options: PF[] = ["all", ...(Object.keys(PROVIDER_META) as Provider[])];
  const label = filter === "all" ? "All" : PROVIDER_META[filter].name;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all"
        style={{ color: "#ECECF0", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)" }}
      >
        {label}
        <ChevronDown size={11} color="#71717A" style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }} />
      </button>

      {open && (
        <div
          className="absolute right-0 z-10 mt-1.5 min-w-[140px] rounded-lg shadow-lg animate-in fade-in slide-in-from-top-1 duration-150 overflow-hidden"
          style={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.1)" }}
        >
          {options.map((f) => {
            const active = filter === f;
            const meta = f === "all" ? null : PROVIDER_META[f];
            return (
              <button
                key={f}
                onClick={() => { onFilter(f); setOpen(false); }}
                className="w-full flex items-center justify-between gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-white/5"
                style={{ background: active ? "rgba(255,255,255,0.04)" : "transparent" }}
              >
                <span style={{ color: active ? "#ECECF0" : "#A1A1AA" }}>{f === "all" ? "All" : meta!.name}</span>
                {active && <CheckCircle2 size={13} color="#ECECF0" className="shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
