import { describe, expect, it } from "vitest";
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
