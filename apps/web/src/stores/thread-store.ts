// Thread store: the only channel between chat and inspector components.
// FROZEN API (WP-B/WP-C import only `useThread`, `threadActions`). WP-A owns the implementation:
// replace the TODO bodies with real logic (streams + apply-event reducer + mock adapter).
import { create } from "zustand";
import { emptySnapshot, type ThreadActions, type ThreadSnapshot } from "@/types/agent";

export const useThreadStore = create<ThreadSnapshot>(() => emptySnapshot());

/** Select a slice: `const todos = useThread((s) => s.todos)`. */
export const useThread = <T,>(selector: (s: ThreadSnapshot) => T): T => useThreadStore(selector);

export const threadActions: ThreadActions = {
  async openThread(_id) {
    useThreadStore.setState(emptySnapshot()); // TODO(WP-A)
  },
  async send(_text) {
    // TODO(WP-A): create thread if needed, push user message, streams.run(), applyEvent
  },
  async stop() {
    // TODO(WP-A)
  },
  async decide(_interruptId, _decisions) {
    // TODO(WP-A): streams.resume(); mark approval status
  },
  async refreshAssets() {
    // TODO(WP-A)
  },
};
