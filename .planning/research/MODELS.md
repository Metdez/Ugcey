# MODELS — Workers AI model spike for Ugecy Deep Agents

- **Date:** 2026-11-07 · **Stack:** deepagents 0.7.34, langchain 1.4.9, langgraph 1.2.20, langchain-openai 1.7.4, langchain-core 1.7.6, openai 3.46.0, httpx 0.28.1, Python 3.13
- **Endpoint (verified 200):** `https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1` with `/chat/completions` and `/embeddings`. `GET …/ai/v1/models` returns **405** (code 7001), so use `GET …/ai/models/search?task=…` for discovery.
- **Budget:** 145 Cloudflare API calls in total (5 catalog, 50 raw, 15 LangChain, 69 Deep Agents, 6 debug/aux). The stop-at-25-model-calls guard never fired.
- **Caveat:** each latency is a **single sample** (n=1). Workers AI showed 20–68 s outliers on otherwise ~2 s calls (see Quirk Q9).
- **Sources:** live API responses; Cloudflare model pages for glm-5.3, qwen3.8-27b and glm-5.2 (via Firecrawl); the langchain-openai and deepagents source code installed in the venv.

## 1. Candidates (catalog values from `/ai/models/search`)

| Model | Origin | Ctx | $/M in · out (cached in) | Reasoning effort (catalog) | Vision | Notes |
|---|---|---|---|---|---|---|
| `@cf/zai-org/glm-5.3` | CN (Zhipu) | 1,048,576 | 1.40 · 4.40 (0.26) | low/high/**max** default; *mandatory*; none/medium→max | – | Workers Paid required |
| `@cf/zai-org/glm-4.7-flash` | CN (Zhipu) | 131,072 | 0.0605 · 0.40 | on by default; no levels | – | cheapest |
| `@cf/deepseek-ai/deepseek-v4.1-flash-1017` | CN (DeepSeek) | 1,048,576 | 0.30 · 1.20 (0.006) | none/low/**high** default/max; medium→high | works (not flagged) | Workers Paid required |
| `@cf/qwen/qwen3.8-27b` | CN (Alibaba) | 262,144 | 0.45 · 3.20 (0.05) | low/medium/**xhigh** default | **yes** | catalog says `supports_max_tokens:false` (wrong, see Q8) |
| `@cf/openai/gpt-oss-120b` | US (reference) | 128,000 | 0.35 · 0.75 | low/**medium**/high; mandatory | – | |

## 2. Raw httpx results (`/chat/completions`, default effort, `max_completion_tokens=4096`)

Legend: ✅ pass · ⚠️ pass with quirk · ❌ fail. Times are wall-clock seconds.

| Test | glm-5.3 | glm-4.7-flash | deepseek-v4.1-flash | qwen3.8-27b | gpt-oss-120b |
|---|---|---|---|---|---|
| (a) non-stream, 1 sentence | ✅ 2.01 s (193 tok) | ⚠️ **67.9 s** (860 tok, mostly reasoning) | ✅ 2.13 s | ⚠️ 2.11 s (content starts with `\n\n`) | ❌ 1.93 s: content held raw `analysis: user asks…` |
| (a2) low effort / thinking off | ✅ `low` 0.70 s, **0 reasoning** | ⚠️ `enable_thinking:false` 23.4 s (35 tok; queueing?) | ✅ `low` 1.49 s (still reasons) | ✅ `low` 2.35 s (still reasons) | ✅ `low` 1.42 s, clean |
| (b) SSE TTFT / total / throughput | ✅ 0.42 / 2.63 s / ~142 tok/s | ✅ 0.41 / 29.5 s / ~48 tok/s | ✅ 2.07 / 4.07 s / ~65 tok/s | ✅ 0.26 / 2.57 s / ~46 tok/s | ✅ 0.43 / 1.83 s / ~50 tok/s |
| (b) `stream_options.include_usage` | ✅ usage chunk | ✅ | ✅ | ✅ | ✅ |
| (c) single tool call, args valid JSON | ✅ 1.25 s | ✅ 2.79 s | ✅ (24.8 s outlier) | ✅ 2.86 s | ✅ 0.90 s |
| (d) parallel tool calls (3 cities) | ✅ 3 calls, 4.29 s | ✅ 3, 2.27 s | ✅ 3, 2.62 s | ✅ 3, 2.62 s | ❌ **1 call only** (also in streams and LangChain) |
| (d2) streamed tool-call deltas → valid JSON | ✅ 2 deltas per call | ✅ 1 delta per call | ✅ 3–6 fragments | ✅ 4–5 fragments | ✅ 17 fragments (pretty-printed) |
| (e) reasoning field | `reasoning` + `reasoning_content` (dup) | both (dup) | both (dup) | **only `reasoning`** | both (dup) |
| (e) `<think>` tags in content | none | none | none | none | none (but harmony leak, see a) |
| (f) `tool_choice:"auto"` | ✅ | ✅ | ✅ | ✅ | ✅ |
| (f) `tool_choice:"required"` | ❌ text `<tool_call>get_weather</tool_call>`, finish=stop | ✅ | ❌ **DSML leak**, ran to max tokens (22.6 s), invalid JSON | ✅ | ❌ no call; finish=`tool_calls` with no tool_calls |
| (f) named function | ✅ (finish=`stop`) | ✅ (finish=`stop`) | ✅ (finish=`stop`) | ✅ (finish=`stop`, 23 s) | ❌ ignored; wrote 1.9k tokens about Rome |
| (g) multi-turn `role:tool` round-trip | ✅ 4.07 s, all 3 temps | ✅ 2.45 s | ✅ 3.35 s | ✅ 2.14 s | ⚠️ asked for the next city (sequential tools) |

