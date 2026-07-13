import json
from collections.abc import Mapping
from typing import Any, Literal

from app.integrations.file_reader.structure.schema import ParsedDocumentV1
from app.modules.contract_review.context_experiment.filters import conservative_filter_blocks
from app.modules.contract_review.context_experiment.schemas import (
    ContractFullContextInput,
    ContextSourceBlock,
    FilteredContextBlock,
)

FilterMode = Literal["none", "conservative"]
UNKNOWN_BLOCK_TYPE = "unknown"
CONTEXT_TRUNCATED = "context_truncated"


def build_full_context_input(
    *,
    file_parse_task_id: str,
    contract_type: str,
    parsed_document: ParsedDocumentV1 | Mapping[str, Any],
    filter_mode: FilterMode = "none",
    max_context_chars: int | None = None,
) -> ContractFullContextInput:
    """构建全文上下文实验的 Dify 输入对象。

    Args:
        file_parse_task_id: 已成功解析的 ``file_parse_task.id``。
        contract_type: 合同类型，例如 ``warehouse`` 或 ``transport``。
        parsed_document: ``ParsedDocumentV1`` 实例，或数据库中的
            ``file_parse_task.result_snapshot`` 字典。
        filter_mode: ``none`` 表示只排除空文本；``conservative`` 会额外过滤纯页码、
            目录、签章页提示和重复页眉页脚。
        max_context_chars: 可选最大上下文字符数。为空时不截断。

    Returns:
        ContractFullContextInput: 可传给全文上下文实验 Dify workflow 的输入。

    Boundary:
        本函数只做合同审查实验输入适配，不修改 ``ParsedDocumentV1``，也不把合同
        审查过滤规则写入 ``file_reader``。
    """
    if filter_mode not in {"none", "conservative"}:
        raise ValueError("filter_mode must be 'none' or 'conservative'")

    snapshot = _snapshot_to_dict(parsed_document)
    blocks = _build_source_blocks(snapshot)
    filter_reasons = _build_filter_reasons(blocks, filter_mode=filter_mode)

    included_segments: list[str] = []
    included_block_ids: list[str] = []
    filtered_blocks = [
        FilteredContextBlock(block_id=block_id, reason=reason)
        for block_id, reason in filter_reasons.items()
    ]
    warnings: list[str] = []
    used_chars = 0

    for index, block in enumerate(blocks):
        if block.block_id in filter_reasons:
            continue
        segment = _format_tagged_block(block)
        next_length = used_chars + len(segment) + (2 if included_segments else 0)
        if max_context_chars is not None and next_length > max_context_chars:
            _append_warning(warnings, CONTEXT_TRUNCATED)
            for truncated_block in blocks[index:]:
                if truncated_block.block_id not in filter_reasons:
                    filtered_blocks.append(
                        FilteredContextBlock(
                            block_id=truncated_block.block_id,
                            reason=CONTEXT_TRUNCATED,
                        )
                    )
            break
        included_segments.append(segment)
        included_block_ids.append(block.block_id)
        used_chars = next_length

    filtered_block_ids = [item.block_id for item in filtered_blocks]
    return ContractFullContextInput(
        file_parse_task_id=file_parse_task_id,
        contract_type=contract_type,
        context_text="\n\n".join(included_segments),
        included_block_ids=included_block_ids,
        filtered_block_ids=filtered_block_ids,
        filtered_blocks=filtered_blocks,
        warnings=warnings,
    )


def build_full_context_json(
    *,
    file_parse_task_id: str,
    contract_type: str,
    parsed_document: ParsedDocumentV1 | Mapping[str, Any],
    filter_mode: FilterMode = "none",
    max_context_chars: int | None = None,
) -> str:
    """构建全文上下文实验的 JSON 字符串。

    Args:
        file_parse_task_id: 已成功解析的 ``file_parse_task.id``。
        contract_type: 合同类型，例如 ``warehouse`` 或 ``transport``。
        parsed_document: ``ParsedDocumentV1`` 实例，或数据库中的解析 snapshot。
        filter_mode: 全文实验过滤模式。
        max_context_chars: 可选最大上下文字符数。

    Returns:
        str: UTF-8 友好的 JSON 字符串，可作为 Dify 输入变量。
    """
    payload = build_full_context_input(
        file_parse_task_id=file_parse_task_id,
        contract_type=contract_type,
        parsed_document=parsed_document,
        filter_mode=filter_mode,
        max_context_chars=max_context_chars,
    )
    return json.dumps(payload.model_dump(mode="json"), ensure_ascii=False)


def _snapshot_to_dict(parsed_document: ParsedDocumentV1 | Mapping[str, Any]) -> dict[str, Any]:
    """把解析结果统一转换为普通字典。"""
    if isinstance(parsed_document, ParsedDocumentV1):
        return parsed_document.to_dict()
    if isinstance(parsed_document, Mapping):
        return dict(parsed_document)
    raise ValueError("parsed_document must be ParsedDocumentV1 or mapping snapshot")


def _build_source_blocks(snapshot: Mapping[str, Any]) -> list[ContextSourceBlock]:
    """从解析 snapshot 中构建全文实验 block 列表。"""
    section_lookup = _build_section_lookup(snapshot)
    blocks: list[ContextSourceBlock] = []
    for block in snapshot.get("blocks") or []:
        if not isinstance(block, Mapping):
            continue
        block_id = _required_string(block.get("id"), field_name="blocks[].id")
        section_id, section_title = section_lookup.get(block_id, (None, None))
        blocks.append(
            ContextSourceBlock(
                block_id=block_id,
                block_type=str(block.get("kind") or UNKNOWN_BLOCK_TYPE),
                section_id=section_id,
                section_title=section_title,
                text=str(block.get("text") or "").strip(),
            )
        )
    return blocks


def _build_filter_reasons(
    blocks: list[ContextSourceBlock],
    *,
    filter_mode: FilterMode,
) -> dict[str, str]:
    """按过滤模式返回 block 排除原因。"""
    if filter_mode == "none":
        return {
            block.block_id: "blank_text"
            for block in blocks
            if not block.text.strip()
        }
    return conservative_filter_blocks(blocks)


def _format_tagged_block(block: ContextSourceBlock) -> str:
    """把 block 渲染成带来源锚点的全文上下文片段。"""
    tags = [
        f"block_id={_tag_value(block.block_id)}",
        f"type={_tag_value(block.block_type)}",
        f"section_id={_tag_value(block.section_id)}",
        f"section_title={_tag_value(block.section_title)}",
    ]
    return f"[{']['.join(tags)}]\n{block.text}"


def _tag_value(value: str | None) -> str:
    """把 tag 值转换成单行安全字符串。"""
    if value is None:
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").replace("]", ")").strip()


def _build_section_lookup(snapshot: Mapping[str, Any]) -> dict[str, tuple[str | None, str | None]]:
    """构建 ``block_id -> (section_id, section_title)`` 反查表。

    同一个 block 同时挂到父章节和子章节时，优先选择层级更深的章节。
    """
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


def _append_warning(warnings: list[str], warning: str) -> None:
    """向 warning 列表追加去重后的稳定字符串。"""
    if warning and warning not in warnings:
        warnings.append(warning)
