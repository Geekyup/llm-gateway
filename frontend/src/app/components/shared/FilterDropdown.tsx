import { useRef, useState, type ReactNode } from "react";
import { CheckCircle2, ChevronDown } from "lucide-react";
import { useClickOutside } from "../../lib/useClickOutside";
import { DropdownPortal } from "./DropdownPortal";

export interface FilterOption {
  value: string;
  label: string;
  icon?: ReactNode;
  bg?: string;
  border?: string;
}

const NEUTRAL_BG = "color-mix(in srgb, var(--ink) 6%, transparent)";
const NEUTRAL_BORDER = "color-mix(in srgb, var(--ink) 8.4%, transparent)";
const SELECTED_BG = "color-mix(in srgb, var(--ink) 4.2%, transparent)";

export function ColorDot({ color }: { color: string }) {
  return <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: color }} />;
}

function MenuItem({
  selected,
  icon,
  label,
  onSelect,
}: {
  selected: boolean;
  icon?: ReactNode;
  label: string;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className="group w-full flex items-center justify-between gap-2 text-left px-3 py-2 text-xs transition-colors hover:bg-ink/10"
      style={{ background: selected ? SELECTED_BG : "transparent" }}
    >
      <span className="flex items-center gap-1.5">
        {icon}
        <span
          className="transition-colors group-hover:!text-[var(--ink)]"
          style={{ color: selected ? "var(--ink)" : "var(--ink-2)" }}
        >
          {label}
        </span>
      </span>
      {selected && <CheckCircle2 size={13} color="var(--ink)" className="shrink-0" />}
    </button>
  );
}

export function FilterDropdown({
  value,
  onChange,
  options,
  allValue = "",
  allLabel,
  shortAllLabel,
  allIcon,
}: {
  value: string;
  onChange: (value: string) => void;
  options: FilterOption[];
  allValue?: string;
  allLabel: string;
  shortAllLabel?: string;
  allIcon: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useClickOutside([anchorRef, menuRef], () => setOpen(false), open);

  const active = value !== allValue;
  const selected = active ? options.find((o) => o.value === value) : undefined;
  const label = active ? selected?.label ?? value : allLabel;
  const shortLabel = active ? label : shortAllLabel ?? allLabel;

  function select(next: string) {
    onChange(next);
    setOpen(false);
  }

  return (
    <div className="relative" ref={anchorRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-2.5 py-1 rounded-md text-[12px] font-medium transition-all whitespace-nowrap hover:brightness-125"
        style={{
          color: "var(--ink)",
          background: selected?.bg ?? NEUTRAL_BG,
          border: `1px solid ${selected?.border ?? NEUTRAL_BORDER}`,
        }}
      >
        {active ? selected?.icon : allIcon}
        <span className="sm:hidden">{shortLabel}</span>
        <span className="hidden sm:inline">{label}</span>
        <ChevronDown
          size={11}
          color="var(--ink-3)"
          className="shrink-0"
          style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s ease" }}
        />
      </button>

      <DropdownPortal anchorRef={anchorRef} open={open} align="right">
        <div
          ref={menuRef}
          className="min-w-[150px] rounded-lg shadow-lg duration-150 overflow-hidden"
          style={{ background: "var(--field)", border: "1px solid color-mix(in srgb, var(--ink) 10.2%, transparent)" }}
        >
          <MenuItem selected={!active} icon={allIcon} label={allLabel} onSelect={() => select(allValue)} />
          {options.map((o) => (
            <MenuItem
              key={o.value}
              selected={value === o.value}
              icon={o.icon}
              label={o.label}
              onSelect={() => select(o.value)}
            />
          ))}
        </div>
      </DropdownPortal>
    </div>
  );
}
