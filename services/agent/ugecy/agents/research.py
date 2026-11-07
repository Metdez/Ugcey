"""research-analyst subagent module (registered at import)."""
from ugecy.agents._base import load_prompt
from ugecy.registry import AgentModule, register_agent

register_agent(AgentModule(
    name="research-analyst",
    description=(
        "Finds winning public short-form UGC (TikTok, Reels, Shorts) and turns each into an evidence-backed pattern card in /research/patterns/. Researches on the operator's Glasshand iPhone when one is connected (read-only), else on the web. Use for trend research, hook and format analysis, and competitor teardown. Cites every URL; never copies scripts. Give it the niche, product category, platforms and how many patterns you need."
    ),
    system_prompt=load_prompt("research-analyst"),
    tools=["web_search", "fetch_page", "remember_pattern", "search_patterns", "device_status", "device_start_session", "device_screenshot", "device_scroll", "device_back",
           "device_observe", "device_tap", "device_swipe", "device_next_post", "device_type", "device_home"],
    model_role="research",
    uncapped=True,  # no model-call cap: research runs until the task is done
    skills=["/skills/"],
))
