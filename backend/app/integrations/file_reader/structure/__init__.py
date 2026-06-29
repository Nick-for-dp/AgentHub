"""章节推断层导出入口。

该包只暴露 AgentHub 自有结构类型和推断器；即使底层尝试 Dedoc 等库，
业务层也不应感知第三方库的数据结构。

Exports:
    DocumentStructureAnalyzer: 当前主链路规则推断器。
    ParsedBlock / InferredSection / ParsedDocumentV1: 章节推断层输入输出结构。

Boundary:
    Dedoc 等第三方工具只能在 adapter 内转换为这些平台自有类型。
"""

from app.integrations.file_reader.structure.analyzer import DocumentStructureAnalyzer
from app.integrations.file_reader.structure.schema import (
    InferredSection,
    NumberingInfo,
    ParsedBlock,
    ParsedDocumentV1,
    ParsedMetadata,
    SourceLocation,
    StructureWarning,
    StyleFeatures,
)

__all__ = [
    "DocumentStructureAnalyzer",
    "InferredSection",
    "NumberingInfo",
    "ParsedBlock",
    "ParsedDocumentV1",
    "ParsedMetadata",
    "SourceLocation",
    "StructureWarning",
    "StyleFeatures",
]
