import { useMemo, useState } from "react";
import { MoreHorizontal, Trash2 } from "lucide-react";
import type { ThreadSummary } from "@ugecy/contracts";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import {
  SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarMenu, SidebarMenuAction, SidebarMenuButton,
  SidebarMenuItem, SidebarMenuSkeleton,
} from "@/components/ui/sidebar";
import { Spinner } from "@/components/ui/spinner";
import { StatusDot } from "@/components/common/status-dot";
import { navigateToThread } from "@/hooks/use-thread-route";
import { api } from "@/lib/api";
import posthog from "@/lib/posthog";
import { dateBucket } from "@/lib/time";
import { useThread } from "@/stores/thread-store";
import { useWorkspace } from "@/stores/workspace-store";

const ORDER = ["Today", "Yesterday", "Previous 7 days", "Older"] as const;

function Dot({ t, live }: { t: ThreadSummary; live: boolean }) {
  if (live || t.status === "running") return <Spinner className="size-3" />;
  if (t.status === "awaiting_approval") return <StatusDot tone="warning" label="Needs approval" />;
  if (t.status === "error") return <StatusDot tone="error" label="Error" />;
  return null;
}

export function ThreadNav() {
  const threads = useWorkspace((s) => s.threads);
  const loaded = useWorkspace((s) => s.threadsLoaded);
  const activeId = useThread((s) => s.threadId);
  const status = useThread((s) => s.status);
  const [doomed, setDoomed] = useState<ThreadSummary | null>(null);

  const groups = useMemo(() => {
    const g: Record<string, ThreadSummary[]> = {};
    for (const t of threads) (g[dateBucket(t.updated_at)] ??= []).push(t);
    return g;
  }, [threads]);

  const remove = async () => {
    if (!doomed) return;
    const deleted = await api.deleteThread(doomed.id).then(() => true).catch(() => false);
    if (deleted) posthog.capture("chat_deleted");
    if (doomed.id === activeId) navigateToThread(null);
    setDoomed(null);
    void useWorkspace.getState().refreshThreads();
  };

  if (!loaded) {
    return <SidebarGroup><SidebarMenu>{[0, 1, 2, 3, 4].map((i) => <SidebarMenuItem key={i}><SidebarMenuSkeleton /></SidebarMenuItem>)}</SidebarMenu></SidebarGroup>;
  }
  if (!threads.length) {
    return <p className="px-4 py-2 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">No chats yet.</p>;
  }
  return (
    <>
      {ORDER.filter((k) => groups[k]).map((k) => (
        <SidebarGroup key={k}>
          <SidebarGroupLabel>{k}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {groups[k].map((t) => (
                <SidebarMenuItem key={t.id}>
                  <SidebarMenuButton isActive={t.id === activeId} tooltip={t.title} onClick={() => navigateToThread(t.id)}>
                    <Dot t={t} live={t.id === activeId && (status === "streaming" || status === "connecting")} />
                    <span className="truncate">{t.title}</span>
                  </SidebarMenuButton>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <SidebarMenuAction showOnHover aria-label={`Actions for ${t.title}`}><MoreHorizontal /></SidebarMenuAction>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent side="right" align="start">
                      <DropdownMenuItem variant="destructive" onSelect={() => setDoomed(t)}><Trash2 />Delete chat</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      ))}
      <AlertDialog open={!!doomed} onOpenChange={(o) => !o && setDoomed(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this chat?</AlertDialogTitle>
            <AlertDialogDescription>"{doomed?.title}" and its plan, files and approvals history will be removed. This can't be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void remove()}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
