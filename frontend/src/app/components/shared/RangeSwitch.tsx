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
      style={{ background: "var(--background)", border: "1px solid color-mix(in srgb, var(--ink) 14%, transparent)" }}
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
            className="px-2.5 py-1 rounded-md text-[12px] font-medium font-mono transition-colors"
            style={
              active
                ? { background: "color-mix(in srgb, var(--accent) 14%, transparent)", color: "var(--accent-hover)" }
                : { background: "transparent", color: "var(--ink-3)" }
            }
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
