import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { InspectorTabContent, TAB_META } from "@/components/inspector";
import { useUi } from "@/stores/ui-store";

/** Header + active tab body. Shared by the docked panel and the sheet. */
export function InspectorPanel() {
  const { inspectorTab, toggleInspector } = useUi();
  return (
    <aside id="inspector-panel" aria-label="Agent context" className="flex h-full min-w-0 flex-col bg-background">
      <header className="flex h-12 shrink-0 items-center justify-between border-b px-3">
        <h2 className="text-sm font-semibold">{TAB_META[inspectorTab].label}</h2>
        <Button variant="ghost" size="icon" className="size-8" aria-label="Close inspector" onClick={toggleInspector}>
          <X />
        </Button>
      </header>
      <ScrollArea className="min-h-0 flex-1">
        <InspectorTabContent tab={inspectorTab} />
      </ScrollArea>
    </aside>
  );
}
