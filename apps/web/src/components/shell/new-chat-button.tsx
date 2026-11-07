import { SquarePen } from "lucide-react";
import { Kbd } from "@/components/ui/kbd";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import { navigateToThread } from "@/hooks/use-thread-route";

export function NewChatButton() {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton tooltip="New chat" onClick={() => navigateToThread(null)} className="bg-sidebar-accent">
          <SquarePen /><span>New chat</span>
          <Kbd className="ml-auto group-data-[collapsible=icon]:hidden">⌘⇧O</Kbd>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
