import { useCallback, useState } from "react";

export function useIdSet() {
  const [ids, setIds] = useState<Set<string>>(() => new Set());

  const add = useCallback((id: string) => {
    setIds((prev) => new Set(prev).add(id));
  }, []);

  const remove = useCallback((id: string) => {
    setIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);

  return { ids, add, remove };
}
