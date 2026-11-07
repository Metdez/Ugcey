import { describe, expect, it } from "vitest";
import { glasshandAllowed } from "../glasshand/allow";
import { Glasshand } from "../glasshand/core";
import { handleGlasshand } from "../glasshand/egress";
import { pipe } from "../glasshand/relay";
import { memoryStore } from "../glasshand/store";
import type { FetchFn } from "../glasshand/types";

type Call = { url: string; init?: RequestInit };
const json = (b: unknown, status = 200) => Response.json(b, { status });
const DEVICE = { client_id: "cid", device_code: "dc", user_code: "ABCD", verification_uri: "https://g/v", verification_uri_complete: "https://g/v?c=ABCD", expires_in: 600, interval: 5 };
const tok = (n: number, exp = 900) => ({ access_token: `a${n}`, refresh_token: `r${n}`, token_type: "Bearer", expires_in: exp, scope: "x" });

function setup(handler: (c: Call, calls: Call[]) => Response | Promise<Response>) {
  const calls: Call[] = [];
  let t = 1_000_000;
  const f: FetchFn = async (url, init) => {
    const c = { url, init };
    calls.push(c);
    return handler(c, calls);
  };
  const store = memoryStore();
  const gh = new Glasshand(store, f, () => t);
  return { gh, store, calls, advance: (ms: number) => (t += ms) };
}
const bodyOf = (c: Call) => new URLSearchParams(String(c.init?.body));
const connectedStore = (store: ReturnType<typeof memoryStore>, exp: number, extra = {}) =>
  store.put({ client_id: "cid", access_token: "a1", refresh_token: "r1", access_expires_at: String(exp), ...extra });

describe("device flow", () => {
  it("starts the device code and stores pending state", async () => {
    const { gh, store, calls } = setup(() => json(DEVICE));
    const s = await gh.connect();
    expect(calls[0]!.url).toBe("https://api.glasshand.com/v1/auth/device/code");
    expect(JSON.parse(String(calls[0]!.init!.body))).toEqual({ clientName: "Ugecy" });
    expect(s).toMatchObject({ state: "pending", user_code: "ABCD", interval: 5, verification_uri_complete: "https://g/v?c=ABCD" });
    expect(store.all()).toMatchObject({ client_id: "cid", device_code: "dc", last_poll_at: "0" });
  });

  it("polls at most once per interval, handles pending/slow_down/denied", async () => {
    const answers = [{ error: "authorization_pending" }, { error: "slow_down" }, { error: "access_denied" }];
    let n = 0;
    const { gh, store, calls, advance } = setup((c) => (c.url.endsWith("/code") ? json(DEVICE) : json(answers[n++], 400)));
    await gh.connect();
    expect((await gh.status()).state).toBe("pending");
    await gh.status(); // inside interval: no second poll
    expect(calls.filter((c) => c.url.endsWith("/token"))).toHaveLength(1);
    const p = bodyOf(calls[1]!);
    expect(Object.fromEntries(p)).toEqual({ grant_type: "urn:ietf:params:oauth:grant-type:device_code", client_id: "cid", device_code: "dc" });
    expect((calls[1]!.init!.headers as Record<string, string>)["content-type"]).toBe("application/x-www-form-urlencoded");
    advance(5_000);
    await gh.status();
    expect(store.all().interval).toBe("10"); // slow_down +5
    advance(10_000);
    expect(await gh.status()).toEqual({ state: "denied" });
    expect(store.all().device_code).toBeUndefined();
  });

  it("expires by clock, and stores tokens on success then lists + auto-selects a rental", async () => {
    const rentals = { items: [
      { id: "r0", name: "pending", kind: "iphone", status: "provisioning", deviceReady: false },
      { id: "r1", name: "phone", kind: "iphone", status: "active", deviceReady: true },
    ] };
    const { gh, store, advance } = setup((c) =>
      c.url.endsWith("/code") ? json(DEVICE) : c.url.endsWith("/token") ? json(tok(1)) : json(rentals));
    await gh.connect();
    advance(5_000);
    const s = await gh.status();
    expect(s).toMatchObject({ state: "connected", selected_rental_id: "r1" });
    expect(s.rentals).toHaveLength(2);
    expect(store.all()).toMatchObject({ access_token: "a1", refresh_token: "r1", selected_rental_id: "r1" });
    expect(store.all().device_code).toBeUndefined();
    expect(JSON.stringify(s)).not.toContain("a1\"");

    const e = setup(() => json(DEVICE));
    await e.gh.connect();
    e.advance(601_000);
    expect(await e.gh.status()).toEqual({ state: "expired" });
  });
});