**Not sending reasoning back works.** In (g) and in every agent run, `reasoning_content` was not echoed back on tool-call turns, and no model complained.

## 3. LangChain `ChatOpenAI` (via the `ChatWorkersAI` subclass, Appendix A)

| Check | glm-5.3 (high) | glm-4.7-flash (thinking off) | deepseek (high) | qwen (medium) | gpt-oss (medium) |
|---|---|---|---|---|---|
| `bind_tools` + `ainvoke` → 3 parsed `tool_calls`, 0 invalid | ✅ 0.89 s | ✅ 1.80 s | ✅ 2.58 s | ✅ 3.37 s | ⚠️ 1 call (1.29 s) |
| `astream` `tool_call_chunks` aggregate to valid calls | ✅ TTFT 1.69 s | ✅ 0.77 s | ✅ 0.79 s | ✅ 1.09 s | ✅ 0.29 s |
| `usage_metadata` with `stream_usage=True` | ✅ | ✅ | ✅ | ✅ | ✅ |
| reasoning visible in `additional_kwargs` (subclass only) | 0 chunks* | n/a | ✅ | ✅ | ✅ |
| `with_structured_output(Verdict)` (default json_schema), "cured my eczema in 3 days" hook | ✅ non-compliant, 2/10, 1.75 s | ❌ said **compliant**, 8/10 | ✅ non-compliant, 1/10, 11.6 s | ❌ **score 11** (bound 1–10), off-task reason, 16.2 s | ✅ non-compliant, 3/10, 8.0 s |

\*glm-5.3 at `high` emitted no reasoning on short tool turns but did emit it in the agent run (47 chunks).

## 4. Deep Agents end-to-end (`create_deep_agent` + fake `search_trends` + `creative-strategist` subagent)

Task: *"Research 3 trending hook styles for a skincare UGC ad, write a todo plan, delegate a script draft to creative-strategist, save it to /scripts/draft.md"*. Streamed with `astream(stream_mode=["updates","messages"], subgraphs=True)`, `InMemorySaver`, and `middleware=[TodoListMiddleware()]`.

