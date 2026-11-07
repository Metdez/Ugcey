---
name: higgsfield-prompting
description: "How to turn an approved UGC script into a Higgsfield ad that looks like real phone video: one first-frame still, then one multi-shot generation for the whole ad (Kling 3.0 multi-shot for previews and live demos, Seedance 2.5 timed shots for finals). Covers shot planning, endpoints, the exact prompt shapes and argument rules. Read before calling estimate_media_cost or generate_media."
---
# Higgsfield prompting for UGC

Every rule here comes from a test or an official guide (ByteDance's Seedance 2.5 prompt guide, Higgsfield's own skills and API docs, side-by-side runs on 2026-11-07). Follow them literally.

## 1. Plan: one still, one multi-shot clip
A 15 s ad is 3 shots of about 5 s, generated in ONE call with the cuts inside it. Tested: both Kling 3.0 multi-shot and Seedance 2.5 timed shots cut within half a second of the requested times and kept the same person, outfit and bottle across all three shots. This is cheaper and more consistent than separate clips that must be joined.
- Translate the script; do not copy camera-crew details (frame rates, lenses, takes). Merge beats into 3 shots for 15 s (5 or 6 for 30 s).
- One setting, one subject action and at most one camera move per shot.
- The first shot starts from the still, so the still must show the person, product and backdrop of shot 1.
- On-screen text, price tags, captions and the exact product label are added in the edit. Never ask a model to render text.
- If the script needs speech, keep it to one short line or move it to a caption. Spoken lines are not yet tested on this pipeline; say so in your reply.

## 2. Who is on screen
- No real creator with recorded consent: use the script's **fictional AI creator** (an invented adult, never a real or famous person, never a minor), described with the same words in the still and every shot. They demonstrate; they never claim personal use or results.
- Hands-only or product-only only when the script or operator asks for it; keep hand motion slow and small.

## 3. Pick the endpoint
| Need | endpoint_id |
|---|---|
| First-frame still without product photos | `higgsfield-ai/soul/v2/standard` |
| First-frame still with the real product (operator supplied photos) | `marketing-studio/image/flare` with `reference_asset_ids` = the product photo ids (section 3a) |
| End-frame still with the real product, legible | `marketing-studio/image/flare` with `reference_asset_ids` = the product photo ids, then the first-frame still (section 3a) |
| Preview, iteration or anything generated live | `kling-video/v3.0/std/image-to-video` with `multi_shots` (720p, about 3.5 min and $1.60 for 15 s) |
| Final ad | `bytedance/seedance-2.5/image-to-video` with timed shots in the prompt (720p, about $6.90 for 15 s; slowest) |

Do not use Wan as a draft for Seedance or Kling: it does not predict them. Do not use reference-to-video unless you hold completed reference assets.

## 3a. With product photos
The operator's photos are the only reliable source of the real label: generated labels come out as garbled text (tested), and ByteDance's guide says exact label text needs a supplied image. Product photos arrive as asset ids ("Product photos attached: ..."); pass them as `reference_asset_ids`, never as URLs.
1. **First-frame still**, `marketing-studio/image/flare`, `args: {"enhance_prompt": false, "aspect_ratio": "9:16", "resolution": "2k", "quality": "high"}`. Prompt: the shot 1 pose with the creator holding "the product from the reference image", label facing the camera, "the product exactly as in the reference image", then backdrop, light and phone-photo style as in section 4. Do not describe the label wording. Tested: Flare, Sunburst and 2.0 Alpha all reproduced a printed wordmark exactly; Flare was fastest and most phone-like.
2. **End-frame still**, same endpoint and args, after the first still is completed. `reference_asset_ids` = the product photo ids first, then the first-frame still id (without the person reference it drew a different woman). Prompt: "the same woman from the last reference image" holds "the product from the first reference image" upright and close to the lens, filling the centre of the frame, label facing the camera and sharp; she is softly out of focus behind it, same outfit, backdrop and light.
3. **Clip**: `image_asset_id` = first-frame still, `end_image_asset_id` = end-frame still. The last shot's action must lead into that frame ("she brings the product close to the lens and holds it still"). Shots in between keep the product at arm's length or farther, label toward the camera; never a close-up of small text, never a rotation.
Not yet verified on our pipeline: how exactly Kling multi-shot lands on the end frame. Say so in your reply.

