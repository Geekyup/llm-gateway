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
          style={{ background: open === "provider" ? "rgba(255,255,255,0.09)" : "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", color: "#DCDCE1" }}
        >
          <ProvIcon provider={provider} size={11} />
          {PROVIDER_NAMES[provider].name}
          <ChevronDown size={11} color="#71717A" style={{ transform: open === "provider" ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }} />
        </button>
        {open === "provider" && (
          <div
            className="absolute z-20 bottom-full mb-1.5 left-0 w-44 max-w-[calc(100vw-2rem)] rounded-lg shadow-lg animate-in fade-in slide-in-from-bottom-1 duration-150 overflow-hidden"
            style={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.1)" }}
          >
            {providers.map((p) => {
              const active = p === provider;
              return (
                <button
                  key={p}
                  onClick={() => { onProvider(p); setOpen(null); }}
                  className="w-full flex items-center gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-white/5"
                  style={{ background: active ? "rgba(255,255,255,0.04)" : "transparent" }}
                >
                  <ProvIcon provider={p} size={12} />
                  <span className="flex-1" style={{ color: active ? "#ECECF0" : "#A1A1AA" }}>{PROVIDER_NAMES[p].name}</span>
                  {active && <CheckCircle2 size={12} color="#ECECF0" />}
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
          style={{ background: open === "model" ? "rgba(255,255,255,0.09)" : "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", color: model ? "#DCDCE1" : "#71717A" }}
        >
          <span className="truncate min-w-0">{model || "pool default"}</span>
          <ChevronDown size={11} color="#71717A" className="shrink-0 ml-auto" style={{ transform: open === "model" ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }} />
        </button>
        {open === "model" && (
          <div
            className="absolute z-20 bottom-full mb-1.5 left-0 w-56 max-w-[calc(100vw-2rem)] rounded-lg shadow-lg animate-in fade-in slide-in-from-bottom-1 duration-150 overflow-hidden"
            style={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.1)" }}
          >
            <div className="max-h-52 overflow-y-auto py-1">
              <button
                onClick={() => { onModel(""); setOpen(null); }}
                className="w-full flex items-center justify-between text-left px-3 py-2 text-xs transition-colors hover:bg-white/5"
                style={{ background: !model ? "rgba(255,255,255,0.04)" : "transparent" }}
              >
                <span style={{ color: !model ? "#ECECF0" : "#A1A1AA" }}>Pool default (any)</span>
                {!model && <CheckCircle2 size={12} color="#ECECF0" />}
              </button>
              {modelsForProvider.map((m) => {
                const active = m === model;
                return (
                  <button key={m} onClick={() => { onModel(m); setOpen(null); }} className="w-full flex items-center justify-between text-left px-3 py-2 text-xs font-mono transition-colors hover:bg-white/5">
                    <span className="truncate" style={{ color: active ? "#ECECF0" : "#A1A1AA" }}>{m}</span>
                    {active && <CheckCircle2 size={12} color="#ECECF0" className="shrink-0 ml-2" />}
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