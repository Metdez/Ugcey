import { describe, expect, it } from "vitest";
import type { Env, RuntimeProps } from "../env";
import { handleState } from "../egress/state";

const PROPS = { runtimeId: "rt" } as RuntimeProps;
const env = (next: string | null) => {
  const calls: unknown[][] = [];
  const rt = { kvGet: async (...a: unknown[]) => (calls.push(a), { items: [{ key: "a", value_b64: "MQ==" }], next }) };
  return { calls, env: { AGENT_RUNTIME: { idFromString: (s: string) => s, get: () => rt } } as unknown as Env };
};
const get = (body: object, e: Env) =>
  handleState(new Request("http://state.internal/kv/get", { method: "POST", body: JSON.stringify(body) }), e, PROPS);

describe("state.internal /kv/get", () => {
  it("returns one page and its cursor to a paging caller", async () => {
    const { calls, env: e } = env("a");
    const r = await get({ ns: "ckpt:t", prefix: "c|", after: "" }, e);
    expect(await r.json()).toEqual({ items: [{ key: "a", value_b64: "MQ==" }], next: "a" });
    expect(calls[0]).toEqual(["ckpt:t", "c|", ""]);
  });
  it("fails a caller that does not page instead of truncating its read", async () => {
    expect((await get({ ns: "ckpt:t", prefix: "" }, env("a").env)).status).toBe(400);
    expect(await (await get({ ns: "ckpt:t", prefix: "" }, env(null).env)).json()).toEqual({ items: [{ key: "a", value_b64: "MQ==" }], next: null });
  });
});
