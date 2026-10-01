import { useEffect, useRef, useState } from "react";
import { ChevronDown, CheckCircle2 } from "lucide-react";
import { PROVIDER_NAMES } from "../../lib/domain";
import { ProviderIcon as ProvIcon } from "../shared/ProviderIcon";
import type { Provider } from "../../types";

export function ModelPill({
  provider,
  model,
  providers,
  modelsForProvider,
  onProvider,
  onModel,
}: {
  provider: Provider;
  model: string;
  providers: Provider[];
  modelsForProvider: string[];
  onProvider: (p: Provider) => void;
  onModel: (m: string) => void;
}) {
  const [open, setOpen] = useState<"provider" | "model" | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(null);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  return (
    <div className="flex items-center gap-1.5 min-w-0" ref={ref}>
      <div className="relative shrink-0">
        <button
          onClick={() => setOpen((o) => (o === "provider" ? null : "provider"))}
          className="flex items-center gap-1.5 pl-2 pr-1.5 py-1 rounded-full text-xs font-medium transition-colors"
          style={{ background: open === "provider" ? "color-mix(in srgb, var(--ink) 9%, transparent)" : "color-mix(in srgb, var(--ink) 4.8%, transparent)", border: "1px solid color-mix(in srgb, var(--ink) 8.4%, transparent)", color: "var(--ink-2)" }}
        >
          <ProvIcon provider={provider} size={13} />
          {PROVIDER_NAMES[provider].name}
          <ChevronDown size={11} color="var(--ink-3)" style={{ transform: open === "provider" ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }} />
        </button>
        {open === "provider" && (
          <div
            className="absolute z-20 bottom-full mb-1.5 left-0 w-44 max-w-[calc(100vw-2rem)] rounded-lg shadow-lg duration-150 overflow-hidden"
            style={{ background: "var(--field)", border: "1px solid color-mix(in srgb, var(--ink) 10.2%, transparent)" }}
          >
            {providers.map((p) => {
              const active = p === provider;
              return (
                <button
                  key={p}
                  onClick={() => { onProvider(p); setOpen(null); }}
                  className="w-full flex items-center gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-ink/5"
                  style={{ background: active ? "color-mix(in srgb, var(--ink) 4.2%, transparent)" : "transparent" }}
                >
                  <ProvIcon provider={p} size={12} />
                  <span className="flex-1" style={{ color: active ? "var(--ink)" : "var(--ink-2)" }}>{PROVIDER_NAMES[p].name}</span>
                  {active && <CheckCircle2 size={12} color="var(--ink)" />}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="relative min-w-0">
        <button
          onClick={() => setOpen((o) => (o === "model" ? null : "model"))}
          className="flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-full text-xs font-mono transition-colors w-full max-w-[160px] min-w-0"
          style={{ background: open === "model" ? "color-mix(in srgb, var(--ink) 9%, transparent)" : "color-mix(in srgb, var(--ink) 4.8%, transparent)", border: "1px solid color-mix(in srgb, var(--ink) 8.4%, transparent)", color: model ? "var(--ink-2)" : "var(--ink-3)" }}
        >
          <span className="truncate min-w-0">{model || "pool default"}</span>
          <ChevronDown size={11} color="var(--ink-3)" className="shrink-0 ml-auto" style={{ transform: open === "model" ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }} />
        </button>
        {open === "model" && (
          <div
            className="absolute z-20 bottom-full mb-1.5 left-0 w-56 max-w-[calc(100vw-2rem)] rounded-lg shadow-lg duration-150 overflow-hidden"
            style={{ background: "var(--field)", border: "1px solid color-mix(in srgb, var(--ink) 10.2%, transparent)" }}
          >
            <div className="max-h-52 overflow-y-auto py-1">
              <button
                onClick={() => { onModel(""); setOpen(null); }}
                className="w-full flex items-center justify-between text-left px-3 py-2 text-xs transition-colors hover:bg-ink/5"
                style={{ background: !model ? "color-mix(in srgb, var(--ink) 4.2%, transparent)" : "transparent" }}
              >
                <span style={{ color: !model ? "var(--ink)" : "var(--ink-2)" }}>Pool default (any)</span>
                {!model && <CheckCircle2 size={12} color="var(--ink)" />}
              </button>
              {modelsForProvider.map((m) => {
                const active = m === model;
                return (
                  <button key={m} onClick={() => { onModel(m); setOpen(null); }} className="w-full flex items-center justify-between text-left px-3 py-2 text-xs font-mono transition-colors hover:bg-ink/5">
                    <span className="truncate" style={{ color: active ? "var(--ink)" : "var(--ink-2)" }}>{m}</span>
                    {active && <CheckCircle2 size={12} color="var(--ink)" className="shrink-0 ml-2" />}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}