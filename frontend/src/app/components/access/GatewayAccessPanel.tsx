import { useCallback, useEffect, useState } from "react";
import { Ban, Plus, Loader2, AlertTriangle, CheckCircle2, Trash2, X } from "lucide-react";
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
      <div className="rounded-xl p-4" style={{ background: "#1C1C1F", border: "1px solid rgba(255,255,255,0.1)" }}>
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-zinc-100 mb-1">App tokens</h2>
            <p className="text-xs text-zinc-500 leading-relaxed max-w-md">
              Each token lets one app call your key pool. Keypool handles rotation and
              failover behind it — your app just sends a bearer token to{" "}
              <code className="px-1 py-0.5 rounded font-mono" style={{ background: "rgba(255,255,255,0.08)" }}>/v1/chat/completions</code>.
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          <input
            className="flex-1 px-3 py-2 rounded-lg text-sm outline-none min-w-0"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#ECECF0" }}
            placeholder="my-web-app"
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
            Create token
          </button>
        </div>
        <p className="mt-2 text-[11px] text-zinc-600">
          Name it after the app that will use it, like <span className="font-mono">web-app</span> or <span className="font-mono">ios-client</span>.
        </p>

        {error && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg text-xs" style={{ background: "rgba(239,68,68,0.08)", color: "#EF4444", border: "1px solid rgba(239,68,68,0.2)" }}>
            <AlertTriangle size={13} className="shrink-0" /> {error}
          </div>
        )}

        {freshToken && (
          <div className="mt-4 p-3 rounded-lg" style={{ background: "rgba(0,214,143,0.07)", border: "1px solid rgba(0,214,143,0.35)" }}>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-zinc-200 flex items-center gap-1.5">
                <CheckCircle2 size={13} color="#00D68F" />
                Token created — copy it now, you won't see it again
              </p>
              <button
                onClick={() => setFreshToken(null)}
                aria-label="Dismiss"
                className="p-1 rounded-md transition-colors hover:bg-white/5 shrink-0"
              >
                <X size={13} color="#71717A" />
              </button>
            </div>
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
              <code className="flex-1 px-2 py-1.5 rounded text-xs font-mono break-all" style={{ background: "#0A0A0B", color: "#22E3A8", border: "1px solid rgba(0,214,143,0.3)" }}>
                {freshToken.plaintext}
              </code>
              <button onClick={() => copy(freshToken.plaintext)} className="px-2.5 py-1.5 rounded text-xs font-medium shrink-0" style={{ background: "rgba(255,255,255,0.08)", color: "#ECECF0" }}>
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>

            <p className="mt-3 text-[11px] text-zinc-500">
              Connect your app — pick a language and copy the snippet:
            </p>
            <CodeSnippetTabs token={freshToken.plaintext} baseUrl={API_BASE_URL} />
          </div>
        )}
      </div>

      <div className="rounded-xl overflow-hidden" style={{ background: "#141416", border: "1px solid rgba(255,255,255,0.06)" }}>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={18} className="animate-spin" color="#52525B" />
          </div>
        ) : tokens.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-sm text-zinc-400 mb-1">Create your first token</p>
            <p className="text-xs text-zinc-600">It'll show up here once you generate one above.</p>
          </div>
        ) : (
          <>
            <div className="sm:hidden">
              {tokens.map((t, i) => (
                <div key={t.id} className="px-4 py-3" style={{ borderBottom: i < tokens.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none" }}>
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <span className="text-sm text-zinc-200 truncate">{t.label}</span>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => toggle(t)}
                        aria-label={t.is_active ? `Revoke token ${t.label}` : `Reactivate token ${t.label}`}
                        title={t.is_active ? "Revoke" : "Reactivate"}
                        className="p-1.5 rounded-md transition-colors hover:bg-white/5"
                      >
                        <Ban size={13} color={t.is_active ? "#F59E0B" : "#00D68F"} />
                      </button>
                      <button
                        onClick={() => remove(t.id)}
                        aria-label={`Delete token ${t.label}`}
                        title="Delete"
                        className="p-1.5 rounded-md transition-colors hover:bg-white/5"
                      >
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
                      {t.last_used_at ? new Date(t.last_used_at).toLocaleString() : "Never used"}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <table className="hidden sm:table w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-zinc-600" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                  <th className="px-4 py-2.5 font-medium">App name</th>
                  <th className="px-4 py-2.5 font-medium">Token</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Last request</th>
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
                      {t.last_used_at ? new Date(t.last_used_at).toLocaleString() : "Never used"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1.5">
                        <button
                          onClick={() => toggle(t)}
                          aria-label={t.is_active ? `Revoke token ${t.label}` : `Reactivate token ${t.label}`}
                          title={t.is_active ? "Revoke" : "Reactivate"}
                          className="p-1.5 rounded-md transition-colors hover:bg-white/5"
                        >
                          <Ban size={13} color={t.is_active ? "#F59E0B" : "#00D68F"} />
                        </button>
                        <button
                          onClick={() => remove(t.id)}
                          aria-label={`Delete token ${t.label}`}
                          title="Delete"
                          className="p-1.5 rounded-md transition-colors hover:bg-white/5"
                        >
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