## 4. Still prompt (Soul)
Shape, about 40 to 80 words, plain sentences, no motion words:
`[the creator, same words as the script] [pose for shot 1: how they hold the product, one hand if it is a selfie] [the product: shape, material, colour] [one plain, specific backdrop] [light] [phone-photo style]`
- Backdrop: plain and nameable, for example "plain white tiled wall". Fixtures such as toilet paper holders, faucets, rails and shelf brackets come out malformed.
- Soul adds a label with garbled text to bottles and boxes even when the prompt says "unlabeled". Without product photos, accept that the label is fake and say in your reply that the real label must replace it in the edit or that product photos are needed. Never describe label wording.
- Style words that work: "front-camera selfie photo", "natural skin texture", "soft window daylight", "slightly imperfect framing". Avoid "cinematic", "8k", "masterpiece".
- Positive phrasing only: write what you want ("bare wall behind her"), not lists of what to avoid.
- Put `aspect_ratio: "9:16"` and `resolution: "1080p"` in `args`.

## 5. Multi-shot clip prompts (image-to-video)
The still fixes the look of shot 1. Each shot describes, in this order:
1. Camera: what it is framed on and how it moves. Example: "Handheld front-camera selfie at arm's length, slight hand shake."
2. Start state, one slow and small operation, end state. Example: "She holds the bottle beside her cheek with one hand, then slowly brings it a little closer to the lens and gives a small closed-mouth smile."
3. Expression as small visible cues ("brows lift slightly"), never strong emotion words such as "shocked" or "obsessed".

**Kling** (`args.multi_shots: true`): `args.multi_prompt` is a list of `{"prompt": ..., "duration": 5}` items (each prompt at most 512 characters, durations summing to the ad length). The top-level `prompt` is one short paragraph naming the same person, outfit, product and backdrop for all shots, then the sound line: "She does not speak. Quiet room tone only. No music. No subtitles or on-screen text."

**Seedance** (`args.duration` 15): one prompt. First a one-sentence summary, then `Shot 1 (0-5s): ...`, `Shot 2 (5-10s): Cut to ...`, `Shot 3 (10-15s): Cut back to ...`, then one line listing what stays the same in every shot (person, outfit, hair, product, backdrop, light), then the sound line: "Her mouth stays naturally closed, with no narration and no music; only quiet [room] tone is heard. No subtitles or on-screen text appear."

Rules for both:
- Selfie shots allow one-handed actions only. Two-handed demos are framed as "the phone is propped on the counter".
- Do not re-describe what the still shows in shot 1, and do not put aspect ratio, resolution, model names or quality words in prompts.
- Do not rotate a labelled product; move it toward or away from the lens. Avoid falling, tipping or splashing objects.
- Keep the camera facing the same backdrop in every shot (closer or wider, not side-on). Side and over-the-shoulder angles bring in mirrors, reflections and a different wall colour.
- Give shot 1 an action the still already sets up (hold, lift, bring closer). Kling cut our first agent-written shot to 1.75 s when its action (pressing a dropper with a thumb) did not fit the still.

## 6. Arguments and chaining
- Everything except `model`, `prompt`, `kind`, `image_asset_id`, `reference_asset_ids` and `end_image_asset_id` goes inside `args`. Top-level extras are dropped.
- `end_image_asset_id` becomes Kling's `last_image_url` or Seedance's `end_image_url` automatically; only image-to-video endpoints take it.
- Kling: `args: {"duration": 15, "sound": "on", "multi_shots": true, "multi_prompt": [...]}`. Seedance: `args: {"duration": 15, "resolution": "720p", "generate_audio": true}`.
- Generate the clip only after `check_media_job` reports every still it uses completed, and pass them as `image_asset_id` (and `end_image_asset_id`). Use asset ids exactly as tools return them; never invent one and never pass an empty id.

## 7. Check every prompt before submitting
- No contradictions (for example "fingertips" and "no hands").
- The person and product are described the same way in the still and every shot.
- Each shot has one action, at most one camera move and a clear end state; durations add up.
- No text, labels or prices for the model to render.

Every asset is AI-generated: set `ai_generated: true` in the manifest so publishing applies the platform AI label. Higgsfield deletes outputs after 7 days.
