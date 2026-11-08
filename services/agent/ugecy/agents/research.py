"""research-analyst subagent module (registered at import)."""
from ugecy.agents._base import load_prompt
from ugecy.registry import AgentModule, register_agent

register_agent(AgentModule(
    name="research-analyst",
    description=(
        "Deep web research with Firecrawl and Tavily (never the phone): which UGC hooks and short-form formats are winning right now, what people are saying about the niche, and competitor ads. Writes an evidence-backed hook library and pattern cards to /research/. Use for trend research, hook and format analysis, and competitor teardown. Cites every URL; never copies scripts. Give it the niche, product category, audience and platforms."
    ),
    system_prompt=load_prompt("research-analyst"),
    tools=["tavily_research", "tavily_search", "tavily_extract", "web_search", "fetch_page", "remember_pattern",
           "search_patterns"],
    model_role="research",
    skills=["/skills/"],
))
