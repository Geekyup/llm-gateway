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
      <div className="rounded-lg p-4" style={{ background: "var(--field)", border: "1px solid color-mix(in srgb, var(--ink) 10.2%, transparent)" }}>
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-ink mb-1">App tokens</h2>
            <p className="text-xs text-ink-3 leading-relaxed max-w-md">
              Each token lets one app call your key pool. Keypool handles rotation and
              failover behind it — your app just sends a bearer token to{" "}
              <code className="px-1 py-0.5 rounded font-mono" style={{ background: "color-mix(in srgb, var(--ink) 8.4%, transparent)" }}>/v1/chat/completions</code>.
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          <input
            className="flex-1 px-3 py-2 rounded-lg text-sm outline-none min-w-0"
            style={{ background: "color-mix(in srgb, var(--ink) 4.2%, transparent)", border: "1px solid color-mix(in srgb, var(--ink) 8.4%, transparent)", color: "var(--ink)" }}
            placeholder="my-web-app"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <button
            onClick={handleCreate}
            disabled={creating || !label.trim()}
            className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition-all shrink-0"
            style={{ background: "var(--accent)", color: "var(--on-accent)", opacity: creating || !label.trim() ? 0.6 : 1 }}
          >
            {creating ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            Create token
          </button>
        </div>
        <p className="mt-2 text-[12px] text-ink-3">
          Name it after the app that will use it, like <span className="font-mono">web-app</span> or <span className="font-mono">ios-client</span>.
        </p>

        {error && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg text-xs" style={{ background: "color-mix(in srgb, var(--bad) 8%, transparent)", color: "var(--bad)", border: "1px solid color-mix(in srgb, var(--bad) 20%, transparent)" }}>
            <AlertTriangle size={13} className="shrink-0" /> {error}
          </div>
        )}

        {freshToken && (
          <div className="mt-4 p-3 rounded-lg" style={{ background: "color-mix(in srgb, var(--ok) 7%, transparent)", border: "1px solid color-mix(in srgb, var(--ok) 35%, transparent)" }}>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-ink flex items-center gap-1.5">
                <CheckCircle2 size={13} color="var(--ok)" />
                Token created — copy it now, you won't see it again
              </p>
              <button
                onClick={() => setFreshToken(null)}
                aria-label="Dismiss"
                className="p-1 rounded-md transition-colors hover:bg-ink/5 shrink-0"
              >
                <X size={13} color="var(--ink-3)" />
              </button>
            </div>
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
              <code className="flex-1 px-2 py-1.5 rounded text-xs font-mono break-all" style={{ background: "var(--background)", color: "var(--ok)", border: "1px solid color-mix(in srgb, var(--ok) 30%, transparent)" }}>
                {freshToken.plaintext}
              </code>
              <button onClick={() => copy(freshToken.plaintext)} className="px-2.5 py-1.5 rounded text-xs font-medium shrink-0" style={{ background: "color-mix(in srgb, var(--ink) 8.4%, transparent)", color: "var(--ink)" }}>
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>

            <p className="mt-3 text-[12px] text-ink-3">
              Connect your app — pick a language and copy the snippet:
            </p>
            <CodeSnippetTabs token={freshToken.plaintext} baseUrl={API_BASE_URL} />
          </div>
        )}
      </div>

      <div className="rounded-lg overflow-hidden" style={{ background: "var(--card)", border: "1px solid color-mix(in srgb, var(--ink) 6%, transparent)" }}>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={18} className="animate-spin" color="var(--ink-4)" />
          </div>
        ) : tokens.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-sm text-ink-2 mb-1">Create your first token</p>
            <p className="text-xs text-ink-3">It'll show up here once you generate one above.</p>
          </div>
        ) : (
          <>
            <div className="sm:hidden">
              {tokens.map((t, i) => (
                <div key={t.id} className="px-4 py-3" style={{ borderBottom: i < tokens.length - 1 ? "1px solid color-mix(in srgb, var(--ink) 4.2%, transparent)" : "none" }}>
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <span className="text-sm text-ink truncate">{t.label}</span>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => toggle(t)}
                        aria-label={t.is_active ? `Revoke token ${t.label}` : `Reactivate token ${t.label}`}
                        title={t.is_active ? "Revoke" : "Reactivate"}
                        className="p-1.5 rounded-md transition-colors hover:bg-ink/5"
                      >
                        <Ban size={13} color={t.is_active ? "var(--warn)" : "var(--ok)"} />
                      </button>
                      <button
                        onClick={() => remove(t.id)}
                        aria-label={`Delete token ${t.label}`}
                        title="Delete"
                        className="p-1.5 rounded-md transition-colors hover:bg-ink/5"
                      >
                        <Trash2 size={13} color="var(--bad)" />
                      </button>
                    </div>
                  </div>
                  <div className="font-mono text-xs text-ink-3 mb-2">{t.token_preview}</div>
                  <div className="flex items-center justify-between">
                    <span
                      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[12px] font-mono font-medium"
                      style={
                        t.is_active
                          ? { color: "var(--ok)", background: "color-mix(in srgb, var(--ok) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--ok) 25%, transparent)" }
                          : { color: "var(--ink-3)", background: "color-mix(in srgb, var(--ink-3) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--ink-3) 20%, transparent)" }
                      }
                    >
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: t.is_active ? "var(--ok)" : "var(--ink-3)" }} />
                      {t.is_active ? "active" : "revoked"}
                    </span>
                    <span className="text-[12px] text-ink-3">
                      {t.last_used_at ? new Date(t.last_used_at).toLocaleString() : "Never used"}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <table className="hidden sm:table w-full text-sm">
              <thead>
                <tr className="text-left text-[12px] tracking-wide text-ink-3" style={{ borderBottom: "1px solid color-mix(in srgb, var(--ink) 6%, transparent)" }}>
                  <th className="px-4 py-2.5 font-medium">App name</th>
                  <th className="px-4 py-2.5 font-medium">Token</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Last request</th>
                  <th className="px-4 py-2.5 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {tokens.map((t) => (
                  <tr key={t.id} style={{ borderBottom: "1px solid color-mix(in srgb, var(--ink) 4.2%, transparent)" }}>
                    <td className="px-4 py-3 text-ink">{t.label}</td>
                    <td className="px-4 py-3 font-mono text-xs text-ink-3">{t.token_preview}</td>
                    <td className="px-4 py-3">
                      <span
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[12px] font-mono font-medium"
                        style={
                          t.is_active
                            ? { color: "var(--ok)", background: "color-mix(in srgb, var(--ok) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--ok) 25%, transparent)" }
                            : { color: "var(--ink-3)", background: "color-mix(in srgb, var(--ink-3) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--ink-3) 20%, transparent)" }
                        }
                      >
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: t.is_active ? "var(--ok)" : "var(--ink-3)" }} />
                        {t.is_active ? "active" : "revoked"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-ink-3">
                      {t.last_used_at ? new Date(t.last_used_at).toLocaleString() : "Never used"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1.5">
                        <button
                          onClick={() => toggle(t)}
                          aria-label={t.is_active ? `Revoke token ${t.label}` : `Reactivate token ${t.label}`}
                          title={t.is_active ? "Revoke" : "Reactivate"}
                          className="p-1.5 rounded-md transition-colors hover:bg-ink/5"
                        >
                          <Ban size={13} color={t.is_active ? "var(--warn)" : "var(--ok)"} />
                        </button>
                        <button
                          onClick={() => remove(t.id)}
                          aria-label={`Delete token ${t.label}`}
                          title="Delete"
                          className="p-1.5 rounded-md transition-colors hover:bg-ink/5"
                        >
                          <Trash2 size={13} color="var(--bad)" />
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