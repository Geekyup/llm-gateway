import { useState, useEffect, useCallback, useRef } from "react";
import {
  Plus, Eye, EyeOff, X, Activity, RefreshCw, Trash2, Edit2,
  Power, Clock, ArrowRight, CheckCircle2, Shield, AlertTriangle,
  LayoutDashboard, KeyRound, Zap, LogOut, Loader2, Stethoscope, ChevronDown, Search,
  Sparkles, Route,
} from "lucide-react";
import { AreaChart, Area, XAxis, Tooltip, ResponsiveContainer } from "recharts";
import {
  api, streamEvents, getAccessToken, getRefreshToken, setTokenPair, clearTokenPair,
  startGoogleLogin,
  ApiError, type ApiKeyRead, type RequestEvent as ApiRequestEvent,
  type GatewayTokenRead, type GatewayTokenCreated, type UserRead, type ModelOption,
  API_BASE_URL,
} from "./lib/api";
import { CodeSnippetTabs } from "./components/CodeSnippetTabs";

type Status = "active" | "cooldown" | "exhausted" | "disabled";
type Provider = "gemini" | "openrouter";
type View = "dashboard" | "monitor" | "access";
type PF = "all" | Provider;

interface AK {
  id: string; label: string; provider: Provider; status: Status;
  masked: string; used: number; limit: number; model: string | null;
  cooldownUntil?: number; lastUsed?: number; created: number; updated: number;
}

interface LR {
  id: string; provider: string; keyLabel: string;
  code: number; latency: number; ts: number;
  chain?: { label: string; code: number }[];
  totalTokens: number | null;
}

interface FormState { label: string; provider: Provider; rawKey: string; limit: string; model: string }

function toAK(k: ApiKeyRead): AK {
  return {
    id: String(k.id),
    label: k.label,
    provider: k.provider,
    status: k.status,
    masked: `#${k.id}`,
    used: k.requests_today,
    limit: k.daily_limit,
    model: k.model,
    cooldownUntil: k.cooldown_until ? new Date(k.cooldown_until).getTime() : undefined,
    lastUsed: k.last_used_at ? new Date(k.last_used_at).getTime() : undefined,
    created: new Date(k.created_at).getTime(),
    updated: new Date(k.updated_at).getTime(),
  };
}

function toLR(e: ApiRequestEvent): LR {
  return {
    id: `${e.request_id}-${e.attempt}`,
    provider: e.provider,
    keyLabel: e.key_label ?? "—",
    code: e.upstream_status ?? (e.outcome === "no_keys" ? 503 : 0),
    latency: e.latency_ms ?? 0,
    ts: new Date(e.timestamp).getTime(),
    totalTokens: e.total_tokens,
  };
}

const S: Record<Status, { text: string; color: string; bg: string; bd: string }> = {
  active:    { text: "Active",    color: "#00D68F", bg: "rgba(0,214,143,0.08)",  bd: "rgba(0,214,143,0.22)"  },
  cooldown:  { text: "Cooldown",  color: "#F59E0B", bg: "rgba(245,158,11,0.08)", bd: "rgba(245,158,11,0.22)" },
  exhausted: { text: "Exhausted", color: "#EF4444", bg: "rgba(239,68,68,0.08)",  bd: "rgba(239,68,68,0.22)"  },
  disabled:  { text: "Disabled",  color: "#52525B", bg: "rgba(82,82,91,0.08)",   bd: "rgba(82,82,91,0.18)"   },
};

const P: Record<string, { name: string; color: string; bg: string; Icon: typeof Sparkles }> = {
  gemini:     { name: "Gemini",     color: "#4F8EF7", bg: "rgba(79,142,247,0.1)",  Icon: Sparkles },
  openrouter: { name: "OpenRouter", color: "#A78BFA", bg: "rgba(167,139,250,0.1)", Icon: Route    },
};
function providerMeta(provider: string) {
  return P[provider] ?? { name: provider, color: "#71717A", bg: "rgba(113,113,122,0.1)", Icon: KeyRound };
}

// Нейтральная (белая/серая) палитра — используется только в Provider-переключателе модалки AddEditModal,
// чтобы не менять цвета бейджей провайдера по всему остальному интерфейсу.
const PN: Record<Provider, { name: string; Icon: typeof Sparkles }> = {
  gemini:     { name: "Gemini",     Icon: Sparkles },
  openrouter: { name: "OpenRouter", Icon: Route    },
};

function rel(ts: number, now: number) {
  const d = now - ts;
  if (d < 60000)   return `${Math.floor(d / 1000)}s ago`;
  if (d < 3600000) return `${Math.floor(d / 60000)}m ago`;
  if (d < 86400000)return `${Math.floor(d / 3600000)}h ago`;
  return `${Math.floor(d / 86400000)}d ago`;
}

function cd(until: number, now: number) {
  const d = until - now;
  if (d <= 0) return "Ready";
  const h = Math.floor(d / 3600000);
  const m = Math.floor((d % 3600000) / 60000);
  const s = Math.floor((d % 60000) / 1000);
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function SBadge({ status }: { status: Status }) {
  const s = S[status];
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-mono font-medium whitespace-nowrap transition-colors duration-300"
      style={{ color: s.color, background: s.bg, border: `1px solid ${s.bd}` }}>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 transition-colors duration-300 ${status === "active" ? "animate-pulse" : ""}`}
        style={{ background: s.color }} />
      {s.text}
    </span>
  );
}

function PBadge({ provider }: { provider: string }) {
  const p = providerMeta(provider);
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium max-w-full truncate justify-self-start"
      style={{ color: p.color, background: p.bg }}>
      {p.name}
    </span>
  );
}

function UBar({ used, limit, status }: { used: number; limit: number; status: Status }) {
  const pct = limit > 0 ? Math.min(100, Math.max(0, (used / limit) * 100)) : 0;
  const color = S[status].color;
  return (
    <div className="min-w-[140px]">
      <div className="flex justify-between mb-1.5">
        <span className="text-[11px] font-mono text-zinc-300">{used.toLocaleString()}</span>
        <span className="text-[11px] font-mono text-zinc-600">/ {limit.toLocaleString()}</span>
      </div>
      <div className="h-[3px] rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color, boxShadow: pct > 80 ? `0 0 8px ${color}60` : "none" }} />
      </div>
    </div>
  );
}

function CircP({ used, limit, color }: { used: number; limit: number; color: string }) {
  const r = 48, circ = 2 * Math.PI * r, pct = limit > 0 ? Math.min(1, Math.max(0, used / limit)) : 0, dash = pct * circ;
  return (
    <div className="relative inline-flex items-center justify-center shrink-0">
      <svg width={120} height={120} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={60} cy={60} r={r} fill="none" strokeWidth={7} stroke="rgba(255,255,255,0.05)" />
        <circle cx={60} cy={60} r={r} fill="none" strokeWidth={7} stroke={color}
          strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 6px ${color}70)`, transition: "stroke-dasharray 0.5s ease" }} />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-xl font-mono font-medium" style={{ color }}>{Math.round(pct * 100)}%</span>
        <span className="text-[10px] text-zinc-600 font-mono">used</span>
      </div>
    </div>
  );
}

