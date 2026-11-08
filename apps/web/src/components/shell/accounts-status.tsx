import { useEffect, useState } from "react";
import { Camera, Cloud, Music2, Play, Smartphone, Users, type LucideIcon } from "lucide-react";
import type { ConnectedAccount, Platform } from "@ugecy/contracts";
import { SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarMenu, SidebarMenuItem } from "@/components/ui/sidebar";
import { StatusDot, type Tone } from "@/components/common/status-dot";
import { DropboxConnect } from "@/components/storage/dropbox-connect";
import { dropbox, type DropboxStatus } from "@/lib/dropbox";
import { glasshand, type GlasshandStatus } from "@/lib/glasshand";
import { useWorkspace } from "@/stores/workspace-store";

const ICON: Record<Platform, LucideIcon> = { tiktok: Music2, instagram: Camera, youtube: Play, facebook: Users };
const TONE: Record<ConnectedAccount["status"], [Tone, string]> = {
  connected: ["success", "Connected"], needs_auth: ["warning", "Reconnect needed"], error: ["error", "Error"],
};

export function AccountsStatus() {
  const accounts = useWorkspace((s) => s.accounts);
  const [gh, setGh] = useState<GlasshandStatus | null>(null);
  const [dbx, setDbx] = useState<DropboxStatus | null>(null);
  const [dbxOpen, setDbxOpen] = useState(false);
  useEffect(() => { glasshand.status().then(setGh).catch(() => {}); dropbox.status().then(setDbx).catch(() => {}); }, []);
  const ghTone: [Tone, string] = gh?.state === "connected" ? ["success", "Connected"] : gh?.state === "pending" ? ["warning", "Awaiting approval"] : ["muted", "Not connected"];
  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>Accounts</SidebarGroupLabel>
      <SidebarGroupContent>
        <div className="flex items-center gap-2 px-2 py-1.5 text-xs">
          <Smartphone className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate">iPhone</span>
          <StatusDot tone={ghTone[0]} label={ghTone[1]} className="ml-auto" />
        </div>
        <button type="button" onClick={() => setDbxOpen(true)} className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs hover:bg-sidebar-accent">
          <Cloud className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate">{dbx?.connected ? `Dropbox: ${dbx.account_name ?? "connected"}` : "Dropbox"}</span>
          <StatusDot tone={dbx?.connected ? (dbx.missing_scopes.length ? "warning" : "success") : "muted"} label={dbx?.connected ? (dbx.missing_scopes.length ? "Missing permissions" : "Connected") : "Not connected"} className="ml-auto" />
        </button>
        <DropboxConnect open={dbxOpen} onOpenChange={setDbxOpen} status={dbx} onStatus={setDbx} />
        {accounts.length === 0 ? (
          <p className="px-2 text-xs text-muted-foreground">No social accounts connected.</p>
        ) : (
          <SidebarMenu>
            {accounts.map((a) => {
              const Icon = ICON[a.platform];
              const [tone, label] = TONE[a.status];
              return (
                <SidebarMenuItem key={a.id} className="flex items-center gap-2 px-2 py-1.5 text-xs">
                  <Icon className="size-4 shrink-0 text-muted-foreground" />
                  <span className="truncate">{a.handle}</span>
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
