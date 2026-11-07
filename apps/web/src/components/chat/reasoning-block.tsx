import { Brain } from "lucide-react";
import { TraceLine } from "./primitives/trace";

export function ReasoningBlock({ text, streaming }: { text: string; streaming: boolean }) {
  return (
    <TraceLine icon={<Brain />} title={streaming ? "Thinking…" : "Thought"} running={streaming}>
      <p className="py-1 text-[13px] whitespace-pre-wrap text-muted-foreground">{text}</p>
    </TraceLine>
  );
}
