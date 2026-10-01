import { useEffect, useRef, useState } from "react";
import { ChevronDown, CheckCircle2, Plug } from "lucide-react";
import { PROVIDER_META } from "../../lib/domain";
import { DropdownPortal } from "../shared/DropdownPortal";
import { ProviderIcon } from "../shared/ProviderIcon";

const PROVIDER_OPTIONS = Object.keys(PROVIDER_META);

export function ActivityProviderFilterDropdown({
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
  const fullLabel = active ? PROVIDER_META[value]?.name ?? value : "All providers";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[12px] rounded-md px-2 py-1 outline-none transition-colors hover:brightness-125"
        style={{
          color: "var(--ink)",
          background: active ? (PROVIDER_META[value]?.bg ?? "color-mix(in srgb, var(--ink) 10%, transparent)") : "color-mix(in srgb, var(--ink) 10%, transparent)",
          border: `1px solid ${active ? (PROVIDER_META[value]?.color ?? "var(--ink-3)") + "38" : "color-mix(in srgb, var(--ink) 14%, transparent)"}`,
        }}
      >
        {active ? <ProviderIcon provider={value} size={13} className="shrink-0" /> : <Plug size={11} color="var(--ink-3)" className="shrink-0" />}
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
          style={{ background: "var(--field)", border: "1px solid color-mix(in srgb, var(--ink) 17%, transparent)" }}
        >
          <button
            onClick={() => { onChange(""); setOpen(false); }}
            className="group w-full flex items-center justify-between gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-ink/10"
            style={{ background: !active ? "color-mix(in srgb, var(--ink) 7%, transparent)" : "transparent" }}
          >
            <span
              className="transition-colors group-hover:!text-[var(--ink)]"
              style={{ color: !active ? "var(--ink)" : "var(--ink-2)" }}
            >
              All providers
            </span>
            {!active && <CheckCircle2 size={13} color="var(--ink)" className="shrink-0" />}
          </button>
          {PROVIDER_OPTIONS.map((p) => {
            const isSelected = value === p;
            const meta = PROVIDER_META[p];
            return (
              <button
                key={p}
                onClick={() => { onChange(p); setOpen(false); }}
                className="group w-full flex items-center justify-between gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-ink/10"
                style={{ background: isSelected ? "color-mix(in srgb, var(--ink) 7%, transparent)" : "transparent" }}
              >
                <span className="flex items-center gap-1.5">
                  <ProviderIcon provider={p} size={12} className="shrink-0" />
                  <span
                    className="transition-colors group-hover:!text-[var(--ink)]"
                    style={{ color: isSelected ? "var(--ink)" : "var(--ink-2)" }}
                  >
                    {meta.name}
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