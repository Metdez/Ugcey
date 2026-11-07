# LangChain Deep Agents (Python): source-verified brief for Ugecy

Researched 2026-11-07. I read the source of `deepagents==0.7.34` and `langchain==1.4.9` (wheels extracted to scratch). Every snippet marked **[ran]** was executed in a uv venv with a scripted fake chat model (`deepagents 0.7.34`, `langchain 1.4.9`, `langchain-core 1.7.6`, `langgraph 1.2.20`, `langgraph-checkpoint 4.3.1`, `langchain-openai 1.7.4`, `langgraph-checkpoint-postgres 3.2.0`, `langgraph-checkpoint-sqlite 3.1.3`).

## 0. TL;DR (the findings that change decisions)

1. **`write_todos` is NOT in the default stack anymore** (it was removed in 0.7.0, per the CHANGELOG). Add `TodoListMiddleware()` yourself, or `state["todos"]` never exists and the UI todo sidebar stays empty. The official docs say the same: "Task planning is opt-in." [ran]
2. **Pass a `ChatOpenAI` instance, not a model string.** An `"openai:..."` string goes through a built-in ProviderProfile that forces `use_responses_api=True`, and the Workers AI endpoint is chat-completions. A pre-built instance skips the provider profile, so set `use_responses_api=False` on it. [ran]
3. **Set `profile={"max_input_tokens": N}` on every ChatOpenAI.** Without it, summarization falls back to a 170k-token trigger, which overflows smaller context windows. With it, the trigger moves to 85% of the window. [ran]
4. **Never call `create_deep_agent` without `model`.** It falls back to `claude-sonnet-4-6`. Subagents inherit the parent's model unless they set `model`. `langchain-anthropic` is a hard install dependency, but it is only imported when a request actually targets an Anthropic model.
5. Backend factories (`backend=lambda rt: StateBackend(rt)`) were **removed in 0.7.0**. Pass instances, e.g. `StateBackend()` and `StoreBackend(namespace=lambda rt: (...))`.
6. HITL payloads and the resume shape are stable and verified. Subagent interrupts **bubble up to the root** with the same interrupt id, so you resume at the root. [ran]
7. Streaming has two layers: stable `astream(..., version="v2")` parts (`{"type","ns","data"}`), and a new **experimental** `astream_events(version="v3")` protocol with `stream.subagents` handles and `lifecycle` events. [ran]
8. **Ephemeral disk means no SQLite.** Use Postgres (`AsyncPostgresSaver` + `AsyncPostgresStore`, both in one package) on Neon or Supabase. A Cloudflare D1 checkpointer exists (`langgraph-checkpoint-cloudflare-d1` 0.1.6, REST API), but it lacks the optimized delta-history read and ships no Store. See §5.

## 1. Install (pins verified on PyPI 2026-11-07)

```bash
uv add "deepagents==0.7.34" "langchain==1.4.9" "langgraph==1.2.20" "langchain-openai==1.7.4" \
       "langgraph-checkpoint-postgres==3.2.0" "psycopg[binary,pool]"   # prod persistence
# deepagents pulls in: langchain-core>=1.7.6, langchain-anthropic, langchain-google-genai, langsmith, wcmatch
```

## 2. `create_deep_agent` (deepagents/graph.py, 0.7.34)

```python
def create_deep_agent(
    model: str | BaseChatModel | None = None,                 # None => deprecated Claude default. ALWAYS pass.
    tools: Sequence[BaseTool | Callable | dict] | None = None, # additive to built-ins; also inherited by subagents w/o own `tools`
    *, system_prompt: str | SystemMessage | None = None,       # USER part; final = USER + profile BASE + profile SUFFIX
    middleware: Sequence[AgentMiddleware] = (),                # spliced after core stack, before tail; same .name => replaces in place
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,       # skill source dirs in backend paths, e.g. ["/skills/"]; adds SkillsMiddleware (main + GP)
    memory: list[str] | None = None,       # AGENTS.md paths, e.g. ["/memories/AGENTS.md"]; adds MemoryMiddleware (main only)
    permissions: list[FilesystemPermission] | None = None,     # fs rules allow|deny|interrupt; inherited by subagents
    backend: BackendProtocol | None = None,                    # default StateBackend()
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,  # HITL; inherited by declarative subagents
    response_format: ResponseFormat | type | dict | None = None,      # structured output -> state["structured_response"]
    state_schema: type[DeepAgentState] | None = None,          # must subclass DeepAgentState (keeps DeltaChannel on messages)
    context_schema: type | None = None,                        # immutable run context: astream(..., context=Ctx(...))
    checkpointer: Checkpointer | None = None,                  # REQUIRED for HITL + threads
    store: BaseStore | None = None,                            # REQUIRED for StoreBackend routes
    debug: bool = False, name: str | None = None,              # name -> metadata lc_agent_name
    cache: BaseCache | None = None,                            # LangGraph node cache
) -> CompiledStateGraph   # .with_config({"recursion_limit": 9_999, "metadata": {...}})
```

## 3. Default middleware stack and tools (assembly order in graph.py)

