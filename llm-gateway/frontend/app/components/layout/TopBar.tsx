import { Plus, Activity, Shield, LayoutDashboard, KeyRound, LogOut } from "lucide-react";
import type { View } from "../../types";

export function TopBar({ view, onView, onAdd, operational, onLogout }: {
  view: View; onView: (v: View) => void; onAdd: () => void; operational: boolean; onLogout: () => void;
}) {
  return (
    <header className="flex flex-col md:flex-row md:items-center md:justify-between md:h-14 shrink-0 px-3 sm:px-6 gap-2 md:gap-5 py-2.5 md:py-0"
      style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", background: "#0A0A0B" }}>
      <div className="flex items-center justify-between md:justify-start gap-2.5 md:gap-5">
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
        <div className="hidden md:block h-4 w-px" style={{ background: "rgba(255,255,255,0.08)" }} />
        <div className="flex md:hidden items-center gap-2">
          <span className="w-2 h-2 rounded-full"
            style={{
              background: operational ? "#00D68F" : "#EF4444",
              boxShadow: operational ? "0 0 7px rgba(0,214,143,0.8)" : "0 0 7px rgba(239,68,68,0.8)",
            }} />
        </div>
      </div>

      <nav className="flex gap-0.5 overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0">
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

      <div className="flex items-center justify-between md:justify-end gap-4">
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
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
          style={{ background: "#00D68F", color: "#0A0A0B", boxShadow: "0 0 16px rgba(0,214,143,0.3)" }}
          onMouseEnter={e => (e.currentTarget.style.boxShadow = "0 0 28px rgba(0,214,143,0.55)")}
          onMouseLeave={e => (e.currentTarget.style.boxShadow = "0 0 16px rgba(0,214,143,0.3)")}>
          <Plus size={13} /> Add Key
        </button>
        <button onClick={onLogout} title="Sign out"
          className="p-1.5 rounded-lg transition-colors hover:bg-white/5">
          <LogOut size={14} color="#52525B" />
        </button>
      </div>
    </header>
  );
}
