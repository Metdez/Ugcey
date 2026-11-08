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
  return null; // idle, error and offline show nothing up here (operator: only green in the top right); details stay in the chat
}
