import { Bot } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useThread } from "@/stores/thread-store";
import { AgentRoster } from "@/components/agents/agent-roster";
import { SubagentDetail } from "@/components/agents/subagent-detail";
import { SubagentRunCard } from "@/components/agents/subagent-run-card";
import { useUi } from "@/stores/ui-store";
import { EmptyState } from "../empty";

export default function AgentsTab() {
  const subagents = useThread((s) => s.subagents);
  const toolCalls = useThread((s) => s.toolCalls);
  const focusId = useUi((s) => (s.focus?.kind === "subagent" ? s.focus.id : null));
  const [openId, setOpenId] = useState<string | null>(null);
  useEffect(() => { if (focusId && subagents[focusId]) setOpenId(focusId); }, [focusId, subagents]);

  const runs = useMemo(() => Object.values(subagents).sort((a, b) => b.startedAt.localeCompare(a.startedAt)), [subagents]);
  const open = openId ? subagents[openId] : undefined;
  if (open) {
    return <SubagentDetail run={open} calls={open.toolCallIds.map((id) => toolCalls[id]).filter(Boolean)} onBack={() => setOpenId(null)} />;
  }
  const running = runs.filter((r) => r.status === "running");
  const done = runs.filter((r) => r.status !== "running");
  const list = (title: string, items: typeof runs) => items.length > 0 && (
    <section className="flex flex-col gap-1.5">
      <h3 className="text-xs font-medium text-muted-foreground">{title} ({items.length})</h3>
      {items.map((r) => <SubagentRunCard key={r.id} run={r} focused={focusId === r.id} onOpen={() => setOpenId(r.id)} />)}
    </section>
  );
  return (
    <div className="flex flex-col gap-4 p-3">
      {runs.length ? <>{list("Running", running)}{list("Completed", done)}</>
        : <EmptyState icon={Bot}>No subagents have run in this thread.</EmptyState>}
      <section className="flex flex-col gap-1.5">
        <h3 className="text-xs font-medium text-muted-foreground">Team</h3>
        <AgentRoster />
      </section>
    </div>
  );
}