| Model (main = sub) | Result | Time | Model calls | write_todos | search_trends | task → creative | write_file | draft.md | Invalid tool calls / loops |
|---|---|---|---|---|---|---|---|---|---|
| glm-5.3 | ✅ **PASS** | **42.9 s** | 9 | 4× | 2× | ✅ | 1× | 4,191 ch, compliant | 0 / none |
| glm-4.7-flash (thinking off) | ✅ PASS (verbose) | 114.5 s | 14 | 6× | 4× main + 5× sub | ✅ | 2× (extra file) | 6,771 ch | 0 / none (redundant calls) |
| deepseek-v4.1-flash | ✅ **PASS** (best draft) | 64.5 s | 10 | 3× | 3× | ✅ | 1× (+ `ls`, `read_file` to verify) | 7,442 ch: claim-substantiation flags, legal-review status | 0 / none |
| qwen3.8-27b | ✅ PASS | 102.0 s | 9 | 3× | 3× + 1× sub | ✅ | 1× | 3,076 ch | 0 / none |
| gpt-oss-120b | ⚠️ PASS **only after 2 payload fixes** (Q1, Q2) | 36.6 s | 7 | 2× | 1× | ✅ | 1× | 1,894 ch, weakest | first 2 runs: HTTP 400 |
| **glm-5.3 + creative-strategist on deepseek** | ✅ PASS | 68.1 s | 10 | 4× | 1× + 2× sub | ✅ (served by deepseek) | 1× | ✅ | 0 / none |

- No model hit the loop guard (25 calls) or the recursion limit. deepagents' own default is `recursion_limit=9999`, so production needs `ModelCallLimitMiddleware`.
- Compliance: every draft avoided cure/medical claims. Risky words such as "cures", "heals" and "eczema" appeared **only** inside "do not say X" compliance notes.
- First glm-5.3 run *without* `TodoListMiddleware`: it passed in 31.5 s / 7 calls but wrote a `/todos.md` file instead, because **`write_todos` does not exist by default in 0.7.34** (Q3).

## 5. Quirks and exact workarounds

| # | Quirk (observed) | Workaround (verified unless noted) |
|---|---|---|
| Q1 | gpt-oss-120b: 400 code 5006 `Type mismatch of '/messages/0/content'`. deepagents sends the SystemMessage as a **list of text blocks**. The CN models accept lists. | `ChatWorkersAI._get_request_payload` joins pure-text block lists into one string (image blocks are left alone). |
| Q2 | gpt-oss-120b: 400 `'/messages/2/content' 'string' not in 'null'`. ChatOpenAI serializes assistant tool-call turns with `content: null`. | Same hook: `None → ""`. Harmless for the CN models. |
| Q3 | deepagents 0.7.34 **no longer adds `TodoListMiddleware`** (`write_todos`). Its own codex profile notes "the SDK no longer provides it by default". | `create_deep_agent(..., middleware=[TodoListMiddleware()])` from `langchain.agents.middleware`. |
| Q4 | `ChatOpenAI` drops `reasoning_content` and `reasoning`. This is documented in its module header: "official OpenAI spec only". | Subclass copies either field into `additional_kwargs["reasoning_content"]` (stream and non-stream). Read `reasoning` too, because qwen sends only `reasoning`. GLM, DeepSeek and gpt-oss send both, duplicated, so take one. |
| Q5 | `tool_choice="required"` broken on **glm-5.3** (fake text tool call), **deepseek** (DSML markup `</｜DSML｜ parameter>` inside arguments, runs to max tokens) and **gpt-oss**. | Never send `required`. Use `auto` plus prompting; deepagents does this by default. To force a tool, use a named `tool_choice` (works on all 4 CN models; not on gpt-oss). |
| Q6 | Named `tool_choice` returns `finish_reason:"stop"` even when tool_calls are present (all CN models). | Branch on `msg.tool_calls`, never on `finish_reason`. |
| Q7 | Streamed `finish_reason` is repeated across ~3 chunks, so LangChain's merged `response_metadata["finish_reason"]` becomes `"tool_callstool_callstool_calls"` (all models). | Same as Q6. Cosmetic for agents. |
| Q8 | qwen3.8-27b catalog says `supports_max_tokens:false`, but `max_completion_tokens:30` **was enforced** (finish=length, 30 tokens). | Use `max_completion_tokens` (`max_tokens` is deprecated in the docs). Set 8192 for agents: 4096 was exhausted by runaway output (deepseek in Q5). |
| Q9 | Latency outliers on short calls: glm-4.7-flash 67.9 s (default thinking) and 23.4 s (thinking off); deepseek 24.8 s; qwen 23.0 s and 48.3 s (30 tokens). | `timeout=180`, `max_retries=2`, plus `ModelFallbackMiddleware` / `ModelRetryMiddleware` (exist in langchain 1.4.9). Track p95 per model in prod. |
| Q10 | glm-4.7-flash `reasoning_effort:"none"` → **400 code 8001** "Invalid input". Default thinking is extremely verbose. | `extra_body={"chat_template_kwargs": {"enable_thinking": False}}` (verified: 0 reasoning). |
| Q11 | glm-5.3 effort aliases: `none`, `minimal` and `medium` silently map to **max**; reasoning cannot be disabled per the docs. `low` produced 0 reasoning tokens (0.7 s) in practice. | Use only `low` / `high` / `max`. |
| Q12 | gpt-oss-120b at default effort once put raw harmony text (`analysis: …`) in `content`. It also never emits parallel tool calls. | Set `reasoning_effort` explicitly. Keep it out of CN-first routes. |
| Q13 | qwen3.8-27b content often starts with `"\n\n"`. | `.strip()` before UI display or storage. |
| Q14 | `ChatOpenAI` auto-switches to `/responses` if `reasoning=`, `include=` and similar are set; deepagents' OpenAI profile forces `use_responses_api=True` for `openai:*` **strings**. | Pass a ChatOpenAI **instance** with `use_responses_api=False` and use top-level `reasoning_effort=`, never `reasoning={...}`. |
| Q15 | langchain-openai warns that `http_socket_options` disables httpx proxy auto-detection (`HTTPS_PROXY`). | `http_socket_options=()`, or pass your own `http_async_client`. |
| Q16 | Subagents **inherit the main agent's tools** unless `tools` is set (creative-strategist called `search_trends`). | Give every SubAgent an explicit `tools=[...]` (least privilege, per engineering-rules). |
| Q17 | `/v1/embeddings` responses have no `usage` key. | Meter by input tokens yourself. With LangChain `OpenAIEmbeddings`, set `check_embedding_ctx_length=False` (default True sends tiktoken IDs; **not exercised in spike**). |

