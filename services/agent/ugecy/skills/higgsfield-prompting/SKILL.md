---
name: higgsfield-prompting
description: "How to write Higgsfield image and video generation prompts for 9:16 UGC (subject, setting, camera, lighting), which model endpoint to choose and which arguments matter. Use before calling estimate_media_cost or generate_media, or when turning a shot list into prompts."
---
# Higgsfield prompting for UGC

Always take model ids from `list_media_models`; the table below is the current catalog for orientation.

## Choosing a model
Ids come from `list_media_models`; this table is for orientation. Prices are rough, the live estimate decides.
| Need | endpoint_id | Key args | About |
|---|---|---|---|
| Creator or product still, 9:16 | `higgsfield-ai/soul/v2/standard` | prompt, aspect_ratio `9:16`, resolution 720p/1080p, batch_size 1 or 4, seed, enhance_prompt | cents |
| Product ad still | `marketing-studio/image` | prompt, image_urls (up to 16), aspect_ratio `9:16`, resolution 1k/2k/4k, quality low/medium/high | $0.2 |
| Ad concepts from product images | `higgsfield/ads-studio/v1.0` | prompt (brief), image_urls (up to 10), niche, target_audience, language, batch_size 1-8 | no estimate |
| Text to video with audio | `bytedance/seedance-2.5/text-to-video` | prompt, aspect_ratio `9:16`, duration 4-30, resolution 480p/720p/1080p, generate_audio | $0.46/s at 720p |
| Animate a still | `bytedance/seedance-2.5/image-to-video` | image_asset_id, prompt, duration 4-30, resolution, generate_audio (ratio follows the still) | $0.46/s at 720p |
| Consistent character across shots | `bytedance/seedance-2.5/reference-to-video` | reference_asset_ids (up to 30 images), prompt, duration, aspect_ratio `9:16` | $0.46/s at 720p |
| Multi-shot clip | `kling-video/v3.0/std/image-to-video` | image_asset_id, prompt, duration 3-15, sound on/off, multi_shots true + multi_prompt (up to 6 x {prompt, duration}) | $0.54 for 5 s |
| Cheap motion draft | `alibaba/wan-3.0/image-to-video` | image_asset_id, prompt, duration 2-30, resolution 480p | $0.05/s |
Talking-head lip-sync is not in the API catalog. Use Seedance with `generate_audio` or Kling `sound: on`, and flag that the result needs a quality check.

## Workflow and cost discipline
1. Still first (Soul or Marketing Studio) to lock the look; then `generate_media(model=<i2v>, image_asset_id=<still>)`. Stills are cheap; video re-rolls are not.
2. Estimate before every submit. Defaults: batch_size 1, 5 s, 720p, 9:16. Longer, 1080p and extra variants only after the operator approves the draft.
3. One clip per shot (4-8 s), assembled later. Short clips drift less.
4. Seedance/Kling i2v keep the still's framing, so make the still vertical 9:16 from the start.

## Prompt formula
`[subject + action], [setting], [camera], [lighting], [mood/style], vertical 9:16`.
- Subject: concrete and visible ("woman in her 30s holding a white serum bottle to the camera, smiling slightly").
- Action: one movement per clip ("unscrews the cap and applies one drop to the back of her hand").
- Setting: a lived-in place ("small bathroom, tiled wall, towel on hook").
- Camera: "handheld selfie angle, slight shake", "35mm close-up, slow push-in", "over-the-shoulder".
- Lighting: "soft window daylight", "warm lamp light", "ring-light reflection in eyes".
- Style: "handheld iPhone footage, unpolished, natural skin texture" for native UGC feel. Avoid "cinematic masterpiece, 8k" language.
- Always say `vertical 9:16`, and set `aspect_ratio` to `9:16` in args.

## What to avoid
- No brand logos or legible small text in prompts; add captions and product shots in editing or use real product image references.
- No real people's likeness, celebrities or minors. Characters are fictional or operator-owned references with recorded consent. Without consent, shoot hands-only product demos (hands, product, surface, no identifiable face).
- No claims in the visuals (before/after skin results, medical imagery).
- Do not describe on-screen text for the model to render; it is unreliable.

## Mark everything as AI-generated
Every asset gets `ai_generated: true` in the manifest so publishing sets the platform AI label.

## Sound and expiry
Seedance and Kling can generate audio; describe it in the prompt ("quiet room tone, a soft click as the cap opens") and keep spoken lines out unless the operator supplied a script. Higgsfield output URLs are deleted after 7 days, so completed clips must be ingested into Ugecy storage promptly.
