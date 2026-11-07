import { ArrowLeft } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SubagentRunView, ToolCallView } from "@/types/agent";
import { duration } from "../inspector/lib";
import { StatusIcon } from "./subagent-run-card";

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="flex flex-col gap-1">
    <h3 className="text-xs font-medium text-muted-foreground">{title}</h3>
    {children}
  </section>
);

export function SubagentDetail({ run, calls, onBack }: { run: SubagentRunView; calls: ToolCallView[]; onBack: () => void }) {
  return (
    <div className="flex flex-col gap-3 p-3">
      <Button variant="ghost" size="sm" className="-ml-2 w-fit" onClick={onBack}><ArrowLeft />All agents</Button>
      <div className="flex items-center gap-2">
        <h2 className="flex-1 truncate text-sm font-semibold">{run.name}</h2>
        <StatusIcon status={run.status} />
        <span className="text-xs tabular-nums text-muted-foreground">{duration(run.startedAt, run.endedAt)}</span>
      </div>
      {run.model && <Badge variant="outline" className="w-fit font-mono">{run.model}</Badge>}
      <Section title="Task"><p className="text-[13px]">{run.task}</p></Section>
      <Section title={`Tool calls (${calls.length})`}>
        <ul className="flex flex-col gap-1">
          {calls.map((c) => (
            <li key={c.id} className="flex items-center gap-2 rounded-md border px-2 py-1 text-xs">
              <span className="flex-1 truncate font-mono">{c.name}</span>
              <Badge variant={c.status === "error" ? "destructive" : "secondary"}>{c.status.replace("_", " ")}</Badge>
            </li>
          ))}
          {!calls.length && <li className="text-xs text-muted-foreground">No tool calls yet.</li>}
        </ul>
      </Section>
      {run.text && <Section title="Streamed text"><p className="whitespace-pre-wrap text-[13px] text-muted-foreground">{run.text}</p></Section>}
      {run.result && (
        <Section title="Result">
          <div className="prose-sm text-[13px] [&_li]:ml-4 [&_li]:list-disc [&_p]:my-1"><ReactMarkdown>{run.result}</ReactMarkdown></div>
        </Section>
      )}
    </div>
  );
}
