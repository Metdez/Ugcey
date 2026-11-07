// WP-C public entry point (FROZEN export names): TAB_ORDER, TAB_META, InspectorTabContent.
// WP-A's InspectorPanel renders <InspectorTabContent tab={...} /> inside its ScrollArea.
import {
  Bot, FolderTree, Brain, Globe, Images, ListTodo, ScrollText, ShieldCheck, Smartphone, type LucideIcon,
} from "lucide-react";
import { createElement, lazy, Suspense, type ComponentType } from "react";
import type { InspectorTab } from "@/types/agent";

export const TAB_ORDER: InspectorTab[] = [
  "plan", "agents", "files", "memory", "sources", "assets", "approvals", "audit", "device",
];

export const TAB_META: Record<InspectorTab, { label: string; chord: string; icon: LucideIcon }> = {
  plan: { label: "Plan", chord: "P", icon: ListTodo },
  agents: { label: "Agents", chord: "A", icon: Bot },
  files: { label: "Files", chord: "F", icon: FolderTree },
  memory: { label: "Memory", chord: "M", icon: Brain },
  sources: { label: "Sources", chord: "S", icon: Globe },
  assets: { label: "Assets", chord: "X", icon: Images },
  approvals: { label: "Approvals", chord: "R", icon: ShieldCheck },
  audit: { label: "Audit", chord: "L", icon: ScrollText },
  device: { label: "Device", chord: "D", icon: Smartphone },
};

const TABS: Record<InspectorTab, ComponentType> = {
  plan: lazy(() => import("./tabs/plan-tab")),
  agents: lazy(() => import("./tabs/agents-tab")),
  files: lazy(() => import("./tabs/files-tab")),
  memory: lazy(() => import("./tabs/memory-tab")),
  sources: lazy(() => import("./tabs/sources-tab")),
  assets: lazy(() => import("./tabs/assets-tab")),
  approvals: lazy(() => import("./tabs/approvals-tab")),
  audit: lazy(() => import("./tabs/audit-tab")),
  device: lazy(() => import("./tabs/device-tab")),
};

const fallback = createElement("div", { className: "p-3 text-xs text-muted-foreground", role: "status" }, "Loading…");

export function InspectorTabContent({ tab }: { tab: InspectorTab }) {
  return createElement(Suspense, { fallback }, createElement(TABS[tab]));
}
