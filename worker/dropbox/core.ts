// Dropbox connection state. Runs inside the AgentRuntime DO; token mutations are serialized by `lock`.
import { authorizeUrl, exchangeCode, refresh, revoke } from "./oauth";
import { API, InvalidCodeError, REFRESH_SKEW_MS, REQUIRED_SCOPES, STATUS_TTL_MS, type DropboxStatus, type DropboxStore, type FetchFn } from "./types";

const TOKENS = ["access_token", "refresh_token", "expires_at", "scopes", "account_id", "account_name", "email", "account_at"];
type Keys = { DROPBOX_APP_KEY?: string; DROPBOX_APP_SECRET?: string };

export class Dropbox {
  private chain: Promise<unknown> = Promise.resolve();

  constructor(
    private store: DropboxStore,
    private env: Keys,
    private f: FetchFn = (i, init) => fetch(i, init),
    private now: () => number = Date.now,
  ) {}

  private lock<T>(fn: () => Promise<T>): Promise<T> {
    const p = this.chain.then(fn, fn);
    this.chain = p.catch(() => undefined);
    return p;
  }

  private creds(): [string, string] | null {
    const { DROPBOX_APP_KEY: k, DROPBOX_APP_SECRET: s } = this.env;
    return k && s ? [k, s] : null;
  }

  /** null when the app keys are not set. */
  connectUrl(): string | null {
    const k = this.env.DROPBOX_APP_KEY;
    return k && this.creds() ? authorizeUrl(k) : null;
  }

  async submitCode(code: string): Promise<DropboxStatus> {
    const c = this.creds();
    if (!c) throw new Error("Dropbox app keys are not set");
    await this.lock(async () => {
      const r = await exchangeCode(code.trim(), c[0], c[1], this.f);
      if (!r.ok) {
        if (r.status === 400) throw new InvalidCodeError(r.message);
        throw new Error(`dropbox code exchange failed: ${r.message}`);
      }
      const t = r.tokens;
      if (!t.refresh_token) throw new InvalidCodeError("Dropbox returned no refresh token");
      this.store.del(TOKENS);
      this.store.put({
        access_token: t.access_token,
        refresh_token: t.refresh_token,
        expires_at: String(this.now() + t.expires_in * 1000),
        scopes: t.scope ?? "",
        account_id: t.account_id ?? "",
      });
    });
    return this.status();
  }

  /** Fresh access token (refreshing when < 60 s remain or `stale` just got a 401), or null if not connected. */
  async token(stale?: string): Promise<string | null> {
    const ok = (s: Record<string, string>) =>
      stale === undefined ? Number(s.expires_at) - this.now() > REFRESH_SKEW_MS : s.access_token !== stale;
    const s = this.store.all();
    if (!s.refresh_token || !s.access_token) return null;
    if (ok(s)) return s.access_token;
    const c = this.creds();
    if (!c) return null;
    return this.lock(async () => {
      const cur = this.store.all(); // another caller may have refreshed while we waited
      if (!cur.refresh_token || !cur.access_token) return null;
      if (ok(cur)) return cur.access_token;
      const r = await refresh(cur.refresh_token, c[0], c[1], this.f);
      if (r.ok) {
        this.store.put({ access_token: r.tokens.access_token, expires_at: String(this.now() + r.tokens.expires_in * 1000) });
        return r.tokens.access_token;
      }
      if (r.rejected) {
        this.store.del(TOKENS);
        return null;
      }
      throw new Error(`dropbox token refresh failed: ${r.message}`);
    });
  }

  async status(): Promise<DropboxStatus> {
    const configured = !!this.creds();
    const s = this.store.all();
    if (!s.refresh_token || !s.access_token) return { configured, connected: false, scopes: [], missing_scopes: [] };
    const scopes = (s.scopes ?? "").split(" ").filter(Boolean);
    const out: DropboxStatus = { configured, connected: true, scopes, missing_scopes: REQUIRED_SCOPES.filter((r) => !scopes.includes(r)) };
    const acct = await this.account(s);
    if (acct) Object.assign(out, acct);
    return out;
  }

  async disconnect(): Promise<DropboxStatus> {
    const t = this.store.all().access_token;
    if (t) await revoke(t, this.f).catch(() => undefined);
    await this.lock(async () => this.store.del(TOKENS));
    return this.status();
  }

  /** Account name/email, cached 5 min; undefined if unavailable. */
  private async account(s: Record<string, string>): Promise<{ account_name?: string; email?: string } | undefined> {
    if (s.account_at && this.now() - Number(s.account_at) < STATUS_TTL_MS)
      return { account_name: s.account_name || undefined, email: s.email || undefined };
    try {
      let t = await this.token();
      if (!t) return undefined;
      const get = (tok: string) => this.f(`${API}/2/users/get_current_account`, { method: "POST", headers: { authorization: `Bearer ${tok}` } });
      let r = await get(t);
      if (r.status === 401) {
        await r.body?.cancel();
        t = await this.token(t);
        if (!t) return undefined;
        r = await get(t);
      }
      if (!r.ok) {
        await r.body?.cancel();
        return undefined;
      }
      const a = (await r.json()) as { name?: { display_name?: string }; email?: string };
      const account_name = a.name?.display_name ?? "";
      const email = a.email ?? "";
      this.store.put({ account_name, email, account_at: String(this.now()) });
      return { account_name: account_name || undefined, email: email || undefined };
    } catch {
      return undefined;
    }
  }
}
