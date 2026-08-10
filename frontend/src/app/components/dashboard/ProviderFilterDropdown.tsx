import { useEffect, useRef, useState } from "react";
import { ChevronDown, CheckCircle2, Plug } from "lucide-react";
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
  const active = filter !== "all";
  const label = active ? PROVIDER_META[filter].name : "All providers";
  const ActiveIcon = active ? PROVIDER_META[filter].Icon : Plug;
  const iconColor = active ? PROVIDER_META[filter].color : "#71717A";

  return (
    <div className="relative" ref={ref}>
      <div className="text-[10px] text-zinc-600 mb-1">Provider</div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all"
        style={{
          color: "#ECECF0",
          background: active ? PROVIDER_META[filter].bg : "rgba(255,255,255,0.06)",
          border: `1px solid ${active ? PROVIDER_META[filter].color + "38" : "rgba(255,255,255,0.08)"}`,
        }}
      >
        <ActiveIcon size={12} color={iconColor} />
        {label}
        <ChevronDown size={11} color="#71717A" style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }} />
      </button>

      {open && (
        <div
          className="absolute right-0 z-10 mt-1.5 min-w-[140px] rounded-lg shadow-lg animate-in fade-in slide-in-from-top-1 duration-150 overflow-hidden"
          style={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.1)" }}
        >
          {options.map((f) => {
            const isSelected = filter === f;
            const meta = f === "all" ? null : PROVIDER_META[f];
            return (
              <button
                key={f}
                onClick={() => { onFilter(f); setOpen(false); }}
                className="w-full flex items-center justify-between gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-white/5"
                style={{ background: isSelected ? "rgba(255,255,255,0.04)" : "transparent" }}
              >
                <span style={{ color: isSelected ? "#ECECF0" : "#A1A1AA" }}>{f === "all" ? "All" : meta!.name}</span>
                {isSelected && <CheckCircle2 size={13} color="#ECECF0" className="shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}