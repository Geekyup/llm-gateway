import { Plug } from "lucide-react";
import { PROVIDERS, alpha, providerMeta } from "../../lib/domain";
import { FilterDropdown, type FilterOption } from "./FilterDropdown";
import { ProviderIcon } from "./ProviderIcon";

const OPTIONS: FilterOption[] = PROVIDERS.map((p) => {
  const meta = providerMeta(p);
  return {
    value: p,
    label: meta.name,
    icon: <ProviderIcon provider={p} size={12} className="shrink-0" />,
    bg: meta.bg,
    border: alpha(meta.color, 22),
  };
});

export function ProviderFilterDropdown({
  value,
  onChange,
  allValue,
}: {
  value: string;
  onChange: (value: string) => void;
  allValue?: string;
}) {
  return (
    <FilterDropdown
      value={value}
      onChange={onChange}
      options={OPTIONS}
      allValue={allValue}
      allLabel="All providers"
      shortAllLabel="Provider"
      allIcon={<Plug size={12} color="var(--ink-3)" className="shrink-0" />}
    />
  );
}
