from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.risk_assessment.extraction.schemas import ScalarValue


@dataclass(frozen=True)
class OcrBlock:
    source_id: str
    page_number: int | None
    text: str
    bbox: Any | None = None
    label: str | None = None


@dataclass(frozen=True)
class OcrDocument:
    blocks: tuple[OcrBlock, ...]
    page_count: int

    @property
    def anchored_text(self) -> str:
        return "\n".join(f"[{block.source_id}] {block.text}" for block in self.blocks)


class QwenFieldCandidate(BaseModel):
    """Qwen 的最小临时输出；模型自报 bbox 等额外字段一律忽略。"""

    model_config = ConfigDict(extra="ignore")

    field_code: str = Field(min_length=1, max_length=100)
    raw_value: ScalarValue | None = None
    source_ids: list[str] = Field(default_factory=list)
    quote: str = ""


class QwenExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fields: list[QwenFieldCandidate] = Field(default_factory=list)
