---
name: deep-research
description: "Run deep web research on winning UGC hooks, short-form formats, customer language and trends with Tavily (tavily_research, tavily_search, tavily_extract) and Firecrawl (web_search, fetch_page). Use for any research brief: what is working now in a niche, competitor ad teardowns, voice of customer, trend scans."
---
# Deep research playbook (Tavily + Firecrawl)

## Principles
- Breadth first, then depth. Fire many queries and research tasks in one turn (they run in parallel), then extract and read the best sources, then fill gaps in follow-up rounds.
- Evidence beats opinion. A pattern needs 2+ independent sources dated within 90 days, at least one primary (an ad library or Creative Center entry, or a real post). An ad running 30+ days has passed a market test.
- Log structures, not lines. Separate the angle (problem, outcome, social proof, demo, comparison) from the hook type (question, stat, POV, callout...).

## Tavily
- `tavily_research` (model pro): the heaviest tool. One task per angle, 4 to 6 in the first batch, more in follow-ups. Put the full context in the question: product, category, audience, platforms, time window ("right now", "last 30 days"), and the exact output wanted ("a table: hook pattern, example paraphrase, format, why it works, source URL, date").
- `tavily_search`: advanced depth, up to 20 results with the relevant passages. Use `time_range` week or month for "now", `topic` news for launches and press, `include_domains` ["reddit.com"] for customer language, ["tiktok.com"] or ["youtube.com"] for trend snippets. Keep each query focused; split broad questions into several.
- `tavily_extract`: pass all the promising URLs at once (groups of 20 run in parallel) with a `query` such as "ad hooks and the first 3 seconds" to get the relevant passages.

## Firecrawl
- `web_search`: a second index. `recency` week or month returns the newest first; `news=True` for news. Run the same angles here to catch what Tavily missed.
- `fetch_page`: the full text of one page, including TikTok Creative Center and Meta Ad Library keyword pages.

## Query bank (swap in the niche, product, pains and competitors)
- Hooks: "<category> UGC ad hooks 2026", "best performing <category> TikTok ads", "<category> ad hook examples first 3 seconds", "<competitor> TikTok ad", "<category> creative strategy breakdown"
- Formats: "<category> UGC video formats that convert", "<category> before after UGC", "<category> founder story ad", "short-form ad structure <category>"
- Customer voice: "<category> worst part", "I wish <category>", "<competitor> review", "<pain> reddit"
- Trends: "<category> TikTok trend", "<niche> viral", "<category> trending sounds", "<category> news" (news topic)
- Primary sources:
  - Creative Center: https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en and https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en
  - Meta Ad Library: https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&media_type=video&q=<term>

## Hook library entry
hook line (paraphrased), hook_type, angle, format, first 3 seconds (visual, on-screen text, spoken), beat structure (0-3 s hook, problem, demo, proof, CTA), platforms, why it works, audience language, evidence [URL, source type, date, days running or metric], recency, confidence 0-1, observed or inferred, do_not_copy, compliance flags.

## Stop when
New research rounds stop producing new hook types, formats or customer themes, and each kept pattern meets the evidence bar.
