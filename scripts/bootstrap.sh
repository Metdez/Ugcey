#!/usr/bin/env bash
# Idempotent: creates the Ugecy Cloudflare resources if missing, applies D1 migrations, prints D1_ID / KV_ID.
# Needs CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN. Never touches resspark* resources.
set -euo pipefail
cd "$(dirname "$0")/.."
W="pnpm exec wrangler"
DB=ugecy-db KVN=ugecy-cache Q=ugecy-jobs DLQ=ugecy-jobs-dlq VEC=ugecy-memory

json() { node -e "$1" 2>/dev/null; }  # reads JSON on stdin

# D1
if ! $W d1 list --json | json "process.exit(JSON.parse(require('fs').readFileSync(0,'utf8')).some(d=>d.name==='$DB')?0:1)"; then
  $W d1 create "$DB"
fi
D1_ID=$($W d1 list --json | json "const d=JSON.parse(require('fs').readFileSync(0,'utf8')).find(d=>d.name==='$DB');console.log(d.uuid||d.id)")

# KV (title is prefixed by worker name only for wrangler-managed ones; match on suffix)
KV_ID=$($W kv namespace list | json "const k=JSON.parse(require('fs').readFileSync(0,'utf8')).find(k=>k.title==='$KVN');if(k)console.log(k.id)" || true)
if [ -z "$KV_ID" ]; then
  $W kv namespace create "$KVN" >/dev/null
  KV_ID=$($W kv namespace list | json "console.log(JSON.parse(require('fs').readFileSync(0,'utf8')).find(k=>k.title==='$KVN').id)")
fi

# Queues (no --json on list: match the name as a whole word)
QUEUES=$($W queues list 2>/dev/null || true)
for q in "$DLQ" "$Q"; do  # DLQ first: the consumer references it
  if ! grep -qw -- "$q" <<<"$QUEUES"; then $W queues create "$q"; fi
done

# Vectorize: qwen3-embedding-0.6b outputs 1024 dimensions (checked in Workers AI docs)
if ! $W vectorize list --json | json "process.exit(JSON.parse(require('fs').readFileSync(0,'utf8')).some(i=>i.name==='$VEC')?0:1)"; then
  $W vectorize create "$VEC" --dimensions=1024 --metric=cosine
fi

# Migrations: wrangler needs the real D1 id, so render wrangler.deploy.jsonc at the repo root (migrations_dir resolves next to it)
if [ -d migrations ]; then
  D1_ID="$D1_ID" KV_ID="$KV_ID" node scripts/render-config.mjs wrangler.jsonc wrangler.deploy.jsonc
  $W d1 migrations apply "$DB" --remote --config wrangler.deploy.jsonc
fi

echo "D1_ID=$D1_ID"
echo "KV_ID=$KV_ID"
