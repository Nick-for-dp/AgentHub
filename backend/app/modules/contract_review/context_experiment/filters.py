import re
from collections import Counter
from collections.abc import Sequence

from app.modules.contract_review.context_experiment.schemas import ContextSourceBlock

BLANK_TEXT = "blank_text"
PURE_PAGE_NUMBER = "pure_page_number"
TABLE_OF_CONTENTS = "table_of_contents"
SIGNATURE_OR_SEAL = "signature_or_seal"
REPEATED_HEADER_FOOTER = "repeated_header_footer"

_PURE_PAGE_RE = re.compile(
    r"^\s*(?:[-—]?\s*\d{1,4}\s*[-—]?|第\s*\d{1,4}\s*页(?:\s*/\s*共\s*\d{1,4}\s*页)?|page\s+\d{1,4}(?:\s+of\s+\d{1,4})?)\s*$",
    re.IGNORECASE,
)
_TOC_LINE_RE = re.compile(r".*(?:\.{2,}|…{2,}|\s{2,})\s*\d{1,4}\s*$")
_SIGNATURE_RE = re.compile(
    r"(以下无正文|签字盖章页|签署页|盖章页|甲方\s*[（(]盖章[）)]|乙方\s*[（(]盖章[）)]|法定代表人.*签字|授权代表.*签字)"
)
_BUSINESS_SIGNAL_RE = re.compile(
    r"(货物|存货|仓储物|单据|验收|入库|出库|提货|付款|结算|赔偿|违约|侵权|留置|仲裁|诉讼|法院|争议|责任|质量|数量|包装|节假日|短信|吨|甲方|乙方|我方|我司|受托方|承运方|保管方|客户|委托方|托运方|提货方)"
)


def conservative_filter_blocks(blocks: Sequence[ContextSourceBlock]) -> dict[str, str]:
    """对全文实验输入执行保守过滤。

    Args:
        blocks: 已按文档顺序标准化的 blocks。

    Returns:
        dict[str, str]: ``block_id -> reason``，表示应从全文上下文中排除的 blocks。

    Policy:
        只过滤明显无关内容：空文本、纯页码、目录、签章页提示、重复页眉页脚。
        含有合同业务信号的文本默认保留，避免删除主体定义、付款、验收、争议解决、
        附件表格等对条款识别有价值的上下文。
    """
    decisions: dict[str, str] = {}
    normalized_counts = Counter(_normalize_repeated_text(block.text) for block in blocks)

    for block in blocks:
        text = block.text.strip()
        if not text:
            decisions[block.block_id] = BLANK_TEXT
            continue
        if _looks_like_page_number(text):
            decisions[block.block_id] = PURE_PAGE_NUMBER
            continue
        if _looks_like_toc(text):
            decisions[block.block_id] = TABLE_OF_CONTENTS
            continue
        if _looks_like_signature_or_seal(text):
            decisions[block.block_id] = SIGNATURE_OR_SEAL
            continue
        normalized = _normalize_repeated_text(text)
        if (
            normalized
            and normalized_counts[normalized] >= 3
            and len(normalized) <= 80
            and not _has_business_signal(text)
        ):
            decisions[block.block_id] = REPEATED_HEADER_FOOTER
    return decisions


def _looks_like_page_number(text: str) -> bool:
    """判断文本是否为纯页码。"""
    return bool(_PURE_PAGE_RE.match(text))


def _looks_like_toc(text: str) -> bool:
    """判断文本是否为目录或目录行集合。"""
    stripped = text.strip()
    if stripped in {"目录", "目 录", "contents", "Contents"}:
        return True
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) < 3:
        return False
    toc_like_count = sum(1 for line in lines if _TOC_LINE_RE.match(line))
    return toc_like_count == len(lines)


def _looks_like_signature_or_seal(text: str) -> bool:
    """判断文本是否为签章页或签署提示。"""
    return bool(_SIGNATURE_RE.search(text))


def _has_business_signal(text: str) -> bool:
    """判断文本是否包含合同审查相关业务信号。"""
    return bool(_BUSINESS_SIGNAL_RE.search(text))


def _normalize_repeated_text(text: str) -> str:
    """归一化文本以识别重复页眉页脚。"""
    return " ".join(text.split())

