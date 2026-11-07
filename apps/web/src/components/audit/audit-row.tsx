import { Bot, CircleAlert, CircleCheck, CircleDashed, CircleX, Cog, User } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import type { AuditEntry } from "@/types/agent";
import { useFlash } from "../inspector/hooks";
import { hhmmss } from "../inspector/lib";

const ACTOR = { agent: Bot, operator: User, system: Cog } as const;
const STATUS = {
  ok: [CircleCheck, "text-success", "OK"], error: [CircleX, "text-destructive", "Error"],
  pending: [CircleDashed, "text-warning", "Pending"], rejected: [CircleAlert, "text-destructive", "Rejected"],
} as const;

export function AuditRow({ row, focused }: { row: AuditEntry; focused: boolean }) {
  const [open, setOpen] = useState(false);
  const flash = useFlash(focused);
  const Actor = ACTOR[row.actor];
  const [Status, color, label] = STATUS[row.status];
  return (
    <li ref={flash.ref as React.Ref<HTMLLIElement>} className={`rounded-md border-b [content-visibility:auto] ${flash.className}`}>
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-x-2 gap-y-0.5 px-2 py-1.5 text-left text-xs hover:bg-accent">
        <span className="font-mono tabular-nums text-muted-foreground">{hhmmss(row.ts)}</span>
        <Actor className="size-3.5 text-muted-foreground" aria-label={row.actor} />
        {row.agent && <span className="text-muted-foreground">{row.agent}</span>}
        <Badge variant="outline" className="font-mono">{row.action}</Badge>
        {row.tool && <span className="truncate font-mono">{row.tool}</span>}
        <Status className={`ml-auto size-3.5 ${color}`} aria-label={label} />
      </button>
      {open && <pre className="mx-2 mb-2 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-2 font-mono text-[11.5px]">{row.detail || "(no detail)"}</pre>}
    </li>
  );
}
