import { LayoutDashboard, Activity, MessageSquare, Shield } from "lucide-react";
import type { View } from "../../types";

const NAV_ITEMS: { v: View; label: string; Icon: typeof LayoutDashboard }[] = [
  { v: "dashboard",  label: "Dashboard",     Icon: LayoutDashboard },
  { v: "monitor",    label: "Live Monitor",  Icon: Activity },
  { v: "playground", label: "Playground",    Icon: MessageSquare },
  { v: "access",     label: "Gateway Access", Icon: Shield },
];

export function SidebarNav({ view, onView }: { view: View; onView: (v: View) => void }) {
  return (
    <nav className="flex flex-col gap-0.5 px-3 py-4">
      {NAV_ITEMS.map(({ v, label, Icon }) => (
        <button
          key={v}
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
      ))}
    </nav>
  );
}