function TopBar({ view, onView, onAdd, operational, onLogout, userEmail }: {
  view: View; onView: (v: View) => void; onAdd: () => void; operational: boolean; onLogout: () => void;
  userEmail?: string | null;
}) {
  return (
    <header className="flex flex-col md:grid md:grid-cols-[1fr_auto_1fr] md:items-center md:h-14 shrink-0 px-3 sm:px-6 gap-2 md:gap-5 py-2.5 md:py-0"
      style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", background: "#0A0A0B" }}>
      <div className="flex items-center justify-between md:justify-self-start gap-2.5 md:gap-5">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
            style={{ background: "rgba(0,214,143,0.12)", border: "1px solid rgba(0,214,143,0.2)" }}>
            <KeyRound size={14} color="#00D68F" />
          </div>
          <span className="font-mono text-sm font-medium tracking-tight text-zinc-100 truncate">keypool</span>
          <span className="hidden sm:inline text-[10px] font-mono px-1.5 py-0.5 rounded shrink-0"
            style={{ color: "#52525B", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
            v0.4.1
          </span>
        </div>
        <div className="flex md:hidden items-center gap-2">
          <span className="w-2 h-2 rounded-full"
            style={{
              background: operational ? "#00D68F" : "#EF4444",
              boxShadow: operational ? "0 0 7px rgba(0,214,143,0.8)" : "0 0 7px rgba(239,68,68,0.8)",
            }} />
        </div>
      </div>

      <nav className="flex gap-0.5 overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0 md:justify-self-center">
        {(["dashboard", "monitor", "access"] as View[]).map(v => (
          <button key={v} onClick={() => onView(v)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all shrink-0 whitespace-nowrap"
            style={{
              color: view === v ? "#ECECF0" : "#52525B",
              background: view === v ? "rgba(255,255,255,0.07)" : "transparent",
              border: view === v ? "1px solid rgba(255,255,255,0.08)" : "1px solid transparent",
            }}>
            {v === "dashboard" ? <LayoutDashboard size={12} /> : v === "monitor" ? <Activity size={12} /> : <Shield size={12} />}
            {v === "dashboard" ? "Dashboard" : v === "monitor" ? "Live Monitor" : "Gateway Access"}
          </button>
        ))}
      </nav>

      <div className="flex items-center justify-between md:justify-self-end gap-4">
        <div className="hidden md:flex items-center gap-2">
          <span className="w-2 h-2 rounded-full"
            style={{
              background: operational ? "#00D68F" : "#EF4444",
              boxShadow: operational ? "0 0 7px rgba(0,214,143,0.8)" : "0 0 7px rgba(239,68,68,0.8)",
            }} />
          <span className="text-xs font-mono" style={{ color: operational ? "#00D68F" : "#EF4444" }}>
            {operational ? "Operational" : "Degraded"}
          </span>
        </div>
        <button onClick={onAdd}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all active:scale-95"
          style={{ background: "#00D68F", color: "#0A0A0B", boxShadow: "0 0 16px rgba(0,214,143,0.3)" }}
          onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 0 28px rgba(0,214,143,0.55)")}
          onMouseLeave={e => (e.currentTarget.style.boxShadow = "0 0 16px rgba(0,214,143,0.3)")}>
          <Plus size={13} /> Add Key
        </button>
        {userEmail && (
          <span className="hidden lg:inline text-[11px] font-mono truncate max-w-[160px]" style={{ color: "#52525B" }}>
            {userEmail}
          </span>
        )}
        <button onClick={onLogout} title="Sign out"
          className="p-1.5 rounded-lg transition-colors hover:bg-white/5">
          <LogOut size={14} color="#52525B" />
        </button>
      </div>
    </header>
  );
}

function MetricCards({ keys }: { keys: AK[] }) {
  const total  = keys.length;
  const active = keys.filter(k => k.status === "active").length;
  const cool   = keys.filter(k => k.status === "cooldown").length;
  const req    = keys.reduce((a, k) => a + k.used, 0);

  const cards = [
    { label: "Total Keys",       val: String(total),           color: "#71717A", Icon: KeyRound,      glow: false },
    { label: "Active Keys",      val: String(active),          color: "#00D68F", Icon: CheckCircle2,  glow: true  },
    { label: "Requests Today",   val: req.toLocaleString(),    color: "#4F8EF7", Icon: Zap,           glow: false },
    { label: "Keys in Cooldown", val: String(cool),            color: "#F59E0B", Icon: Clock,         glow: false },
  ] as const;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((c, i) => (
        <div key={c.label}
          className="rounded-xl p-4 transition-transform duration-200 hover:-translate-y-0.5 animate-in fade-in slide-in-from-bottom-1"
          style={{
            background: "#111113",
            border: "1px solid rgba(255,255,255,0.06)",
            boxShadow: c.glow ? "0 0 24px rgba(0,214,143,0.05)" : "none",
            animationDuration: "300ms",
            animationDelay: `${i * 40}ms`,
            animationFillMode: "backwards",
          }}>
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium">{c.label}</span>
            <div className="w-6 h-6 rounded-md flex items-center justify-center"
              style={{ background: `${c.color}14` }}>
              <c.Icon size={12} color={c.color} />
            </div>
          </div>
          <span className="text-2xl font-mono font-medium" style={{ color: c.glow ? c.color : "#ECECF0" }}>
            {c.val}
          </span>
        </div>
      ))}
    </div>
  );
}

function KeysTable({ keys, filter, onFilter, onSelect, onEdit, onToggle, onCheck, checkingIds, now }: {
  keys: AK[]; filter: PF; onFilter: (f: PF) => void; now: number;
  onSelect: (id: string) => void; onEdit: (id: string) => void; onToggle: (id: string) => void;
  onCheck: (id: string) => void; checkingIds: Set<string>;
}) {
  const filtered = filter === "all" ? keys : keys.filter(k => k.provider === filter);

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.06)" }}>
      <div className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: "#0F0F11" }}>
        <span className="text-xs font-medium text-zinc-400">API Keys</span>
        <div className="flex gap-1">
          {(["all", "gemini", "openrouter"] as PF[]).map(f => (
            <button key={f} onClick={() => onFilter(f)}
              className="px-2.5 py-1 rounded-md text-[11px] font-medium capitalize transition-all"
              style={{
                color: filter === f ? "#ECECF0" : "#52525B",
                background: filter === f ? "rgba(255,255,255,0.08)" : "transparent",
                border: filter === f ? "1px solid rgba(255,255,255,0.1)" : "1px solid transparent",
              }}>
              {f}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="px-4 py-16 text-center" style={{ background: "#111113" }}>
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <KeyRound size={18} color="#3F3F46" />
            </div>
            <p className="text-sm text-zinc-500">No keys found</p>
            <p className="text-xs text-zinc-600">Add your first API key to get started</p>
          </div>
        </div>
      ) : (
        <>
          <div className="sm:hidden" style={{ background: "#111113" }}>
            {filtered.map((k, i) => (
              <div key={k.id} className="px-4 py-3.5 transition-colors active:bg-white/[0.03] cursor-pointer"
                style={{ borderBottom: i < filtered.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none" }}
                onClick={() => onSelect(k.id)}>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-zinc-200 leading-none truncate">{k.label}</div>
                    <div className="text-[11px] font-mono text-zinc-600 mt-1 truncate">
                      {k.masked}{k.model && <span className="text-zinc-700"> · {k.model}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0" onClick={e => e.stopPropagation()}>
                    <button onClick={() => onCheck(k.id)} disabled={checkingIds.has(k.id)}
                      className="p-1.5 rounded-md transition-colors hover:bg-white/5 disabled:opacity-50" title="Test key">
                      {checkingIds.has(k.id)
                        ? <Loader2 size={13} color="#71717A" className="animate-spin" />
                        : <Stethoscope size={13} color="#71717A" />}
                    </button>
                    <button onClick={() => onEdit(k.id)}
                      className="p-1.5 rounded-md transition-colors hover:bg-white/5" title="Edit">
                      <Edit2 size={13} color="#71717A" />
                    </button>
                    <button onClick={() => onToggle(k.id)}
                      className="p-1.5 rounded-md transition-colors hover:bg-white/5"
                      title={k.status === "disabled" ? "Enable" : "Disable"}>
                      <Power size={13} color={k.status === "disabled" ? "#ECECF0" : "#71717A"} />
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-2 mb-2.5">
                  <PBadge provider={k.provider} />
                  <SBadge status={k.status} />
                </div>
                <UBar used={k.used} limit={k.limit} status={k.status} />
                <div className="flex items-center justify-between mt-2.5">
                  <span className="text-[11px] text-zinc-600">
                    Last used: <span className="font-mono text-zinc-500">{k.lastUsed ? rel(k.lastUsed, now) : "—"}</span>
                  </span>
                  {k.cooldownUntil ? (
                    <span className="text-[11px] font-mono" style={{ color: "#F59E0B" }}>
                      {cd(k.cooldownUntil, now)}
                    </span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          <div className="hidden sm:block overflow-x-auto" style={{ background: "#111113" }}>
            <table className="w-full min-w-[760px]">
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                  {["Label", "Provider", "Status", "Usage", "Cooldown", "Last Used", ""].map((h, i) => (
                    <th key={i}
                      className="px-4 py-2.5 text-left text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((k, i) => (
                  <tr key={k.id} className="group cursor-pointer transition-colors hover:bg-white/[0.02]"
                    style={{ borderBottom: i < filtered.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none" }}
                    onClick={() => onSelect(k.id)}>
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-zinc-200 leading-none">{k.label}</div>
                      <div className="text-[11px] font-mono text-zinc-600 mt-1">
                        {k.masked}{k.model && <span className="text-zinc-700"> · {k.model}</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3"><PBadge provider={k.provider} /></td>
                    <td className="px-4 py-3"><SBadge status={k.status} /></td>
                    <td className="px-4 py-3"><UBar used={k.used} limit={k.limit} status={k.status} /></td>
                    <td className="px-4 py-3">
                      {k.cooldownUntil ? (
                        <span className="text-xs font-mono" style={{ color: "#F59E0B" }}>
                          {cd(k.cooldownUntil, now)}
                        </span>
                      ) : (
                        <span className="text-xs text-zinc-700">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-mono text-zinc-500">
                        {k.lastUsed ? rel(k.lastUsed, now) : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={e => e.stopPropagation()}>
                        <button onClick={() => onCheck(k.id)} disabled={checkingIds.has(k.id)}
                          className="p-1.5 rounded-md transition-colors hover:bg-white/5 disabled:opacity-50" title="Test key">
                          {checkingIds.has(k.id)
                            ? <Loader2 size={13} color="#71717A" className="animate-spin" />
                            : <Stethoscope size={13} color="#71717A" />}
                        </button>
                        <button onClick={() => onEdit(k.id)}
                          className="p-1.5 rounded-md transition-colors hover:bg-white/5" title="Edit">
                          <Edit2 size={13} color="#71717A" />
                        </button>
                        <button onClick={() => onToggle(k.id)}
                          className="p-1.5 rounded-md transition-colors hover:bg-white/5"
                          title={k.status === "disabled" ? "Enable" : "Disable"}>
                          <Power size={13} color={k.status === "disabled" ? "#ECECF0" : "#71717A"} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function AddEditModal({ editKey, onSave, onClose, error, saving }: {
  editKey: AK | null; onSave: (f: FormState) => void; onClose: () => void;
  error?: string | null; saving?: boolean;
}) {
  const [form, setForm] = useState<FormState>({
    label: editKey?.label ?? "",
    provider: editKey?.provider ?? "gemini",
    rawKey: "",
    limit: String(editKey?.limit ?? 15000),
    model: editKey?.model ?? "",
  });
  const [showKey, setShowKey] = useState(false);
  const [providerPickerOpen, setProviderPickerOpen] = useState(false);
  const [modelOptions, setModelOptions] = useState<ModelOption[] | null>(null);
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [modelLoading, setModelLoading] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);
  const [modelSearch, setModelSearch] = useState("");

  async function fetchModels() {
    if (!form.rawKey.trim()) {
      setModelError("Enter the API key above to look up models for it.");
      return;
    }
    setModelLoading(true);
    setModelError(null);
    try {
      const models = await api.listModels(form.provider, form.rawKey.trim());
      setModelOptions(models);
      setModelPickerOpen(true);
    } catch (err) {
      setModelError(err instanceof ApiError ? err.message : "Couldn't reach the provider to list models.");
    } finally {
      setModelLoading(false);
    }
  }

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const providerPickerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!providerPickerOpen) return;
    const h = (e: MouseEvent) => {
      if (providerPickerRef.current && !providerPickerRef.current.contains(e.target as Node)) {
        setProviderPickerOpen(false);
      }
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [providerPickerOpen]);

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

  const overlayMouseDownOnSelf = useRef(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
      style={{ background: "rgba(0,0,0,0.72)", backdropFilter: "blur(4px)" }}
      onMouseDown={e => { overlayMouseDownOnSelf.current = e.target === e.currentTarget; }}
      onMouseUp={e => {
        if (overlayMouseDownOnSelf.current && e.target === e.currentTarget) onClose();
        overlayMouseDownOnSelf.current = false;
      }}>
      <div className="w-full sm:max-w-md rounded-2xl p-5 sm:p-6 max-h-[92vh] overflow-y-auto animate-in fade-in zoom-in-95 slide-in-from-bottom-2 duration-200 ease-out"
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
            <div className="relative" ref={providerPickerRef}>
              <button onClick={() => setProviderPickerOpen(o => !o)}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm outline-none transition-all"
                style={{ ...baseInp, borderColor: providerPickerOpen ? "rgba(0,214,143,0.4)" : baseInp.border as string }}>
                <span className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-md flex items-center justify-center shrink-0"
                    style={{ background: "rgba(255,255,255,0.06)" }}>
                    {(() => { const Icon = PN[form.provider].Icon; return <Icon size={12} color="#ECECF0" />; })()}
                  </span>
                  <span className="font-medium text-zinc-100">{PN[form.provider].name}</span>
                </span>
                <ChevronDown size={14} color="#52525B"
                  style={{ transform: providerPickerOpen ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }} />
              </button>

              {providerPickerOpen && (
                <div className="absolute z-10 mt-1.5 w-full rounded-lg shadow-lg animate-in fade-in slide-in-from-top-1 duration-150 overflow-hidden"
                  style={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.1)" }}>
                  {(["gemini", "openrouter"] as Provider[]).map(p => {
                    const meta = PN[p];
                    const Icon = meta.Icon;
                    const active = form.provider === p;
                    return (
                      <button key={p}
                        onClick={() => {
                          setForm({ ...form, provider: p, model: "" });
                          setModelOptions(null);
                          setModelError(null);
                          setProviderPickerOpen(false);
                        }}
                        className="w-full flex items-center gap-2.5 text-left px-3 py-2.5 text-sm transition-colors hover:bg-white/5"
                        style={{ background: active ? "rgba(255,255,255,0.04)" : "transparent" }}>
                        <span className="w-5 h-5 rounded-md flex items-center justify-center shrink-0" style={{ background: "rgba(255,255,255,0.06)" }}>
                          <Icon size={12} color="#ECECF0" />
                        </span>
                        <span className="flex-1" style={{ color: active ? "#ECECF0" : "#A1A1AA" }}>{meta.name}</span>
                        {active && <CheckCircle2 size={14} color="#ECECF0" className="shrink-0" />}
                      </button>
                    );
                  })}
                </div>
              )}
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
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Model <span className="text-zinc-600 font-normal">(optional)</span>
            </label>
            <p className="text-[11px] text-zinc-600 mb-2">
              Pin this key to one model — it will still be used for requests to that model, plus any request
              that doesn't specify a model. Leave unset to serve requests for any model.
            </p>

            {form.model ? (
              <div className="flex items-center justify-between px-3 py-2 rounded-lg text-sm"
                style={{ ...baseInp, background: "rgba(0,214,143,0.06)", borderColor: "rgba(0,214,143,0.2)" }}>
                <span className="font-mono text-zinc-200 truncate">{form.model}</span>
                <button onClick={() => setForm({ ...form, model: "" })}
                  className="shrink-0 ml-2 p-0.5 rounded transition-colors hover:bg-white/10">
                  <X size={13} color="#71717A" />
                </button>
              </div>
            ) : (
              <div>
                <button onClick={() => { fetchModels(); setModelSearch(""); }} disabled={modelLoading}
                  className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.98] disabled:active:scale-100 disabled:opacity-60"
                  style={{ background: "rgba(255,255,255,0.04)", color: "#A1A1AA", border: "1px solid rgba(255,255,255,0.08)" }}>
                  {modelLoading ? <Loader2 size={13} className="animate-spin" /> : <ChevronDown size={13} />}
                  {modelLoading ? "Loading models…" : "Select Model"}
                </button>

                {modelPickerOpen && modelOptions && (
                  <div className="relative z-10 mt-1.5 w-full rounded-lg shadow-lg animate-in fade-in slide-in-from-top-1 duration-150 overflow-hidden"
                    style={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.1)" }}>
                    {modelOptions.length > 5 && (
                      <div className="p-1.5 sticky top-0" style={{ background: "#1C1C1E", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                        <div className="relative">
                          <Search size={12} color="#52525B" className="absolute left-2 top-1/2 -translate-y-1/2" />
                          <input
                            autoFocus
                            value={modelSearch}
                            onChange={e => setModelSearch(e.target.value)}
                            placeholder="Search models…"
                            className="w-full pl-6.5 pr-2 py-1.5 rounded-md text-xs outline-none"
                            style={{ background: "rgba(255,255,255,0.05)", color: "#ECECF0", border: "1px solid transparent" }}
                          />
                        </div>
                      </div>
                    )}
                    <div className="max-h-40 overflow-y-auto">
                      {(() => {
                        const q = modelSearch.trim().toLowerCase();
                        const filtered = q
                          ? modelOptions.filter(m => m.label.toLowerCase().includes(q) || m.id.toLowerCase().includes(q))
                          : modelOptions;
                        if (modelOptions.length === 0) {
                          return <p className="px-3 py-2.5 text-xs text-zinc-500">No models available for this key.</p>;
                        }
                        if (filtered.length === 0) {
                          return <p className="px-3 py-2.5 text-xs text-zinc-500">No models match "{modelSearch}".</p>;
                        }
                        return filtered.map(m => (
                          <button key={m.id}
                            onClick={() => { setForm({ ...form, model: m.id }); setModelPickerOpen(false); setModelSearch(""); }}
                            className="w-full text-left px-3 py-2 text-xs transition-colors hover:bg-white/5">
                            <div className="text-zinc-200 truncate">{m.label}</div>
                            {m.label !== m.id && <div className="text-[10px] font-mono text-zinc-600 truncate">{m.id}</div>}
                          </button>
                        ));
                      })()}
                    </div>
                  </div>
                )}
              </div>
            )}
            {modelError && <p className="mt-1.5 text-[11px]" style={{ color: "#EF4444" }}>{modelError}</p>}
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
            className="flex-1 py-2 rounded-lg text-sm font-medium transition-colors active:scale-95"
            style={{ background: "rgba(255,255,255,0.04)", color: "#71717A", border: "1px solid rgba(255,255,255,0.06)" }}>
            Cancel
          </button>
          <button onClick={() => !saving && onSave(form)} disabled={saving}
            className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-1.5 active:scale-95 disabled:active:scale-100"
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

function KeyDetailDrawer({ keyData, now, onClose, onDisable, onReset, onDelete, onCheck, checking, resetting }: {
  keyData: AK; now: number;
  onClose: () => void; onDisable: () => void; onReset: () => void; onDelete: () => void;
  onCheck: () => void; checking: boolean; resetting: boolean;
}) {
  const s = S[keyData.status];
  const [chartMode, setChartMode] = useState<"requests" | "tokens">("requests");
  const [chartData, setChartData] = useState<{ h: string; r: number }[] | null>(null);
  const [chartError, setChartError] = useState(false);
  const [tokenData, setTokenData] = useState<{ h: string; r: number; prompt: number; completion: number }[] | null>(null);
  const [tokenError, setTokenError] = useState(false);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setChartData(null);
    setChartError(false);
    setTokenData(null);
    setTokenError(false);
    setChartMode("requests");
    api.hourlyUsage(Number(keyData.id))
      .then(res => {
        if (cancelled) return;
        setChartData(res.points.map(p => ({ h: `${p.hour}h`, r: p.requests })));
      })
      .catch(() => {
        if (!cancelled) setChartError(true);
      });
    return () => { cancelled = true; };
  }, [keyData.id]);

  useEffect(() => {
    if (chartMode !== "tokens" || tokenData !== null || tokenError) return;
    let cancelled = false;
    api.hourlyTokenUsage(Number(keyData.id))
      .then(res => {
        if (cancelled) return;
        setTokenData(res.points.map(p => ({ h: `${p.hour}h`, r: p.total_tokens, prompt: p.prompt_tokens, completion: p.completion_tokens })));
      })
      .catch(() => {
        if (!cancelled) setTokenError(true);
      });
    return () => { cancelled = true; };
  }, [chartMode, keyData.id, tokenData, tokenError]);

  const meta = [
    { label: "Provider",   val: P[keyData.provider].name,                                           mono: false },
    { label: "Model",      val: keyData.model ?? "Any (unpinned)",                                    mono: true  },
    { label: "Masked Key", val: keyData.masked,                                                      mono: true  },
    { label: "Created",    val: new Date(keyData.created).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }), mono: false },
    { label: "Updated",    val: new Date(keyData.updated).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }), mono: false },
    { label: "Last Used",  val: keyData.lastUsed ? rel(keyData.lastUsed, now) : "—",                mono: false },
    { label: "Cooldown",   val: keyData.cooldownUntil ? cd(keyData.cooldownUntil, now) : "—",       mono: true  },
  ];

  return (
    <>
      <div className="fixed inset-0 z-40 animate-in fade-in duration-200" onClick={onClose}
        style={{ background: "rgba(0,0,0,0.5)", backdropFilter: "blur(2px)" }} />
      <aside className="fixed right-0 top-0 bottom-0 z-50 w-full sm:w-96 flex flex-col overflow-y-auto animate-in slide-in-from-right duration-300 ease-out"
        style={{ background: "#111113", borderLeft: "1px solid rgba(255,255,255,0.07)", boxShadow: "-24px 0 60px rgba(0,0,0,0.4)" }}>
        <div className="flex items-start justify-between p-5"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">{keyData.label}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[11px] font-mono text-zinc-600">{keyData.masked}</span>
              <PBadge provider={keyData.provider} />
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg transition-colors hover:bg-white/5 shrink-0 mt-0.5">
            <X size={16} color="#52525B" />
          </button>
        </div>

        <div className="p-5 space-y-5 flex-1">
          <div className="flex items-center gap-4">
            <CircP used={keyData.used} limit={keyData.limit} color={s.color} />
            <div className="space-y-3">
              <SBadge status={keyData.status} />
              <div>
                <p className="text-[11px] text-zinc-600 mb-0.5">Daily quota</p>
                <p className="text-sm font-mono text-zinc-200">{keyData.limit.toLocaleString()} req</p>
              </div>
              <div>
                <p className="text-[11px] text-zinc-600 mb-0.5">Remaining</p>
                <p className="text-sm font-mono" style={{ color: s.color }}>
                  {Math.max(0, keyData.limit - keyData.used).toLocaleString()} req
                </p>
              </div>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2.5">
              <p className="text-[10px] text-zinc-600 uppercase tracking-widest font-semibold">
                {chartMode === "requests" ? "Hourly Usage Today" : "Hourly Tokens Today"}
              </p>
              <div className="flex gap-0.5 rounded-md p-0.5" style={{ background: "rgba(255,255,255,0.03)" }}>
                {(["requests", "tokens"] as const).map(m => (
                  <button key={m} onClick={() => setChartMode(m)}
                    className="px-2 py-0.5 rounded text-[10px] font-medium transition-all"
                    style={{
                      color: chartMode === m ? "#ECECF0" : "#52525B",
                      background: chartMode === m ? "rgba(255,255,255,0.07)" : "transparent",
                    }}>
                    {m === "requests" ? "Requests" : "Tokens"}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ height: 88 }} className="flex items-center justify-center">
              {chartMode === "requests" ? (
                chartError ? (
                  <p className="text-[11px] text-zinc-600">Couldn't load usage data</p>
                ) : chartData === null ? (
                  <Loader2 size={16} className="animate-spin" color="#52525B" />
                ) : chartData.every(p => p.r === 0) ? (
                  <p className="text-[11px] text-zinc-600">No requests yet today</p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 4, right: 0, left: -32, bottom: 0 }}>
                      <defs>
                        <linearGradient id="agrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor={s.color} stopOpacity={0.22} />
                          <stop offset="95%" stopColor={s.color} stopOpacity={0}    />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="h"
                        tick={{ fontSize: 9, fill: "#52525B", fontFamily: "JetBrains Mono, monospace" }}
                        tickLine={false} axisLine={false} interval={3} />
                      <Tooltip
                        contentStyle={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }}
                        labelStyle={{ color: "#71717A" }} itemStyle={{ color: s.color }}
                        formatter={(v: number) => [v.toLocaleString(), "req"]} />
                      <Area type="monotone" dataKey="r" stroke={s.color} strokeWidth={1.5}
                        fill="url(#agrad)" dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                )
              ) : (
                tokenError ? (
                  <p className="text-[11px] text-zinc-600">Couldn't load token data</p>
                ) : tokenData === null ? (
                  <Loader2 size={16} className="animate-spin" color="#52525B" />
                ) : tokenData.every(p => p.r === 0) ? (
                  <p className="text-[11px] text-zinc-600">No token usage yet today</p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={tokenData} margin={{ top: 4, right: 0, left: -32, bottom: 0 }}>
                      <defs>
                        <linearGradient id="tgrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="#A78BFA" stopOpacity={0.22} />
                          <stop offset="95%" stopColor="#A78BFA" stopOpacity={0}    />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="h"
                        tick={{ fontSize: 9, fill: "#52525B", fontFamily: "JetBrains Mono, monospace" }}
                        tickLine={false} axisLine={false} interval={3} />
                      <Tooltip
                        contentStyle={{ background: "#1C1C1E", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 11, fontFamily: "JetBrains Mono, monospace" }}
                        labelStyle={{ color: "#71717A" }}
                        formatter={(v: number, name: string, p: { payload?: { prompt: number; completion: number } }) => {
                          if (name !== "r") return [v, name];
                          const pt = p.payload;
                          return [
                            pt ? `${v.toLocaleString()} (${pt.prompt.toLocaleString()} in / ${pt.completion.toLocaleString()} out)` : v.toLocaleString(),
                            "tokens",
                          ];
                        }} />
                      <Area type="monotone" dataKey="r" stroke="#A78BFA" strokeWidth={1.5}
                        fill="url(#tgrad)" dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                )
              )}
            </div>
          </div>

          <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.06)" }}>
            {meta.map((m, i) => (
              <div key={m.label} className="flex items-center justify-between px-3.5 py-2.5"
                style={{
                  borderBottom: i < meta.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none",
                  background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.01)",
                }}>
                <span className="text-[11px] text-zinc-600">{m.label}</span>
                <span className={`text-[11px] text-zinc-300 ${m.mono ? "font-mono" : ""}`}>{m.val}</span>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <button onClick={onCheck} disabled={checking}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.97] disabled:active:scale-100 disabled:opacity-50"
              style={{ background: "rgba(0,214,143,0.08)", color: "#00D68F", border: "1px solid rgba(0,214,143,0.16)" }}>
              {checking ? <Loader2 size={12} className="animate-spin" /> : <Stethoscope size={12} />}
              {checking ? "Checking..." : "Test Key"}
            </button>
            <button onClick={onReset} disabled={resetting}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.97] disabled:active:scale-100 disabled:opacity-50"
              style={{ background: "rgba(79,142,247,0.08)", color: "#4F8EF7", border: "1px solid rgba(79,142,247,0.16)" }}>
              {resetting ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              {resetting ? "Resetting..." : "Reset Cooldown"}
            </button>
            <button onClick={onDisable}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.97]"
              style={{ background: "rgba(255,255,255,0.04)", color: "#71717A", border: "1px solid rgba(255,255,255,0.07)" }}>
              <Power size={12} />
              {keyData.status === "disabled" ? "Enable Key" : "Disable Key"}
            </button>
            <button onClick={onDelete}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all active:scale-[0.97]"
              style={{ background: "rgba(239,68,68,0.07)", color: "#EF4444", border: "1px solid rgba(239,68,68,0.16)" }}>
              <Trash2 size={12} /> Delete Key
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

function LiveMonitor({ reqs, now }: { reqs: LR[]; now: number }) {
  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.06)" }}>
      <div className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: "#0F0F11" }}>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: "#00D68F", boxShadow: "0 0 6px rgba(0,214,143,0.7)" }} />
          <span className="text-xs font-medium text-zinc-400">Live Request Feed</span>
        </div>
        <span className="text-[11px] font-mono text-zinc-600">{reqs.length} captured</span>
      </div>

      <div style={{ background: "#111113" }}>
        <div className="hidden sm:grid px-4 py-2"
          style={{ gridTemplateColumns: "72px 88px 1fr 52px 64px 56px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
          {["Time", "Provider", "Key / Chain", "Status", "Tokens", "Latency"].map(h => (
            <span key={h} className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest">{h}</span>
          ))}
        </div>

        {reqs.map((r, i) => {
          const cColor = r.code === 200 ? "#00D68F" : r.code === 429 ? "#F59E0B" : "#EF4444";
          const isNewest = i === 0;
          return (
            <div key={r.id} className={isNewest ? "animate-in fade-in slide-in-from-top-2 duration-300 ease-out" : undefined}>
              <div className="sm:hidden px-4 py-2.5"
                style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2 min-w-0">
                    <PBadge provider={r.provider} />
                    <span className="text-[11px] font-mono text-zinc-300 truncate">{r.keyLabel}</span>
                  </div>
                  <span className="text-[11px] font-mono px-1.5 py-0.5 rounded shrink-0"
                    style={{ color: cColor, background: `${cColor}12`, border: `1px solid ${cColor}22` }}>
                    {r.code}
                  </span>
                </div>
                {r.chain && r.chain.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
                    {r.chain.map((c, i) => (
                      <div key={`${c.label}-${c.code}-${i}`} className="flex items-center gap-1.5 shrink-0">
                        <span className="text-[11px] font-mono text-zinc-500 truncate max-w-[100px]">{c.label}</span>
                        <span className="text-[11px] font-mono px-1 py-0.5 rounded shrink-0"
                          style={{ color: "#F59E0B", background: "rgba(245,158,11,0.1)" }}>{c.code}</span>
                        <ArrowRight size={10} color="#3F3F46" className="shrink-0" />
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono text-zinc-600">
                    {new Date(r.ts).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </span>
                  <div className="flex items-center gap-2">
                    {r.totalTokens != null && (
                      <span className="text-[11px] font-mono text-zinc-500">{r.totalTokens.toLocaleString()} tok</span>
                    )}
                    <span className="text-[11px] font-mono text-zinc-600">{r.latency}ms</span>
                  </div>
                </div>
              </div>

              <div className="hidden sm:grid items-center px-4 py-2.5 transition-colors"
                style={{
                  gridTemplateColumns: "72px 88px 1fr 52px 64px 56px",
                  borderBottom: "1px solid rgba(255,255,255,0.03)",
                }}
                onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.015)")}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                <span className="text-[11px] font-mono text-zinc-600">
                  {new Date(r.ts).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                </span>
                <PBadge provider={r.provider} />
                <div className="flex items-center gap-1.5 min-w-0">
                  {r.chain?.map((c, i) => (
                    <div key={`${c.label}-${c.code}-${i}`} className="flex items-center gap-1.5 shrink-0">
                      <span className="text-[11px] font-mono text-zinc-500 truncate max-w-[100px]">{c.label}</span>
                      <span className="text-[11px] font-mono px-1 py-0.5 rounded shrink-0"
                        style={{ color: "#F59E0B", background: "rgba(245,158,11,0.1)" }}>{c.code}</span>
                      <ArrowRight size={10} color="#3F3F46" className="shrink-0" />
                    </div>
                  ))}
                  <span className="text-[11px] font-mono text-zinc-300 truncate">{r.keyLabel}</span>
                </div>
                <span className="text-[11px] font-mono px-1.5 py-0.5 rounded justify-self-start"
                  style={{ color: cColor, background: `${cColor}12`, border: `1px solid ${cColor}22` }}>
                  {r.code}
                </span>
                <span className="text-[11px] font-mono text-zinc-500">
                  {r.totalTokens != null ? r.totalTokens.toLocaleString() : "—"}
                </span>
                <span className="text-[11px] font-mono text-zinc-600 justify-self-end">{r.latency}ms</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function LoginGate({ error }: { error?: string | null }) {
  const [googleLoginPending, setGoogleLoginPending] = useState(false);

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
            <p className="text-[11px] text-zinc-600">Sign in to manage your keys</p>
          </div>
        </div>

        {error && (
          <p className="mb-4 text-xs flex items-center gap-1.5" style={{ color: "#EF4444" }}>
            <AlertTriangle size={12} className="shrink-0" /> {error}
          </p>
        )}

        <button onClick={() => { setGoogleLoginPending(true); startGoogleLogin(); }} disabled={googleLoginPending}
          className="w-full py-2 rounded-lg text-sm font-semibold transition-all active:scale-[0.97] disabled:active:scale-100 disabled:opacity-70 flex items-center justify-center gap-2"
          style={{ background: "#00D68F", color: "#0A0A0B" }}>
          {googleLoginPending ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
              <path fill="#0A0A0B" d="M12 11v2.8h6.5c-.3 1.6-2.1 4.7-6.5 4.7-3.9 0-7.1-3.2-7.1-7.2s3.2-7.2 7.1-7.2c2.2 0 3.7.9 4.6 1.7l3.1-3C17.6 1 15.1 0 12 0 5.4 0 0 5.4 0 12s5.4 12 12 12c6.9 0 11.5-4.8 11.5-11.6 0-.8-.1-1.4-.2-2H12z"/>
            </svg>
          )}
          {googleLoginPending ? "Redirecting..." : "Sign in with Google"}
        </button>

        <p className="mt-4 text-[11px] text-zinc-600 leading-relaxed">
          Each account only sees and manages its own keys, gateway tokens,
          and request history.
        </p>
      </div>
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [user, setUser] = useState<UserRead | null>(null);

  useEffect(() => {
    (async () => {
      if (location.hash.includes("access_token=")) {
        const params = new URLSearchParams(location.hash.slice(1));
        const accessToken = params.get("access_token");
        const refreshToken = params.get("refresh_token");
        if (accessToken && refreshToken) {
          setTokenPair(accessToken, refreshToken);
          history.replaceState(null, "", location.pathname + location.search);
        }
      }

      if (getAccessToken() || getRefreshToken()) {
        try {
          const me = await api.me();
          setUser(me);
          setAuthed(true);
        } catch {
          clearTokenPair();
          setAuthError("Your session expired — please sign in again.");
        }
      }
      setCheckingAuth(false);
    })();
  }, []);

  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#0A0A0B" }}>
        <Loader2 size={20} className="animate-spin" color="#52525B" />
      </div>
    );
  }

  if (!authed) {
    return <LoginGate error={authError} />;
  }

  return (
    <Dashboard
      user={user}
      onLogout={async () => {
        await api.logout();
        clearTokenPair();
        setUser(null);
        setAuthed(false);
      }}
    />
  );
}

function GatewayAccessPanel() {
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
    setTokens(prev => prev.map(x => x.id === t.id ? { ...x, is_active: !x.is_active } : x));
    try {
      if (t.is_active) await api.revokeGatewayToken(t.id);
      else await api.activateGatewayToken(t.id);
    } catch {
      await refresh();
    }
  }

  async function remove(id: number) {
    setTokens(prev => prev.filter(x => x.id !== id));
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
            onChange={e => setLabel(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleCreate()}
          />
          <button onClick={handleCreate} disabled={creating || !label.trim()}
            className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition-all shrink-0"
            style={{ background: "#00D68F", color: "#0A0A0B", opacity: creating || !label.trim() ? 0.6 : 1 }}>
            {creating ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            Generate Token
          </button>
        </div>

        {error && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg text-xs"
            style={{ background: "rgba(239,68,68,0.08)", color: "#EF4444", border: "1px solid rgba(239,68,68,0.2)" }}>
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
              <code className="flex-1 px-2 py-1.5 rounded text-xs font-mono break-all"
                style={{ background: "#0A0A0B", color: "#00D68F", border: "1px solid rgba(0,214,143,0.2)" }}>
                {freshToken.plaintext}
              </code>
              <button onClick={() => copy(freshToken.plaintext)}
                className="px-2.5 py-1.5 rounded text-xs font-medium shrink-0"
                style={{ background: "rgba(255,255,255,0.06)", color: "#ECECF0" }}>
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
                <div key={t.id} className="px-4 py-3"
                  style={{ borderBottom: i < tokens.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none" }}>
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <span className="text-sm text-zinc-200 truncate">{t.label}</span>
                    <div className="flex items-center gap-1 shrink-0">
                      <button onClick={() => toggle(t)}
                        className="p-1.5 rounded-md transition-colors hover:bg-white/5" title={t.is_active ? "Revoke" : "Reactivate"}>
                        <Power size={13} color={t.is_active ? "#F59E0B" : "#00D68F"} />
                      </button>
                      <button onClick={() => remove(t.id)}
                        className="p-1.5 rounded-md transition-colors hover:bg-white/5" title="Delete">
                        <Trash2 size={13} color="#EF4444" />
                      </button>
                    </div>
                  </div>
                  <div className="font-mono text-xs text-zinc-500 mb-2">{t.token_preview}</div>
                  <div className="flex items-center justify-between">
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-mono font-medium"
                      style={t.is_active
                        ? { color: "#00D68F", background: "rgba(0,214,143,0.1)", border: "1px solid rgba(0,214,143,0.25)" }
                        : { color: "#71717A", background: "rgba(113,113,122,0.1)", border: "1px solid rgba(113,113,122,0.2)" }}>
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
                <tr className="text-left text-[11px] uppercase tracking-wide text-zinc-600"
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                  <th className="px-4 py-2.5 font-medium">Label</th>
                  <th className="px-4 py-2.5 font-medium">Token</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Last used</th>
                  <th className="px-4 py-2.5 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {tokens.map(t => (
                  <tr key={t.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                    <td className="px-4 py-3 text-zinc-200">{t.label}</td>
                    <td className="px-4 py-3 font-mono text-xs text-zinc-500">{t.token_preview}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-mono font-medium"
                        style={t.is_active
                          ? { color: "#00D68F", background: "rgba(0,214,143,0.1)", border: "1px solid rgba(0,214,143,0.25)" }
                          : { color: "#71717A", background: "rgba(113,113,122,0.1)", border: "1px solid rgba(113,113,122,0.2)" }}>
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: t.is_active ? "#00D68F" : "#71717A" }} />
                        {t.is_active ? "active" : "revoked"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-500">
                      {t.last_used_at ? new Date(t.last_used_at).toLocaleString() : "never"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1.5">
                        <button onClick={() => toggle(t)}
                          className="p-1.5 rounded-md transition-colors hover:bg-white/5" title={t.is_active ? "Revoke" : "Reactivate"}>
                          <Power size={13} color={t.is_active ? "#F59E0B" : "#00D68F"} />
                        </button>
                        <button onClick={() => remove(t.id)}
                          className="p-1.5 rounded-md transition-colors hover:bg-white/5" title="Delete">
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

function Dashboard({ user, onLogout }: { user: UserRead | null; onLogout: () => void }) {
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

  useEffect(() => {
    api.recentEvents(50).then(events => setReqs(events.map(toLR))).catch(() => {});
    const stop = streamEvents(
      evt => setReqs(prev => [toLR(evt), ...prev.slice(0, 49)]),
      err => console.warn("live event stream disconnected:", err)
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
    const key = keys.find(k => k.id === id);
    if (!key) return;
    setKeys(prev => prev.map(k => k.id === id
      ? { ...k, status: k.status === "disabled" ? "active" : "disabled" }
      : k));
    try {
      await api.updateKey(Number(id), { status: key.status === "disabled" ? "active" : "disabled" });
      await refreshKeys();
    } catch {
      await refreshKeys();
    }
  }

  async function resetCooldown(id: string) {
    setResettingIds(prev => new Set(prev).add(id));
    try {
      await api.resetCooldown(Number(id));
      await refreshKeys();
    } catch {
    } finally {
      setResettingIds(prev => {
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
    setCheckingIds(prev => new Set(prev).add(id));
    const toastId = `${id}-${Date.now()}`;
    try {
      const result = await api.checkKey(Number(id));
      setCheckResults(prev => [...prev, { toastId, keyId: id, ok: result.ok, detail: result.detail }]);
      await refreshKeys();
    } catch (err) {
      setCheckResults(prev => [...prev, {
        toastId,
        keyId: id,
        ok: false,
        detail: err instanceof ApiError ? err.message : "Check failed — couldn't reach the API",
      }]);
    } finally {
      setCheckingIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      setTimeout(() => setCheckResults(prev => prev.filter(r => r.toastId !== toastId)), 5000);
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "#0A0A0B", fontFamily: "Inter, sans-serif" }}>
      <TopBar view={view} onView={setView} onAdd={() => setAddOpen(true)} operational={operational} onLogout={onLogout} userEmail={user?.email} />

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
          <div key="dashboard" className="space-y-4 animate-in fade-in slide-in-from-bottom-1 duration-300 ease-out">
            <MetricCards keys={keys} />
            <KeysTable
              keys={keys} filter={filter} onFilter={setFilter} now={now}
              onSelect={setSelectedId}
              onEdit={id => { setEditId(id); setSelectedId(null); }}
              onToggle={toggleKey}
              onCheck={checkKey}
              checkingIds={checkingIds}
            />
          </div>
        ) : view === "monitor" ? (
          <div key="monitor" className="animate-in fade-in slide-in-from-bottom-1 duration-300 ease-out">
            <LiveMonitor reqs={reqs} now={now} />
          </div>
        ) : (
          <div key="access" className="animate-in fade-in slide-in-from-bottom-1 duration-300 ease-out">
            <GatewayAccessPanel />
          </div>
        )}
      </main>

      {checkResults.length > 0 && (
        <div className="fixed bottom-4 right-4 z-[60] flex flex-col-reverse gap-2 pointer-events-none">
          {checkResults.map(r => (
            <div key={r.toastId}
              className="flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg animate-in fade-in slide-in-from-bottom-2 duration-250 ease-out pointer-events-auto"
              style={{
                background: "#18181B",
                border: `1px solid ${r.ok ? "rgba(0,214,143,0.3)" : "rgba(239,68,68,0.3)"}`,
                maxWidth: 360,
              }}>
              {r.ok
                ? <CheckCircle2 size={16} color="#00D68F" className="shrink-0" />
                : <AlertTriangle size={16} color="#EF4444" className="shrink-0" />}
              <div className="min-w-0">
                <div className="text-xs font-medium text-zinc-200">
                  {r.ok ? "Key is working" : "Key check failed"}
                </div>
                {r.detail && (
                  <div className="text-[11px] text-zinc-500 truncate">{r.detail}</div>
                )}
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
          keyData={selectedKey} now={now}
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