## 6. Real stream event shapes (deepagents, `subgraphs=True`, `stream_mode=["updates","messages"]`)

Each item is a 3-tuple `(namespace: tuple[str,...], mode: str, data)`. `namespace == ()` is the main agent; a subagent is `("tools:<uuid>",)`.

```text
# messages: token chunk, main agent, reasoning (ChatWorkersAI only)
((), "messages", (AIMessageChunk(content="", additional_kwargs={"reasoning_content": "…"}),
  {"langgraph_node": "model", "langgraph_step": 2, "checkpoint_ns": "model:d35003a2-ba2d-e3b9-d926-66cfae545b3a",
   "lc_agent_name": None, "ls_model_name": "@cf/zai-org/glm-5.3"}))
# messages: tool-call chunk (first fragment has name+id, args None; later fragments carry args by index)
((), "messages", (AIMessageChunk(content=".", tool_call_chunks=[{"name": "write_todos", "args": None,
  "id": "chatcmpl-tool-9cabdc3f979d424d", "index": 0, "type": "tool_call_chunk"}]), {...same meta...}))
# messages: ToolMessage results also flow through "messages" (node "tools")
((), "messages", (ToolMessage(content="Updated todo list to [{'content': 'Research 3 trending hook styles…"),
  {"langgraph_node": "tools", "langgraph_step": 4, "lc_agent_name": None}))
# updates: model node
((), "updates", {"model": {"messages": [AIMessage("I'll start by writing a todo plan, then research trends.",
  tool_calls=[{"name": "write_todos", ...}])]}})
# updates: tools node (todos land in state)
((), "updates", {"tools": {"messages": [ToolMessage(...)], "todos": [{"content": "...", "status": "in_progress"}, ...]}})
# updates: middleware nodes emit data=None  ← consumers must handle None
((), "updates", {"PatchToolCallsMiddleware.before_agent": None})
((), "updates", {"TodoListMiddleware.after_model": None})
((), "updates", {"_ParentNotifierMiddleware.after_agent": None})
# subagent (mixed run): namespace + lc_agent_name identify it; ls_model_name shows the routed model
(("tools:d0b4a47e-7d96-4d06-fcbb-7476cdea8749",), "messages", (AIMessageChunk(...),
  {"langgraph_node": "model", "langgraph_step": 2, "checkpoint_ns": "tools:d0b4a47e-…",
   "lc_agent_name": "creative-strategist", "ls_model_name": "@cf/deepseek-ai/deepseek-v4.1-flash-1017"}))
(("tools:1e8c2b30-e858-b650-2820-2ce71436cf4b",), "updates", {"model": {"messages": [AIMessage(
  "I've reviewed the trend research — I'm going with **Hook Sty…")]}})
```

