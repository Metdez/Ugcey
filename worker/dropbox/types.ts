// Shared types for the Dropbox edge. Tokens only ever live in a DropboxStore (DO SQLite); never log them.
import type { DropboxStatus } from "../../packages/contracts/src/models";

export type { DropboxStatus };

export const API = "https://api.dropboxapi.com";
export const REFRESH_SKEW_MS = 60_000;
export const STATUS_TTL_MS = 5 * 60_000;
export const REQUIRED_SCOPES = ["account_info.read", "files.metadata.read", "files.content.read", "files.content.write"];

/** Flat string key/value store backed by the `dropbox` table (or a Map in tests). */
export interface DropboxStore {
  all(): Record<string, string>;
  put(patch: Record<string, string>): void; // atomic: all keys or none
  del(keys: string[]): void;
}

export type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

/** Thrown by submitCode when Dropbox rejects the code. */
export class InvalidCodeError extends Error {
  constructor(message = "Dropbox rejected that code") {
    super(message);
  }
}

/** What the egress gateway needs from the runtime DO (an RPC stub or a test fake). */
export interface DropboxRuntime {
  dropboxStatus(): Promise<DropboxStatus>;
  /** Fresh access token, or null when not connected. Pass the token that just got a 401 to force a refresh. */
  dropboxToken(stale?: string): Promise<string | null>;
}
