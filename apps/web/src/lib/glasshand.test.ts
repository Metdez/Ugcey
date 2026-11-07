import { describe, expect, it } from "vitest";
import { cropRect, formatCountdown, streamUrl, viewState } from "./glasshand";

describe("cropRect", () => {
  const g = { width: 1920, height: 1080, viewport: { x: 700, y: 0, width: 500, height: 1080 } };
  it("uses the viewport", () => expect(cropRect(g, 1920, 1080)).toEqual([700, 0, 500, 1080]));
  it("clamps to a smaller bitmap", () => expect(cropRect(g, 900, 1080)).toEqual([700, 0, 200, 1080]));
});
describe("viewState", () => {
  it("maps states", () => {
    expect(viewState(null)).toBe("disconnected");
    expect(viewState({ state: "pending" })).toBe("pending");
    expect(viewState({ state: "connected" })).toBe("connected");
    for (const s of ["denied", "expired", "error"] as const) expect(viewState({ state: s })).toBe("failed");
  });
});
describe("formatCountdown", () => {
  const now = Date.parse("2026-01-01T00:00:00Z");
  it("formats m:ss", () => expect(formatCountdown("2026-01-01T00:09:05Z", now)).toBe("9:05"));
  it("expires", () => { expect(formatCountdown("2025-12-31T23:59:59Z", now)).toBe("Expired"); expect(formatCountdown(undefined, now)).toBe("Expired"); });
});
describe("streamUrl", () => {
  it("picks ws scheme", () => {
    expect(streamUrl({ protocol: "https:", host: "a.b" })).toBe("wss://a.b/api/glasshand/stream");
    expect(streamUrl({ protocol: "http:", host: "localhost:5173" })).toBe("ws://localhost:5173/api/glasshand/stream");
  });
});
