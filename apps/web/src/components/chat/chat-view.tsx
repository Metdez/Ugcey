import { useLayoutEffect, useRef, useState } from "react";
import { ArrowDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useThread } from "@/stores/thread-store";
import { AssistantMessage } from "./assistant-message";
import { Composer } from "./composer/composer";
import { EmptyThread } from "./empty-thread";
import { RunStatusPill } from "./run-status-pill";
import { messageText, UserMessage } from "./user-message";

export function ChatView() {
  const messages = useThread((s) => s.messages);
  const toolCalls = useThread((s) => s.toolCalls);
  const subagents = useThread((s) => s.subagents);
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const [away, setAway] = useState(false);

  const toBottom = () => { const el = scroller.current; if (el) el.scrollTop = el.scrollHeight; };
  useLayoutEffect(() => { if (stick.current) toBottom(); }, [messages, toolCalls, subagents]);

  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    stick.current = near;
    setAway(!near);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={scroller} onScroll={onScroll} role="log" aria-label="Conversation" className="relative min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col gap-6 px-6 py-6">
          {messages.length === 0 ? <EmptyThread /> : messages.map((m, i) => {
            if (m.role === "user") return <UserMessage key={m.id} message={m} />;
            const prev = messages.slice(0, i).reverse().find((x) => x.role === "user");
            return <AssistantMessage key={m.id} message={m} lastUserText={prev ? messageText(prev) : null} />;
          })}
        </div>
      </div>
      <div className="relative mx-auto w-full max-w-3xl px-6 pb-4">
        {away && (
          <Button variant="outline" size="sm" className="absolute -top-10 left-1/2 -translate-x-1/2 rounded-full shadow-sm"
            onClick={() => { stick.current = true; setAway(false); toBottom(); }}>
            <ArrowDown />Jump to latest
          </Button>
        )}
        <RunStatusPill />
        <Composer />
      </div>
    </div>
  );
}
