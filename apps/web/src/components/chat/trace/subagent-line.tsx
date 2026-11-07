import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";
import { AgentDot, TraceLine } from "../primitives/trace";
import { MarkdownContent } from "../markdown-content";
import { agentColor, agentLabel } from "../tool-labels";
import { ToolCallLine } from "./tool-call-line";

export function SubagentLine({ subagentId }: { subagentId: string }) {
  const sub = useThread((s) => s.subagents[subagentId]);
  const openInspector = useUi((s) => s.openInspector);
  const [more, setMore] = useState(false);
  if (!sub) return null;
  const label = agentLabel(sub.name);
  const running = sub.status === "running";
  const title = running ? `${label} is working…` : sub.status === "error" ? `${label} failed` : `Ran ${label.toLowerCase()}`;
  return (
    <TraceLine icon={<AgentDot color={agentColor(sub.name)} />} title={title} running={running}
      meta={sub.model && <Badge variant="outline" className="rounded-sm text-[11px]">{sub.model}</Badge>}>
      <div className="flex flex-col gap-2 py-1">
        <p className="text-[13px] text-muted-foreground">{sub.task}</p>
        {sub.toolCallIds.map((id) => <ToolCallLine key={id} toolCallId={id} />)}
        {stripJson(sub.text) && <MarkdownContent text={stripJson(sub.text)} streaming={running} />}
        {sub.result && (
          <div>
            <div className={more ? "" : "line-clamp-6"}><MarkdownContent text={sub.result} /></div>
            <Button variant="link" size="xs" onClick={() => setMore(!more)}>{more ? "Show less" : "Show more"}</Button>
          </div>
        )}
        <Button variant="outline" size="xs" className="w-fit"
          onClick={() => openInspector("agents", { kind: "subagent", id: sub.id })}>Open in Agents</Button>
      </div>
    </TraceLine>
  );
}

/** Remove raw JSON objects (e.g. echoed screen descriptions) from narration so only the prose shows. */
export function stripJson(text: string): string {
  let out = "";
  for (let i = 0; i < text.length; i++) {
    if (text[i] === "{" && /^\{\s*"/.test(text.slice(i, i + 3))) {
      let depth = 0, j = i, inStr = false;
      for (; j < text.length; j++) {
        const c = text[j];
        if (inStr) { if (c === "\\") j++; else if (c === '"') inStr = false; continue; }
        if (c === '"') inStr = true; else if (c === "{") depth++; else if (c === "}" && --depth === 0) break;
      }
      i = j; out += " ";
      continue;
    }
    out += text[i];
  }
  return out.replace(/[ \t]{2,}/g, " ").trim();
}
