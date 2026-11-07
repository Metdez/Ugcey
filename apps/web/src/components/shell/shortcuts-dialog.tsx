import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Kbd } from "@/components/ui/kbd";
import { TAB_META, TAB_ORDER } from "@/components/inspector";
import { useUi } from "@/stores/ui-store";

const GENERAL: [string[], string][] = [
  [["⌘", "K"], "Command palette"], [["⌘", "B"], "Toggle sidebar"], [["⌘", "I"], "Toggle inspector"],
  [["⌘", "/"], "This dialog"], [["⌘", "⇧", "O"], "New chat"], [["/"], "Focus composer"],
  [["Enter"], "Send"], [["⇧", "Enter"], "New line"], [["Esc"], "Stop streaming"], [["⌘", "↵"], "Approve focused card"],
];

const Row = ({ keys, label }: { keys: string[]; label: string }) => (
  <li className="flex items-center justify-between gap-3 py-1">
    <span>{label}</span><span className="flex gap-1">{keys.map((k) => <Kbd key={k}>{k}</Kbd>)}</span>
  </li>
);

export function ShortcutsDialog() {
  const { shortcutsOpen, setShortcuts } = useUi();
  return (
    <Dialog open={shortcutsOpen} onOpenChange={setShortcuts}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>Ctrl replaces ⌘ on Windows and Linux.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-6 text-sm sm:grid-cols-2">
          <section aria-label="General"><ul>{GENERAL.map(([k, l]) => <Row key={l} keys={k} label={l} />)}</ul></section>
          <section aria-label="Go to inspector tab">
            <p className="mb-1 text-xs text-muted-foreground">Press G, then:</p>
            <ul>{TAB_ORDER.map((t) => <Row key={t} keys={[TAB_META[t].chord]} label={TAB_META[t].label} />)}</ul>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
