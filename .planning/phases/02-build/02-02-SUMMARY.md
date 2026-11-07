# 02-02 SUMMARY (WP-B: chat stream, approvals, assets)

## Files created (all under apps/web/src/components/)
- chat/: index.ts (frozen exports re-exported), chat-view, assistant-message, user-message (+CopyButton), markdown-content, reasoning-block, inline-plan-card, turn-error, run-status-pill, empty-thread, tool-labels(+test)
- chat/primitives/trace.tsx (TraceLine, CodeBlock, AgentDot); chat/trace/{tool-call-line,subagent-line}.tsx
- chat/composer/{composer.tsx,slash-commands.ts}
- chat/__fixtures__/snapshot.ts, chat/__dev__/preview.tsx (default export; mount on `?preview=chat`)
- approvals/{approval-card,approval-edit-form,approval-reject-form,approval-decisions(+test)}
- assets/{asset-thumb,asset-preview-grid,asset-lightbox}.tsx

## Exported interfaces
ChatView, ApprovalCard({approvalId,variant}), AssetThumb({assetId,size?}), AssetLightbox() via chat/index.ts. Also AssetPreviewGrid, toolLabel/agentColor.

## Verify
- vitest (chat, approvals): 2 files, 5 tests pass.
- `tsc -b`: no errors in my files. Remaining errors are in others' files: files/file-tree.tsx (unused `entry`), inspector/tabs/memory-tab.tsx (`usePoll` undefined).
- `vite build` alone passes. `pnpm build` fails only because of the tsc errors above.
- Visual screenshot not taken (no Playwright installed); the preview route exists but needs mounting by WP-A.

## Deviations
- Approval card is card-level: Approve/Reject/Edit apply to every request in the interrupt, and a button shows only if all requests allow it. Edit shows one form per request.
- Skipped (shortcut): TraceGroup ("N more steps"), SourcesRow, follow-up suggestion chips, MessageActions beyond Copy, "Approve all" low-risk shortcut, mention menu, `question` respond form, Sheet for >4KB output (truncated inline instead).
- Mobbin consulted (Searchable, Plane, Voicenotes): "Working for Ns" status, jump-to-latest arrow button.

## Change requests
- WP-A: mount `<ChatView/>` in a `h-full` container; lazy-import `chat/__dev__/preview` for `?preview=chat` in DEV; mount AssetLightbox once.
- WP-A: for the first send, push the user message in `threadActions.send` so EmptyThread hides; retry uses the last user message text.
- WP-A: `decide` should set approval status so the resolved line renders.

## Risks
- Autoscroll uses scrollTop, untested in a browser.
- Video hover play depends on url being set (mock assets have null url, so they show only the SIMULATED badge).
