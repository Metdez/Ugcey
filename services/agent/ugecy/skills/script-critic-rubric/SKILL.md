---
name: script-critic-rubric
description: Scoring rubric and verdict rules for reviewing short-form UGC scripts before generation or publishing: hook strength, retention structure, originality, claim safety, disclosure, AI-label readiness and brand fit. Use when reviewing a script and writing /reviews/<script>.md.
---
# Script critic rubric

Score each criterion 1 to 5. Quote or timestamp the evidence; a score without evidence is invalid.

| Criterion | 5 | 3 | 1 |
|---|---|---|---|
| Hook strength | One clear idea in 0-3 s, works muted, open loop | Decent idea, vague or slow, needs sound | No hook, generic greeting, brand-first opener |
| Retention structure | Re-hook every 5-8 s, payoff delivered, one CTA | Some dead stretches or a late payoff | Rambling, multiple ideas, no payoff |
| Originality vs sources | Structure adapted, wording and bits new | Close paraphrase of a source beat | Copied wording, character or distinctive bit |
| Claim safety | Every claim allowed or substantiated | Vague superlatives ("best") unsupported | Health, medical, income or guaranteed-result claim |
| Disclosure | `#ad` first line when paid, no fake testimonial | Disclosure present but buried | Missing, or synthetic person claims personal experience |
| AI-label readiness | Flag set, caption honest | Flag planned but unspecified | Realistic AI media with no label plan |
| Brand fit | Matches voice and forbidden topics | Slightly off-voice | Violates memory rules |

## Automatic fails (verdict `rejected`)
- Health, medical, weight-loss, cure or income claims, or "guaranteed" results.
- An AI avatar, synthetic voice or non-existent person delivering a personal testimonial ("I used this for 30 days").
- Verbatim lines, characters, music or distinctive bits copied from a source.
- Fabricated reviews, ratings, statistics or endorsements. Minors in a promotional context without guardian consent noted.

## Verdicts
- `approved`: no score below 3, claim safety and disclosure at 4 or above.
- `revise`: list required edits as numbered before/after text so the strategist can paste them.
- `rejected`: name the automatic fail and offer a compliant reframe (for example demo or POV instead of testimonial).

## Hook checks
Does the first line promise a payoff the video delivers? Is it clickbait that the body breaks? Would the hook work in a different niche (too generic)? Is on-screen text duplicating the voiceover?

## Review file format
Line 1: `Verdict: approved|revise|rejected`. Then a score table with evidence, required edits (numbered), optional improvements, the compliance_check summary, and one sentence on the first test to run. Be specific and brief. Independence matters: do not soften a verdict because the operator is eager.
