import { useEffect, useRef, useState } from "react";
import { X, ChevronDown, CheckCircle2, AlertTriangle, Loader2 } from "lucide-react";
import { api, ApiError, type ApiKeyBulkCreateResult } from "../../lib/api";
import { PROVIDER_NAMES } from "../../lib/domain";
import { ProviderIcon } from "../shared/ProviderIcon";
import type { Provider } from "../../types";

export function BulkAddModal({
  onDone,
  onClose,
}: {
  onDone: () => void;
  onClose: () => void;
}) {
  const [provider, setProvider] = useState<Provider>("gemini");
  const [rawKeys, setRawKeys] = useState("");
  const [labelPrefix, setLabelPrefix] = useState("Key");
  const [limit, setLimit] = useState("15000");
  const [model, setModel] = useState("");
  const [providerPickerOpen, setProviderPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ApiKeyBulkCreateResult | null>(null);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const providerPickerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!providerPickerOpen) return;
    const h = (e: MouseEvent) => {
      if (providerPickerRef.current && !providerPickerRef.current.contains(e.target as Node)) {
        setProviderPickerOpen(false);
      }
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [providerPickerOpen]);

  const baseInp: React.CSSProperties = {
    background: "#1A1A1D",
    border: "1px solid rgba(255,255,255,0.10)",
    boxShadow: "inset 0 1px 0 rgba(0,0,0,0.25)",
    color: "#ECECF0",
  };

  function focus(e: React.FocusEvent<HTMLElement>) {
    e.currentTarget.style.borderColor = "rgba(0,214,143,0.4)";
    e.currentTarget.style.boxShadow = "inset 0 1px 0 rgba(0,0,0,0.25), 0 0 0 3px rgba(0,214,143,0.07)";
  }

  function blur(e: React.FocusEvent<HTMLElement>) {
    e.currentTarget.style.borderColor = "rgba(255,255,255,0.10)";
    e.currentTarget.style.boxShadow = "inset 0 1px 0 rgba(0,0,0,0.25)";
  }

  const keyCount = rawKeys.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean).length;

  async function handleSubmit() {
    if (!rawKeys.trim()) {
      setError("Paste at least one API key.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await api.createKeysBulk({
        provider,
        raw_keys: rawKeys,
        label_prefix: labelPrefix.trim() || "Key",
        daily_limit: Number(limit) || 15000,
        model: model.trim() || null,
      });
      setResult(res);
      if (res.created.length > 0) onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Request failed");
    } finally {
      setSaving(false);
    }
  }

  const overlayMouseDownOnSelf = useRef(false);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
      style={{ background: "rgba(0,0,0,0.72)", backdropFilter: "blur(4px)" }}
      onMouseDown={(e) => { overlayMouseDownOnSelf.current = e.target === e.currentTarget; }}
      onMouseUp={(e) => {
        if (overlayMouseDownOnSelf.current && e.target === e.currentTarget) onClose();
        overlayMouseDownOnSelf.current = false;
      }}
    >
      <div
        className="w-full sm:max-w-lg rounded-2xl p-5 sm:p-6 max-h-[92vh] overflow-y-auto animate-in fade-in zoom-in-95 slide-in-from-bottom-2 duration-200 ease-out"
        style={{ background: "#141416", border: "1px solid rgba(255,255,255,0.09)", boxShadow: "0 32px 80px rgba(0,0,0,0.6)" }}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-sm font-semibold text-zinc-100">Bulk Add Keys</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg transition-colors hover:bg-white/5">
            <X size={16} color="#52525B" />
          </button>
        </div>

        {result ? (
          <div className="space-y-4">
            <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg text-xs" style={{ background: "rgba(0,214,143,0.08)", color: "#00D68F", border: "1px solid rgba(0,214,143,0.2)" }}>
              <CheckCircle2 size={14} className="shrink-0 mt-0.5" />
              <span>
                Added {result.created.length} key{result.created.length === 1 ? "" : "s"}.
                {result.skipped_duplicates > 0 && ` Skipped ${result.skipped_duplicates} duplicate${result.skipped_duplicates === 1 ? "" : "s"}.`}
              </span>
            </div>

            {result.errors.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-zinc-400">{result.errors.length} key{result.errors.length === 1 ? "" : "s"} failed:</p>
                <div className="rounded-lg overflow-hidden" style={{ border: "1px solid rgba(239,68,68,0.2)" }}>
                  {result.errors.map((e, i) => (
                    <div key={i} className="flex items-start gap-2 px-3 py-2 text-xs" style={{ background: "rgba(239,68,68,0.06)", borderTop: i > 0 ? "1px solid rgba(239,68,68,0.15)" : undefined }}>
                      <AlertTriangle size={12} color="#EF4444" className="shrink-0 mt-0.5" />
                      <div>
                        <span className="font-mono text-zinc-300">{e.raw_key_preview}</span>
                        <span className="text-zinc-500"> — {e.detail}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={onClose}
              className="w-full py-2 rounded-lg text-sm font-semibold transition-all active:scale-95"
              style={{ background: "#00D68F", color: "#0A0A0B" }}
            >
              Done
            </button>
          </div>
        ) : (
          <>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">Provider</label>
                <div className="relative" ref={providerPickerRef}>
                  <button
                    onClick={() => setProviderPickerOpen((o) => !o)}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm outline-none transition-all"
                    style={{ ...baseInp, borderColor: providerPickerOpen ? "rgba(0,214,143,0.4)" : (baseInp.border as string) }}
                  >
                    <span className="flex items-center gap-2">
                      <span className="flex items-center justify-center shrink-0">
                        <ProviderIcon provider={provider} size={15} />
                      </span>
                      <span className="font-medium text-zinc-100">{PROVIDER_NAMES[provider].name}</span>
                    </span>
                    <ChevronDown size={14} color="#52525B" style={{ transform: providerPickerOpen ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }} />
                  </button>

                  {providerPickerOpen && (
                    <div
                      className="absolute z-10 mt-1.5 w-full rounded-lg shadow-lg animate-in fade-in slide-in-from-top-1 duration-150 overflow-hidden"
                      style={{ background: "#202024", border: "1px solid rgba(255,255,255,0.12)", boxShadow: "0 12px 32px rgba(0,0,0,0.5)" }}
                    >
                      {(Object.keys(PROVIDER_NAMES) as Provider[]).map((p) => {
                        const meta = PROVIDER_NAMES[p];
                        const active = provider === p;
                        return (
                          <button
                            key={p}
                            onClick={() => { setProvider(p); setProviderPickerOpen(false); }}
                            className="w-full flex items-center gap-2.5 text-left px-3 py-2.5 text-sm transition-colors hover:bg-white/5"
                            style={{ background: active ? "#26262B" : "transparent", borderLeft: active ? "2px solid #00D68F" : "2px solid transparent" }}
                          >
                            <span className="flex items-center justify-center shrink-0">
                              <ProviderIcon provider={p} size={15} />
                            </span>
                            <span className="flex-1" style={{ color: active ? "#ECECF0" : "#A1A1AA" }}>{meta.name}</span>
                            {active && <CheckCircle2 size={14} color="#00D68F" className="shrink-0" />}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                  API Keys <span className="text-zinc-600 font-normal">— one per line (commas also work)</span>
                </label>
                <textarea
                  className="dark-scrollbar w-full px-3 py-2.5 rounded-lg text-xs font-mono leading-relaxed outline-none transition-all resize-none"
                  style={{ ...baseInp, height: 200 }}
                  rows={8}
                  placeholder={"AIza...\nAIza...\nAIza..."}
                  value={rawKeys}
                  onChange={(e) => setRawKeys(e.target.value)}
                  onFocus={focus}
                  onBlur={blur}
                  autoFocus
                />
                <p className="mt-1.5 text-[11px] text-zinc-600">
                  {keyCount} key{keyCount === 1 ? "" : "s"} detected. Duplicates of keys you already have are skipped automatically.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">Label Prefix</label>
                  <input
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none transition-all"
                    style={baseInp}
                    placeholder="Key"
                    value={labelPrefix}
                    onChange={(e) => setLabelPrefix(e.target.value)}
                    onFocus={focus}
                    onBlur={blur}
                  />
                  <p className="mt-1 text-[10px] text-zinc-600">Keys are labeled "{labelPrefix || "Key"} 1", "{labelPrefix || "Key"} 2", …</p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">Daily Limit</label>
                  <input
                    className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none transition-all"
                    style={baseInp}
                    type="number"
                    placeholder="15000"
                    value={limit}
                    onChange={(e) => setLimit(e.target.value)}
                    onFocus={focus}
                    onBlur={blur}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                  Model <span className="text-zinc-600 font-normal">(optional, applies to all)</span>
                </label>
                <input
                  className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none transition-all"
                  style={baseInp}
                  placeholder="e.g. gemini-3.6-flash"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  onFocus={focus}
                  onBlur={blur}
                />
              </div>
            </div>

            {error && (
              <div className="mt-4 flex items-start gap-2 px-3 py-2 rounded-lg text-xs" style={{ background: "rgba(239,68,68,0.08)", color: "#EF4444", border: "1px solid rgba(239,68,68,0.2)" }}>
                <AlertTriangle size={13} className="shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <div className="flex gap-2 mt-6">
              <button
                onClick={onClose}
                className="flex-1 py-2 rounded-lg text-sm font-medium transition-colors active:scale-95"
                style={{ background: "rgba(255,255,255,0.04)", color: "#71717A", border: "1px solid rgba(255,255,255,0.06)" }}
              >
                Cancel
              </button>
              <button
                onClick={() => !saving && handleSubmit()}
                disabled={saving || keyCount === 0}
                className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-1.5 active:scale-95 disabled:active:scale-100 disabled:opacity-60"
                style={{ background: "#00D68F", color: "#0A0A0B", boxShadow: "0 0 16px rgba(0,214,143,0.3)" }}
              >
                {saving && <Loader2 size={13} className="animate-spin" />}
                {saving ? "Adding…" : `Add ${keyCount || ""} Key${keyCount === 1 ? "" : "s"}`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}