# 04-02 Glasshand Python provider + vision

## Files
- New: `integrations/device/auto.py`, `integrations/device/vision.py`, `tests/_fakes_04_02.py`, `tests/test_glasshand_provider.py`, `tests/test_glasshand_auto.py`
- Reworked: `integrations/device/glasshand.py`, `tools/device.py`, `agents/prompts/device-operator.md`
- Edited: `deps.py` (device "auto" entry; auto always loads `AutoDeviceProvider`), `settings.py` (`glasshand_token`/`glasshand_rental_id`, aliases `GLASSHAND_TOKEN`/`GLASSHAND_RENTAL_ID`, dev only), `api/misc.py` (screenshot endpoint maps HTTP errors to 503)

## Interfaces
- `AutoDeviceProvider(settings, transport=None, clock=..., vision_model=None)`: dynamic `name`/`mode`, 15 s status cache, falls back to mock (never raises). Routes by device id (mock id always goes to mock).
- `GlasshandProvider`: base `/v1` (edge `http://glasshand.internal/v1`, local `https://api.glasshand.com/v1`); receipts `{request_id, ok, error, error_code}`; invalid coordinates/text return an error receipt without sending.
- `vision.py`: `crop_viewport`, `to_jpeg`, `extract_json`, `normalize`, `describe_jpeg` (<=900 px tall, JPEG q80, data-URI `image_url`).
- Tools: `device_screenshot` returns describe JSON plus a how-to-act hint; status/audit use the provider's real name and mode; `control_taken` flips control to human.

## Tests
`uv run pytest -q`: 104 passed, 1 skipped. `ruff check ugecy` clean.

## Deviations
- Edited the existing `tests/test_tools_production_glasshand.py` (path `/v1/rentals`, `ready` filter) because the base URL now includes `/v1` and `list_devices` returns not-ready rentals with `ready=False`.
- In the `device_screenshot` tool, a describe failure returns an `error:` string.

## Change requests
None. `ProviderModes.device` stays "mock" or "live" per `resolve_modes`; the real mode comes from `device.mode`.

## Risks
- Qwen coordinate accuracy is unverified live.
- Status is only re-checked every 15 s, so a disconnect can take up to 15 s to show.
- Swipes use a fixed 400 ms duration.
