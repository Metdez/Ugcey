// Pure Glasshand OAuth device-flow calls with injectable fetch. Token endpoint bodies are form-encoded.
import { API, GRANT_DEVICE, type FetchFn, type OAuthError } from "./types";

export interface DeviceCode {
  client_id: string;
  device_code: string;
  user_code: string;
  verification_uri: string;
  verification_uri_complete: string;
  expires_in: number;
  interval: number;
}
export interface Tokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}
export type PollResult =
  | { kind: "ok"; tokens: Tokens }
  | { kind: "pending" }
  | { kind: "slow_down" }
  | { kind: "denied" }
  | { kind: "expired" }
  | { kind: "error"; message: string };

const form = (o: Record<string, string>) => ({
  method: "POST",
  headers: { "content-type": "application/x-www-form-urlencoded", accept: "application/json" },
  body: new URLSearchParams(o).toString(),
});

export async function parseOAuthError(r: Response): Promise<OAuthError> {
  const j = (await r.json().catch(() => ({}))) as { error?: unknown; error_description?: unknown; message?: unknown };
  const e = typeof j.error === "string" ? j.error : "http_" + r.status;
  const d = typeof j.error_description === "string" ? j.error_description : undefined;
  return { error: e, description: d, status: r.status };
}

export async function startDevice(f: FetchFn): Promise<DeviceCode> {
  const r = await f(`${API}/auth/device/code`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify({ clientName: "Ugecy" }),
  });
  if (!r.ok) throw new Error(`glasshand device/code failed: ${(await parseOAuthError(r)).error}`);
  return (await r.json()) as DeviceCode;
}

export async function pollDevice(f: FetchFn, clientId: string, deviceCode: string): Promise<PollResult> {
  const r = await f(`${API}/auth/device/token`, form({ grant_type: GRANT_DEVICE, client_id: clientId, device_code: deviceCode }));
  if (r.ok) return { kind: "ok", tokens: (await r.json()) as Tokens };
  const e = await parseOAuthError(r);
  switch (e.error) {
    case "authorization_pending": return { kind: "pending" };
    case "slow_down": return { kind: "slow_down" };
    case "access_denied": return { kind: "denied" };
    case "expired_token": return { kind: "expired" };
    default: return { kind: "error", message: e.description ?? e.error };
  }
}

/** Rotates the refresh token. `rejected` = grant is dead (operator must re-approve); otherwise transient. */
export async function refreshTokens(
  f: FetchFn,
  clientId: string,
  refreshToken: string,
): Promise<{ ok: true; tokens: Tokens } | { ok: false; rejected: boolean; message: string }> {
  const r = await f(`${API}/auth/device/token`, form({ grant_type: "refresh_token", client_id: clientId, refresh_token: refreshToken }));
  if (r.ok) return { ok: true, tokens: (await r.json()) as Tokens };
  const e = await parseOAuthError(r);
  const rejected = r.status === 400 || r.status === 401 || r.status === 403;
  return { ok: false, rejected, message: e.description ?? e.error };
}
