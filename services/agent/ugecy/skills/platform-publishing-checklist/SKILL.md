---
name: platform-publishing-checklist
description: "Per-platform publishing checklist for TikTok, Instagram Reels, Facebook Reels and YouTube Shorts covering AI-content label flags, paid-partnership toggles, posting caps, format limits and mandatory steps. Use before calling publish_post or when scheduling posts."
---
# Platform publishing checklist

Run this before every `publish_post`. Publishing in this studio goes only to the operator's own connected accounts and always needs operator approval.

## AI-content labels (set the flag AND disclose honestly)
| Platform | Flag | Notes |
|---|---|---|
| TikTok | `post_info.is_aigc = true` | Realistic AI content must be labeled. Content with C2PA credentials is auto-labeled and the auto label cannot be removed. |
| Instagram | `is_ai_generated = true` on the container | Meta also applies "AI info" from C2PA/IPTC signals. |
| YouTube | `status.containsSyntheticMedia = true` | Required for realistic altered or synthetic content. |
| Facebook Reels | no documented API flag | Disclose in the caption; preserve C2PA metadata. |
Never strip metadata or hide that media is AI-generated.

## Paid partnerships
- TikTok: commercial-content toggle ("Your brand" = promotional; "Branded content" = paid partnership, which cannot be private-only).
- Instagram: `is_paid_partnership`, `branded_content_sponsor_ids` (Facebook Login only, max 2).
- YouTube: paid product placement setting in upload details.
- Everywhere: `#ad` or the platform label in the first line of the caption (the fold hides the rest).

## Format limits
- TikTok: fetch creator info first, privacy choice has no default, no watermark or added branding, comment/duet/stitch only if enabled.
- Instagram Reels: caption up to 2,200 characters, up to 3 minutes. Public `video_url`, poll container status until FINISHED, then publish; the container expires in 24 hours.
- Facebook Reels: 3 to 90 s, 9:16, at least 540x960, 24 to 60 fps.
- YouTube Shorts: vertical or square up to 3 minutes; always set `privacyStatus` explicitly and `selfDeclaredMadeForKids`.

## Posting caps (be well under them)
TikTok about 15 posts per day per creator, 6 requests per minute; unaudited apps post `SELF_ONLY` privately. Instagram 50 to 100 API posts per 24 h (read the quota at runtime). Facebook 30 API Reels per 24 h per Page. YouTube has a daily quota; uploads cost units. House rule: at most 3 posts per account per day.

## Pre-flight
1. Asset status is `completed` and approved; review verdict is `approved`.
2. Account is in `list_connected_accounts`.
3. Caption: disclosure first, 1 to 4 relevant hashtags, no banned claims.
4. `ai_disclosure=true` for AI media. Paid or gifted: `#ad`.
5. Schedule off-peak overlap with existing posts; do not post duplicates across accounts at the same minute.
6. After posting, call `get_post_status` and report the result. Direct API publishing is not connected: when `publish_post` says so, hand the post to the device-operator to publish from the iPhone (with approvals).
