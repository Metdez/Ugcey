# Ugecy UI-SPEC v1: chat workspace with agent-context inspector

**Status:** ready to build. **Date:** 2026-11-07. **Evidence:** `UI-RESEARCH.md` (Mobbin IDs and docs) plus alignment with `CLOUDFLARE.md` and `DEEPAGENTS.md`.

**Scope:** shell, chat stream, 9-tab inspector, optional device pane and connections page. **Out of scope:** campaign board view (phase 2) and auth screens.

**Paths and rules:** paths are relative to the SPA source root, `src/` of the `ugecy` Worker app (CLOUDFLARE.md §0.1, §4). Every source file has 500 lines or fewer.

## 0. Stack and setup (WP-A runs these; nobody else runs `shadcn add`)
```bash
npx shadcn@latest init -t vite -b base            # Base UI flavour, Vite template, css-variables on (inside the ugecy app)
npx shadcn@latest add sidebar resizable tabs sheet dialog alert-dialog command popover hover-card tooltip \
  dropdown-menu scroll-area separator badge button button-group toggle toggle-group input input-group textarea \
  field label switch select checkbox radio-group avatar skeleton spinner kbd empty item card progress \
  collapsible breadcrumb aspect-ratio alert toast trace code-block message message-scroller bubble attachment
pnpm add streamdown agents zustand react-router lucide-react @fontsource-variable/inter @fontsource-variable/jetbrains-mono
```

- **Platform:** Vite plugins `react()`, `tailwindcss()`, `cloudflare()` and the `@` alias; Wrangler `assets.not_found_handling="single-page-application"`. OAuth callbacks go through `run_worker_first` (owned by the Cloudflare WP).
- **Component rules:** Base UI composes with the `render` prop, not `asChild`. Toasts use `toast.add()` from `@/components/ui/toast`; **do not add Sonner**. Icons are lucide only.
- **Routes and transport:** react-router routes `/`, `/t/:threadId` and `/settings/connections`. `VITE_AGENT_TRANSPORT=agents|mock`, defaulting to `mock` in dev when the Worker is not running.

## 1. Layout
```
┌────────────┬──────────────────────────────────────────────┬────────────────────────┬────┐
│LeftSidebar │ MainHeader  [≡] Campaign / Thread title   [Model ▾][● Running][MOCK][⌘K][⊟]  │Rail│
│ ws switch  │ SystemBanners (mock | offline | reconnecting)                       │44px│
│ + New chat │ ChatView: centered column max-w-[48rem], px-6                        │ ▣  │
│ Campaigns ▸│   …turns…                                  ║ InspectorPanel         │ ▣  │
│  threads   │                                            ║ header: title+actions+×│ ▣  │
│ Recent     │ RunStatusPill (docked, only while running)  ║ active tab (ScrollArea)│ ▣  │
│ Accounts ● │ Composer                                    ║                        │ ▣  │
└────────────┴────────────────────────────────────────────╨────────────────────────┴────┘
```

**Shell structure:** `SidebarProvider` wraps `LeftSidebar` + `SidebarInset`. The inset holds `ResizablePanelGroup orientation="horizontal"` with panels `main`, `device` (pinned only) and `inspector`; `InspectorRail` sits outside the group at the right edge. **Do not use a second shadcn `Sidebar` for the inspector**: one provider has only one open state.

| Pane | Default | Min / Max | Collapse | Persisted |
|---|---|---|---|---|
| Left sidebar | 256px (`--sidebar-width:16rem`) | icon mode 48px (`--sidebar-width-icon:3rem`) | `collapsible="icon"`; ⌘B (shadcn built-in); `SidebarRail` | shadcn cookie |
| Main | flex | min `"40%"`; chat column ≤768px | never | – |
| Device (pinned) | `"28%"` | `"300px"` / `"40%"` | Unpin returns it to the Device tab; ≥1280px only | `localStorage ugecy.layout.v1` |
| Inspector | `"30%"` | `"320px"` / `"50%"`; `collapsible`, `collapsedSize="0%"` | ⌘I, or click the active rail icon; another icon opens that tab | `localStorage ugecy.layout.v1` |
| Rail | 44px fixed | – | always visible ≥1024px | – |

Sizes are react-resizable-panels v4 strings; get collapse and expand through `panelRef`.

**Responsive behaviour:**
- **≥1280px:** everything. **1024–1279px:** inspector starts collapsed; opening it sets the left sidebar to icon mode; no device pinning.
- **768–1023px:** the left sidebar is an off-canvas Sheet (shadcn `isMobile`). The inspector is a `Sheet side="right"` at `w-[min(440px,92vw)]` (header button or ⌘I). The rail is hidden and tabs become a horizontally scrolling icon+label `Tabs` list.
- **<768px:** both are sheets, the inspector full width. The header keeps the trigger, truncated title, approvals count and inspector button. The composer is sticky with `pb-[env(safe-area-inset-bottom)]`; the pill shrinks to icon + "3/7". No horizontal scroll at 360px.

**Inspector rail:** a vertical single-value `ToggleGroup` of 32px icon buttons with Tooltip (label + chord). Order and lucide icons: Plan `ListTodo` · Agents `Bot` (badge: running count, pulse) · Files `FolderTree` (badge: changed since viewed) · Memory `Brain` · Sources `Globe` · Assets `Images` (badge: new/generating) · Approvals `ShieldCheck` (badge: pending count, `bg-warning`) · Audit `ScrollText` · Device `Smartphone` (red dot when live).

