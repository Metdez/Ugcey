import { describe, expect, it, vi } from "vitest";
import { guardPublicUrl, guardSql, HttpError } from "../egress/bindings-guards";
import { handleBindings } from "../egress/bindings";
import type { Env } from "../env";

const call = (env: unknown, path: string, body: unknown) =>
  handleBindings(new Request(`http://bindings.internal${path}`, { method: "POST", body: JSON.stringify(body) }), new URL(`http://bindings.internal${path}`), env as Env, { runtimeId: "x" });

describe("guardPublicUrl", () => {
  it("accepts public http(s)", () => expect(guardPublicUrl("https://example.com/a").hostname).toBe("example.com"));
  it.each(["ftp://example.com", "file:///etc/passwd", "http://localhost/", "http://127.0.0.1/", "http://2130706433/", "http://10.0.0.1/", "http://192.168.1.1/", "http://169.254.169.254/", "http://[::1]/", "http://foo.internal/", "http://intranet/", "nope"])("rejects %s", (u) => {
    expect(() => guardPublicUrl(u)).toThrow(HttpError);
  });
});

describe("guardSql", () => {
  it("allows a single statement, with trailing semicolon and keywords in strings", () => {
    expect(guardSql("SELECT 'drop table' FROM t;")).toContain("SELECT");
  });
  it.each(["SELECT 1; SELECT 2", "ATTACH DATABASE 'x' AS y", "pragma writable_schema=1", "DROP TABLE t", "", "/* x */ drop table t"])("rejects %j", (s) => {
    expect(() => guardSql(s)).toThrow(HttpError);
  });
});

describe("handleBindings", () => {
  it("returns the error envelope for bad bodies and unknown paths", async () => {
    expect(await (await call({}, "/d1/query", { sql: 5 })).json()).toMatchObject({ error: { code: "bad_request" } });
    expect((await call({}, "/nope", {})).status).toBe(404);
    expect((await call({}, "/browser/markdown", { url: "http://localhost" })).status).toBe(400);
  });
  it("queues media ingest and returns the original url", async () => {
    const send = vi.fn();
    const r = await call({ JOBS: { send } }, "/media/ingest", { asset_id: "a1", url: "https://cdn.example.com/v.mp4", kind: "video" });
    expect(await r.json()).toEqual({ asset_id: "a1", queued: true, playback_url: "https://cdn.example.com/v.mp4", thumbnail_url: null });
    expect(send).toHaveBeenCalledWith({ kind: "media.ingest", asset_id: "a1", url: "https://cdn.example.com/v.mp4", media_kind: "video" });
  });
  it("upserts vectors with text in metadata and namespace", async () => {
    const upsert = vi.fn();
    const env = { AI: { run: async () => ({ data: [[0.1, 0.2]] }) }, MEMORY: { upsert } };
    const r = await call(env, "/vectors/upsert", { namespace: "ws", items: [{ id: "m1", text: "hello", metadata: { k: "v" } }] });
    expect(await r.json()).toEqual({ ok: true, count: 1 });
    expect(upsert).toHaveBeenCalledWith([{ id: "m1", values: [0.1, 0.2], namespace: "ws", metadata: { k: "v", text: "hello" } }]);
  });
  it("returns the existing workflow id when the instance already exists", async () => {
    const env = { PUBLISH_WF: { create: async () => { throw new Error("exists"); }, get: async () => ({ id: "p1" }) } };
    expect(await (await call(env, "/publish/schedule", { post_id: "p1" })).json()).toEqual({ workflow_id: "p1" });
  });
});
