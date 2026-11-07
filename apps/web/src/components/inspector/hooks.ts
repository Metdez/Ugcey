import { useCallback, useEffect, useRef, useState } from "react";
import { useUi, type FocusKind } from "@/stores/ui-store";

/** Poll `fn` every `ms` while the document is visible (tabs only mount while active). */
export function usePoll<T>(fn: () => Promise<T>, ms: number, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const refresh = useCallback(async () => {
    try {
      setData(await fnRef.current());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    }
  }, []);
  useEffect(() => {
    if (!enabled) return;
    void refresh();
    const id = setInterval(() => { if (!document.hidden) void refresh(); }, ms);
    return () => clearInterval(id);
  }, [ms, enabled, refresh]);
  return { data, error, refresh };
}

/** Focus target for `kind` (set by openInspector(tab, focus)). */
export function useFocusId(kind: FocusKind): string | null {
  return useUi((s) => (s.focus?.kind === kind ? s.focus.id : null));
}

/** Scroll into view and flash bg-primary/10 for 1.2s when `active` turns true. */
export function useFlash(active: boolean) {
  const ref = useRef<HTMLDivElement>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    if (!active) return;
    ref.current?.scrollIntoView?.({ block: "nearest" });
    setOn(true);
    const t = setTimeout(() => setOn(false), 1200);
    return () => clearTimeout(t);
  }, [active]);
  return { ref, className: on ? "bg-primary/10" : "" };
}

export function download(name: string, text: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export const copy = (text: string) => navigator.clipboard?.writeText(text).catch(() => {});
