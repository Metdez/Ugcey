import { useEffect, useState } from "react";
import { Camera, Music2, Play, Smartphone, Users, type LucideIcon } from "lucide-react";
import type { ConnectedAccount, Platform } from "@ugecy/contracts";
import { Badge } from "@/components/ui/badge";
import { SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarMenu, SidebarMenuItem } from "@/components/ui/sidebar";
import { StatusDot, type Tone } from "@/components/common/status-dot";
import { glasshand, type GlasshandStatus } from "@/lib/glasshand";
import { useWorkspace } from "@/stores/workspace-store";

const ICON: Record<Platform, LucideIcon> = { tiktok: Music2, instagram: Camera, youtube: Play, facebook: Users };
const TONE: Record<ConnectedAccount["status"], [Tone, string]> = {
  connected: ["success", "Connected"], needs_auth: ["warning", "Reconnect needed"], error: ["error", "Error"],
};

export function AccountsStatus() {
  const accounts = useWorkspace((s) => s.accounts);
  const [gh, setGh] = useState<GlasshandStatus | null>(null);
  useEffect(() => { glasshand.status().then(setGh).catch(() => {}); }, []);
  const ghTone: [Tone, string] = gh?.state === "connected" ? ["success", "Connected"] : gh?.state === "pending" ? ["warning", "Awaiting approval"] : ["muted", "Not connected"];
  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>Accounts</SidebarGroupLabel>
      <SidebarGroupContent>
        <div className="flex items-center gap-2 px-2 py-1.5 text-xs">
          <Smartphone className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate">Glasshand iPhone</span>
          <StatusDot tone={ghTone[0]} label={ghTone[1]} className="ml-auto" />
        </div>
        {accounts.length === 0 ? (
          <p className="px-2 text-xs text-muted-foreground">No accounts connected.</p>
        ) : (
          <SidebarMenu>
            {accounts.map((a) => {
              const Icon = ICON[a.platform];
              const [tone, label] = TONE[a.status];
              return (
                <SidebarMenuItem key={a.id} className="flex items-center gap-2 px-2 py-1.5 text-xs">
                  <Icon className="size-4 shrink-0 text-muted-foreground" />
                  <span className="truncate">{a.handle}</span>
                  {a.mode === "mock" && <Badge variant="outline" className="h-4 px-1 text-[10px]">mock</Badge>}
                  <StatusDot tone={tone} label={label} className="ml-auto" />
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        )}
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
