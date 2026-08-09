import { providerMeta } from "../../lib/domain";

export function ProviderBadge({ provider }: { provider: string }) {
  const p = providerMeta(provider);
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium max-w-full truncate justify-self-start"
      style={{ color: p.color, background: p.bg }}
    >
      {p.name}
    </span>
  );
}
