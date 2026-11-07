import { useCallback, useEffect, useRef, useState } from "react";
import { glasshand, type GlasshandStatus } from "@/lib/glasshand";

/** Glasshand status with visibility-aware polling (pending: server `interval`, connected: 10 s). */
export function useGlasshand() {
  const [status, setStatus] = useState<GlasshandStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);

  const run = useCallback(async (fn: () => Promise<GlasshandStatus>) => {
    try { const s = await fn(); if (alive.current) { setStatus(s); setError(null); } return s; }
    catch (e) { if (alive.current) setError(e instanceof Error ? e.message : "Request failed"); }
  }, []);
  const act = useCallback(async (fn: () => Promise<GlasshandStatus>) => { setBusy(true); await run(fn); if (alive.current) setBusy(false); }, [run]);

  useEffect(() => { alive.current = true; void run(glasshand.status); return () => { alive.current = false; }; }, [run]);

  const state = status?.state;
  const every = state === "pending" ? Math.max(1, status?.interval ?? 5) * 1000 : state === "connected" ? 10000 : 0;
  useEffect(() => {
    if (!every) return;
    const id = setInterval(() => { if (!document.hidden) void run(glasshand.status); }, every);
    return () => clearInterval(id);
  }, [every, run]);

  return {
    status, error, busy,
    connect: () => act(glasshand.connect),
    disconnect: () => act(glasshand.disconnect),
    select: (id: string) => act(() => glasshand.select(id)),
  };
}