## 2. Data contracts (WP-A writes `src/types/agent.ts` verbatim; B and C import types only from here)
```ts
export type InspectorTab = 'plan'|'agents'|'files'|'memory'|'sources'|'assets'|'approvals'|'audit'|'device';
export type AgentKind = 'orchestrator'|'research_analyst'|'creative_strategist'|'production_coordinator'|'publishing_coordinator'|'device_operator'|'analytics';
export type RunStatus = 'idle'|'connecting'|'streaming'|'interrupted'|'error'|'offline';
export interface ModelInfo { id: string; provider: string; label: string; contextWindow: number; usedTokens?: number }
export interface Todo { id: string; content: string; status: 'pending'|'in_progress'|'completed' }   // = deepagents write_todos
export interface ToolCall { id: string; name: string; args: Record<string, unknown>; agent: AgentKind;
  status: 'running'|'complete'|'error'|'denied'|'awaiting_approval'; output?: string; error?: string;
  startedAt: string; endedAt?: string; fileRefs?: string[]; assetRefs?: string[]; sourceRefs?: string[] }
export interface SubagentRun { id: string /* `task` tool_call id */; kind: AgentKind; name: string; task: string;
  status: 'running'|'complete'|'error'; model?: string; tools?: string[]; toolCallIds: string[]; result?: string;
  startedAt: string; endedAt?: string; parentMessageId: string }
export interface VirtualFile { path: string; content: string; author: AgentKind; updatedAt: string; sizeBytes: number }  // state.files
export interface MemoryItem { id: string; path: string /* /memories/brand.md */; kind: 'brand'|'preference'|'playbook'|'fact'|'instruction';
  scope: 'workspace'|'campaign'; content: string; updatedAt: string; author: 'user'|AgentKind; source?: { threadId: string; messageId?: string } }
export interface Source { id: string; url: string; title: string; domain: string; platform: 'tiktok'|'instagram'|'youtube'|'x'|'web';
  retrievedAt: string; snippet?: string; metrics?: { views?: number; likes?: number; shares?: number }; usedInMessageIds: string[] }
export interface Asset { id: string; kind: 'image'|'video'; status: 'queued'|'generating'|'ready'|'failed'; progress?: number;
  url?: string; thumbUrl?: string; width: number; height: number; durationSec?: number; prompt: string; model: string;
  provider: 'higgsfield'|'mock'; simulated: boolean; createdAt: string; campaignId?: string;
  publishState?: 'draft'|'pending_approval'|'approved'|'scheduled'|'published'|'failed' }
export type DecisionType = 'approve'|'edit'|'reject'|'respond';
export type Decision = { type: 'approve' } | { type: 'edit'; edited_action: { name: string; args: Record<string, unknown> } }
  | { type: 'reject'; message?: string } | { type: 'respond'; message: string };   // = LangChain HITL resume items (positional)
export interface ActionRequest { name: string; args: Record<string, unknown>; description?: string; allowedDecisions: DecisionType[] }
export interface ApprovalRequest { id: string /* interrupt id; subagent interrupts bubble to root with same id */; threadId: string;
  createdAt: string; agent: AgentKind; category: 'publish'|'generate_media'|'device_action'|'spend'|'memory_write'|'question'|'other';
  risk: 'low'|'medium'|'high'; title: string; actions: ActionRequest[]; assetIds?: string[];
  status: 'pending'|'approved'|'edited'|'rejected'|'responded'|'expired'; decidedAt?: string; decidedBy?: string; decisions?: Decision[] }
export interface AuditEvent { id: string; at: string; actor: { type: 'user'|'agent'|'system'; id: string; label: string; agent?: AgentKind };
  action: string /* dot key, e.g. post.published */; summary: string; result: 'success'|'failure'|'pending';
  target?: { type: string; id: string; label: string }; threadId?: string; approvalId?: string; meta?: Record<string, unknown> }
export interface DeviceReceipt { id: string; at: string; action: string; summary: string; screenshotUrl?: string; approvalId?: string }
export interface DeviceSession { id: string; deviceName: string; supported: boolean; streamUrl?: string; streamKind?: 'webrtc'|'hls'|'mjpeg';
  status: 'unsupported'|'disconnected'|'consent_required'|'connecting'|'live'|'paused'|'ended'|'error';
  consent: { granted: boolean; grantedAt?: string; scopes: string[] }; latencyMs?: number; receipts: DeviceReceipt[] }
export type MessagePart = { type: 'text'; text: string } | { type: 'reasoning'; text: string; durationMs?: number }
  | { type: 'tool'; toolCallId: string } | { type: 'subagent'; subagentId: string } | { type: 'approval'; approvalId: string }
  | { type: 'assets'; assetIds: string[] } | { type: 'plan' } | { type: 'sources'; sourceIds: string[] }
  | { type: 'error'; message: string; retryable: boolean };
export interface ChatMessage { id: string; role: 'user'|'assistant'; createdAt: string; parts: MessagePart[];
  status: 'streaming'|'complete'|'error'|'interrupted'; model?: string; durationMs?: number;
  attachments?: { name: string; url: string; kind: 'image'|'video'|'file' }[] }
export interface ThreadSnapshot { threadId: string|null; title: string; campaignId?: string; status: RunStatus; model?: ModelInfo;
  messages: ChatMessage[]; todos: Todo[]; toolCalls: Record<string, ToolCall>; subagents: Record<string, SubagentRun>;
  files: Record<string, VirtualFile>; memory: MemoryItem[]; sources: Record<string, Source>; assets: Record<string, Asset>;
  approvals: Record<string, ApprovalRequest>; audit: AuditEvent[]; device?: DeviceSession; error?: { message: string; retryable: boolean } }
export interface Health { status: 'ok'|'degraded'|'down'; integrations: { id: string; label: string; mode: 'live'|'mock'|'error' }[] }
export interface ConnectedAccount { id: string; platform: 'tiktok'|'instagram'|'youtube'|'x'|'higgsfield'|'glasshand';
  handle?: string; status: 'connected'|'expired'|'error'|'not_connected'|'mock'; scopes: string[]; lastCheckedAt?: string }
export interface Campaign { id: string; name: string; status: 'draft'|'active'|'paused'|'completed'; threadIds: string[] }
export interface ThreadSummary { id: string; title: string; campaignId?: string; updatedAt: string; status: RunStatus; pendingApprovals: number }
```

