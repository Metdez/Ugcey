import { AssetPreviewGrid } from "../assets/asset-preview-grid";
import { ApprovalCard } from "../approvals/approval-card";
import { InlinePlanCard } from "./inline-plan-card";
import { MarkdownContent } from "./markdown-content";
import { AgentDot } from "./primitives/trace";
import { ReasoningBlock } from "./reasoning-block";
import { SubagentLine } from "./trace/subagent-line";
import { ToolCallLine } from "./trace/tool-call-line";
import { TurnError } from "./turn-error";
import { agentColor } from "./tool-labels";
import { CopyButton, messageText } from "./user-message";
import type { UiMessage } from "@/types/agent";

export function AssistantMessage({ message, lastUserText }: { message: UiMessage; lastUserText: string | null }) {
  const streaming = message.status === "streaming";
  const lastIdx = message.parts.length - 1;
  return (
    <article className="flex flex-col gap-2" aria-label="Assistant message">
      <header className="flex items-center gap-2 text-xs text-muted-foreground">
        <AgentDot color={agentColor(message.agent)} />
        <span className="font-medium text-foreground">Ugecy</span>
        {message.model && <span className="font-mono">{message.model}</span>}
        <time dateTime={message.createdAt}>{new Date(message.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>
      </header>
      {message.parts.map((p, i) => {
        switch (p.type) {
          case "text": return <MarkdownContent key={i} text={p.text} streaming={streaming && i === lastIdx} />;
          case "reasoning": return <ReasoningBlock key={i} text={p.text} streaming={streaming && i === lastIdx} />;
          case "tool": return <ToolCallLine key={i} toolCallId={p.toolCallId} />;
          case "subagent": return <SubagentLine key={i} subagentId={p.subagentId} />;
          case "plan": return <InlinePlanCard key={i} />;
          case "approval": return <ApprovalCard key={i} approvalId={p.approvalId} variant="inline" />;
          case "assets": return <AssetPreviewGrid key={i} assetIds={p.assetIds} />;
          case "error": return <TurnError key={i} message={p.message} retryable={p.retryable} lastUserText={lastUserText} />;
        }
      })}
      {!streaming && <footer className="-ml-2"><CopyButton text={messageText(message)} /></footer>}
    </article>
  );
}
