// Glasshand connection state machine. Runs inside the AgentRuntime DO; all mutations are serialized by `lock`.
import { pollDevice, refreshTokens, startDevice } from "./oauth";
import { API, REFRESH_SKEW_MS, type FetchFn, type GlasshandRental, type GlasshandStatus, type GlasshandStore } from "./types";

const PENDING = ["device_code", "interval", "expires_at", "last_poll_at", "user_code", "verification_uri", "verification_uri_complete"];
const TOKENS = ["access_token", "refresh_token", "access_expires_at"];

interface ApiRental extends GlasshandRental {
  [k: string]: unknown;
}

export class Glasshand {
  private chain: Promise<unknown> = Promise.resolve();

  constructor(
    private store: GlasshandStore,
    private f: FetchFn = (i, init) => fetch(i, init),
    private now: () => number = Date.now,
  ) {}

  private lock<T>(fn: () => Promise<T>): Promise<T> {
    const p = this.chain.then(fn, fn);
    this.chain = p.catch(() => undefined);
    return p;
  }

  state(): { connected: boolean; selected_rental_id: string | null } {
    const s = this.store.all();
    return { connected: !!(s.access_token && s.refresh_token), selected_rental_id: s.selected_rental_id ?? null };
  }

  async connect(): Promise<GlasshandStatus> {
    if (this.state().connected) return this.connected();
    const r = await this.lock(async (): Promise<GlasshandStatus | "connected"> => {
      if (this.state().connected) return "connected";
      const d = await startDevice(this.f);
      this.store.put({
        client_id: d.client_id,
        device_code: d.device_code,
        interval: String(d.interval),
        expires_at: String(this.now() + d.expires_in * 1000),
        last_poll_at: "0",
        user_code: d.user_code,
        verification_uri: d.verification_uri,
        verification_uri_complete: d.verification_uri_complete,
      });
      return this.pending();
    });
    return r === "connected" ? this.connected() : r;
  }

  async status(): Promise<GlasshandStatus> {
    if (this.state().connected) return this.connected();
    if (!this.store.all().device_code) return { state: "disconnected" };
    const r = await this.lock(() => this.pollOnce()); // connected() must run outside the lock: it may refresh
    return r === "connected" ? this.connected() : r;
  }

  async select(rentalId: string): Promise<GlasshandStatus> {
    if (!this.state().connected) return { state: "disconnected" };
    const items = await this.rentals();
    if (items === null) return { state: "disconnected" };
    if (!items.some((r) => r.id === rentalId)) return { state: "error", message: "rental not found" };
    this.store.put({ selected_rental_id: rentalId });
    return this.connected();
  }

  async disconnect(): Promise<GlasshandStatus> {
    return this.lock(async () => {
      this.store.del(Object.keys(this.store.all()));
      return { state: "disconnected" };
    });
  }

  /** Fresh access token (refreshing when < 60 s remain), or null if not connected / re-approval needed. */
  async token(stale?: string): Promise<string | null> {
    const ok = (s: Record<string, string>) =>
      stale === undefined ? Number(s.access_expires_at) - this.now() > REFRESH_SKEW_MS : s.access_token !== stale;
    const s = this.store.all();
    if (!s.refresh_token || !s.access_token) return null;
    if (ok(s)) return s.access_token;
    return this.lock(async () => {
      const cur = this.store.all(); // another caller may have rotated while we waited
      if (!cur.refresh_token || !cur.access_token) return null;
      if (ok(cur)) return cur.access_token;
      const r = await refreshTokens(this.f, cur.client_id ?? "", cur.refresh_token);
      if (r.ok) {
        // one atomic write: both tokens rotate together
        this.store.put({
          access_token: r.tokens.access_token,
          refresh_token: r.tokens.refresh_token,
          access_expires_at: String(this.now() + r.tokens.expires_in * 1000),
        });
        return r.tokens.access_token;
      }
      if (r.rejected) {
        this.store.del([...TOKENS, "selected_rental_id"]);
        return null;
      }
      throw new Error(`glasshand token refresh failed: ${r.message}`);
    });
  }

  // ---- internals ----
  private pending(): GlasshandStatus {
    const s = this.store.all();
    return {
      state: "pending",
      user_code: s.user_code,
      verification_uri: s.verification_uri,
      verification_uri_complete: s.verification_uri_complete,
      expires_at: new Date(Number(s.expires_at)).toISOString(),
      interval: Number(s.interval),
    };
  }

  private async pollOnce(): Promise<GlasshandStatus | "connected"> {
    const s = this.store.all();
    if (!s.device_code) return this.state().connected ? "connected" : { state: "disconnected" };
    const now = this.now();
    if (now >= Number(s.expires_at)) {
      this.store.del(PENDING);
      return { state: "expired" };
    }
    if (now - Number(s.last_poll_at) < Number(s.interval) * 1000) return this.pending();
    this.store.put({ last_poll_at: String(now) });
    let r;
    try {
      r = await pollDevice(this.f, s.client_id ?? "", s.device_code);
    } catch (e) {
      return { ...this.pending(), message: e instanceof Error ? e.message : "poll failed" };
    }
    switch (r.kind) {
      case "pending":
        return this.pending();
      case "slow_down":
        this.store.put({ interval: String(Number(s.interval) + 5) });
        return this.pending();
      case "denied":
        this.store.del(PENDING);
        return { state: "denied" };
      case "expired":
        this.store.del(PENDING);
        return { state: "expired" };
      case "error":
        return { ...this.pending(), message: r.message };
      case "ok":
        this.store.put({
          access_token: r.tokens.access_token,
          refresh_token: r.tokens.refresh_token,
          access_expires_at: String(now + r.tokens.expires_in * 1000),
        });
        this.store.del(PENDING);
        return "connected";
    }
  }

  /** GET /rentals with one refresh+retry on 401; null when not connected. */
  private async rentals(): Promise<ApiRental[] | null> {
    let t = await this.token();
    if (!t) return null;
    const get = (tok: string) => this.f(`${API}/rentals`, { headers: { authorization: `Bearer ${tok}`, accept: "application/json" } });
    let r = await get(t);
    if (r.status === 401) {
      await r.body?.cancel();
      t = await this.token(t);
      if (!t) return null;
      r = await get(t);
    }
    if (!r.ok) throw new Error(`glasshand rentals failed: HTTP ${r.status}`);
    return ((await r.json()) as { items: ApiRental[] }).items;
  }

  private async connected(): Promise<GlasshandStatus> {
    let items: ApiRental[] | null;
    try {
      items = await this.rentals();
    } catch (e) {
      return { state: "connected", rentals: [], selected_rental_id: this.state().selected_rental_id, message: e instanceof Error ? e.message : "rentals failed" };
    }
    if (items === null) return { state: "disconnected", message: "Glasshand needs re-approval" };
    const rentals: GlasshandRental[] = items.map((r) => ({ id: r.id, name: r.name, kind: r.kind, status: r.status, deviceReady: r.deviceReady }));
    let sel = this.state().selected_rental_id;
    if (!sel) {
      sel = rentals.find((r) => r.deviceReady && (r.status === "active" || r.status === "grace"))?.id ?? null;
      if (sel) this.store.put({ selected_rental_id: sel });
    }
    return { state: "connected", rentals, selected_rental_id: sel };
  }
}
