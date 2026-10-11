import { ListFilter } from "lucide-react";
import { STATUS_META } from "../../lib/domain";
import type { SF, Status } from "../../types";
import { ColorDot, FilterDropdown, type FilterOption } from "../shared/FilterDropdown";

const OPTIONS: FilterOption[] = (Object.keys(STATUS_META) as Status[]).map((s) => ({
  value: s,
  label: STATUS_META[s].text,
  icon: <ColorDot color={STATUS_META[s].color} />,
  bg: STATUS_META[s].bg,
  border: STATUS_META[s].bd,
}));

export function StatusFilterDropdown({ filter, onFilter }: { filter: SF; onFilter: (f: SF) => void }) {
  return (
    <FilterDropdown
      value={filter}
      onChange={(v) => onFilter(v as SF)}
      options={OPTIONS}
      allValue="all"
      allLabel="All statuses"
      shortAllLabel="Status"
      allIcon={<ListFilter size={12} color="var(--ink-3)" className="shrink-0" />}
    />
  );
}
