# Ugecy UI research: chat-first agent operator workspace

- **Date:** 2026-11-07. **Phase:** GSD `ui-phase` research, input to `UI-SPEC.md`.
- **Method:** Mobbin MCP (21 screen searches, 1 flow search and 1 section search) and Firecrawl (shadcn/ui docs and raw MDX on GitHub, LangChain docs, GitHub repos, Cloudflare docs).
- **Question:** What should a chat-first workspace look like when it has to show a Deep Agents run (plan, subagents, tool calls, files, memory, sources, assets, approvals, audit, device), and which component foundation should we use?
- **Success criteria:**
  - Every pattern we adopt has a cited reference.
  - The library choice is license-compatible, and the code is ours to own.
  - The spec is concrete enough for 2–3 coding agents to build in parallel without asking questions.

---

## 1. Key findings

1. **AI SDK Elements is being folded into shadcn/ui.** elements.ai-sdk.dev shows the banner *"AI Elements is moving to shadcn/ui. This project will be deprecated at the end of November 2026."* ui.shadcn.com/docs/ai-elements now ships the same patterns as copy-in code: *"There is no package to install. The code is yours."* We should not start on the deprecated registry.
2. **shadcn now has first-party chat primitives.**
   - **Components:** `Message`, `Message Scroller`, `Bubble`, `Trace`, `Code Block`, `Attachment`, `Questionnaire`, `Kbd`, `Spinner`, `Empty` and `Item`.
   - **AI patterns built on them:** Chat, Reasoning, Chain of Thought, Tool, Subagent, Plan, Queue, Confirmation, Sources, Inline Citation, Context, Model Selector, Prompt Input, Suggestion, File Tree and Checkpoint.
   - Each agent step (Reasoning, Tool, Plan, Subagent) renders as the same kind of `TraceLine`. That is what makes a dense activity stream readable.
3. **The Queue pattern's todo statuses match Deep Agents exactly.**
   - `pending` uses `CircleIcon`.
   - `in_progress` uses `CircleDotIcon` with `status="running"`.
   - `completed` uses `CircleCheckIcon`.
   - These are the same statuses as `stream.values.todos` from `@langchain/react` `useStream`. No mapping layer is needed.
4. **The interrupt contract is fixed by LangChain.**
   - **Interrupt payload:** `{action_requests:[{name,args,description}], review_configs:[{action_name, allowed_decisions}]}`.
   - **Resume:** `Command(resume={"decisions":[...]})`, with one decision per action and in the same order.
   - **Decision shapes (from deep-agents-ui `ToolApprovalInterrupt`):**
     - `{type:"approve"}`
     - `{type:"edit", edited_action:{name,args}}`
     - `{type:"reject", message}`
   - shadcn's Confirmation pattern only covers approve and deny, so we extend it with Edit and Reject-with-reason.
5. **Every serious agent product shows the run in two places.** There is a compact inline trace in the chat, plus a persistent side panel. Examples: Manus "Manus's Computer", Devin "Worklog / Desktop", ChatGPT deep research "Activity | 23 Sources", Cursor "Setup/Git/Desktop/Terminal" and NotebookLM "Sources | Chat | Studio". This confirms the chat + right inspector design.
6. **Approvals in good products happen inline in the chat, not in modals.**
   - Base44 asks inline questions with options, a free-text answer, and Skip/Send.
   - Emergent shows "Agent has been paused".
   - Relevance AI shows a "This task is paused…" banner with "Resume Task".
   - Modals (Dub, Asana, Runway) are kept for destructive or global confirmations such as delete, disconnect and device consent.

---

## 2. Mobbin findings (app → pattern → how Ugecy uses it)

Links use the form `https://mobbin.com/screens/<id>` unless marked *flow* or *section*.

