import { providerMeta } from "../../lib/constants";

export function PBadge({ provider }: { provider: string }) {
  const p = providerMeta(provider);
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium"
      style={{ color: p.color, background: p.bg }}>
      {p.name}
    </span>
  );
}
