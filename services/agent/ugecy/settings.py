"""Runtime configuration (env vars). In the container the Worker sets UGECY_INTERNAL_MODE=edge
and the UGECY_HAS_* flags; secrets never enter the container."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderChoice = Literal["auto", "live", "mock"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UGECY_", extra="ignore")

    version: str = "0.1.0"
    workspace_id: str = "default"
    internal_mode: Literal["edge", "local", "test"] = "local"
    data_dir: str = ".ugecy"

    # local-mode credentials (read from the developer's env; unused in edge mode)
    cf_account_id: str | None = Field(default=None, validation_alias="CLOUDFLARE_ACCOUNT_ID")
    cf_api_token: str | None = Field(default=None, validation_alias="CLOUDFLARE_API_TOKEN")
    hf_key: str | None = Field(default=None, validation_alias="HF_KEY")
    hf_api_key_secret: str | None = Field(default=None, validation_alias="HF_API_KEY_SECRET")
    firecrawl_api_key: str | None = Field(default=None, validation_alias="FIRECRAWL_API_KEY")
    glasshand_token: str | None = Field(default=None, validation_alias="GLASSHAND_TOKEN")  # local dev only
    glasshand_rental_id: str | None = Field(default=None, validation_alias="GLASSHAND_RENTAL_ID")  # local dev only

    # edge-mode capability flags set by the AgentRuntime DO from the Worker's secrets
    has_higgsfield: bool = False
    has_firecrawl: bool = False
    has_glasshand: bool = False

    # provider selection
    media_provider: ProviderChoice = "auto"
    device_provider: ProviderChoice = "auto"
    research_provider: ProviderChoice = "auto"
    publishing_provider: ProviderChoice = "mock"  # live social adapters need app review (FEATURES.md)

    # model routing (Workers AI ids; see .planning/research/MODELS.md). No Anthropic models.
    model_orchestrator: str = "@cf/zai-org/glm-5.3"
    model_research: str = "@cf/deepseek-ai/deepseek-v4.1-flash-1017"
    model_creative: str = "@cf/deepseek-ai/deepseek-v4.1-flash-1017"
    model_critic: str = "@cf/zai-org/glm-5.3"
    model_fast: str = "@cf/zai-org/glm-4.7-flash"
    model_vision: str = "@cf/qwen/qwen3.8-27b"
    model_fallback: str = "@cf/qwen/qwen3.8-27b"  # 300 rpm; absorbs 20-rpm limits on paid models
    model_embeddings: str = "@cf/qwen/qwen3-embedding-0.6b"

    disabled_agents: str = ""  # comma-separated agent names
    disabled_tools: str = ""
    max_model_calls_per_run: int = 80
    max_model_calls_per_subagent: int = 30
    llm_timeout_s: float = 180.0

    @property
    def higgsfield_key(self) -> str | None:
        """Local mode only. HF_API_KEY_SECRET holds the combined 'key-id:key-secret' form."""
        if self.hf_key:
            return self.hf_key
        if self.hf_api_key_secret and ":" in self.hf_api_key_secret:
            return self.hf_api_key_secret
        return None

    def disabled(self, which: Literal["agents", "tools"]) -> set[str]:
        raw = self.disabled_agents if which == "agents" else self.disabled_tools
        return {x.strip() for x in raw.split(",") if x.strip()}

    def model_for(self, role: str) -> str:
        return getattr(self, f"model_{role}", self.model_fast)


@lru_cache
def get_settings() -> Settings:
    return Settings()
