import { useEffect } from "react";
import { useWorkspace } from "@/stores/workspace-store";

/** Poll /api/healthz while offline: every 10s, backing off to 60s. */
export function useHealthPoll() {
  const health = useWorkspace((s) => s.health);
  useEffect(() => {
    if (health !== "offline") return;
    let delay = 10_000;
    let t: ReturnType<typeof setTimeout>;
    const tick = () => {
      void useWorkspace.getState().ping();
      delay = Math.min(delay * 2, 60_000);
      t = setTimeout(tick, delay);
    };
    t = setTimeout(tick, delay);
    return () => clearTimeout(t);
  }, [health]);
}
