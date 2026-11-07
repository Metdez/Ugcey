# 02-01 Summary (WP-A: shell, stores, data layer)

## Files created / changed
- `src/index.css` (UI-SPEC §7 tokens, fonts, `success/warning/info/agent-*`), `vite.config.ts` (vitest block), `main.tsx`, `App.tsx`
- `src/components/ui/`: added alert-dialog, breadcrumb, aspect-ratio, checkbox, spinner, empty, item, field, input-group, button-group (Radix flavour). Registry emitted `from "cn"`; rewritten to `@/lib/utils` in all ui files.
- `src/stores/`: `apply-event.ts` (+test), `history.ts`, `thread-store.ts`, `workspace-store.ts`
- `src/fixtures/`: `mock-run.ts` (`MOCK`, `mockRun`, `mockResume`, `replay`), `mock-data.ts`
- `src/lib/`: `location.ts`, `time.ts`, `theme.ts`, `sse.test.ts`
- `src/hooks/`: `use-shortcuts`, `use-thread-route` (`navigateToThread`), `use-health`, `use-media-query`
- `src/components/shell/`: app-shell, left-sidebar, new-chat-button, thread-nav, accounts-status, main-header, model-chip, run-status-badge, system-banners, inspector-panel/rail/sheet, inspector-icons (`TAB_ICONS`, `useTabBadges`), command-palette, shortcuts-dialog
- `src/components/common/`: agent-avatar (`AgentAvatar{kind,size}`), status-dot (`StatusDot{tone,label,pulse}`), relative-time, empty-state (`EmptyState{icon,title,description,action}`)

## Exported interfaces
`applyEvent(s, e)`, `historyToUi`, `useThread/threadActions` (frozen API), `useWorkspace` (config, threads, accounts, health, boot/refresh*), `navigateToThread(id|null)`, `MOCK`.

## Tests
- `pnpm --filter web build`: pass. `tsc -b`: clean.
- `pnpm --filter web test`: my 11 tests pass (applyEvent nesting/approval/dedupe/seq, full mock timeline, readSse chunking/CRLF/comments/UTF-8). The suite as a whole FAILS only because WP-C's `components/inspector/lib.test.ts` imports `node:test` (see change requests).
- Playwright `/?mock=1`: shell, banner, sidebar, inspector rail/panel, streaming run render; zero console errors (screenshots in scratchpad `02-01/`).

## Deviations
- Assistant UiMessage is per `message_id` (spec literal); tool/subagent/approval/asset parts attach to the latest assistant message. One turn may be several consecutive assistant messages.
- Skipped (not in task list): WorkspaceSwitcher, CampaignNav, UserMenu, inline title rename, sidebar icon-mode on inspector open at 1024-1279px.
- History conversion drops subagent-internal assistant turns (no parent id in ChatMessage). `# shortcut` noted in `history.ts`.

## Change requests
- WP-C: `inspector/lib.test.ts` must import from `vitest` (not `node:test`); vitest `include` is `src/**/*.test.{ts,tsx}`.
- WP-B: composer textarea must live inside `<main>` (the `/` shortcut and Esc-to-stop use `main textarea`). Mock approval interrupt id is `int-1`, call `g1`.

## Risks
- Deps added with pnpm: `@fontsource-variable/inter`, `@fontsource-variable/jetbrains-mono`, dev `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` (testing-library not yet used in tests).
- Main bundle 710 kB (no code splitting yet).
