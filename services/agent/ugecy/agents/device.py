"""device-operator subagent module (registered at import)."""
from ugecy.agents._base import load_prompt
from ugecy.registry import AgentModule, register_agent

register_agent(AgentModule(
    name="device-operator",
    description=(
        "Drives the operator's own phone or Mac through the device provider: observe, act, verify, with a final device_commit for irreversible taps. Can sign in to or create the operator's own accounts and enter operator-supplied credentials or codes. Use only when an API route does not exist for the task."
    ),
    system_prompt=load_prompt("device-operator"),
    tools=["device_status", "device_screenshot", "device_start_session", "device_tap", "device_swipe", "device_scroll",
           "device_back", "device_open_url", "device_type", "device_home", "device_confirm", "device_commit"],
    model_role="research",  # GPT-5.6 Terra drives the phone
    skills=["/skills/"],
))
