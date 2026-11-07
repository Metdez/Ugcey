import type { LucideIcon } from "lucide-react";

export function EmptyState({ icon: Icon, children }: { icon: LucideIcon; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-12 text-center text-muted-foreground">
      <Icon className="size-6" aria-hidden />
      <p className="max-w-[28ch] text-[13px] leading-[18px]">{children}</p>
    </div>
  );
}
