// Typed client for the Worker-handled /api/glasshand/* routes (packages/contracts/GLASSHAND.md §1).
import type { GlasshandRental, GlasshandStatus } from "@ugecy/contracts";

export type { GlasshandRental, GlasshandStatus };
export interface Rect { x: number; y: number; width: number; height: number }
export interface Geometry { width: number; height: number; viewport: Rect }

async function call(method: string, path: string, body?: unknown): Promise<GlasshandStatus> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error(`Glasshand request failed (${res.status})`);
  return res.json() as Promise<GlasshandStatus>;
}

export const glasshand = {
  connect: () => call("POST", "/api/glasshand/connect"),
  status: () => call("GET", "/api/glasshand/status"),
  select: (rental_id: string) => call("POST", "/api/glasshand/select", { rental_id }),
  disconnect: () => call("POST", "/api/glasshand/disconnect"),
};

/** Same-origin WebSocket URL for the read-only live relay. */
export function streamUrl(loc: Pick<Location, "protocol" | "host"> = window.location): string {
  return `${loc.protocol === "https:" ? "wss:" : "ws:"}//${loc.host}/api/glasshand/stream`;
}

/** drawImage source rect: crop the full HDMI frame to the viewport (clamped to the frame). */
export function cropRect(g: Geometry, bmpW: number, bmpH: number): [number, number, number, number] {
  const v = g.viewport;
  const x = Math.min(Math.max(0, v.x), Math.max(0, bmpW - 1));
  const y = Math.min(Math.max(0, v.y), Math.max(0, bmpH - 1));
  return [x, y, Math.max(1, Math.min(v.width, bmpW - x)), Math.max(1, Math.min(v.height, bmpH - y))];
}

/** No frame this long after the socket says hello: fall back to snapshots. */
export const FIRST_FRAME_MS = 3000;
/** Frames stopped this long: fall back to snapshots until they resume. */
export const STALE_FRAME_MS = 5000;

export type FeedMode = "connecting" | "live" | "snapshots";
export interface FeedInput {
  /** When the relay's hello arrived, or null while the socket is not live. */
  helloAt: number | null;
  lastFrameAt: number | null;
  /** false once Glasshand reports `capture_status` unavailable. */
  captureAvailable: boolean;
  paused: boolean;
  now: number;
}
/** Show the live canvas only while it is actually receiving frames; otherwise polled snapshots. */
export function feedMode({ helloAt, lastFrameAt, captureAvailable, paused, now }: FeedInput): FeedMode {
  if (helloAt === null || !captureAvailable) return "snapshots";
  if (lastFrameAt !== null && (paused || now - lastFrameAt < STALE_FRAME_MS)) return "live";
  if (lastFrameAt === null && now - helloAt < FIRST_FRAME_MS) return "connecting";
  return "snapshots";
}

export type ViewState ="disconnected" | "pending" | "connected" | "failed";
export function viewState(s: GlasshandStatus | null | undefined): ViewState {
  switch (s?.state) {
    case "pending": return "pending";
    case "connected": return "connected";
    case "denied": case "expired": case "error": return "failed";
    default: return "disconnected";
  }
}

/** m:ss remaining until an ISO time; "Expired" once reached. */
export function formatCountdown(expiresAt: string | undefined, now = Date.now()): string {
  const ms = expiresAt ? Date.parse(expiresAt) - now : NaN;
  if (!Number.isFinite(ms) || ms <= 0) return "Expired";
  const t = Math.ceil(ms / 1000);
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}

export const rentalReady = (r: GlasshandRental) => r.deviceReady && (r.status === "active" || r.status === "grace");