**Main agent:** `FilesystemMiddleware` → `SubAgentMiddleware` (the `task` tool) → `_ParentNotifierMiddleware` (for async-subagent callbacks) → `SummarizationMiddleware` (deepagents variant) → `PatchToolCallsMiddleware` (adds dangling-call ToolMessages) → `AsyncSubAgentMiddleware` (only if async specs) → **your `middleware=`** → harness-profile `extra_middleware` → `SkillsMiddleware` (if `skills`) → `AnthropicPromptCachingMiddleware` (lazy stand-in, no-op for non-Anthropic) → Bedrock/Fireworks caching (only if those packages are installed) → `MemoryMiddleware` (if `memory`) → `HumanInTheLoopMiddleware` (if `interrupt_on` or interrupt permissions) → `UnsupportedContentMiddleware` → `ModelRefusalMiddleware` → `_ToolExclusionMiddleware` (if the profile excludes tools). `FilesystemMiddleware` and `SubAgentMiddleware` are protected and a profile cannot exclude them.

**Declarative subagent stack:** Filesystem → Summarization → PatchToolCalls → profile extras → Skills (if the spec has `skills`) → prompt caching → ModelRefusal, then the spec's `middleware`, then `HumanInTheLoopMiddleware` (if `interrupt_on`) and `UnsupportedContentMiddleware`.

**Built-in tools:**

| Tool | Notes |
|---|---|
| `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep` | Always present. `grep` matches **literal** strings, not regex. `read_file` defaults to 100 lines, paginated. |
| `delete` | New in 0.7.0. Only exposed when the backend implements `delete`. |
| `execute` | Only when the backend is a `SandboxBackendProtocol`. Otherwise it is filtered out. |
| `task(description, subagent_type)` | Present when at least one sync subagent exists (GP is auto-added). Unknown argument keys are rejected. |
| `write_todos` | **Only if you add `TodoListMiddleware()`.** Each todo is `{"content": str, "status": "pending"\|"in_progress"\|"completed"}`. |
| `start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks` | Only with `AsyncSubAgent` specs. |

To restrict the filesystem tools, pass `FilesystemMiddleware(backend=..., tools=["ls","read_file","glob","grep"])`. It replaces the default by name, and `read_file` is mandatory.

**Other useful FilesystemMiddleware defaults:**
- A tool result over 20k tokens is evicted to a file and replaced by a head/tail preview.
- A HumanMessage over 50k tokens gets the same treatment.

**Anthropic-specific pieces and how they behave with GLM, DeepSeek or Qwen:**
- The prompt caching stand-in calls through unchanged for non-Anthropic models. It never even imports the `anthropic` SDK.
- `MemoryMiddleware(add_cache_control=True)` adds the cache marker only for ChatAnthropic.
- The built-in harness profiles exist for `anthropic:claude-*`, `openai:gpt-5.x-codex` and Nemotron 3 Ultra. **None matches a `ChatOpenAI` pointed at Workers AI** (provider "openai", id "@cf/...", empty profile, no prompt suffix). [ran]
- The OpenAI ProviderProfile (`use_responses_api=True`) applies only to `"openai:..."` strings.
- Summarization uses the agent's own model. Defaults:
  - With `profile.max_input_tokens` set: trigger at 0.85 of the window, keep 0.10.
  - Without it: trigger at 170k tokens, keep the last 6 messages.
  - Evicted history is written to `/conversation_history/{session}.md` on the backend.

## 4. Subagents (middleware/subagents.py)

```python
class SubAgent(TypedDict):          # name, description required
    name: str; description: str     # description = routing signal for the orchestrator
    tools: NotRequired[Sequence[BaseTool | Callable | dict]]  # OMIT => inherits parent `tools`!  Always set explicitly.
    model: NotRequired[str | BaseChatModel]                   # default: parent model
    middleware: NotRequired[list[AgentMiddleware]]            # appended after the subagent base stack
    interrupt_on: NotRequired[dict[str, bool | InterruptOnConfig]]  # overrides inherited top-level interrupt_on
    skills: NotRequired[list[str]]                            # NOT inherited (except mode="fork")
    permissions: NotRequired[list[FilesystemPermission]]      # replaces parent's rules entirely
    response_format: NotRequired[ResponseFormat | type | dict]# structured_response -> JSON ToolMessage to parent
    system_prompt: NotRequired[str]                           # empty if omitted
    mode: NotRequired[Literal["isolated", "fork"]]            # fork (beta): inherits parent conversation + prompt
class CompiledSubAgent(TypedDict):  # name, description, runnable (state must have "messages"), mode?
    ...                             # does NOT inherit interrupt_on/state_schema; bring your own HITL
class AsyncSubAgent(TypedDict):     # name, description, graph_id, url?, headers?, webhook?, update_strategy?
    ...                             # background runs on an Agent-Protocol/LangGraph server via langgraph_sdk
```

- **General-purpose subagent:**
  - It is auto-added (`"general-purpose"`) with the main model, the main `tools` and `skills`, and the default prompt.
  - To override it, pass your own spec named `"general-purpose"`.
  - To disable it, register a `HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False))` under the model's provider key.
- **How results flow back:**
  - The parent's `task` call invokes the subagent graph with filtered parent state. Excluded keys: `messages`, `todos`, `structured_response`, `skills_metadata` and private keys.
  - The subagent receives `messages=[HumanMessage(description)]`.
  - The parent gets back a `Command(update=...)` with **one ToolMessage**: `structured_response` as JSON, otherwise the last non-empty AI text.
  - All other changed state keys are merged into the parent. **`files` written by a subagent show up in the parent's `files`.** [ran]
  - Subagent `todos` are not returned.
