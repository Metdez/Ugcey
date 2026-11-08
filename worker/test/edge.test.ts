import { afterEach, describe, expect, it, vi } from "vitest";
import type { Env } from "../env";
import { filterSseLine, sseFilterStream, CHAT_MODELS } from "../egress/llm";
import { handleVendor, VENDORS } from "../egress/vendors";

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

describe("vendor allowlists", () => {
  it("restricts paths", () => {
    expect(VENDORS["higgsfield.internal"]!.allowed("/v1/agent/x")).toBe(false);
    expect(VENDORS["higgsfield.internal"]!.allowed("/v1/image")).toBe(true);
    expect(VENDORS["firecrawl.internal"]!.allowed("/v2/scrape")).toBe(true);
    expect(VENDORS["firecrawl.internal"]!.allowed("/v2/crawl")).toBe(false);
    expect(VENDORS["glasshand.internal"]!.allowed("/v1/rentals/1")).toBe(true);
    expect(VENDORS["glasshand.internal"]!.allowed("/v1/other")).toBe(false);
    const tv = VENDORS["tavily.internal"]!.allowed;
    for (const p of ["/search", "/extract", "/research"]) expect(tv(p, "POST")).toBe(true);
    expect(tv("/research/abc", "GET")).toBe(true);
    for (const p of ["/crawl", "/map", "/usage", "/research/abc/x"]) expect(tv(p, "POST") || tv(p, "GET")).toBe(false);
    expect(tv("/search", "GET")).toBe(false);
    expect(tv("/research/abc", "POST")).toBe(false);
  });
});

describe("vendor passthrough", () => {
  afterEach(() => vi.unstubAllGlobals());
  const env = { TAVILY_API_KEY: "tvly-k" } as unknown as Env;
  const poll = () => new Request("http://tavily.internal/research/abc", { headers: { authorization: "Bearer fake" } });

  it.each([[202, null], [429, "7"], [432, null]] as const)("GET forwards with the key and returns %i unchanged", async (status, ra) => {
    const fetchMock = vi.fn(async () => new Response('{"status":"x"}', { status, headers: ra ? { "retry-after": ra } : {} }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await handleVendor(poll(), env, { runtimeId: "r" });
    expect([res.status, res.headers.get("retry-after"), await res.text()]).toEqual([status, ra, '{"status":"x"}']);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect([url, init.method, init.body]).toEqual(["https://api.tavily.com/research/abc", "GET", undefined]);
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer tvly-k");
  });

  it("refuses crawl and reports not_configured without a key, without calling out", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect((await handleVendor(new Request("http://tavily.internal/crawl", { method: "POST", body: "{}" }), env, { runtimeId: "r" })).status).toBe(403);
    expect((await handleVendor(poll(), {} as Env, { runtimeId: "r" })).status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
