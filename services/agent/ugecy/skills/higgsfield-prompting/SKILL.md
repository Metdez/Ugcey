---
name: higgsfield-prompting
description: "How to write Higgsfield image and video generation prompts for 9:16 UGC (subject, setting, camera, lighting), which model endpoint to choose and which arguments matter. Use before calling estimate_media_cost or generate_media, or when turning a shot list into prompts."
---
# Higgsfield prompting for UGC

Always take model ids from `list_media_models`; the table below is the current catalog for orientation.

## Choosing a model
| Need | endpoint_id | Key args |
|---|---|---|
| Creator or product still, 9:16 | `higgsfield-ai/soul/v2/standard` | prompt, aspect_ratio `9:16`, resolution 720p or 1080p, batch_size 1 or 4, seed, enhance_prompt |
| Product ad stills | `marketing-studio/image` | prompt, image_urls (up to 16), aspect_ratio auto or 9:16, resolution 1k/2k/4k |
| Ad from product images | `higgsfield/ads-studio/v1.0` | prompt, image_urls (up to 10), niche, target_audience, language, aspect_ratio 9:16 or 4:5, batch_size 1 to 8 |
| Image to video with audio, up to 30 s | `bytedance/seedance-2.5/image-to-video` | image_url, prompt, duration 4 to 30, resolution 480/720/1080p, generate_audio |
| Multi-reference UGC video | `bytedance/seedance-2.5/reference-to-video` | image_urls (up to 30), prompt, duration, aspect_ratio 9:16, generate_audio |
| Text to video | `bytedance/seedance-2.5/text-to-video` | prompt, aspect_ratio, duration 4 to 30 |
| Multi-shot clip | `kling-video/v3.0/{std,pro}/image-to-video` | image_url, prompt, duration 3 to 15, sound on or off, multi_prompt (up to 6 shots) |
Talking-head lip-sync is not in the API catalog. Use Seedance reference-to-video with `generate_audio` or Kling `sound: on`, and say the result needs a quality check.

## Workflow
1. Make a still first (Soul or Marketing Studio) to lock the look; animate with image-to-video. Stills are cheap; re-rolls on video are not.
2. Generate per shot (3 to 8 s each) rather than one long take, then assemble. Short clips drift less.
3. Estimate cost for the whole batch before the first submit; keep batches small.

## Prompt formula
`[subject + action], [setting], [camera], [lighting], [mood/style], vertical 9:16`.
- Subject: concrete and visible ("woman in her 30s holding a white serum bottle to the camera, smiling slightly").
- Action: one movement per clip ("unscrews the cap and applies one drop to the back of her hand").
- Setting: a lived-in place ("small bathroom, tiled wall, towel on hook").
- Camera: "handheld selfie angle, slight shake", "35mm close-up, slow push-in", "over-the-shoulder".
- Lighting: "soft window daylight", "warm lamp light", "ring-light reflection in eyes".
- Style: "unpolished phone footage, natural skin texture" for native UGC feel. Avoid "cinematic masterpiece, 8k" language.
- Always say `vertical 9:16`, and set `aspect_ratio` to `9:16` in args.

## What to avoid
- No brand logos or legible small text in prompts; add captions and product shots in editing or use real product image references.
- No real people's likeness, celebrities or minors. Characters are fictional or operator-owned references with recorded consent.
- No claims in the visuals (before/after skin results, medical imagery).
- Do not describe on-screen text for the model to render; it is unreliable.

## Mark everything as AI-generated
Every asset gets `ai_generated: true` in the manifest so publishing sets the platform AI label.
