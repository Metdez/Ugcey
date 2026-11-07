import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { TAB_META, TAB_ORDER } from "@/components/inspector";
import { cn } from "@/lib/utils";
import { useUi } from "@/stores/ui-store";
import { TAB_ICONS, useTabBadges } from "./inspector-icons";

/** 44px vertical tab strip at the right edge (≥1024px). Clicking the active icon collapses the panel. */
export function InspectorRail() {
  const { inspectorOpen, inspectorTab, openInspector, toggleInspector } = useUi();
  const badges = useTabBadges();
  return (
    <div role="tablist" aria-orientation="vertical" aria-label="Inspector tabs"
      className="flex w-11 shrink-0 flex-col items-center gap-1 border-l bg-sidebar py-2">
      {TAB_ORDER.map((tab) => {
        const Icon = TAB_ICONS[tab];
        const active = inspectorOpen && inspectorTab === tab;
        const n = badges[tab] ?? 0;
        return (
          <Tooltip key={tab}>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" role="tab" aria-selected={active} aria-controls="inspector-panel"
                aria-label={n ? `${TAB_META[tab].label}, ${n}` : TAB_META[tab].label}
                onClick={() => (active ? toggleInspector() : openInspector(tab))}
                className={cn("relative size-8", active && "bg-accent text-accent-foreground")}>
                <Icon />
                {n > 0 && (
                  <Badge className={cn("absolute -top-1 -right-1 h-4 min-w-4 justify-center rounded-full px-1 text-[10px] tabular-nums",
                    tab === "approvals" ? "bg-warning text-background" : tab === "agents" ? "animate-pulse" : "")}>
                    {n}
                  </Badge>
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left">
              {TAB_META[tab].label} <Kbd>G</Kbd><Kbd>{TAB_META[tab].chord}</Kbd>
            </TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}