| App | Screen ID | Pattern observed | How Ugecy uses it |
|---|---|---|---|
| ChatGPT | aa10c227-727c-4f1c-b628-c219f29cbfb8 | Sidebar with New chat/Search/Projects and grouped chats; message action row (copy, thumbs, share, regenerate) | Left sidebar structure; assistant footer actions |
| ChatGPT (deep research) | 73833b79-1dd5-4354-8fc4-a2e99c33a75e | Right panel with `Activity / 23 Sources` segmented tabs; "Read domain" rows; footer "Research completed in 5m · 23 sources"; stacked favicons + "Sources" button | Inspector Sources tab; sources row under assistant turns |
| Customer.io Agent | fafcbfb9-fa85-4b4d-b17f-54df962305b5 | "Thought for 2 seconds" and "Searched docs" collapsibles; "5 references" popover; suggestion chips above the composer | Reasoning collapsible; per-turn sources popover; follow-up chips |
| Grok | 0d566935-f7bd-405e-bcb3-5c9cc1d026c8 | Floating composer with model chip; Stop replaces Send while streaming | Composer send/stop swap; model chip |
| Mistral Le Chat | f55821bf-0d53-4ae9-92e7-4c68fcf4fffe | "Context" nav item; "Type / for quick access"; Think toggle | `/` slash menu in the composer |
| Mistral memories | b2c011be-a7e2-4b9d-a63b-86908762ef26 | "Enabled" badge; "Type to add a new memory"; date grouping; success toast | Memory tab add-input and toast |
| Mistral feedback | 4a5c8393-5ae0-47ee-a729-499c3d68256f | Inline feedback card with reason chips + textarea + Submit | Reject-with-reason form inside the ApprovalCard |
| Mistral Canvas | dc92d05f-dbb6-4151-89ec-d9bacd44c0da | Artifact card in chat opens a right pane with copy, fullscreen and download | File/asset "open in inspector" behaviour |
| Lindy | 111149e0-4dff-4de8-b3c1-0f7d032ff105 | Two-level left nav (agents + chat list with search/filter) | Campaigns group with nested threads |
| Lindy computer | 9f4affd5-f387-4149-860e-95c83f9bbba5 | Chat + right Browser/Terminal pane; checklist of steps with chevrons; "Processing…" current step | Inline Plan card; Device pane next to chat |
| Manus | 59dd33d5-6390-464e-a5b0-48ceced1b893 | "Manus is working" collapsible with skill chips; **docked progress pill above the composer** ("working 0:03 Thinking 1/1") with a live thumbnail | `RunStatusPill` docked above the composer |
| Manus | 728a9190-886a-4843-8b2e-a9ea8c180d18 | Plan steps as a vertical timeline; plan card with "Accepted" state; "2/2" step counter | Plan card states; step counter |
| Manus | 0f0a51a4-a51f-4726-9f9e-b85123e701fd | Inline document card; "Task completed"; Suggested follow-ups; scroll-to-bottom button | Turn-complete footer; follow-up suggestions; jump-to-latest |
| Manus | 51a42fdf-a153-4d72-8350-67ab7e251b81 | "Manus's Computer" panel: "using Editor · Reading file"; replay scrubber with ● live | Device tab: live badge + action caption |
| Relevance AI | c1486516-90be-4b17-9bb7-f7d5e3290911 | Task list with spinner on the running task; "1 step performed in the background" collapsible | Thread row running state |
| Relevance AI | 4366a3ad-efe2-464b-99e7-2ff4202948a5 | Paused banner + "Resume Task"; details panel (status, actions used, credits, run time) | Interrupted state banner; Agents detail metrics |
| Browserbase | f6d570c4-1c95-4789-a9bd-95cffe881757 | Run trace with step types (Prompt/Reason/Tool) + timestamps; HTTP 200 result cards | Audit row anatomy; tool output cards |
| Rox | 107c729c-a68d-48e3-8ece-51d43eff4215 | "Step 1 of 7" + progress bar + "3 min left"; tool sub-step chips ("Searching the web for…") | Pill progress text; tool line titles as sentences |
| Descript | ee6bcb01-04ba-40f1-b108-4ad5f83adc62 | "Analyzing steps…" status strip docked on the composer; "@ to add context" | Pill placement; `@agent` mentions |
| Asana | 4723019e-bcb7-4df0-8dca-fc7f4ab94c93 | "Summarize task is running" inline; "Running 1 rule" toast | Background-run toast when the inspector is closed |
| Google AI Studio | 7b4e8430-808c-4720-a543-2a5a528b940c | Turn header "Model · Ran for 46s"; boxed inline error; checkpoint restore | Turn header (model + duration); inline error block |
| Replit | fc901296-5e3a-4d81-aec5-ed164e3fce20 | "Worked for 24 minutes"; actions collapsed to "7 actions" | Collapse long traces to "N steps" |
| Replit | 7211ff6b-68b2-48cb-9091-e47ac1908090 | Inline publish-status card; usage warning card; "Suggested next tasks" with Start | Inline post-publish receipt card |
| Replit device | dd1c8162-34b3-4502-89dd-207cd54aa119 | iPhone frame with Dynamic Island preview; "Try on device" | Device frame proportions and chrome |
| v0 | e41c1642-db55-4234-9ee3-f0a497cdb878 | "Thought for 3s"; "Worked for 12s · 11:18 AM"; empty state with shortcut hints | Turn footer; empty Files tab with hints |
| v0 | c79203ed-5f35-4138-a53f-b6b6e9605242 | "All tasks complete" status line at the top of a turn | Completed-plan line |
| Emergent | e123876d-56ef-4731-aa60-d8e6a4c05ec4 | Tool rows as compact bars ("Created /app/x.md >"); "3 Testing Agent messages"; "Agent has been paused" | Tool and file-write lines; subagent message count |
| Base44 | 90985d0c-3c8a-42b4-83e1-20d1797a9a14 | **Inline agent question card** with radio options, "Write your own answer", Skip/Send | Model for HITL cards in the stream |
| Base44 memory | b10ccc41-be58-4148-abe8-2502bf623490 | Memory tabs Knowledge/Working context/Memory log; type badges (Preference/Instruction/Fact); edit/delete; scope card | Memory tab structure |
| Cofounder | 2e10afc9-7866-492f-9e43-2813af44235f | "Send Message to Agent" delegation cards; "Routed to @Design…"; "2 agent updates · Review" notifier; cost/time meta | Subagent delegation line + Agents tab |
| Devin | 769b3371-28a2-43ea-8d0f-f9e4ae23e274 | Session list with status sublines; right Worklog tab; ● Live scrubber; "Devin went to sleep" | Thread status sublines; Audit "Live" toggle |
| Devin | b427b367-6210-4200-972d-ead195327f97 | Action stream ("Clicked at (511,387)", "Typed text"); right Desktop tab with live view; "Guide Devin while it works" | Device action receipts; composer stays usable while running |
| Cursor | 59358834-5391-4d2d-8a18-e80750431b58 | Agent list group/filter by Status (Running/Finished/Error…); status pills | Agents tab grouping and filters |
| Cursor | cd216d87-4761-46e2-87c4-6a26d97932a7 | Right tabs Setup/Secrets/Git/Desktop/Terminal; "Worked for 16m 44s"; inline video + screenshot gallery | Inspector tab model; inline asset gallery |
| Langdock | 579fb137-50fa-42d0-9222-4970f35648d5 | File chip in chat expands into a right document pane with skeleton while streaming | Files tab viewer + skeleton |
| Langdock | 80e91145-fa23-4920-82d9-08a0fcf3208c | Capability chips under the composer; "Get started 10% done" card | Starter grid; onboarding checklist |
| Plane AI | 8d800a40-7843-4810-95a1-9206c3289efc | "What can I do for you?" + context chip + model selector; Suggestions list | Empty state layout |
| Copy.ai | 7a691954-e171-4668-8329-5f8aa5b7c9fe | Starter prompts grouped by category with examples | Starter cards grouped by UGC loop |
| Notion AI | 7f5c8c5c-01c0-4b83-a505-cf3fe0bd49bc | "+" menu (files, mention, research-mode toggle) | Composer `+` menu |
| Jasper | 9ec0b65f-9bf7-4d0a-99a4-1578c442e66f | "Here's the plan" + step row; variant pager "2 of 2"; DRAFT badge | Script variants; draft badges |
| Semrush | d5fa9c73-0fbd-4b6e-9d7a-b7fa36e54a2c | **Vertical icon rail on the far right** switching right-panel tools | Inspector tab rail (9 tabs do not fit as text) |
| Fabric | 61d7d915-b6d3-4f7b-8544-ed2701fdce96 | Dark right panel; model chip; "Current file" context chip | Dark inspector styling; context chip |
| Gemini NotebookLM | 05def46a-970f-46b2-8bf0-e0e83c7dd49e | Sources / Chat / Studio three panes; numbered citation bubbles; "8 sources" | Inline citations; per-thread source count |
| Cohere | 4100675f-3440-45a6-8b20-de1a8c765568 | "Performing multistep reasoning using tools" with rationale + query; citation chips "+8" | Tool line descriptions; citation overflow chip |
| Perplexity | 4bb8f8e1-be0b-42b4-bc48-f8eab91c0182 | Answer/Links/Images tabs; "1 source" in action row | Sources button in footer |
| PlanetScale | d7448333-6400-49dd-b11f-e48e4e229200 | Audit row: actor + human sentence + mono event-key chip (`deploy_request.approved`); Add filter → Actor | Audit row anatomy and filters |
| Front | 0c2efddc-d2d9-4a17-b589-34523d08e1d8 | Filter chips (date, actor, event) + Export; "Last updated just now · Refresh" | Audit toolbar |
| Aboard | 8c5f9bca-6ac8-4fab-b216-6b058c3a7d21 | Field-level diff (attribute, new value, old value) | Edited-approval diff in history |
| Vanta / Gorgias | 41659ab7-5710-4abf-91ca-c6bf482c9b0b / 44a16fee-609a-40a5-afa0-f901dcacdfa8 | Export CSV; object links in rows | Audit export; target links |
| Luma | dfbf830e-9991-439b-863f-0dcca23db00c | All/Videos/Images filter; density toggle; "1080p 5s" hover meta | Assets tab filters and hover meta |
| Higgsfield / ElevenLabs / Artlist | 0a05b63a-f7da-4700-9527-96b607c87e6d / 64951be0-4326-4e94-af8a-076a2c34843d / 8a111127-e705-4203-9fb8-44d0da0cfe35 | Dark media grids; video badge; model + ratio chips | Asset card badges; generation metadata |
| Linear | 3b7417c7-551f-4935-890f-4788e4d8d334 | Connected accounts list (logo, purpose line, Connect ↗) | Connections page rows |
| Linear (dark) | 267d16a1-982b-4479-85b5-22294fdab01a | Near-black surfaces, low-contrast borders, property chips, "On track" | Dark token calibration |
| Apollo | e4e07047-5579-43e7-87f4-b61a25df1e46 | "Connected (4)" vs "Available (29)"; green-dot "Connected to X workspace"; Disconnect | Connections page sections |
| Rows | f7878183-4fbe-40a3-b174-1984e010b197 | Multiple credentials per provider; Default badge; usage meter | Model/provider status in settings |
| ChatGPT / Notion MCP | 8c5133dd-2437-4e5e-bdb1-867359c20dae / 9909017c-ef46-4364-a2b4-f9c1a656cfdc | Scope list before OAuth; "I trust this URL" checkbox | Pre-connect scope disclosure |
| Quicken | c5e6870f-21ee-458f-82a9-fb49ef245651 | "AI Agent … view your screen" consent dialog explaining what is recorded | **Device stream consent dialog** |
| Buffer | af871c1d-00d1-4c74-a4a4-87ae2e9455c8 | Channels in left nav with network badges; per-post red error + "Retry Now"; Queue/Drafts/Approvals/Sent tabs | Connected-accounts footer; publish error state |
| Assembly / Adobe Express | 37a2dca3-23c8-4789-8aed-90e4f5c1ab5f / f90999e7-48e7-4ef5-ad34-c028e0d6c551 | Post status pills; Draft/Scheduled/Published/Failed color dots | Asset approval/publish status colors |
| Podia / X | 9aa533e5-2042-4aaf-9470-097fef5f080c / 744d79ff-4e39-4676-8e2b-058ee762ed01 | Disconnected banner replacing the composer; "Failed, Try Again" under a bubble | Offline + send-failure states |
| Magnific / Vapi / Slite | e22e26e2-f813-4f1e-beda-43c9ecf26419 / 593d7acd-2e16-4365-bcd6-02ce52f48f3b / 2e1cc584-70e7-4698-b1da-bf1e6239b00f | ⌘K palette that doubles as an AI prompt; Recents + Actions with shortcuts; ↑↓/↵/Esc footer; ⌘/ shortcut sheet | Command palette + shortcuts dialog |
| Searchable *(flow)* | d9049949-2a6e-4ae7-a9bb-9b310edfbe1e | "Working for 8s" → "Thinking…" → result + Follow-ups | Streaming header copy |
| Replit *(flow)* | bee79141-e8ea-4852-873a-695974a82f85 | "Clear agent context" → confirm ("files will not be changed") → toast | Reset-thread-context confirm copy |
| Intercom *(section)* | 5f8b6b2d-c08c-4c54-9b2d-5c04a3f15ff5 | Conversation + right Details/Copilot tabs; "5 relevant sources found" | Inspector tabs beside the conversation |

