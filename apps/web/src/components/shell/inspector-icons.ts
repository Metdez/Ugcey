import { Bot, Brain, FolderTree, Globe, Images, ListTodo, ScrollText, ShieldCheck, Smartphone, type LucideIcon } from "lucide-react";
import type { InspectorTab } from "@/types/agent";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";

export const TAB_ICONS: Record<InspectorTab, LucideIcon> = {
  plan: ListTodo, agents: Bot, files: FolderTree, memory: Brain, sources: Globe,
  assets: Images, approvals: ShieldCheck, audit: ScrollText, device: Smartphone,
};

/** Badge counts for the rail and sheet tabs, from the thread store. */
export function useTabBadges(): Partial<Record<InspectorTab, number>> {
  const subagents = useThread((s) => s.subagents);
  const files = useThread((s) => s.files);
  const assets = useThread((s) => s.assets);
  const approvals = useThread((s) => s.approvals);
  const seen = useUi((s) => s.lastViewed);
  const since = (tab: InspectorTab) => seen[tab] ?? 0;
  return {
    agents: Object.values(subagents).filter((a) => a.status === "running").length,
    files: files.filter((f) => f.modified_at && Date.parse(f.modified_at) > since("files")).length,
    // the Assets tab shows only finished-ad videos, so only they are counted
    assets: Object.values(assets).filter((a) => a.kind === "video" && (a.status === "queued" || a.status === "in_progress"
      || Date.parse(a.created_at) > since("assets"))).length,
    approvals: Object.values(approvals).filter((a) => a.status === "pending").length,
  };
}
