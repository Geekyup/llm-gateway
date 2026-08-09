import { useCallback, useEffect, useState } from "react";
import { Shield, Plus, Loader2, AlertTriangle, CheckCircle2, Power, Trash2 } from "lucide-react";
import { api, ApiError, API_BASE_URL, type GatewayTokenRead, type GatewayTokenCreated } from "../../lib/api";
import { CodeSnippetTabs } from "../CodeSnippetTabs";

export function GatewayAccessPanel() {
  const [tokens, setTokens] = useState<GatewayTokenRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [label, setLabel] = useState("");
  const [freshToken, setFreshToken] = useState<GatewayTokenCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await api.listGatewayTokens();
      setTokens(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load tokens");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function handleCreate() {
    if (!label.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const result = await api.createGatewayToken(label.trim());
      setFreshToken(result);
      setLabel("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create token");
    } finally {
      setCreating(false);
    }
  }

  async function toggle(t: GatewayTokenRead) {
    setTokens((prev) => prev.map((x) => (x.id === t.id ? { ...x, is_active: !x.is_active } : x)));
    try {
      if (t.is_active) await api.revokeGatewayToken(t.id);
      else await api.activateGatewayToken(t.id);
    } catch {
      await refresh();
    }
  }

  async function remove(id: number) {
    setTokens((prev) => prev.filter((x) => x.id !== id));
    try {
      await api.deleteGatewayToken(id);
    } catch {
      await refresh();
    }
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl p-4" style={{ background: "#141416", border: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center gap-2 mb-1">
          <Shield size={14} color="#00D68F" />
          <h2 className="text-sm font-semibold text-zinc-100">Gateway Access Tokens</h2>
        </div>
        <p className="text-xs text-zinc-500 leading-relaxed mb-4">
          One token gives access to the entire key pool on the Dashboard tab.
          Your app sends requests to <code className="px-1 py-0.5 rounded font-mono" style={{ background: "rgba(255,255,255,0.06)" }}>/v1/gemini/...</code> with
          this token in the <code className="px-1 py-0.5 rounded font-mono" style={{ background: "rgba(255,255,255,0.06)" }}>Authorization: Bearer</code> header —
          which key from the pool actually gets used is up to the gateway; your app doesn't need to know or care about rotation and failover.
        </p>

        <div className="flex flex-col sm:flex-row gap-2">
          <input
            className="flex-1 px-3 py-2 rounded-lg text-sm outline-none min-w-0"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#ECECF0" }}
            placeholder="Label, e.g. kitroom-backend"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <button
            onClick={handleCreate}
            disabled={creating || !label.trim()}
            className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition-all shrink-0"
            style={{ background: "#00D68F", color: "#0A0A0B", opacity: creating || !label.trim() ? 0.6 : 1 }}
          >
            {creating ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            Generate Token
          </button>
        </div>

        {error && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg text-xs" style={{ background: "rgba(239,68,68,0.08)", color: "#EF4444", border: "1px solid rgba(239,68,68,0.2)" }}>
            <AlertTriangle size={13} className="shrink-0" /> {error}
          </div>
        )}

        {freshToken && (
          <div className="mt-4 p-3 rounded-lg" style={{ background: "rgba(0,214,143,0.06)", border: "1px solid rgba(0,214,143,0.25)" }}>
            <p className="text-xs font-medium text-zinc-200 mb-2 flex items-center gap-1.5">
              <CheckCircle2 size={13} color="#00D68F" />
              Token created — save it now, it won't be shown again
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-2 py-1.5 rounded text-xs font-mono break-all" style={{ background: "#0A0A0B", color: "#00D68F", border: "1px solid rgba(0,214,143,0.2)" }}>
                {freshToken.plaintext}
              </code>
              <button onClick={() => copy(freshToken.plaintext)} className="px-2.5 py-1.5 rounded text-xs font-medium shrink-0" style={{ background: "rgba(255,255,255,0.06)", color: "#ECECF0" }}>
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>

            <p className="mt-3 text-[11px] text-zinc-500">
              Ready-to-use integration code — just drop it into your project:
            </p>
            <CodeSnippetTabs token={freshToken.plaintext} baseUrl={API_BASE_URL} />

            <button onClick={() => setFreshToken(null)} className="mt-3 text-[11px] text-zinc-500 hover:text-zinc-300">
              Close
            </button>
          </div>
        )}
      </div>

      <div className="rounded-xl overflow-hidden" style={{ background: "#141416", border: "1px solid rgba(255,255,255,0.06)" }}>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={18} className="animate-spin" color="#52525B" />
          </div>
        ) : tokens.length === 0 ? (
          <div className="py-16 text-center text-xs text-zinc-600">No tokens yet — generate your first one above.</div>
        ) : (
          <>
            <div className="sm:hidden">
              {tokens.map((t, i) => (
                <div key={t.id} className="px-4 py-3" style={{ borderBottom: i < tokens.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none" }}>
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <span className="text-sm text-zinc-200 truncate">{t.label}</span>
                    <div className="flex items-center gap-1 shrink-0">
                      <button onClick={() => toggle(t)} className="p-1.5 rounded-md transition-colors hover:bg-white/5" title={t.is_active ? "Revoke" : "Reactivate"}>
                        <Power size={13} color={t.is_active ? "#F59E0B" : "#00D68F"} />
                      </button>
                      <button onClick={() => remove(t.id)} className="p-1.5 rounded-md transition-colors hover:bg-white/5" title="Delete">
                        <Trash2 size={13} color="#EF4444" />
                      </button>
                    </div>
                  </div>
                  <div className="font-mono text-xs text-zinc-500 mb-2">{t.token_preview}</div>
                  <div className="flex items-center justify-between">
                    <span
                      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-mono font-medium"
                      style={
                        t.is_active
                          ? { color: "#00D68F", background: "rgba(0,214,143,0.1)", border: "1px solid rgba(0,214,143,0.25)" }
                          : { color: "#71717A", background: "rgba(113,113,122,0.1)", border: "1px solid rgba(113,113,122,0.2)" }
                      }
                    >
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: t.is_active ? "#00D68F" : "#71717A" }} />
                      {t.is_active ? "active" : "revoked"}
                    </span>
                    <span className="text-[11px] text-zinc-500">
                      {t.last_used_at ? new Date(t.last_used_at).toLocaleString() : "never"}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <table className="hidden sm:table w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-zinc-600" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                  <th className="px-4 py-2.5 font-medium">Label</th>
                  <th className="px-4 py-2.5 font-medium">Token</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Last used</th>
                  <th className="px-4 py-2.5 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {tokens.map((t) => (
                  <tr key={t.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                    <td className="px-4 py-3 text-zinc-200">{t.label}</td>
                    <td className="px-4 py-3 font-mono text-xs text-zinc-500">{t.token_preview}</td>
                    <td className="px-4 py-3">
                      <span
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-mono font-medium"
                        style={
                          t.is_active
                            ? { color: "#00D68F", background: "rgba(0,214,143,0.1)", border: "1px solid rgba(0,214,143,0.25)" }
                            : { color: "#71717A", background: "rgba(113,113,122,0.1)", border: "1px solid rgba(113,113,122,0.2)" }
                        }
                      >
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: t.is_active ? "#00D68F" : "#71717A" }} />
                        {t.is_active ? "active" : "revoked"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-500">
                      {t.last_used_at ? new Date(t.last_used_at).toLocaleString() : "never"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1.5">
                        <button onClick={() => toggle(t)} className="p-1.5 rounded-md transition-colors hover:bg-white/5" title={t.is_active ? "Revoke" : "Reactivate"}>
                          <Power size={13} color={t.is_active ? "#F59E0B" : "#00D68F"} />
                        </button>
                        <button onClick={() => remove(t.id)} className="p-1.5 rounded-md transition-colors hover:bg-white/5" title="Delete">
                          <Trash2 size={13} color="#EF4444" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}
