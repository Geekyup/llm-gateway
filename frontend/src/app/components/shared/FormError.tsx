import { AlertTriangle } from "lucide-react";

export function FormError({ message, className = "mt-4" }: { message: string; className?: string }) {
  return (
    <div
      className={`${className} flex items-start gap-2 px-3 py-2 rounded-lg text-xs`}
      style={{
        background: "color-mix(in srgb, var(--bad) 8%, transparent)",
        color: "var(--bad)",
        border: "1px solid color-mix(in srgb, var(--bad) 20%, transparent)",
      }}
    >
      <AlertTriangle size={13} className="shrink-0 mt-0.5" />
      <span>{message}</span>
    </div>
  );
}
