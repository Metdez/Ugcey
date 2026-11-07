# 02-03 Summary: WP-C 9-tab inspector

## Files created (all under apps/web/src/components/)
- inspector/: index.ts (replaced stub; TAB_ORDER, TAB_META with `icon`, InspectorTabContent lazy), lib.ts (pure helpers), lib.test.ts, hooks.ts (usePoll, useFlash, download), chips.tsx, empty.tsx, tabs/{plan,agents,files,memory,sources,assets,approvals,audit,device}-tab.tsx, __fixtures__/index.ts, __dev__/preview.{html,tsx}
- agents/{subagent-run-card,subagent-detail,agent-roster}.tsx
- files/{file-tree,file-viewer}.tsx; memory/{memory-row,memory-add}.tsx; sources/source-item.tsx; audit/audit-row.tsx; device/{device-frame,device-receipts}.tsx

## Exported interfaces
TAB_ORDER, TAB_META (label, chord, icon), InspectorTabContent({tab}); each tab is a no-prop default export.

## Tests
- `node --test --experimental-strip-types src/components/inspector/lib.test.ts`: 2 pass (groupFiles, filterAudit). No vitest in repo; used node's runner.
- `pnpm --filter web exec tsc -b`: only errors are in stores/apply-event.ts (WP-A, TS2783 duplicate keys line 42). None in WP-C.
- `pnpm --filter web build`: passed on first run (before apply-event landed).
- Playwright screenshots of all 9 tabs with fixtures: scratchpad/02-03/*.png; no console errors.

## Preview
Standalone: `pnpm --filter web dev` then /src/components/inspector/__dev__/preview.html?tab=<tab> (stubs fetch with fixtures). No WP-A mount needed.

## Deviations
- Mobbin not consulted; UI-SPEC covered every pattern.
- Files tab: simple stacked tree + viewer, not ResizablePanelGroup. Memory tab: no Pending/Log tabs, no delete. Audit: JSON export only. No Expand dialog.
- AssetThumb already opens the lightbox; the tab does not wrap it.

## Change requests
- WP-B: AssetThumb reads only `useThread.assets`, so assets from other threads (api.listAssets) render null. Accept an optional `asset` prop or fall back to a shared lookup.
- WP-A: fix apply-event.ts:42 duplicate keys (TS2783).

## Risks
- Audit is scoped to current thread (all if none); device receipts are workspace-wide.
- Poll hooks pause on document.hidden only; tabs mount only while active.
