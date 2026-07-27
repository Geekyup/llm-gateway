import { useState } from "react";
import { KeyRound, AlertTriangle, Loader2 } from "lucide-react";
import { api, setAdminToken, clearAdminToken } from "../../lib/api";

export function LoginGate({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [token, setToken] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!token.trim()) return;
    setChecking(true);
    setError(null);
    setAdminToken(token.trim());
    const ok = await api.verifyToken();
    setChecking(false);
    if (ok) {
      onAuthenticated();
    } else {
      clearAdminToken();
      setError("Invalid admin token, or the API is unreachable.");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4"
      style={{ background: "#0A0A0B", fontFamily: "Inter, sans-serif" }}>
      <div className="w-full max-w-sm rounded-2xl p-6"
        style={{ background: "#141416", border: "1px solid rgba(255,255,255,0.09)", boxShadow: "0 32px 80px rgba(0,0,0,0.6)" }}>
        <div className="flex items-center gap-2.5 mb-6">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: "rgba(0,214,143,0.12)", border: "1px solid rgba(0,214,143,0.2)" }}>
            <KeyRound size={16} color="#00D68F" />
          </div>
          <div>
            <p className="font-mono text-sm font-medium text-zinc-100">keypool</p>
            <p className="text-[11px] text-zinc-600">Sign in to the admin dashboard</p>
          </div>
        </div>

        <label className="block text-xs font-medium text-zinc-400 mb-1.5">Admin API Token</label>
        <input
          className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none transition-all"
          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#ECECF0" }}
          type="password"
          placeholder="ADMIN_API_KEY from your .env"
          value={token}
          onChange={e => setToken(e.target.value)}
          onKeyDown={e => e.key === "Enter" && submit()}
          autoFocus
        />
        {error && (
          <p className="mt-2 text-xs flex items-center gap-1.5" style={{ color: "#EF4444" }}>
            <AlertTriangle size={12} className="shrink-0" /> {error}
          </p>
        )}

        <button onClick={submit} disabled={checking || !token.trim()}
          className="w-full mt-4 py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-1.5"
          style={{ background: "#00D68F", color: "#0A0A0B", opacity: checking || !token.trim() ? 0.6 : 1 }}>
          {checking && <Loader2 size={14} className="animate-spin" />}
          {checking ? "Checking…" : "Continue"}
        </button>

        <p className="mt-4 text-[11px] text-zinc-600 leading-relaxed">
          This is the same value as <span className="font-mono text-zinc-500">ADMIN_API_KEY</span> in
          the backend's <span className="font-mono text-zinc-500">.env</span>. It's stored only in
          this browser's local storage.
        </p>
      </div>
    </div>
  );
}
