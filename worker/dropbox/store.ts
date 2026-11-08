// DropboxStore implementations: DO SQLite (`dropbox` table) and an in-memory one for tests.
import type { DropboxStore } from "./types";

export function sqlStore(storage: DurableObjectStorage): DropboxStore {
  const sql = storage.sql;
  sql.exec("CREATE TABLE IF NOT EXISTS dropbox (k TEXT PRIMARY KEY, v TEXT)");
  return {
    all() {
      const out: Record<string, string> = {};
      for (const r of sql.exec<{ k: string; v: string }>("SELECT k, v FROM dropbox")) out[r.k] = r.v;
      return out;
    },
    put(patch) {
      storage.transactionSync(() => {
        for (const [k, v] of Object.entries(patch))
          sql.exec("INSERT INTO dropbox (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v", k, v);
      });
    },
    del(keys) {
      storage.transactionSync(() => {
        for (const k of keys) sql.exec("DELETE FROM dropbox WHERE k = ?", k);
      });
    },
  };
}

export function memoryStore(): DropboxStore {
  const m = new Map<string, string>();
  return {
    all: () => Object.fromEntries(m),
    put: (p) => void Object.entries(p).forEach(([k, v]) => m.set(k, v)),
    del: (ks) => void ks.forEach((k) => m.delete(k)),
  };
}
