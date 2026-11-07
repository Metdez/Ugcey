"""analytics-analyst subagent module (registered at import)."""
from ugecy.agents._base import load_prompt
from ugecy.registry import AgentModule, register_agent

register_agent(AgentModule(
    name="analytics-analyst",
    description=(
        "Reads post metrics, explains why posts won or lost against stored patterns, and proposes playbook updates for /memories/playbook.md (operator approval required). Use after posts have been live long enough to measure."
    ),
    system_prompt=load_prompt("analytics-analyst"),
    tools=["get_post_metrics", "search_patterns", "remember_pattern"],
    model_role="research",
    skills=["/skills/"],
))
