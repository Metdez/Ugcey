import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GlasshandLive } from "./glasshand-live";

class FakeSocket {
  static last: FakeSocket;
  binaryType = "blob";
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor() { FakeSocket.last = this; }
  close() {}
  emit(data: unknown) { this.onmessage?.({ data }); }
}
const HELLO = JSON.stringify({ type: "hello", geometry: { width: 8, height: 8, viewport: { x: 0, y: 0, width: 4, height: 8 } } });
const tick = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });
const badge = () => screen.getByText(/^(LIVE|SNAPSHOTS|CONNECTING)/).textContent;

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.stubGlobal("createImageBitmap", vi.fn(async () => ({ width: 8, height: 8, close() {} })));
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage() {} } as unknown as CanvasRenderingContext2D);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("GlasshandLive", () => {
  it("never shows a blank LIVE · 0 fps: hello without frames falls back to snapshots after ~3 s", () => {
    render(<GlasshandLive rentalId="r1" />);
    expect(FakeSocket.last.binaryType).toBe("arraybuffer");
    act(() => FakeSocket.last.emit(HELLO));
    tick(1000);
    expect(badge()).toBe("CONNECTING");
    tick(3000);
    expect(badge()).toBe("SNAPSHOTS");
    expect(screen.getByRole("status").textContent).toMatch(/not sending frames/);
    expect(screen.getByAltText("iPhone screen snapshot")).toBeTruthy();
  });

  it("goes LIVE once a frame is drawn, and back to snapshots when frames stop for ~5 s", async () => {
    render(<GlasshandLive rentalId="r1" />);
    act(() => FakeSocket.last.emit(HELLO));
    await act(async () => { FakeSocket.last.emit(new Uint8Array([0xff, 0xd8]).buffer); await Promise.resolve(); });
    tick(1000);
    expect(badge()).toMatch(/^LIVE · \d fps$/);
    expect(screen.queryByAltText("iPhone screen snapshot")).toBeNull();
    tick(5000);
    expect(badge()).toBe("SNAPSHOTS");
  });

  it("shows snapshots with an honest note when capture is unavailable", () => {
    render(<GlasshandLive rentalId="r1" />);
    act(() => { FakeSocket.last.emit(HELLO); FakeSocket.last.emit(JSON.stringify({ type: "capture_status", available: false })); });
    tick(1000);
    expect(badge()).toBe("SNAPSHOTS");
    expect(screen.getByRole("status").textContent).toMatch(/capture unavailable/);
  });
});
