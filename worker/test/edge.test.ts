import { describe, expect, it } from "vitest";
import { cookieValid, keyMatches, readCookie, sha256Hex, unlock } from "../auth";
import { filterSseLine, sseFilterStream, CHAT_MODELS } from "../egress/llm";
import { VENDORS } from "../egress/vendors";

describe("sse filter", () => {
  it("keeps choices and DONE, drops usage-only and garbage data lines", () => {
    expect(filterSseLine('data: {"choices":[{"delta":{}}]}')).not.toBeNull();
    expect(filterSseLine("data: [DONE]")).toBe("data: [DONE]");
    expect(filterSseLine('data: {"response":"","usage":{}}')).toBeNull();
    expect(filterSseLine("data: {oops")).toBeNull();
    expect(filterSseLine(": ping")).toBe(": ping");
    expect(filterSseLine("")).toBe("");
  });
  it("handles lines split across chunks", async () => {
    const t = sseFilterStream();
    const w = t.writable.getWriter();
    void (async () => {
      await w.write('data: {"choi');
      await w.write('ces":[]}\n\ndata: {"response":""}\n\ndata: [DONE]');
      await w.close();
    })();
    let out = "";
    for await (const c of t.readable) out += c;
    expect(out).toBe('data: {"choices":[]}\n\n\ndata: [DONE]\n');
  });
  it("allowlist", () => expect(CHAT_MODELS.has("@cf/zai-org/glm-5.3")).toBe(true));
});

describe("auth", () => {
  it("compares keys", async () => {
    expect(await keyMatches("a", "a")).toBe(true);
    expect(await keyMatches("a", "b")).toBe(false);
    expect(await keyMatches(undefined, "b")).toBe(false);
  });
  it("cookie round trip", async () => {
    const h = await sha256Hex("k");
    expect(readCookie(`x=1; ugecy_key=${h}`, "ugecy_key")).toBe(h);
    expect(await cookieValid(`ugecy_key=${h}`, "k")).toBe(true);
    expect(await cookieValid(`ugecy_key=${h}`, "other")).toBe(false);
    expect(await cookieValid(null, "k")).toBe(false);
  });
  it("unlock sets cookie and redirects, or 401s", async () => {
    const env: any = { UGECY_ACCESS_KEY: "k" };
    const ok = await unlock({ req: { query: () => "k" }, env });
    expect(ok.status).toBe(302);
    expect(ok.headers.get("set-cookie")).toContain("HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000");
    expect((await unlock({ req: { query: () => "no" }, env })).status).toBe(401);
  });
});

describe("vendor allowlists", () => {
  it("restricts paths", () => {
    expect(VENDORS["higgsfield.internal"]!.allowed("/v1/agent/x")).toBe(false);
    expect(VENDORS["higgsfield.internal"]!.allowed("/v1/image")).toBe(true);
    expect(VENDORS["firecrawl.internal"]!.allowed("/v2/scrape")).toBe(true);
    expect(VENDORS["firecrawl.internal"]!.allowed("/v2/crawl")).toBe(false);
    expect(VENDORS["glasshand.internal"]!.allowed("/v1/rentals/1")).toBe(true);
    expect(VENDORS["glasshand.internal"]!.allowed("/v1/other")).toBe(false);
  });
});
