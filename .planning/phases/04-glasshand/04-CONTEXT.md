# Phase 04: Glasshand live iPhone

**Goal:** The operator clicks "Connect Glasshand", approves an email code, picks the rented iPhone, and then sees the live screen in the Device tab. The device-operator agent can see the real screen (vision grounding) and act on it, with approvals.
**Contract:** packages/contracts/GLASSHAND.md (frozen) and the `GlasshandStatus` types in packages/contracts/src/models.ts.
**Plans (wave 1, parallel, disjoint files):**
- 04-01: edge (Worker OAuth, token store, routes, relay, egress)
- 04-02: python (AutoDeviceProvider, Glasshand provider, vision describe)
- 04-03: web (connect flow and live view in the Device tab)
**Rules:** .planning/phases/02-build/EXECUTOR-BRIEF.md applies (ownership, no git, Ponytail, ≤500 lines, never print credentials). There is no live Glasshand account in this session, so every test uses mocked HTTP and WebSocket.
