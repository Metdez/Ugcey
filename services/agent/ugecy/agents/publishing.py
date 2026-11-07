"""publishing-coordinator subagent module (registered at import)."""
from ugecy.agents._base import load_prompt
from ugecy.registry import AgentModule, register_agent

register_agent(AgentModule(
    name="publishing-coordinator",
    description=(
        "Publishes or schedules completed, approved assets to the operator's own connected accounts with correct AI-disclosure flags and #ad where paid. Operator approval is required for every publish. Give it asset id, account id, caption and timing."
    ),
    system_prompt=load_prompt("publishing-coordinator"),
    tools=["list_connected_accounts", "publish_post", "get_post_status"],
    model_role="fast",
    skills=["/skills/"],
))