**Patterns we deliberately reject:**
- **Modal approvals** (Dub, Asana). They block the stream and hide context, so we keep only consent and destructive confirms as modals.
- **Neon brand accents** (Higgsfield lime). Brand reference only.
- **Text tab bars for 9 inspector tabs.** They overflow at 360px.

---

## 3. Library evaluation and decision

| Option | License / health | Model | Fit for Ugecy | Verdict |
|---|---|---|---|---|
| **shadcn/ui + AI Elements patterns** (ui.shadcn.com/docs/ai-elements) | MIT (shadcn-ui/ui); first-party; active (Nov 2026 docs) | Copy-in code we own; `npx shadcn@latest add …`; Base UI (`-b base`), Radix or Aria | Native Tool / Subagent / Queue / Confirmation / Reasoning / Sources / Chat patterns on one `Trace` primitive; Vite template supported | **Adopt** |
| AI SDK Elements (elements.ai-sdk.dev) | **Deprecated end of Nov 2026** (site banner) | Registry `npx ai-elements@latest add` | Superseded by the shadcn row above | Reject |
| assistant-ui | MIT, ~9.9k★ (adminlte 2026 roundup); production users include LangChain | Runtime owns thread state (`@assistant-ui/react`); LangGraph via `useExternalStoreRuntime` (BaseMessage → ThreadMessageLike) | Strong, but a second state owner duplicates our snapshot store. The runtime is a heavy dependency for custom inspector views | Reject as core; fallback only |
| prompt-kit (ibelick) | MIT; shadcn registry | Copy-in | Overlaps with first-party shadcn patterns now | Reject (borrow ideas only) |
| langchain-ai/deep-agents-ui | MIT, ~1.7k★, last commit May 14 2026; Next.js app | Full app (ChatInterface, TasksFilesSidebar, SubAgentIndicator, ToolCallBox, ToolApprovalInterrupt, FileViewDialog) | Reference for Deep Agents state shapes and HITL decision payloads; Next.js, not Vite | Reference; port logic deliberately, with attribution |
| langchain-ai/agent-chat-ui | MIT, ~3.3k★, updated Nov 3 2026; Next.js | Full app; artifact side panel via `thread.meta.artifact` | Reference for message hiding (`langsmith:nostream`, `do-not-render-` prefix) and the auth/passthrough warning | Reference only |
| **@langchain/react `useStream`** | MIT (langgraphjs); official | Hook: `stream.messages`, `stream.values.todos`, `stream.subagents`, interrupts, submit/stop | Official Deep Agents frontend API. Wrapped behind our `AgentClient` adapter so a mock or Worker gateway can replace it | **Adopt (behind an adapter)** |
| **Streamdown** (vercel/streamdown) | Apache-2.0 (check `package.json` at install) | Drop-in react-markdown for streaming; plugins code/math/mermaid | Recommended by the shadcn Message pattern | **Adopt** |

