import { useCallback, useEffect, useState } from "react";
import { Loader2, AlertTriangle, CheckCircle2 } from "lucide-react";
import { api, ApiError, type UserRead } from "./lib/api";
import { toAK } from "./lib/domain";
import type { AK, FormState, PF, SF, View } from "./types";
import { Sidebar } from "./components/layout/Sidebar";
import { MobileSidebarDrawer } from "./components/layout/MobileSidebarDrawer";
import { TopBar } from "./components/layout/TopBar";
import { MetricCards } from "./components/dashboard/MetricCards";
import { KeysTable } from "./components/dashboard/KeysTable";
import { AddEditModal } from "./components/dashboard/AddEditModal";
import { KeyDetailDrawer } from "./components/dashboard/KeyDetailDrawer";
import { ActivityPage } from "./components/activity/ActivityPage";
import { ChatPlayground } from "./components/playground/ChatPlayground";
import { GatewayAccessPanel } from "./components/access/GatewayAccessPanel";

export function Dashboard({ user, onLogout }: { user: UserRead | null; onLogout: () => void }) {
  const [keys, setKeys] = useState<AK[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [filter, setFilter] = useState<PF>("all");
  const [statusFilter, setStatusFilter] = useState<SF>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [checkingIds, setCheckingIds] = useState<Set<string>>(new Set());
  const [resettingIds, setResettingIds] = useState<Set<string>>(new Set());
  const [checkResults, setCheckResults] = useState<{ toastId: string; keyId: string; ok: boolean; detail: string | null }[]>([]);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const refreshKeys = useCallback(async () => {
    try {
      const data = await api.listKeys();
      setKeys(data.map(toAK));
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to reach the API");
      if (err instanceof ApiError && err.status === 401) onLogout();
    } finally {
      setLoading(false);
    }
  }, [onLogout]);

  useEffect(() => {
    refreshKeys();
    const id = setInterval(refreshKeys, 15000);
    return () => clearInterval(id);
  }, [refreshKeys]);

  const selectedKey = selectedId ? keys.find((k) => k.id === selectedId) ?? null : null;
  const editKey = editId ? keys.find((k) => k.id === editId) ?? null : null;
  const operational = keys.some((k) => k.status === "active");

  async function handleSave(form: FormState) {
    setSaving(true);
    setFormError(null);
    try {
      if (editId) {
        await api.updateKey(Number(editId), {
          label: form.label || undefined,
          daily_limit: Number(form.limit) || undefined,
          model: form.model.trim() || null,
        });
        setEditId(null);
      } else {
        if (!form.rawKey.trim()) {
          setFormError("API key is required.");
          setSaving(false);
          return;
        }
        await api.createKey({
          label: form.label || "New Key",
          provider: form.provider,
          raw_key: form.rawKey.trim(),
          daily_limit: Number(form.limit) || 15000,
          model: form.model.trim() || null,
        });
        setAddOpen(false);
      }
      await refreshKeys();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Request failed");
    } finally {
      setSaving(false);
    }
  }

  async function toggleKey(id: string) {
    const key = keys.find((k) => k.id === id);
    if (!key) return;
    setKeys((prev) => prev.map((k) => (k.id === id ? { ...k, status: k.status === "disabled" ? "active" : "disabled" } : k)));
    try {
      await api.updateKey(Number(id), { status: key.status === "disabled" ? "active" : "disabled" });
      await refreshKeys();
    } catch {
      await refreshKeys();
    }
  }

  async function resetCooldown(id: string) {
    setResettingIds((prev) => new Set(prev).add(id));
    try {
      await api.resetCooldown(Number(id));
      await refreshKeys();
    } catch {
    } finally {
      setResettingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  async function deleteKey(id: string) {
    setSelectedId(null);
    try {
      await api.deleteKey(Number(id));
      await refreshKeys();
    } catch {
      await refreshKeys();
    }
  }

  async function checkKey(id: string) {
    setCheckingIds((prev) => new Set(prev).add(id));
    const toastId = `${id}-${Date.now()}`;
    try {
      const result = await api.checkKey(Number(id));
      setCheckResults((prev) => [...prev, { toastId, keyId: id, ok: result.ok, detail: result.detail }]);
      await refreshKeys();
    } catch (err) {
      setCheckResults((prev) => [
        ...prev,
        { toastId, keyId: id, ok: false, detail: err instanceof ApiError ? err.message : "Check failed — couldn't reach the API" },
      ]);
    } finally {
      setCheckingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      setTimeout(() => setCheckResults((prev) => prev.filter((r) => r.toastId !== toastId)), 5000);
    }
  }

  return (
    <div className="min-h-screen flex" style={{ background: "var(--background)" }}>
      <Sidebar view={view} onView={setView} />
      {menuOpen && <MobileSidebarDrawer view={view} onView={setView} onClose={() => setMenuOpen(false)} />}

      <div className="flex-1 flex flex-col min-w-0">
        <TopBar onAdd={() => setAddOpen(true)} operational={operational} onLogout={onLogout} userEmail={user?.email} onMenu={() => setMenuOpen(true)} />

        <main className="flex-1 px-3 sm:px-6 py-4 sm:py-5 w-full max-w-[1400px] mx-auto space-y-4">
          {loadError && (
            <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs" style={{ background: "rgba(239,68,68,0.08)", color: "var(--destructive)", border: "1px solid rgba(239,68,68,0.2)" }}>
              <AlertTriangle size={13} className="shrink-0" />
              Could not reach the API: {loadError}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-24">
              <Loader2 size={20} className="animate-spin" color="var(--muted-foreground)" />
            </div>
          ) : (
            <>
              {view === "dashboard" && (
                <div key="dashboard" className="space-y-4 animate-in fade-in slide-in-from-bottom-1 duration-300 ease-out">
                  <MetricCards keys={keys} />
                  <KeysTable
                    keys={keys}
                    filter={filter}
                    onFilter={setFilter}
                    statusFilter={statusFilter}
                    onStatusFilter={setStatusFilter}
                    now={now}
                    onSelect={setSelectedId}
                    onEdit={(id) => { setEditId(id); setSelectedId(null); }}
                    onToggle={toggleKey}
                    onCheck={checkKey}
                    checkingIds={checkingIds}
                  />
                </div>
              )}
              {view === "activity" && (
                <div key="activity" className="animate-in fade-in slide-in-from-bottom-1 duration-300 ease-out">
                  <ActivityPage />
                </div>
              )}
              <div key="playground" className={view === "playground" ? "animate-in fade-in slide-in-from-bottom-1 duration-300 ease-out" : "hidden"}>
                <ChatPlayground keys={keys} active={view === "playground"} />
              </div>
              {view === "access" && (
                <div key="access" className="animate-in fade-in slide-in-from-bottom-1 duration-300 ease-out">
                  <GatewayAccessPanel />
                </div>
              )}
            </>
          )}
        </main>
      </div>

      {checkResults.length > 0 && (
        <div className="fixed bottom-4 right-4 z-[60] flex flex-col-reverse gap-2 pointer-events-none">
          {checkResults.map((r) => (
            <div
              key={r.toastId}
              className="flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg animate-in fade-in slide-in-from-bottom-2 duration-250 ease-out pointer-events-auto"
              style={{ background: "var(--muted)", border: `1px solid ${r.ok ? "rgba(0,214,143,0.3)" : "rgba(239,68,68,0.3)"}`, maxWidth: 360 }}
            >
              {r.ok ? <CheckCircle2 size={16} color="var(--primary)" className="shrink-0" /> : <AlertTriangle size={16} color="var(--destructive)" className="shrink-0" />}
              <div className="min-w-0">
                <div className="text-xs font-medium text-zinc-200">{r.ok ? "Key is working" : "Key check failed"}</div>
                {r.detail && <div className="text-[11px] text-zinc-500 truncate">{r.detail}</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {(addOpen || !!editId) && (
        <AddEditModal
          editKey={editId ? editKey : null}
          onSave={handleSave}
          onClose={() => { setAddOpen(false); setEditId(null); setFormError(null); }}
          error={formError}
          saving={saving}
        />
      )}

      {selectedKey && (
        <KeyDetailDrawer
          keyData={selectedKey}
          now={now}
          onClose={() => setSelectedId(null)}
          onDisable={() => toggleKey(selectedKey.id)}
          onReset={() => resetCooldown(selectedKey.id)}
          onDelete={() => deleteKey(selectedKey.id)}
          onCheck={() => checkKey(selectedKey.id)}
          checking={checkingIds.has(selectedKey.id)}
          resetting={resettingIds.has(selectedKey.id)}
        />
      )}
    </div>
  );
}