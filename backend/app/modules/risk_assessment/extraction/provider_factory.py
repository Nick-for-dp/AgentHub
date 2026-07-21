from urllib.parse import urlparse

from app.core.config import Settings, get_settings
from app.integrations.document_extraction import (
    PaddleOcrClient,
    PaddleOcrQwenDocumentExtractionProvider,
    QwenExtractionClient,
)
from app.modules.risk_assessment.extraction.ports import DocumentExtractionProvider


class DocumentExtractionProviderConfigurationError(RuntimeError):
    """provider 未选型、未配置或不允许在当前 profile 初始化。"""


PADDLEOCR_QWEN_PROVIDER_NAME = "paddleocr_qwen"


def create_document_extraction_provider(
    settings: Settings | None = None,
) -> DocumentExtractionProvider:
    """创建 ADR 选定的唯一 provider；当前选型完成前始终安全失败。"""
    resolved = settings or get_settings()
    provider_name = (resolved.risk_document_extraction_provider or "").strip().lower()
    if not provider_name:
        raise DocumentExtractionProviderConfigurationError(
            "risk document extraction provider is not configured"
        )
    if provider_name != PADDLEOCR_QWEN_PROVIDER_NAME:
        raise DocumentExtractionProviderConfigurationError(
            f"unsupported risk document extraction provider: {provider_name}"
        )
    if not resolved.risk_document_cloud_egress_enabled:
        raise DocumentExtractionProviderConfigurationError(
            "risk document cloud egress is disabled"
        )

    _require_https_url(
        "PaddleOCR job URL",
        resolved.risk_document_paddleocr_job_url,
    )
    _require_secret(
        "PaddleOCR API token",
        resolved.risk_document_paddleocr_api_token,
    )
    _require_text("PaddleOCR model", resolved.risk_document_paddleocr_model)
    if not resolved.risk_document_paddleocr_result_host_list:
        raise DocumentExtractionProviderConfigurationError(
            "PaddleOCR result hosts are not configured"
        )
    _require_https_url("Qwen base URL", resolved.risk_document_qwen_base_url)
    _require_secret("Qwen API key", resolved.risk_document_qwen_api_key)
    _require_text("Qwen model", resolved.risk_document_qwen_model)
    if resolved.risk_document_qwen_input_mode != "ocr_text":
        raise DocumentExtractionProviderConfigurationError(
            "production Qwen input mode must be ocr_text"
        )

    return PaddleOcrQwenDocumentExtractionProvider(
        paddleocr=PaddleOcrClient(
            job_url=resolved.risk_document_paddleocr_job_url,
            api_token=resolved.risk_document_paddleocr_api_token,
            model=resolved.risk_document_paddleocr_model,
            allowed_result_hosts=resolved.risk_document_paddleocr_result_host_list,
        ),
        qwen=QwenExtractionClient(
            base_url=resolved.risk_document_qwen_base_url or "",
            api_key=resolved.risk_document_qwen_api_key,
            model=resolved.risk_document_qwen_model,
        ),
    )


def _require_text(name: str, value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise DocumentExtractionProviderConfigurationError(f"{name} is not configured")
    return normalized


def _require_secret(name: str, value) -> None:
    if value is None or not value.get_secret_value().strip():
        raise DocumentExtractionProviderConfigurationError(f"{name} is not configured")


def _require_https_url(name: str, value: str | None) -> str:
    normalized = _require_text(name, value)
    parsed = urlparse(normalized)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise DocumentExtractionProviderConfigurationError(
            f"{name} must be an HTTPS URL"
        )
    return normalized
