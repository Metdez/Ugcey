#!/usr/bin/env bash
# Build web, render wrangler.deploy.jsonc with real IDs, deploy. Usage: D1_ID=... KV_ID=... scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
: "${D1_ID:?set D1_ID (printed by scripts/bootstrap.sh)}"
: "${KV_ID:?set KV_ID (printed by scripts/bootstrap.sh)}"

pnpm --filter web build
node scripts/render-config.mjs wrangler.jsonc wrangler.deploy.jsonc
pnpm exec wrangler deploy --config wrangler.deploy.jsonc
echo "Deployed. URL: https://ugecy.${CLOUDFLARE_WORKERS_SUBDOMAIN:-zh-a16}.workers.dev"
