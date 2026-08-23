import { X } from "lucide-react";
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
        <div className="flex items-center justify-between px-5 h-14 shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <span className="font-mono font-semibold" style={{ fontSize: "20px", letterSpacing: "0.01em", lineHeight: 1 }}>
            <span className="text-zinc-100">key</span>
            <span style={{ color: "#00D68F" }}>pool</span>
          </span>
          <button onClick={onClose} className="p-1.5 rounded-lg transition-colors hover:bg-white/5 shrink-0">
            <X size={16} color="#52525B" />
          </button>
        </div>
        <SidebarNav view={view} onView={(v) => { onView(v); onClose(); }} />
      </aside>
    </>
  );
}