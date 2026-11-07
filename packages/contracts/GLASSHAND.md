# Glasshand (real iPhone) contract: phase 04

Glasshand (https://glasshand.com, API `https://api.glasshand.com/v1`, OpenAPI at `.planning/phases/04-glasshand/glasshand-openapi.json`) rents physical iPhones.

**Authentication** uses the OAuth device flow:
- The operator approves the request by entering an email code on Glasshand's site.
- Access tokens last **15 minutes**. Refresh tokens **rotate**, so replace both atomically and serialize refreshes.
- If a refresh is rejected, the operator has to approve again.

**Tokens** live only in the `AgentRuntime` Durable Object's SQLite. They never reach the browser or the Python container, and must never be logged.

## 1. Browser ↔ Worker

These routes are handled inside the Worker and are **not** proxied to the container. Responses use `GlasshandStatus` from `packages/contracts/src/models.ts`.

| Route | Behaviour |
|---|---|
| `POST /api/glasshand/connect` | Calls `POST /auth/device/code {"clientName":"Ugecy"}` and stores `client_id`, `device_code`, `interval`, `expires_at` and `last_poll_at=0`. Returns `{state:"pending", user_code, verification_uri, verification_uri_complete, expires_at, interval}`. Calling it while already connected returns the connected status unchanged. |
| `GET /api/glasshand/status` | **Pending:** if `now - last_poll_at >= interval`, polls the token endpoint exactly once (form body `grant_type=urn:ietf:params:oauth:grant-type:device_code&client_id&device_code`).<br>• `authorization_pending`: stays pending.<br>• `slow_down`: `interval += 5`.<br>• `access_denied`: returns `denied` and clears the pending fields.<br>• `expired_token`, or past `expires_at`: returns `expired`.<br>• `200`: stores the tokens; state becomes `connected`.<br>**Connected:** includes `rentals` from `GET /rentals` (`items[]`, mapped to `GlasshandRental`) and `selected_rental_id`. When nothing is selected yet, it auto-selects the first rental with `deviceReady && status in {active, grace}`.<br>**Neither:** returns `disconnected`. |
| `POST /api/glasshand/select` `{rental_id}` | Persists the selected rental (it must belong to the account). Returns the status. |
| `POST /api/glasshand/disconnect` | Deletes all stored tokens and pending state. Returns `{state:"disconnected"}`. |
| `GET /api/glasshand/stream` (WebSocket upgrade) | A read-only live view of the selected rental. Details in the next section. |

**Relay protocol for `GET /api/glasshand/stream`.** (Source: https://glasshand.com/agents.md, "For a live stream".) The Worker fetches the `controlUrl` from `GET /rentals/{id}/connection` and opens it as an outbound WebSocket with `Authorization: Bearer <token>`. The token is never put in the URL. The upstream socket's `binaryType` must be set to `"arraybuffer"`: workerd defaults it to `"blob"`, and `send(Blob)` goes out as the text `"[object Blob]"`, so the browser never receives a frame.
- **Upstream messages:**
  - `hello` (JSON with geometry): forward to the client as `{type:"hello", geometry}`.
  - `{v:1,type:"frame",frameId,...}`, followed immediately by a binary JPEG: forward the **binary JPEG** to the client, then reply upstream with `{v:1,type:"frame_ack",frameId}` (at most 4 unacked frames are allowed). A header whose JPEG never arrives is acked when the next header comes.
  - `capture_status` (`available` or `capture.available` false means no frames): forward as `{type:"capture_status", available}`.
  - Any `error` JSON (`message` or `error.message`): forward it as `{type:"error", message}`.
- **Client messages:** ignored, because viewers are read-only. A human takes over only through `https://app.glasshand.com`.
- **Closing:** if either side closes, close the other. Not connected, or no rental selected, means close with code 4401 or 4404 and a reason.
- **Frames:** each binary frame is the **full HDMI image**. The client crops it to `geometry.viewport` (pixel rect `{x,y,width,height}` within `{width,height}`) when drawing.

## 2. Container ↔ Worker (the `glasshand.internal` egress intercept)

| Request from Python | Gateway behaviour |
|---|---|
| `GET http://glasshand.internal/_ugecy/status` | Answered locally with `{connected: boolean, selected_rental_id: string \| null}`. No upstream call. |
| `GET /v1/rentals`, `GET /v1/rentals/{id}`, `GET /v1/rentals/{id}/connection`, `GET /v1/rentals/{id}/screenshot`, `GET /v1/me`, `POST /v1/rentals/{id}/input` | Passed through to `https://api.glasshand.com/v1/...`. The gateway injects `Authorization: Bearer <fresh token>`, refreshing when fewer than 60 s remain, and forwards `Idempotency-Key` and `content-type`. On an upstream 401 it refreshes once and retries once. If the refresh is rejected, it clears the tokens and returns `503 {"error":{"code":"not_configured"}}`. |
| Anything else (checkout, cancel, resume, billing, waitlist, auth) | `403`. The agent can never spend money or manage the account. |

Token refresh posts the form body `grant_type=refresh_token&client_id&refresh_token` to `/auth/device/token`, then **atomically** stores the new `access_token` and `refresh_token`, with `access_expires_at = now + expires_in`.

## 3. Python device layer

- **Default provider.** `AutoDeviceProvider` is the default for `UGECY_DEVICE_PROVIDER=auto`. It checks `glasshand.internal/_ugecy/status` and caches the result for 15 s. When connected, it delegates to `GlasshandProvider` for the selected rental; otherwise it uses `MockDeviceProvider`. Its `mode`/`name` reflect the current delegate. In local mode it uses Glasshand only when env `GLASSHAND_TOKEN` and `GLASSHAND_RENTAL_ID` are set (dev only).
- **Screenshots.** `GlasshandProvider.screenshot` crops the JPEG to `geometry.viewport`, using `/connection` cached per rental.
- **Vision grounding.** `GlasshandProvider.describe` sends the cropped screenshot, downscaled to at most 900 px tall, to `settings.model_vision` (Qwen3.8 on Workers AI, OpenAI `image_url` data URI). It returns compact JSON text of the form `{"app": "...", "screen": "...", "elements": [{"label": "...", "kind": "button|field|tab|icon|text", "x": 0.5, "y": 0.9}]}`, where `x` and `y` are the element centre normalized 0..1 within the viewport. That is the same coordinate space `/input` uses.
- **Inputs** map to the OpenAPI `Input` schema:
  - tap: `{type:"click", x, y}`
  - swipe: `{type:"drag", fromX, fromY, toX, toY, durationMs}`
  - type: `{type:"text", text}` (ASCII only, ≤ 512 characters)
  - home: `{type:"home"}`
- **Idempotency.** Each input sends a fresh `Idempotency-Key`. On an ambiguous failure, take a screenshot and never replay. `control_taken` and `control_busy` come back to the agent as receipt errors.
