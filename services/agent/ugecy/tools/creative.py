"""compliance_check: deterministic pre-flight for UGC copy. No LLM. Not legal advice."""
from __future__ import annotations

import json
import re

from langchain_core.tools import tool

from ugecy import registry

# (rule, severity, regex, fix). "block" = must not ship; "fix" = change before publishing.
_CLAIMS: list[tuple[str, str, str, str]] = [
    ("health.cure_claim", "block", r"\b(heals?|treats?|reverses?)\b.{0,40}\b(acne|eczema|psoriasis|diabetes|cancer|anxiety|depression|arthritis|adhd|insomnia|disease)\b",
     "Remove disease cure/treat claims; supplements and cosmetics cannot claim to treat disease."),
    ("health.cure_word", "block", r"\bcures?\b", "Drop 'cure'; describe your own routine or the ingredient, not a medical outcome."),
    ("claim.guaranteed", "block", r"\bguarantee[sd]?\b(?!.{0,20}(money.back|refund|return))", "Remove 'guaranteed' results; only a money-back guarantee with terms is allowed."),
    ("health.weight_loss", "block", r"\b(lose|drop|shed)\w*\s+\d+\s*(lbs?|pounds?|kg|kilos?|inches)\b", "Remove specific weight-loss numbers and timeframes."),
    ("health.weight_loss_time", "block", r"\b(lose|lost|drop)\w*\s+\w*\s*(weight|fat|belly fat)\b.{0,30}\b(in|within)\s+\d+\s*(days?|weeks?)\b", "Remove time-bound weight-loss claims."),
    ("health.doctor_endorsement", "fix", r"\b(doctor|dermatologist|physician|dentist)s?[- ](recommended|approved|endorsed|certified)\b", "Only keep with a real, documented, disclosed professional endorsement."),
    ("health.fda", "block", r"\bfda[- ](approved|cleared|certified)\b", "Do not claim FDA approval for supplements or cosmetics."),
    ("health.miracle", "fix", r"\b(miracle|instantly|overnight results?|permanent(ly)?|100% effective|no side effects?)\b", "Replace absolutes with specific, supportable statements."),
    ("finance.guaranteed_returns", "block", r"\b(guaranteed|risk[- ]free|sure[- ]thing)\b.{0,40}\b(returns?|profits?|income|money|roi)\b|\bpassive income\b.{0,30}\b(effortless|guaranteed)\b",
     "Remove guaranteed or risk-free return claims; add the required risk disclosure."),
    ("finance.get_rich", "block", r"\b(get rich quick|make \$?\d[\d,]*\s*(a|per)\s*(day|week|month)|double your money)\b", "Remove income promises; show typical results with a disclaimer or drop the claim."),
]
_CLINICAL = re.compile(r"\bclinically[- ](proven|tested|shown)\b|\bstudies (show|prove)\b|\bscientifically proven\b", re.I)
_SOURCE = re.compile(r"https?://|\bsource:|\(\d{4}\)|\bstudy\b.{0,20}\b(n=|participants|journal)", re.I)
_DISCLOSURE = re.compile(r"(#|\b)(ad|sponsored|paidpartnership|paid partnership|gifted)\b|paid partnership", re.I)
_TESTIMONIAL = re.compile(r"\b(i tried|i['’]?ve been using|i used|my results?|i lost|i love this|changed my life|after (\d+|a few) (days|weeks|months) (of|using))\b", re.I)
_AI_LABEL = {
    "tiktok": "Set the AI-generated content toggle (is_aigc) and add a visible label such as #AIgenerated.",
    "instagram": "Set the 'AI info' / is_ai_generated flag and keep C2PA/IPTC metadata intact.",
    "youtube": "Set 'Altered or synthetic content' (containsSyntheticMedia) in the upload.",
    "facebook": "No API AI flag is documented; add a clear caption disclosure and keep C2PA metadata.",
}
# Visible caption limits (characters). shortcut: limits change; refresh from platform docs each quarter.
_CAPTION = {"tiktok": 4000, "instagram": 2200, "youtube": 5000, "facebook": 63206}
_SEV = {"block": 3, "fix": 2, "warn": 1}


def _issue(rule: str, sev: str, excerpt: str, fix: str) -> dict[str, str]:
    return {"rule": rule, "severity": sev, "excerpt": excerpt[:120], "fix": fix}


def run_checks(text: str, platform: str, is_ai_generated: bool, is_paid_partnership: bool) -> dict:
    issues: list[dict[str, str]] = []
    seen: set[str] = set()
    for rule, sev, pat, fix in _CLAIMS:
        for m in re.finditer(pat, text, re.I | re.S):
            if m.group(0).lower() not in seen:
                seen.add(m.group(0).lower())
                issues.append(_issue(rule, sev, m.group(0), fix))
    for m in _CLINICAL.finditer(text):
        if not _SOURCE.search(text):
            issues.append(_issue("claim.unsubstantiated", "fix", m.group(0),
                                 "Cite the study or remove; 'clinically proven' needs competent, available evidence."))
    if is_paid_partnership and not _DISCLOSURE.search(text):
        issues.append(_issue("ftc.disclosure_missing", "block", text[:60],
                             "Add #ad or #sponsored (or the platform paid-partnership label) in the first line, before 'more'."))
    elif is_paid_partnership and not _DISCLOSURE.search(text[:125]):
        issues.append(_issue("ftc.disclosure_buried", "fix", text[:60], "Move #ad into the first 125 characters so it shows without expanding."))
    if is_ai_generated:
        p = platform.lower()
        issues.append(_issue("platform.ai_label", "fix", f"platform={p}", _AI_LABEL.get(p, _AI_LABEL["facebook"])))
        for m in _TESTIMONIAL.finditer(text):
            issues.append(_issue("ftc.fake_testimonial", "block", m.group(0),
                                 "AI actors must not claim personal experience (16 CFR 465). Rewrite as a product demo or "
                                 "feature statement, or use a real consenting customer."))
            break
    limit = _CAPTION.get(platform.lower())
    if limit and len(text) > limit:
        issues.append(_issue("platform.caption_length", "fix", f"{len(text)} chars", f"Shorten to {limit} characters or fewer for {platform}."))
    elif limit and len(text) > limit * 0.9:
        issues.append(_issue("platform.caption_length", "warn", f"{len(text)} chars", f"Close to the {limit}-character limit for {platform}."))
    # An AI label alone is a to-do (fix), not a failure of the copy; verdict reflects the worst non-label issue.
    worst = max((_SEV[i["severity"]] for i in issues if i["rule"] != "platform.ai_label"), default=0)
    verdict = "block" if worst == 3 else "fix" if worst == 2 else "pass"
    return {"verdict": verdict, "issues": issues}


@tool
def compliance_check(text: str, platform: str = "tiktok", is_ai_generated: bool = True,
                     is_paid_partnership: bool = False) -> str:
    """Check a script, caption or voiceover line against advertising and platform rules before approval.

    Use on every draft script and caption, and again after edits. Deterministic rule check (no
    model): flags disease/cure, guaranteed-result, weight-loss, doctor-recommended and unsourced
    'clinically proven' claims, finance promises, missing FTC #ad disclosure on paid partnerships,
    first-person testimonials spoken by AI actors, the platform's AI-label requirement, and caption
    length. Returns JSON {verdict: pass|fix|block, issues:[{rule, severity, excerpt, fix}]}.
    It is a screening aid, not legal advice; a human still approves. Only public, permitted content.
    """
    return json.dumps(run_checks(text, platform, is_ai_generated, is_paid_partnership))


registry.register_tool(compliance_check, domain="creative")
