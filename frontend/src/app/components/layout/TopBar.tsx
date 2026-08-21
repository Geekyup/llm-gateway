import { Menu, Plus, Layers, LogOut } from "lucide-react";

export function TopBar({
  onAdd,
  onBulkAdd,
  operational,
  onLogout,
  userEmail,
  onMenu,
}: {
  onAdd: () => void;
  onBulkAdd: () => void;
  operational: boolean;
  onLogout: () => void;
  userEmail?: string | null;
  onMenu: () => void;
}) {
  return (
    <header
      className="flex items-center justify-between h-14 shrink-0 px-3 sm:px-6 gap-3"
      style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", background: "#0A0A0B" }}
    >
      <div className="flex items-center gap-2">
        <button onClick={onMenu} className="md:hidden p-1.5 -ml-1.5 rounded-lg transition-colors hover:bg-white/5 shrink-0">
          <Menu size={18} color="#A1A1AA" />
        </button>
        <span
          className="w-2 h-2 rounded-full shrink-0"
          style={{
            background: operational ? "#00D68F" : "#EF4444",
            boxShadow: operational ? "0 0 7px rgba(0,214,143,0.8)" : "0 0 7px rgba(239,68,68,0.8)",
          }}
        />
        <span className="hidden sm:inline text-xs font-mono" style={{ color: operational ? "#00D68F" : "#EF4444" }}>
          {operational ? "Operational" : "Degraded"}
        </span>
      </div>

      <div className="flex items-center gap-3 sm:gap-4">
        <button
          onClick={onBulkAdd}
          className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all active:scale-95"
          style={{ background: "rgba(255,255,255,0.04)", color: "#ECECF0", border: "1px solid rgba(255,255,255,0.08)" }}
        >
          <Layers size={13} /> Bulk Add
        </button>
        <button
          onClick={onAdd}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all active:scale-95"
          style={{ background: "#00D68F", color: "#0A0A0B", boxShadow: "0 0 16px rgba(0,214,143,0.3)" }}
          onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "0 0 28px rgba(0,214,143,0.55)")}
          onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "0 0 16px rgba(0,214,143,0.3)")}
        >
          <Plus size={13} /> Add Key
        </button>
        {userEmail && (
          <span className="hidden lg:inline text-[11px] font-mono truncate max-w-[160px]" style={{ color: "#52525B" }}>
            {userEmail}
          </span>
        )}
        <button onClick={onLogout} title="Sign out" className="p-1.5 rounded-lg transition-colors hover:bg-white/5">
          <LogOut size={14} color="#52525B" />
        </button>
      </div>
    </header>
  );
}