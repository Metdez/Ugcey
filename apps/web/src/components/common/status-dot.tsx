import { cn } from "@/lib/utils";

export type Tone = "success" | "warning" | "error" | "info" | "muted";

const TONE: Record<Tone, string> = {
  success: "bg-success", warning: "bg-warning", error: "bg-destructive", info: "bg-info", muted: "bg-muted-foreground/50",
};

/** Color is never the only signal: pass `label` so screen readers get the state. */
export function StatusDot({ tone, label, pulse, className }: { tone: Tone; label?: string; pulse?: boolean; className?: string }) {
  return (
    <span
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn("inline-block size-2 shrink-0 rounded-full", TONE[tone], pulse && "animate-pulse", className)}
    />
  );
}
