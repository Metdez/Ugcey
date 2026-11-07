---
name: higgsfield-prompting
description: "How to turn an approved UGC script into a Higgsfield ad that looks like real phone video: one first-frame still (plus a real-product end frame when product photos exist), then one Seedance 2.5 generation with timed shots for the whole ad (Kling 3.0 multi-shot only when speed matters). Covers shot planning, endpoints, the exact prompt shapes and argument rules. Read before calling estimate_media_cost or generate_media."
---
# Higgsfield prompting for UGC

Every rule here comes from a test or an official guide (ByteDance's Seedance 2.5 prompt guide, Higgsfield's own skills and API docs, side-by-side runs on 2026-11-07). Follow them literally.

## 1. Plan: one still, one multi-shot clip
A 15 s ad is 3 shots of about 5 s, generated in ONE call with the cuts inside it. Tested: Seedance 2.5 timed shots cut within half a second of the requested times in every run and kept the same person, outfit and product; Kling 3.0 multi-shot did in some runs but ignored the cuts in another (section 3). This is cheaper and more consistent than separate clips that must be joined.
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
| The ad (default) | `bytedance/seedance-2.5/image-to-video` with timed shots in the prompt. `resolution` "480p" for previews (about $3.10 and 2.5 min for 15 s), "720p" when the operator asks for the final (about $6.90) |
| Speed matters more than consistency | `kling-video/v3.0/std/image-to-video` with `multi_shots` (720p, about $1.60 and 2.5 min for 15 s) |

Why Seedance: across our tests it was the most consistent. In the product test it cut on time, kept the shade right and on, and showed no glitches; Kling on the same frames skipped the cuts entirely (one long take) and briefly added a dark spot to the creator's cheek.

Do not use Wan as a draft for Seedance or Kling: it does not predict them. Do not use reference-to-video unless you hold completed reference assets.

## 3a. With product photos
The operator's photos are the only reliable source of the real label: generated labels come out as garbled text (tested), and ByteDance's guide says exact label text needs a supplied image. Product photos arrive as asset ids ("Product photos attached: ..."); pass them as `reference_asset_ids`, never as URLs.
1. **First-frame still**, `marketing-studio/image/flare`, `args: {"enhance_prompt": false, "aspect_ratio": "9:16", "resolution": "2k", "quality": "high"}`. Prompt: the shot 1 pose with the creator holding "the product from the reference image", label facing the camera, "the product exactly as in the reference image", then backdrop, light and phone-photo style as in section 4. Do not describe the label wording. Tested: Flare, Sunburst and 2.0 Alpha all reproduced a printed wordmark exactly; Flare was fastest and most phone-like.
2. **End-frame still**, same endpoint and args, after the first still is completed. `reference_asset_ids` = the product photo ids first, then the first-frame still id (without the person reference it drew a different woman). Prompt: "the same woman from the last reference image" holds "the product from the first reference image" upright and close to the lens, label facing the camera and sharp, same outfit, backdrop and light. If the ad shows the product's effect, she is visibly wearing it here, fully and evenly applied (for a lipstick: "both lips fully and evenly wearing the lipstick from the first reference image in exactly its [true shade] shade, matching the swatch"), so the ad ends on the correct, finished result. Never end on a partial application.
3. **Clip**: `image_asset_id` = first-frame still, `end_image_asset_id` = end-frame still. The last shot keeps natural motion all the way through (slight handheld sway, a blink, a small smile or laugh) and reaches the end-frame pose only in its final half second: "she keeps moving naturally and, in the last moment, brings the product close to the lens". Never write "hold still", "holds it steady" or "ending on the exact pose": in our first full run that wording froze the last 4 seconds into a still photo. The end frame must also differ from the opening pose (closer to the lens, a different smile) so the clip has somewhere to travel. Keep the last shot to 3 or 4 s. Shots in between keep the product at arm's length or farther, label toward the camera; never a close-up of small text, never a rotation.
Tested: Kling and Seedance clips given both frames started on the first still and ended on a frame that matched the end-frame still almost exactly, wordmark sharp.
- **Show the product's effect, anchored.** Showing it in use sells. Unanchored, the model invents the result (a mauve lipstick turned the lips bright red and the colour vanished in the next shot). Anchored, it worked: the end-frame still shows the creator wearing the true shade, every shot after the moment of use names the colour ("muted rosy-mauve, the same colour as the lipstick"), and the clip prompt says it "stays on her lips for the rest of the video". With that, Seedance kept the right shade on from application to the last frame. Keep application gestures gentle (lips gently parted, no open mouth).
- **Apply it fully, never half.** Apply to the whole area in one shot (for a lipstick: "glides it slowly once across her lower lip and once across her upper lip, then presses her lips together"), so every shot after the moment of use shows the finished look. Never produce a split or half-and-half comparison on one face (half the lips, one eye, one cheek), even when the script asks for it: in the 2026-11-07 live run a split-lip script gave a hard vertical seam down the lips and, anchored to a half-done end frame, the ad ended half done. If the script asks for a split, apply it fully in the stills and the clip and say so in your reply.

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

