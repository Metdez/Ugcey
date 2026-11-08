"""production-coordinator subagent module (registered at import)."""
from ugecy.agents._base import load_prompt
from ugecy.registry import AgentModule, register_agent

register_agent(AgentModule(
    name="production-coordinator",
    description=(
        "Turns an approved script into a finished-length Higgsfield ad: one first-frame still, then one multi-shot clip with the cuts inside it (Seedance 2.5 timed shots by default, Kling 3.0 multi-shot when speed matters). Estimates cost, submits generation (operator approval required) and tracks jobs in /assets/manifest.json. Use only for scripts whose review verdict is approved; give it the script path, preview or final, and whether product photos or likeness consent exist."
    ),
    system_prompt=load_prompt("production-coordinator"),
    tools=["dropbox_status", "list_dropbox_media", "browse_dropbox", "save_to_dropbox", "dropbox_backfill", "web_search", "fetch_page",
           "list_media_models", "estimate_media_cost", "generate_media", "check_media_job"],
    model_role="creative",  # GPT-5.6 Terra: on glm-flash it wrote self-contradicting prompts, empty and invented asset ids
    skills=["/skills/"],
))