**Stores (WP-A, zustand). They are the only cross-component channel:**
- **`stores/thread-store.ts`:** `useThread(selector)` over `ThreadSnapshot` & actions `send(text,{attachments?,mentions?})`, `stop()`, `retry(messageId)`, `decide(approvalId, decisions: Decision[])`, `memoryAdd/Update/Remove`, `deviceRequestConsent()`, `deviceStop()`.
- **`stores/ui-store.ts`:** `useUi` state `inspectorOpen`, `inspectorTab`, `focus:{kind:'file'|'source'|'asset'|'approval'|'subagent'|'audit'|'memory';id}|null`, `devicePinned`, `paletteOpen`, `shortcutsOpen`, `lightboxAssetId`, `lastViewed`; actions `openInspector(tab, focus?)`, `toggleInspector()`, `setTab`, `openLightbox(id|null)`, `setPalette`, `setShortcuts`, `togglePinDevice`. Example: a chat file link calls `openInspector('files',{kind:'file',id:'/research/hooks.md'})`.

**Client (WP-A, `lib/agent/`):**
- **`client.ts`:** `AgentClient` with `health()` (`GET /api/health`), `listCampaigns()`, `listThreads()`, `listAccounts()`, `subscribe(threadId|null, onSnapshot)` → `unsubscribe`, `send`, `stop`, `retry`, `resume(threadId, approvalId, decisions)` (batched as `{[approvalId]:{decisions}}` when several interrupts are pending), `memory.*`, `device.*`.
- **`agents-adapter.ts` (live):** `useAgent` from `agents/react` against `/agents/chat-session/:threadId`. It consumes `shared/events.ts`, which the Cloudflare WP4 owns. A pure `applyEvent(snapshot, event)` reducer gets unit tests.
- **UI event needs (proposal for Cloudflare WP4's `shared/events.ts`; `applyEvent` maps each to the snapshot):**

| Event | Updates |
|---|---|
| `run.status{status}` | status |
| `message.start\|delta\|done{id,partIndex,text}` | text parts |
| `reasoning.delta\|done` | reasoning part |
| `tool.start\|end\|error{ToolCall}` | toolCalls + tool part |
| `subagent.start\|update\|end{SubagentRun}` | subagents |
| `todos.set{Todo[]}` | todos (`write_todos`) |
| `file.write{VirtualFile}` | files |
| `memory.write{MemoryItem}` | memory |
| `source.add{Source}` | sources |
| `asset.update{Asset}` | assets |
| `approval.request\|resolved{ApprovalRequest}` | approvals; on request, status `interrupted` |
| `audit.append{AuditEvent}` | audit |
| `device.state{DeviceSession}`, `device.receipt{DeviceReceipt}` | device |
| `error{message,retryable}` | error |

  Every event carries `threadId`, `seq` (monotonic, for de-dupe and resync) and `at`. On reconnect the client sends `lastSeq`, and the server replays or sends a `snapshot{ThreadSnapshot}`.
- **`mock-adapter.ts`:** replays `fixtures/*.ts` timelines with realistic delays. `?scenario=happy|approval|error|offline|mock|device` selects one.
- **Mock models** use DEEPAGENTS.md names: "GLM-5.3" for the orchestrator, "GLM-4.7-Flash" and "DeepSeek-V4.1-Flash" for workers. Never Anthropic.

## 3. Component inventory (path under `src/components/` · shadcn primitives · props / notes)

### WP-A: shell, data and common
| Component | Path | Primitives | Props / notes |
|---|---|---|---|
| AppShell | `shell/app-shell.tsx` | SidebarProvider, SidebarInset, ResizablePanelGroup/Panel/Handle(withHandle) | `{children}`; owns panelRefs for ⌘I |
| LeftSidebar | `shell/left-sidebar.tsx` | Sidebar(collapsible icon), SidebarHeader/Content/Footer/Rail | composes the rows below |
| WorkspaceSwitcher | `shell/workspace-switcher.tsx` | DropdownMenu, Avatar | `{workspaces, activeId, onSelect}` |
| NewChatButton | `shell/new-chat-button.tsx` | SidebarMenuButton, Kbd | → `/`; ⌘⇧O |
| CampaignNav | `shell/campaign-nav.tsx` | SidebarGroup(+Action), Collapsible, SidebarMenuSub, SidebarMenuBadge | `{campaigns, threads, activeThreadId}`; status dot draft/active/paused/completed |
| ThreadNav | `shell/thread-nav.tsx` | SidebarMenu, SidebarMenuAction, DropdownMenu, SidebarMenuSkeleton | Today / Yesterday / Previous 7 days / Older; Spinner if streaming; amber dot if `pendingApprovals` |
| AccountsStatus | `shell/accounts-status.tsx` | SidebarGroup, Tooltip, Badge | platform icon + handle + StatusDot (connected / expired / error / mock); "Manage" link |
| UserMenu | `shell/user-menu.tsx` | DropdownMenu, Avatar | theme System/Dark/Light, shortcuts, sign out |
| MainHeader | `shell/main-header.tsx` | SidebarTrigger, Breadcrumb, Button, Tooltip, Kbd | inline-rename title; inspector button with approvals count |
| ModelChip | `shell/model-chip.tsx` | Popover, Badge, Progress | `{model}`; popover: provider, context used/limit (shadcn Context pattern), per-agent models |
| RunStatusBadge | `shell/run-status-badge.tsx` | Badge, Spinner | Idle / Running / Needs approval / Error / Offline |
| SystemBanners | `shell/system-banners.tsx` | Alert, Button | `{health, transport}`; mock, offline and reconnecting banners (§6) |
| InspectorPanel | `shell/inspector-panel.tsx` | ScrollArea, Button | header = label + tab's `actions` export + close; body = `lazy(registry[tab].load)` + Suspense skeleton |
| InspectorRail / InspectorSheet | `shell/inspector-rail.tsx`, `shell/inspector-sheet.tsx` | ToggleGroup(vertical), Tooltip, Badge / Sheet, Tabs | counts from the thread store |
| Inspector registry | `shell/inspector-registry.ts` | – | `Record<InspectorTab,{label,icon,chord,load:()=>import('@/components/inspector/tabs/<tab>-tab')}>` |
| CommandPalette / ShortcutsDialog | `shell/command-palette.tsx`, `shell/shortcuts-dialog.tsx` | Command(CommandDialog), Dialog, Kbd | §8 |
| ConnectionsPage | `routes/settings-connections.tsx`, `connections/connection-row.tsx` | Item, Badge, Button, Popover, AlertDialog | "Connected (n)" / "Available"; scopes shown before connect; Disconnect confirm; Mock badge |
| Common atoms | `common/{agent-avatar,status-dot,relative-time,empty-state,kbd-combo}.tsx` | Avatar, Empty, Kbd | `AgentAvatar{kind,size}` uses `--agent-*`; `StatusDot{tone}`; `EmptyState{icon,title,description,action?}` |
| Formatting | `lib/format/{tool-labels,time,number}.ts` | – | `toolLabel(call)` → sentence by state: "Searching TikTok for “glow serum hooks”" / "Searched…" / "Failed to search…" |

### WP-B: chat stream, approvals and assets
| Component | Path | Primitives | Props / notes |
|---|---|---|---|
| ChatView | `chat/chat-view.tsx` | MessageScrollerProvider(autoScroll), MessageScroller(+Viewport/Content/Item/Button) | user turn `scrollAnchor`; EmptyThread when there are no messages |
| UserMessage | `chat/user-message.tsx` | Message(align end), Bubble(variant muted), Attachment, MessageFooter | hover Copy / Edit; send failure "Failed to send · Retry" |
| AssistantMessage | `chat/assistant-message.tsx` | Message, MessageContent, MessageFooter | renders `parts[]` in stream order (§4) |
| TurnHeader | `chat/turn-header.tsx` | Badge | AgentAvatar · "Ugecy" · model label · "Working for 12s" / time |
| MarkdownContent | `chat/markdown-content.tsx` | Streamdown, CodeBlock, HoverCard | `{text, streaming, sourceIds}`; `[n]` → inline citation hover |
| ReasoningBlock | `chat/reasoning-block.tsx` | Trace, TraceCollapsible | "Thinking…" (shimmer) → "Thought for 8s", collapsed |
| ToolCallLine | `chat/trace/tool-call-line.tsx` | Trace*, CodeBlock(size sm, max-h-64), Sheet | `{toolCallId}`; output >4KB → "Open output" Sheet; refs become links |
| SubagentLine | `chat/trace/subagent-line.tsx` | Trace*, Badge, CodeBlock | `{subagentId}`; nested Trace; "Open in Agents" |
| TraceGroup | `chat/trace/trace-group.tsx` | Trace, Collapsible | more than 6 consecutive lines → "N more steps" |
| InlinePlanCard | `chat/inline-plan-card.tsx` | Trace (Queue pattern), Progress | "Plan · 3/7 done"; current item; "Open Plan" |
| SourcesRow | `chat/sources-row.tsx` | Avatar (≤4 stacked favicons), Button | "12 sources" → Sources tab filtered to this message |
| MessageActions | `chat/message-actions.tsx` | Button(ghost icon-sm), Toggle(aria-pressed), Tooltip, DropdownMenu | Copy (✓ for 2s), Good, Bad, Retry, More (Copy markdown, View in Audit) |
| TurnError | `chat/turn-error.tsx` | Alert(destructive), Button | "The run stopped: {message}" · Retry · Copy details |
| RunStatusPill | `chat/run-status-pill.tsx` | Spinner, Progress, Collapsible, Button | docked above the composer (§6) |
| Composer | `chat/composer/composer.tsx` | InputGroup, Textarea(autosize 1–8 rows), Button, DropdownMenu, Badge | `+` menu (Attach media, Add source URL); campaign chip; Send ↔ Stop |
| SlashMenu / MentionMenu | `chat/composer/{slash-menu,mention-menu}.tsx` | Popover, Command | `/research /patterns /script /generate /publish /analyze`; `@research @creative @production @publishing @device @analytics` |
| EmptyThread | `chat/empty-thread.tsx` | Empty, Card, Item | greeting + StarterGrid + onboarding checklist (§6) |
| ApprovalCard | `approvals/approval-card.tsx` | Item(outline), Badge, Button, Separator, Kbd | `{approvalId, variant:'inline'|'panel'}`; reads the store; calls `decide` |
| ApprovalEditForm | `approvals/approval-edit-form.tsx` | Field, Input, Textarea, Switch, CodeBlock | string→Textarea, number→Input, bool→Switch, ISO date→datetime-local, object→JSON Textarea (validated) |
| ApprovalRejectForm / RespondForm | `approvals/{approval-reject-form,approval-respond-form}.tsx` | ToggleGroup chips, Textarea | reject reasons: Off-brand · Unsupported claim · Missing #ad disclosure · Wrong account · Bad timing; respond = answer textarea + options if given |
| ApprovalResolvedLine | `approvals/approval-resolved-line.tsx` | Trace | "Approved: publish to @glowco on TikTok · you · 14:02" (+ "edited" badge) |
| AssetThumb / PreviewGrid / Lightbox | `assets/{asset-thumb,asset-preview-grid,asset-lightbox}.tsx` | AspectRatio(9/16), Badge, Progress, Skeleton, Dialog | thumb `{assetId,size}` with duration / SIMULATED / publishState badges; grid 1→240px, 2–4→2 cols, >4→"+N"; lightbox via `ui.lightboxAssetId` (player, prompt, model, state, Download) |

### WP-C: inspector (each `inspector/tabs/<tab>-tab.tsx` is a no-prop default export and may `export const actions`)
| Tab | Files | Primitives | Content |
|---|---|---|---|
| Plan | `tabs/plan-tab.tsx` | Trace (Queue), Progress, Popover | "3 of 7"; "To do (n)" defaultOpen / "Completed (n)"; in_progress running; "Updated 2m ago · Revisions" |
| Agents | `tabs/agents-tab.tsx`, `agents/{subagent-run-card,subagent-detail,agent-roster}.tsx` | Card, Badge, Trace, ToggleGroup | Running / Completed; card = avatar, name, status, duration, task (2 lines), tools count, model; drill-in detail (task, model, tool trace, result, tokens); Team roster |
| Files | `tabs/files-tab.tsx`, `files/{file-tree,file-viewer}.tsx` | ResizablePanelGroup(vertical 40/60), Collapsible, CodeBlock, Streamdown, Dialog | tree from `state.files` paths (`/plans`, `/research`, `/scripts`, `/assets/manifest.json`…); "edited Ns ago" dot; viewer: path, author, updatedAt, Copy, Download, Expand |
| Memory | `tabs/memory-tab.tsx`, `memory/{memory-row,memory-add}.tsx` | Tabs(Long-term · Pending · Log), Item, Badge, InputGroup, AlertDialog | `/memories/**` docs with kind and scope; edit/delete with confirm; **Pending** = `memory_write` approvals; notice "Memory changes apply to new threads" (DEEPAGENTS.md §12) |
| Sources | `tabs/sources-tab.tsx`, `sources/source-item.tsx` | ToggleGroup(All/TikTok/IG/YT/Web), InputGroup, Item, Avatar, HoverCard | favicon, title, domain, platform, metrics, "used in N messages"; footer "Analyzed for patterns only — never re-published" |
| Assets | `tabs/assets-tab.tsx` | ToggleGroup(All/Images/Videos), Select(status, publish state), Toggle(density) | 2-col grid of B's `AssetThumb`; click → `openLightbox` |
| Approvals | `tabs/approvals-tab.tsx` | Badge, Collapsible, Select(category) | Pending: B's `ApprovalCard variant="panel"`; Resolved: decision, who, when, edit diff (arg: old → new) |
| Audit | `tabs/audit-tab.tsx`, `audit/{audit-row,audit-filters,export}.ts(x)` | DropdownMenu, Switch(Live), Collapsible, Badge, CodeBlock | row: `HH:mm:ss`, actor icon/avatar, sentence, mono `action` chip, result icon; expand → meta JSON; Export JSON/CSV; read-only |
| Device | `tabs/device-tab.tsx`, `device/{device-frame,device-consent-dialog,device-controls,device-receipts}.tsx` | Dialog, AlertDialog, Badge, Button, Trace | §5.6 |

## 4. Chat message anatomy
1. **User turn.** A right-aligned muted Bubble, max-w 85%, 15px. Attachments sit above it as 64px thumbs.
2. **Assistant turn.** No bubble. Parts render in stream order:
   - **a. TurnHeader.**
   - **b. ReasoningBlock.** 13px muted.
   - **c. Tool lines.** The sentence title always carries the state (Trace a11y rule): "Running fetch_trending_videos…", "Read 24 TikTok videos", "Wrote /research/hook-patterns.md" (opens Files with focus), "Failed to generate image".
   - **d. Subagent line.** Agent color dot. Running: "Research analyst is working…"; done: "Ran research analyst · 1m 12s". Expanded: task, Badges (model, tools), nested lines, result markdown clamped to 6 lines + "Show more".
   - **e. InlinePlanCard.** Shown on the first `write_todos` of the run and updated in place.
   - **f. ApprovalCard (inline):**
     - **Frame:** 3px `--warning` left border.
     - **Header:** category icon (Send / Clapperboard / Smartphone / CreditCard / Brain / MessageCircleQuestion), a title such as "Publish 1 video to @glowco on TikTok?", and a risk Badge.
     - **Args:** key/value preview (caption, account, schedule) plus asset thumbs.
     - **Footer:** Reject (ghost destructive), Edit (outline), Approve (primary, `⌘↵`). Only `allowedDecisions` appear.
     - **`question` category:** answer form + "Send answer" (`respond`), in the Base44 inline-question pattern.
     - **After a decision:** the card animates (180ms) into `ApprovalResolvedLine`.
     - **Several actions:** stacked cards. "Approve all (n)" appears only when every action is `risk:'low'`. `publish`, `spend` and `device_action` are always decided one at a time.
   - **g. MarkdownContent.** 15px/1.65 with clickable `[n]` citations.
   - **h. AssetPreviewGrid.** Generating: Skeleton + Progress + "Generating with Higgsfield · 0:23". Failed: red outline + Retry.
   - **i. SourcesRow.**
   - **j. Footer.** "Worked for 1m 42s · 14:03" + MessageActions.
3. **Follow-ups.** After the last completed turn, show 2–3 Suggestion chips, e.g. "Write 5 scripts from these patterns".

## 5. Inspector behaviours
1. **Focus.** `openInspector(tab, focus)` scrolls the item into view and flashes `bg-primary/10` for 1.2s.
2. **One source of truth.** Approvals, assets, files and memory render from one store, so a decision inline or in the tab updates both at once.
3. **Badges.** `lastViewed[tab]` clears a badge after the tab has been visible for 1s. Pending approvals never clear until decided.
4. **Empty states** (EmptyState; icon + one line): Plan "No plan yet. Ugecy writes one for multi-step work." · Agents "No subagents have run in this thread." · Files "Research notes, briefs and scripts the agent writes appear here." · Memory "Nothing remembered yet. Add brand rules or preferences." · Sources "Videos and pages the agent analyzes appear here." · Assets "Generated images and videos appear here." · Approvals "Nothing needs your approval. Publishing, spending and device actions always stop here first." · Audit "Every tool call, approval and external action is logged here." · Device "No device session. The device operator asks for consent before it connects."
5. **Audit.** Newest first. Live mode keeps the view pinned to the top. Use `content-visibility:auto` rows; virtualization is a v2 concern.
6. **Device.** Header: device name, state badge, latency.
   - **Consent gate:** no stream before consent. The consent Dialog (Quicken pattern) lists what is visible, what is recorded and how to stop, with Cancel / "I consent".
   - **Frame:** aspect 393:852, `rounded-[3rem] border-[10px] border-neutral-900`, Dynamic Island 126×37px. The screen is `<video>` (webrtc/hls) or `<img>` (mjpeg). Overlays: "LIVE" + latency, and a caption from the latest receipt ("Agent is tapping “Post”…").
   - **Controls:** Pause/Resume stream · Pin as pane · Stop session (AlertDialog).
   - **Receipts:** a Trace list with screenshot thumb and approval link.
   - **`supported:false`:** session state + receipts only (interface.md).

## 6. States
| State | Main pane | Composer | Chrome / inspector |
|---|---|---|---|
| Empty thread | H1 "What are we making today?"; StarterGrid 2×3 Cards (icon, title, example); "Get set up" checklist: Connect a social account · Connect Higgsfield · Add brand memory | focused; placeholder "Ask Ugecy to research, script, generate or publish…" | tabs empty |
| Loading | 3 Skeleton turns | disabled | SidebarMenuSkeleton ×5; tab skeleton rows |
| Streaming | shimmer on running lines; caret; `MessageScrollerButton` "Jump to latest (n)" when scrolled up | Send→Stop (Esc); typing allowed | Pill "Working · Step 3/7 — Writing hook variants · 0:42 [^][Stop]"; Agents pulse; title "● {thread} – Ugecy" |
| Awaiting approval | inline cards; pill amber "Paused · 2 approvals waiting [Review]" (focuses the first card) | Send becomes "Review approvals"; draft kept | Approvals badge; amber thread dot; title "(2) Approval needed · Ugecy"; `toast.add` with Review action when the card is off-screen or the tab hidden |
| Tool error | error TraceLine "Failed to …" + expandable error; run continues | – | Audit failure row |
| Turn error | TurnError Alert [Retry] [Copy details] | enabled | badge Error |
| Reconnecting | muted inline "Connection lost — reconnecting (2/5)…" | disabled | – |
| Offline | OfflineBanner "Can't reach the Ugecy server. Retrying in 8s · Retry now"; cached thread stays readable | replaced by "You're offline — messages can't be sent." | badge Offline; health every 10s, backoff to 60s |
| Mock mode | MockModeBanner (`FlaskConical`, warning-subtle): "Mock mode — Higgsfield and TikTok aren't connected, so media and publishing are simulated. Nothing will be posted. [Connect accounts]"; dismissible per session | – | header `MOCK` badge stays; SIMULATED badges on assets; "Approve (simulated)" |
| Account expired | AccountsStatus row amber "Reconnect" | – | publish card shows a warning Alert and disables Approve |

**Starters (title → example):** Find winning hooks → "Find the top 20 TikTok UGC hooks for clean skincare this month and explain why they work." · Extract patterns → "Break these 5 videos into hook, script structure and CTA patterns." · Write scripts → "Write 5 original 30-second UGC scripts for our serum using the top patterns." · Generate media → "Generate 3 vertical UGC-style videos for script #2 with Higgsfield." · Schedule posts → "Schedule the approved videos to @glowco on TikTok and Instagram this week." · Review performance → "How did last week's posts perform? What should we make next?"

## 7. Design tokens (`src/index.css`, WP-A; `<html class="dark">` by default; theme pref in localStorage)

Contrast (WCAG math, oklch→sRGB), dark: fg/bg 17.7:1 · muted-fg/bg 7.9 · muted-fg/muted 6.7 · primary/bg 7.6 · primary-fg/primary 7.5 · destructive/card 5.8 · agent colors/popover ≥7.1. Light: text tokens ≥4.5:1 on background. Agent colors are for dots, borders and avatars only; labels stay `foreground`.
```css
@import "tailwindcss"; @import "@fontsource-variable/inter"; @import "@fontsource-variable/jetbrains-mono";
@custom-variant dark (&:is(.dark *));
:root { --radius: 0.625rem;
  --background: oklch(0.99 0.002 270); --foreground: oklch(0.2 0.01 270); --card: oklch(1 0 0); --card-foreground: var(--foreground);
  --popover: oklch(1 0 0); --popover-foreground: var(--foreground); --primary: oklch(0.52 0.2 285); --primary-foreground: oklch(0.985 0.005 285);
  --secondary: oklch(0.96 0.004 270); --secondary-foreground: var(--foreground); --muted: oklch(0.965 0.004 270); --muted-foreground: oklch(0.5 0.015 270);
  --accent: oklch(0.95 0.01 285); --accent-foreground: var(--foreground); --destructive: oklch(0.56 0.21 25); --border: oklch(0.91 0.004 270);
  --input: oklch(0.89 0.005 270); --ring: oklch(0.52 0.2 285); --success: oklch(0.52 0.14 155); --warning: oklch(0.55 0.13 65); --info: oklch(0.52 0.14 240);
  --sidebar: oklch(0.975 0.003 270); --sidebar-foreground: var(--foreground); --sidebar-primary: var(--primary); --sidebar-primary-foreground: var(--primary-foreground);
  --sidebar-accent: oklch(0.94 0.006 270); --sidebar-accent-foreground: var(--foreground); --sidebar-border: var(--border); --sidebar-ring: var(--ring);
  --agent-orchestrator: oklch(0.52 0.2 285); --agent-research: oklch(0.52 0.13 240); --agent-creative: oklch(0.53 0.17 330); --agent-production: oklch(0.55 0.13 75);
  --agent-publishing: oklch(0.52 0.13 160); --agent-device: oklch(0.56 0.16 45); --agent-analytics: oklch(0.52 0.1 200);
  --chart-1: var(--agent-research); --chart-2: var(--agent-publishing); --chart-3: var(--agent-production); --chart-4: var(--agent-creative); --chart-5: var(--agent-device); }
.dark {
  --background: oklch(0.155 0.006 270); --foreground: oklch(0.965 0.003 270); --card: oklch(0.195 0.007 270); --card-foreground: var(--foreground);
  --popover: oklch(0.215 0.008 270); --popover-foreground: var(--foreground); --primary: oklch(0.72 0.15 285); --primary-foreground: oklch(0.16 0.02 285);
  --secondary: oklch(0.255 0.008 270); --secondary-foreground: var(--foreground); --muted: oklch(0.235 0.007 270); --muted-foreground: oklch(0.72 0.01 270);
  --accent: oklch(0.27 0.012 270); --accent-foreground: var(--foreground); --destructive: oklch(0.68 0.2 25); --border: oklch(1 0 0 / 9%);
  --input: oklch(1 0 0 / 15%); --ring: oklch(0.72 0.15 285); --success: oklch(0.76 0.15 155); --warning: oklch(0.82 0.15 80); --info: oklch(0.74 0.12 235);
  --sidebar: oklch(0.175 0.006 270); --sidebar-foreground: var(--foreground); --sidebar-primary: var(--primary); --sidebar-primary-foreground: var(--primary-foreground);
  --sidebar-accent: oklch(0.235 0.008 270); --sidebar-accent-foreground: var(--foreground); --sidebar-border: oklch(1 0 0 / 7%); --sidebar-ring: var(--ring);
  --agent-orchestrator: oklch(0.72 0.15 285); --agent-research: oklch(0.76 0.12 235); --agent-creative: oklch(0.74 0.15 330); --agent-production: oklch(0.8 0.14 85);
  --agent-publishing: oklch(0.77 0.15 160); --agent-device: oklch(0.74 0.15 45); --agent-analytics: oklch(0.8 0.11 195); }
@theme inline {
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif; --font-mono: "JetBrains Mono Variable", ui-monospace, monospace;
  /* map EVERY token above as --color-<name>: var(--<name>); (shadcn set + success, warning, info, agent-*) */
  --radius-sm: calc(var(--radius) * 0.6); --radius-md: calc(var(--radius) * 0.8); --radius-lg: var(--radius); --radius-xl: calc(var(--radius) * 1.4);
  --ease-out-quint: cubic-bezier(0.22, 1, 0.36, 1); --animate-shimmer: shimmer 1.6s linear infinite; }
@keyframes shimmer { from { background-position: 200% 0 } to { background-position: -200% 0 } }
@media (prefers-reduced-motion: reduce) { *, ::before, ::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important } }
```

**Subtle fills:** `bg-warning/12 text-warning` (same for success, destructive and info) for banners and badges. Use `text-background` on solid fills.

- **Typography:** Inter Variable (`font-feature-settings:"cv11","ss01"`); JetBrains Mono for paths, event keys and args; `tabular-nums` for figures. Sizes: chrome 13px/18 · chat prose 15px/1.65 · meta 12px/16 muted · Trace 13px · code 12.5px/1.6 · tab/section titles 14px/20 semibold · empty-state H1 28px/34 semibold, −0.02em.
- **Spacing (4px grid):** sidebar items `px-2 py-1.5` · chat column `px-6` · turns `gap-6` · parts `gap-2` · inspector `p-3`, lists `gap-1` · cards `p-3` · targets ≥32px (≥40px touch).
- **Radius:** `--radius` 10px; cards and dialogs `rounded-lg`, buttons and inputs `rounded-md`, badges `rounded-sm`, bubbles `rounded-2xl`, avatars `rounded-full`.
- **Motion:** hover/press 120ms · collapsible and card→line 180ms `ease-out-quint` · sheets and dialogs 220ms · toast 200ms · shimmer 1.6s. Panel resize is not animated. Reduced motion stops all of it; state stays in the text.
- **Icons (lucide):** `size-4` chrome, `size-3.5` Trace, `size-6` empty states. send `ArrowUp`, stop `Square`, inspector `PanelRight`, sidebar `PanelLeft`, mock `FlaskConical`, offline `WifiOff`, approvals `ShieldCheck`.

## 8. Interaction details and keyboard shortcuts (`hooks/use-shortcuts.ts`, WP-A)
| Keys | Action | Notes |
|---|---|---|
| ⌘K / Ctrl+K | Command palette | free text + ↵ on "Ask Ugecy: …" sends to the current or a new chat (Magnific pattern) |
| ⌘B | Toggle left sidebar | shadcn built-in; do not re-bind |
| ⌘I | Toggle inspector | `preventDefault`; on mobile opens the inspector Sheet |
| ⌘/ | Shortcuts dialog | two-column list (Slite pattern) |
| ⌘⇧O | New chat | |
| `/` | Focus composer | not while typing in a field |
| Enter / Shift+Enter | Send / newline | ignore while `isComposing` (IME) |
| Esc | Stop streaming if the composer is focused; else close the top Sheet/Dialog/palette | |
| ↑ (empty composer) | Edit last user message | |
| G then P/A/F/M/S/X/R/L/D | Plan / Agents / Files / Memory / Sources / Assets / Approvals (Review) / Audit (Log) / Device | 1s chord window; not in fields |
| ⌘↵ | Approve the focused ApprovalCard | No single-key approve, ever. Edit and Reject are buttons only |
| J / K | Next / previous pending approval | Approvals tab |

- **Palette groups:** Ask Ugecy (starters) · Navigate (campaigns, fuzzy threads, connections) · Inspector (9 tabs) · Actions (New chat, Stop run, Review approvals, Toggle sidebar/inspector, Pin device) · Settings (Theme). Footer: ↑↓ Navigate · ↵ Select · Esc Close.
- **Resize handles:** arrow keys ±1% on a focused handle; double-click resets. **External links:** new tab, `rel="noopener noreferrer"`, `ExternalLink` icon, `sr-only` "(opens in a new tab)".

## 9. Accessibility
- **Landmarks:** `nav` (sidebar), `main` (chat), `aside aria-label="Agent context"` (inspector). The rail is `role="tablist" aria-orientation="vertical"`, and panels are labelled.
- **Live regions:** Message Scroller announces each new Trace line once; RunStatusPill is `aria-live="polite"`; a new approval triggers an assertive sr-only "Approval needed: {title}".
- **Focus and signals:** visible `ring-[3px] ring-ring/50`. Color is never the only signal: status words go in titles and badges carry text. Icon-only buttons have `aria-label` + Tooltip; collapsibles expose `aria-expanded`.
- **Media:** videos have controls and a muted hover-preview only. The device stream has an `aria-label` and a text receipt log.

## 10. Work packages (parallel; exclusive write ownership; cross-package imports only of listed exports)
| WP | Exclusive files | Milestone 1 (contract freeze, ≤25% of effort) | Done when |
|---|---|---|---|
| **A: Foundation & shell** | SPA config entries (`components.json`, `index.html`, `src/main.tsx`, `src/App.tsx`), `src/routes/**`, `src/index.css`, `src/components/ui/**` (only A runs `shadcn add`), `src/types/**`, `src/lib/**`, `src/stores/**`, `src/hooks/**`, `src/components/{shell,common,connections}/**`. `vite.config.ts` and `wrangler.jsonc` are shared with the Cloudflare WP1; A edits only the SPA parts | **A1:** primitives + tokens + `types/agent.ts` + stores + mock adapter and fixtures + **stub files with final export signatures for every B and C module** (render a placeholder), so the app builds | Responsive shell at 4 breakpoints; ⌘K/⌘B/⌘I/⌘/ and G-chords; banners; connections page; live adapter with a unit-tested `applyEvent` against `shared/events.ts` |
| **B: Chat stream** | `src/components/{chat,approvals,assets}/**` (replaces A1 stubs) | message list + markdown + tool lines on the mock timeline | every §4 part renders; Approve/Edit/Reject/Respond send the exact `Decision` shapes; streaming, interrupted, error and empty states per §6 |
| **C: Inspector** | `src/components/{inspector,agents,files,memory,sources,audit,device}/**` (replaces A1 stubs) | Plan + Agents + Files tabs on mock data | all 9 tabs per §3/§5 with empty states; reuses B's `ApprovalCard`, `AssetThumb` and `AssetLightbox` by import only; consent gate; audit export |

**Rules:** (1) never edit another WP's files; send change requests to the owner. (2) B and C can start before A1 merges by coding against the §2/§3 signatures. (3) Extra fixtures go in `src/components/<own-dir>/__fixtures__/`. (4) Every WP ships Vitest + Testing Library tests: pure mappers plus one render test per component.

## 11. Acceptance checklist
- [ ] 3-pane resizable shell with collapse and persistence per §1. Sheets below 1024px. No horizontal scroll at 360px.
- [ ] One mock run shows, in both the chat and the tabs: plan, ≥2 subagents, tool lines (one failing), file writes, a memory-write approval, sources, generating→ready assets, a publish approval, audit rows and a device session.
- [ ] Approve, Edit (args changed), Reject (with reason) and Respond each produce the documented payload, collapse to a resolved line and append an audit event.
- [ ] Mock, offline, reconnecting and error states can be triggered via `?scenario=`. The model is visible in the header chip, turn headers and subagents. No Anthropic names.
- [ ] Contrast ≥4.5:1 for text and ≥3:1 for indicators. Keyboard-only walkthrough of §8 passes. Reduced motion stops shimmer.
