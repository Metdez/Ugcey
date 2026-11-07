// GET /api/glasshand/stream: read-only relay of the rental's control WebSocket to the browser.
import type { Env } from "../env";
import { API, type GlasshandRuntime } from "./types";

export interface Sock {
  send(d: string | ArrayBuffer | ArrayBufferView): void;
  close(code?: number, reason?: string): void;
  addEventListener(t: string, fn: (e: any) => void): void;
  binaryType?: "blob" | "arraybuffer";
}

const safe = (fn: () => void) => {
  try {
    fn();
  } catch {
    // peer already closed
  }
};
const closeCode = (c: unknown) => (typeof c === "number" && (c === 1000 || (c >= 3000 && c <= 4999)) ? c : 1000);

const isBlob = (d: unknown): d is Blob => typeof (d as Blob | null)?.arrayBuffer === "function";

/**
 * Wire an upstream control socket to the browser socket. Client messages are ignored (read-only viewer).
 * Upstream protocol (https://glasshand.com/agents.md): `hello`, then `{v:1,type:"frame",frameId}` immediately
 * followed by a binary JPEG; ack each frame with `{v:1,type:"frame_ack",frameId}` (at most 4 unacked).
 */
export function pipe(up: Sock, client: Sock): void {
  // workerd defaults binaryType to "blob" (current compat dates), and send(Blob) is stringified to
  // "[object Blob]", so frames reached the browser as text and were never drawn. Ask for ArrayBuffers.
  up.binaryType = "arraybuffer";
  // Keep client order when a Blob still has to be read asynchronously.
  let tail: Promise<void> = Promise.resolve();
  let queued = 0;
  const toClient = (d: string | ArrayBuffer | ArrayBufferView | Promise<ArrayBuffer>) => {
    if (queued === 0 && !(d instanceof Promise)) return safe(() => client.send(d));
    queued++;
    tail = tail
      .then(() => d)
      .then((v) => safe(() => client.send(v)), () => undefined)
      .finally(() => void queued--);
  };
  let pending: unknown; // frameId whose JPEG has not arrived yet
  const ack = () => {
    if (pending === undefined) return;
    const frameId = pending;
    pending = undefined;
    safe(() => up.send(JSON.stringify({ v: 1, type: "frame_ack", frameId })));
  };
  up.addEventListener("message", (ev) => {
    const d = ev.data;
    if (typeof d !== "string") {
      toClient(isBlob(d) ? d.arrayBuffer() : d); // full HDMI JPEG
      return ack(); // the documented order is header, JPEG, then ack
    }
    let m: { type?: string; frameId?: unknown; geometry?: unknown; message?: unknown; error?: unknown; available?: unknown; capture?: { available?: unknown } };
    try {
      m = JSON.parse(d);
    } catch {
      return;
    }
    if (m.type === "hello") toClient(JSON.stringify({ type: "hello", geometry: m.geometry }));
    else if (m.type === "frame" && m.frameId !== undefined) {
      ack(); // a header whose JPEG never came: ack it anyway so upstream never stalls
      pending = m.frameId;
    } else if (m.type === "capture_status") toClient(JSON.stringify({ type: "capture_status", available: !(m.available === false || m.capture?.available === false) }));
    else if (m.type === "error") {
      const e = m.error as { message?: unknown } | string | undefined;
      toClient(JSON.stringify({ type: "error", message: String(m.message ?? (typeof e === "object" ? e?.message : e) ?? "error") }));
    }
  });
  const end = (to: Sock) => (ev: { code?: number; reason?: string }) => safe(() => to.close(closeCode(ev?.code), String(ev?.reason ?? "").slice(0, 100)));
  up.addEventListener("close", end(client));
  up.addEventListener("error", () => safe(() => client.close(1011, "upstream error")));
  client.addEventListener("close", end(up));
  client.addEventListener("error", () => safe(() => up.close(1011, "client error")));
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
  up.binaryType = "arraybuffer"; // before accept, so no frame is delivered as a Blob
  server.accept();
  up.accept();
  pipe(up, server);
  return new Response(null, { status: 101, webSocket: client });
}
