-- Ugecy system of record. Applied to D1 by wrangler and by the local sqlite AppStore (same file).
-- Mirrored at services/agent/ugecy/persistence/schema.sql (a test keeps them equal).
CREATE TABLE IF NOT EXISTS threads (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'idle'
);
CREATE INDEX IF NOT EXISTS idx_threads_updated ON threads(updated_at);

CREATE TABLE IF NOT EXISTS audit (
  id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  thread_id TEXT,
  actor TEXT NOT NULL,
  agent TEXT,
  action TEXT NOT NULL,
  tool TEXT,
  status TEXT NOT NULL,
  mode TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_thread ON audit(thread_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts);

CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  thread_id TEXT,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt TEXT NOT NULL,
  url TEXT,
  thumbnail_url TEXT,
  job_id TEXT,
  mode TEXT NOT NULL,
  estimated_usd REAL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assets_thread ON assets(thread_id);
CREATE INDEX IF NOT EXISTS idx_assets_created ON assets(created_at);

CREATE TABLE IF NOT EXISTS posts (
  id TEXT PRIMARY KEY,
  thread_id TEXT,
  account_id TEXT NOT NULL,
  asset_id TEXT,
  caption TEXT NOT NULL,
  ai_disclosure INTEGER NOT NULL,
  status TEXT NOT NULL,
  publish_at TEXT,
  external_url TEXT,
  mode TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_thread ON posts(thread_id);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at);

CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  handle TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'connected'
);

CREATE TABLE IF NOT EXISTS approvals (
  interrupt_id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  requests TEXT NOT NULL,          -- JSON: ApprovalRequest[]
  created_at TEXT NOT NULL,
  decided_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_approvals_thread ON approvals(thread_id);
CREATE INDEX IF NOT EXISTS idx_approvals_created ON approvals(created_at);

CREATE TABLE IF NOT EXISTS sources (
  thread_id TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  platform TEXT,
  snippet TEXT,
  created_at TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (thread_id, url)
);
CREATE INDEX IF NOT EXISTS idx_sources_thread ON sources(thread_id);
