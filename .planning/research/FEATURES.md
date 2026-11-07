# FEATURES — Ugecy research (features dimension)

**Researched:** 2026-11-07 · **Researcher:** features dimension (1 of 8) · **Method:** Firecrawl search/scrape of primary docs + GitHub metadata (via Firecrawl Alexandria `github-com`), WebFetch where Firecrawl can't reach (developers.tiktok.com).
**Confidence:** HIGH for API facts quoted from platform docs (dated below); MEDIUM for practitioner frameworks (hooks/formats/benchmarks); LOW items marked `VERIFY`.
Scratch notes with all raw citations: `/tmp/claude-0/-home-user-Ugcey/fa2c91df-9a17-597b-a1bb-bf83d8f15881/scratchpad/features-research/notes.md`

---

## 0. Decision-relevant findings (read this first)

1. **Publishing is gated by platform review, not by code.** TikTok: unaudited clients post `SELF_ONLY` only, ≤5 posting users/24h, account must be private ([guidelines](https://developers.tiktok.com/doc/content-sharing-guidelines)). Instagram: Advanced Access via App Review for anyone without a role on the app. YouTube: since **2026-11-02** unverified API projects are **no longer forced private**, and an omitted `privacyStatus` now **defaults to public** ([revision history](https://developers.google.com/youtube/v3/revision_history)). So YouTube Shorts is the fastest path to a real public post. Submit the TikTok audit and Meta App Review in week 1. They are the critical path.
2. **Every platform now has an API-level AI disclosure flag.** TikTok `is_aigc`, Instagram `is_ai_generated`, YouTube `status.containsSyntheticMedia`. Facebook Page Reels has no documented field (`VERIFY`). Make the AI flag a **required, no-default** field in `PublishDraft`. Ugecy's media comes from Higgsfield, so nearly every post will be AI-generated.
3. **Commercial access to research data is narrow.** TikTok Research API is academic/non-profit only. TikTok Commercial Content API and Meta Ad Library (all ad types) cover **EU/UK ads only**. TikTok Creative Center has no public API. The usable v1 sources are the YouTube Data API (public stats), IG `business_discovery` (public pro accounts), oEmbed for pasted links, and **operator-uploaded files**. Downloading third-party TikTok/IG/YouTube videos for analysis conflicts with platform ToS. Ingest by upload with a rights attestation, and **flag this for legal review**.
4. **Platforms explicitly reward originality and penalize mass production.** YouTube renamed its "repetitious content" policy to "inauthentic content" on 2025-07-15 and now covers AI template mass production ([YPP policy](https://support.google.com/youtube/answer/1311392)). TikTok's guidelines say copying content from other platforms "is not acceptable". Mosseri says recycled content gets replaced and other apps' watermarks hurt reach. Ugecy's moat should be **explained, transferable patterns plus original scripts**, not cloning.
5. **The Deep Agents primitives map directly onto the "wow" features.** These are long-term memory (filesystem/store), Skills, subagents, human-in-the-loop interrupts, and **Rubric grading (beta) middleware**, an LLM-as-judge that iterates until a rubric passes ([middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)). Together they give a pattern library, playbooks, critic tournaments and approval gates with little custom plumbing. `langchain-ai/paid-media-agent` (Apache-2.0, built on Deep Agents, "reviewed changes") is the closest public reference architecture.

---

## 1. Virality analysis method

### 1.1 What platforms say they weight (primary sources)
| Platform | Signal | Source |
|---|---|---|
| Instagram | Top three ranking signals are **watch time, likes, sends**. *Sends per reach* matters most for reaching non-followers. Since 2026-10-23, sends count "a lot more" than comments | Mosseri, [reel DFFyRp-pINJ](https://www.instagram.com/reel/DFFyRp-pINJ/), summarized by [Buffer](https://buffer.com/resources/instagram-algorithms/) |
| Instagram (owned) | API exposes `reels_skip_rate` (share of viewers who skip in the first 3 s), `ig_reels_avg_watch_time`, `shares`, `saved`, `reach`, `views` | [IG Media Insights](https://developers.facebook.com/documentation/instagram-platform/reference/instagram-media/insights) |
| TikTok (ads) | Creative Codes: hook/body/close. **90% of ad-recall impact lands in the first 6 s**. Product on screen gives +65% brand affinity. CTA cards give +45% recall. 88% of users say sound is vital | [TikTok Creative Codes](https://ads.tiktok.com/business/en-US/blog/creative-best-practices-top-performing-ads) |
| YouTube Shorts | Studio metrics "Shown in feed" and "Viewed (vs. swiped away)". Shorts can run up to **3 min**, square or vertical | [YT community](https://support.google.com/youtube/community-video/273390203), [3-min Shorts](https://support.google.com/youtube/answer/15424877) |
| Meta paid | Hook rate = 3-s plays ÷ impressions (Motion targets 30–40%). Hold rate = ThruPlays ÷ 3-s plays (40–50% is average) | [Motion metrics](https://motionapp.com/blog/key-creative-performance-metrics), [admakeai summary](https://admakeai.com/blog/hook-rate) |

### 1.2 Retention structure (beat grammar the agent labels)
`HOOK (0–3 s: stop the scroll) → CONTEXT/PROBLEM (why care) → OPEN LOOP (promise held back) → BODY (demo / story / proof beats, re-hook every ~5–8 s) → PAYOFF (loop closed) → CTA (soft or explicit) → LOOP-BACK (ending flows into the start)`.
Diagnostics come from the [Exposure](https://www.exposure.com.au/blog/hook-rate-vs-hold-rate) and Motion definitions. A low hook rate or high skip rate means a frame-zero problem. A good hook with a low hold rate means a body or pacing problem, or a clickbait mismatch.

### 1.3 Hook taxonomy (practitioner consensus; enum `hook_type`)
| hook_type | Mechanism | Template (abstract, never copied) | Detection cue |
|---|---|---|---|
| curiosity_gap | Withhold the answer | "Nobody tells you this about [X]…" | Unresolved claim, payoff later |
| pattern_interrupt | Unexpected visual or audio in frame 0 | Object thrown at the lens, odd angle, sudden cut | High motion or novelty in the first 0.5 s |
| negative_warning | Loss aversion | "Stop doing [X] if you [Y]" | Negation or imperative in the first sentence |
| contrarian | Violates a belief | "[Popular thing] is a scam. Here's why" | Opposing stance word |
| result_first | Show the outcome first | Before/after reveal, then "here's how" | Transformation visual at t<2 s |
| callout_question | Self-identification | "If you have [problem], watch this" | 2nd person + condition |
| pov_relatable | Viewer is the protagonist | "POV: you just [situation]" | "POV" on-screen text |
| storytime | Narrative tension | "I almost [bad outcome] until…" | Past-tense opener + stakes |
| listicle_number | Bounded effort | "3 things I'd never buy again" | Number in the first line |
| challenge_test | Proof by experiment | "I tried [X] for 30 days" | Duration or test framing |
| social_proof_authority | Credibility borrowing | "Dermatologist reacts to…" / "10k sold" | Title, credential, number |
| comparison_us_vs_them | Contrast | "$5 vs $50 [product]" | Split screen or side-by-side |
| sensory_asmr | Sensory pull | Close-up texture or sound | Macro shot, foley-heavy audio |
| price_value_shock | Anchoring | "This replaced my $200 [X]" | Price token in the first 2 s |
TikTok explicitly names suspense, surprise and emotion as hook levers. Pattern interrupt, direct question and immediate value prop are the common practitioner trio ([Improvado](https://improvado.io/blog/tiktok-advertising-guide)).

### 1.4 UGC ad formats (enum `format`; pick by the objection to overcome)
| format | Objection it answers | Skeleton |
|---|---|---|
| testimonial | "Can I trust this?" | Hook → problem → why I tried it → specific experience → result → CTA |
| problem_solution | "Do I need this?" | Relatable pain → agitate → product as fix → outcome |
| unboxing | "What is it really like?" | Package → reveal → first impression → first use |
| before_after | "Does it work?" | Result-first → process → proof |
| tutorial_demo | "How does it work?" | Outcome → steps → tip → CTA |
| pov_skit | "Is this for me?" | POV text → situation → product saves the moment |
| street_interview | "Do real people care?" | Mic-in-hand question → reactions → reveal |
| us_vs_them | "Why this vs. alternatives?" | Side-by-side → criteria → winner |
| green_screen_reaction | "Is the claim real?" | Creator over a screenshot/review/article → commentary |
| day_in_life | "Does it fit my life?" | Routine montage with natural product placement |
| founder_story | "Why this brand?" | Origin → mission → product |
| text_on_screen_ugly_ad | Low-fi native feel | Bold text over b-roll, minimal production |
Sources: [Promer styles](https://promer.ai/blog/different-styles-of-ugc-ads), [Cohley](https://www.cohley.com/ugc-video), [Hustler Marketing](https://www.hustlermarketing.com/types-of-ugc-ads-the-formats-that-work-for-ecommerce-brands-2026/). Practitioner consensus is that testimonial and problem/solution are the most reliable starting formats.

### 1.5 Outlier detection & metrics (formulas the research agent computes)
- **Outlier ratio** = views ÷ *median* views of the same account's last N=20 posts, excluding the target. Flag ≥3×, strong ≥10× (1of10's working rule: [method](https://1of10.com/blog/viral-youtube-video-ideas-outlier-method/)). Outlier.so's variant is `views/median − 1`. Store `baseline.method` so scores stay comparable.
- **Age-normalize.** Use views/hour in the first 48 h ("velocity", which vidIQ blends into its score: [vidIQ](https://vidiq.com/features/outliers/)), or compare against the baseline at equal age.
- **Reach beyond audience** = views ÷ followers at capture.
- **ER by views** = (likes+comments+shares+saves) ÷ views. **Shares/view** is the proxy for Mosseri's sends/reach. **Saves/view** captures utility content.
- **Owned only:** hook rate, hold rate, `reels_skip_rate`, average watch time, and % viewed.
- **Rule:** one outlier is an anecdote. Several outliers sharing a hook_type and format inside a niche is a **pattern**, so cluster before concluding.

### 1.6 Pattern card schema (what the agent fills; JSON in D1 + markdown mirror in memory)
```yaml
pattern_card:
  id, version, created_at, workspace_id, campaign_ids[]
  source: {platform, url, post_id, author_handle, author_followers, published_at, captured_at,
           access_method: api|oembed|operator_upload|manual, rights_attestation_id, language}
  metrics: {views, likes, comments, shares, saves, age_hours, views_per_hour_48h,
            er_by_views, shares_per_view, saves_per_view, views_per_follower,
            outlier: {ratio, baseline: {method: median_last_20, value, n}}, metrics_source}
  classification: {format, hook_types[], angle, awareness_stage: unaware|problem|solution|product|most,
                   funnel_stage: tofu|mofu|bofu, niche, product_category, emotion[]}
  hook: {spoken_paraphrase, on_screen_text, first_frame_desc, visual_action, audio_cue,
         time_to_hook_ms, open_loop: text|null}
  beats[]: {t_start, t_end, role: hook|context|problem|agitate|open_loop|demo|proof|objection|reveal|payoff|cta|loop,
            summary, on_screen_text, shot_type, cuts, evidence_frame_ref}
  retention_devices[]: open_loop|countdown|list|rehook|payoff_delay|loop_ending|captions|trend_sound
  production: {talent: on_cam|voiceover|faceless|avatar, setting, camera: selfie|handheld|tripod,
               cuts_per_10s, caption_style, music: original|trending|library|none, length_s, aspect}
  proof_elements[]: demo|before_after|numbers|social_proof|authority|guarantee
  cta: {type: soft|follow|link|shop|comment, text, at_s}
  why_it_works[]: {claim, mechanism, evidence_refs[beat|timestamp|metric], confidence: 0..1}
  transferable_template: "<brand-agnostic beat outline with slots>"
  do_not_copy[]: verbatim lines, characters, music, brand assets, distinctive bits
  compliance: {claims_made[], disclosures_seen[#ad|paid_partnership|ai_label], music_rights_risk, minors_present}
  performance_priors: {times_used, our_posts[], win_rate, last_updated}
```

---

## 2. Permitted research data sources

| Source | What you get | Auth / eligibility | Limits (as of 2026-11-07) | Ugecy verdict |
|---|---|---|---|---|
| **YouTube Data API v3** | Public video/channel stats incl. Shorts; channel uploads (median baseline) | API key (public data) or OAuth | `search.list` 100 calls/day bucket; other methods 10k units/day; `videos.list`/`channels.list`/`playlistItems.list` 1 unit ([quota](https://developers.google.com/youtube/v3/determine_quota_cost)) | **v1**. Best legal outlier source; avoid `search.list`, walk uploads playlists |
| **IG Graph `business_discovery`** | Other *professional* accounts: followers, media count, per-media like/comment/`view_count` | Operator's IG pro account + Facebook Login | Platform rate limits (~200 calls/hr/user); age-gated accounts excluded ([docs](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/business-discovery)) | **v1/v2**. Watchlist outliers on IG |
| **IG hashtag search** | `top_media` / `recent_media` per hashtag | Instagram Public Content Access feature (App Review) | **30 unique hashtags / rolling 7 days** per account; `media_url` omitted for copyrighted audio ([docs](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/hashtag-search)) | v2 |
| **TikTok Research API** | Public video/user data | Non-profit academic/research orgs only; commercial use ineligible | 1,000 req/day | **Not eligible** ([product](https://developers.tiktok.com/products/research-api/)) |
| **TikTok Commercial Content API** | Ads: dates, targeting, reach | Application, ~2 working days, any country | **EU ads only** ([product](https://developers.tiktok.com/products/commercial-content-api)) | v2 competitor-ad watch (`VERIFY` commercial ToS) |
| **TikTok Creative Center** (now "TikTok One Creative Suite") | Top Ads, trending hashtags/songs/creators (7/30/120-day) | Free web UI | No public API ([site](https://ads.tiktok.com/creative/creativeCenter)) | v1 **manual**. Operator browses and pastes links; don't scrape |
| **TikTok oEmbed / Display API** | oEmbed: title/author/thumbnail of pasted links. Display API: *operator's own* video stats | oEmbed public; Display API OAuth `video.list` | Display ~600 rpm/endpoint (3rd-party report, `VERIFY`) | v1 oEmbed for link cards; v2 owned metrics |
| **Meta Ad Library API** | `ads_archive` creatives & metadata | FB account + identity confirmation | `ad_type=ALL` only for ads reaching EU/UK (past year); spend/impressions only for political ads; no engagement metrics ([API](https://www.facebook.com/ads/library/api/), [Adspo](https://adspo.co/blog/meta-ad-library-api)) | v2 (EU proxy for competitor ads) |
| **Firecrawl** | Public web: brand/landing pages, reviews, blogs, docs | Firecrawl key | Refuses some domains (observed: developers.tiktok.com). Instagram Terms forbid automated collection without permission | v1 for **non-platform** pages (product pages, VOC, competitor sites), not social-platform scraping |
| **Whisper on Workers AI** | Transcript + timestamps | Workers AI binding | `@cf/openai/whisper-large-v3-turbo`, $0.000513/audio-min, zero data retention, batch ([model](https://developers.cloudflare.com/workers-ai/models/whisper-large-v3-turbo/)) | **v1** |
| **Vision on Workers AI** | Keyframe understanding (on-screen text, shot type, product on screen) | Workers AI | Catalog lists vision-capable models incl. Chinese `kimi-k2.6` and `deepseek-v4.1-flash-1017`, plus `llama-4-scout-17b-16e-instruct` and `mistral-small-3.1-24b-instruct` ([catalog](https://developers.cloudflare.com/workers-ai/models/)) | **v1**. Sample densely at 0–3 s (~4 fps), then scene-change frames (ffmpeg in a Container), cap ~24 frames |

**Ingest rule (proposed):** `access_method` must be `api | oembed | operator_upload | manual`. `operator_upload` requires a rights attestation (own content, licensed, or creator-submitted). Use no yt-dlp/TikTok-Api-style downloading by default. This needs a legal sign-off. It is the biggest product risk in "understand WHY it performs".

---

## 3. Official publishing APIs, labeling rules, adapter contract

### 3.1 Platform matrix
| | TikTok Content Posting | Instagram Reels | Facebook Page Reels | YouTube Shorts |
|---|---|---|---|---|
| Flow | **Direct Post:** `POST /v2/post/publish/video/init/` (`FILE_UPLOAD` chunks, or `PULL_FROM_URL` from a **verified domain**) → status fetch/webhook. **Upload (inbox):** `post_mode=MEDIA_UPLOAD`; user finishes in the app via inbox notification | `POST /{ig-id}/media` `media_type=REELS` + public `video_url` (or `upload_type=resumable`, FB Login only) → poll `status_code` (IN_PROGRESS/FINISHED/ERROR/EXPIRED) → `POST /{ig-id}/media_publish`. Container expires in 24 h | `POST /{page}/video_reels upload_phase=start` → bytes or `file_url` to `rupload.facebook.com` → `upload_phase=finish video_state=PUBLISHED` | `videos.insert` resumable upload. Square/vertical ≤3 min is classified as a Short |
| Scopes | Direct: `video.publish` (`VERIFY`); inbox: `video.upload` | IG Login: `instagram_business_basic`, `instagram_business_content_publish`. FB Login: `instagram_basic`, `instagram_content_publish`, `pages_read_engagement` | `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`; Page token with CREATE_CONTENT | `youtube.upload` |
| Review gate | **Audit.** Unaudited = `SELF_ONLY`, ≤5 posting users/24h, account must be private | App Review → Advanced Access (dev mode works for accounts with app roles) | App Review | Google OAuth verification for sensitive scopes. Since 2026-11-02 unverified projects are no longer forced private |
| Limits | 6 req/min per user token; ~15 posts/day/creator shared across apps (`spam_risk_too_many_posts`); inbox ≤5 pending/24h | **100/24h** per the guide vs **50** per the `media_publish` reference and `content_publishing_limit` → **read the quota at runtime** ([guide](https://developers.facebook.com/documentation/instagram-platform/content-publishing), [analysis](https://social-api.ai/blog/instagram-accounts-are-limited-to-100-api-published-posts)); error 9/2207042 | **30 API reels/24h per Page**; 3–90 s; 9:16; ≥540×960; 24–60 fps; error 613 ([guide](https://developers.facebook.com/documentation/video-api/guides/reels-publishing)) | 100 `videos.insert`/day bucket at 1 unit each (granular buckets since 2026-06-01); `thumbnails.set` 50 units |
| AI flag | `post_info.is_aigc=true` → "Creator labeled as AI-generated" | `is_ai_generated=true` on the container | None documented → caption disclosure + C2PA (`VERIFY`) | `status.containsSyntheticMedia=true` (since 2024-10-30) |
| Branded | Commercial-content toggle: "Your brand" → *Promotional content*; "Branded content" → *Paid partnership* (can't be SELF_ONLY) | `is_paid_partnership`, `branded_content_sponsor_ids` (FB Login only, max 2 sponsors) | Branded content tools (`VERIFY` API) | `paidProductPlacementDetails` (`VERIFY`) |
| Mandatory UX | Fetch `creator_info` before render; show nickname; privacy dropdown with **no default**; comment/duet/stitch unchecked and greyed if disabled; consent text ("Music Usage Confirmation" / "Branded Content Policy"); preview; express consent; **no watermark/branding**; editable title | Captions; ≤3 min | — | **Always set `privacyStatus` explicitly** (the default is now public); `selfDeclaredMadeForKids`; `publishAt` for native scheduling |

### 3.2 AI-content labeling rules (policy, not just API)
- **TikTok** requires labels on realistic AIGC. It auto-labels content carrying C2PA Content Credentials, and an auto label cannot be removed ([support](https://support.tiktok.com/en/using-tiktok/creating-videos/ai-generated-content), [newsroom](https://newsroom.tiktok.com/en-us/partnering-with-our-industry-to-advance-ai-transparency-and-literacy)).
- **Meta** applies an "AI info" label from industry signals (C2PA/IPTC) or self-disclosure ([Meta](https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/)).
- **YouTube** requires disclosure of realistic altered/synthetic content ([help](https://support.google.com/youtube/answer/14328491)). It carries forward C2PA ≥2.1 "made with AI" claims into "How this content was made" ([help](https://support.google.com/youtube/answer/15447836)).
- **US FTC 16 CFR 465** (effective 2024-10-21) bans fake consumer reviews and testimonials, including ones attributed to people who don't exist or lack the experience ([Federal Register](https://www.federalregister.gov/documents/2024/08/22/2024-18519/trade-regulation-rule-on-the-use-of-consumer-reviews-and-testimonials)). **AI-avatar "testimonials" must not pose as real customers.**
- **Implication:** set the API flag **and** preserve or sign C2PA (`contentauth/c2pa-python`, Apache-2.0). Never strip metadata. `VERIFY` whether Higgsfield outputs already carry C2PA.

### 3.3 `PublishingProvider` adapter (Python; one module per platform, each <500 lines)
```python
class PublishingProvider(Protocol):
    platform: Literal["tiktok", "instagram", "facebook_page", "youtube"]
    def capabilities(self) -> Capabilities: ...          # modes (direct|inbox|draft), max_duration_s, aspects,
                                                         # ai_flag_field, branded_fields, native_schedule: bool
    async def account_constraints(self, conn: Connection) -> AccountConstraints: ...
        # TikTok creator_info (privacy options, max duration, can_post); IG content_publishing_limit;
        # YouTube quota bucket remaining; FB 30/24h counter
    def validate(self, draft: PublishDraft, asset: MediaAsset, ac: AccountConstraints) -> list[PolicyIssue]: ...
        # duration/aspect/fps, ai_generated set (no default), privacy chosen, branded rules, caption length
    async def stage(self, conn, draft, asset) -> StagedPost: ...       # IG container / TT init / FB start / YT resumable
    async def publish(self, conn, staged: StagedPost, approval: ApprovalReceipt) -> PublishReceipt: ...
        # refuses unless approval.hash == sha256(draft+asset) and approval not expired
    async def status(self, conn, staged_or_receipt) -> PublishStatus: ...  # PROCESSING|PUBLISHED|FAILED(+platform code)
    async def metrics(self, conn, post_ref: str) -> PostMetrics: ...       # normalized: views, reach, likes, comments,
                                                                           # shares, saves, avg_watch_s, skip_rate_3s
    async def revoke(self, conn) -> None: ...

@dataclass
class PublishDraft:
    caption: str; title: str | None; hashtags: list[str]
    privacy: str                      # REQUIRED, operator-chosen from account_constraints options
    ai_generated: bool                # REQUIRED, no default → is_aigc / is_ai_generated / containsSyntheticMedia
    branded: BrandedContent | None    # your_brand / paid_partnership / sponsors
    interactions: Interactions        # comments/duet/stitch default False (TikTok rule)
    made_for_kids: bool | None        # YouTube required
    schedule_at: datetime | None      # Ugecy-owned scheduler (Durable Object alarm) unless native_schedule
    cover_ms: int | None; idempotency_key: str; campaign_id: str; pattern_card_ids: list[str]
```
Cross-cutting rules: token-bucket per (platform, account) in a Durable Object; retries only on documented transient codes; every stage/publish/status call goes to the audit log with the platform request id; publish is the only operation behind a mandatory HITL interrupt.

---

## 4. Similar open-source repos (GitHub metadata pulled 2026-11-07)

| Repo | ★ | License | Last push | What to reuse | License flag |
|---|---|---|---|---|---|
| [langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) | 31.1k | MIT | 2026-11-07 | Core harness: skills, memory, subagents, HITL | ✅ |
| [langchain-ai/paid-media-agent](https://github.com/langchain-ai/paid-media-agent) | 120 | Apache-2.0 | 2026-11-06 | **Closest analogue**: Deep Agents marketing agent with *reviewed changes*, reports, Slack | ✅ study first |
| [langchain-ai/social-media-agent](https://github.com/langchain-ai/social-media-agent) | 3.0k | MIT | 2026-11-07 | HITL post curation/scheduling interrupt flow (TS) | ✅ |
| [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | 140.5k | MIT | 2026-11-07 | Pipeline shape: script→TTS→subtitles→ffmpeg compose; subtitle timing | ✅ (skip stock-footage slop approach) |
| [ATH-MaaS/Pixelle-Video](https://github.com/ATH-MaaS/Pixelle-Video) | 29.8k | Apache-2.0 | 2026-06-14 | Modular step pipeline (ComfyUI); swap-in model nodes | ✅ |
| [linyqh/NarratoAI](https://github.com/linyqh/NarratoAI) | 11.7k | MIT | 2026-10-24 | Frame analysis → narration script prompts | ✅ |
| [Anil-matcha/AI-Youtube-Shorts-Generator](https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator) | 5.8k | MIT | 2026-11-06 | LLM highlight detection + Whisper + auto 9:16 crop | ✅ |
| [HKUDS/VideoAgent](https://github.com/HKUDS/VideoAgent) | 2.0k | MIT | 2026-07-22 | Agentic video understanding/remaking (beat extraction ideas) | ✅ |
| [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) | 19.1k | Apache-2.0 | 2026-09-30 | Subtitle segmentation/alignment; localization variants | ✅ |
| [m-bain/whisperX](https://github.com/m-bain/whisperX) | 25.1k | BSD-2 | 2026-10-22 | Word-level timestamps for the beat map (offline/eval) | ✅ |
| [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | 30.5k | Apache-2.0 | 2026-10-10 | Research-digest planner/report structure | ✅ |
| [contentauth/c2pa-python](https://github.com/contentauth/c2pa-python) | 108 | Apache-2.0 | 2026-11-05 | Sign/read C2PA manifests on outputs | ✅ |
| [RayVentura/ShortGPT](https://github.com/RayVentura/ShortGPT) | 8.1k | MIT | **2025-02-10 (stale)** | JSON "editing markup" timeline concept | ✅ reference |
| [inovector/mixpost](https://github.com/inovector/mixpost) | 3.9k | MIT | 2026-03-16 | Provider/quota/scheduling data model (PHP) | ✅ ideas |
| [Anil-matcha/Open-AI-UGC](https://github.com/Anil-matcha/Open-AI-UGC) | 418 | MIT | 2026-10-01 | AI-actor UGC flow (Next.js) | ✅ code / ⚠️ FTC risk |
| [gitroomhq/postiz-app](https://github.com/gitroomhq/postiz-app) | 41.1k | **AGPL-3.0** | 2026-11-06 | Read provider edge cases only | ⛔ no code copy (network copyleft) |
| [FujiwaraChoki/MoneyPrinterV2](https://github.com/FujiwaraChoki/MoneyPrinterV2) | 32.3k | **AGPL-3.0** | 2026-09-15 | — | ⛔ reference only |
| [brightbeanxyz/brightbean-studio](https://github.com/brightbeanxyz/brightbean-studio) | 2.6k | **AGPL-3.0** | 2026-10-25 | Python/Django scheduler patterns | ⛔ reference only |
| [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | 71.4k | Remotion License | 2026-11-07 | React video composition | ⚠️ paid company license above the free-tier team size (`VERIFY`) |
| [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload) | 16.3k | MIT | 2026-10-22 | — (browser-automation uploading) | ⛔ anti-pattern vs official APIs |
| [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | 70.5k | Custom (non-commercial) | 2026-11-05 | — | ⛔ license + ToS |
| [davidteather/TikTok-Api](https://github.com/davidteather/TikTok-Api) | 6.7k | MIT | 2026-08-24 | — (unofficial wrapper) | ⛔ ToS risk |
Archived and not to be built on: `langchain-ai/open_deep_research` (12.7k, MIT) and `langchain-ai/agent-inbox` (1.1k, MIT).

---

## 5. Features (GSD)

Complexity: S ≤2 days, M ≤1 week, L >1 week. IDs feed the planner.

### 5.1 Table stakes (users leave without these)
| ID | Feature | Cx | Depends on |
|---|---|---|---|
| T1 | Chat workspace: streaming agent turns, todo/progress, right rail (sources, tool activity, approvals, audit) | M | Deep Agents runtime, shadcn UI |
| T2 | Brand/campaign profile: product, audience, offers, **approved claims / forbidden claims**, tone, platforms | S | D1 schema |
| T3 | Ingest: paste URL (YouTube API / IG business_discovery / TikTok oEmbed) or upload a file with rights attestation → R2 | M | R2, platform keys |
| T4 | Media analysis: Whisper transcript + keyframe sampling + vision → beats, on-screen text, shot types | M | T3, Workers AI, ffmpeg Container |
| T5 | Pattern card extraction (§1.6) with timestamped evidence and confidence | M | T4 |
| T6 | Outlier scoring (median baseline, velocity) for YouTube + IG watchlists; manual metrics entry for TikTok | M | T3 |
| T7 | Original hook/script generation from cards, with a **similarity check** against the source transcript (block near-copies) | M | T5 |
| T8 | Creative brief export (markdown/PDF) for human creators or Higgsfield | S | T7 |
| T9 | Higgsfield job orchestration: submit → webhook/poll → R2 → review in UI ([docs](https://docs.higgsfield.ai/)) | M | Higgsfield key, Queues |
| T10 | Approval gates (HITL interrupt) on publish, spend and external writes; approval receipt bound to a content hash | M | Deep Agents HITL |
| T11 | Append-only audit log: tool calls, model/version, approvals, platform request ids | S | D1 + R2/Logpush |
| T12 | OAuth connections per platform; encrypted tokens; refresh; revoke | M | App registrations, Secrets |
| T13 | `PublishingProvider` adapters + status polling (§3.3) | L | T10–T12, platform review |
| T14 | Disclosure controls: AI flag (required), branded/paid partnership, TikTok-mandated post UI | S | T13 |
| T15 | Quota-aware scheduler (per-account token buckets; IG `content_publishing_limit`) | M | Durable Objects, T13 |
| T16 | Owned-post metrics pull (IG insights incl. `reels_skip_rate`, YouTube Analytics, TikTok Display) | M | T12 |

### 5.2 Differentiators (why Ugecy over Postiz + ChatGPT)
| ID | Feature | Cx | Depends on |
|---|---|---|---|
| D1 | **Pattern Library memory**: persistent cross-campaign cards + clusters ("5 outliers share result_first + us_vs_them in skincare"); agent recalls it on every brief | M | T5, Deep Agents long-term memory, Vectorize |
| D2 | **"Why it worked" explainer**: beat timeline with frames, mechanism + confidence per claim, "what to transfer / what not to copy" | M | T4, T5 |
| D3 | **Script tournament**: N variants (hook × format × angle) judged by a critic subagent with Rubric-grading middleware (hook strength, clarity, claim compliance, originality, platform fit); pairwise Elo; top 3 to the human | M | T7, rubric middleware |
| D4 | **Brand voice + claims memory**: learns from the operator's HITL edits/rejections (diffs → style rules); hard-blocks unapproved claims | M | T2, T10 |
| D5 | **Playbook Skills**: one `SKILL.md` per format (§1.4) and per platform (constraints, disclosure, specs), loaded on demand | S each | Deep Agents skills |
| D6 | **Compliance preflight subagent**: platform specs, AI/branded flags, music rights, watermark ban, FTC testimonial rule, minors, medical/financial claims | M | T13, D4 |
| D7 | **Experiment loop**: hypothesis card → 3–5 variants → publish → metrics at 24 h/72 h/7 d (scheduled re-entry) → updates `performance_priors` → proposes the next test | L | T13, T16, D1 |
| D8 | **Scheduled research digest**: weekly watchlist outliers (YouTube + IG), new patterns, hook-fatigue alerts (rising skip rate) | M | T6, Cron Triggers |
| D9 | **Hook-swap remix**: keep a winning body; generate 5 new 0–3 s hooks (Higgsfield clip + recut) | M | T9, D7 |
| D10 | **Multi-platform cut planner**: one master script → per-platform variants within limits (FB 3–90 s, TikTok `max_video_post_duration_sec`, Shorts ≤3 min) | S | T13 capabilities |
| D11 | **Provenance by default**: C2PA manifest + API AI flags + audit receipt per post | M | c2pa-python, signing cert |
| D12 | Model router with recorded rationale (Chinese Workers AI models first) + run cost/quota meter | S | Architecture |
| D13 | Competitor ad watch (EU): Meta Ad Library + TikTok Commercial Content API | M | Identity verification |
| D14 | Retention beat-map visual (timeline of hook/proof/CTA, cut density, text overlays) | M | T4, UI |

### 5.3 Anti-features (deliberately NOT built)
| ID | Anti-feature | Reason |
|---|---|---|
| A1 | Account creation, warming, multi-account/detection evasion | Out of scope; ToS and legal exposure |
| A2 | Scraping TikTok/IG (TikTok-Api, MediaCrawler, logged-in crawling) | Instagram Terms forbid automated collection without permission; MediaCrawler license; brittle |
| A3 | Browser/device automation as a publishing path where an official API exists | Bypasses review, consent UX and audit; TikTok requires express per-post consent. Keep Glasshand to consented device sessions with action receipts |
| A4 | Reposting or near-cloning third-party videos/scripts | YouTube "inauthentic content" (2025-07-15); TikTok: copying from other platforms "is not acceptable"; IG demotes unoriginal content |
| A5 | AI avatars presented as real customers / fake reviews | FTC 16 CFR 465; label AI talent as such |
| A6 | Auto-publish without a human approval, or bulk "post 50/day" | Platform caps (TikTok ~15/day, FB 30, IG 50–100); spam signals; mass-production policies |
| A7 | Engagement automation (auto-comment, follow/unfollow, DM blasts) | Spam/integrity policies; not UGC ops |
| A8 | AI flag defaulting to off; stripping C2PA/metadata | Violates TikTok, Meta and YouTube disclosure rules; auto-labels can't be undone anyway |
| A9 | Ugecy watermark/branding on posts | TikTok guidelines prohibit it; IG penalizes other-app watermarks |
| A10 | A single opaque "virality score" sold as prediction | Misleading; show evidence, baselines and confidence |
| A11 | Rebuilding a full social-suite clone (Postiz) | Scope creep; AGPL; the adapter + queue is enough |

### 5.4 "Wow" ideas that Deep Agents uniquely enable
- **Living swipe file.** `/memories/patterns/<niche>/<id>.md` plus D1 rows. The agent writes a card after every analysis and cites prior cards ("this matches pattern #42, which won 3 of 4 tests for you").
- **Critic tournament with transparent reasoning.** A generator subagent produces variants. A judge subagent scores them against a rubric. A red-team subagent hunts compliance problems. The operator sees the bracket and the judge's reasons, and overrides become rubric weights (D3+D4).
- **Self-scheduling experiments.** After publishing, the agent schedules its own wake-ups (24 h/72 h/7 d). It pulls metrics, writes a "learning" note to memory and proposes the next variant, which waits for approval (D7).
- **Playbook skills marketplace.** Skills are folders, so agencies can author house playbooks (e.g. a "street-interview for DTC supplements" skill) without code (D5).
- **Hook-fatigue radar.** When `reels_skip_rate` on owned posts rises week over week, the agent proposes a hook-swap batch (D9).
- **One-message campaign kickoff.** "Here are 5 links + our product page." The agent fans out parallel analyst subagents, clusters patterns, writes 3 briefs and queues Higgsfield drafts. Everything lands in one approval tray.

---

## 6. Recommendation — v1 (demoable this week) vs v2

**v1 demo story:** paste 3–5 links (or upload files), get pattern cards with a "why it worked" timeline, generate original scripts, run the tournament, write a brief, produce a Higgsfield draft, approve it, publish to YouTube Shorts and Instagram with the AI flag set, and show the audit trail.

| v1 (this week) | Notes |
|---|---|
| T1, T2, T10, T11 (minimal) | Chat + approval tray + audit list |
| T3 (YouTube URL via Data API, any URL via oEmbed/manual, file upload with attestation), T4, T5 | Whisper turbo + one Chinese vision model; ≤24 frames |
| T6 for YouTube only (median-of-last-20 baseline) | Cheapest legal outlier data |
| T7 + D3 (3–5 variants, one critic subagent with rubric) + T8 | The visible "wow" in the demo |
| D5 for 3 formats (testimonial, problem_solution, us_vs_them) + platform skill for YT/IG | Pure markdown |
| D1-lite (save/search cards) | D1 table + memory files; Vectorize optional |
| T9 one Higgsfield model end-to-end | Webhook → R2 → preview |
| T13/T14 for **YouTube Shorts** (public, explicit `privacyStatus`, `containsSyntheticMedia`) + **Instagram Reels** on the operator's own pro account in dev mode (`is_ai_generated`) | TikTok: demo `SELF_ONLY` or inbox upload only; start the audit now |

**v2 (after review approvals):** TikTok public Direct Post (post-audit) with the mandated UI; Facebook Page Reels; T15 scheduler with quotas; T16 metrics + D7 experiment loop; D8 weekly digest; D4 learned brand voice; D6 full compliance subagent; D11 C2PA signing; D9 hook-swap; D10 cut planner; D13 EU competitor-ad watch; IG hashtag research; D14 beat-map visual; team roles.

**Week-1 non-code actions (critical path):** register TikTok app + Content Posting API and submit the audit with UX screenshots; Meta app with Instagram/Pages products, business verification and App Review for `instagram_business_content_publish` and `pages_manage_posts`; Google Cloud project + OAuth consent verification for `youtube.upload`; legal review of the ingest rule (§2).

---

## 7. Open questions / VERIFY list
1. TikTok Direct Post scope name (`video.publish`) and whether `is_aigc` is also honored on inbox (MEDIA_UPLOAD) posts.
2. Instagram publish quota: 100 (guide) vs 50 (reference). Treat `content_publishing_limit` as truth.
3. Facebook Page Reels: is there an API AI-disclosure parameter? If not, rely on C2PA plus caption text.
4. Do Higgsfield outputs embed C2PA? If not, sign with `c2pa-python` (needs a signing certificate).
5. Commercial-use terms for TikTok Commercial Content API and Meta Ad Library data in a paid product.
6. Is YouTube "Viewed vs swiped away" exposed in the YouTube Analytics API, or Studio-only?
7. Legal position on analyzing operator-uploaded copies of third-party videos (fair-use style analysis, no redistribution).
8. Remotion license threshold, if Remotion is chosen for composition (another researcher's dimension).
