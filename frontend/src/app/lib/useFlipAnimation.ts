import { useLayoutEffect, useRef } from "react";

/**
 * Classic FLIP (First-Last-Invert-Play) animation for reordering DOM nodes
 * without a layout library. Attach the returned ref to the container whose
 * direct children get reordered (e.g. by toggling a `grouped` prop that
 * changes render order) and every animated child needs a stable
 * `data-flip-id` attribute so the hook can match old position -> new
 * position across the re-render.
 */
export function useFlipAnimation<T extends HTMLElement = HTMLDivElement>(dep: unknown) {
  const containerRef = useRef<T>(null);
  const prevRects = useRef<Map<string, DOMRect>>(new Map());

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const nodes = Array.from(container.querySelectorAll<HTMLElement>("[data-flip-id]"));
    const prev = prevRects.current;

    if (prev.size > 0) {
      for (const node of nodes) {
        const id = node.dataset.flipId!;
        const before = prev.get(id);
        if (!before) continue;
        const after = node.getBoundingClientRect();
        const dx = before.left - after.left;
        const dy = before.top - after.top;
        if (dx || dy) {
          node.style.transition = "none";
          node.style.transform = `translate(${dx}px, ${dy}px)`;
          // force reflow so the browser registers the starting transform
          // before we animate it away on the next frame
          node.getBoundingClientRect();
          requestAnimationFrame(() => {
            node.style.transition = "transform 320ms cubic-bezier(0.22, 1, 0.36, 1)";
            node.style.transform = "";
          });
        }
      }
    }

    const next = new Map<string, DOMRect>();
    for (const node of nodes) {
      next.set(node.dataset.flipId!, node.getBoundingClientRect());
    }
    prevRects.current = next;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dep]);

  return containerRef;
}