**Seedance** (`args.duration` 15): one prompt. First a one-sentence summary, then `Shot 1 (0-5s): ...`, `Shot 2 (5-10s): Cut to ...`, `Shot 3 (10-15s): Cut back to ...`, then one line listing what stays the same in every shot (person, outfit, hair, product, backdrop, light), then the sound line: "Her mouth stays naturally closed, with no narration and no music; only quiet [room] tone is heard. No subtitles or on-screen text appear." When the product goes on the lips, write "Her mouth stays naturally closed except while applying" (the wording of the tested 02c run); the plain line contradicts the application shot.

Rules for both:
- Selfie shots allow one-handed actions only. Two-handed demos are framed as "the phone is propped on the counter".
- Do not re-describe what the still shows in shot 1, and do not put aspect ratio, resolution, model names or quality words in prompts.
- Do not rotate a labelled product; move it toward or away from the lens. Avoid falling, tipping or splashing objects.
- Keep the camera facing the same backdrop in every shot (closer or wider, not side-on). Side and over-the-shoulder angles bring in mirrors, reflections and a different wall colour.
- Give shot 1 an action the still already sets up (hold, lift, bring closer). Kling cut our first agent-written shot to 1.75 s when its action (pressing a dropper with a thumb) did not fit the still.

## 6. Arguments and chaining
- Everything except `model`, `prompt`, `kind`, `image_asset_id`, `reference_asset_ids`, `end_image_asset_id` and `brief_path` goes inside `args`. Top-level extras are dropped.
- `end_image_asset_id` becomes Kling's `last_image_url` or Seedance's `end_image_url` automatically; only image-to-video endpoints take it.
- Kling: `args: {"duration": 15, "sound": "on", "multi_shots": true, "multi_prompt": [...]}`. Seedance: `args: {"duration": 15, "resolution": "480p", "generate_audio": true}` for previews ("720p" only when the operator asks for the final).
- Generate the clip only after `check_media_job` reports every still it uses completed, and pass them as `image_asset_id` (and `end_image_asset_id`). Use asset ids exactly as tools return them; never invent one and never pass an empty id.

## 7. Check every prompt before submitting
- No contradictions (for example "fingertips" and "no hands", or "mouth stays closed" with a lip application shot).
- After the moment of use, the effect is fully applied in every shot and in the end-frame still; nothing is half done.
- The person and product are described the same way in the still and every shot.
- Each shot has one action, at most one camera move and a clear end state; durations add up.
- No text, labels or prices for the model to render.

Every asset is AI-generated: set `ai_generated: true` in the manifest so publishing applies the platform AI label. Higgsfield deletes outputs after 7 days.
