import { Loader2 } from "lucide-react";

export function ModalActions({
  onCancel,
  onSubmit,
  submitLabel,
  saving,
  disabled,
}: {
  onCancel: () => void;
  onSubmit: () => void;
  submitLabel: string;
  saving: boolean;
  disabled?: boolean;
}) {
  return (
    <div className="flex gap-2 mt-6">
      <button
        onClick={onCancel}
        className="flex-1 py-2 rounded-lg text-sm font-medium transition-colors active:scale-95"
        style={{ background: "color-mix(in srgb, var(--ink) 4.2%, transparent)", color: "var(--ink-3)", border: "1px solid color-mix(in srgb, var(--ink) 6%, transparent)" }}
      >
        Cancel
      </button>
      <button
        onClick={() => !saving && onSubmit()}
        disabled={saving || disabled}
        className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-1.5 active:scale-95 disabled:active:scale-100 disabled:opacity-60"
        style={{ background: "var(--accent)", color: "var(--on-accent)" }}
      >
        {saving && <Loader2 size={13} className="animate-spin" />}
        {submitLabel}
      </button>
    </div>
  );
}
