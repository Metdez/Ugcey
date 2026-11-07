import { useState, type ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

/** One trace line: icon + sentence title (+ optional meta), expandable body. */
export function TraceLine(props: {
  icon: ReactNode; title: ReactNode; meta?: ReactNode; children?: ReactNode;
  running?: boolean; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(props.defaultOpen ?? false);
  const head = (
    <span className="flex min-w-0 items-center gap-2 text-[13px] text-muted-foreground">
      <span className="flex size-3.5 shrink-0 items-center justify-center [&>svg]:size-3.5">{props.icon}</span>
      <span className={cn("truncate", props.running && "animate-pulse text-foreground")}>{props.title}</span>
      {props.meta}
    </span>
  );
  if (!props.children) return <div className="py-1">{head}</div>;
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="group flex w-full items-center gap-1 rounded-md py-1 text-left hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
        {head}
        <ChevronRight className="size-3 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
      </CollapsibleTrigger>
      <CollapsibleContent className="ml-1.5 border-l pl-4">{props.children}</CollapsibleContent>
    </Collapsible>
  );
}

export function CodeBlock({ children, className }: { children: string; className?: string }) {
  return (
    <pre className={cn("max-h-64 overflow-auto rounded-md bg-muted p-2 font-mono text-[12.5px] leading-[1.6] whitespace-pre-wrap break-words", className)}>
      {children}
    </pre>
  );
}

export function AgentDot({ color }: { color: string }) {
  return <span aria-hidden className="inline-block size-2 shrink-0 rounded-full" style={{ background: color }} />;
}
