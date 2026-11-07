import { useEffect } from "react";
import { useDefaultLayout, usePanelRef } from "react-resizable-panels";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useHealthPoll } from "@/hooks/use-health";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useShortcuts } from "@/hooks/use-shortcuts";
import { useUi } from "@/stores/ui-store";
import { CommandPalette } from "./command-palette";
import { InspectorPanel } from "./inspector-panel";
import { InspectorRail } from "./inspector-rail";
import { InspectorSheet } from "./inspector-sheet";
import { LeftSidebar } from "./left-sidebar";
import { MainHeader } from "./main-header";
import { ShortcutsDialog } from "./shortcuts-dialog";
import { SystemBanners } from "./system-banners";

/** Left sidebar + (main | inspector) panels + rail. `children` is the main column body (ChatView). */
export function AppShell({ children }: { children: React.ReactNode }) {
  const desktop = useMediaQuery("(min-width: 1024px)");
  const inspectorOpen = useUi((s) => s.inspectorOpen);
  const panel = usePanelRef();
  const layout = useDefaultLayout({ id: "ugecy.layout.v1", panelIds: ["main", "inspector"], storage: localStorage });
  useShortcuts();
  useHealthPoll();

  // Below 1280px the inspector starts closed (sheet on small screens).
  useEffect(() => { if (window.innerWidth < 1280) useUi.setState({ inspectorOpen: false }); }, []);

  // Store -> panel. The panel -> store direction is `onResize` below.
  useEffect(() => {
    const p = panel.current;
    if (!desktop || !p) return;
    if (inspectorOpen && p.isCollapsed()) p.expand();
    else if (!inspectorOpen && !p.isCollapsed()) p.collapse();
  }, [inspectorOpen, desktop, panel]);

  return (
    <TooltipProvider>
      <SidebarProvider className="h-svh">
        <LeftSidebar />
        <SidebarInset className="min-w-0 overflow-hidden">
          <div className="flex h-full min-h-0">
            {desktop ? (
              <>
                <ResizablePanelGroup orientation="horizontal" defaultLayout={layout.defaultLayout}
                  onLayoutChanged={layout.onLayoutChanged} className="min-w-0 flex-1">
                  <ResizablePanel id="main" minSize="40%" className="min-w-0">
                    <MainColumn>{children}</MainColumn>
                  </ResizablePanel>
                  <ResizableHandle withHandle />
                  <ResizablePanel id="inspector" panelRef={panel} collapsible collapsedSize="0%" defaultSize="30%"
                    minSize="320px" maxSize="50%"
                    onResize={(s) => useUi.setState({ inspectorOpen: s.asPercentage > 0 })}>
                    <InspectorPanel />
                  </ResizablePanel>
                </ResizablePanelGroup>
                <InspectorRail />
              </>
            ) : (
              <>
                <MainColumn>{children}</MainColumn>
                <InspectorSheet />
              </>
            )}
          </div>
        </SidebarInset>
        <CommandPalette />
        <ShortcutsDialog />
      </SidebarProvider>
    </TooltipProvider>
  );
}

function MainColumn({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <MainHeader />
      <SystemBanners />
      <main className="min-h-0 flex-1">{children}</main>
    </div>
  );
}
