import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { StatusDot } from "@/components/common/status-dot";
import { useThread } from "@/stores/thread-store";

export function RunStatusBadge() {
  const status = useThread((s) => s.status);
  const pending = useThread((s) => Object.values(s.approvals).filter((a) => a.status === "pending").length);
  if (status === "streaming" || status === "connecting")
    return <Badge variant="secondary" className="gap-1.5"><Spinner className="size-3" />Running</Badge>;
  if (status === "interrupted" || pending)
    return <Badge className="gap-1.5 bg-warning/12 text-warning"><StatusDot tone="warning" />Needs approval</Badge>;
  if (status === "error") return <Badge className="gap-1.5 bg-destructive/12 text-destructive"><StatusDot tone="error" />Error</Badge>;
  if (status === "offline") return <Badge variant="outline" className="gap-1.5"><StatusDot tone="muted" />Offline</Badge>;
  if (status === "locked") return <Badge variant="outline" className="gap-1.5"><StatusDot tone="warning" />Locked</Badge>;
  return <Badge variant="outline" className="gap-1.5 text-muted-foreground"><StatusDot tone="muted" />Idle</Badge>;
}
