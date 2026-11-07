// Thread store: the only channel between chat and inspector components (FROZEN API:
// `useThread`, `threadActions`). Streams real SSE.
import { create } from "zustand";
import type { Decision, UiEvent } from "@ugecy/contracts";
import { api, ApiError, streams } from "@/lib/api";
import { setThreadParam } from "@/lib/location";
import { clip } from "@/lib/time";
import { emptySnapshot, type ThreadActions, type ThreadSnapshot, type UiMessage } from "@/types/agent";
import { applyEvent } from "./apply-event";
import { historyToUi } from "./history";
import { useWorkspace } from "./workspace-store";

export const useThreadStore = create<ThreadSnapshot>(() => emptySnapshot());

/** Select a slice: `const todos = useThread((s) => s.todos)`. */
export const useThread = <T,>(selector: (s: ThreadSnapshot) => T): T => useThreadStore(selector);

const set = useThreadStore.setState;
const get = useThreadStore.getState;
let abort: AbortController | null = null;

const onEvent = (e: UiEvent) => {
  if (e.thread_id !== get().threadId) return;
  set((s) => applyEvent(s, e));
};

/** Run one stream, mapping transport failures onto status. */
async function run(fn: (signal: AbortSignal) => Promise<void>) {
  abort?.abort();
  const ctl = (abort = new AbortController());
  set({ status: "connecting", error: null });
  try {
    await fn(ctl.signal);
  } catch (err) {
    if (ctl.signal.aborted) return;
    if (err instanceof ApiError && err.status === 401) set({ status: "locked" });
    else if (err instanceof ApiError) set({ status: "error", error: { message: err.message, retryable: err.status >= 500 } });
    else set({ status: "offline" });
  } finally {
    if (abort === ctl) {
      abort = null;
      if (get().status === "connecting" || get().status === "streaming") set({ status: "idle" }); // stream ended without run.completed
      void useWorkspace.getState().refreshThreads();
    }
  }
}

const userMessage = (text: string): UiMessage => ({
  id: `u-${Date.now()}`, role: "user", agent: "operator", createdAt: new Date().toISOString(),
  parts: [{ type: "text", text }], status: "complete",
});

let creatingThread: Promise<string> | null = null;

export const threadActions: ThreadActions = {
  async openThread(id) {
    abort?.abort();
    abort = null;
    if (!id) return set(emptySnapshot());
    set({ ...emptySnapshot(), threadId: id, status: "connecting" });
    try {
      const [st, assets] = await Promise.all([api.getThread(id), api.listAssets(id).catch(() => [])]);
      if (get().threadId !== id) return; // user navigated away
      const hist = historyToUi(st.messages);
      const messages = hist.messages;
      const pa = st.pending_approval;
      if (pa?.status === "pending") {
        const l = messages.findLast((m) => m.role === "assistant");
        if (l) l.parts.push({ type: "approval", approvalId: pa.interrupt_id });
      }
      set({
        ...hist, messages, title: st.thread.title, todos: st.todos, files: st.files, sources: st.sources,
        assets: Object.fromEntries(assets.map((a) => [a.id, a])),
        approvals: pa ? { [pa.interrupt_id]: pa } : {},
        status: pa?.status === "pending" ? "interrupted" : "idle",
      });
      if (st.thread.status === "running") await run((sig) => streams.attach(id, 0, onEvent, sig));
    } catch (err) {
      if (get().threadId !== id) return;
      set({ status: err instanceof ApiError && err.status === 401 ? "locked" : err instanceof ApiError ? "error" : "offline",
        error: err instanceof ApiError ? { message: err.message, retryable: false } : null });
    }
  },

  async send(text) {
    if (get().status === "streaming" || get().status === "connecting") return;
    let id: string;
    try {
      id = await threadActions.ensureThread(text);
    } catch (err) {
      return set({ status: err instanceof ApiError && err.status === 401 ? "locked" : "offline" });
    }
    set((s) => ({ messages: [...s.messages, userMessage(text)] }));
    const tid = id;
    await run((sig) => streams.run(tid, text, onEvent, sig));
  },

  async ensureThread(titleSource) {
    const existing = get().threadId;
    if (existing) return existing;
    // Concurrent callers (two photos picked at once, or send during the first upload) share one creation.
    creatingThread ??= (async () => {
      const title = clip(titleSource.trim(), 60) || "New chat";
      const id = (await api.createThread(title)).id;
      if (!get().threadId) {
        set({ threadId: id, title });
        setThreadParam(id, "replace");
      }
      return id;
    })().finally(() => { creatingThread = null; });
    return creatingThread;
  },

  async stop() {
    const id = get().threadId;
    abort?.abort();
    abort = null;
    set({ status: "idle", progress: null });
    if (id) await api.cancel(id).catch(() => undefined);
  },

  async decide(interruptId, decisions: Decision[]) {
    const id = get().threadId;
    const ap = get().approvals[interruptId];
    if (!id || !ap) return;
    const d = decisions[0]?.type;
    set((s) => ({ approvals: { ...s.approvals, [interruptId]: {
      ...ap, status: d === "reject" ? "rejected" : d === "edit" ? "edited" : "approved", decided_at: new Date().toISOString(),
    } } }));
    await run((sig) => streams.resume(id, interruptId, decisions, onEvent, sig));
  },

  async refreshAssets() {
    const id = get().threadId;
    if (!id) return;
    const list = await api.listAssets(id).catch(() => null);
    if (list && get().threadId === id) set({ assets: Object.fromEntries(list.map((a) => [a.id, a])) });
  },
};
