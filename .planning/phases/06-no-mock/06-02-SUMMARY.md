# 06-02 Remove mock mode (web) — summary

Removed: `src/fixtures/*` (MOCK flag, `?mock=1`, VITE_MOCK, replay), `__dev__` preview mounts (chat, inspector), unused `__fixtures__` dirs, `device-frame.tsx` (mock iPhone), SIMULATED/MOCK badges (asset thumb, lightbox, audit row, device tab, accounts).
Changed: workspace-store / thread-store / thread-nav (no MOCK branches); system-banners (dismissible "Not connected" banner, per session); main-header (iPhone/Higgsfield live/off chips); device-tab (connect card only when not connected); accounts sidebar ("No social accounts connected").
Added: `lib/not-connected.ts` (+ test) mapping off modes to messages; test-only timeline at `stores/__fixtures__/run-timeline.ts` (sampleRun/sampleResume, imported only by apply-event.test.ts).
Verify: tsc -b, build, vitest 21/21 pass; final grep for mock|simulat|demo|sample data (non-test, non-__fixtures__) returns nothing. Screenshot: scratchpad/06-02/not-connected.png.
Risks: none known; a tab-opening "Open Device tab" link is shown in the banner when device is off.
