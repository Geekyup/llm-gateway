export function SidebarBrand() {
  return (
    <div className="flex items-center px-5 h-14 shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
      <span
        className="font-mono font-semibold"
        style={{ fontSize: "20px", letterSpacing: "0.01em", lineHeight: 1 }}
      >
        <span className="text-zinc-100">key</span>
        <span style={{ color: "#00D68F" }}>pool</span>
      </span>
    </div>
  );
}