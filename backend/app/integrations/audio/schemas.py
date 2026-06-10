from pydantic import BaseModel, Field


class AudioTranscriptionResult(BaseModel):
    text: str
    provider: str = "VOLCENGINE"
    request_id: str | None = None
    log_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class SpeechSynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: str | None = Field(default=None, max_length=100)

