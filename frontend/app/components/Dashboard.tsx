import { useState, useEffect, useCallback } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { TopBar } from "./layout/TopBar";
import { MetricCards } from "./dashboard/MetricCards";
import { KeysTable } from "./dashboard/KeysTable";
import { AddEditModal } from "./modals/AddEditModal";
import { KeyDetailDrawer } from "./modals/KeyDetailDrawer";
import { LiveMonitor } from "./monitor/LiveMonitor";
import { GatewayAccessPanel } from "./access/GatewayAccessPanel";
import { api, streamEvents, ApiError } from "../lib/api";
import { toAK, toLR } from "../lib/mappers";
import type { AK, LR, View, PF, FormState } from "../types";

export function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [keys, setKeys]           = useState<AK[]>([]);
  const [loading, setLoading]     = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [view, setView]           = useState<View>("dashboard");
  const [filter, setFilter]       = useState<PF>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editId, setEditId]       = useState<string | null>(null);
  const [addOpen, setAddOpen]     = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving]       = useState(false);
  const [reqs, setReqs]           = useState<LR[]>([]);
  const [now, setNow]             = useState(Date.now());

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

  // Live request feed via SSE, plus an initial snapshot so the monitor isn't empty on load.
  useEffect(() => {
    api.recentEvents(50).then(events => setReqs(events.map(toLR))).catch(() => {});
    const stop = streamEvents(
      evt => setReqs(prev => [...prev.slice(-99), toLR(evt)]),
      () => {}
    );
    return stop;
  }, []);

  const selectedKey = selectedId ? (keys.find(k => k.id === selectedId) ?? null) : null;
  const editKey     = editId     ? (keys.find(k => k.id === editId)     ?? null) : null;
  const operational = keys.some(k => k.status === "active");

  async function handleSave(form: FormState) {
    setSaving(true);
    setFormError(null);
    try {
      if (editId) {
        await api.updateKey(Number(editId), {
          label: form.label || undefined,
          daily_limit: Number(form.limit) || undefined,
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
    const key = keys.find(k => k.id === id);
    if (!key) return;
    setKeys(prev => prev.map(k => k.id === id
      ? { ...k, status: k.status === "disabled" ? "active" : "disabled" }
      : k));
    try {
      await api.updateKey(Number(id), { status: key.status === "disabled" ? "active" : "disabled" });
      await refreshKeys();
    } catch {
      await refreshKeys(); // revert optimistic update on failure
    }
  }

  async function resetCooldown(id: string) {
    try {
      await api.resetCooldown(Number(id));
      await refreshKeys();
    } catch {
      // surfaced via loadError on next refresh
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

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "#0A0A0B", fontFamily: "Inter, sans-serif" }}>
      <TopBar view={view} onView={setView} onAdd={() => setAddOpen(true)} operational={operational} onLogout={onLogout} />

      <main className="flex-1 px-3 sm:px-6 py-4 sm:py-5 w-full max-w-[1400px] mx-auto space-y-4">
        {loadError && (
          <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs"
            style={{ background: "rgba(239,68,68,0.08)", color: "#EF4444", border: "1px solid rgba(239,68,68,0.2)" }}>
            <AlertTriangle size={13} className="shrink-0" />
            Could not reach the API: {loadError}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 size={20} className="animate-spin" color="#52525B" />
          </div>
        ) : view === "dashboard" ? (
          <>
            <MetricCards keys={keys} />
            <KeysTable
              keys={keys} filter={filter} onFilter={setFilter} now={now}
              onSelect={setSelectedId}
              onEdit={id => { setEditId(id); setSelectedId(null); }}
              onToggle={toggleKey}
            />
          </>
        ) : view === "monitor" ? (
          <LiveMonitor reqs={reqs} now={now} />
        ) : (
          <GatewayAccessPanel />
        )}
      </main>

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
          keyData={selectedKey} now={now}
          onClose={() => setSelectedId(null)}
          onDisable={() => toggleKey(selectedKey.id)}
          onReset={() => resetCooldown(selectedKey.id)}
          onDelete={() => deleteKey(selectedKey.id)}
        />
      )}
    </div>
  );
}
