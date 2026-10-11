import { useRef, useState } from "react";
import { CheckCircle2, ChevronDown } from "lucide-react";
import { PROVIDERS, providerMeta } from "../../lib/domain";
import { useClickOutside } from "../../lib/useClickOutside";
import type { Provider } from "../../types";
import { FIELD_BORDER, FIELD_STYLE, FOCUS_BORDER } from "./formField";
import { ProviderIcon } from "./ProviderIcon";

export function ProviderPicker({ value, onChange }: { value: Provider; onChange: (provider: Provider) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useClickOutside(ref, () => setOpen(false), open);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm outline-none transition-all"
        style={{ ...FIELD_STYLE, border: `1px solid ${open ? FOCUS_BORDER : FIELD_BORDER}` }}
      >
        <span className="flex items-center gap-2">
          <span className="flex items-center justify-center shrink-0">
            <ProviderIcon provider={value} size={15} />
          </span>
          <span className="font-medium text-ink">{providerMeta(value).name}</span>
        </span>
        <ChevronDown size={14} color="var(--ink-4)" style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }} />
      </button>

      {open && (
        <div
          className="absolute z-10 mt-1.5 w-full rounded-lg shadow-lg duration-150 overflow-hidden"
          style={{ background: "var(--field)", border: "1px solid color-mix(in srgb, var(--ink) 12%, transparent)", boxShadow: "0 12px 32px rgba(0,0,0,0.6)" }}
        >
          {PROVIDERS.map((p) => {
            const active = value === p;
            return (
              <button
                key={p}
                onClick={() => { onChange(p); setOpen(false); }}
                className="w-full flex items-center gap-2.5 text-left px-3 py-2.5 text-sm transition-colors hover:bg-ink/5"
                style={{ background: active ? "var(--field)" : "transparent", borderLeft: active ? "2px solid var(--accent)" : "2px solid transparent" }}
              >
                <span className="flex items-center justify-center shrink-0">
                  <ProviderIcon provider={p} size={15} />
                </span>
                <span className="flex-1" style={{ color: active ? "var(--ink)" : "var(--ink-2)" }}>{providerMeta(p).name}</span>
                {active && <CheckCircle2 size={14} color="var(--accent)" className="shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
