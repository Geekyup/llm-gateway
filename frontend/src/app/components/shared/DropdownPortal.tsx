import { useLayoutEffect, useState, type RefObject } from "react";
import { createPortal } from "react-dom";

export function DropdownPortal({
  anchorRef,
  open,
  align = "right",
  children,
}: {
  anchorRef: RefObject<HTMLElement | null>;
  open: boolean;
  align?: "left" | "right";
  children: React.ReactNode;
}) {
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  useLayoutEffect(() => {
    if (!open || !anchorRef.current) {
      setPos(null);
      return;
    }
    const update = () => {
      const rect = anchorRef.current!.getBoundingClientRect();
      setPos({
        top: rect.bottom + window.scrollY + 6,
        left: align === "right"
          ? rect.right + window.scrollX
          : rect.left + window.scrollX,
      });
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open, anchorRef, align]);

  if (!open || !pos) return null;

  return createPortal(
    <div
      style={{
        position: "absolute",
        top: pos.top,
        left: align === "right" ? undefined : pos.left,
        right: align === "right" ? `calc(100vw - ${pos.left}px)` : undefined,
        zIndex: 50,
      }}
    >
      {children}
    </div>,
    document.body
  );
}