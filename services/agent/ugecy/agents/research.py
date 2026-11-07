"""research-analyst subagent module (registered at import)."""
from ugecy.agents._base import load_prompt
from ugecy.registry import AgentModule, register_agent

register_agent(AgentModule(
    name="research-analyst",
    description=(
        "Finds winning public short-form UGC (TikTok, Reels, Shorts) and turns each into an evidence-backed pattern card in /research/patterns/. Use for trend research, hook and format analysis, and competitor teardown. Cites every URL; never copies scripts. Give it the niche, product category, platforms and how many patterns you need."
    ),
    system_prompt=load_prompt("research-analyst"),
    tools=["web_search", "fetch_page", "remember_pattern", "search_patterns"],
    model_role="research",
    skills=["/skills/"],
))