describe("token refresh", () => {
  it("rotates both tokens atomically when < 60 s remain, and serializes concurrent refreshes", async () => {
    const { gh, store, calls } = setup(async () => {
      await new Promise((r) => setTimeout(r, 5));
      return json(tok(2));
    });
    connectedStore(store, 1_000_000 + 30_000);
    const [a, b, c] = await Promise.all([gh.token(), gh.token(), gh.token()]);
    expect([a, b, c]).toEqual(["a2", "a2", "a2"]);
    expect(calls).toHaveLength(1);
    expect(Object.fromEntries(bodyOf(calls[0]!))).toEqual({ grant_type: "refresh_token", client_id: "cid", refresh_token: "r1" });
    expect(store.all()).toMatchObject({ access_token: "a2", refresh_token: "r2", access_expires_at: String(1_000_000 + 900_000) });
  });

  it("does not refresh a healthy token; rejected refresh clears tokens", async () => {
    const ok = setup(() => json({}, 500));
    connectedStore(ok.store, 1_000_000 + 600_000);
    expect(await ok.gh.token()).toBe("a1");
    expect(ok.calls).toHaveLength(0);

    const bad = setup(() => json({ error: "invalid_grant", error_description: "revoked" }, 400));
    connectedStore(bad.store, 0);
    expect(await bad.gh.token()).toBeNull();
    expect(bad.gh.state().connected).toBe(false);
  });

  it("a stale token is refreshed only once", async () => {
    const { gh, store, calls } = setup(() => json(tok(2)));
    connectedStore(store, 1_000_000 + 600_000);
    expect(await gh.token("a1")).toBe("a2");
    expect(await gh.token("a1")).toBe("a2"); // already rotated: no second refresh
    expect(calls).toHaveLength(1);
  });
});

describe("glasshand.internal gateway", () => {
  const rt = (gh: Glasshand) => ({ glasshandState: async () => gh.state(), glasshandToken: (s?: string) => gh.token(s) });
  const get = (path: string, method = "GET") => new Request(`http://glasshand.internal${path}`, { method, body: method === "POST" ? "{}" : undefined, headers: { "idempotency-key": "k1", "content-type": "application/json" } });

  it("answers _ugecy/status locally", async () => {
    const { gh, store, calls } = setup(() => json({}));
    expect(await (await handleGlasshand(get("/_ugecy/status"), rt(gh), (u, i) => (calls.push({ url: u, init: i }), Promise.resolve(json({}))))).json()).toEqual({ connected: false, selected_rental_id: null });
    connectedStore(store, 1_000_000 + 600_000, { selected_rental_id: "r9" });
    expect(await (await handleGlasshand(get("/_ugecy/status"), rt(gh))).json()).toEqual({ connected: true, selected_rental_id: "r9" });
    expect(calls).toHaveLength(0);
  });

  it("allowlist blocks checkout and billing", async () => {
    expect(glasshandAllowed("/v1/rentals/abc/screenshot")).toBe(true);
    expect(glasshandAllowed("/v1/rentals/abc/input", "POST")).toBe(true);
    expect(glasshandAllowed("/v1/rentals/abc/input", "GET")).toBe(false);
    for (const p of ["/v1/checkout", "/v1/rentals/abc/cancel", "/v1/billing/portal", "/v1/rentals/abc/resume", "/v1/auth/device/token", "/v1/rentals/abc/connection/../x"])
      expect(glasshandAllowed(p, "POST") || glasshandAllowed(p, "GET")).toBe(false);
    const { gh } = setup(() => json({}));
    expect((await handleGlasshand(get("/v1/checkout", "POST"), rt(gh))).status).toBe(403);
  });

  it("503 not_configured when disconnected", async () => {
    const { gh } = setup(() => json({}));
    const r = await handleGlasshand(get("/v1/rentals"), rt(gh));
    expect(r.status).toBe(503);
    expect(await r.json()).toMatchObject({ error: { code: "not_configured" } });
  });

  it("injects bearer, forwards idempotency-key, and on 401 refreshes then retries once", async () => {
    const seen: { auth: string | null; idem: string | null }[] = [];
    const { gh, store } = setup((c) => (c.url.endsWith("/auth/device/token") ? json(tok(2)) : json({})));
    connectedStore(store, 1_000_000 + 600_000);
    const up = async (u: string, init?: RequestInit) => {
      if (u.endsWith("/auth/device/token")) return gh["f"](u, init); // refresh goes through the core's fake
      const h = new Headers(init!.headers);
      seen.push({ auth: h.get("authorization"), idem: h.get("idempotency-key") });
      return seen.length === 1 ? json({ error: "expired" }, 401) : json({ ok: true });
    };
    const r = await handleGlasshand(get("/v1/rentals/abc/input", "POST"), rt(gh), up);
    expect(r.status).toBe(200);
    expect(seen).toEqual([{ auth: "Bearer a1", idem: "k1" }, { auth: "Bearer a2", idem: "k1" }]);
  });

  it("clears tokens and returns 503 when the retry's refresh is rejected", async () => {
    const { gh, store } = setup(() => json({ error: "invalid_grant" }, 400));
    connectedStore(store, 1_000_000 + 600_000);
    const r = await handleGlasshand(get("/v1/me"), rt(gh), async () => json({}, 401));
    expect(r.status).toBe(503);
    expect(gh.state().connected).toBe(false);
  });
});

