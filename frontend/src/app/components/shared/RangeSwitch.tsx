export function RangeSwitch<T extends string>({
  value,
  onChange,
  options,
  label = "Time range",
}: {
  value: T;
  onChange: (r: T) => void;
  options: { value: T; label: string }[];
  label?: string;
}) {
  return (
    <div
      className="inline-flex items-center rounded-lg p-0.5"
      style={{ background: "#0B0B0D", border: "1px solid rgba(255,255,255,0.08)" }}
      role="group"
      aria-label={label}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            aria-pressed={active}
            className="px-2.5 py-1 rounded-md text-[11px] font-medium font-mono transition-colors"
            style={
              active
                ? { background: "rgba(0,214,143,0.14)", color: "#22E3A8" }
                : { background: "transparent", color: "#71717A" }
            }
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
