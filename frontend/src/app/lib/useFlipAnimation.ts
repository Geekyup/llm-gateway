import { useLayoutEffect, useRef } from "react";


const ANIMATION_MS = 320;

function findScrollParent(el: HTMLElement): HTMLElement | null {
  let node: HTMLElement | null = el.parentElement;
  while (node && node !== document.body) {
    const style = getComputedStyle(node);
    if (/(auto|scroll)/.test(style.overflowX + style.overflowY)) return node;
    node = node.parentElement;
  }

  return (document.scrollingElement as HTMLElement) ?? document.documentElement;
}

export function useFlipAnimation<T extends HTMLElement = HTMLDivElement>(dep: unknown) {
  const containerRef = useRef<T>(null);
  const prevRects = useRef<Map<string, DOMRect>>(new Map());

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const nodes = Array.from(container.querySelectorAll<HTMLElement>("[data-flip-id]"));
    const prev = prevRects.current;
    let animated = false;


    const scrollParent = findScrollParent(container);
    const targets = new Set<HTMLElement>([document.documentElement, document.body]);
    if (scrollParent) targets.add(scrollParent);
    const prevOverflow = new Map<HTMLElement, string>();
    for (const t of targets) prevOverflow.set(t, t.style.overflow);

    if (prev.size > 0) {
      for (const node of nodes) {
        const id = node.dataset.flipId!;
        const before = prev.get(id);
        if (!before) continue;
        const after = node.getBoundingClientRect();
        const dx = before.left - after.left;
        const dy = before.top - after.top;
        if (dx || dy) {
          animated = true;
          node.style.transition = "none";
          node.style.transform = `translate(${dx}px, ${dy}px)`;
          node.getBoundingClientRect();
          requestAnimationFrame(() => {
            node.style.transition = `transform ${ANIMATION_MS}ms cubic-bezier(0.22, 1, 0.36, 1)`;
            node.style.transform = "";
          });
        }
      }

      if (animated) {
        for (const t of targets) t.style.overflow = "hidden";
        window.setTimeout(() => {
          for (const t of targets) t.style.overflow = prevOverflow.get(t) ?? "";
        }, ANIMATION_MS + 30);
      }
    }

    const next = new Map<string, DOMRect>();
    for (const node of nodes) {
      next.set(node.dataset.flipId!, node.getBoundingClientRect());
    }
    prevRects.current = next;
  }, [dep]);

  return containerRef;
}