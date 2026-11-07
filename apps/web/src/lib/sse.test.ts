import { describe, expect, it } from "vitest";
import { readSse } from "./sse";

const body = (chunks: string[]) =>
  new ReadableStream<Uint8Array>({
    start(c) {
      for (const ch of chunks) c.enqueue(new TextEncoder().encode(ch));
      c.close();
    },
  });

describe("readSse", () => {
  it("handles chunk boundaries mid-event, CRLF, comments and multi-line data", async () => {
    const got: [string, string][] = [];
    await readSse(body([": ping\r\n\r\nevent: a\r\nda", "ta: {\"x\":1}\r\n\r\nevent: b\ndata: l1\ndata: l2\n", "\ndata: tail\n\n"]),
      (e, d) => got.push([e, d]));
    expect(got).toEqual([["a", '{"x":1}'], ["b", "l1\nl2"], ["message", "tail"]]);
  });

  it("splits a multibyte char across chunks", async () => {
    const bytes = new TextEncoder().encode("data: é\n\n");
    const s = new ReadableStream<Uint8Array>({ start(c) { c.enqueue(bytes.slice(0, 7)); c.enqueue(bytes.slice(7)); c.close(); } });
    const got: string[] = [];
    await readSse(s, (_e, d) => got.push(d));
    expect(got).toEqual(["é"]);
  });
});
