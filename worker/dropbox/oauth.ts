// Pure Dropbox OAuth calls with injectable fetch. Code flow without redirect_uri: Dropbox shows the code on its page.
import { API, type FetchFn } from "./types";

export interface Tokens {
  access_token: string;
  expires_in: number;
  refresh_token?: string; // only on code exchange; Dropbox refresh tokens don't rotate
  scope?: string;
  account_id?: string;
}
export type TokenResult = { ok: true; tokens: Tokens } | { ok: false; status: number; rejected: boolean; message: string };

export const authorizeUrl = (appKey: string) =>
  `https://www.dropbox.com/oauth2/authorize?client_id=${encodeURIComponent(appKey)}&response_type=code&token_access_type=offline`;

async function token(f: FetchFn, key: string, secret: string, form: Record<string, string>): Promise<TokenResult> {
  const r = await f(`${API}/oauth2/token`, {
    method: "POST",
    headers: {
      "content-type": "application/x-www-form-urlencoded",
      accept: "application/json",
      authorization: `Basic ${btoa(`${key}:${secret}`)}`,
    },
    body: new URLSearchParams(form).toString(),
  });
  if (r.ok) return { ok: true, tokens: (await r.json()) as Tokens };
  const j = (await r.json().catch(() => ({}))) as { error?: unknown; error_description?: unknown };
  const message = typeof j.error_description === "string" ? j.error_description : typeof j.error === "string" ? j.error : `HTTP ${r.status}`;
  return { ok: false, status: r.status, rejected: r.status === 400 || r.status === 401, message };
}

export const exchangeCode = (code: string, key: string, secret: string, f: FetchFn) =>
  token(f, key, secret, { grant_type: "authorization_code", code });

export const refresh = (refreshToken: string, key: string, secret: string, f: FetchFn) =>
  token(f, key, secret, { grant_type: "refresh_token", refresh_token: refreshToken });

/** Best effort: failures are ignored by the caller. */
export async function revoke(accessToken: string, f: FetchFn): Promise<void> {
  const r = await f(`${API}/2/auth/token/revoke`, { method: "POST", headers: { authorization: `Bearer ${accessToken}` } });
  await r.body?.cancel();
}
