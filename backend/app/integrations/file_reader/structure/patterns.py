import re
from dataclasses import dataclass

from app.integrations.file_reader.structure.schema import NumberingInfo


CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}

# 中文合同里标题样式经常缺失，首版主要依赖这些编号模式建立结构。
ARTICLE_RE = re.compile(r"^第(?P<num>[一二三四五六七八九十百零〇两]+)条\s*(?P<title>.*)$")
APPENDIX_RE = re.compile(
    r"^附件(?P<num>[一二三四五六七八九十百零〇两\d]+)[：:、.\s]*(?P<title>.*)$"
)
ARABIC_RE = re.compile(r"^(?P<num>\d{1,3})(?P<sep>[\.、])\s*(?P<title>.*)$")
PAREN_RE = re.compile(r"^[（(](?P<num>[一二三四五六七八九十百零〇两\d]+)[）)]\s*(?P<title>.*)$")
CN_COMMA_RE = re.compile(r"^(?P<num>[一二三四五六七八九十百零〇两]+)、\s*(?P<title>.*)$")


@dataclass(frozen=True)
class HeadingMatch:
    """某个 block 命中标题规则后的候选结果。

    Attributes:
        level: 推断层级。首期约定一级章节为 1，子条款为 2，括号子项为 3。
        numbering: 标准化编号信息；纯版式标题可为空。
        title: 标题原文，通常就是 block.text。
        confidence: 当前规则给出的置信度。
        code: 命中的规则代码，用于调试和 warning。
    """

    level: int
    numbering: NumberingInfo | None
    title: str
    confidence: float
    code: str


def chinese_to_int(value: str) -> int | None:
    """把常见中文序号转换成整数。

    Args:
        value: 中文序号或阿拉伯数字字符串，例如 ``十六``、``二``、``12``。

    Returns:
        可解析时返回整数；无法稳定解析时返回 None。

    Processing:
        1. 阿拉伯数字直接转 int。
        2. 中文数字按 ``百``、``十`` 和个位累加。
        3. 遇到不在合同序号范围内的字符时返回 None。

    Limit:
        这里只覆盖合同章节常见写法，不处理复杂金额、日期或更大中文数字。
    """
    if not value:
        return None
    if value.isdigit():
        return int(value)

    total = 0
    current = 0
    unit_seen = False
    for char in value:
        if char in CHINESE_DIGITS:
            current = CHINESE_DIGITS[char]
            continue
        if char == "十":
            unit_seen = True
            total += (current or 1) * 10
            current = 0
            continue
        if char == "百":
            unit_seen = True
            total += (current or 1) * 100
            current = 0
            continue
        return None
    total += current
    if total == 0 and not unit_seen:
        return None
    return total


def match_numbered_heading(text: str, *, has_parent: bool = False) -> HeadingMatch | None:
    """识别中文合同常见编号标题。

    Args:
        text: 待读取块文本，通常来自 ``ParsedBlock.text``。
        has_parent: 当前扫描位置前是否已经存在章节路径。

    Returns:
        命中时返回 ``HeadingMatch``；没有命中时返回 None。

    Processing:
        1. 优先识别 ``第X条``，作为一级章节。
        2. 识别 ``附件X``，作为一级附件章节。
        3. 识别 ``1.`` / ``1、``；有父章节时作为二级条款，否则作为一级编号。
        4. 识别 ``（一）`` / ``(1)``，作为更深层子项。
        5. 识别 ``一、``，作为中文顿号编号。

    Note:
        has_parent 会影响阿拉伯数字编号的层级判断：已有一级章节时，``1.`` 更可能是
        条款子项；没有父级时，它可能是文档自己的一级编号。
    """
    stripped = text.strip()
    if not stripped:
        return None

    if match := ARTICLE_RE.match(stripped):
        raw = f"第{match.group('num')}条"
        ordinal = chinese_to_int(match.group("num"))
        return HeadingMatch(
            level=1,
            numbering=NumberingInfo(
                raw=raw,
                normalized=str(ordinal) if ordinal is not None else match.group("num"),
                scheme="chinese_article",
                ordinal=ordinal,
            ),
            title=stripped,
            confidence=0.95,
            code="CHINESE_ARTICLE",
        )

    if match := APPENDIX_RE.match(stripped):
        raw = f"附件{match.group('num')}"
        ordinal = chinese_to_int(match.group("num"))
        if ordinal is None and match.group("num").isdigit():
            ordinal = int(match.group("num"))
        return HeadingMatch(
            level=1,
            numbering=NumberingInfo(
                raw=raw,
                normalized=str(ordinal) if ordinal is not None else match.group("num"),
                scheme="appendix",
                ordinal=ordinal,
            ),
            title=stripped,
            confidence=0.9,
            code="APPENDIX",
        )

    if match := ARABIC_RE.match(stripped):
        ordinal = int(match.group("num"))
        return HeadingMatch(
            level=2 if has_parent else 1,
            numbering=NumberingInfo(
                raw=f"{match.group('num')}{match.group('sep')}",
                normalized=str(ordinal),
                scheme="arabic_dot" if match.group("sep") == "." else "arabic_comma",
                ordinal=ordinal,
            ),
            title=stripped,
            confidence=0.78 if has_parent else 0.65,
            code="ARABIC_NUMBER",
        )

    if match := PAREN_RE.match(stripped):
        raw_num = match.group("num")
        ordinal = chinese_to_int(raw_num)
        return HeadingMatch(
            level=3 if has_parent else 2,
            numbering=NumberingInfo(
                raw=f"（{raw_num}）",
                normalized=str(ordinal) if ordinal is not None else raw_num,
                scheme="paren_cn",
                ordinal=ordinal,
            ),
            title=stripped,
            confidence=0.7,
            code="PAREN_NUMBER",
        )

    if match := CN_COMMA_RE.match(stripped):
        ordinal = chinese_to_int(match.group("num"))
        return HeadingMatch(
            level=2 if has_parent else 1,
            numbering=NumberingInfo(
                raw=f"{match.group('num')}、",
                normalized=str(ordinal) if ordinal is not None else match.group("num"),
                scheme="chinese_comma",
                ordinal=ordinal,
            ),
            title=stripped,
            confidence=0.72 if has_parent else 0.62,
            code="CHINESE_COMMA",
        )

    return None
