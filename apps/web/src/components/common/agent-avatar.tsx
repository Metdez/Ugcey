import { Bot, Clapperboard, Megaphone, PenTool, Search, ShieldCheck, Smartphone, BarChart3, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Kind = "orchestrator" | "research" | "creative" | "production" | "publishing" | "device" | "analytics";

const KIND: Record<string, Kind> = {
  "research-analyst": "research", "creative-strategist": "creative", "compliance-critic": "creative",
  "production-coordinator": "production", "publishing-coordinator": "publishing",
  "device-operator": "device", "analytics-analyst": "analytics", orchestrator: "orchestrator",
};

const ICON: Record<Kind, LucideIcon> = {
  orchestrator: Bot, research: Search, creative: PenTool, production: Clapperboard,
  publishing: Megaphone, device: Smartphone, analytics: BarChart3,
};

// Literal class names so Tailwind can see them.
const TONE: Record<Kind, string> = {
  orchestrator: "bg-agent-orchestrator/15 text-agent-orchestrator ring-agent-orchestrator/40",
  research: "bg-agent-research/15 text-agent-research ring-agent-research/40",
  creative: "bg-agent-creative/15 text-agent-creative ring-agent-creative/40",
  production: "bg-agent-production/15 text-agent-production ring-agent-production/40",
  publishing: "bg-agent-publishing/15 text-agent-publishing ring-agent-publishing/40",
  device: "bg-agent-device/15 text-agent-device ring-agent-device/40",
  analytics: "bg-agent-analytics/15 text-agent-analytics ring-agent-analytics/40",
};

export const agentKind = (name: string): Kind => KIND[name] ?? "orchestrator";

/** `kind` is an agent name ("research-analyst") or a color kind ("research"). */
export function AgentAvatar({ kind, size = "md", className }: { kind: string; size?: "sm" | "md" | "lg"; className?: string }) {
  const k = (kind in TONE ? kind : agentKind(kind)) as Kind;
  const Icon = kind === "compliance-critic" ? ShieldCheck : ICON[k];
  return (
    <span
      aria-hidden
      data-agent={kind}
      className={cn("inline-flex shrink-0 items-center justify-center rounded-full ring-1", TONE[k],
        size === "sm" ? "size-5 [&_svg]:size-3" : size === "lg" ? "size-9 [&_svg]:size-5" : "size-7 [&_svg]:size-4", className)}
    >
      <Icon />
    </span>
  );
}
