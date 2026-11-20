from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    message: str = Field(min_length=1, max_length=4000)
    model: str | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=512, ge=1, le=2000)


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    source: str


class ChatResponse(BaseModel):
    request_id: str
    model: str
    content: str
    usage: Usage
    latency_ms: int

class ChatMessage(BaseModel):
    role: str
    content: str


class CompletionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False


class CompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class CompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str | None = None


class CompletionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[CompletionChoice]
    usage: CompletionUsage