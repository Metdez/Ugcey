# Integrations research: Glasshand, Higgsfield, Ponytail

Researched 2026-11-07. Sources are primary (vendor docs, OpenAPI specs, and package source) unless a line is marked otherwise. Scratch copies of every fetched source are in `/tmp/claude-0/-home-user-Ugcey/fa2c91df-9a17-597b-a1bb-bf83d8f15881/scratchpad/integrations-research/`.

## TL;DR for the planner

| Topic | What it is (confirmed) | Decision |
| - | - | - |
| **Glasshand** | glasshand.com, run by **Codapt Inc** (the "Solid" team). It rents dedicated **physical** iPhone SE (3rd gen) devices at $60/mo and Mac mini M4 machines at $90/mo from its data center. Access is a REST API plus a WebSocket stream of JPEG frames. It has **no MCP server, no SDK, and no accessibility tree**. Launched on Product Hunt in Nov 2026; the API is v0.1.0. | Build a `GlasshandDeviceProvider` over plain `httpx` plus `websockets`. The live stream has to be **relayed by Ugecy's backend**, because browsers cannot send the bearer token and the Glasshand dashboard sends `frame-ancestors 'none'`. |
| **Higgsfield** | api.higgsfield.ai, an async model API with 84 workflows (Seedance, Kling, Wan, MiniMax, SOUL, Marketing/Ads Studio and others). Auth header is `Authorization: Key <key-id>:<key-secret>`. Official Python SDK `higgsfield-client` 0.2.0 (Apache-2.0). A hosted MCP server exists at `mcp.higgsfield.ai/mcp`, but it uses consumer OAuth and plan credits. | Write a thin `httpx` adapter that follows the SDK's semantics. The SDK cannot send `Idempotency-Key` and retries billable POSTs, so it is unsafe for production. Use webhooks (Standard Webhooks) with polling as the fallback. Copy outputs to R2 within 7 days. |
| **`HF_API_KEY_SECRET`** | Checked by shape only; the value was never printed or sent. It holds the **combined** form `<36-char uuid>:<64-hex>`, which is exactly the `key-id:key-secret` string the SDK expects in `HF_KEY`. | Map it to `HF_KEY`, or pass it as `api_key=`. Do **not** treat it as a bare secret, even though the docs' curl examples use `HF_API_KEY_ID` and `HF_API_KEY_SECRET` as two separate variables. |
| **Ponytail** | `DietrichGebert/ponytail` v5.3.3, MIT, about 186k stars. A "lazy senior dev" skill/plugin: a 6-step ladder that forces the smallest complete change. | Install it as a Claude Code plugin, or vendor `skills/ponytail/SKILL.md`. It is **not installed in this session**, so coding agents cannot "invoke" it until it is. A checklist is in section C. |

---

## A. Glasshand

### A1. Identity and sources
- Landing page: https://glasshand.com. Agent docs: https://glasshand.com/agents.md (the authoritative integration guide). Index: https://glasshand.com/llms.txt.
- OpenAPI 3.1: https://api.glasshand.com/openapi.json (title "Glasshand agent API", **v0.1.0**). Base URL: `https://api.glasshand.com/v1`. Human dashboard: https://app.glasshand.com.
- Product Hunt: https://www.producthunt.com/products/glasshand (makers Trevor Keith and Riley S; "team behind Solid"). Terms: https://glasshand.com/terms, "Operated by Codapt Inc." Devices may report MDM management by Codapt Inc.
- agents.md says: "No installation or MCP server is required". It is HTTPS only. There is no SDK, no GitHub org found, and no rate-limit numbers are published.
- Live catalog as of today (`GET /v1/catalog`, no auth): iPhone SE 3rd gen at **$60/mo**, Mac mini M4 (16 GB/256 GB) at **$90/mo**, `billingMode:"live"`, `launchOpen:true`. Rental is **monthly only**: no hourly or daily option, and no device pool.

### A2. Auth: OAuth 2.0 device flow with a human email OTP
1. `POST /auth/device/code {"clientName": "Ugecy – <workspace>"}` (≤80 chars, no auth). Returns `client_id, device_code, user_code, verification_uri(_complete), expires_in, interval`. Show `verification_uri_complete` and `user_code` to the operator. Keep `device_code` and `client_id` private.
2. Poll `POST /auth/device/token` (form-encoded) with `grant_type=urn:ietf:params:oauth:grant-type:device_code`, `client_id`, `device_code`. Wait at least `interval` between polls (≈5 s). On `slow_down`, add 5 s or more. Stop on `access_denied` or `expired_token`.
3. The response is `{access_token (JWT, **15 min**), refresh_token, token_type:"Bearer", expires_in, scope}`. Refresh with `grant_type=refresh_token`. **Refresh tokens rotate**: replace both atomically and serialize refreshes per account. If a refresh is rejected, the operator must re-approve.
4. Scopes shown at approval: `rentals:read`, `rentals:write`, `devices:control`, `billing:write`. Approval is **account-wide for the named agent**. Revoking the agent in the dashboard rejects the API immediately and closes streams shortly after.
5. Never collect the operator's OTP, cookies, or card details. Never put tokens in URLs or logs. Payment always happens in the human's Stripe browser flow.

