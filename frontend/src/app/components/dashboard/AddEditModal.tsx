import { useState } from "react";
import { X, Eye, EyeOff, Shield, ChevronDown, Search, Loader2 } from "lucide-react";
import { api, errorMessage, type ModelOption } from "../../lib/api";
import { defaultKeyLabel } from "../../lib/domain";
import type { AK, FormState } from "../../types";
import { FIELD_STYLE, blurField, focusField } from "../shared/formField";
import { FormError } from "../shared/FormError";
import { ModalActions } from "../shared/ModalActions";
import { ModalShell } from "../shared/ModalShell";
import { ProviderPicker } from "../shared/ProviderPicker";

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
      setModelError(errorMessage(err, "Couldn't reach the provider to list models."));
    } finally {
      setModelLoading(false);
    }
  }

  return (
    <ModalShell title={editKey ? "Edit Key" : "Add API Key"} onClose={onClose} widthClass="sm:max-w-md">
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1.5">Label</label>
          <input
            className="w-full px-3 py-2 rounded-lg text-sm outline-none transition-all"
            style={FIELD_STYLE}
            placeholder={editKey ? "Label" : defaultKeyLabel(form.provider, form.model)}
            value={form.label}
            onChange={(e) => setForm({ ...form, label: e.target.value })}
            onFocus={focusField}
            onBlur={blurField}
            autoFocus
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1.5">Provider</label>
          <ProviderPicker
            value={form.provider}
            onChange={(p) => {
              setForm({ ...form, provider: p, model: "" });
              setModelOptions(null);
              setModelError(null);
            }}
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1.5">API Key</label>
          <div className="relative">
            <input
              className="w-full px-3 py-2 pr-9 rounded-lg text-sm font-mono outline-none transition-all"
              style={FIELD_STYLE}
              type={showKey ? "text" : "password"}
              placeholder={editKey ? "Leave blank to keep current" : "sk-… or AIza…"}
              value={form.rawKey}
              onChange={(e) => setForm({ ...form, rawKey: e.target.value })}
              onFocus={focusField}
              onBlur={blurField}
            />
            <button onClick={() => setShowKey(!showKey)} className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded transition-colors hover:bg-ink/5">
              {showKey ? <EyeOff size={14} color="var(--ink-4)" /> : <Eye size={14} color="var(--ink-4)" />}
            </button>
          </div>
          <p className="mt-1.5 text-[12px] text-ink-3 flex items-center gap-1.5">
            <Shield size={10} color="var(--ink-4)" className="shrink-0" />
            Encrypted before storage — never shown in plaintext
          </p>
        </div>

        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1.5">
            Model <span className="text-ink-3 font-normal">(optional)</span>
          </label>
          <p className="text-[12px] text-ink-3 mb-2">
            Pin this key to one model — it will still be used for requests to that model, plus any request
            that doesn't specify a model. Leave unset to serve requests for any model.
          </p>

          {form.model ? (
            <div
              className="flex items-center justify-between px-3 py-2 rounded-lg text-sm"
              style={{ ...FIELD_STYLE, background: "color-mix(in srgb, var(--accent) 6%, transparent)", borderColor: "color-mix(in srgb, var(--accent) 20%, transparent)" }}
            >
              <span className="font-mono text-ink truncate">{form.model}</span>
              <button onClick={() => setForm({ ...form, model: "" })} className="shrink-0 ml-2 p-0.5 rounded transition-colors hover:bg-ink/10">
                <X size={13} color="var(--ink-3)" />
              </button>
            </div>
          ) : (
            <div>
              <button
                onClick={() => { fetchModels(); setModelSearch(""); }}
                disabled={modelLoading}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.98] disabled:active:scale-100 disabled:opacity-60"
                style={{ background: "var(--field)", color: "var(--ink-2)", border: "1px solid color-mix(in srgb, var(--ink) 10.2%, transparent)", boxShadow: "inset 0 1px 0 rgba(0,0,0,0.3)" }}
              >
                {modelLoading ? <Loader2 size={13} className="animate-spin" /> : <ChevronDown size={13} />}
                {modelLoading ? "Loading models…" : editKey ? "Select Model (uses saved key)" : "Select Model"}
              </button>

              {modelPickerOpen && modelOptions && (
                <div
                  className="relative z-10 mt-1.5 w-full rounded-lg shadow-lg duration-150 overflow-hidden"
                  style={{ background: "var(--field)", border: "1px solid color-mix(in srgb, var(--ink) 12%, transparent)", boxShadow: "0 12px 32px rgba(0,0,0,0.6)" }}
                >
                  {modelOptions.length > 5 && (
                    <div className="p-1.5 sticky top-0" style={{ background: "var(--field)", borderBottom: "1px solid color-mix(in srgb, var(--ink) 8.4%, transparent)" }}>
                      <div className="relative">
                        <Search size={12} color="var(--ink-4)" className="absolute left-2 top-1/2 -translate-y-1/2" />
                        <input
                          autoFocus
                          value={modelSearch}
                          onChange={(e) => setModelSearch(e.target.value)}
                          placeholder="Search models…"
                          className="w-full pl-6.5 pr-2 py-1.5 rounded-md text-xs outline-none"
                          style={{ background: "color-mix(in srgb, var(--ink) 4.8%, transparent)", color: "var(--ink)", border: "1px solid transparent" }}
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
                        return <p className="px-3 py-2.5 text-xs text-ink-3">No models available for this key.</p>;
                      }
                      if (filtered.length === 0) {
                        return <p className="px-3 py-2.5 text-xs text-ink-3">No models match "{modelSearch}".</p>;
                      }
                      return filtered.map((m) => (
                        <button
                          key={m.id}
                          onClick={() => { setForm({ ...form, model: m.id }); setModelPickerOpen(false); setModelSearch(""); }}
                          className="w-full text-left px-3 py-2 text-xs transition-colors hover:bg-ink/5"
                        >
                          <div className="text-ink truncate">{m.label}</div>
                          {m.label !== m.id && <div className="text-[12px] font-mono text-ink-3 truncate">{m.id}</div>}
                        </button>
                      ));
                    })()}
                  </div>
                </div>
              )}
            </div>
          )}
          {modelError && <p className="mt-1.5 text-[12px]" style={{ color: "var(--bad)" }}>{modelError}</p>}
        </div>

        <div>
          <label className="block text-xs font-medium text-ink-2 mb-1.5">Daily Limit</label>
          <input
            className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none transition-all"
            style={FIELD_STYLE}
            type="number"
            placeholder="15000"
            value={form.limit}
            onChange={(e) => setForm({ ...form, limit: e.target.value })}
            onFocus={focusField}
            onBlur={blurField}
          />
        </div>
      </div>

      {error && <FormError message={error} />}

      <ModalActions
        onCancel={onClose}
        onSubmit={() => onSave(form)}
        submitLabel={editKey ? "Save Changes" : "Add Key"}
        saving={!!saving}
      />
    </ModalShell>
  );
}
