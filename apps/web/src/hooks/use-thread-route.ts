import { useEffect } from "react";
import { getThreadParam, setThreadParam } from "@/lib/location";
import { threadActions } from "@/stores/thread-store";

/** Open a thread (or a new empty chat with null) and reflect it in the URL. */
export function navigateToThread(id: string | null) {
  setThreadParam(id);
  void threadActions.openThread(id);
}

/** Boot: open `?t=` if present, and follow back/forward. */
export function useThreadRoute() {
  useEffect(() => {
    const sync = () => void threadActions.openThread(getThreadParam());
    if (getThreadParam()) sync();
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
}