### Decision

1. **UI foundation.** shadcn/ui, Base UI flavour, scaffolded with `npx shadcn@latest init -t vite -b base -n ugecy-web`. Agentic UI is built from the shadcn AI Elements patterns as copied code under `src/components/**`.
2. **Runtime dependencies stay small:**
   - `@base-ui/react`
   - `@shadcn/react` (needed by Message Scroller)
   - `react-resizable-panels` v4 (via `resizable`)
   - `streamdown`
   - `lucide-react`
   - `@langchain/react`
   - `zustand` (UI and thread store)
   - `react-router` (3 routes)
3. **Why copy-in over a runtime library.** The code is ours (an AGENTS.md requirement). There is no hidden state owner. The rule of 500 lines or fewer per file stays enforceable. When shadcn patterns change, we migrate with `npx shadcn@latest add --diff`.

### Platform notes for the spec

- **Vite setup.** `@tailwindcss/vite`, `@/*` alias and `@types/node` (shadcn Vite docs).
- **Cloudflare static assets.** Use `@cloudflare/vite-plugin` and set `[assets] not_found_handling = "single-page-application"` so client routes return `index.html` (developers.cloudflare.com/workers/framework-guides/web-apps/react/).
- **Sidebar.** `collapsible="icon"` with the built-in ⌘B (`SIDEBAR_KEYBOARD_SHORTCUT="b"`). One `SidebarProvider` holds a single open state, so **the right inspector must be a resizable panel, not a second shadcn Sidebar**.
- **Resizable is now react-resizable-panels v4.** Use `orientation` (not `direction`), string sizes (`"30%"`) and `panelRef` / `PanelImperativeHandle` for collapse and expand.
- **Toasts.** In the Base flavour, Toast is Base UI's (`toast.add/close/promise`); Sonner exists only in the Radix flavour. **Use `toast`** and do not add Sonner.
- **Tool status from `Trace`.** Status is shown with color and motion, so it must also be in the title ("Running …", "Failed to run …"). Shimmer stops under `prefers-reduced-motion`.