- **Parallelism:** the model can issue several `task` calls in one turn, and they run concurrently. Give any custom state key a reducer, or parallel writes raise `InvalidUpdateError`.
- **Per-call structured output:** set `config["configurable"]["__deepagents_subagent_response_format"]`.
- **Async/background:** `AsyncSubAgent` needs a reachable Agent Protocol server (LangGraph Platform or self-hosted `langgraph` API). Async local ASGI transport (no `url`) only works via `ainvoke`. **Not viable for Ugecy v1** on Cloudflare Containers. Use Cloudflare Queues jobs with polling tools instead (§11).
- **Subagents carry their name in metadata:** the subagent's `lc_agent_name` equals the spec `name`, and `lc_subagent_tool_call_id` equals the parent's `task` tool_call id.

## 5. Backends and persistence

**BackendProtocol** (deepagents/backends/protocol.py). Sync methods are required. Async defaults wrap them in `asyncio.to_thread`, so override with real async for HTTP.

```python
class BackendProtocol(abc.ABC):
    def ls(self, path: str) -> LsResult                                   # LsResult(error|None, entries=[FileInfo{path,is_dir?,size?,modified_at?}])
    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult  # raw text window; set start_line/end_line
    def grep(self, pattern: str, path: str|None=None, glob: str|None=None, *, max_count: int|None=None) -> GrepResult
    def glob(self, pattern: str, path: str|None=None) -> GlobResult
    def write(self, file_path: str, content: str) -> WriteResult          # WriteResult(error|None, path)
    def edit(self, file_path, old_string, new_string, replace_all=False) -> EditResult  # (error, path, occurrences)
    def delete(self, file_path: str) -> DeleteResult                      # optional (enables `delete` tool)
    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]
    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]  # used by Memory/Skills loaders!
    # + als/aread/agrep/aglob/awrite/aedit/adelete/aupload_files/adownload_files
class SandboxBackendProtocol(BackendProtocol):  # adds .id and execute(command, *, timeout=None) -> ExecuteResponse
FileData = {"content": str, "encoding": "utf-8"|"base64", "created_at"?: str, "modified_at"?: str}
```

**Built-in backends** (import from `deepagents.backends`):

| Backend | What it does |
|---|---|
| `StateBackend()` | Lives in the `files` state key (a DeltaChannel). Checkpointed per thread. Seed it with `invoke({"files": {...}})`. |
| `StoreBackend(namespace=lambda rt: tuple, store=None)` | Cross-thread storage. Namespace parts are restricted to `[A-Za-z0-9-_.@+:~]`. Item key = path after route stripping, value = FileData dict. |
| `FilesystemBackend(root_dir=...)` | Local disk. Do not use on ephemeral disk. |
| `LocalShellBackend` | Local disk plus `execute`. Dev only. |
| `CompositeBackend(default, routes={"/memories/": ...}, artifacts_root="/")` | Routes by path prefix, longest match first, and strips the prefix: `/memories/brand.md` is stored as key `/brand.md`. [ran] |
| `ContextHubBackend` | LangSmith Hub. |
| `LangSmithSandbox` | LangSmith sandbox. |

Partner sandbox packages: `langchain-daytona` 0.0.9, `langchain-modal` 0.0.7, `langchain-runloop` 0.0.7, `langchain-quickjs` 0.3.12. Ugecy does not need `execute` in v1.

**Custom backend (e.g. Cloudflare D1 or KV behind a Worker).**
- **Preferred:** don't write a BackendProtocol. Implement a `langgraph.store.base.BaseStore` (`batch(ops)` and `abatch(ops)` handling `GetOp`, `PutOp`, `SearchOp`, `ListNamespacesOp`) over HTTP, and reuse `StoreBackend`. You get filesystem semantics, grep and glob for free.
- **If you do subclass `BackendProtocol`:** reuse `deepagents.backends.utils` helpers: `create_file_data(content)`, `update_file_data(fd, content)`, `slice_read_response(fd, offset, limit)`, `perform_string_replacement(content, old, new, replace_all) -> (new, n) | error_str`, `grep_matches_from_files(...)`, `_glob_search_files(...)`.
- Implement `download_files` too (Memory and Skills depend on it). Add async methods using `httpx.AsyncClient`.

**Checkpointers and stores (LangGraph):**

| Kind | Import path | Package | Ugecy use |
|---|---|---|---|
| Memory | `langgraph.checkpoint.memory.InMemorySaver`, `langgraph.store.memory.InMemoryStore` | langgraph | tests |
| SQLite | `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver`, `langgraph.store.sqlite.AsyncSqliteStore` | `langgraph-checkpoint-sqlite` 3.1.3 | local dev only (data lost on container restart) |
| Postgres | `langgraph.checkpoint.postgres.aio.AsyncPostgresSaver`, `langgraph.store.postgres.AsyncPostgresStore` | `langgraph-checkpoint-postgres` 3.2.0 | **prod** (implements optimized `aget_delta_channel_history`) |
| Cloudflare D1 | `langgraph_checkpoint_cloudflare_d1.AsyncCloudflareD1Saver(account_id, database_id, api_token)` | `langgraph-checkpoint-cloudflare-d1` 0.1.6 (cloudflare/langchain-cloudflare) | fallback. No delta-history override, so the base fallback walks up to ~50 parent checkpoints, each a REST call. No Store. |

