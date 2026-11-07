// Shared types for the Glasshand edge. Tokens only ever live in a GlasshandStore (DO SQLite); never log them.
import type { GlasshandRental, GlasshandStatus } from "../../packages/contracts/src/models";

export type { GlasshandRental, GlasshandStatus };

export const API = "https://api.glasshand.com/v1";
export const GRANT_DEVICE = "urn:ietf:params:oauth:grant-type:device_code";
export const REFRESH_SKEW_MS = 60_000;

/** Flat string key/value store backed by the `glasshand` table (or a Map in tests). */
export interface GlasshandStore {
  all(): Record<string, string>;
  put(patch: Record<string, string>): void; // atomic: all keys or none
  del(keys: string[]): void;
}

export type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

export interface OAuthError {
  error: string;
  description?: string;
  status: number;
}

/** What the egress gateway and relay need from the runtime DO (an RPC stub or a test fake). */
export interface GlasshandRuntime {
  glasshandState(): Promise<{ connected: boolean; selected_rental_id: string | null }>;
  /** Fresh access token, or null when not connected. Pass the token that just got a 401 to force a (deduplicated) refresh. */
  glasshandToken(stale?: string): Promise<string | null>;
}
