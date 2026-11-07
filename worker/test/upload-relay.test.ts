import { afterEach, describe, expect, it, vi } from "vitest";
import { handleUploadRelay, MAX_UPLOAD_BYTES, uploadTarget } from "../egress/upload-relay";

const BUCKET = "https://fnf-api-input-prod-20250414194641741400000002.s3.amazonaws.com/in/p.png?X-Amz-Signature=abc";
const relay = (to: string) => `http://hfupload.internal/?to=${encodeURIComponent(to)}`;

describe("upload relay target", () => {
  it("accepts only Higgsfield's input bucket over https", () => {
    expect(uploadTarget(relay(BUCKET))).toBeInstanceOf(URL);
    expect(uploadTarget(relay("http://fnf-api-input-prod-1.s3.amazonaws.com/x"))).toMatch(/https/);
    expect(uploadTarget(relay("https://evil.s3.amazonaws.com/x"))).toMatch(/not allowed/);
    expect(uploadTarget(relay("https://fnf-api-input-prod-1.s3.amazonaws.com.evil.com/x"))).toMatch(/not allowed/);
    expect(uploadTarget(relay("https://user:pw@fnf-api-input-prod-1.s3.amazonaws.com/x"))).toMatch(/credentials/);
    expect(uploadTarget("http://hfupload.internal/")).toMatch(/missing/);
  });
});

describe("upload relay", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("forwards the PUT with only the allowed headers and never credentials", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await handleUploadRelay(new Request(relay(BUCKET), {
      method: "PUT", body: "img",
      headers: { "content-type": "image/png", "x-amz-tagging": "retention=temporary", "content-length": "3",
                 authorization: "Key secret", cookie: "c=1" },
    }));
    expect(res.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(BUCKET);
    const h = new Headers(init.headers);
    expect(h.get("authorization")).toBeNull();
    expect(h.get("cookie")).toBeNull();
    expect(h.get("x-amz-tagging")).toBe("retention=temporary");
  });

  it("rejects other methods, other hosts and oversize bodies without calling out", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect((await handleUploadRelay(new Request(relay(BUCKET), { method: "GET" }))).status).toBe(405);
    expect((await handleUploadRelay(new Request(relay("https://example.com/x"), {
      method: "PUT", body: "x", headers: { "content-length": "1" } }))).status).toBe(403);
    expect((await handleUploadRelay(new Request(relay(BUCKET), {
      method: "PUT", body: "x", headers: { "content-length": String(MAX_UPLOAD_BYTES + 1) } }))).status).toBe(413);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