`AsyncPostgresSaver.from_conn_string(conn, *, pipeline=False, serde=None)` and `AsyncPostgresStore.from_conn_string(conn, *, pool_config=None, index=None, ttl=None)` are async context managers. Call `await x.setup()` once.

## 6. Skills and memory

**Skills** (Agent Skills spec, agentskills.io):
- Each skill is a directory `<source>/<name>/SKILL.md`.
- Frontmatter fields:
  - `name`: required, 1-64 characters of `a-z0-9-`, and must equal the directory name.
  - `description`: required, at most 1024 characters. Write it as "what it does + when to use it".
  - Optional: `license`, `compatibility`, `metadata` (dict), `allowed-tools`.
- Loading is progressive disclosure:
  - Only name, description and path go into the system prompt.
  - The model then calls `read_file(path, limit=1000)`.
  - Skills are loaded once per thread into `skills_metadata`. Set it to `None` to reload.
  - `pinned_skills: ["name"]` on input force-injects a skill body as a HumanMessage (good for slash-commands).
- **Skill tools:** `metadata.include_tools: "tool_a tool_b"` keeps tools hidden until the skill is read. `skills=` builds SkillsMiddleware without tools, so pass your own `SkillsMiddleware(backend=..., sources=[...], tools=[...])` in `middleware=` (it replaces the default by name). Alternatively, mark agent tools `extras={"defer_loading": True}`. This is the right fit for publish and device tools.
- Later sources override earlier ones on name clashes.
- Skills load from **any backend route**. A `/skills/` route to a StoreBackend works: the skill name and the AGENTS.md text both appeared in the system prompt. [ran]

**Memory** (`MemoryMiddleware`, AGENTS.md spec):
- Files are concatenated into `<agent_memory>` in the system prompt, plus guidelines telling the model to persist learnings via `edit_file`.
- HTML comments are stripped.
- Memory is loaded **once per thread** (cached in private `memory_contents`).
- A missing file is silently skipped.
- Only the main agent gets memory. Forked subagents also get it.
- Use for: brand voice, operator preferences, learned hook playbook. Do not store credentials (the prompt says so too).

## 7. Human-in-the-loop (langchain 1.4.9 `HumanInTheLoopMiddleware`, default `interrupt_mode="batched"`)

```python
interrupt_on = {
  "publish_post": {"allowed_decisions": ["approve", "edit", "reject"], "description": "Publish to connected account"},
  "glasshand_action": {"allowed_decisions": ["approve", "reject"],
                       "when": lambda req: req.tool_call["args"]["action"] != "screenshot"},  # predicate must be deterministic
  "draft_note": True,     # True = approve|edit|reject|respond ; False = auto-approve
}
# also: permissions=[FilesystemPermission(operations=["write"], paths=["/memories/**"], mode="interrupt")]
```

**Interrupt value the client sees** [ran]. It arrives in `updates` as `{"__interrupt__": (Interrupt(id=..., value=...),)}` and in `state.interrupts`:

```json
{"action_requests": [{"name": "publish_post", "args": {"account_id": "acct_1", "caption": "hi"},
                      "description": "Tool execution requires approval\n\nTool: publish_post\nArgs: {...}"}],
 "review_configs": [{"action_name": "publish_post", "allowed_decisions": ["approve", "edit", "reject"]}]}
```

**Resume** [ran]. Decisions are positional, one per `action_requests` entry:

```python
Command(resume={"decisions": [{"type": "approve"}]})
Command(resume={"decisions": [{"type": "edit", "edited_action": {"name": "publish_post", "args": {...}}}]})
Command(resume={"decisions": [{"type": "reject", "message": "Caption needs #ad disclosure"}]})
Command(resume={"decisions": [{"type": "respond", "message": "..."}]})   # human answers instead of tool
# several concurrent interrupts (e.g. parallel subagents): Command(resume={interrupt.id: {"decisions": [...]}, ...})
```

**Interrupts and resume inside subagents:**
- A subagent's interrupt appears at ns `('tools:<task_id>',)` **and** again at the root with the same id.
- `aget_state(cfg).interrupts` lists it, and `Command(resume=...)` at the root continues the subagent. [ran]
- **Edits:** a tool call the reviewer edited gets an "edited by human" notice prepended to its ToolMessage.
- **per_call mode:** `interrupt_mode="per_call"` (one `{"type": "tool_approval", ...}` interrupt per call, resumed by interrupt id) is planned to become the default in the next major. `create_deep_agent(interrupt_on=...)` still builds batched; to get per_call, pass your own `HumanInTheLoopMiddleware(...)` in `middleware=`.
- **Rule:** the checkpointer is required. A reject produces an error ToolMessage, and the model is told not to retry.

## 8. Streaming

**Stable (recommended baseline):**

```python
async for part in agent.astream(inp, cfg, context=ctx, version="v2", subgraphs=True,
                                 stream_mode=["messages", "updates", "custom", "values"]):
    part["type"], part["ns"], part["data"]
```

- **Part shapes:**
  - `messages`: `data = (AIMessageChunk | ToolMessage, metadata)`.
  - `updates`: `data = {node_name: update}` or `{"__interrupt__": (...)}`.
  - `custom`: `data` = whatever the tool wrote.
  - `values`: `data` = full state, plus `part["interrupts"]`.
