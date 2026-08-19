import { useEffect, useRef } from "react";

/**
 * Calls `callback` immediately (via the effect below in the consumer) and then
 * every `intervalMs`. Pauses while the tab is hidden and resumes (with an
 * immediate tick) when it becomes visible again, so we don't burn requests
 * on backgrounded tabs and the data is fresh the moment the user comes back.
 */
export function usePolling(callback: () => void, intervalMs: number, enabled = true) {
  const savedCallback = useRef(callback);
  savedCallback.current = callback;

  useEffect(() => {
    if (!enabled) return;

    let id: ReturnType<typeof setInterval> | null = null;

    const start = () => {
      if (id !== null) return;
      id = setInterval(() => savedCallback.current(), intervalMs);
    };
    const stop = () => {
      if (id === null) return;
      clearInterval(id);
      id = null;
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        stop();
      } else {
        savedCallback.current();
        start();
      }
    };

    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [intervalMs, enabled]);
}
