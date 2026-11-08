import { useEffect } from "react";
import { Command, PanelRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";
import { useWorkspace } from "@/stores/workspace-store";
import { ModelChip } from "./model-chip";
import { RunStatusBadge } from "./run-status-badge";

export function MainHeader() {
  const title = useThread((s) => s.title);
  const status = useThread((s) => s.status);
  const pending = useThread((s) => Object.values(s.approvals).filter((a) => a.status === "pending").length);
  const modes = useWorkspace((s) => s.config?.modes);
  const { inspectorOpen, toggleInspector, setPalette } = useUi();

  useEffect(() => {
    const running = status === "streaming" || status === "connecting";
    document.title = pending ? `(${pending}) Approval needed · Ugecy` : running ? `● ${title} – Ugecy` : `${title} – Ugecy`;
  }, [title, status, pending]);

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b px-3">
      <SidebarTrigger aria-label="Toggle sidebar" />
      <h1 className="min-w-0 flex-1 truncate text-sm font-semibold">{title}</h1>
      <div className="hidden items-center gap-2 sm:flex"><ModelChip /></div>
      <RunStatusBadge />
      {modes && (
        <div className="hidden items-center gap-1 md:flex">
          {([["iPhone", modes.device], ["Video", modes.media], ["Research", modes.research], ["Deep research", modes.tavily]] as const).map(([name, m]) => (
            <Badge key={name} variant="outline" className="gap-1 text-[11px]" title={`${name} ${m === "live" ? "connected" : "not connected"}`}>
              <span className={`size-1.5 rounded-full ${m === "live" ? "bg-success" : "bg-muted-foreground"}`} aria-hidden />
              {name} {m === "live" ? "live" : "off"}
            </Badge>
          ))}
        </div>
      )}
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="ghost" size="icon" className="size-8" aria-label="Command palette" onClick={() => setPalette(true)}>
            <Command />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Command palette <Kbd>⌘K</Kbd></TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="ghost" size="icon" className="relative size-8 lg:hidden" aria-label="Toggle inspector"
            aria-pressed={inspectorOpen} onClick={toggleInspector}>
            <PanelRight />
            {pending > 0 && <Badge className="absolute -top-1 -right-1 h-4 min-w-4 rounded-full bg-warning px-1 text-[10px] text-background">{pending}</Badge>}
          </Button>
        </TooltipTrigger>
        <TooltipContent>Inspector <Kbd>⌘I</Kbd></TooltipContent>
      </Tooltip>
    </header>
  );
}
