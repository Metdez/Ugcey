import { Check, Loader2, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { StopAgentButton } from "./stop-agent-button";
import type { SubagentRunView } from "@/types/agent";
import { agentColor, duration } from "../inspector/lib";
import { useFlash } from "../inspector/hooks";

export function StatusIcon({ status }: { status: SubagentRunView["status"] }) {
  return status === "running" ? <Loader2 className="size-3.5 animate-spin text-primary" aria-label="Running" />
    : status === "error" ? <TriangleAlert className="size-3.5 text-destructive" aria-label="Failed" />
    : <Check className="size-3.5 text-success" aria-label="Complete" />;
}

export function SubagentRunCard({ run, focused, onOpen }: { run: SubagentRunView; focused: boolean; onOpen: () => void }) {
  const flash = useFlash(focused);
  return (
    <div className="relative">
    <button
      ref={flash.ref as React.Ref<HTMLButtonElement>}
      onClick={onOpen}
      className={`flex w-full flex-col gap-1.5 rounded-lg border bg-card p-3 text-left transition-colors hover:bg-accent ${flash.className}`}
    >
      <span className="flex items-center gap-2">
        <span className="size-5 shrink-0 rounded-full" style={{ background: agentColor(run.name) }} aria-hidden />
        <span className="flex-1 truncate text-[13px] font-medium">{run.name}</span>
        <StatusIcon status={run.status} />
        <span className="text-xs tabular-nums text-muted-foreground">{duration(run.startedAt, run.endedAt)}</span>
      </span>
      <span className="line-clamp-2 text-xs text-muted-foreground">{run.task}</span>
      <span className="flex items-center gap-1.5">
        <Badge variant="secondary">{run.toolCallIds.length} tools</Badge>
        {run.model && <Badge variant="outline" className="font-mono">{run.model.split("/").pop()}</Badge>}
      </span>
    </button>
    {run.status === "running" && <StopAgentButton callId={run.id} label={run.name} className="absolute bottom-2 right-2" />}
    </div>
  );
}
