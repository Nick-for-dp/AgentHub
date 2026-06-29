"""文件读取集成层的稳定导出入口。

业务模块应从这里导入 FileReader、FileSource 和 ParsedDocumentV1 等平台自有类型，
不要直接依赖 python-docx、pymupdf 或 Dedoc 的第三方类型。

Exports:
    FileReader: 文件读取协议。
    FileSource: 文件来源描述。
    parse_local_file: 本地文件 PoC 解析入口。
    ParsedDocumentV1: 统一解析输出结构。

Boundary:
    该模块是 integrations/file_reader 的公共 API 面，后续内部实现替换不应影响
    合同审查和风控业务模块的导入路径。
"""

from app.integrations.file_reader.base import FileReader, FileSource
from app.integrations.file_reader.factory import get_file_reader, parse_local_file
from app.integrations.file_reader.structure.schema import (
    InferredSection,
    ParsedBlock,
    ParsedDocumentV1,
    ParsedMetadata,
    SourceLocation,
    StructureWarning,
    StyleFeatures,
)

__all__ = [
    "FileReader",
    "FileSource",
    "InferredSection",
    "ParsedBlock",
    "ParsedDocumentV1",
    "ParsedMetadata",
    "SourceLocation",
    "StructureWarning",
    "StyleFeatures",
    "get_file_reader",
    "parse_local_file",
]
