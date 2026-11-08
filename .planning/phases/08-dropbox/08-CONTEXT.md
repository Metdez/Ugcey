# Phase 08: Dropbox media library

## Operator ask (2026-11-07)
- Add a Dropbox tool to the agent.
- When this ships, move all existing Higgsfield content to Dropbox. From then on, every new Higgsfield output is added to Dropbox automatically.
- The operator signs in to the Dropbox app on the iPhone themselves. The agent should know, through memory and prompts, that new videos are found in the Dropbox app.
- Wire up the Dropbox environment variables so the agent has access.

## Findings: codebase (read-only exploration)
- **Higgsfield outputs are never copied anywhere durable.**
  - `tools/media.py:_poll` takes `job.outputs[0].url` and calls `edge.media_ingest`.
  - The Worker queue consumer only copies videos, and only into Stream. `STREAM` is not configured, so `Asset.url` stays a Higgsfield CloudFront URL.
  - Higgsfield deletes outputs after **7 days** (`_RETENTION_DAYS`).
- **Live data:** 35 assets (32 images, 3 videos), all created 2026-11-07, all on `d3u0tzju9qaucj.cloudfront.net`. They expire around 2026-11-14, so the backfill has a deadline.
- **Finalization happens in Python:**
  - `_poll` runs as a background task (2 s to 10 s backoff, 15 min cap).
  - `resume_media_jobs()` runs at startup (`main.py`).
  - `check_media_job` only reads D1. Nothing depends on the agent calling it again.
- **Assets:** stored in the D1 `assets` table (`migrations/0001_init.sql:27-43`). `AppStore.upsert_asset` is a generic upsert generated from the model fields. `/api/assets` serves them to the Assets tab.
- **There is no Higgsfield "list past generations" API.** The backfill source is D1.
- **Credential pattern to copy is Glasshand:**
  - Tokens live in DO SQLite (`worker/glasshand/{store,core,oauth,egress,routes}.ts`).
  - Refresh runs under a promise lock, with a 60 s skew and one retry after a 401.
  - The egress handler injects the bearer for `glasshand.internal`.
  - `/_ugecy/status` is answered locally and drives a live mode in Python (`integrations/device/auto.py`, 15 s cache).
  - Routes are mounted after `requireKey` in `worker/index.ts`.
- **Cookie gate:** the `ugecy_key` cookie is `SameSite=Lax`, so a top-level GET redirect from dropbox.com back to `/api/dropbox/callback` carries it. The callback can live under `/api/*`.
- **Hosts:** a container egress host is added through `VHOSTS` in `worker/do/agent-runtime.ts` plus a case in `worker/egress/gateway.ts`. Env flags reach the container only when it starts, so the live status check is the source of truth.
- **Phone posting today:** `device-operator.md` step 1 opens the Higgsfield URL in Safari, then uses "Save Video". This breaks once the URL expires.

