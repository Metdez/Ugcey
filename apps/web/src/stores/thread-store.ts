// Thread store: the only channel between chat and inspector components (FROZEN API:
// `useThread`, `threadActions`). Streams real SSE.
import { toast } from "sonner";
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

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const active = () => ["connecting", "streaming"].includes(get().status);

/** Run one stream. If it drops mid-run, silently reattach to the live run (no error state) until it completes. */
async function run(fn: (signal: AbortSignal) => Promise<void>) {
  abort?.abort();
  const ctl = (abort = new AbortController());
  set({ status: "connecting", error: null });
  try {
    for (let attempt = 0; attempt < 120; attempt++) {
      const id = get().threadId;
      try {
        await (attempt === 0 ? fn(ctl.signal) : streams.attach(id!, get().lastSeq, onEvent, ctl.signal));
      } catch (err) {
        if (ctl.signal.aborted) return;
        if (err instanceof ApiError && err.status === 401) return set({ status: "locked" });
        if (err instanceof ApiError && err.status >= 400 && err.status < 500 && err.status !== 409 && attempt === 0) {
          toast(err.message);
          return set({ status: "idle" });
        }
      }
      if (ctl.signal.aborted || !active() || !id) return; // run.completed / approval arrived
      // Stream ended without run.completed: is the run still going on the server?
      const t = await api.getThread(id).catch(() => null);
      if (t && t.thread.status !== "running") {
        if (abort === ctl) abort = null;
        return threadActions.openThread(id); // finished while disconnected: load the final state
      }
      set({ status: "streaming", progress: "Reconnecting to the live run…" });
      await sleep(Math.min(1000 * (attempt + 1), 5000));
    }
  } finally {
    if (abort === ctl) {
      abort = null;
      if (active()) set({ status: "idle" });
      void useWorkspace.getState().refreshThreads();
    }
  }
}

const userMessage = (text: string): UiMessage => ({
  id: `u-${Date.now()}`, role: "user", agent: "operator", createdAt: new Date().toISOString(),
  parts: [{ type: "text", text }], status: "complete",
});

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
    let id = get().threadId;
    try {
      if (!id) {
        const title = clip(text.trim(), 60);
        id = (await api.createThread(title)).id;
        set({ threadId: id, title });
        setThreadParam(id, "replace");
      }
    } catch (err) {
      return set({ status: err instanceof ApiError && err.status === 401 ? "locked" : "offline" });
    }
    const um = userMessage(text);
    set((s) => ({ messages: [...s.messages, um] }));
    const tid = id;
    await run(async (sig) => {
      try {
        await streams.run(tid, text, onEvent, sig);
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 409)) throw err;
        // The agent is still working on the previous request: reconnect to it instead of erroring.
        set((s) => ({ messages: s.messages.filter((m) => m !== um) }));
        toast("Ugecy is still working on the previous task. Showing it live; press Stop to interrupt, then send again.");
        await streams.attach(tid, get().lastSeq, onEvent, sig);
      }
    });
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
