"""creative-strategist subagent module (registered at import)."""
from ugecy.agents._base import load_prompt
from ugecy.registry import AgentModule, register_agent

register_agent(AgentModule(
    name="creative-strategist",
    description=(
        "Writes original creative briefs and 3-5 script variants (different hook types, 15/30/45 s beat timings, on-screen text, shot list) into /briefs/ and /scripts/. Use after research exists or when the operator supplies a product and angle. Needs: product, audience, platform, length, pattern card paths."
    ),
    system_prompt=load_prompt("creative-strategist"),
    tools=["search_patterns"],
    model_role="creative",
    skills=["/skills/"],
))
