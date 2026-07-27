import { useState, useEffect } from "react";
import { X, Eye, EyeOff, Shield, AlertTriangle, Loader2 } from "lucide-react";
import { P } from "../../lib/constants";
import type { AK, FormState, Provider } from "../../types";

export function AddEditModal({ editKey, onSave, onClose, error, saving }: {
  editKey: AK | null; onSave: (f: FormState) => void; onClose: () => void;
  error?: string | null; saving?: boolean;
}) {
  const [form, setForm] = useState<FormState>({
    label: editKey?.label ?? "",
    provider: editKey?.provider ?? "gemini",
    rawKey: "",
    limit: String(editKey?.limit ?? 15000),
  });
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const baseInp: React.CSSProperties = {
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)",
    color: "#ECECF0",
  };

  function focus(e: React.FocusEvent<HTMLInputElement>) {
    e.target.style.borderColor = "rgba(0,214,143,0.4)";
    e.target.style.boxShadow = "0 0 0 3px rgba(0,214,143,0.07)";
  }

  function blur(e: React.FocusEvent<HTMLInputElement>) {
    e.target.style.borderColor = "rgba(255,255,255,0.08)";
    e.target.style.boxShadow = "none";
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      style={{ background: "rgba(0,0,0,0.72)", backdropFilter: "blur(4px)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl p-5 sm:p-6 max-h-[92vh] overflow-y-auto"
        style={{ background: "#141416", border: "1px solid rgba(255,255,255,0.09)", boxShadow: "0 32px 80px rgba(0,0,0,0.6)" }}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-sm font-semibold text-zinc-100">{editKey ? "Edit Key" : "Add API Key"}</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg transition-colors hover:bg-white/5">
            <X size={16} color="#52525B" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Label</label>
            <input className="w-full px-3 py-2 rounded-lg text-sm outline-none transition-all"
              style={baseInp}
              placeholder="Production Primary"
              value={form.label}
              onChange={e => setForm({ ...form, label: e.target.value })}
              onFocus={focus} onBlur={blur}
              autoFocus />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Provider</label>
            <div className="flex gap-2">
              {(["gemini"] as Provider[]).map(p => (
                <button key={p} onClick={() => setForm({ ...form, provider: p })}
                  className="flex-1 py-2 rounded-lg text-xs font-medium transition-all"
                  style={{
                    color: form.provider === p ? P[p].color : "#52525B",
                    background: form.provider === p ? P[p].bg : "rgba(255,255,255,0.03)",
                    border: form.provider === p ? `1px solid ${P[p].color}30` : "1px solid rgba(255,255,255,0.06)",
                  }}>
                  {P[p].name}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">API Key</label>
            <div className="relative">
              <input className="w-full px-3 py-2 pr-9 rounded-lg text-sm font-mono outline-none transition-all"
                style={baseInp}
                type={showKey ? "text" : "password"}
                placeholder={editKey ? "Leave blank to keep current" : "sk-… or AIza…"}
                value={form.rawKey}
                onChange={e => setForm({ ...form, rawKey: e.target.value })}
                onFocus={focus} onBlur={blur} />
              <button onClick={() => setShowKey(!showKey)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded transition-colors hover:bg-white/5">
                {showKey ? <EyeOff size={14} color="#52525B" /> : <Eye size={14} color="#52525B" />}
              </button>
            </div>
            <p className="mt-1.5 text-[11px] text-zinc-600 flex items-center gap-1.5">
              <Shield size={10} color="#52525B" className="shrink-0" />
              Encrypted before storage — never shown in plaintext
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Daily Limit</label>
            <input className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none transition-all"
              style={baseInp}
              type="number"
              placeholder="15000"
              value={form.limit}
              onChange={e => setForm({ ...form, limit: e.target.value })}
              onFocus={focus} onBlur={blur} />
          </div>
        </div>

        {error && (
          <div className="mt-4 flex items-start gap-2 px-3 py-2 rounded-lg text-xs"
            style={{ background: "rgba(239,68,68,0.08)", color: "#EF4444", border: "1px solid rgba(239,68,68,0.2)" }}>
            <AlertTriangle size={13} className="shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <div className="flex gap-2 mt-6">
          <button onClick={onClose}
            className="flex-1 py-2 rounded-lg text-sm font-medium transition-colors"
            style={{ background: "rgba(255,255,255,0.04)", color: "#71717A", border: "1px solid rgba(255,255,255,0.06)" }}>
            Cancel
          </button>
          <button onClick={() => !saving && onSave(form)} disabled={saving}
            className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-1.5"
            style={{ background: "#00D68F", color: "#0A0A0B", boxShadow: "0 0 16px rgba(0,214,143,0.3)", opacity: saving ? 0.7 : 1 }}
            onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 0 28px rgba(0,214,143,0.55)")}
            onMouseLeave={e => (e.currentTarget.style.boxShadow = "0 0 16px rgba(0,214,143,0.3)")}>
            {saving && <Loader2 size={13} className="animate-spin" />}
            {editKey ? "Save Changes" : "Add Key"}
          </button>
        </div>
      </div>
    </div>
  );
}
