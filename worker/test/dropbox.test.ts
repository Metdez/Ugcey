import { describe, expect, it } from "vitest";
import { Dropbox } from "../dropbox/core";
import { handleDropbox } from "../dropbox/egress";
import { authorizeUrl } from "../dropbox/oauth";
import { memoryStore } from "../dropbox/store";
import { InvalidCodeError, type DropboxRuntime, type FetchFn } from "../dropbox/types";

type Call = { url: string; init?: RequestInit };
const json = (b: unknown, status = 200) => Response.json(b, { status });
const ENV = { DROPBOX_APP_KEY: "key", DROPBOX_APP_SECRET: "sec" };
const SCOPE = "account_info.read files.metadata.read files.content.read files.content.write";
const ACCT = { name: { display_name: "Zed" }, email: "z@x.io" };

function setup(handler: (c: Call, calls: Call[]) => Response | Promise<Response>, env: object = ENV) {
  const calls: Call[] = [];
  let t = 1_000_000;
  const f: FetchFn = async (url, init) => {
    const c = { url, init };
    calls.push(c);
    return handler(c, calls);
  };
  const store = memoryStore();
  const dbx = new Dropbox(store, env, f, () => t);
  return { dbx, store, calls, advance: (ms: number) => (t += ms) };
}
const connected = (store: ReturnType<typeof memoryStore>, exp: number, extra = {}) =>
  store.put({ access_token: "a1", refresh_token: "r1", expires_at: String(exp), scopes: SCOPE, ...extra });
const form = (c: Call) => Object.fromEntries(new URLSearchParams(String(c.init?.body)));
const hdr = (c: Call, k: string) => new Headers(c.init?.headers).get(k);

describe("oauth", () => {
  it("builds the authorize url without redirect_uri", () => {
    const u = new URL(authorizeUrl("k"));
    expect(u.origin + u.pathname).toBe("https://www.dropbox.com/oauth2/authorize");
    expect(Object.fromEntries(u.searchParams)).toEqual({ client_id: "k", response_type: "code", token_access_type: "offline" });
  });

  it("exchanges a code with basic auth and stores tokens + scopes", async () => {
    const { dbx, store, calls } = setup((c) =>
      c.url.endsWith("/oauth2/token") ? json({ access_token: "a1", refresh_token: "r1", expires_in: 14400, scope: SCOPE, account_id: "dbid:1" }) : json(ACCT));
    const s = await dbx.submitCode(" abc ");
    expect(calls[0]!.url).toBe("https://api.dropboxapi.com/oauth2/token");
    expect(form(calls[0]!)).toEqual({ grant_type: "authorization_code", code: "abc" });
    expect(hdr(calls[0]!, "authorization")).toBe(`Basic ${btoa("key:sec")}`);
    expect(store.all()).toMatchObject({ access_token: "a1", refresh_token: "r1", scopes: SCOPE, account_id: "dbid:1" });
    expect(s).toEqual({ configured: true, connected: true, account_name: "Zed", email: "z@x.io", scopes: SCOPE.split(" "), missing_scopes: [] });
  });

  it("throws InvalidCodeError on 400 and stores nothing", async () => {
    const { dbx, store } = setup(() => json({ error: "invalid_grant", error_description: "bad code" }, 400));
    await expect(dbx.submitCode("x")).rejects.toBeInstanceOf(InvalidCodeError);
    expect(store.all()).toEqual({});
  });
});

describe("token", () => {
  it("returns the stored token while fresh", async () => {
    const { dbx, store, calls } = setup(() => json({}));
    connected(store, 1_000_000 + 600_000);
    expect(await dbx.token()).toBe("a1");
    expect(calls).toHaveLength(0);
  });

  it("refreshes near expiry and keeps the refresh token", async () => {
    const { dbx, store, calls } = setup(() => json({ access_token: "a2", expires_in: 14400 }));
    connected(store, 1_000_000 + 30_000);
    expect(await dbx.token()).toBe("a2");
    expect(form(calls[0]!)).toEqual({ grant_type: "refresh_token", refresh_token: "r1" });
    expect(store.all()).toMatchObject({ access_token: "a2", refresh_token: "r1", expires_at: String(1_000_000 + 14_400_000) });
  });

  it("forces a refresh for a stale token, deduplicating concurrent callers", async () => {
    const { dbx, store, calls } = setup(() => json({ access_token: "a2", expires_in: 14400 }));
    connected(store, 1_000_000 + 600_000);
    const [x, y] = await Promise.all([dbx.token("a1"), dbx.token("a1")]);
    expect([x, y]).toEqual(["a2", "a2"]);
    expect(calls).toHaveLength(1);
  });

  it("clears tokens when the refresh is rejected", async () => {
    const { dbx, store } = setup(() => json({ error: "invalid_grant" }, 400));
    connected(store, 0);
    expect(await dbx.token()).toBeNull();
    expect(store.all().access_token).toBeUndefined();
    expect(store.all().refresh_token).toBeUndefined();
  });

  it("keeps tokens and throws on a transient refresh failure", async () => {
    const { dbx, store } = setup(() => json({}, 500));
    connected(store, 0);
    await expect(dbx.token()).rejects.toThrow();
    expect(store.all().refresh_token).toBe("r1");
  });
});

