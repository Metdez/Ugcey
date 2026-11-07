// REST contract between apps/web and the backend. The Worker proxies every /api/* path
// (except /api/edge/*) to the Python service unchanged. All bodies are JSON.
// Errors: non-2xx with { "error": { "code": string, "message": string } }.
// Auth: none. The app is public; there is no access key or cookie gate.
import type {
  AppConfig, ApprovalRecord, Asset, AuditEntry, ConnectedAccount, Decision, DeviceStatus,
  FileContent, MemoryFile, Post, ThreadState, ThreadSummary,
} from "./models";

export interface ApiError {
  error: { code: string; message: string };
}

export interface HealthResponse {
  ok: boolean;
  service: string;
  version: string;
}

export interface CreateThreadRequest {
  title?: string;
}
export interface RunRequest {
  message: string;
}
export interface ResumeRequest {
  interrupt_id: string;
  /** One decision per ApprovalRequest, same order. */
  decisions: Decision[];
}
export interface PutMemoryRequest {
  path: string; // must start with /memories/
  content: string;
}

/**
 * Endpoint table (method path -> response):
 *  GET    /api/healthz                         -> HealthResponse
 *  GET    /api/config                          -> AppConfig
 *  GET    /api/threads                         -> ThreadSummary[]
 *  POST   /api/threads        CreateThreadRequest -> ThreadSummary
 *  GET    /api/threads/:id                     -> ThreadState
 *  DELETE /api/threads/:id                     -> { ok: true }
 *  POST   /api/threads/:id/runs   RunRequest   -> text/event-stream of UiEvent
 *  POST   /api/threads/:id/resume ResumeRequest-> text/event-stream of UiEvent
 *  GET    /api/threads/:id/stream?since=<seq>  -> text/event-stream: replays buffered events of the
 *                                                 active/last run with seq > since, then live (reconnect)
 *  POST   /api/threads/:id/cancel              -> { ok: boolean }
 *  GET    /api/threads/:id/files?path=/a.md    -> FileContent
 *  GET    /api/memories                        -> MemoryFile[]
 *  PUT    /api/memories   PutMemoryRequest     -> MemoryFile
 *  GET    /api/assets?thread_id=               -> Asset[]
 *  GET    /api/approvals?status=pending        -> ApprovalRecord[]
 *  GET    /api/audit?thread_id=&limit=100      -> AuditEntry[]
 *  GET    /api/accounts                        -> ConnectedAccount[]
 *  GET    /api/posts?thread_id=                -> Post[]
 *  GET    /api/device                          -> DeviceStatus
 *  GET    /api/device/screenshot               -> image/jpeg (latest frame)
 */
export interface ApiResponses {
  "GET /api/healthz": HealthResponse;
  "GET /api/config": AppConfig;
  "GET /api/threads": ThreadSummary[];
  "POST /api/threads": ThreadSummary;
  "GET /api/threads/:id": ThreadState;
  "DELETE /api/threads/:id": { ok: true };
  "POST /api/threads/:id/cancel": { ok: boolean };
  "GET /api/threads/:id/files": FileContent;
  "GET /api/memories": MemoryFile[];
  "PUT /api/memories": MemoryFile;
  "GET /api/assets": Asset[];
  "GET /api/approvals": ApprovalRecord[];
  "GET /api/audit": AuditEntry[];
  "GET /api/accounts": ConnectedAccount[];
  "GET /api/posts": Post[];
  "GET /api/device": DeviceStatus;
}
