"""Pattern memory tools: remember_pattern, search_patterns (Vectorize via edge bindings)."""
from __future__ import annotations

import json
import re

from langchain_core.tools import tool

from ugecy import registry
from ugecy.deps import get_deps
from ugecy.events import emit


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "pattern"


def _ns() -> str:
    return f"{get_deps().settings.workspace_id}:patterns"


@tool
async def remember_pattern(title: str, hook: str, hook_type: str, structure: str, why_it_works: str,
                           source_urls: list[str], tags: list[str]) -> str:
    """Save a reusable, brand-agnostic pattern card to the workspace pattern library.

    Use after you have analysed a hook/format and can explain WHY it works. Store the abstract
    mechanism and beat outline, never verbatim scripts, music or brand assets of a third party.
    `hook_type` is one of the taxonomy values (curiosity_gap, pattern_interrupt, negative_warning,
    contrarian, result_first, callout_question, pov_relatable, storytime, listicle_number,
    challenge_test, social_proof_authority, comparison_us_vs_them, sensory_asmr, price_value_shock).
    """
    pid = _slug(title)
    text = f"{title}\nHook ({hook_type}): {hook}\nStructure: {structure}\nWhy it works: {why_it_works}\nTags: {', '.join(tags)}"
    meta = {"title": title, "hook": hook, "hook_type": hook_type, "structure": structure,
            "why_it_works": why_it_works, "source_urls": source_urls, "tags": tags}
    await get_deps().edge.vectors_upsert(_ns(), [{"id": pid, "text": text, "metadata": meta}])
    emit("memory.updated", path=f"patterns/{pid}")
    return json.dumps({"saved": pid, "title": title})


@tool
async def search_patterns(query: str, top_k: int = 5) -> str:
    """Search the saved pattern library for hooks, formats or angles relevant to a brief.

    Use before writing scripts so new ideas build on proven patterns. Returns only patterns this
    workspace saved (JSON lines); an empty library returns results 0.
    """
    top_k = max(1, min(top_k, 10))
    matches = await get_deps().edge.vectors_query(_ns(), query, top_k)
    if not matches:
        return json.dumps({"results": 0, "note": "no saved patterns match; research first, then remember_pattern"})
    rows = [{"label": "library", "id": m.get("id"), "score": m.get("score"), **(m.get("metadata") or {})} for m in matches]
    return "\n".join(json.dumps(r) for r in rows)


registry.register_tool(remember_pattern, domain="memory")
registry.register_tool(search_patterns, domain="memory")
