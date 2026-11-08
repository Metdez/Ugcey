"""Wire models shared with the UI. Mirror of packages/contracts/src/{models,events}.ts.

Change both files together. Field names are snake_case on the wire.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Mode = Literal["live", "off"]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ProviderModes(BaseModel):
    llm: Mode = "live"
    media: Mode = "off"
    device: Mode = "off"
    publishing: Mode = "off"
    research: Mode = "off"  # web_search (Firecrawl); fetch_page is always available
    tavily: Mode = "off"  # deep_search, read_pages, deep_research
    storage: Mode = "off"  # Dropbox media library, live while the operator's Dropbox is connected


class ModelRoute(BaseModel):
    role: str
    model: str
    fallback: str | None = None


class AgentInfo(BaseModel):
    name: str
    description: str
    model: str
    tools: list[str]
    enabled: bool = True


class AppConfig(BaseModel):
    version: str
    modes: ProviderModes
    models: list[ModelRoute]
    agents: list[AgentInfo]
    starter_prompts: list[str]


class Todo(BaseModel):
    content: str
    status: Literal["pending", "in_progress", "completed"]


class FileEntry(BaseModel):
    path: str
    size: int
    modified_at: str | None = None


class FileContent(BaseModel):
    path: str
    content: str


class MemoryFile(BaseModel):
    path: str
    scope: Literal["memories", "skills"]
    content: str
    updated_at: str | None = None
    editable: bool


class ToolCall(BaseModel):
    id: str
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "tool"]
    agent: str
    text: str
    reasoning: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None
    created_at: str | None = None


DecisionType = Literal["approve", "edit", "reject"]


class ApprovalRequest(BaseModel):
    tool: str
    agent: str
    args: dict[str, Any]
    description: str
    allowed_decisions: list[DecisionType]
    estimated_cost_usd: float | None = None


class ApprovalRecord(BaseModel):
    interrupt_id: str
    thread_id: str
    status: Literal["pending", "approved", "edited", "rejected", "expired"] = "pending"
    requests: list[ApprovalRequest]
    created_at: str = Field(default_factory=now_iso)
    decided_at: str | None = None


class Decision(BaseModel):
    type: DecisionType
    args: dict[str, Any] | None = None  # for "edit"
    message: str | None = None  # for "reject"


class Asset(BaseModel):
    id: str
    thread_id: str | None
    kind: Literal["image", "video", "audio"]
    status: Literal["queued", "in_progress", "completed", "failed"]
    provider: str
    model: str
    prompt: str
    url: str | None = None
    thumbnail_url: str | None = None
    job_id: str | None = None
    mode: Mode
    estimated_usd: float | None = None
    created_at: str = Field(default_factory=now_iso)
    dropbox_path: str | None = None  # copy in the operator's Dropbox (written only by set_asset_dropbox)
    dropbox_status: Literal["pending", "saved", "failed"] | None = None


class Source(BaseModel):
    url: str
    title: str
    platform: str | None = None
    snippet: str | None = None


Platform = Literal["tiktok", "instagram", "youtube", "facebook"]


class ConnectedAccount(BaseModel):
    id: str
    platform: Platform
    handle: str
    mode: Mode
    status: Literal["connected", "needs_auth", "error"] = "connected"


class Post(BaseModel):
    id: str
    thread_id: str | None
    account_id: str
    asset_id: str | None
    caption: str
    ai_disclosure: bool
    status: Literal["draft", "scheduled", "published", "failed"]
    publish_at: str | None = None
    external_url: str | None = None
    mode: Mode
    created_at: str = Field(default_factory=now_iso)


class AuditEntry(BaseModel):
    id: str
    ts: str = Field(default_factory=now_iso)
    thread_id: str | None = None
    actor: Literal["agent", "operator", "system"]
    agent: str | None = None
    action: str
    tool: str | None = None
    status: Literal["ok", "error", "pending", "rejected"]
    mode: Mode
    detail: str = ""


class ThreadSummary(BaseModel):
    id: str
    title: str
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    status: Literal["idle", "running", "awaiting_approval", "error"] = "idle"


class ThreadState(BaseModel):
    thread: ThreadSummary
    messages: list[ChatMessage]
    todos: list[Todo]
    files: list[FileEntry]
    sources: list[Source]
    pending_approval: ApprovalRecord | None = None


class DeviceInfo(BaseModel):
    id: str
    name: str
    kind: Literal["iphone", "mac"]
    status: str
    ready: bool


class DeviceSessionInfo(BaseModel):
    id: str
    device_id: str
    goal: str
    steps_used: int
    max_steps: int  # 0 = no cap (research sessions)


class DeviceStatus(BaseModel):
    provider: str
    mode: Mode
    devices: list[DeviceInfo]
    session: DeviceSessionInfo | None = None
    control: Literal["agent", "human", "idle"] = "idle"
    last_action: str | None = None


# ---- REST bodies -------------------------------------------------------------------------

class CreateThreadRequest(BaseModel):
    title: str | None = None


class RunRequest(BaseModel):
    message: str


class ResumeRequest(BaseModel):
    interrupt_id: str
    decisions: list[Decision]


class PutMemoryRequest(BaseModel):
    path: str
    content: str


# ---- SSE events (UiEvent) ----------------------------------------------------------------
# One flat model keeps the emitter simple; `type` selects which optional fields are set.
# The TS side (events.ts) is the discriminated union; keep field names identical.

EventType = Literal[
    "run.started", "message.delta", "reasoning.delta", "message.completed",
    "tool.started", "tool.completed", "subagent.started", "subagent.completed",
    "todos.updated", "files.updated", "source.added", "asset.updated", "memory.updated",
    "progress", "approval.requested", "run.completed", "error",
]


class UiEvent(BaseModel):
    type: EventType
    seq: int
    ts: str = Field(default_factory=now_iso)
    thread_id: str
    run_id: str
    agent: str = "orchestrator"
    ns: list[str] = Field(default_factory=list)
    parent_call_id: str | None = None
    # optional payload fields (see events.ts for which apply to which type)
    model: str | None = None
    message_id: str | None = None
    text: str | None = None
    call_id: str | None = None
    name: str | None = None
    args: dict[str, Any] | None = None
    status: str | None = None
    output_preview: str | None = None
    subagent: str | None = None
    description: str | None = None
    summary: str | None = None
    todos: list[Todo] | None = None
    files: list[FileEntry] | None = None
    source: Source | None = None
    asset: Asset | None = None
    path: str | None = None
    tool: str | None = None
    message: str | None = None
    interrupt_id: str | None = None
    requests: list[ApprovalRequest] | None = None
    retryable: bool | None = None

    def wire(self) -> dict[str, Any]:
        """JSON for the SSE `data:` line: drop unset optional payload fields."""
        return self.model_dump(mode="json", exclude_none=True) | {"parent_call_id": self.parent_call_id}
