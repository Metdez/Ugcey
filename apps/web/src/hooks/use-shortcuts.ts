// Global keyboard shortcuts (UI-SPEC §8). ⌘B is shadcn's built-in; Esc/Enter belong to the composer.
import { useEffect } from "react";
import { TAB_META, TAB_ORDER } from "@/components/inspector";
import { navigateToThread } from "@/hooks/use-thread-route";
import { threadActions, useThreadStore } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";

const inField = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));

export function useShortcuts() {
  useEffect(() => {
    let gAt = 0;
    const onKey = (e: KeyboardEvent) => {
      if (e.isComposing) return;
      const mod = e.metaKey || e.ctrlKey;
      const k = e.key.toLowerCase();
      const ui = useUi.getState();
      if (mod && k === "k") { e.preventDefault(); ui.setPalette(!ui.paletteOpen); return; }
      if (mod && k === "i") { e.preventDefault(); ui.toggleInspector(); return; }
      if (mod && e.key === "/") { e.preventDefault(); ui.setShortcuts(!ui.shortcutsOpen); return; }
      if (mod && e.shiftKey && k === "o") { e.preventDefault(); navigateToThread(null); return; }
      if (e.key === "Escape" && e.target instanceof HTMLTextAreaElement && useThreadStore.getState().status === "streaming") {
        void threadActions.stop();
        return;
      }
      if (mod || e.altKey || inField(e.target)) return;
      if (e.key === "/") {
        const box = document.querySelector<HTMLTextAreaElement>("main textarea");
        if (box) { e.preventDefault(); box.focus(); }
        return;
      }
      if (k === "g") { gAt = Date.now(); return; }
      if (gAt && Date.now() - gAt < 1000) {
        gAt = 0;
        const tab = TAB_ORDER.find((t) => TAB_META[t].chord.toLowerCase() === k);
        if (tab) ui.openInspector(tab);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
