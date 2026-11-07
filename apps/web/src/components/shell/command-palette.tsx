import { useState, type ReactNode } from "react";
import { MessageSquare, PanelRight, Plus, Sparkles, Square, Sun } from "lucide-react";
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator,
} from "@/components/ui/command";
import { TAB_META, TAB_ORDER } from "@/components/inspector";
import { navigateToThread } from "@/hooks/use-thread-route";
import { getTheme, setTheme } from "@/lib/theme";
import { threadActions } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";
import { useWorkspace } from "@/stores/workspace-store";
import { TAB_ICONS } from "./inspector-icons";

export function CommandPalette() {
  const { paletteOpen, setPalette, openInspector, toggleInspector } = useUi();
  const config = useWorkspace((s) => s.config);
  const threads = useWorkspace((s) => s.threads);
  const [q, setQ] = useState("");

  const run = (fn: () => void) => () => { setPalette(false); setQ(""); fn(); };
  const ask = (text: string) => run(() => void threadActions.send(text));
  const Item = ({ icon, children, onSelect, value }: { icon: ReactNode; children: ReactNode; onSelect: () => void; value?: string }) => (
    <CommandItem value={value} onSelect={onSelect}>{icon}{children}</CommandItem>
  );

  return (
    <CommandDialog open={paletteOpen} onOpenChange={(o) => { setPalette(o); if (!o) setQ(""); }}
      title="Command palette" description="Ask Ugecy, open a chat, or jump to an inspector tab" className="max-w-xl">
      <CommandInput placeholder="Ask Ugecy or search commands…" value={q} onValueChange={setQ} />
      <CommandList>
        <CommandEmpty>No matches.</CommandEmpty>
        {q.trim() && (
          <CommandGroup heading="Ask Ugecy">
            <Item value={`ask ${q}`} icon={<Sparkles />} onSelect={ask(q.trim())}>Ask Ugecy: {q.trim()}</Item>
          </CommandGroup>
        )}
        {!q.trim() && config && (
          <CommandGroup heading="Ask Ugecy">
            {config.starter_prompts.slice(0, 6).map((p) => <Item key={p} icon={<Sparkles />} onSelect={ask(p)}>{p}</Item>)}
          </CommandGroup>
        )}
        <CommandSeparator />
        <CommandGroup heading="Chats">
          {threads.slice(0, 20).map((t) => (
            <Item key={t.id} value={`chat ${t.title} ${t.id}`} icon={<MessageSquare />} onSelect={run(() => navigateToThread(t.id))}>{t.title}</Item>
          ))}
        </CommandGroup>
        <CommandGroup heading="Inspector">
          {TAB_ORDER.map((tab) => {
            const Icon = TAB_ICONS[tab];
            return <Item key={tab} value={`inspector ${TAB_META[tab].label}`} icon={<Icon />} onSelect={run(() => openInspector(tab))}>{TAB_META[tab].label}</Item>;
          })}
        </CommandGroup>
        <CommandGroup heading="Actions">
          <Item icon={<Plus />} onSelect={run(() => navigateToThread(null))}>New chat</Item>
          <Item icon={<Square />} onSelect={run(() => void threadActions.stop())}>Stop run</Item>
          <Item icon={<PanelRight />} onSelect={run(toggleInspector)}>Toggle inspector</Item>
          <Item icon={<Sun />} onSelect={run(() => setTheme(getTheme() === "dark" ? "light" : "dark"))}>Toggle theme</Item>
        </CommandGroup>
      </CommandList>
      <div className="flex gap-4 border-t px-3 py-2 text-xs text-muted-foreground">
        <span>↑↓ Navigate</span><span>↵ Select</span><span>Esc Close</span>
      </div>
    </CommandDialog>
  );
}
