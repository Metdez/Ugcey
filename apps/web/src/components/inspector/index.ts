// WP-C public entry point (FROZEN export names). WP-C replaces this stub.
// WP-A's InspectorPanel renders <InspectorTabContent tab={...} /> inside its ScrollArea and
// uses TAB_META for the rail (labels, icons, chord letters).
import { createElement } from "react";
import type { InspectorTab } from "@/types/agent";

export const TAB_ORDER: InspectorTab[] = [
  "plan", "agents", "files", "memory", "sources", "assets", "approvals", "audit", "device",
];

export const TAB_META: Record<InspectorTab, { label: string; chord: string }> = {
  plan: { label: "Plan", chord: "P" },
  agents: { label: "Agents", chord: "A" },
  files: { label: "Files", chord: "F" },
  memory: { label: "Memory", chord: "M" },
  sources: { label: "Sources", chord: "S" },
  assets: { label: "Assets", chord: "X" },
  approvals: { label: "Approvals", chord: "R" },
  audit: { label: "Audit", chord: "L" },
  device: { label: "Device", chord: "D" },
};

export function InspectorTabContent(props: { tab: InspectorTab }) {
  return createElement("div", { className: "p-3 text-sm text-muted-foreground" }, `${props.tab} (WP-C)`);
}
