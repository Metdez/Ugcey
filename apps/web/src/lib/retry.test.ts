import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { retryTransient } from "./retry";

describe("retryTransient", () => {
  const noWait = async () => {};
  it("rides out a restart: 503s and network errors, then success", async () => {
    const errs: unknown[] = [new ApiError(503, "x", "down"), new TypeError("Failed to fetch")];
    let n = 0;
    expect(await retryTransient(async () => { if (n < errs.length) throw errs[n++]; return "ok"; }, 5, noWait)).toBe("ok");
  });
  it("does not retry client errors, and gives up after `tries`", async () => {
    let n = 0;
    await expect(retryTransient(async () => { n++; throw new ApiError(404, "not_found", "gone"); }, 5, noWait)).rejects.toThrow("gone");
    expect(n).toBe(1);
    n = 0;
    await expect(retryTransient(async () => { n++; throw new ApiError(500, "e", "boom"); }, 3, noWait)).rejects.toThrow("boom");
    expect(n).toBe(3);
  });
});
