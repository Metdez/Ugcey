import { ShieldCheck } from "lucide-react";
import { useMemo } from "react";
import { ApprovalCard } from "@/components/chat";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";
import { EmptyState } from "../empty";
import { useFlash, usePoll } from "../hooks";
import { timeAgo } from "../lib";

function Pending({ id, focused }: { id: string; focused: boolean }) {
  const flash = useFlash(focused);
  return <div ref={flash.ref} className={`rounded-lg ${flash.className}`}><ApprovalCard approvalId={id} variant="panel" /></div>;
}

export default function ApprovalsTab() {
  const approvals = useThread((s) => s.approvals);
  const focusId = useUi((s) => (s.focus?.kind === "approval" ? s.focus.id : null));
  const { data: all } = usePoll(() => api.listApprovals(), 10_000);
  const pending = useMemo(() => Object.values(approvals).filter((a) => a.status === "pending"), [approvals]);
  const history = useMemo(() => {
    const m = new Map((all ?? []).map((a) => [a.interrupt_id, a]));
    for (const a of Object.values(approvals)) m.set(a.interrupt_id, a); // store is fresher
    return [...m.values()].filter((a) => a.status !== "pending")
      .sort((a, b) => (b.decided_at ?? b.created_at).localeCompare(a.decided_at ?? a.created_at));
  }, [all, approvals]);

  if (!pending.length && !history.length) {
    return <EmptyState icon={ShieldCheck}>Nothing needs your approval. Publishing, spending and device actions always stop here first.</EmptyState>;
  }
  return (
    <div className="flex flex-col gap-4 p-3">
      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-medium text-muted-foreground">Pending ({pending.length})</h3>
        {pending.map((a) => <Pending key={a.interrupt_id} id={a.interrupt_id} focused={focusId === a.interrupt_id} />)}
        {!pending.length && <p className="text-xs text-muted-foreground">Nothing waiting.</p>}
      </section>
      {history.length > 0 && (
        <section className="flex flex-col gap-1.5">
          <h3 className="text-xs font-medium text-muted-foreground">History ({history.length})</h3>
          <ul className="flex flex-col gap-1.5">
            {history.map((a) => (
              <li key={a.interrupt_id} className="flex flex-col gap-1 rounded-lg border p-2.5 text-xs">
                <span className="flex items-center gap-2">
                  <Badge variant={a.status === "rejected" ? "destructive" : a.status === "expired" ? "outline" : "secondary"}>{a.status}</Badge>
                  <span className="text-muted-foreground">{timeAgo(a.decided_at ?? a.created_at)}</span>
                </span>
                <span className="font-mono">{a.requests.map((r) => r.tool).join(", ")}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
