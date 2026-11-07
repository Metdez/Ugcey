# Phase 07: Stuck recovery and continuous agent memory

## Operator ask (2026-11-07)
1. If an agent gets stuck, or keeps doing the same thing, it should use Firecrawl web search to understand its situation.
2. Agents should keep adding to their memory: how they did things, what worked, and what failed. Later runs should reference it. Use the Deep Agents memory framework.

## What the codebase does today
- `graph.py` passes `memory=["/memories/AGENTS.md"]` to `create_deep_agent`. Deep Agents adds a `MemoryMiddleware` to the **orchestrator only**. Declarative subagents get one only in `mode="fork"`, which we don't use.
- `MemoryMiddleware.abefore_agent` loads its sources once per thread into the private state key `memory_contents`. It skips loading when the key is already set, so edits made later in the same thread are not seen.
- It injects `<agent_memory>` plus guidelines that tell the model to save learnings with `edit_file`. The model rarely does this without a push.
- `/memories/` routes to `StoreBackend(namespace=memories_ns(workspace))`, which is mirrored to the DO SQLite. The Memory tab (`/api/memories`) lists every file under `/memories/`.
- Every specialist has `web_search` and `fetch_page` (Firecrawl, live). Nothing tells an agent to use them when it loops.

## Deep Agents memory model (docs.langchain.com/oss/python/deepagents/memory)
- **Semantic memory:** facts and lessons in `AGENTS.md`-style files, loaded into the system prompt.
- **Episodic memory:** records of how a problem was solved, recalled later.
- **Agent-scoped memory:** set by the StoreBackend namespace and the file path. Updates are file edits.

## Decisions
- **Per-agent semantic memory.** `/memories/agents/<agent>.md` holds a "Lessons" list for each agent. Each subagent loads it plus the shared `/memories/AGENTS.md` through its own `MemoryMiddleware`. The orchestrator loads `/memories/agents/orchestrator.md` too.
- **Fresh loads.** A `LiveMemoryMiddleware` subclass reloads the sources on every agent invocation, so lessons written by one subagent call are visible to the next call in the same thread.
- **Automatic recording, so it does not depend on the model choosing to call `edit_file`.** `ExperienceMiddleware.aafter_agent` runs after every subagent task and every orchestrator turn:
  - Episodic: append a dated entry (task, outcome, tools used, errors, stuck events) to `/memories/episodes/<agent>.md`. Keep the newest 60 entries; this is housekeeping, not a run limit.
  - Semantic: the fast model merges the episode into the existing lessons and returns an updated list of at most 25 short how-to bullets. If that model call fails, the deterministic episode is still saved.
  - Runs in the background so it never delays or blocks a run. Writes to the same file are serialized with a per-file lock.
- **Stuck detection.** `StuckMiddleware.awrap_model_call` scans the messages since the last `web_search`/`fetch_page`. It flags:
  - the same tool with the same arguments 3 or more times;
  - 3 tool errors in a row;
  - the same tool result 3 or more times in a row (for example, an identical phone screen).
  When it flags, it appends a "You appear stuck" section to the system message, naming the pattern and a suggested search query. It tells the agent to call `web_search`/`fetch_page` (agents without those tools are told to delegate a lookup to research-analyst), then try a different approach. Once the agent searches, the window resets. The nudge is ephemeral and never added to state. It is not a blocker: no caps, no stopping, no denial (AGENTS.md rule 8).
- Stuck events are recorded in the episode so the lesson ("X failed until Y") is learned.
- Never store credentials in memory (existing rule). The summarizer prompt says so explicitly.

## Out of scope
- Vector recall of episodes (the Vectorize pattern store already covers research patterns).