### A3. Rentals (operator-managed; keep these out of agent tools)
- `GET /rentals` returns `{items:[Rental]}`, and `GET /rentals/{id}` returns one rental. `Rental = {id, kind: iphone|mac, name, status, createdAt, currentPeriodEnd, cancelAtPeriodEnd, graceUntil, monthlyPrice, deviceReady, billingManaged, failureMessage}`.
- Status values: `awaiting_payment | provisioning | active | grace | ending | refunding | failed | ended`. **Connect only when `deviceReady && status in {active, grace}`.** A grace period lasts up to 72 h after a failed renewal.
- `POST /rentals/checkout {"kind":"iphone"}` (needs `Idempotency-Key`) returns `checkoutUrl` and `rentalId`. Neither the checkout nor its success redirect proves payment; poll the status. `POST /rentals/{id}/cancel {"cancelAtPeriodEnd":true}`, `POST /rentals/{id}/resume {}`, `POST /billing/portal`, `GET/POST/DELETE /waitlist`.
- Durable idempotency: generate a key once, persist it with the exact body, and retry timeouts and 503s with the **same** key and body. A new key means a second rental. Reusing a key with a different body returns 409.

### A4. Device control API
- `GET /rentals/{id}/connection` returns `{rentalId, geometry:{width,height,viewport:{x,y,width,height}}, capture, control, screenshotUrl, controlUrl}`.
- `GET /rentals/{id}/screenshot` returns a fresh **full-HDMI JPEG**. Crop it to `geometry.viewport` before handing it to a vision model. It returns **503 if capture is stale**.
- `POST /rentals/{id}/input` takes one JSON input and **requires `Idempotency-Key`** (≤128 chars). It returns `{v:1,type:"result",requestId,ok,result?,error?{code,message}}`. Deduplication only lasts for the current controller process, so **never blindly replay**: take a screenshot first.
- Coordinates are **normalized 0..1 inside the viewport**. Input union, from the OpenAPI `Input` schema:

| type | fields |
| - | - |
| `click` | `x,y`, `button?` 1/2/4, `count?` 1/2 |
| `drag` | `fromX,fromY,toX,toY`, `durationMs?` 100..3000 (swipe) |
| `scroll` | `delta` −127..127, `x?,y?` |
| `text` | `text` ≤512 chars, **printable US ASCII plus `\n`/`\t` only**, with no Unicode or clipboard |
| `press` | `keys[]` (USB HID usage IDs, ≤6), `modifiers` bitmask; an atomic chord, auto-released |
| `key` / `pointer` | full keyboard state / pointer `buttons` 0..31 (explicit release needed) |
| `home` | iPhone Home (Mission Control on Mac) |
| `release_all` | releases all held inputs |

- Errors and control states: `control_taken` means a human took over in the dashboard, so pause. `control_busy` means another agent input session is active. HTTP errors use the envelope `{error:{code,message}}` with 400/401/403/404/409/**429 (back off; no numbers published, no rate-limit headers seen)**/503 (retry safely).
- **Not available**: accessibility tree or UI hierarchy, "launch app" (go Home, then swipe down to Spotlight, then type the name), notification API, shell, filesystem, clipboard API, and file push to the device. Hidden iOS permission modals can be missing from the HDMI image while they block input; the docs describe a VoiceOver Quick Nav workaround. AssistiveTouch is pre-enabled and its floating button can cover targets.

### A5. Live stream: the embed answer
- Open `controlUrl` (WSS) with an `Authorization: Bearer` **header**. The server sends `hello` (geometry plus connection id), then repeats `{v:1,type:"frame",frameId,...}` followed **immediately by a binary JPEG**. The client must send `{v:1,type:"frame_ack",frameId}`, and **at most 4 frames may be unacked**. Input can also go over the socket: `{v:1,type:"input",requestId,input:{...}}`. Never send `role` or `sessionId`. Disconnecting releases held input, and reconnecting does not replay.
- The transport is **WebSocket JPEG frames with ack-based flow control**. It is not WebRTC, HLS, or MJPEG-over-HTTP. FPS and resolution are not documented.
- **It cannot connect directly from the browser.** Browser WebSocket clients cannot set the Authorization header, and tokens must never go in URLs. The dashboard (`app.glasshand.com`) sends `X-Frame-Options: DENY` and `frame-ancestors 'none'`, verified by response headers today, so **it cannot be iframed**.
- So Ugecy needs a **StreamRelay**: one upstream connection per rental, held server-side with the token. It acks upstream as soon as a frame is received, keeps the latest frame, and fans it out to authorized viewers over Ugecy's own authenticated WebSocket as binary JPEG. The browser draws frames into `<img>`/`<canvas>` via `createImageBitmap` and drops stale frames for slow viewers.
  - A Cloudflare **Durable Object** per rental is the natural host, using outbound WebSocket with headers plus hibernation for viewers. A Python Worker DO, or a TS exception, is an open question.