Event volume per run (glm-5.3): `updates` main 26, sub 2; `messages` main 569, sub 454. gpt-oss produced about 3,500 `messages` events because of fine-grained reasoning chunks. UI should batch or throttle.

Raw SSE (before LangChain), real lines:

```text
data: {"id":"id-1794058452795","created":1794058452,"model":"@cf/zai-org/glm-5.3","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":""},"logprobs":null,"finish_reason":null}],"u…
glm-5.3   tool delta: {"id":"chatcmpl-tool-8fea2980c07ce4fc","type":"function","index":0,"function":{"name":"get_weather"}} → {"index":0,"function":{"arguments":"{\"city\": \"Paris\"}"}}
glm-4.7f  tool delta: {"id":"chatcmpl-tool-aa2e…","type":"function","index":0,"function":{"name":"get_weather","arguments":"{\"city\": \"Paris\"}"}}   (whole call, 1 delta)
deepseek  tool delta: {"index":0,"function":{"arguments":"{\"city\": \"Paris"}} → {"index":0,"function":{"arguments":"\", \"unit\": \""}}
gpt-oss   tool delta: {"id":"chatcmpl-tool-999f…","index":0,"function":{"name":"get_weather","arguments":""}} → {"arguments":"{\n"} → {"arguments":" "} …
```

## 7. Exact working configuration

Use `make_model()` from Appendix A. Its effective `ChatOpenAI` kwargs are:

```python
ChatWorkersAI(                      # ChatOpenAI subclass, Appendix A
    model="@cf/zai-org/glm-5.3",
    base_url=f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID']}/ai/v1",
    api_key=os.environ["CLOUDFLARE_API_TOKEN"],
    streaming=True, stream_usage=True,          # usage chunk works; LangChain defaults it off for custom base_url
    max_completion_tokens=8192, timeout=180, max_retries=2,
    use_responses_api=False, http_socket_options=(),
    reasoning_effort="high",                    # per-model: see MODEL_KWARGS
)
# Not needed: parallel_tool_calls / disabled_params (CN models handle parallel calls; gpt-oss ignores it).
# Never: tool_choice="required", reasoning={...}, reasoning_effort="none" on glm-4.7-flash or glm-5.3.
```

Deep Agents wiring that passed:

```python
agent = create_deep_agent(
    model=make_model("@cf/zai-org/glm-5.3"),
    tools=[search_trends], system_prompt=SYSTEM,
    subagents=[{"name": "creative-strategist", "description": "...", "system_prompt": "...",
                "model": make_model("@cf/deepseek-ai/deepseek-v4.1-flash-1017"), "tools": []}],
    middleware=[TodoListMiddleware(), ModelCallLimitMiddleware(run_limit=40)],  # Q3 + loop guard
    checkpointer=InMemorySaver())                    # prod: durable checkpointer
```

## 8. Non-chat catalog (current, non-deprecated; 🇨🇳 = Chinese origin)