---

## 4. Open assumptions

1. **Backend surface.** The Python Deep Agents service exposes a LangGraph-compatible Agent Server API (threads, runs, stream, interrupts). Store-backed long-term memory, audit events, assets and accounts come from REST endpoints owned by the architecture researchers. The UI codes against the `AgentClient` interface in `UI-SPEC.md` §3 and ships with a mock adapter.
2. **Glasshand stream transport is unknown.** It could be WebRTC, HLS or MJPEG. The Device tab takes `streamUrl` + `streamKind` and degrades to action receipts only.
3. **Higgsfield job progress.** We assume polled status (`queued|generating|ready|failed`, optional `progress`).
4. **Mock mode signal.** The backend reports per-integration `mode: "live"|"mock"` on `/health`. The frontend's mock adapter also counts as mock mode.

---

## 5. References (retrieved 2026-11-07)

- shadcn AI Elements index: https://ui.shadcn.com/docs/ai-elements
- shadcn pattern sources (raw MDX), all under `https://raw.githubusercontent.com/shadcn-ui/ui/main/apps/v4/content/docs/`:
  - `ai-elements/base/{tool,subagent,confirmation,chat,queue,message}.mdx`
  - `components/base/{trace,message-scroller,sidebar,resizable,toast}.mdx`
  - `components/radix/sonner.mdx`
  - `installation/vite.mdx`
  - `(root)/{cli,theming}.mdx`
