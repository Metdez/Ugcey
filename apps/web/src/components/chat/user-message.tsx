import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { UiMessage } from "@/types/agent";

export const messageText = (m: UiMessage) =>
  m.parts.flatMap((p) => (p.type === "text" ? [p.text] : [])).join("\n\n");

export function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button variant="ghost" size="icon-sm" aria-label="Copy"
      onClick={() => { void navigator.clipboard?.writeText(text); setDone(true); setTimeout(() => setDone(false), 2000); }}>
      {done ? <Check /> : <Copy />}
    </Button>
  );
}

export function UserMessage({ message }: { message: UiMessage }) {
  const text = messageText(message);
  return (
    <div className="group flex flex-col items-end gap-1">
      <div className="max-w-[85%] rounded-2xl bg-muted px-4 py-2 text-[15px] whitespace-pre-wrap">{text}</div>
      <div className="opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100"><CopyButton text={text} /></div>
    </div>
  );
}
