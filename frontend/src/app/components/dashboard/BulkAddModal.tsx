import { useState } from "react";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import { api, errorMessage, type ApiKeyBulkCreateResult } from "../../lib/api";
import type { Provider } from "../../types";
import { FIELD_STYLE, blurField, focusField } from "../shared/formField";
import { FormError } from "../shared/FormError";
import { ModalActions } from "../shared/ModalActions";
import { ModalShell } from "../shared/ModalShell";
import { ProviderPicker } from "../shared/ProviderPicker";

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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ApiKeyBulkCreateResult | null>(null);

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
      setError(errorMessage(err, "Request failed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <ModalShell title="Bulk Add Keys" onClose={onClose} widthClass="sm:max-w-lg">
      {result ? (
        <div className="space-y-4">
          <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg text-xs" style={{ background: "color-mix(in srgb, var(--accent) 8%, transparent)", color: "var(--accent)", border: "1px solid color-mix(in srgb, var(--accent) 20%, transparent)" }}>
            <CheckCircle2 size={14} className="shrink-0 mt-0.5" />
            <span>
              Added {result.created.length} key{result.created.length === 1 ? "" : "s"}.
              {result.skipped_duplicates > 0 && ` Skipped ${result.skipped_duplicates} duplicate${result.skipped_duplicates === 1 ? "" : "s"}.`}
            </span>
          </div>

          {result.errors.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-ink-2">{result.errors.length} key{result.errors.length === 1 ? "" : "s"} failed:</p>
              <div className="rounded-lg overflow-hidden" style={{ border: "1px solid color-mix(in srgb, var(--bad) 20%, transparent)" }}>
                {result.errors.map((e, i) => (
                  <div key={i} className="flex items-start gap-2 px-3 py-2 text-xs" style={{ background: "color-mix(in srgb, var(--bad) 6%, transparent)", borderTop: i > 0 ? "1px solid color-mix(in srgb, var(--bad) 15%, transparent)" : undefined }}>
                    <AlertTriangle size={12} color="var(--bad)" className="shrink-0 mt-0.5" />
                    <div>
                      <span className="font-mono text-ink-2">{e.raw_key_preview}</span>
                      <span className="text-ink-3"> — {e.detail}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={onClose}
            className="w-full py-2 rounded-lg text-sm font-semibold transition-all active:scale-95"
            style={{ background: "var(--accent)", color: "var(--on-accent)" }}
          >
            Done
          </button>
        </div>
      ) : (
        <>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-ink-2 mb-1.5">Provider</label>
              <ProviderPicker value={provider} onChange={setProvider} />
            </div>

            <div>
              <label className="block text-xs font-medium text-ink-2 mb-1.5">
                API Keys <span className="text-ink-3 font-normal">— one per line (commas also work)</span>
              </label>
              <textarea
                className="thin-scrollbar w-full px-3 py-2.5 rounded-lg text-xs font-mono leading-relaxed outline-none transition-all resize-none"
                style={{ ...FIELD_STYLE, height: 200 }}
                rows={8}
                placeholder={"AIza...\nAIza...\nAIza..."}
                value={rawKeys}
                onChange={(e) => setRawKeys(e.target.value)}
                onFocus={focusField}
                onBlur={blurField}
                autoFocus
              />
              <p className="mt-1.5 text-[12px] text-ink-3">
                {keyCount} key{keyCount === 1 ? "" : "s"} detected. Duplicates of keys you already have are skipped automatically.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-2 mb-1.5">Label Prefix</label>
                <input
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none transition-all"
                  style={FIELD_STYLE}
                  placeholder="Key"
                  value={labelPrefix}
                  onChange={(e) => setLabelPrefix(e.target.value)}
                  onFocus={focusField}
                  onBlur={blurField}
                />
                <p className="mt-1 text-[12px] text-ink-3">Keys are labeled "{labelPrefix || "Key"} 1", "{labelPrefix || "Key"} 2", …</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-2 mb-1.5">Daily Limit</label>
                <input
                  className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none transition-all"
                  style={FIELD_STYLE}
                  type="number"
                  placeholder="15000"
                  value={limit}
                  onChange={(e) => setLimit(e.target.value)}
                  onFocus={focusField}
                  onBlur={blurField}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-ink-2 mb-1.5">
                Model <span className="text-ink-3 font-normal">(optional, applies to all)</span>
              </label>
              <input
                className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none transition-all"
                style={FIELD_STYLE}
                placeholder="e.g. gemini-3.6-flash"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                onFocus={focusField}
                onBlur={blurField}
              />
            </div>
          </div>

          {error && <FormError message={error} />}

          <ModalActions
            onCancel={onClose}
            onSubmit={handleSubmit}
            submitLabel={saving ? "Adding…" : `Add ${keyCount || ""} Key${keyCount === 1 ? "" : "s"}`}
            saving={saving}
            disabled={keyCount === 0}
          />
        </>
      )}
    </ModalShell>
  );
}
