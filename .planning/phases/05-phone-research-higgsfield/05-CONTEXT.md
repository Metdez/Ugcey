# Phase 05: research on the Glasshand iPhone + live Higgsfield production

**Operator request:**
- "When we say do research, it does it on Glasshand."
- "Glasshand does everything on the phone; on our end Higgsfield does the work."

**Decisions:**
- **D1 Research source.** When a real iPhone is connected (`device_status` provider=glasshand and ready), the research analyst researches **on the phone**: it opens TikTok, Instagram or YouTube, searches, watches posts and records observations. Web search becomes a supplement. Otherwise it falls back to web or sample data and says so.
- **D2 Read-only research sessions.**
  - `device_start_session(..., purpose="research")` needs one approval per session.
  - Research sessions can tap, swipe, type search queries (≤ 80 characters), go Home, screenshot and observe.
  - They can **not** call `device_commit`, like, follow, comment, DM, share, post, buy, log in or handle verification codes. The prompt and a code guard both enforce this.
  - Pace is human: a 2–4 s dwell per post. Budget: ≤ 12 posts and ≤ 60 steps per session.
  - If a login wall, captcha or verification screen appears, stop and report. Never solve it.
- **D3 Observation tool.** `device_observe(note="")` runs screenshot → vision (Qwen3.8) with a post-extraction prompt. It returns JSON: platform, creator handle, caption, on-screen text, hook, visible metrics (views, likes, comments, shares, saves), audio, format guess, and UI elements with coordinates. It records a Source (url = the visible post URL if any, else `device://<platform>/<handle>`) and emits `source.added`.
- **D4 Higgsfield is the production engine.** The adapter is verified against docs.higgsfield.ai, and the estimate is live. The chain is still (Soul / Marketing Studio) → image-to-video (Seedance 2.5 / Kling 3.0), or Seedance text-to-video directly. Every generation still needs approval and shows the estimated cost. Pollers resume after a container restart.
- **D5 Secret.** The Worker secret `HF_KEY` must be set by the operator, because auto mode blocks the agent from writing secrets. Until then, media stays mock.

**Plans:** 05-01 phone research (python), 05-02 Higgsfield production (python). The file sets are disjoint. Rules: `.planning/phases/02-build/EXECUTOR-BRIEF.md`.
