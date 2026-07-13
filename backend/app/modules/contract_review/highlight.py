from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceSpan:
    """条款在解析文本中的确定性高亮位置。"""

    block_id: str
    section_id: str | None
    section_title: str | None
    start_offset: int
    end_offset: int
    matched_text: str

    def to_dict(self) -> dict[str, Any]:
        """返回可写入 JSON 的普通字典。"""
        return {
            "block_id": self.block_id,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "matched_text": self.matched_text,
        }


@dataclass(frozen=True)
class HighlightResolution:
    """高亮定位结果。"""

    source_spans: list[SourceSpan] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)


class HighlightResolver:
    """基于 ``block_id + text`` 的解析文本高亮定位器。

    LLM 不负责计算 offset。本类只在原始 ``ParsedDocumentV1.blocks[].text`` 中查找
    Dify 抽取出的候选条款文本，保证高亮结果可解释、可复核。
    """

    def __init__(self, parsed_snapshot: Mapping[str, Any]):
        """初始化 block 和 section 反查表。"""
        self.block_lookup = _build_block_lookup(parsed_snapshot)
        self.section_lookup = _build_section_lookup(parsed_snapshot)

    def resolve(self, *, clause_text: str, source_block_ids: list[str]) -> HighlightResolution:
        """解析单条条款的高亮 span。

        Args:
            clause_text: Dify 抽取的候选条款原文。
            source_block_ids: Dify 给出的来源 block ID 列表。

        Returns:
            HighlightResolution: 包含 0 到多条 source_spans 和稳定 warning。
        """
        warnings: list[dict[str, Any]] = []
        spans: list[SourceSpan] = []
        normalized_clause = " ".join(clause_text.split())
        if not normalized_clause:
            return HighlightResolution(
                warnings=[{"code": "empty_clause_text", "message": "条款文本为空，无法高亮。"}]
            )
        if not source_block_ids:
            return HighlightResolution(
                warnings=[{"code": "source_block_missing", "message": "条款缺少来源 block。"}]
            )

        for block_id in source_block_ids:
            block = self.block_lookup.get(block_id)
            if block is None:
                warnings.append(
                    {
                        "code": "source_block_not_found",
                        "block_id": block_id,
                        "message": "来源 block 不存在。",
                    }
                )
                continue
            block_text = str(block.get("text") or "")
            matches = _find_matches(block_text, normalized_clause)
            if not matches:
                warnings.append(
                    {
                        "code": "highlight_match_not_found",
                        "block_id": block_id,
                        "message": "条款文本未在来源 block 中找到。",
                    }
                )
                continue
            if len(matches) > 1:
                warnings.append(
                    {
                        "code": "highlight_match_ambiguous",
                        "block_id": block_id,
                        "message": "条款文本在来源 block 中出现多次，已取首个匹配。",
                    }
                )
            start_offset, end_offset = matches[0]
            section_id, section_title = self.section_lookup.get(block_id, (None, None))
            spans.append(
                SourceSpan(
                    block_id=block_id,
                    section_id=section_id,
                    section_title=section_title,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    matched_text=block_text[start_offset:end_offset],
                )
            )
        return HighlightResolution(source_spans=spans, warnings=warnings)


def _find_matches(block_text: str, clause_text: str) -> list[tuple[int, int]]:
    """在 block 文本中查找条款文本，返回所有字符 offset。"""
    matches: list[tuple[int, int]] = []
    start = 0
    while True:
        index = block_text.find(clause_text, start)
        if index < 0:
            break
        matches.append((index, index + len(clause_text)))
        start = index + 1
    return matches


def _build_block_lookup(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """构建 block ID 到 block 的反查表。"""
    lookup: dict[str, Mapping[str, Any]] = {}
    for block in snapshot.get("blocks") or []:
        if not isinstance(block, Mapping):
            continue
        block_id = str(block.get("id") or "").strip()
        if block_id:
            lookup[block_id] = block
    return lookup


def _build_section_lookup(snapshot: Mapping[str, Any]) -> dict[str, tuple[str | None, str | None]]:
    """构建 block ID 到最具体 section 的反查表。"""
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
    return {block_id: (value[2], value[3]) for block_id, value in selected.items()}


def _section_block_ids(section: Mapping[str, Any]) -> list[str]:
    """返回 section 覆盖的 block ID。"""
    block_ids: list[str] = []
    heading_block_id = _optional_string(section.get("heading_block_id"))
    if heading_block_id:
        block_ids.append(heading_block_id)
    for block_id in section.get("block_ids") or []:
        normalized = _optional_string(block_id)
        if normalized:
            block_ids.append(normalized)
    return block_ids


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_default(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
