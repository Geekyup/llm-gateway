import { KeyRound, X } from "lucide-react";
import type { View } from "../../types";
import { SidebarNav } from "./SidebarNav";

export function MobileSidebarDrawer({
  view,
  onView,
  onClose,
}: {
  view: View;
  onView: (v: View) => void;
  onClose: () => void;
}) {
  return (
    <>
      <div
        className="fixed inset-0 z-40 animate-in fade-in duration-200"
        onClick={onClose}
        style={{ background: "rgba(0,0,0,0.5)", backdropFilter: "blur(2px)" }}
      />
      <aside
        className="fixed left-0 top-0 bottom-0 z-50 w-64 flex flex-col animate-in slide-in-from-left duration-250 ease-out"
        style={{ background: "#0D0D0F", borderRight: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center justify-between px-4 h-14 shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="flex items-center gap-2.5 min-w-0">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
              style={{ background: "rgba(0,214,143,0.12)", border: "1px solid rgba(0,214,143,0.2)" }}
            >
              <KeyRound size={14} color="#00D68F" />
            </div>
            <span className="font-mono text-sm font-medium tracking-tight text-zinc-100 truncate">keypool</span>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg transition-colors hover:bg-white/5 shrink-0">
            <X size={16} color="#52525B" />
          </button>
        </div>
        <SidebarNav view={view} onView={(v) => { onView(v); onClose(); }} />
      </aside>
    </>
  );
}
