import { useState } from "react";
import { Square } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import posthog from "@/lib/posthog";
import { useThread } from "@/stores/thread-store";

/** Stops one running subagent (identified by its `task` call id). The rest of the run keeps going. */
export function StopAgentButton({ callId, label, className }: { callId: string; label: string; className?: string }) {
  const threadId = useThread((s) => s.threadId);
  const [stopping, setStopping] = useState(false);
  const stop = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!threadId || stopping) return;
    setStopping(true);
    try {
      await api.stopSubagent(threadId, callId);
      posthog.capture("agent_run_stop_requested");
      toast(`Stopping ${label}…`);
    } catch {
      setStopping(false);
      toast(`Couldn't stop ${label}. Try again.`);
    }
  };
  return (
    <Button variant="outline" size="xs" className={className} onClick={stop} disabled={stopping}
      aria-label={`Stop ${label}`}>
      <Square className="size-3 fill-current" />{stopping ? "Stopping…" : "Stop"}
    </Button>
  );
}
