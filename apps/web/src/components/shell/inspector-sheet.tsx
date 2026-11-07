import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { InspectorTabContent, TAB_META, TAB_ORDER } from "@/components/inspector";
import { cn } from "@/lib/utils";
import { useUi } from "@/stores/ui-store";
import { TAB_ICONS, useTabBadges } from "./inspector-icons";

/** Inspector below 1024px: right sheet with a horizontally scrolling tab list. */
export function InspectorSheet() {
  const { inspectorOpen, inspectorTab, setTab, toggleInspector } = useUi();
  const badges = useTabBadges();
  return (
    <Sheet open={inspectorOpen} onOpenChange={(o) => o !== inspectorOpen && toggleInspector()}>
      <SheetContent side="right" className="w-[min(440px,92vw)] gap-0 p-0 sm:max-w-none">
        <SheetTitle className="sr-only">Agent context</SheetTitle>
        <SheetDescription className="sr-only">Plan, agents, files, sources, assets and approvals for this chat.</SheetDescription>
        <div role="tablist" aria-label="Inspector tabs" className="flex shrink-0 gap-1 overflow-x-auto border-b p-2 pr-10">
          {TAB_ORDER.map((tab) => {
            const Icon = TAB_ICONS[tab];
            const n = badges[tab] ?? 0;
            return (
              <button key={tab} role="tab" aria-selected={inspectorTab === tab} onClick={() => setTab(tab)}
                className={cn("flex h-8 shrink-0 items-center gap-1.5 rounded-md px-2 text-xs text-muted-foreground",
                  "hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
                  inspectorTab === tab && "bg-accent text-accent-foreground")}>
                <Icon className="size-4" />{TAB_META[tab].label}
                {n > 0 && <Badge className="h-4 min-w-4 rounded-full px-1 text-[10px]">{n}</Badge>}
              </button>
            );
          })}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto"><InspectorTabContent tab={inspectorTab} /></div>
      </SheetContent>
    </Sheet>
  );
}
