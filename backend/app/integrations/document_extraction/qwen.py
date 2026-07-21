import json

import httpx
from pydantic import SecretStr, ValidationError

from app.integrations.document_extraction.errors import DocumentExtractionIntegrationError
from app.integrations.document_extraction.schemas import (
    QwenExtractionResponse,
    QwenFieldCandidate,
)
from app.modules.risk_assessment.extraction.schemas import DocumentType


class QwenExtractionClient:
    """百炼 OpenAI-compatible JSON Mode client；一期只发送文本。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: SecretStr,
        model: str,
        request_timeout_seconds: float = 180.0,
        max_response_bytes: int = 2 * 1024 * 1024,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self.request_timeout_seconds = request_timeout_seconds
        self.max_response_bytes = max_response_bytes
        self._http_client = http_client

    async def extract(
        self,
        *,
        document_type: DocumentType,
        field_codes: tuple[str, ...],
        field_guidance: dict[str, str],
        prompt: str,
        anchored_text: str,
    ) -> list[QwenFieldCandidate]:
        if not anchored_text.strip():
            return []
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": _build_prompt(
                        document_type=document_type,
                        field_codes=field_codes,
                        field_guidance=field_guidance,
                        prompt=prompt,
                        anchored_text=anchored_text,
                    ),
                }
            ],
            "response_format": {"type": "json_object"},
            "enable_thinking": False,
            "temperature": 0,
            "max_tokens": 5000,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        if self._http_client is not None:
            return await self._extract_with_client(self._http_client, headers, body, field_codes)
        timeout = httpx.Timeout(self.request_timeout_seconds, connect=20.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            return await self._extract_with_client(client, headers, body, field_codes)

    async def _extract_with_client(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        body: dict,
        field_codes: tuple[str, ...],
    ) -> list[QwenFieldCandidate]:
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DocumentExtractionIntegrationError("Qwen request failed") from exc
        if len(response.content) > self.max_response_bytes:
            raise DocumentExtractionIntegrationError("Qwen response exceeds size limit")
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            result = QwenExtractionResponse.model_validate(parsed)
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise DocumentExtractionIntegrationError(
                "Qwen returned invalid structured output"
            ) from exc

        allowed = set(field_codes)
        seen: set[str] = set()
        candidates: list[QwenFieldCandidate] = []
        for candidate in result.fields:
            if candidate.field_code not in allowed or candidate.field_code in seen:
                continue
            seen.add(candidate.field_code)
            candidates.append(candidate)
        return candidates


def _build_prompt(
    *,
    document_type: DocumentType,
    field_codes: tuple[str, ...],
    field_guidance: dict[str, str],
    prompt: str,
    anchored_text: str,
) -> str:
    guidance = [
        {"field_code": code, "description": field_guidance.get(code, code)}
        for code in field_codes
    ]
    return (
        "你是供应链风控文档字段抽取器。只能使用输入中的带锚点原文。"
        "输出必须是 JSON 对象，格式为 "
        '{"fields":[{"field_code":"...","raw_value":null或字符串或数字,'
        '"source_ids":["P001-B001"],"quote":"锚点中的简短原文"}]}。'
        "每个声明字段必须恰好出现一次；缺失时 raw_value 为 null、source_ids 为空、"
        "quote 为空。source_ids 只能从输入锚点中选择。不得输出 bbox，不得计算、"
        "补全或猜测。quote 应尽量逐字复制原文；表格数字不得改写数值。\n"
        f"文档类型：{document_type.value}\n"
        f"字段定义：{json.dumps(guidance, ensure_ascii=False)}\n"
        f"专用要求：{prompt}\n"
        f"带锚点原文：\n{anchored_text}"
    )
