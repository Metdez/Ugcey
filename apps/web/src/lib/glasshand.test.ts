import { describe, expect, it } from "vitest";
import { cropRect, feedMode, formatCountdown, streamUrl, viewState, type FeedInput } from "./glasshand";

describe("feedMode", () => {
  const base: FeedInput = { helloAt: 1000, lastFrameAt: null, captureAvailable: true, paused: false, now: 1000 };
  const at = (o: Partial<FeedInput>) => feedMode({ ...base, ...o });
  it("snapshots while the socket is not live", () => expect(at({ helloAt: null })).toBe("snapshots"));
  it("waits ~3 s for a first frame, then shows snapshots instead of a blank LIVE canvas", () => {
    expect(at({ now: 3999 })).toBe("connecting");
    expect(at({ now: 4000 })).toBe("snapshots");
  });
  it("is live while frames are fresh and falls back after ~5 s without one", () => {
    expect(at({ lastFrameAt: 2000, now: 6999 })).toBe("live");
    expect(at({ lastFrameAt: 2000, now: 7000 })).toBe("snapshots");
    expect(at({ lastFrameAt: 2000, now: 60000, paused: true })).toBe("live"); // paused keeps the last frame
  });
  it("snapshots when Glasshand reports capture unavailable", () =>
    expect(at({ lastFrameAt: 1000, now: 1000, captureAvailable: false })).toBe("snapshots"));
});

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
