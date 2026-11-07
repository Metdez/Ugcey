import { Loader2, PauseCircle, XCircle } from "lucide-react";
import { clip } from "@/lib/time";
import { useThread } from "@/stores/thread-store";

export function RunStatusPill() {
  const status = useThread((s) => s.status);
  const progress = useThread((s) => s.progress);
  const error = useThread((s) => s.error);
  const waiting = useThread((s) => Object.values(s.approvals).filter((a) => a.status === "pending").length);
  let body = null;
  if (status === "streaming" || status === "connecting")
    body = <><Loader2 className="size-3.5 animate-spin" />Working{progress ? ` · ${progress}` : ""}</>;
  else if (status === "interrupted")
    body = <><PauseCircle className="size-3.5 text-warning" />Paused · {waiting} approval{waiting === 1 ? "" : "s"} waiting</>;
  else if (status === "error") body = <><XCircle className="size-3.5 text-destructive" />Error{error?.message ? ` · ${clip(error.message, 90)}` : ""}</>;
  return (
    <div aria-live="polite" className="flex min-h-7 justify-center">
      {body && <span className="flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs">{body}</span>}
    </div>
  );
}
