import { LayoutDashboard, Activity, BarChart2, MessageSquare, Shield } from "lucide-react";
import type { View } from "../../types";

const WORK_ITEMS: { v: View; label: string; Icon: typeof LayoutDashboard }[] = [
  { v: "dashboard",  label: "Dashboard",    Icon: LayoutDashboard },
  { v: "monitor",    label: "Live Monitor", Icon: Activity },
  { v: "activity",   label: "Activity",     Icon: BarChart2 },
  { v: "playground", label: "Playground",   Icon: MessageSquare },
];

const SETTINGS_ITEMS: { v: View; label: string; Icon: typeof LayoutDashboard }[] = [
  { v: "access", label: "Gateway Access", Icon: Shield },
];

function NavButton({ v, label, Icon, view, onView }: { v: View; label: string; Icon: typeof LayoutDashboard; view: View; onView: (v: View) => void }) {
  return (
    <button
      onClick={() => onView(v)}
      className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-all"
      style={{
        color: view === v ? "#ECECF0" : "#71717A",
        background: view === v ? "rgba(0,214,143,0.10)" : "transparent",
      }}
      onMouseEnter={(e) => { if (view !== v) e.currentTarget.style.background = "rgba(255,255,255,0.04)"; }}
      onMouseLeave={(e) => { if (view !== v) e.currentTarget.style.background = "transparent"; }}
    >
      <Icon size={15} color={view === v ? "#00D68F" : "#52525B"} />
      {label}
    </button>
  );
}

export function SidebarNav({ view, onView }: { view: View; onView: (v: View) => void }) {
  return (
    <nav className="flex flex-col px-3 py-4">
      <div className="flex flex-col gap-0.5">
        {WORK_ITEMS.map((item) => (
          <NavButton key={item.v} {...item} view={view} onView={onView} />
        ))}
      </div>

      <div className="my-3 mx-3" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }} />
      <div className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-zinc-700">Settings</div>

      <div className="flex flex-col gap-0.5">
        {SETTINGS_ITEMS.map((item) => (
          <NavButton key={item.v} {...item} view={view} onView={onView} />
        ))}
      </div>
    </nav>
  );
}