| Task | Options (price) | Deprecating 2026-11-20 (avoid) |
|---|---|---|
| Text Embeddings | 🇨🇳 `@cf/qwen/qwen3-embedding-0.6b` (8k ctx, **1024-d verified**, $0.0118/M); 🇨🇳 `@cf/baai/bge-m3` (multilingual, **1024-d verified**, $0.0118/M, 0.3 s); 🇨🇳 `@cf/baai/bge-large-en-v1.5` (1024-d, 512 tok); 🇨🇳 `bge-base-en-v1.5` (768-d); 🇨🇳 `bge-small-en-v1.5` (384-d); `@cf/pfnet/plamo-embedding-1b` (JP) | `@cf/google/embeddinggemma-300m` |
| Automatic Speech Recognition | `@cf/openai/whisper-large-v3-turbo` ($0.000513/audio-min); `@cf/deepgram/nova-3` (partner, realtime WS, $0.0052/min, $0.0092 WS); `@cf/deepgram/flux` (partner, realtime turn-taking, $0.0077/min WS); `@cf/openai/whisper`. **No Chinese ASR available.** | `@cf/openai/whisper-tiny-en` |
| Image-to-Text | `@cf/moondream/moondream3.1-9B-A2B` (detection/pointing/OCR, $0.30/$1.00) | `@cf/llava-hf/llava-1.5-7b-hf` |
| Vision-capable chat | 🇨🇳 `@cf/qwen/qwen3.8-27b` (**verified**: "A blue square is centered against a solid red background", 2.5 s); 🇨🇳 `@cf/deepseek-ai/deepseek-v4.1-flash-1017` (**verified** 2.6 s, though not flagged `vision` in the catalog); `@cf/google/gemma-4-26b-a4b-it` (256k, FC, $0.10/$0.30); `@cf/meta/llama-4-scout-17b-16e-instruct`; `@cf/mistralai/mistral-small-3.1-24b-instruct`; `@cf/meta/llama-3.2-11b-vision-instruct`; `@cf/swiss-ai/apertus-v1.5-8b`; `@cf/cloudflare/clef`, `clef-flash`, `clef-omni`, `clairic` | `@cf/moonshotai/kimi-k2.7-code` |
| Text-to-Image | `@cf/black-forest-labs/flux-2-dev`, `flux-2-klein-9b`, `flux-2-klein-4b` (partner); `flux-1-schnell`; `@cf/leonardo/lucid-origin`, `phoenix-1.0` (partner). **No non-deprecated Chinese option.** | 🇨🇳 `@cf/bytedance/stable-diffusion-xl-lightning`, `@cf/lykon/dreamshaper-8-lcm`, SDXL base, SD-1.5 inpainting |

## 9. RECOMMENDED ROUTING TABLE

| Role | Primary | Fallback | Settings | Rationale (measured) |
|---|---|---|---|---|
| **Orchestrator** (main deep agent) | 🇨🇳 `glm-5.3` | 🇨🇳 `deepseek-v4.1-flash-1017` | effort `high`; 1M ctx both | Fastest clean agent run (42.9 s / 9 calls), perfect todo/task/file discipline, correct judgment. DeepSeek also passed (64.5 s / 10 calls) at about 1/4 the price. Both avoid `required` (Q5). |
| **research-analyst** subagent | 🇨🇳 `deepseek-v4.1-flash-1017` | 🇨🇳 `glm-5.3` | effort `high`; explicit `tools=[...]` | 1M ctx at $0.30/M in ($0.006 cached) for long evidence dumps; reliable parallel tool calls; self-verified its file (`ls`/`read_file`); multimodal for screenshot evidence. |
| **creative-strategist** subagent | 🇨🇳 `deepseek-v4.1-flash-1017` | 🇨🇳 `glm-5.3` | effort `high`, `tools=[]` | Best draft (7.4k ch, flagged claim substantiation and legal review, 82-word VO timing). Routing to it as a subagent was verified (68.1 s run). |
| **critic / judge** | 🇨🇳 `glm-5.3` | 🇨🇳 `deepseek-v4.1-flash-1017` | `with_structured_output` (json_schema); effort `high` | Correct verdict in 1.75 s. A different family from the creator (DeepSeek) reduces self-preference bias. **Do not** use glm-4.7-flash (approved a cure claim) or qwen (score out of range, off-task). |
| **fast utility** (titles, summaries, tags) | 🇨🇳 `glm-4.7-flash` | 🇨🇳 `glm-5.3` @ `low` | flash: `chat_template_kwargs.enable_thinking=false`; glm-5.3 low = 0 reasoning, 0.7 s | Flash is $0.06/$0.40 and ~1–2 s in LangChain with thinking off. **Never run it with default thinking** (67.9 s). Optional cheaper fallback to verify: deepseek `reasoning_effort="none"`. Not for judgment calls. |
| **vision** (frames, thumbnails, screenshots) | 🇨🇳 `qwen3.8-27b` | 🇨🇳 `deepseek-v4.1-flash-1017` | effort `low`; `.strip()` output (Q13) | Both verified on a data-URI PNG (~2.5 s). Qwen is officially flagged `vision`; DeepSeek works but is unflagged, so re-check it per release. Use `moondream3.1` for OCR/pointing/detection. |
| **embeddings** | 🇨🇳 `@cf/qwen/qwen3-embedding-0.6b` (1024-d) | 🇨🇳 `@cf/baai/bge-m3` (1024-d) | `/v1/embeddings` | Both verified via the OpenAI-compatible endpoint. Same dimensions but **incompatible vector spaces**, so a fallback needs its own index. Pin one model per index. |
| **speech-to-text** | `@cf/openai/whisper-large-v3-turbo` (batch) | `@cf/deepgram/nova-3` (realtime WS) | `/ai/run` (not OpenAI-compat; untested) | No Chinese ASR on Workers AI. Whisper is open-weight (not Anthropic) and 10× cheaper per minute; use Deepgram for live iPhone-stream captions. |
| (not routed) non-CN reference | `gpt-oss-120b` | – | needs Q1/Q2 normalizer | Passed the agent run only after the payload fixes. No parallel calls, ignores forced tool choice, weakest draft. Last-resort fallback only. |

