// Workspace store: app config, thread list, connected accounts, backend health.
import { create } from "zustand";
import type { AppConfig, ConnectedAccount, ThreadSummary } from "@ugecy/contracts";
import { api, ApiError } from "@/lib/api";

export type Health = "unknown" | "ok" | "offline" | "locked";

interface WorkspaceState {
  config: AppConfig | null;
  threads: ThreadSummary[];
  threadsLoaded: boolean;
  accounts: ConnectedAccount[];
  health: Health;
  boot: () => Promise<void>;
  refreshThreads: () => Promise<void>;
  refreshAccounts: () => Promise<void>;
  setHealth: (h: Health) => void;
  /** Cheap liveness probe used by the health poller. */
  ping: () => Promise<void>;
}

const healthOf = (err: unknown): Health => (err instanceof ApiError && err.status === 401 ? "locked" : "offline");

export const useWorkspace = create<WorkspaceState>((set, get) => ({
  config: null, threads: [], threadsLoaded: false, accounts: [], health: "unknown",
  setHealth: (health) => set({ health }),

  async boot() {
    try {
      set({ config: await api.getConfig(), health: "ok" });
    } catch (err) {
      set({ health: healthOf(err), threadsLoaded: true });
      return;
    }
    await Promise.all([get().refreshThreads(), get().refreshAccounts()]);
  },

  async refreshThreads() {
    try {
      const threads = await api.listThreads();
      set({ threads: threads.toSorted((a, b) => b.updated_at.localeCompare(a.updated_at)), threadsLoaded: true });
    } catch (err) {
      set({ threadsLoaded: true, health: healthOf(err) });
    }
  },

  async refreshAccounts() {
    try { set({ accounts: await api.listAccounts() }); } catch { /* sidebar footer only; health comes from threads */ }
  },

  async ping() {
    try {
      const res = await fetch("/api/healthz", { credentials: "same-origin" });
      if (res.status === 401) return set({ health: "locked" });
      if (!res.ok) return set({ health: "offline" });
      if (get().health !== "ok") { set({ health: "ok" }); void get().boot(); }
    } catch {
      set({ health: "offline" });
    }
  },
}));
