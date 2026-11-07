---
name: phone-research
description: "Research short-form UGC on a real iPhone (Glasshand) in read-only mode: open TikTok, Instagram Reels or YouTube Shorts via Spotlight, search a niche, observe up to 12 posts at human pace, read metrics, stop on login walls or captchas, and turn observations into outlier-based pattern cards. Use whenever the research-analyst has a ready Glasshand device (read-only research on the real phone only)."
---
# Phone research playbook

## Preconditions
- `device_status`: provider glasshand, mode live, a device with ready true. Mode off = no phone: tell the operator to connect Glasshand in the Device tab.
- `device_start_session(goal, allowed_apps, purpose="research")` once; the operator approves. Budget is 60 steps and 12 observed posts.

## Read-only rules
Allowed: Home, swipe, tap to open search, results and posts, type a search query (80 characters at most), screenshot, observe.
Never: like, follow, comment, share, save, DM, post, buy, log in, sign up, enter codes, change settings, open notifications or messages. `device_commit` is refused. Do not tap the Like/Comment/Share/Save column; read its numbers instead.

## Stop conditions (stop, report, do not work around)
Login wall or "Log in to continue", captcha or puzzle, age gate, verification code, "unusual activity" or "try again later", account or permission prompt, a human taking control (`control_taken`). Report the screen description and what was collected so far.

## Human pace
`device_next_post` already dwells 2 to 4 s. Let each post play before `device_observe`. Never loop faster, never batch-swipe. One action, then `device_screenshot`, then the next. If a tap misses twice, go Home and re-orient instead of guessing coordinates.

## Opening an app (iOS)
`device_home` -> `device_swipe` from (0.5,0.4) to (0.5,0.8) opens Spotlight -> `device_type` "TikTok" (or "Instagram", "YouTube") -> `device_screenshot` -> tap the app result. Dismiss any tip card or notification prompt with the visible Not Now / Close, never Allow or Log in.

## Search flows
- TikTok: magnifier at the top right of For You -> field -> type the query -> Search. Tabs: Top (default, ranked), Videos, Users. Open Top, then the most-viewed tiles. View counts show on grid tiles; likes, comments, shares and saves sit in the right column of the post.
- Instagram Reels: Search tab (magnifier) -> field -> query -> Reels tab in results. Views show on grid tiles; like and comment counts in the right column; shares (paper plane) often show a count; saves are usually hidden, record `unknown`.
- YouTube Shorts: magnifier -> query -> Filters -> Shorts, or open a Shorts result. Likes and comments are in the right column; views appear in the description sheet or on the grid; shares show a label, not always a count.

## Reading metrics
`device_observe` returns numbers (1.2M = 1200000, 45.3K = 45300). Missing = absent key, write `unknown`. Never estimate. Views on the grid and the post may differ slightly; keep the post value. Record the query, the app and the tab you used (Top, Videos, Reels).

## How many and what to record
Per query observe 4 to 8 posts, max 12 per session, over 2 to 3 query variants (product word, problem word, "ugc ad" or "review"). For each post keep: creator, hook_guess (paraphrase), on_screen_text, caption, metrics, audio, format_guess, is_ad, `device://` source URL, rank in results. Flag `is_ad` posts separately: sponsored creative is a different baseline from organic.

## From observations to pattern cards
1. Baseline: you cannot see the account's last 20 posts cheaply. Use the median views of the posts you observed in the same query as the baseline and say so (`baseline.method = observed-query-median`). Outlier ratio = views / that median; 3x outlier, 10x strong. If you opened a profile and saw a median, use it instead.
2. Engagement shape: shares/views (distribution), saves/views (utility), comments/views (debate), likes/views. A high shares ratio with ordinary views often beats raw views.
3. Classify the hook with the `ugc-hook-extraction` taxonomy (curiosity_gap, pattern_interrupt, negative_warning, contrarian, result_first, callout_question, pov_relatable, storytime, listicle_number, challenge_test, social_proof_authority, comparison_us_vs_them, sensory_asmr, price_value_shock) and the format enum. Treat `hook_guess` and `format_guess` as a first read: confirm against the screenshot.
4. A pattern needs at least 3 observed outliers sharing hook type and format. One viral post is an anecdote: say so, confidence under 0.5.
5. Write cards per the research-analyst format. Cite `device://` URLs and the exact observed numbers; paraphrase hooks; put verbatim lines and creators' distinctive bits under `do_not_copy`. Note ad labels, music rights risk and minors in compliance notes.
6. Say in the summary which numbers were observed on the phone, which came from the web, and the date.
