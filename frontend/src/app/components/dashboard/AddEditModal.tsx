import { useEffect, useRef, useState } from "react";
import {
  X, Eye, EyeOff, Shield, AlertTriangle, ChevronDown, CheckCircle2, Search, Loader2,
} from "lucide-react";
import { api, ApiError, type ModelOption } from "../../lib/api";
import { PROVIDER_NAMES } from "../../lib/domain";
import { ProviderIcon } from "../shared/ProviderIcon";
import type { AK, FormState, Provider } from "../../types";

export function AddEditModal({
  editKey,
  onSave,
  onClose,
  error,
  saving,
}: {
  editKey: AK | null;
  onSave: (f: FormState) => void;
  onClose: () => void;
  error?: string | null;
  saving?: boolean;
}) {
  const [form, setForm] = useState<FormState>({
    label: editKey?.label ?? "",
    provider: editKey?.provider ?? "gemini",
    rawKey: "",
    limit: String(editKey?.limit ?? 15000),
    model: editKey?.model ?? "",
  });
  const [showKey, setShowKey] = useState(false);
  const [providerPickerOpen, setProviderPickerOpen] = useState(false);
  const [modelOptions, setModelOptions] = useState<ModelOption[] | null>(null);
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [modelLoading, setModelLoading] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);
  const [modelSearch, setModelSearch] = useState("");

  async function fetchModels() {
    if (!form.rawKey.trim() && !editKey) {
      setModelError("Enter the API key above to look up models for it.");
      return;
    }
    setModelLoading(true);
    setModelError(null);
    try {
      const models = form.rawKey.trim()
        ? await api.listModels(form.provider, form.rawKey.trim())
        : await api.listModelsForKey(Number(editKey!.id));
      setModelOptions(models);
      setModelPickerOpen(true);
    } catch (err) {
      setModelError(err instanceof ApiError ? err.message : "Couldn't reach the provider to list models.");
    } finally {
      setModelLoading(false);
    }
  }

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

  function focus(e: React.FocusEvent<HTMLInputElement>) {
    e.target.style.borderColor = "rgba(0,214,143,0.4)";
    e.target.style.boxShadow = "inset 0 1px 0 rgba(0,0,0,0.25), 0 0 0 3px rgba(0,214,143,0.07)";
  }

  function blur(e: React.FocusEvent<HTMLInputElement>) {
    e.target.style.borderColor = "rgba(255,255,255,0.10)";
    e.target.style.boxShadow = "inset 0 1px 0 rgba(0,0,0,0.25)";
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
        className="w-full sm:max-w-md rounded-2xl p-5 sm:p-6 max-h-[92vh] overflow-y-auto animate-in fade-in zoom-in-95 slide-in-from-bottom-2 duration-200 ease-out"
        style={{ background: "#141416", border: "1px solid rgba(255,255,255,0.09)", boxShadow: "0 32px 80px rgba(0,0,0,0.6)" }}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-sm font-semibold text-zinc-100">{editKey ? "Edit Key" : "Add API Key"}</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg transition-colors hover:bg-white/5">
            <X size={16} color="#52525B" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Label</label>
            <input
              className="w-full px-3 py-2 rounded-lg text-sm outline-none transition-all"
              style={baseInp}
              placeholder="Production Primary"
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
              onFocus={focus}
              onBlur={blur}
              autoFocus
            />
          </div>

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
                    <ProviderIcon provider={form.provider} size={15} />
                  </span>
                  <span className="font-medium text-zinc-100">{PROVIDER_NAMES[form.provider].name}</span>
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
                    const active = form.provider === p;
                    return (
                      <button
                        key={p}
                        onClick={() => {
                          setForm({ ...form, provider: p, model: "" });
                          setModelOptions(null);
                          setModelError(null);
                          setProviderPickerOpen(false);
                        }}
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
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">API Key</label>
            <div className="relative">
              <input
                className="w-full px-3 py-2 pr-9 rounded-lg text-sm font-mono outline-none transition-all"
                style={baseInp}
                type={showKey ? "text" : "password"}
                placeholder={editKey ? "Leave blank to keep current" : "sk-… or AIza…"}
                value={form.rawKey}
                onChange={(e) => setForm({ ...form, rawKey: e.target.value })}
                onFocus={focus}
                onBlur={blur}
              />
              <button onClick={() => setShowKey(!showKey)} className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded transition-colors hover:bg-white/5">
                {showKey ? <EyeOff size={14} color="#52525B" /> : <Eye size={14} color="#52525B" />}
              </button>
            </div>
            <p className="mt-1.5 text-[11px] text-zinc-600 flex items-center gap-1.5">
              <Shield size={10} color="#52525B" className="shrink-0" />
              Encrypted before storage — never shown in plaintext
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Model <span className="text-zinc-600 font-normal">(optional)</span>
            </label>
            <p className="text-[11px] text-zinc-600 mb-2">
              Pin this key to one model — it will still be used for requests to that model, plus any request
              that doesn't specify a model. Leave unset to serve requests for any model.
            </p>

            {form.model ? (
              <div
                className="flex items-center justify-between px-3 py-2 rounded-lg text-sm"
                style={{ ...baseInp, background: "rgba(0,214,143,0.06)", borderColor: "rgba(0,214,143,0.2)" }}
              >
                <span className="font-mono text-zinc-200 truncate">{form.model}</span>
                <button onClick={() => setForm({ ...form, model: "" })} className="shrink-0 ml-2 p-0.5 rounded transition-colors hover:bg-white/10">
                  <X size={13} color="#71717A" />
                </button>
              </div>
            ) : (
              <div>
                <button
                  onClick={() => { fetchModels(); setModelSearch(""); }}
                  disabled={modelLoading}
                  className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.98] disabled:active:scale-100 disabled:opacity-60"
                  style={{ background: "#1A1A1D", color: "#A1A1AA", border: "1px solid rgba(255,255,255,0.10)", boxShadow: "inset 0 1px 0 rgba(0,0,0,0.25)" }}
                >
                  {modelLoading ? <Loader2 size={13} className="animate-spin" /> : <ChevronDown size={13} />}
                  {modelLoading ? "Loading models…" : editKey ? "Select Model (uses saved key)" : "Select Model"}
                </button>

                {modelPickerOpen && modelOptions && (
                  <div
                    className="relative z-10 mt-1.5 w-full rounded-lg shadow-lg animate-in fade-in slide-in-from-top-1 duration-150 overflow-hidden"
                    style={{ background: "#202024", border: "1px solid rgba(255,255,255,0.12)", boxShadow: "0 12px 32px rgba(0,0,0,0.5)" }}
                  >
                    {modelOptions.length > 5 && (
                      <div className="p-1.5 sticky top-0" style={{ background: "#202024", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                        <div className="relative">
                          <Search size={12} color="#52525B" className="absolute left-2 top-1/2 -translate-y-1/2" />
                          <input
                            autoFocus
                            value={modelSearch}
                            onChange={(e) => setModelSearch(e.target.value)}
                            placeholder="Search models…"
                            className="w-full pl-6.5 pr-2 py-1.5 rounded-md text-xs outline-none"
                            style={{ background: "rgba(255,255,255,0.05)", color: "#ECECF0", border: "1px solid transparent" }}
                          />
                        </div>
                      </div>
                    )}
                    <div className="max-h-40 overflow-y-auto">
                      {(() => {
                        const q = modelSearch.trim().toLowerCase();
                        const filtered = q
                          ? modelOptions.filter((m) => m.label.toLowerCase().includes(q) || m.id.toLowerCase().includes(q))
                          : modelOptions;
                        if (modelOptions.length === 0) {
                          return <p className="px-3 py-2.5 text-xs text-zinc-500">No models available for this key.</p>;
                        }
                        if (filtered.length === 0) {
                          return <p className="px-3 py-2.5 text-xs text-zinc-500">No models match "{modelSearch}".</p>;
                        }
                        return filtered.map((m) => (
                          <button
                            key={m.id}
                            onClick={() => { setForm({ ...form, model: m.id }); setModelPickerOpen(false); setModelSearch(""); }}
                            className="w-full text-left px-3 py-2 text-xs transition-colors hover:bg-white/5"
                          >
                            <div className="text-zinc-200 truncate">{m.label}</div>
                            {m.label !== m.id && <div className="text-[10px] font-mono text-zinc-600 truncate">{m.id}</div>}
                          </button>
                        ));
                      })()}
                    </div>
                  </div>
                )}
              </div>
            )}
            {modelError && <p className="mt-1.5 text-[11px]" style={{ color: "#EF4444" }}>{modelError}</p>}
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Daily Limit</label>
            <input
              className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none transition-all"
              style={baseInp}
              type="number"
              placeholder="15000"
              value={form.limit}
              onChange={(e) => setForm({ ...form, limit: e.target.value })}
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
            onClick={() => !saving && onSave(form)}
            disabled={saving}
            className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-1.5 active:scale-95 disabled:active:scale-100"
            style={{ background: "#00D68F", color: "#0A0A0B", boxShadow: "0 0 16px rgba(0,214,143,0.3)", opacity: saving ? 0.7 : 1 }}
            onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "0 0 28px rgba(0,214,143,0.55)")}
            onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "0 0 16px rgba(0,214,143,0.3)")}
          >
            {saving && <Loader2 size={13} className="animate-spin" />}
            {editKey ? "Save Changes" : "Add Key"}
          </button>
        </div>
      </div>
    </div>
  );
}