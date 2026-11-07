import { AlertCircle, CheckCircle2, Loader2, ShieldQuestion } from "lucide-react";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";
import { CodeBlock, TraceLine } from "../primitives/trace";
import { toolFilePath, toolLabel } from "../tool-labels";

const ICON = {
  running: <Loader2 className="animate-spin" />,
  complete: <CheckCircle2 className="text-success" />,
  error: <AlertCircle className="text-destructive" />,
  awaiting_approval: <ShieldQuestion className="text-warning" />,
};

export function ToolCallLine({ toolCallId }: { toolCallId: string }) {
  const call = useThread((s) => s.toolCalls[toolCallId]);
  const openInspector = useUi((s) => s.openInspector);
  if (!call) return null;
  const path = toolFilePath(call.args);
  const hasArgs = Object.keys(call.args).length > 0;
  return (
    <TraceLine icon={ICON[call.status]} title={toolLabel(call.name, call.args, call.status)} running={call.status === "running"}>
      <div className="flex flex-col gap-2 py-1">
        {path && (
          <button type="button" className="w-fit font-mono text-xs text-primary underline"
            onClick={() => openInspector("files", { kind: "file", id: path })}>
            Open {path}
          </button>
        )}
        {hasArgs && <CodeBlock>{JSON.stringify(call.args, null, 2)}</CodeBlock>}
        {call.output && <CodeBlock>{call.output.length > 4000 ? `${call.output.slice(0, 4000)}\n… (truncated)` : call.output}</CodeBlock>}
      </div>
    </TraceLine>
  );
}
