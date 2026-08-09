import { KeyRound } from "lucide-react";

export function SidebarBrand() {
  return (
    <div className="flex items-center gap-2.5 px-4 h-14 shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
      <div
        className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: "rgba(0,214,143,0.12)", border: "1px solid rgba(0,214,143,0.2)" }}
      >
        <KeyRound size={14} color="#00D68F" />
      </div>
      <span className="font-mono text-sm font-medium tracking-tight text-zinc-100 truncate">keypool</span>
      <span
        className="text-[10px] font-mono px-1.5 py-0.5 rounded shrink-0"
        style={{ color: "#52525B", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}
      >
        v0.4.1
      </span>
    </div>
  );
}