## Findings: Dropbox API (docs.dropboxapi.com, via Firecrawl)
- **OAuth code flow for a server-side app with background access** (the OAuth guide's recommendation):
  - `https://www.dropbox.com/oauth2/authorize?client_id=<APP_KEY>&response_type=code&token_access_type=offline&redirect_uri=<exact registered URI>&state=<csrf>`
  - `POST https://api.dropboxapi.com/oauth2/token`, with `grant_type=authorization_code` (code + redirect_uri) or `grant_type=refresh_token`, authenticated with the app key and secret as Basic auth.
  - The response holds a short-lived `access_token` with `expires_in` (about 4 h), plus a long-lived `refresh_token` that does not rotate.
  - The `redirect_uri` must be registered **exactly** in the app console. It must be HTTPS (localhost excepted).
  - `state` (up to 2000 bytes) is the CSRF guard.
- **Scopes** are enabled in the console's Permissions tab and requested at authorize. We need:
  - `account_info.read` (status)
  - `files.metadata.read` and `files.metadata.write` (list, get_metadata, folders)
  - `files.content.write` (save_url)
  - `files.content.read` (temporary links)
- **`POST /2/files/save_url {path, url}`:** Dropbox fetches the URL itself, so no bytes pass through the Worker or the container.
  - It returns `{".tag":"async_job_id"}` or `{".tag":"complete"}`.
  - Poll `/2/files/save_url/check_job_status {async_job_id}` until `complete` or `failed`.
  - The transfer must finish within 15 minutes.
  - Errors: `invalid_url`, `download_failed`, `path`.
- **Other endpoints:**
  - `/2/files/get_temporary_link` (4 h, private) keeps assets viewable after Higgsfield deletes them, without making public share links.
  - `/2/files/list_folder` (+`/continue`), `/2/files/get_metadata`, `/2/users/get_current_account`.
  - Every RPC endpoint is on `api.dropboxapi.com`, so the content host isn't needed.
- **Errors:** 429 comes with `Retry-After`; back off and retry. 409 is endpoint-specific (e.g. `path/conflict`). A 401 means refresh and retry.
- **App folder vs. Full Dropbox:** set on the app. We write under `/Ugecy/...` relative to the app root, which works either way. With an App-folder app the operator sees it at `Apps/<app name>/Ugecy`.
- **Getting a file from the iPhone Dropbox app into Photos** (help.dropbox.com/installs/export-files-mobile): Files tab → `•••` on the file → Export → **Save video** / Save image. Search finds a file by name in any folder.

## Environment variables
- The cloud environment has `DROPBOX_APP_KEY` and `DROPBOX_APP_SECRET`. They are not in the current container yet; they load when a session starts or resumes.
- At build time they are piped (never printed) into Worker secrets with `wrangler secret put` and added to `worker/env.ts`.
- The OAuth refresh token is not an env var. The Connect flow creates it and stores it in DO SQLite, so it never reaches the container.

## Decisions
1. **Auth:** OAuth code flow with offline refresh, Worker side, mirroring Glasshand.
   - `GET /api/dropbox/authorize` → Dropbox → `GET /api/dropbox/callback`, which redirects to `/?dropbox=connected`.
   - Also `GET /api/dropbox/status` and `POST /api/dropbox/disconnect` (calls `/2/auth/token/revoke`).
2. **Egress:** a new `dropbox.internal` host.
   - The Worker injects a fresh bearer (refresh under a lock, retry once after a 401).
   - Path allowlist covers only the endpoints above.
   - `/_ugecy/status` is answered locally.
3. **Copying:** Dropbox `save_url` pulls straight from the Higgsfield URL.
   - Driven from Python: `ugecy/storage/backup.py`, hooked after `_poll` marks an asset completed.
   - A reconcile pass backs up every completed, unexpired asset not yet saved. It runs at startup, right after Connect (the backfill) and from a tool.
   - Same durability model as `resume_media_jobs`. All outputs are covered, images and videos.
4. **Naming:** `/Ugecy/Videos/<YYYY-MM-DD> <prompt-slug> <asset8>.mp4` (and `Images/`, `Audio/`).
   - The extension comes from the URL, falling back to the kind.
   - On a `path/conflict`, check `get_metadata`. A matching file counts as already saved, which makes retries idempotent.
5. **Data:** add `dropbox_path` and `dropbox_status` (`pending|saved|failed`) to `Asset` (Python, TS, D1 migration 0002, local schema).
   - These are written only by a dedicated `set_asset_dropbox` UPDATE.
   - They are excluded from the generic upsert's update set, so a later `_save` can't wipe them.
6. **After Higgsfield expiry:** `/api/assets` swaps `url` for a Dropbox temporary link (cached about 3.5 h) once an asset is older than 6.5 days and saved to Dropbox. No public share links.
7. **Agent tools** (no approval needed: this is not posting or payment):
   - `dropbox_status`
   - `list_dropbox_media` (saved assets with path and phone steps)
   - `browse_dropbox` (list_folder)
   - `save_to_dropbox` (one asset)
   - `dropbox_backfill`
   - Given to production-coordinator, publishing-coordinator and device-operator.
8. **Phone knowledge:**
   - device-operator prompt: getting media onto the phone becomes "Dropbox app → Search the file name → `•••` → Export → Save video → verify in Photos". Safari on the asset URL stays as a fallback.
   - The same how-to goes into `/memories/AGENTS.md` (Learned playbook), `/memories/agents/device-operator.md`, and the seed template.
9. **Mode:** `ProviderModes.storage` (`live`/`off`) comes from the live status, as with device. With Dropbox off, the tools return the not-connected message. No mock data.

## Out of scope
- Copying `outputs[1:]` of multi-output jobs. Only `outputs[0]` is recorded today; that is a separate fix.
- The `AssetThumb` other-thread lookup bug.
- Higgsfield webhooks.
