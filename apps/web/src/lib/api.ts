// Typed REST client for packages/contracts/src/api.ts. Same-origin; cookie auth.
import type {
  AppConfig, ApprovalRecord, Asset, AuditEntry, ConnectedAccount, Decision, DeviceStatus,
  FileContent, MemoryFile, Post, ThreadState, ThreadSummary, UiEvent,
} from "@ugecy/contracts";
import { readSse } from "./sse";

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err?.error?.code ?? "http_error", err?.error?.message ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

const q = (params: Record<string, string | number | undefined | null>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null) s.set(k, String(v));
  const str = s.toString();
  return str ? `?${str}` : "";
};

export const api = {
  getConfig: () => req<AppConfig>("GET", "/api/config"),
  listThreads: () => req<ThreadSummary[]>("GET", "/api/threads"),
  createThread: (title?: string) => req<ThreadSummary>("POST", "/api/threads", { title }),
  getThread: (id: string) => req<ThreadState>("GET", `/api/threads/${id}`),
  deleteThread: (id: string) => req<{ ok: true }>("DELETE", `/api/threads/${id}`),
  cancel: (id: string) => req<{ ok: boolean }>("POST", `/api/threads/${id}/cancel`),
  stopSubagent: (id: string, callId: string) =>
    req<{ ok: boolean }>("POST", `/api/threads/${id}/subagents/${encodeURIComponent(callId)}/stop`),
  getFile: (id: string, path: string) => req<FileContent>("GET", `/api/threads/${id}/files${q({ path })}`),
  listMemories: () => req<MemoryFile[]>("GET", "/api/memories"),
  putMemory: (path: string, content: string) => req<MemoryFile>("PUT", "/api/memories", { path, content }),
  listAssets: (threadId?: string) => req<Asset[]>("GET", `/api/assets${q({ thread_id: threadId })}`),
  listApprovals: (status?: string) => req<ApprovalRecord[]>("GET", `/api/approvals${q({ status })}`),
  listAudit: (threadId?: string, limit = 100) =>
    req<AuditEntry[]>("GET", `/api/audit${q({ thread_id: threadId, limit })}`),
  listAccounts: () => req<ConnectedAccount[]>("GET", "/api/accounts"),
  listPosts: (threadId?: string) => req<Post[]>("GET", `/api/posts${q({ thread_id: threadId })}`),
  getDevice: () => req<DeviceStatus>("GET", "/api/device"),
  deviceScreenshotUrl: () => `/api/device/screenshot?t=${Date.now()}`,
};

type OnEvent = (e: UiEvent) => void;

async function stream(path: string, body: unknown | undefined, onEvent: OnEvent, signal?: AbortSignal) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { accept: "text/event-stream", ...(body === undefined ? {} : { "content-type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
    signal,
  });
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err?.error?.code ?? "http_error", err?.error?.message ?? res.statusText);
  }
  await readSse(res.body, (_type, data) => onEvent(JSON.parse(data) as UiEvent));
}

export const streams = {
  run: (id: string, message: string, onEvent: OnEvent, signal?: AbortSignal) =>
    stream(`/api/threads/${id}/runs`, { message }, onEvent, signal),
  resume: (id: string, interruptId: string, decisions: Decision[], onEvent: OnEvent, signal?: AbortSignal) =>
    stream(`/api/threads/${id}/resume`, { interrupt_id: interruptId, decisions }, onEvent, signal),
  attach: (id: string, since: number, onEvent: OnEvent, signal?: AbortSignal) =>
    stream(`/api/threads/${id}/stream${q({ since })}`, undefined, onEvent, signal),
};