describe("relay pipe", () => {
  function fake() {
    const l: Record<string, ((e: any) => void)[]> = {};
    const sent: unknown[] = [];
    let closed: [number?, string?] | null = null;
    return {
      sent, get closed() { return closed; }, emit: (t: string, e: any) => l[t]?.forEach((f) => f(e)),
      send: (d: unknown) => void sent.push(d), close: (c?: number, r?: string) => void (closed = [c, r]),
      addEventListener: (t: string, f: (e: any) => void) => void (l[t] ??= []).push(f),
    };
  }
  it("acks frames, forwards hello/error as JSON and JPEGs as binary, closes both ways, ignores client", () => {
    const up = fake(), cl = fake();
    pipe(up, cl);
    up.emit("message", { data: JSON.stringify({ type: "hello", geometry: { width: 1 } }) });
    up.emit("message", { data: JSON.stringify({ v: 1, type: "frame", frameId: 7 }) });
    const jpg = new Uint8Array([0xff, 0xd8]).buffer;
    up.emit("message", { data: jpg });
    up.emit("message", { data: JSON.stringify({ type: "error", message: "boom" }) });
    expect(up.sent).toEqual([JSON.stringify({ v: 1, type: "frame_ack", frameId: 7 })]);
    expect(cl.sent).toEqual([JSON.stringify({ type: "hello", geometry: { width: 1 } }), jpg, JSON.stringify({ type: "error", message: "boom" })]);
    cl.emit("message", { data: "tap" });
    expect(up.sent).toHaveLength(1);
    cl.emit("close", { code: 1001, reason: "bye" });
    expect(up.closed).toEqual([1000, "bye"]); // 1001 is not sendable in close(); normalised
    up.emit("close", { code: 4000, reason: "x" });
    expect(cl.closed).toEqual([4000, "x"]);
  });

  it("asks upstream for ArrayBuffers (workerd's default Blob was sent to the browser as the text '[object Blob]')", () => {
    const up: ReturnType<typeof fake> & { binaryType?: "blob" | "arraybuffer" } = fake();
    pipe(up, fake());
    expect(up.binaryType).toBe("arraybuffer");
  });

  it("still forwards a Blob frame as binary, in order with the messages after it", async () => {
    const up = fake(), cl = fake();
    pipe(up, cl);
    up.emit("message", { data: JSON.stringify({ v: 1, type: "frame", frameId: 1 }) });
    up.emit("message", { data: new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xd9])]) });
    up.emit("message", { data: JSON.stringify({ type: "error", error: { message: "capture lost" } }) });
    await new Promise((r) => setTimeout(r, 0));
    expect(cl.sent).toHaveLength(2);
    expect(cl.sent[0]).toBeInstanceOf(ArrayBuffer);
    expect([...new Uint8Array(cl.sent[0] as ArrayBuffer)]).toEqual([0xff, 0xd8, 0xff, 0xd9]);
    expect(cl.sent[1]).toBe(JSON.stringify({ type: "error", message: "capture lost" }));
    expect(up.sent).toEqual([JSON.stringify({ v: 1, type: "frame_ack", frameId: 1 })]);
  });

  it("acks after the JPEG, never leaves a header unacked, and forwards capture_status", () => {
    const up = fake(), cl = fake();
    pipe(up, cl);
    up.emit("message", { data: JSON.stringify({ v: 1, type: "frame", frameId: 1 }) });
    expect(up.sent).toEqual([]); // not before its JPEG arrives
    up.emit("message", { data: JSON.stringify({ v: 1, type: "frame", frameId: 2 }) }); // JPEG for 1 never came
    up.emit("message", { data: new Uint8Array([1]).buffer });
    expect(up.sent.map((s) => JSON.parse(s as string).frameId)).toEqual([1, 2]);
    up.emit("message", { data: JSON.stringify({ type: "capture_status", capture: { available: false } }) });
    up.emit("message", { data: JSON.stringify({ type: "capture_status", available: true }) });
    expect(cl.sent.slice(-2)).toEqual([
      JSON.stringify({ type: "capture_status", available: false }),
      JSON.stringify({ type: "capture_status", available: true }),
    ]);
  });
});

import { isGlasshandUrl } from "../glasshand/relay";
describe("relay host pinning", () => {
  it("only allows TLS Glasshand hosts", () => {
    expect(isGlasshandUrl("wss://api.glasshand.com/v1/rentals/x/control")).toBe(true);
    expect(isGlasshandUrl("wss://control.glasshand.com/x")).toBe(true);
    expect(isGlasshandUrl("ws://api.glasshand.com/x")).toBe(false);
    expect(isGlasshandUrl("wss://glasshand.com.evil.net/x")).toBe(false);
    expect(isGlasshandUrl("wss://evil.net/glasshand.com")).toBe(false);
  });
});
