import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.integrations.file_reader.structure.schema import ParsedDocumentV1

DOCUMENT_BLOCKS_SCHEMA_VERSION = "document_blocks_v1"
UNKNOWN_BLOCK_TYPE = "unknown"


class DifyDocumentBlock(BaseModel):
    """传入 block-loop Dify 循环节点的单个文档块。

    该结构是历史逐块识别实验的输入格式。MVP 正式链路已切换为全文上下文输入，
    本模块保留在 ``context_experiment`` 下用于后续对比实验和回归排查。
    """

    model_config = ConfigDict(extra="forbid")

    block_id: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    section_id: str | None = None
    section_title: str | None = None
    text: str = Field(min_length=1)


class DifyDocumentBlocksInput(BaseModel):
    """block-loop Dify workflow 的文档块输入。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["document_blocks_v1"] = DOCUMENT_BLOCKS_SCHEMA_VERSION
    file_parse_task_id: str = Field(min_length=1)
    contract_type: str = Field(min_length=1)
    blocks: list[DifyDocumentBlock] = Field(default_factory=list)


def build_document_blocks_input(
    *,
    file_parse_task_id: str,
    contract_type: str,
    parsed_document: ParsedDocumentV1 | Mapping[str, Any],
) -> DifyDocumentBlocksInput:
    """构建 block-loop 实验 workflow 输入对象。

    Args:
        file_parse_task_id: 已成功解析的 ``file_parse_task.id``。
        contract_type: 合同类型，例如 ``warehouse`` 或 ``transport``。
        parsed_document: ``ParsedDocumentV1`` 实例，或数据库中的解析 snapshot。

    Returns:
        DifyDocumentBlocksInput: 可传给历史 block-loop workflow 的结构化输入。

    Boundary:
        该函数只服务历史逐块识别实验，正式合同审查 MVP 不再使用该输入形态。
    """
    snapshot = _snapshot_to_dict(parsed_document)
    section_lookup = _build_section_lookup(snapshot)
    blocks: list[DifyDocumentBlock] = []

    for block in snapshot.get("blocks") or []:
        if not isinstance(block, Mapping):
            continue
        text = str(block.get("text") or "").strip()
        if not text:
            continue
        block_id = _required_string(block.get("id"), field_name="blocks[].id")
        section_id, section_title = section_lookup.get(block_id, (None, None))
        blocks.append(
            DifyDocumentBlock(
                block_id=block_id,
                block_type=str(block.get("kind") or UNKNOWN_BLOCK_TYPE),
                section_id=section_id,
                section_title=section_title,
                text=text,
            )
        )

    return DifyDocumentBlocksInput(
        file_parse_task_id=file_parse_task_id,
        contract_type=contract_type,
        blocks=blocks,
    )


def build_document_blocks_json(
    *,
    file_parse_task_id: str,
    contract_type: str,
    parsed_document: ParsedDocumentV1 | Mapping[str, Any],
) -> str:
    """构建历史 block-loop workflow 的 ``document_blocks_json`` 字符串。"""
    payload = build_document_blocks_input(
        file_parse_task_id=file_parse_task_id,
        contract_type=contract_type,
        parsed_document=parsed_document,
    )
    return json.dumps(payload.model_dump(mode="json"), ensure_ascii=False)


def _snapshot_to_dict(parsed_document: ParsedDocumentV1 | Mapping[str, Any]) -> dict[str, Any]:
    """把解析结果统一转换为普通字典。"""
    if isinstance(parsed_document, ParsedDocumentV1):
        return parsed_document.to_dict()
    if isinstance(parsed_document, Mapping):
        return dict(parsed_document)
    raise ValueError("parsed_document must be ParsedDocumentV1 or mapping snapshot")


def _build_section_lookup(snapshot: Mapping[str, Any]) -> dict[str, tuple[str | None, str | None]]:
    """构建 ``block_id -> (section_id, section_title)`` 反查表。"""
    selected: dict[str, tuple[int, int, str | None, str | None]] = {}
    for index, section in enumerate(snapshot.get("sections") or []):
        if not isinstance(section, Mapping):
            continue
        level = _int_or_default(section.get("level"), default=0)
        section_id = _optional_string(section.get("id"))
        section_title = _optional_string(section.get("title"))
        for block_id in _section_block_ids(section):
            current = selected.get(block_id)
            if current is None or (level, index) >= (current[0], current[1]):
                selected[block_id] = (level, index, section_id, section_title)
    return {block_id: (item[2], item[3]) for block_id, item in selected.items()}


def _section_block_ids(section: Mapping[str, Any]) -> list[str]:
    """返回一个 section 覆盖的 block ID 列表。"""
    block_ids: list[str] = []
    heading_block_id = _optional_string(section.get("heading_block_id"))
    if heading_block_id:
        block_ids.append(heading_block_id)
    for block_id in section.get("block_ids") or []:
        normalized = _optional_string(block_id)
        if normalized:
            block_ids.append(normalized)
    return block_ids


def _required_string(value: Any, *, field_name: str) -> str:
    """读取必填字符串字段。"""
    normalized = _optional_string(value)
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _optional_string(value: Any) -> str | None:
    """把可选值转换成去空白字符串。"""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _int_or_default(value: Any, *, default: int) -> int:
    """把可选值转换成整数，失败时返回默认值。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
