// GET /api/glasshand/stream: read-only relay of the rental's control WebSocket to the browser.
import type { Env } from "../env";
import { API, type GlasshandRuntime } from "./types";

export interface Sock {
  send(d: string | ArrayBuffer | ArrayBufferView): void;
  close(code?: number, reason?: string): void;
  addEventListener(t: string, fn: (e: any) => void): void;
}

const safe = (fn: () => void) => {
  try {
    fn();
  } catch {
    // peer already closed
  }
};
const closeCode = (c: unknown) => (typeof c === "number" && (c === 1000 || (c >= 3000 && c <= 4999)) ? c : 1000);

const json = (d: string): Record<string, unknown> | null => {
  try {
    const m: unknown = JSON.parse(d);
    return m && typeof m === "object" ? (m as Record<string, unknown>) : null;
  } catch {
    return null;
  }
};

/**
 * Wire an upstream control socket to the browser socket. Frame headers reach the browser, which acks each
 * frame only after drawing it (Glasshand's flow control). A validated `frame_ack` is the only client message
 * forwarded upstream, so the viewer stays read-only.
 */
export function pipe(up: Sock, client: Sock): void {
  up.addEventListener("message", (ev) => {
    const d = ev.data;
    if (typeof d !== "string") return safe(() => client.send(d)); // full HDMI JPEG, right after its frame header
    const m = json(d);
    if (m?.type === "hello") safe(() => client.send(JSON.stringify({ type: "hello", geometry: m.geometry })));
    else if (m?.type === "frame" && Number.isSafeInteger(m.frameId)) safe(() => client.send(JSON.stringify({ type: "frame", frameId: m.frameId })));
    else if (m?.type === "error") safe(() => client.send(JSON.stringify({ type: "error", message: String(m.message ?? m.error ?? "error") })));
  });
  client.addEventListener("message", (ev) => {
    const m = typeof ev.data === "string" ? json(ev.data) : null;
    if (m?.type === "frame_ack" && Number.isSafeInteger(m.frameId)) safe(() => up.send(JSON.stringify({ v: 1, type: "frame_ack", frameId: m.frameId })));
  });
  // close() throws on codes other than 1000 or 3000-4999, and safe() would hide that, leaving the peer open.
  const end = (to: Sock) => (ev: { code?: number; reason?: string }) => safe(() => to.close(closeCode(ev?.code), String(ev?.reason ?? "").slice(0, 100)));
  up.addEventListener("close", end(client));
  up.addEventListener("error", () => safe(() => client.close(4502, "upstream error")));
  client.addEventListener("close", end(up));
  client.addEventListener("error", () => safe(() => up.close(1000, "client error")));
}

function refused(code: number, reason: string): Response {
  const [client, server] = Object.values(new WebSocketPair());
  server!.accept();
  server!.close(code, reason);
  return new Response(null, { status: 101, webSocket: client });
}

/** The bearer token may only ever be sent to Glasshand's own hosts over TLS. */
export function isGlasshandUrl(raw: string): boolean {
  try {
    const u = new URL(raw);
    const host = u.hostname.toLowerCase();
    return (u.protocol === "wss:" || u.protocol === "https:") && (host === "glasshand.com" || host.endsWith(".glasshand.com"));
  } catch {
    return false;
  }
}

async function connectionUrl(rt: GlasshandRuntime, rentalId: string, f: typeof fetch): Promise<{ controlUrl: string; token: string } | null> {
  let token = await rt.glasshandToken();
  for (let i = 0; token && i < 2; i++) {
    const r = await f(`${API}/rentals/${encodeURIComponent(rentalId)}/connection`, { headers: { authorization: `Bearer ${token}`, accept: "application/json" } });
    if (r.status === 401) {
      await r.body?.cancel();
      token = await rt.glasshandToken(token);
      continue;
    }
    if (!r.ok) return null;
    const j = (await r.json()) as { controlUrl?: string };
    return j.controlUrl && isGlasshandUrl(j.controlUrl) ? { controlUrl: j.controlUrl, token } : null;
  }
  return null;
}

export async function streamRoute(req: Request, env: Env, rt: GlasshandRuntime, f: typeof fetch = fetch): Promise<Response> {
  if (req.headers.get("upgrade")?.toLowerCase() !== "websocket") return new Response("expected websocket", { status: 426 });
  const st = await rt.glasshandState();
  if (!st.connected) return refused(4401, "glasshand not connected");
  if (!st.selected_rental_id) return refused(4404, "no rental selected");
  let conn: Awaited<ReturnType<typeof connectionUrl>>;
  try {
    conn = await connectionUrl(rt, st.selected_rental_id, f);
  } catch {
    return refused(4502, "glasshand unreachable");
  }
  if (!conn) return refused(4404, "no connection for rental");
  let up: WebSocket | null | undefined;
  try {
    const url = conn.controlUrl.replace(/^wss:/, "https:").replace(/^ws:/, "http:");
    up = (await f(url, { headers: { Upgrade: "websocket", Authorization: `Bearer ${conn.token}` } })).webSocket;
  } catch {
    return refused(4502, "glasshand unreachable");
  }
  if (!up) return refused(4502, "upstream refused websocket");
  const [client, server] = Object.values(new WebSocketPair()) as [WebSocket, WebSocket];
  server.accept();
  up.accept();
  pipe(up, server);
  return new Response(null, { status: 101, webSocket: client });
}
