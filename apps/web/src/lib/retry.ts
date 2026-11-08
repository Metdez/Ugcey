// Retry a request through transient failures (network errors, 5xx) such as a server restart.
import { ApiError } from "@/lib/api";

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** True for failures worth retrying: no response at all, or a server-side (5xx) error. */
export const isTransient = (err: unknown) => !(err instanceof ApiError) || err.status >= 500;

/** Run `fn`, retrying transient failures with backoff (1, 2, 4, 8, 8… s; ~70 s in all, past a container cold start). */
export async function retryTransient<T>(fn: () => Promise<T>, tries = 11, sleep = wait): Promise<T> {
  for (let i = 0; ; i++) {
    try {
      return await fn();
    } catch (err) {
      if (!isTransient(err) || i >= tries - 1) throw err;
      await sleep(Math.min(1000 * 2 ** i, 8000));
    }
  }
}
