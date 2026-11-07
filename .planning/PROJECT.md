# Ugecy

## What This Is

Ugecy is a chat-first operator workspace for UGC campaigns. A LangChain Deep Agents orchestrator and its specialist subagents research short-form content that performs well, work out why it works, write original hooks and scripts, generate media with Higgsfield, and queue approved posts for the operator's own connected social accounts (official APIs or a Glasshand-controlled iPhone). It is built for a solo operator or a small growth team. The interface is one chat window with sidebars that show what the agent is doing and what it has stored.

## Core Value

An operator types a product and a goal. The agent then produces evidence-backed, original UGC scripts and assets, and every todo, file, memory, tool call and approval it touches is visible and controllable.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Chat workspace with streaming Deep Agents conversation, left nav (threads/campaigns/accounts) and right inspector (plan, agents, files, memory, sources, assets, approvals, audit, device)
- [ ] Orchestrator + specialist subagents (research, creative, critic, production, publishing, device, analytics), each a removable module
- [ ] Research tools: Firecrawl web search/scrape, Cloudflare Browser Rendering fallback, pattern cards for hooks/structures
- [ ] Creative pipeline: brief → hooks → scripts → critic tournament → storyboard
- [ ] Media generation through Higgsfield with job tracking and asset gallery
- [ ] Human-in-the-loop approvals for every outward action (generate paid media, publish, device actions)
- [ ] Publishing queue to connected accounts with audit log, idempotency, AI-content disclosure
- [ ] Device pane: Glasshand session state, action receipts, live stream if the provider supports it
- [ ] Persistent memory: brand voice, pattern library, campaign playbooks (skills) that survive restarts
- [ ] Chinese models on Cloudflare Workers AI with a per-role routing table
- [ ] Deployed on Cloudflare (Worker + Static Assets + Container + D1 + KV + Queues + AI) with a public URL
- [ ] Mock mode: the whole loop is demoable when an integration has no credentials

### Out of Scope

- Automated creation of Gmail or social media accounts — violates Google/Meta/TikTok terms and is used for fake-account farms
- Account "warming" or any behaviour designed to make automated accounts look human to platform detection systems — this is detection evasion
- Coordinated multi-account posting meant to look like independent people (astroturfing) — coordinated inauthentic behaviour under every major platform policy
- Publishing or device actions without a human approval step — breaks the audit and consent model
- Scraping content behind logins or paywalls — research uses public, permitted sources only
- Anthropic models — explicit project rule

## Context

- Greenfield repo with five context docs (CLAUDE.md, AGENTS.md, docs/*) that set the rules.
- Cloudflare account: Workers Paid + Stream; workers.dev subdomain `zh-a16`; D1 and Containers available; R2 not enabled yet (dashboard action).
- Workers AI hosts the Chinese models in use: GLM-5.3, GLM-4.7-flash, DeepSeek-V4.1-flash, Qwen3.8-27B.
- Credentials present: Cloudflare API token and account ID, and a Higgsfield key/secret (`HF_API_KEY_SECRET`). No Glasshand credential, so the Glasshand path ships in mock mode.
- The GSD and Ponytail skills are not installed in this cloud session. This project follows the GSD workflow by hand (artifacts in `.planning/`), and coding agents follow the Ponytail rules recorded in research/INTEGRATIONS.md.

## Constraints

- **Tech stack**: Python backend (FastAPI + deepagents), TypeScript frontend (Vite + React + shadcn/ui) — project rule
- **File size**: every source file ≤ 500 lines — project rule
- **Modularity**: agents, tools and providers register through a registry and can be toggled by config — project rule
- **Models**: no Anthropic; Chinese models preferred — project rule
- **Platform**: Cloudflare-first for hosting, data, AI, async work — project rule
- **Process**: Firecrawl research before features; Mobbin + Firecrawl before UI; shadcn for UI — project rule
- **Safety**: approvals and audit for every external action; secrets only in Cloudflare secrets — compliance

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Follow GSD workflow manually in `.planning/` | GSD not installable in session (external-code install blocked) | — Pending |
| Chinese models via Workers AI | Rule + no extra API keys needed; account already has access | — Pending |
| Python agent in Cloudflare Containers behind a TS Worker | Python rule + Cloudflare-first rule | — Pending |
| Exclude account creation / warming / evasion | Platform-abuse and detection-evasion risk | ✓ Locked |

## Evolution

After each phase: move shipped requirements to Validated, log decisions, re-check "What This Is".

---
*Last updated: 2026-11-07 after project initialization*
