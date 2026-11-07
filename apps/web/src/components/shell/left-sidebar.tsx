import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail } from "@/components/ui/sidebar";
import { AccountsStatus } from "./accounts-status";
import { NewChatButton } from "./new-chat-button";
import { ThreadNav } from "./thread-nav";

export function LeftSidebar() {
  return (
    <Sidebar collapsible="icon" aria-label="Chats">
      <SidebarHeader>
        <div className="flex h-8 items-center gap-2 px-2 text-sm font-semibold tracking-tight">
          <span className="grid size-6 place-items-center rounded-md bg-primary text-xs text-primary-foreground">U</span>
          <span className="group-data-[collapsible=icon]:hidden">Ugecy</span>
        </div>
        <NewChatButton />
      </SidebarHeader>
      <SidebarContent><nav aria-label="Threads"><ThreadNav /></nav></SidebarContent>
      <SidebarFooter><AccountsStatus /></SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