- **Identifying the source:**
  - `ns == ()` means the orchestrator. `ns == ("tools:<task_id>",)` means a subagent.
  - `metadata["lc_agent_name"]` is `"research-analyst"` (the spec name; the orchestrator's comes from `name=`).
  - `metadata["lc_subagent_tool_call_id"]` links back to the parent `task` call. Other keys: `langgraph_node` (`model`|`tools`), `langgraph_step`, `thread_id`, `ls_provider`.
- **v1 shapes** (without `version`): with a mode list and `subgraphs=True`, items are `(namespace, mode, data)`. With a mode list only, `(mode, data)`.
- **Todos and files for the UI:** read `values` parts at `ns == ()` (`data["todos"]`, `data["files"]` = `{path: FileData}`), or call `await agent.aget_state(cfg)` and use `.values`. `/memories/` and `/skills/` are **not** in `files` because they live in the Store. List them via `store.asearch(ns)`. [ran]
- **Custom progress:** `from langgraph.config import get_stream_writer; get_stream_writer()({"type": "progress", ...})` inside any tool or node. It surfaces as a `custom` part with the subagent's `ns`. [ran]
- **Experimental v3 protocol** (`LangChainBetaWarning`): `stream = await agent.astream_events(inp, cfg, version="v3")`.
  - Projections: `stream.messages`, `stream.tool_calls`, `stream.subagents`. Each subagent handle has `.name`, `.path`, `.status`, `.messages`, `.tool_calls` and `.output`.
  - Raw events are `{"method": "values"|"messages"|"tools"|"lifecycle", "params": {"namespace", "timestamp", "data"}}`.
  - A lifecycle event looks like `{"event": "started", "graph_name": "research-analyst", "cause": {"type": "toolCall", "tool_call_id": "m1"}}`. [ran]
  - The frontend `@langchain/react` `useStream` (successor to the archived `deep-agents-ui`) exposes `stream.values.todos` and `stream.subagents`, and accepts a custom `transport` for non-LangGraph-Server backends.
  - Owned by the frontend researcher. Recommendation: the backend emits SSE from v2 parts first and adds v3 behind a flag.

## 9. Non-Anthropic models (Cloudflare Workers AI OpenAI-compatible endpoint)

```python
ChatOpenAI(model="@cf/zai-org/glm-4.7-flash",            # exact @cf ids: confirm with models researcher
           base_url=f"https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/v1", api_key=CF_TOKEN,
           use_responses_api=False, temperature=0.3, timeout=120, max_retries=2,
           profile={"max_input_tokens": 131072, "image_inputs": False})   # image_inputs False => images replaced, not 400
```

- **Instance vs string:** an instance skips ProviderProfile and has no matching HarnessProfile. A string `"openai:..."` routes through `init_chat_model` with Responses API on. For other providers' strings, harness profiles may add prompt suffixes and middleware.
- **Profiles for your own models:** register them with `register_harness_profile("openai:@cf/zai-org/glm-5.3", HarnessProfile(system_prompt_suffix=..., extra_middleware=[...], tool_description_overrides={...}))`. Key format is `provider:identifier` as reported by `_get_ls_params()`.
- **Known open-model issues (community and source evidence):**
  - Models narrate instead of calling tools. GLM, Qwen and DeepSeek are the default targets of Hermes' "tool_use_enforcement".
  - The loop stops after the first tool call (copilotkit/opengenerativeui#87, GLM-5).
  - XML or text tool calls appear in content (`<function=..>`, `<tool_call>`) and need parsers (vLLM ships a dedicated `glm47` parser).
  - `<think>` blocks leak into output.
  - DeepSeek V3.2 native function calling fails (open-webui docs).
  - Invented `task` argument keys are now rejected with a validation error that goes back to the model.
- **Reusable mitigations in deepagents source:** `profiles/harness/_nvidia_nemotron_3_ultra.py` contains `NemotronTextToolCallParser`, `NemotronReasoningTagCleanupMiddleware`, `ModelRateLimitRetryMiddleware` (429 backoff), `FinalAnswerGuardMiddleware` and `ToolRetryMiddleware` on filesystem tools. These are private classes. Copy and adapt them into `ugecy/agents/model_compat.py` rather than importing them.
- **Recursion limit:**
  - The agent is bound to `recursion_limit=9_999`, and so is each `create_agent` subagent. The langgraph default is 10007 (env `LANGGRAPH_DEFAULT_RECURSION_LIMIT`).
  - That is effectively unbounded, so cap cost with `ModelCallLimitMiddleware(run_limit=60, exit_behavior="end")` and `ToolCallLimitMiddleware(tool_name="higgsfield_generate", run_limit=4)`, and/or `config={"recursion_limit": 400}`.
- **Retries and fallback:** use `ModelRetryMiddleware(max_retries=2, backoff_factor=2.0)` and `ModelFallbackMiddleware(glm_flash, qwen)` for provider errors.

## 10. Ecosystem

- **langchain-ai/deepagents** (31.1k★, 4.4k forks, MIT, pushed 2026-11-07).
  - `libs/`: `deepagents` (SDK); `code` (**Deep Agents Code**, a terminal coding agent, PyPI `deepagents-code` 0.1.88, successor to `deepagents-cli` 0.3.0); `acp` (Agent Client Protocol server for editors, `deepagents-acp` 0.0.13); `talon` (local runtime host for long-running agents, channel adapters, cron, `deepagents-talon` 0.0.9, experimental); `evals`; `partners/{daytona, modal, quickjs, runloop, vercel}`.
  - `examples/`: `async-subagent-server`, `better-harness`, **`content-builder-agent`** (AGENTS.md brand voice + `skills/blog-post`, `skills/social-media` + `subagents.yaml` + image tool; closest analogue to Ugecy), `deep_research`, `deploy-coding-agent`, `deploy-content-writer`, `deploy-gtm-agent`, `deploy-mcp-docs-agent`, `downloading_agents`, `llm-wiki`, `nvidia_deep_agent`, `ralph_mode`, `rubric_middleware`, `talon`, `text-to-sql-agent`.
- **langchain-ai/deep-agents-ui** (1.7k★, MIT, **archived 2026-06-28**). It was a Next.js app on `useStream` that rendered `todos`, `files`, `task` subagent cards and approvals. Its successor is `@langchain/react` `useStream` plus the frontend bundled with `deepagent deploy` (deepagents#2940). That bundle has subagent cards, per-tool renderers (files, search, think, todos), `filterSubagentMessages` and `getSubagentsByMessage`.
- **Other official:** `deepagentsjs` (1.6k★), `deep-agent-template` (researcher + critic subagents, HITL on `execute`/`write_file`), `design-agent` (589★, Apache-2.0: on-brand stills, decks and motion graphics on Deep Agents with async subagents, a sandbox, Context Hub skills, a router skill over 35 skills, and Slack approvals).
- **Community** (GitHub topic `deepagents`, stars as of 2026-11-07):

| Repo | ★ | License | Reusable for Ugecy |
|---|---|---|---|
| xerrors/Yuxi | 7.6k | MIT | Multi-tenant FastAPI + deepagents platform: per-user sandboxes, Skills/MCP permissioning, approval mode for writes |
| datawhalechina/deepagents-in-action | 2.9k | none stated | Chinese course; patterns for Chinese models and sandboxes |
| Haohao-end/openagent | 748 | MIT | DeepSeek + deepagents vertical-agent harness, Celery jobs, Postgres |
| pizza-bot-app/pizza-bot | 545 | Apache-2.0 | Local-first **inbox UX for long-running agents with HITL** (approval queue pattern) |
| jd-opensource/JoySafeter | 315 | Apache-2.0 | Agent teams with tracing, sandboxing and memory |
| didilili/deepsearch-agents | 313 | none stated | **FastAPI + WebSocket streaming** of deepagents to a web UI |
| emma-sue/AegisOps | 302 | none stated | Evidence tickets plus **approval-gated actions** with LangGraph and deepagents |

**Worth copying:**
- content-builder-agent's file-defined agent (AGENTS.md + skills + `subagents.yaml` loader).
- The deepagents#2940 UI's per-tool renderers and subagent cards.
- pizza-bot's approval inbox.
- The Nemotron compatibility middleware.
- `RubricMiddleware(model=..., max_iterations=3)`: invoke with `{"rubric": "..."}` and a grader loops until it returns `satisfied`. Use it for script QA.

## 11. Recommendation for Ugecy

**Topology.** One orchestrator plus declarative subagents. All subagents are `mode="isolated"` with explicit `tools` and an explicit `model`. Each subagent is one module (`ugecy/agents/<name>.py`) exporting a `SubAgent` spec and its tools, so it can be enabled or disabled through config.

| Agent (name) | Model (env-configurable) | Tools | Writes | HITL |
|---|---|---|---|---|
| orchestrator | glm-5.3 | `write_todos`, fs, `task`, `request_operator_input` (respond-only) | `/plans/` | `/memories/**` writes (interrupt) |
| research-analyst | deepseek-v4.1-flash | `search_public_ugc`, `get_post_details`, `get_transcript`, `firecrawl_scrape` (permitted sources only) | `/research/*.md` with URLs | none (read-only external) |
| creative-strategist | glm-5.3 | none (reads `/research`) + `RubricMiddleware` for originality and hook rules | `/briefs/`, `/scripts/` | none |
| compliance-reviewer (new) | qwen3.8-27b | `check_policy(platform, text)`, `check_similarity(script, sources)` | `/reviews/` | none (gates the next step) |
| production-coordinator | glm-4.7-flash | `higgsfield_generate`, `higgsfield_job_status`, `register_asset` (R2) | `/assets/manifest.json` | `higgsfield_generate` (cost: approve/edit/reject) |
| publishing-coordinator | glm-4.7-flash | `list_connected_accounts`, `schedule_post`, `publish_post`, `get_post_status` | `/publishing/log.md` | `schedule_post`, `publish_post` (approve/edit/reject) |
| device-operator | glm-4.7-flash | `glasshand_start_session`, `glasshand_screenshot`, `glasshand_action` | `/device/receipts/` | `glasshand_start_session` always; `glasshand_action` via a `when` predicate (all mutating actions) |
| analytics-analyst (new) | deepseek-v4.1-flash | `get_post_metrics`, `get_account_insights` | `/analytics/` and proposes edits to the `/memories/playbook.md` (interrupt) | none |
| general-purpose (override) | glm-4.7-flash | `[]` (fs only) | n/a | none |

**Guardrails:**
- The orchestrator has `tools=[]`, so the auto general-purpose subagent cannot inherit side-effect tools. All side-effect tools live only in their coordinator.
- Tools that run long jobs (Higgsfield, Glasshand) return a `job_id` immediately and are polled by a status tool. The real work runs in Cloudflare Queues or Workflows, not inside the graph.

**Audit:** add an `AuditMiddleware(AgentMiddleware)` to `middleware=` and to every subagent spec.
- `awrap_tool_call(request, handler)` logs `request.tool_call` (name, args, id), `request.runtime.context`, the result status and duration to the audit table.
- HITL decisions are logged from the resume endpoint.
- `ToolCallRequest` fields: `tool_call`, `tool`, `state`, `runtime`.

**Memory design:**

| Layer | Where | Contents |
|---|---|---|
| Thread (one campaign = one `thread_id`) | `StateBackend` → checkpointed `files` | research, briefs, scripts, reviews, manifests. **No binary media in state.** Assets live in R2 and are referenced by id/URL. |
| Long-term | `/memories/` → `StoreBackend(namespace=lambda rt: (rt.context.workspace_id, "memories"))`, plus `memory=["/memories/AGENTS.md"]` | brand voice, operator preferences, learned playbook. Writes are approval-gated. |
| Playbooks | `/skills/` → `StoreBackend(namespace=("global","skills"))` (plus optional per-workspace overrides as a second source) | Seeded from `ugecy/skills/*/SKILL.md` at deploy, e.g. `ugc-hook-extraction`, `short-form-script-format`, `higgsfield-prompting`, `platform-publishing-checklist`, `ftc-disclosure`. Agent writes are denied by permissions. Use `metadata.include_tools` to reveal `publish_post` and `glasshand_action` only after the relevant skill is read. |

**Persistence on an ephemeral-disk container:**
- Use **Postgres** (Neon or Supabase, reached directly over TLS from Cloudflare Containers): `AsyncPostgresSaver` (threads, HITL) and `AsyncPostgresStore` (memories, skills), sharing one `psycopg_pool.AsyncConnectionPool`.
- D1 stays the system of record for app data (campaigns, audit, accounts).
- `AsyncCloudflareD1Saver` is a fallback only after a latency test.
- **Never** use in-container SQLite in prod.
- Run `durability="sync"` before external side effects. The default is `"async"`.

**Minimal verified skeleton** (71 lines [ran]). Build with real `ChatOpenAI` objects, then run end-to-end with a fake model. The run confirmed:
- `/skills/` writes are denied.
- `/memories/` writes interrupt, and approving them persists to the Store.
- The research subagent's custom events stream.
- The skill and AGENTS.md content appear in the system prompt.

```python
"""Ugecy orchestrator skeleton. deepagents==0.7.34 langchain==1.4.9 langgraph==1.2.20 langchain-openai==1.7.4"""
import os
from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain.agents.middleware import ModelRetryMiddleware, TodoListMiddleware
from langchain.tools import ToolRuntime, tool
from langgraph.config import get_stream_writer
from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

CF = f"https://api.cloudflare.com/client/v4/accounts/{os.getenv('CF_ACCOUNT_ID', 'ACC')}/ai/v1"

def llm(model: str, ctx: int = 131_072) -> ChatOpenAI:  # profile => summarization triggers at 85% of ctx
    return ChatOpenAI(model=model, base_url=CF, api_key=os.getenv("CF_AI_TOKEN", "x"), use_responses_api=False,
                      temperature=0.3, timeout=120, max_retries=2, profile={"max_input_tokens": ctx})

@dataclass
class Ctx:  # immutable per-run context: agent.astream(..., context=Ctx(...))
    workspace_id: str
    operator_id: str

@tool
def search_public_ugc(query: str, platform: str, runtime: ToolRuntime) -> str:
    """Search permitted public short-form posts (official APIs only) and return metadata JSON."""
    get_stream_writer()({"type": "progress", "tool": "search_public_ugc", "query": query})
    return "[]"  # -> ugecy.integrations.research

@tool
def higgsfield_generate(prompt: str, kind: str, brief_path: str) -> str:
    """Start a Higgsfield media job for an approved brief. Returns job_id."""
    return "job_123"

@tool
def publish_post(account_id: str, asset_id: str, caption: str, scheduled_at: str | None = None) -> str:
    """Publish/schedule an approved asset to the operator's own connected account via official API."""
    return "post_123"

APPROVE_EDIT_REJECT = {"allowed_decisions": ["approve", "edit", "reject"]}
INTERRUPTS = {"higgsfield_generate": APPROVE_EDIT_REJECT, "publish_post": APPROVE_EDIT_REJECT}
PERMS = [FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny"),
         FilesystemPermission(operations=["write"], paths=["/memories/**"], mode="interrupt")]

def build(checkpointer, store, models: dict[str, ChatOpenAI] | None = None):
    m = models or {k: llm(v) for k, v in {"orch": os.getenv("UGECY_ORCH_MODEL", "@cf/zai-org/glm-5.3"),
                                          "fast": os.getenv("UGECY_FAST_MODEL", "@cf/zai-org/glm-4.7-flash")}.items()}
    ws = lambda rt: (rt.context.workspace_id, "memories")  # noqa: E731
    backend = CompositeBackend(default=StateBackend(), routes={
        "/memories/": StoreBackend(namespace=ws),
        "/skills/": StoreBackend(namespace=lambda rt: ("global", "skills"))})
    sub = lambda name, desc, prompt, tools, model="orch": {  # noqa: E731
        "name": name, "description": desc, "system_prompt": prompt, "tools": tools, "model": m[model],
        "middleware": [TodoListMiddleware()]}
    subagents = [
        sub("general-purpose", "Read-only helper for file search/summaries.", "Summarize files; no external actions.", []),
        sub("research-analyst", "Finds winning public UGC and extracts hook/script patterns with evidence to /research/.",
            "Cite every post URL. Write findings to /research/<topic>.md.", [search_public_ugc], "fast"),
        sub("creative-strategist", "Writes ORIGINAL hooks, scripts, briefs from /research/ into /briefs/.",
            "Never copy source scripts verbatim. Output briefs as markdown.", []),
        sub("production-coordinator", "Runs Higgsfield jobs for approved briefs; tracks asset status.",
            "Only generate for briefs marked approved.", [higgsfield_generate], "fast"),
        sub("publishing-coordinator", "Schedules/publishes approved assets to connected accounts.",
            "Confirm account, asset and caption before calling publish_post.", [publish_post], "fast"),
    ]
    return create_deep_agent(
        model=m["orch"], tools=[], name="ugecy-orchestrator",
        system_prompt="You are Ugecy's campaign orchestrator. Plan with write_todos, delegate via task, "
                      "keep artifacts in files, never publish without approval.",
        middleware=[TodoListMiddleware(), ModelRetryMiddleware(max_retries=2)],
        subagents=subagents, backend=backend, permissions=PERMS, interrupt_on=INTERRUPTS,
        skills=["/skills/"], memory=["/memories/AGENTS.md"], context_schema=Ctx,
        checkpointer=checkpointer, store=store)
```

Prod wiring: `async with AsyncPostgresSaver.from_conn_string(DSN) as cp, AsyncPostgresStore.from_conn_string(DSN) as st: await cp.setup(); await st.setup(); agent = build(cp, st)`. Run with `agent.astream({"messages": [...]}, {"configurable": {"thread_id": campaign_id}}, context=Ctx(ws, op), version="v2", subgraphs=True, stream_mode=[...])`. Seed skills with `await st.aput(("global","skills"), "/ugc-hook-extraction/SKILL.md", {"content": md, "encoding": "utf-8"})`.

## 12. Open questions and risks

1. **Tool-calling reliability of glm-5.3, deepseek-v4.1-flash and qwen3.8 through the Workers AI OpenAI shim.** Unknowns: parallel tool calls, streaming `tool_call_chunks`, `tool_choice`, and whether reasoning content leaks. Build a 20-task eval (plan, delegate, write_file, HITL resume) before choosing per-agent models. Budget a `model_compat` middleware (text tool-call parser, `<think>` stripping, "narration without tool call" nudge).
2. **Exact Workers AI model ids and context windows** (the `@cf/...` strings and `max_input_tokens`) are not verified here. A wrong `profile` breaks summarization thresholds.
3. **v3 event streaming is beta.** Its event schema may change. Ship v2 SSE first.
4. **HITL batched vs per_call.** The next langchain major plans to make per_call the default. Write the resume endpoint to accept both shapes (decisions list, or a map of interrupt id to decision).
5. **Postgres vs D1.** The decision depends on Neon/Supabase latency from Cloudflare Containers regions. The D1 saver is untested against DeltaChannel history reads (expect N sequential REST calls) and Cloudflare API rate limits.
6. **Memory is loaded once per thread.** Edits to `/memories/AGENTS.md` show up only in new threads. If the UI needs it sooner, set `memory_contents` or start a new thread.
7. **Subagents inherit the parent `tools` when `tools` is omitted,** and the GP subagent inherits the main `tools`. Both are lint-worthy footguns, so add a unit test asserting each subagent's tool set.
8. **deepagents moves fast** (0.7.x patch releases every few days; `BASE_AGENT_PROMPT` will be removed in 0.9). Pin exact versions and re-verify on upgrade. The prompt-assembly and profile APIs are marked beta.
9. **Async subagents need an Agent Protocol server.** Do not plan on them for Cloudflare Containers v1. Revisit if a self-hosted LangGraph API is adopted.

**Sources:**
- Source code: `deepagents` 0.7.34 wheel (`graph.py`, `middleware/{subagents,filesystem,skills,memory,summarization,_prompt_caching,async_subagents,rubric}.py`, `backends/*.py`, `profiles/**`), `langchain` 1.4.9 (`agents/middleware/human_in_the_loop.py`, `todo.py`), `langgraph` 1.2.20 (`types.py`, `pregel/main.py`), `langgraph-checkpoint-cloudflare-d1` 0.1.6.
- https://github.com/langchain-ai/deepagents (README, `libs/`, `examples/`, `libs/deepagents/CHANGELOG.md`, `examples/content-builder-agent`), https://github.com/langchain-ai/deepagents/issues/2940
- https://docs.langchain.com/oss/python/deepagents/event-streaming, https://docs.langchain.com/oss/python/deepagents/frontend/overview, https://github.com/langchain-ai/docs/blob/main/src/oss/deepagents/frontend/todo-list.mdx
- https://github.com/langchain-ai/deep-agents-ui, https://github.com/langchain-ai/design-agent, https://github.com/cloudflare/langchain-cloudflare, https://github.com/xerrors/Yuxi, GitHub topic search `topic:deepagents`
- https://forum.langchain.com/t/using-the-usestream-frontend-api-with-custom-fastapi-backend/3271
- https://github.com/copilotkit/opengenerativeui/issues/87, vllm-mlx tool-parser docs (`glm47`), open-webui docs (DeepSeek V3.2 function-calling issues)
