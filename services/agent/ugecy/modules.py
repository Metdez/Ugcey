"""The module list: delete a line to remove a feature, add a line to slot one in.
Tool modules load before agent modules (agents reference tools by name)."""
from __future__ import annotations

import importlib

TOOL_MODULES = [
    "ugecy.tools.research",    # web_search, fetch_page (Firecrawl)
    "ugecy.tools.tavily",      # tavily_search, tavily_extract, tavily_research
    "ugecy.tools.memory",      # remember_pattern, search_patterns
    "ugecy.tools.creative",    # compliance_check
    "ugecy.tools.analytics",   # get_post_metrics
    "ugecy.tools.media",       # list_media_models, estimate_media_cost, generate_media, check_media_job
    "ugecy.tools.publishing",  # list_connected_accounts, publish_post, get_post_status
    "ugecy.tools.dropbox",     # dropbox_status, list_dropbox_media, browse_dropbox, save_to_dropbox, dropbox_backfill
    "ugecy.tools.device",      # device_status, device_screenshot, device_start_session, device_tap, ...
]

AGENT_MODULES = [
    "ugecy.agents.research",     # research-analyst
    "ugecy.agents.creative",     # creative-strategist
    "ugecy.agents.critic",       # compliance-critic
    "ugecy.agents.production",   # production-coordinator
    "ugecy.agents.publishing",   # publishing-coordinator
    "ugecy.agents.device",       # device-operator
    "ugecy.agents.analytics",    # analytics-analyst
]


def load_modules() -> None:
    for path in TOOL_MODULES + AGENT_MODULES:
        importlib.import_module(path)