describe("status", () => {
  it("is disconnected with no Dropbox call", async () => {
    const { dbx, calls } = setup(() => json({}));
    expect(await dbx.status()).toEqual({ configured: true, connected: false, scopes: [], missing_scopes: [] });
    expect(calls).toHaveLength(0);
  });

  it("reports configured=false without secrets", async () => {
    const { dbx } = setup(() => json({}), {});
    expect((await dbx.status()).configured).toBe(false);
    expect(dbx.connectUrl()).toBeNull();
  });

  it("computes missing_scopes and caches the account for 5 minutes", async () => {
    const { dbx, store, calls, advance } = setup(() => json(ACCT));
    connected(store, 1_000_000 + 10_000_000, { scopes: "account_info.read files.content.read" });
    const s = await dbx.status();
    expect(s.missing_scopes).toEqual(["files.metadata.read", "files.content.write"]);
    expect(calls[0]!.url).toBe("https://api.dropboxapi.com/2/users/get_current_account");
    expect(hdr(calls[0]!, "content-type")).toBeNull();
    expect(calls[0]!.init!.body).toBeUndefined();
    await dbx.status();
    expect(calls).toHaveLength(1);
    advance(5 * 60_000 + 1);
    await dbx.status();
    expect(calls).toHaveLength(2);
  });

  it("disconnect revokes best effort and clears everything", async () => {
    const { dbx, store, calls } = setup(() => json({}, 500));
    connected(store, 1_000_000 + 600_000);
    const s = await dbx.disconnect();
    expect(calls[0]!.url).toBe("https://api.dropboxapi.com/2/auth/token/revoke");
    expect(hdr(calls[0]!, "authorization")).toBe("Bearer a1");
    expect(store.all()).toEqual({});
    expect(s.connected).toBe(false);
  });
});

describe("egress", () => {
  function rt(tokens: (string | null)[], seen: (string | undefined)[] = []): DropboxRuntime {
    let i = 0;
    return {
      dropboxStatus: async () => ({ configured: true, connected: false, scopes: [], missing_scopes: [] }),
      dropboxToken: async (stale) => (seen.push(stale), tokens[Math.min(i++, tokens.length - 1)] ?? null),
    };
  }
  const post = (path: string, body = '{"a":1}') =>
    new Request("http://dropbox.internal" + path, { method: "POST", headers: { "content-type": "application/json", cookie: "secret", authorization: "Bearer evil" }, body });

  it("answers /_ugecy/status locally", async () => {
    let called = false;
    const r = await handleDropbox(new Request("http://dropbox.internal/_ugecy/status"), rt([null]), async () => ((called = true), json({})));
    expect(await r.json()).toMatchObject({ connected: false, missing_scopes: [] });
    expect(called).toBe(false);
  });

  it("403s other paths and methods", async () => {
    const f: FetchFn = async () => json({});
    const a = await handleDropbox(post("/2/files/delete_v2"), rt(["t"]), f);
    expect(a.status).toBe(403);
    expect(((await a.json()) as { error: { code: string } }).error.code).toBe("path_not_allowed");
    expect((await handleDropbox(new Request("http://dropbox.internal/2/files/list_folder"), rt(["t"]), f)).status).toBe(403);
  });

  it("503s when not connected", async () => {
    const r = await handleDropbox(post("/2/files/list_folder"), rt([null]), async () => json({}));
    expect(r.status).toBe(503);
    expect(await r.json()).toMatchObject({ error: { code: "not_configured", message: "Dropbox is not connected" } });
  });

  it("injects the bearer, forwards only content-type/accept, passes status and Retry-After through", async () => {
    const calls: Call[] = [];
    const f: FetchFn = async (url, init) => (calls.push({ url, init }), new Response('{"e":1}', { status: 429, headers: { "retry-after": "7" } }));
    const r = await handleDropbox(post("/2/files/save_url"), rt(["tok"]), f);
    expect(r.status).toBe(429);
    expect(r.headers.get("retry-after")).toBe("7");
    expect(calls[0]!.url).toBe("https://api.dropboxapi.com/2/files/save_url");
    const h = new Headers(calls[0]!.init!.headers);
    expect(h.get("authorization")).toBe("Bearer tok");
    expect(h.get("content-type")).toBe("application/json");
    expect(h.get("cookie")).toBeNull();
  });

  it("retries once after a 401 with the refreshed token and the same body", async () => {
    const calls: Call[] = [];
    const seen: (string | undefined)[] = [];
    const f: FetchFn = async (url, init) => {
      calls.push({ url, init });
      return calls.length === 1 ? json({ error: "expired_access_token" }, 401) : json({ ok: true });
    };
    const r = await handleDropbox(post("/2/files/get_metadata", '{"path":"/x"}'), rt(["old", "new"], seen), f);
    expect(r.status).toBe(200);
    expect(calls).toHaveLength(2);
    expect(seen).toEqual([undefined, "old"]);
    expect(new Headers(calls[1]!.init!.headers).get("authorization")).toBe("Bearer new");
    expect(new TextDecoder().decode(calls[1]!.init!.body as ArrayBuffer)).toBe('{"path":"/x"}');
  });
});