- AI SDK Elements deprecation banner: https://elements.ai-sdk.dev
- LangChain Deep Agents frontend:
  - https://docs.langchain.com/oss/javascript/deepagents/frontend/overview
  - …/frontend/todo-list
  - https://docs.langchain.com/oss/python/deepagents/frontend/subagent-streaming
  - https://docs.langchain.com/oss/python/deepagents/human-in-the-loop
- deep-agents-ui:
  - https://github.com/langchain-ai/deep-agents-ui
  - `src/app/components/ToolApprovalInterrupt.tsx`
- agent-chat-ui: https://github.com/langchain-ai/agent-chat-ui
- assistant-ui:
  - https://github.com/assistant-ui/assistant-ui
  - LangChain integration: https://docs.langchain.com/oss/python/langchain/frontend/integrations/assistant-ui
- prompt-kit and assistant-ui roundup: https://adminlte.io/blog/shadcn-ui-ai-chat-templates/
- Streamdown: https://github.com/vercel/streamdown, https://streamdown.ai
- Cloudflare SPA on Workers:
  - https://developers.cloudflare.com/workers/static-assets/
  - https://developers.cloudflare.com/workers/framework-guides/web-apps/react/
- Mobbin: the screen IDs in §2 (prefix `https://mobbin.com/screens/`; flows `https://mobbin.com/flows/<id>`; sections `https://mobbin.com/sites/sections/<id>`).
- Scratch notes: `/tmp/claude-0/-home-user-Ugcey/fa2c91df-9a17-597b-a1bb-bf83d8f15881/scratchpad/ui-research/{mobbin-notes.md,web-notes.md}`