- **Human takeover**: Glasshand allows takeover only through its own dashboard controls, and agents must not impersonate a human takeover. Ugecy should show "Take control in Glasshand", which opens app.glasshand.com in a new tab, and treat `control_taken` as a paused state. Ugecy must **not** forward operator clicks through the agent token.

### A6. Terms and compliance notes
- The terms forbid fraud, impersonation, credential theft, spam, harassment, unauthorized access, and reselling account access. Liability is capped at max(US$100, 12-month fees). Glasshand markets eSIM/SMS verification and "find leads" uses. **Ugecy must not use these for account creation or warming** (out of scope), and should block those flows by policy, an app allowlist, and audit.
- Driving TikTok/Instagram through UI automation can conflict with those platforms' automation terms. **Prefer official publishing APIs.** Use Glasshand as a human-supervised path where the final "Post" tap is a separately approved, receipted action.
- **Media transfer gap**: there is no file push, so the generated video has to reach the iPhone through the device UI. The workable pattern is a **Ugecy device handoff page**:
  - a short, single-use, expiring capability link to one approved post (not a credential);
  - the agent types the URL in Safari (ASCII is fine) and saves the video to Photos;
  - a **"Copy caption" button** works around the ASCII-only text endpoint for emoji and Unicode captions;
  - the agent then pastes the caption in the app.

