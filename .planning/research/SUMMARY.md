# Research summary and locked decisions

Synthesized on 2026-11-07 from 9 research files (8 parallel Opus researchers plus my own probes). Where the files disagree, the orchestrator's decision below wins. Detail lives in the individual files.

## Key findings
1. **Deep Agents 0.7.34** (`DEEPAGENTS.md`):
   - `write_todos` is opt-in, so add `TodoListMiddleware`.
   - Pass `ChatOpenAI` instances with `use_responses_api=False` and `profile.max_input_tokens`.
   - Always set `model` and `tools` on every subagent.
   - HITL payload and resume shape are verified, and subagent interrupts bubble to the root.
   - Stream with stable `astream(version="v2", subgraphs=True)`.
2. **Models** (`MODELS.md`, live spike, 145 calls):
   - All 4 Chinese models completed a real deep-agent run.
   - glm-5.3 is the fastest orchestrator. deepseek-v4.1-flash writes the best drafts. qwen3.8-27b handles vision. glm-4.7-flash needs thinking turned off.
   - Never use `tool_choice="required"`. Expect 20–48 s latency spikes.
3. **Cloudflare** (`CLOUDFLARE.md`):
   - Containers are GA. Use the `durable_object` scheduling policy with raw `ctx.container`.
   - Container egress runs with internet off, and outbound intercepts route `*.internal` hosts to a `WorkerEntrypoint`, so no secrets enter the container.
   - Paid models are capped at 20 rpm each, so a fallback model is required.
   - R2 and Access are not enabled on the account.
4. **My probe:** `env.AI.run()` / `/ai/run` already returns OpenAI `chat.completion` and `chat.completion.chunk` SSE for these models, plus one trailing `{"response":...}` line to drop. The `llm.internal` gateway can therefore use the AI binding with **no API token**.
5. **Integrations** (`INTEGRATIONS.md`):
   - Glasshand is real: rented physical iPhones, REST plus a WS JPEG stream that must be relayed, an OAuth device flow, and no file push.
   - Higgsfield is an async REST API with 84 workflows. Its Python SDK is unsafe (retries billable POSTs), so we write a thin httpx adapter.
   - `HF_API_KEY_SECRET` holds the combined `key:secret`.
   - Ponytail is `DietrichGebert/ponytail` (MIT), followed through its checklist.
6. **Features / competitors** (`FEATURES.md`, `COMPETITORS.md`):
   - Rendering is commoditized. The opening is the closed loop for owned accounts: research → original script → critic → generate → approve → publish → learn.
   - Platform app review is the critical path for live publishing.
   - AI-disclosure flags are mandatory.
   - FTC rules expose the "AI actor says I tried it" format.
7. **UI** (`UI-SPEC.md`, `UI-RESEARCH.md`): 3-pane shell, a 9-tab inspector, inline approval cards, a dark-first oklch theme, and three parallel frontend work packages.

## Locked decisions (override research where they differ)
| # | Decision | Why |
|---|---|---|
| L1 | **Custom typed SSE** (`packages/contracts`), built from `astream` v2. Not the LangChain streaming protocol 0.0.x and not `useAgent`. | Stable APIs only. Fewer experimental dependencies. One contract both sides own. |
| L2 | Runs execute as container background tasks with a per-run event buffer. Clients reattach through `GET /api/threads/:id/stream?since=`. | Survives browser disconnects without a ThreadDO event log (v2). |
| L3 | Persistence: `InMemorySaver` and `InMemoryStore` **write-through mirrors** over a KV (`state.internal` → AgentRuntime DO SQLite). The system of record is D1. | All on Cloudflare. Reuses LangGraph's own in-memory logic instead of a custom saver. |
| L4 | Keep the Radix-based shadcn components already scaffolded (not Base UI). Use Sonner for toasts. | Already installed and building; avoids churn. |
| L5 | One `AgentRuntime` DO per workspace (`getByName("default")`) owns the container. All `/api/*` except `/api/edge/*` is proxied to it. | Simplest routing for a single-operator v1. |
| L6 | Interim auth is a long random access key: `/api/edge/unlock?key=` sets an HttpOnly cookie and `/api/*` requires it. Access comes later. | Zero Trust isn't enabled; the URL must not be open to the world. |
| L7 | Publishing is **mock** in v1, with `ai_disclosure` required, approval-gated and audited. Scheduled publishes use Workflows `sleepUntil` → container `/jobs/publish`. | Real platform APIs need app review. |
| L8 | Research search uses Firecrawl when `FIRECRAWL_API_KEY` is set, otherwise a labelled sample-pattern library. `fetch_page` is always live (oEmbed plus Browser Run/HTTP). | No search key in the env. Fetching URLs the operator supplies is permitted. |
| L9 | Media: a Higgsfield httpx adapter, live when the `HF_KEY` Worker secret exists, else mock. Every `generate_media` call needs approval. | Paid side effect. |
| L10 | The device runs as a mock iPhone (Pillow screens) in v1. The Glasshand live provider uses REST only, with the stream relay in v2. | No Glasshand rental or token available. |
| L11 | The edge layer is TypeScript, as an approved exception to the Python rule. All domain logic stays in Python. | The Containers DO API is TS-only. |
| L12 | Never add automated account creation, warming, or multi-account evasion. | Platform abuse and detection evasion (PROJECT.md out of scope). |
