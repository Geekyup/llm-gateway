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
      style={{ borderBottom: "1px solid var(--border)", background: "var(--background)" }}
    >
      <div className="flex items-center gap-2">
        <button onClick={onMenu} className="md:hidden p-1.5 -ml-1.5 rounded-lg transition-colors hover:bg-ink/5 shrink-0">
          <Menu size={18} color="var(--ink-2)" />
        </button>
        <span
          className="w-2 h-2 rounded-full shrink-0"
          style={{
            background: operational ? "var(--ok)" : "var(--bad)",
          }}
        />
        <span className="hidden sm:inline text-xs font-mono" style={{ color: operational ? "var(--ok)" : "var(--bad)" }}>
          {operational ? "Operational" : "Degraded"}
        </span>
      </div>

      <div className="flex items-center gap-3 sm:gap-4">
        <button
          onClick={onBulkAdd}
          className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all active:scale-95"
          style={{ background: "color-mix(in srgb, var(--ink) 7%, transparent)", color: "var(--ink)", border: "1px solid color-mix(in srgb, var(--ink) 14%, transparent)" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "color-mix(in srgb, var(--ink) 14%, transparent)";
            e.currentTarget.style.borderColor = "color-mix(in srgb, var(--ink) 16.0%, transparent)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "color-mix(in srgb, var(--ink) 7%, transparent)";
            e.currentTarget.style.borderColor = "color-mix(in srgb, var(--ink) 14%, transparent)";
          }}
        >
          <Layers size={13} /> Bulk Add
        </button>
        <button
          onClick={onAdd}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all active:scale-95"
          style={{ background: "var(--accent)", color: "var(--on-accent)", boxShadow: "none" }}
        >
          <Plus size={13} /> Add Key
        </button>
        {userEmail && (
          <span className="hidden lg:inline text-[12px] font-mono truncate max-w-[160px]" style={{ color: "var(--ink-4)" }}>
            {userEmail}
          </span>
        )}
        <button onClick={onLogout} title="Sign out" className="p-1.5 rounded-lg transition-colors hover:bg-ink/5">
          <LogOut size={14} color="var(--ink-4)" />
        </button>
      </div>
    </header>
  );
}