Fallback mechanics: the agent's or subagent's `model` is the primary. Add `ModelFallbackMiddleware(make_model(<fallback>))` (signature: `first_model, *additional_models`, fallbacks only) to that agent's or subagent's `middleware`, or use `llm.with_fallbacks([...])` outside agents. Add `ModelRetryMiddleware(max_retries=2)` for Q9 outliers and `ModelCallLimitMiddleware(run_limit=…)` as the loop guard. Record the selected model per task in task context (architecture doc rule).

## Appendix A — `workers_ai_chat.py` (the subclass and config used by all passing runs)

```python
import os
from langchain_openai import ChatOpenAI

class ChatWorkersAI(ChatOpenAI):
    """Copies `reasoning_content` / `reasoning` into additional_kwargs["reasoning_content"]."""
    def _convert_chunk_to_generation_chunk(self, chunk, default_chunk_class, base_generation_info):
        gc = super()._convert_chunk_to_generation_chunk(chunk, default_chunk_class, base_generation_info)
        choices = chunk.get("choices") or []
        if gc is not None and choices:
            d = choices[0].get("delta") or {}
            r = d.get("reasoning_content") or d.get("reasoning")  # some models send both (duplicated)
            if r:
                gc.message.additional_kwargs["reasoning_content"] = r
        return gc

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        # deepagents sends SystemMessage content as [{"type":"text",...}]; gpt-oss rejects non-string (5006).
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        for m in payload.get("messages", []):
            c = m.get("content")
            if isinstance(c, list) and c and all(isinstance(b, dict) and b.get("type") == "text" for b in c):
                m["content"] = "\n\n".join(b.get("text", "") for b in c)
            elif c is None:  # assistant tool-call turns serialize content=null; gpt-oss rejects null
                m["content"] = ""
        return payload

    def _create_chat_result(self, response, generation_info=None):
        res = super()._create_chat_result(response, generation_info)
        rd = response if isinstance(response, dict) else response.model_dump(warnings=False)
        for g, ch in zip(res.generations, rd.get("choices") or []):
            m = ch.get("message") or {}
            r = m.get("reasoning_content") or m.get("reasoning")
            if r:
                g.message.additional_kwargs["reasoning_content"] = r
        return res

MODEL_KWARGS = {
    "@cf/zai-org/glm-5.3": {"reasoning_effort": "high"},
    "@cf/zai-org/glm-4.7-flash": {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
    "@cf/deepseek-ai/deepseek-v4.1-flash-1017": {"reasoning_effort": "high"},
    "@cf/qwen/qwen3.8-27b": {"reasoning_effort": "medium"},
    "@cf/openai/gpt-oss-120b": {"reasoning_effort": "medium"},
}

def make_model(model: str, **overrides) -> ChatWorkersAI:
    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    kw = dict(model=model, base_url=f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/v1",
              api_key=os.environ["CLOUDFLARE_API_TOKEN"], streaming=True, stream_usage=True,
              max_completion_tokens=8192, timeout=180, max_retries=2,
              use_responses_api=False, http_socket_options=())
    kw.update(MODEL_KWARGS.get(model, {})); kw.update(overrides)
    return ChatWorkersAI(**kw)
```

