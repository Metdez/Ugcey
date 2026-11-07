# 04-03 Glasshand connect flow + live iPhone view (web)

## Files
- apps/web/src/lib/glasshand.ts (client: connect/status/select/disconnect, `streamUrl()`, pure `cropRect`, `viewState`, `formatCountdown`, `rentalReady`) + glasshand.test.ts
- apps/web/src/components/device/{use-glasshand.ts, glasshand-connect.tsx (disconnected/pending/failed), glasshand-live.tsx (WS canvas + snapshot fallback), glasshand-panel.tsx (select, live, take control, disconnect)}
- Edited: inspector/tabs/device-tab.tsx, shell/accounts-status.tsx (Glasshand iPhone row + dot)

## Behaviour
- Status polled at `interval` s (pending) / 10 s (connected), only while tab visible.
- WS `binaryType=blob`, hello geometry, createImageBitmap -> cropped drawImage, frames dropped while busy/paused, bitmaps closed.
- WS error/close: 2 s snapshot polling + "Live stream unavailable — showing snapshots"; retry 2/5/15 s.
- Mock iPhone (demo) shown under connect/pending/failed cards.

## Tests
`pnpm --filter web test`: 19 pass (new: crop math, state mapping, countdown, streamUrl). `tsc -b` and `pnpm --filter web build` pass.
Playwright screenshots (stubbed fetch): scratchpad/04-03/device-{disconnected,pending,connected}.png.

## Deviations / risks
- Live canvas path not exercised end to end (no relay); only the fallback was seen. Pause only drops frames (socket stays open).
- Existing DeviceFrame unchanged. No change requests.
