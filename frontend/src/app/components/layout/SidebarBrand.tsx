export function SidebarBrand() {
  return (
    <div className="flex items-center px-5 h-14 shrink-0" style={{ borderBottom: "1px solid color-mix(in srgb, var(--ink) 10%, transparent)" }}>
      <span
        className="font-mono font-semibold"
        style={{ fontSize: "20px", letterSpacing: "0.01em", lineHeight: 1 }}
      >
        <span className="text-ink">key</span>
        <span style={{ color: "var(--accent)" }}>pool</span>
      </span>
    </div>
  );
}