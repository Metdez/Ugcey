"""production-coordinator subagent module (registered at import)."""
from ugecy.agents._base import load_prompt
from ugecy.registry import AgentModule, register_agent

register_agent(AgentModule(
    name="production-coordinator",
    description=(
        "Turns approved scripts into Higgsfield prompts (subject, setting, camera, lighting, 9:16), estimates cost, submits generation (operator approval required) and tracks jobs in /assets/manifest.json. Use only for scripts whose review verdict is approved."
    ),
    system_prompt=load_prompt("production-coordinator"),
    tools=["list_media_models", "estimate_media_cost", "generate_media", "check_media_job"],
    model_role="fast",
    skills=["/skills/"],
))
