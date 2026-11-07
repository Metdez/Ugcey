"""compliance-critic subagent module (registered at import)."""
from ugecy.agents._base import load_prompt
from ugecy.registry import AgentModule, register_agent

register_agent(AgentModule(
    name="compliance-critic",
    description=(
        "Independent reviewer that scores scripts (hook strength, originality vs sources, claim safety, FTC #ad disclosure, platform AI-label readiness, brand fit) and writes /reviews/<script>.md with a verdict and required edits. Use on every script before production. Never approves health claims."
    ),
    system_prompt=load_prompt("compliance-critic"),
    tools=["compliance_check"],
    model_role="critic",
    skills=["/skills/"],
))
