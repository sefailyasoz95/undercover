import { useEffect } from "react";

export function usePolling(load: () => void, every: number, active: boolean) {
  useEffect(() => {
    load();
    if (!active) return;
    const timer = setInterval(load, every);
    return () => {
      clearInterval(timer);
    };
  }, [load, every, active]);
}