### A7. Alternatives for a pluggable DeviceProvider
| Option | Model | Real iPhone with App Store apps | Live view | License / stars | Fit |
| - | - | - | - | - | - |
| **Glasshand** | hosted physical devices, REST + WS | yes (iPhone SE 3) | WS JPEG + ack | commercial, $60/mo | **primary** |
| mobile-next/mobile-mcp | local MCP server (WebDriverAgent under the hood) | yes, your own USB device plus a Mac with Xcode | README claims screen streaming (not verified) | Apache-2.0, 10.4k★ | self-hosted fallback; gives an element tree |
| appium/appium-xcuitest-driver + WebDriverAgent | W3C WebDriver | yes (own device, dev-signed WDA) | WDA MJPEG server (from Appium docs, not re-verified) | Apache-2.0, 906★ | self-hosted; richest automation and accessibility tree |
| meta/idb (was facebook/idb) | CLI/gRPC | mainly simulators | simulator video stream | MIT, 5.4k★ | test-only |
| Limrun (YC) | hosted iOS **simulators**, WebRTC | **no** (simulators can't run App Store social apps) | WebRTC | commercial | not for publishing |
| BrowserStack / AWS Device Farm | real-device test clouds | ephemeral, test-app oriented | web live view | commercial | poor fit (not re-verified this session) |

Stars come from GitHub pages via Firecrawl on 2026-11-07.

---

## B. Higgsfield

### B1. Surfaces
- **REST API** at `https://api.higgsfield.ai`. Docs at https://docs.higgsfield.ai, with a full dump at `/llms-full.txt` (≈600 KB, the source for everything below). Console for keys, limits, webhook secret, and playground: https://console.higgsfield.ai. Billing is a **USD account balance** that expires 1 year after top-up.
- **Python SDK** `higgsfield-client` 0.2.0 (PyPI, Apache-2.0, https://github.com/higgsfield-ai/higgsfield-client, 140★, deps `httpx>=0.21,<0.29`). The TS SDK is `@higgsfield/client/v2` and reads `HF_CREDENTIALS`.
- **Agent API**, `/v1/agent/sessions|media`, ships in SDK 0.2.0. It is account-gated (403 if not enabled) and adds LLM cost. Its underlying LLM is undisclosed, which conflicts with the "no Anthropic models" rule, so **do not use it**. Ugecy's deepagents already orchestrates.
- **Hosted MCP** at `https://mcp.higgsfield.ai/mcp` (https://higgsfield.ai/cli, help-center connector page). Auth is a **Higgsfield account OAuth login, not an API key**, and it bills **consumer plan credits**. Its catalog differs: it includes Veo, Nano Banana Pro, GPT Image and Seedream, and it has skills such as "UGC" and "Ad Multiplier". The CLI is `npm i -g @higgsfield/cli`. Use it for dev exploration only; it is not a multi-tenant server integration.

### B2. Auth and the credential mapping (verified in SDK source `higgsfield_client/auth.py`)
```python
key = os.getenv('HF_KEY')                                   # "key-id:key-secret"
if not key and os.getenv('HF_API_KEY') and os.getenv('HF_API_SECRET'):
    key = f"{HF_API_KEY}:{HF_API_SECRET}"                    # else CredentialsMissedError
# SyncClient/AsyncClient(api_key=...) overrides; header = f"Authorization: Key {key}"
```
- The SDK does **not** read `HF_API_KEY_SECRET` or `HF_API_KEY_ID`. In this environment, `HF_API_KEY_SECRET` holds a combined `uuid:hex64` value, with exactly one colon and no whitespace.
- **Mapping**: `HF_KEY = HF_API_KEY_SECRET` in deploy config (a Cloudflare secret named `HF_KEY`), or `AsyncClient(api_key=settings.higgsfield_key)`.
- Ugecy's resolver order: `HF_KEY` → `HF_API_KEY_SECRET` if it contains `:` → `HF_API_KEY`+`HF_API_SECRET` → `HF_API_KEY_ID`+`HF_API_KEY_SECRET` → otherwise **mock mode**. Hold the value in a `SecretStr`. Never log it, and never let it reach a browser, since the docs forbid client-side use.
- The legacy headers `hf-api-key`/`hf-secret` are still accepted; don't use them. A 401 response is `{"detail":"Invalid credentials"}`. A model the account can't use returns 404, 423, or 503.

### B3. Request lifecycle
- Submit: `POST /{endpoint_id}` with JSON args, optional `?hf_webhook=<urlencoded https>`, header `Idempotency-Key` (1–255 visible ASCII, UUID recommended), and optional `Hf-Expires-After: <3600..account max>` seconds.
- Response: `{status:"queued", request_id, status_url, cancel_url, expires_after:604800}`. **Use the returned URLs**; don't construct them.
- Status: `GET /requests/{id}/status`, one of `queued → in_progress → completed | failed | nsfw | canceled`. Output shapes on `completed`:
  - `images:[{url}]` for images;
  - `video:{url}` for video;
  - `audio:{url}` plus `audios[]` for audio;
  - some video and 3D workflows add `zip|mov|jsx|fbx|ply`;
  - plus `expires_at`.
- Cancel: `POST /requests/{id}/cancel` works only while queued. It returns 202 with an empty body, or 400 if already started, and the cancelled job is refunded.
- Delete: `DELETE /requests/{id}` returns `{request_id,status:"deleted"}`, or 409 while running.
- Estimate: `POST /estimate/{endpoint_id}` with the same args returns `{"usd":"0.094"}`. Uploads: `POST /files/generate-upload-url {content_type}` returns `{public_url, upload_url, upload_headers}`. PUT the file with **all** `upload_headers` and no credentials. The upload URL is valid for 1 h. Accepted types are jpeg/png/webp/gif, wav, and mp4.
- Polling (docs): start at 2 s, multiply by 1.5 up to 10 s, add jitter, and use a per-model timeout.
- Webhooks: deliveries happen on completed, failed, or nsfw, using the envelope `{request_id,status,error,expires_at,payload:{images|video|audio}}`.
  - Signing follows **Standard Webhooks**, with headers `webhook-id`, `webhook-timestamp`, and `webhook-signature: v1,<b64>`. The secret starts with `whsec_` and is revealed in Console Settings; it is account-wide, and **deliveries are unsigned until it is first revealed**.
  - Verify with `pip install standardwebhooks` against the raw body, with ±5 min tolerance. Reply 2xx within 10 s after a durable write, and dedupe on `webhook-id`.
  - 5xx responses are retried for 2 h; 4xx responses are not retried. The URL must be public HTTPS with no credentials in it.
- **Retention is 7 days**, after which the URLs die. Copy outputs to R2 on completion, then optionally `DELETE` the request.

### B4. Errors, rate limits, pricing
- Errors: 400 bad params; 401 credentials; **403 insufficient balance**; 404; 409 still running; 422 validation, idempotency mismatch, or bad `Hf-Expires-After`; 423 model blocked; **429 `account_queue_full`** (`{detail:{code,message,retryable,limit,retry_after_seconds}}` plus a `Retry-After` header); 500; 503 model not ready or `admission_control_unavailable`. Every response carries `X-Correlation-ID`; log it with the `request_id`.
- Limits come from **per-account concurrency**, shown in Console. Requests over the concurrency limit queue automatically. The queue limit is a multiple of concurrency, and each batch output counts separately. Successful responses carry no remaining-capacity headers, so throttle with a semaphore or Queue consumer concurrency. Soul ID training has its own 429.
- Pricing: per generation, charged only on `completed`. Failed, nsfw, and cancelled jobs are refunded. The docs publish few prices, so **always call `/estimate` before approval**. Known examples:
  - SOUL V2 ≈ $0.094 per generation (illustrative);
  - Ads Studio ≈ $0.084 per image (token-metered);
  - Genjutsu restyle $0.318, $0.681, or $1.632 per source-second at 480p, 720p, or 1080p.
  - `GET /models/usage` gives analytics (not billing records).

### B5. SDK 0.2.0 gaps (verified in `http/client.py`, `http/transport.py`, `http/retry.py`)
1. **No `Idempotency-Key`, `Hf-Expires-After`, or custom headers** on `submit()`. Worse, `HttpTransport` **retries POST submissions** on 408/429/5xx up to 3 times with 0.2–0.8 s backoff. Those retries can **duplicate billable generations**, and they ignore `Retry-After`.
2. `poll_request_status` defaults to **0.5 s** polling (the docs ask for 2→10 s). `subscribe()` takes no webhook. There is no `estimate`, `delete`, or usage call.
3. Errors become `HiggsfieldClientError(message)`, and the status code is only reachable through `__cause__`. `RequestController.build_urls` hard-codes the module `BASE_URL`, ignoring a custom `base_url` when looking up by id.
4. The parts that are good: upload flow, status enum, and DONE set. **Recommendation**: one `httpx.AsyncClient` adapter of about 200 lines with the `Authorization: Key …` header. It sends idempotency keys, honors `Retry-After`, and never auto-retries POSTs without a key. Keep the SDK as the reference only, rather than a runtime dependency, to avoid a second HTTP stack.

### B6. Model catalog relevant to UGC
The docs list 84 workflows (17 image, 67 video); each endpoint id is used as the POST path. Store the catalog as data (`catalog.yaml`) that the UI and tools read.

| Use | endpoint_id | key args (default) |
| - | - | - |
| Creator or product still, 9:16 | `higgsfield-ai/soul/v2/standard` | `prompt`*, `aspect_ratio`(1:1; 9:16…), `resolution` 720p\|1080p, `batch_size` 1\|4, `seed`, `style_id`, `custom_reference_id`+`_strength`, `enhance_prompt` |
| Consistent character | `POST /v1/custom-references` (Soul ID) | `name`, `model_version` v1\|v2\|cinema, `input_images[1..100]{type:"image_url",image_url}`. Poll `GET /v1/custom-references/{id}` |
| Product ad stills | `marketing-studio/image` (also `/flare`, `/sunburst`, `/presets`) | `prompt`*, `image_urls[≤16]`, `preset_id`, `aspect_ratio` auto\|9:16…, `resolution` 1k\|2k\|4k, `quality` |
| Ad from product images | `higgsfield/ads-studio/v1.0` | `prompt`*, `image_urls[≤10]`, `niche`, `target_audience`, `language`, `aspect_ratio` (incl. 9:16, 4:5), `batch_size` 1..8 |
| Image→video with audio, ≤30 s | `bytedance/seedance-2.5/image-to-video` | `image_url`*, `prompt`, `duration` 4..30 (5), `resolution` 480/720/1080p, `end_image_url`, `generate_audio`(true), `bitrate_mode` |
| Multi-reference UGC video | `bytedance/seedance-2.5/reference-to-video` | `image_urls[≤30]`, `video_urls[≤10]`, `audio_urls[≤10]`, `prompt`, `duration`, `aspect_ratio` 9:16…, `generate_audio` |
| Text→video / edit / extend | `bytedance/seedance-2.5/{text-to-video,video-edit,video-extend}` | t2v: `prompt`*, `aspect_ratio`, `duration` 4..30, `output_format` mp4\|mov |
| Kling i2v, multi-shot | `kling-video/v3.0/{std,pro,4k}/image-to-video`, `v3.0-turbo/*` | `image_url`*, `prompt`, `duration` 3..15, `sound` on\|off, `multi_shots`, `multi_prompt[≤6]{prompt,duration}`, `last_image_url`, `cfg_scale` |
| Motion transfer to a character | `kling-video/v3/motion-control/{std,pro}`, `higgsfield/genjutsu/motion-transfer/v1.0` | Kling: `image_url`*, `video_url`*, `character_orientation`, `keep_original_sound`. Genjutsu: `video_url`*, `image_urls[1..8]`*, `resolution` |
| Alternatives | `alibaba/wan-3.0{,-prime}/*`, `minimax/h3/*`, `alibaba/happy-horse/v1.1/*`, `lightricks/ltx-2.5/*`, `pixverse/v6/*`, `xai/grok-imagine-*`, `recraft/v4.1/*`, `alibaba/qwen-image-3/*`, `ideogram/v4.0`, `z-image/turbo` | Wan 3.0 i2v: `image_url`*, `prompt`*, `duration` 2..30, `resolution`, `aspect_ratio`, `generate_audio`, `seed`. MiniMax H3 i2v: `prompt`*, `image_url`*, `duration` 5..15, `aigc_watermark` |

**Not in the API catalog** (web app or MCP only): Veo, Nano Banana, Lipsync Studio (talking avatar/lip-sync), "Click to Ad" UGC, upscale, DoP/"product-in-hand" apps. For a talking-head UGC clip, use Seedance 2.5 reference-to-video with `generate_audio`, or Kling with `sound:on`, and validate quality in a spike. Otherwise this is a gap for another provider.

---

## C. Ponytail

- **What it is**: https://github.com/DietrichGebert/ponytail, "lazy senior dev mode". MIT, v5.3.3, ≈186k★, last commit 2026-10-29. Independent benchmarks:
  - JetBrains AI blog (Jul 2026, https://blog.jetbrains.com/ai/2026/07/ponytail-skill-claude-tested/) measured −31% code and −10.3% cost (p=0.004) with no significant quality loss, but only when the hook injects the ruleset.
  - dev.to (https://dev.to/arshtechpro/ponytail-the-ai-coding-skill-that-makes-your-agent-write-less-code-29l3) reproduces the README benchmark: −54% LOC, with the safety-tier tasks holding.
- **Contents**: skills `ponytail` (levels lite/full/ultra; full is the default), `ponytail-review`, `ponytail-audit`, `ponytail-debt` (ledger of `shortcut:` comments), `ponytail-gain`, `ponytail-help`. Hooks on SessionStart, SubagentStart, and UserPromptSubmit inject the ruleset, and they need `node` on PATH.
- **Install, Claude Code**: send `/plugin marketplace add DietrichGebert/ponytail`, then send `/plugin install ponytail@ponytail` as a **separate prompt**. Codex: `codex plugin marketplace add DietrichGebert/ponytail && codex plugin add ponytail@ponytail`. Without plugins, copy `skills/ponytail/SKILL.md` to `.claude/skills/ponytail/SKILL.md`, or paste the repo's `AGENTS.md` rules. **It is not in this session's skill list today**, so the planner should add a setup task.

**Checklist for Ugecy coding agents** (condensed from `skills/ponytail/SKILL.md`):
1. **Scope first**: read the task and the code it touches. List every caller, test, fixture, config, and export the change must reach, and what it could break: data loss or exposure, broken callers.
2. **Ladder** (take the first option that fully works):
   1. does it need to exist? (skip unrequested features and name them in one line);
   2. already in the codebase? (reuse it the house way);
   3. stdlib or platform feature?;
   4. an installed dependency? (never add one for a few lines);
   5. one readable line?;
   6. otherwise the minimum code that works.
3. Do not write unrequested abstractions, wrappers, options, config, boilerplate, or "for later" code. Keep values in their native form. Deletion beats addition. Keep the existing layers and conventions.
4. Be lazy about the solution, never about completeness: fix every caller, test, and fixture the change breaks. For a bug fix, grep every caller and fix the root cause once in the shared code.
5. Moved or merged code keeps its validation and error handling. Between options of equal size, choose the one that is correct on edge cases.
6. Non-trivial logic (a branch, loop, parser, money, security, or a new script) ships with one small test or assert-based self-check.
7. A known-limit shortcut gets a comment: `# shortcut: <limit>, <when to upgrade>`.
8. **Never cut**: validation at trust boundaries, data-loss error handling, security, accessibility, hardware calibration, or anything the user asked for.
9. End each reply with one or two lines on what was skipped or unchecked, plus any risk.
10. Run `/ponytail-review` on each change. It ranks findings as correct > safe > load > tested > fast > lean.

**Tension with Ugecy rules**: Ponytail flags "abstraction with one implementation" as YAGNI. The Device and Media Protocols below are justified because each has **two real implementations** (live and mock), and the project rules mandate swappable modules. Keep them minimal: a plain dict factory, not a plugin framework.

---

## D. Recommendation for Ugecy

### D1. Layout (Python backend; every file ≤500 lines)
```
backend/ugecy/integrations/
  modes.py                 # resolve live|mock per provider + workspace; exposes is_mock for UI banner/audit
  device/base.py           # DeviceProvider Protocol + pydantic models (DeviceAction union = Glasshand Input)
  device/glasshand_auth.py # device-code flow, token store, serialized rotating refresh
  device/glasshand.py      # REST: list/get rental, connection, screenshot(crop), send_input
  device/glasshand_stream.py # upstream WS client (hello/frame/ack/input) used by StreamRelay
  device/mock.py           # scripted screens + hotspots fixture → deterministic flows
  device/tools.py          # deepagents tools + session/approval guards
  media/base.py            # MediaProvider Protocol + MediaJob/MediaOutput models
  media/higgsfield.py      # httpx adapter (submit/status/cancel/delete/estimate/upload)
  media/higgsfield_webhook.py # Standard Webhooks verify + envelope → MediaJob
  media/catalog.yaml       # endpoint_id → kind, arg schema subset, defaults, UI label
  media/mock.py            # timed fake jobs + fixture assets + fault injection
  media/tools.py
tests/contract/test_device_contract.py, test_media_contract.py  # parametrized over [mock, live(opt-in marker)]
```

### D2. Interfaces
```python
# device/base.py
class DeviceKind(StrEnum): IPHONE="iphone"; MAC="mac"
class DeviceInfo(BaseModel): id: str; kind: DeviceKind; name: str; status: str; ready: bool; provider: str
class Geometry(BaseModel): width: int; height: int; viewport: Rect      # Rect(x,y,width,height)
class Screenshot(BaseModel): jpeg: bytes; geometry: Geometry; captured_at: datetime; cropped: bool = True
DeviceAction = Annotated[Click | Drag | Scroll | Text | Press | Key | Pointer | Home | ReleaseAll,
                         Field(discriminator="type")]   # coords normalized 0..1 in viewport; Text: ASCII ≤512
class ActionReceipt(BaseModel): request_id: str; ok: bool; error_code: str | None; at: datetime
    # error_code includes "control_taken" | "control_busy"
class Frame(BaseModel): frame_id: str; jpeg: bytes; geometry: Geometry | None

class DeviceProvider(Protocol):
    name: str
    async def list_devices(self, ws: WorkspaceRef) -> list[DeviceInfo]: ...
    async def get_device(self, ws: WorkspaceRef, device_id: str) -> DeviceInfo: ...
    async def geometry(self, ws: WorkspaceRef, device_id: str) -> Geometry: ...
    async def screenshot(self, ws: WorkspaceRef, device_id: str) -> Screenshot: ...
    async def send(self, ws: WorkspaceRef, device_id: str, action: DeviceAction,
                   idempotency_key: str) -> ActionReceipt: ...
    def stream(self, ws: WorkspaceRef, device_id: str) -> AsyncContextManager[AsyncIterator[Frame]]: ...

class DeviceConnector(Protocol):        # operator Settings UI only, never an agent tool
    async def start(self, ws: WorkspaceRef, client_name: str) -> PendingAuth: ...  # user_code, verification_uri_complete, interval, expires_at
    async def poll(self, ws: WorkspaceRef, pending_id: str) -> Literal["pending","approved","denied","expired"]: ...
    async def disconnect(self, ws: WorkspaceRef) -> None: ...
```
```python
# media/base.py
class JobStatus(StrEnum): QUEUED="queued"; IN_PROGRESS="in_progress"; COMPLETED="completed"; FAILED="failed"; NSFW="nsfw"; CANCELED="canceled"
class MediaOutput(BaseModel): url: str; kind: Literal["image","video","audio","file"]; content_type: str | None
class MediaJob(BaseModel):
    request_id: str; provider: str; model: str; status: JobStatus
    outputs: list[MediaOutput] = []; error: str | None = None
    expires_at: datetime | None = None; estimated_usd: Decimal | None = None; correlation_id: str | None = None
class ModelSpec(BaseModel): endpoint_id: str; kind: Literal["image","video","audio","character"]; label: str; schema: dict; defaults: dict

class MediaProvider(Protocol):
    name: str
    def models(self) -> list[ModelSpec]: ...
    async def estimate(self, endpoint_id: str, args: dict) -> Decimal | None: ...
    async def upload(self, data: bytes, content_type: str) -> str: ...          # returns provider public_url
    async def submit(self, endpoint_id: str, args: dict, *, idempotency_key: str,
                     webhook_url: str | None = None, retention_s: int | None = None) -> MediaJob: ...
    async def get(self, request_id: str) -> MediaJob: ...
    async def cancel(self, request_id: str) -> bool: ...
    async def delete(self, request_id: str) -> None: ...
    def parse_webhook(self, headers: Mapping[str, str], raw_body: bytes) -> MediaJob: ...  # verifies signature; raises on bad sig
```

### D3. deepagents tools
The tools are wired with `create_deep_agent(..., interrupt_on={...}, checkpointer=...)`. In deepagents 0.7.34, `interrupt_on: dict[str, bool | InterruptOnConfig]` maps to LangChain's `HumanInTheLoopMiddleware`, and subagent specs also accept `interrupt_on`. Every tool call writes an audit row: actor, tool, args hash, receipt, provider, `mode` (live or mock), correlation ids. In the table, approval **G** means a backend guard enforced in code, not only in the prompt.

| Tool (owner subagent) | Args | Returns | Approval |
| - | - | - | - |
| `device_list` (Device operator) | – | `[{device_id, kind, status, ready}]` | no |
| `device_screenshot` | `device_id` | image content block (cropped JPEG) + `{asset_id, geometry, captured_at}` | no (store a ref; screens may contain PII) |
| `device_session_start` | `device_id, goal, allowed_apps[], max_steps` | `{session_id, expires_at}` | **yes, interrupt**: the operator approves the plan |
| `device_tap` / `device_swipe` / `device_scroll` / `device_type_text` / `device_press_keys` / `device_home` | `session_id`, action fields (normalized coords) | `ActionReceipt` + fresh screenshot ref | **G**: requires an active approved session and step budget; refuses after `control_taken`; ASCII and length validated |
| `device_commit` | `session_id, x, y, intent:"post"\|"send"\|"purchase"\|"delete", evidence_asset_id` | `ActionReceipt` | **always interrupt**: the final irreversible tap |
| `device_handoff` | `session_id, reason` | `{handoff_url:"https://app.glasshand.com"}`; the agent pauses | no |
| `media_list_models` (Production) | `kind?` | `[ModelSpec(lite)]` | no |
| `media_estimate` | `endpoint_id, args` | `{usd}` | no |
| `media_upload_reference` | `asset_id` (Ugecy R2 asset) | `{url}` | no (operator-owned assets only; **G**) |
| `media_generate` | `endpoint_id, args, campaign_id, brief_id` | `{job_id, request_id, status, estimated_usd}` | **interrupt** above the per-job or campaign budget (default: always). The idempotency key is server-generated and persisted *before* submit |
| `media_job_status` | `job_id` | `MediaJob` (+ R2 asset ids once copied) | no |
| `media_cancel` | `job_id` | `{canceled: bool}` | no |
| `media_create_character` | `name, image_asset_ids[]` | `{reference_id, status}` | **interrupt** + likeness-consent attestation stored |

Rentals, checkout, cancel, and billing are **not** agent tools; they live in the Settings UI behind the operator's Stripe flow. The resume payload after an interrupt follows LangChain HITL (`Command(resume={"decisions":[{"type":"approve"|"edit"|"reject",...}]})`); confirm the exact shape in the deepagents researcher's notes.

### D4. Runtime flows
- **Media**: approve → `submit(..., idempotency_key, webhook_url=https://<edge>/webhooks/higgsfield)` → the Worker verifies the signature, records `webhook-id`, enqueues to a Queue, and returns 2xx in under 10 s → the consumer copies outputs to R2 (storing sha256, model, args, request_id, correlation_id) → asset ready → optional `DELETE`.
  - Fallback poller: Queue delayed messages at 2 s ×1.5 up to 10 s with jitter, used when the webhook secret was never revealed (deliveries unsigned) or a delivery is missed.
  - A per-account semaphore keeps the queue under `account_queue_full`. On 429, honor `Retry-After` and retry with the same key.
- **Device**: the operator connects Glasshand in Settings (device flow; tokens encrypted at rest, with one refresh lock per workspace) and picks a rental.
  - The StreamRelay starts when the device pane opens or a session is active.
  - The agent loop runs screenshot → VLM grounding (non-Anthropic; candidates for the models researcher: Qwen-VL family, ByteDance UI-TARS, Zhipu GLM-V/AutoGLM) → action → receipt → screenshot.
  - On an ambiguous input failure, take a screenshot and **never replay**.

### D5. Mock mode (the app works end-to-end with no credentials)
- `UGECY_DEVICE_PROVIDER` / `UGECY_MEDIA_PROVIDER` = `auto|live|mock` (default `auto`). Media resolves to live when a Higgsfield credential resolves (B2). Device resolves to live when the workspace has a connected Glasshand token and a `ready` device. Otherwise both fall back to mock. `live` with missing creds is a startup error, not a silent fallback.
- **MockMediaProvider**:
  - It serves the same `catalog.yaml` and validates args against the same schema subset.
  - Jobs move queued → in_progress → completed over configurable latency (default 2 s / 6 s), and outputs are fixture assets (one 9:16 jpg, one 9:16 mp4 with audio, CC0 or self-made, provenance recorded).
  - `estimate` returns a table value.
  - Fault injection: a prompt containing `[mock:fail]`, `[mock:nsfw]`, or `[mock:429]` produces that outcome.
  - It emits **signed** mock webhooks to the same endpoint, using a dev `whsec_`, so the webhook path is exercised.
- **MockDeviceProvider**:
  - A JSON fixture of screens defines each screen (png, hotspots → next screen, optional text field), for example: Home → Safari handoff page → Photos → Upload screen → Posted.
  - `screenshot` renders the current screen with Pillow, overlaying the last action and a clock.
  - `stream` yields about 2 fps; `send` returns receipts and can simulate `control_taken`.
- UI and audit: a persistent "Mock provider" badge appears in the device pane and asset cards, and audit rows carry `mode:"mock"`, so a mock "publish" can never be mistaken for a real one.
- The contract tests in `tests/contract/` run the same assertions against mock always, and against live behind `-m live` with explicit env vars, live test budgets, and an `Hf-Expires-After: 3600` header.

---

## E. Open questions / risks
1. **Glasshand maturity**: the product launched in early Nov 2026, the API is v0.1.0, there is no SDK or SLA, rate limits are unpublished, and the only device is the iPhone SE (3rd gen, small 4.7" screen). Pin `openapi.json` in tests and watch for breaking changes. Ask Glasshand for an embeddable viewer or human-role stream token, FPS and resolution, and rate limits.
2. **Platform terms**: UI automation of TikTok/Instagram via Glasshand may breach those platforms' automation terms even on the operator's own accounts. Make official APIs the default path, and keep the device path human-approved per post. Legal review is needed.
3. **Media to device**: there is no file push and no Unicode text input. The handoff-page plus copy-caption pattern (A6) is unproven; spike it first on a real rental.
4. **Stream relay hosting**: is the per-rental Durable Object written as a Python Worker or as a documented TS exception? Each workspace also needs a single control session (`control_busy`).
5. **Higgsfield credential**: it is not validated, because the instruction was not to send it anywhere. The first live smoke test should be `POST /estimate/higgsfield-ai/soul/v2/standard` (free); expect 401, 403 (balance), or 200. Confirm that the key's account has API balance; consumer plan credits don't apply to the API.
6. **Webhook signing**: an admin must reveal `whsec_` in Console once, or deliveries stay unsigned. Store it as `HF_WEBHOOK_SECRET`.
7. **Gaps in the Higgsfield catalog**: there is no lip-sync, talking-avatar, upscale, or Veo in the API. Talking-head UGC quality from Seedance or Kling audio is unverified, and a second media provider may be needed (MediaProvider makes it pluggable).
8. **Soul ID / likeness**: training on real faces needs documented consent; make it an approval with an attestation record.
9. **Ponytail is not installed**: the planner should add a phase-0 task to install the plugin or vendor `SKILL.md`. Mind the YAGNI vs. modularity tension (C).
10. **Cost control**: Higgsfield publishes few prices. Use `/estimate` before every approval, set per-campaign budgets, and keep in mind the balance expires after 1 year. Glasshand is a fixed $60 per device per month, with cancellation at period end.
