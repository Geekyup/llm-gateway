import { useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { useEscapeKey } from "../../lib/useEscapeKey";

export function ModalShell({
  title,
  onClose,
  widthClass,
  children,
}: {
  title: string;
  onClose: () => void;
  widthClass: string;
  children: ReactNode;
}) {
  useEscapeKey(onClose);
  const mouseDownOnOverlay = useRef(false);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 duration-200"
      style={{ background: "rgba(0,0,0,0.86)", backdropFilter: "blur(4px)" }}
      onMouseDown={(e) => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onMouseUp={(e) => {
        if (mouseDownOnOverlay.current && e.target === e.currentTarget) onClose();
        mouseDownOnOverlay.current = false;
      }}
    >
      <div
        className={`w-full ${widthClass} rounded-lg p-5 sm:p-6 max-h-[92vh] overflow-y-auto duration-200 ease-out`}
        style={{ background: "var(--card)", border: "1px solid color-mix(in srgb, var(--ink) 9%, transparent)", boxShadow: "0 32px 80px rgba(0,0,0,0.72)" }}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg transition-colors hover:bg-ink/5">
            <X size={16} color="var(--ink-4)" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
