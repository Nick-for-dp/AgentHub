import re
import unicodedata
from pathlib import Path
from typing import Any

from app.integrations.document_extraction.errors import DocumentExtractionIntegrationError
from app.integrations.document_extraction.paddleocr import PaddleOcrClient
from app.integrations.document_extraction.qwen import QwenExtractionClient
from app.integrations.document_extraction.schemas import OcrBlock, OcrDocument, QwenFieldCandidate
from app.integrations.file_reader.structure.schema import ParsedDocumentV1
from app.modules.risk_assessment.extraction.schemas import DocumentType
from app.modules.risk_assessment.extraction.document_type_validation import (
    validate_document_type,
)


_SCANNED_WARNING = "SCANNED_TEXT_UNAVAILABLE"
_IMAGE_TYPES = {"png", "jpg", "jpeg"}
_SUPPORTED_TYPES = {"pdf", "docx", *_IMAGE_TYPES}

_FIELD_GUIDANCE = {
    "purchase_signing_date": "采购合同双方签字或盖章处的落款签署日期，不是交货、付款或有效期日期",
    "sales_signing_date": "销售合同双方签字或盖章处的落款签署日期，不是交货、付款或有效期日期",
    "deposit_amount": "只提取合同明确写出的保证金金额，不得用比例乘合同金额计算",
    "key_customer_discount": "只提取合同明确写出的大客户优惠金额",
    "occupied_days": "结算单明确记录的资金占用天数",
    "raw_business_mode_text": (
        "只读取审批表中标题为‘业务性质’的表格栏：仅使用已勾选项及其自由填写内容，"
        "不得读取‘业务模式简介’行。若同时勾选‘预付款’和‘其他（联销等）’并填写"
        "‘联销’，返回‘联销（预付款+联合销售）’；不映射正式枚举，也不从合同推断"
    ),
}


class PaddleOcrQwenDocumentExtractionProvider:
    """一期唯一 production adapter：PaddleOCR 定位，Qwen 文本语义选择。"""

    def __init__(
        self,
        *,
        paddleocr: PaddleOcrClient,
        qwen: QwenExtractionClient,
    ) -> None:
        self.paddleocr = paddleocr
        self.qwen = qwen
        self.version = f"paddleocr:{paddleocr.model}+qwen:{qwen.model}:ocr-text-v1"

    async def extract(
        self,
        *,
        document_type: DocumentType,
        parsed_document: ParsedDocumentV1,
        source_filename: str,
        source_content: bytes,
        field_codes: tuple[str, ...],
        prompt: str,
        prompt_version: str,
        expected_title_markers: tuple[str, ...],
        conflicting_title_markers: tuple[str, ...],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        del prompt_version
        suffix = Path(source_filename).suffix.lower().lstrip(".")
        if suffix not in _SUPPORTED_TYPES:
            raise DocumentExtractionIntegrationError(
                f"unsupported risk document file type: {suffix or 'unknown'}"
            )

        if _requires_paddleocr(suffix, parsed_document):
            ocr_document = await self.paddleocr.extract(
                filename=source_filename,
                content=source_content,
            )
            expected_pages = parsed_document.metadata.page_count
            if expected_pages is not None and ocr_document.page_count != expected_pages:
                raise DocumentExtractionIntegrationError(
                    "PaddleOCR page count does not match parsed document"
                )
        else:
            ocr_document = _document_from_parsed_blocks(parsed_document)

        validation = validate_document_type(
            declared_type=document_type,
            original_filename=source_filename,
            block_texts=(block.text for block in ocr_document.blocks),
            expected_markers=expected_title_markers,
            conflicting_markers=conflicting_title_markers,
        )

        candidates = await self.qwen.extract(
            document_type=document_type,
            field_codes=field_codes,
            field_guidance=_FIELD_GUIDANCE,
            prompt=prompt,
            anchored_text=ocr_document.anchored_text,
        )
        fields = [
            item
            for candidate in candidates
            if (item := _candidate_to_provider_field(candidate, ocr_document)) is not None
        ]
        return fields, validation.warnings


def _requires_paddleocr(suffix: str, parsed_document: ParsedDocumentV1) -> bool:
    if suffix in _IMAGE_TYPES:
        return True
    if suffix == "docx":
        return False
    if not parsed_document.blocks:
        return True
    return any(warning.code == _SCANNED_WARNING for warning in parsed_document.warnings)


def _document_from_parsed_blocks(parsed_document: ParsedDocumentV1) -> OcrDocument:
    blocks = tuple(
        OcrBlock(
            source_id=block.id,
            page_number=block.source_location.page_number,
            text=block.text,
            bbox=block.metadata.get("bbox"),
            label=block.kind,
        )
        for block in parsed_document.blocks
        if block.text.strip()
    )
    return OcrDocument(
        blocks=blocks,
        page_count=parsed_document.metadata.page_count or (1 if blocks else 0),
    )


def _candidate_to_provider_field(
    candidate: QwenFieldCandidate,
    document: OcrDocument,
) -> dict[str, Any] | None:
    if candidate.raw_value is None:
        return None
    by_id = {block.source_id: block for block in document.blocks}
    sources: list[dict[str, Any]] = []
    for source_id in candidate.source_ids:
        block = by_id.get(source_id)
        if block is None:
            continue
        business_nature_quote = (
            _business_nature_evidence(block.text, candidate.raw_value)
            if candidate.field_code == "raw_business_mode_text"
            else None
        )
        if business_nature_quote is None and not _matches_block(
            block.text,
            quote=candidate.quote,
            raw_value=candidate.raw_value,
        ):
            continue
        source: dict[str, Any] = {"block_id": block.source_id}
        if block.page_number is not None:
            source["page_number"] = block.page_number
        exact_quote = business_nature_quote or _exact_evidence_text(
            block.text, quote=candidate.quote, raw_value=candidate.raw_value
        )
        if exact_quote:
            source["quote"] = exact_quote
        if block.bbox not in (None, "", []):
            source["bbox"] = block.bbox
        sources.append(source)
    return {
        "field_code": candidate.field_code,
        "raw_value": candidate.raw_value,
        "sources": sources,
        "confidence": 1.0 if sources else 0.5,
    }


def _matches_block(text: str, *, quote: str, raw_value: Any) -> bool:
    normalized_text = _normalize_evidence(text)
    normalized_quote = _normalize_evidence(quote)
    if normalized_quote and normalized_quote in normalized_text:
        return True
    normalized_value = _normalize_evidence(str(raw_value))
    return bool(normalized_value and normalized_value in normalized_text)


def _exact_evidence_text(text: str, *, quote: str, raw_value: Any) -> str | None:
    if quote and quote in text:
        return quote
    value_text = str(raw_value)
    if value_text and value_text in text:
        return value_text
    return None


def _normalize_evidence(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", normalized)


def _business_nature_evidence(text: str, raw_value: Any) -> str | None:
    raw_normalized = _normalize_evidence(str(raw_value))
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("业务性质") or "☑" not in stripped:
            continue
        selected = [
            segment.strip()
            for segment in re.findall(r"☑([^☑□]+)", stripped)
            if segment.strip()
        ]
        if not selected:
            continue
        selected_text = " ".join(selected)
        if "预付款" in selected_text and "联销" in selected_text:
            if raw_normalized == _normalize_evidence("联销（预付款+联合销售）"):
                return stripped
        keywords = [
            keyword
            for keyword in ("预付款", "控货付款", "款到发货销售", "应收款", "联销")
            if keyword in selected_text
        ]
        if keywords and all(
            _normalize_evidence(keyword) in raw_normalized for keyword in keywords
        ):
            return stripped
    return None
