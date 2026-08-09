import type { View } from "../../types";
import { SidebarBrand } from "./SidebarBrand";
import { SidebarNav } from "./SidebarNav";

export function Sidebar({ view, onView }: { view: View; onView: (v: View) => void }) {
  return (
    <aside
      className="hidden md:flex md:flex-col w-56 shrink-0 h-screen sticky top-0"
      style={{ background: "#0D0D0F", borderRight: "1px solid rgba(255,255,255,0.06)" }}
    >
      <SidebarBrand />
      <SidebarNav view={view} onView={onView} />
    </aside>
  );
}
