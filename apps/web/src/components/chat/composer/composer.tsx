import { useEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { threadActions, useThread } from "@/stores/thread-store";
import { useProductPhotos } from "./product-photos";
import { matchSlash } from "./slash-commands";

export function Composer() {
  const status = useThread((s) => s.status);
  const [draft, setDraft] = useState("");
  const [active, setActive] = useState(0);
  const ref = useRef<HTMLTextAreaElement>(null);
  const disabled = status === "locked" || status === "offline";
  const streaming = status === "streaming" || status === "connecting";
  const menu = matchSlash(draft);
  const product = useProductPhotos(() => draft);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 8 * 24 + 16)}px`; // 8 rows max
  }, [draft]);

  const canSend = !!(draft.trim() || product.line) && !product.uploading;
  const send = () => {
    const text = [draft.trim(), product.line].filter(Boolean).join("\n\n");
    if (!canSend || !text || disabled || streaming) return;
    setDraft("");
    product.clear();
    void threadActions.send(text);
  };
  const pick = (i: number) => { setDraft(menu[i].template); setActive(0); ref.current?.focus(); };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing) return;
    if (menu.length) {
      if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => (a + 1) % menu.length); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => (a - 1 + menu.length) % menu.length); return; }
      if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); pick(Math.min(active, menu.length - 1)); return; }
    }
    if (e.key === "Escape" && streaming) { e.preventDefault(); void threadActions.stop(); return; }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <div className="relative">
      {menu.length > 0 && (
        <ul role="listbox" aria-label="Commands" className="absolute bottom-full mb-2 w-full overflow-hidden rounded-lg border bg-popover p-1 shadow-md">
          {menu.map((c, i) => (
            <li key={c.cmd} role="option" aria-selected={i === active}
              className={`flex cursor-pointer items-center justify-between rounded-md px-2 py-1.5 text-[13px] ${i === active ? "bg-accent" : ""}`}
              onMouseDown={(e) => { e.preventDefault(); pick(i); }}>
              <span className="font-mono">{c.cmd}</span><span className="text-muted-foreground">{c.hint}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-col rounded-2xl border bg-card p-2 focus-within:ring-2 focus-within:ring-ring/50">
        {product.chips}
        <div className="flex items-end gap-1">
          {product.pickerButton(disabled)}
          <Textarea ref={ref} rows={1} value={draft} disabled={disabled} autoFocus
            onChange={(e) => { setDraft(e.target.value); setActive(0); }} onKeyDown={onKeyDown}
            aria-label="Message Ugecy"
            placeholder={status === "offline" ? "You're offline — messages can't be sent." : "Ask Ugecy to research, script, generate or publish…"}
            className="max-h-52 min-h-8 resize-none border-0 bg-transparent px-2 py-1 shadow-none focus-visible:ring-0 dark:bg-transparent" />
          {streaming ? (
            <Button size="icon" variant="secondary" aria-label="Stop" onClick={() => void threadActions.stop()}><Square /></Button>
          ) : (
            <Button size="icon" aria-label="Send" disabled={disabled || !canSend} onClick={send}><ArrowUp /></Button>
          )}
        </div>
      </div>
    </div>
  );
}