## Appendix B — Deep Agents spike harness (trimmed from `deep_agent_run.py`)

```python
@tool
def search_trends(query: str) -> str:
    """Search current short-form video trends (TikTok/Reels/Shorts) for a query. Returns JSON."""
    return json.dumps({"query": query, "source": "canned-fixture", "hook_styles": [
        {"style": "POV / relatable moment", "example": "POV: you finally stopped picking at your skin", "lift": "+31% 3s-hold"},
        {"style": "Before/after time-lapse tease", "example": "Day 1 vs day 28 — watch till the end", "lift": "+27% completion"},
        {"style": "Myth-bust / 'stop doing this'", "example": "Stop using hot water on your face", "lift": "+22% shares"},
        {"style": "Ingredient spotlight", "example": "Niacinamide is doing ALL the work here", "lift": "+12% saves"}]})

async def run(model: str):                       # "main" or "main+sub" for mixed routing
    model, _, sub_model = model.partition("+")
    calls = {"n": 0}
    async def hook(req: httpx.Request):          # loop guard: hard stop after 25 model HTTP calls
        if req.url.path.endswith("/chat/completions"):
            calls["n"] += 1
            if calls["n"] > 25: raise RuntimeError("STOP: > 25 model calls (loop guard)")
    hc = httpx.AsyncClient(event_hooks={"request": [hook]}, timeout=180)
    llm = make_model(model, http_async_client=hc, max_retries=1)
    subs = [dict(s, model=make_model(sub_model, http_async_client=hc, max_retries=1)) for s in SUBAGENTS] if sub_model else SUBAGENTS
    agent = create_deep_agent(model=llm, tools=[search_trends], system_prompt=SYSTEM, subagents=subs,
                              checkpointer=InMemorySaver(), middleware=[TodoListMiddleware()])
    cfg = {"configurable": {"thread_id": f"spike-{model}"}, "recursion_limit": 150}
    async for ns, mode, data in agent.astream({"messages": [{"role": "user", "content": TASK}]}, cfg,
                                              stream_mode=["updates", "messages"], subgraphs=True):
        if mode == "updates":                    # {node: update|None}; collect tool_calls / invalid_tool_calls
            for node, upd in (data or {}).items():
                for m in (upd or {}).get("messages", []) if isinstance(upd, dict) else []:
                    for tc in getattr(m, "tool_calls", None) or []:
                        record("sub" if ns else "main", tc["name"], tc["args"])
        else:                                    # (AIMessageChunk|ToolMessage, metadata)
            chunk, meta = data                   # meta: langgraph_node, lc_agent_name, ls_model_name, checkpoint_ns
    st = await agent.aget_state(cfg)             # st.values["files"]["/scripts/draft.md"], st.values["todos"]
```

## Appendix C — raw probe core (trimmed from `raw_tests.py`)

```python
WEATHER = {"type": "function", "function": {"name": "get_weather", "description": "Get current weather for one city.",
           "parameters": {"type": "object", "properties": {"city": {"type": "string"},
                          "unit": {"type": "string", "enum": ["c", "f"]}}, "required": ["city"]}}}
base = {"model": model, "max_completion_tokens": 4096}
chat(c, {**base, "messages": [{"role": "user", "content": "Hi! How are you?"}], "tools": [WEATHER], "tool_choice": "required"})
chat(c, {**base, "messages": msgs, "tools": [WEATHER], "tool_choice": {"type": "function", "function": {"name": "get_weather"}}})
stream_chat(c, {**base, "stream_options": {"include_usage": True}, "messages": [...]})  # TTFT = first content/reasoning/tool delta
# (g) round-trip: msgs + [{"role":"assistant","content":"","tool_calls":tcs}] + [{"role":"tool","tool_call_id":id,"content":json}]
```

Spike files (scratch, not committed): `/tmp/claude-0/-home-user-Ugcey/fa2c91df-9a17-597b-a1bb-bf83d8f15881/scratchpad/model-spike/` holds `common.py`, `raw_tests.py`, `lc_tests.py`, `deep_agent_run.py`, `workers_ai_chat.py`, `aux_tests.py`, `capture_payload.py` and the `results_*.json` files.
