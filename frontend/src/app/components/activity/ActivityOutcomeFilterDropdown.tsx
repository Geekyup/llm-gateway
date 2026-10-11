import { ListFilter } from "lucide-react";
import { alpha, outcomeMeta } from "../../lib/domain";
import { ColorDot, FilterDropdown, type FilterOption } from "../shared/FilterDropdown";

const OUTCOME_OPTIONS: FilterOption[] = [
  { value: "success", label: "Success" },
  { value: "rate_limited", label: "Rate limited" },
  { value: "exhausted", label: "Exhausted" },
  { value: "error", label: "Error" },
].map((o) => {
  const meta = outcomeMeta(o.value);
  return { ...o, icon: <ColorDot color={meta.color} />, bg: meta.bg, border: alpha(meta.color, 22) };
});

export function ActivityOutcomeFilterDropdown({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <FilterDropdown
      value={value}
      onChange={onChange}
      options={OUTCOME_OPTIONS}
      allLabel="All outcomes"
      allIcon={<ListFilter size={12} color="var(--ink-3)" className="shrink-0" />}
    />
  );
}
