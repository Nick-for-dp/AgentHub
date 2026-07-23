import asyncio
import json
import re
import time
from collections.abc import Iterable
from urllib.parse import urlparse

import httpx
from pydantic import SecretStr

from app.integrations.document_extraction.errors import DocumentExtractionIntegrationError
from app.integrations.document_extraction.schemas import OcrBlock, OcrDocument


_SAFE_JOB_ID = re.compile(r"[A-Za-z0-9._-]{1,200}")
_SAFE_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


class PaddleOcrClient:
    """PaddleOCR AI Studio 异步 job client。"""

    def __init__(
        self,
        *,
        job_url: str,
        api_token: SecretStr,
        model: str,
        allowed_result_hosts: Iterable[str],
        poll_interval_seconds: float = 4.0,
        poll_max_interval_seconds: float = 20.0,
        job_timeout_seconds: float = 600.0,
        request_timeout_seconds: float = 180.0,
        max_result_bytes: int = 50 * 1024 * 1024,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.job_url = job_url.rstrip("/")
        self._api_token = api_token
        self.model = model
        self.allowed_result_hosts = frozenset(
            host.strip().lower() for host in allowed_result_hosts if host.strip()
        )
        self.poll_interval_seconds = poll_interval_seconds
        self.poll_max_interval_seconds = max(
            poll_interval_seconds,
            poll_max_interval_seconds,
        )
        self.job_timeout_seconds = job_timeout_seconds
        self.request_timeout_seconds = request_timeout_seconds
        self.max_result_bytes = max_result_bytes
        self._http_client = http_client

    async def extract(self, *, filename: str, content: bytes) -> OcrDocument:
        if not content:
            raise DocumentExtractionIntegrationError("PaddleOCR input file is empty")
        if self._http_client is not None:
            return await self._extract_with_client(self._http_client, filename, content)
        timeout = httpx.Timeout(self.request_timeout_seconds, connect=20.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            return await self._extract_with_client(client, filename, content)

    async def _extract_with_client(
        self,
        client: httpx.AsyncClient,
        filename: str,
        content: bytes,
    ) -> OcrDocument:
        headers = {"Authorization": f"bearer {self._api_token.get_secret_value()}"}
        data = {
            "model": self.model,
            "optionalPayload": json.dumps(
                {
                    "useDocOrientationClassify": False,
                    "useDocUnwarping": False,
                    "useChartRecognition": False,
                }
            ),
        }
        try:
            response = await client.post(
                self.job_url,
                headers=headers,
                data=data,
                files={"file": (filename, content, _content_type(filename))},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DocumentExtractionIntegrationError(
                "PaddleOCR job submission failed"
            ) from exc

        payload = _json_object(response, "PaddleOCR job submission")
        job_id = str((payload.get("data") or {}).get("jobId") or "")
        if not _SAFE_JOB_ID.fullmatch(job_id):
            raise DocumentExtractionIntegrationError("PaddleOCR returned invalid job id")

        result_url = await self._poll_result_url(client, headers, job_id)
        result_bytes = await self._download_result(client, result_url)
        return _parse_jsonl_result(result_bytes)

    async def _poll_result_url(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        job_id: str,
    ) -> str:
        deadline = time.monotonic() + self.job_timeout_seconds
        poll_delay = self.poll_interval_seconds
        while time.monotonic() < deadline:
            try:
                response = await client.get(f"{self.job_url}/{job_id}", headers=headers)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise DocumentExtractionIntegrationError(
                    "PaddleOCR job polling failed"
                ) from exc
            payload = _json_object(response, "PaddleOCR job polling")
            data = payload.get("data") or {}
            state = str(data.get("state") or "")
            if state == "done":
                result_url = str((data.get("resultUrl") or {}).get("jsonUrl") or "")
                self._validate_result_url(result_url)
                return result_url
            if state == "failed":
                raise DocumentExtractionIntegrationError("PaddleOCR job failed")
            if state not in {"pending", "running"}:
                raise DocumentExtractionIntegrationError(
                    "PaddleOCR returned unknown job state"
                )
            remaining = max(0.0, deadline - time.monotonic())
            await asyncio.sleep(min(poll_delay, remaining))
            poll_delay = min(
                self.poll_max_interval_seconds,
                max(self.poll_interval_seconds, poll_delay * 2),
            )
        raise DocumentExtractionIntegrationError("PaddleOCR job timed out")

    def _validate_result_url(self, result_url: str) -> None:
        parsed = urlparse(result_url)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme.lower() != "https" or not hostname:
            raise DocumentExtractionIntegrationError("PaddleOCR result URL must use HTTPS")
        if not any(
            _hostname_matches_pattern(hostname, pattern)
            for pattern in self.allowed_result_hosts
        ):
            raise DocumentExtractionIntegrationError(
                f"PaddleOCR result URL host is not allowed: {hostname}"
            )

    async def _download_result(
        self,
        client: httpx.AsyncClient,
        result_url: str,
    ) -> bytes:
        chunks: list[bytes] = []
        size = 0
        try:
            async with client.stream("GET", result_url) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > self.max_result_bytes:
                        raise DocumentExtractionIntegrationError(
                            "PaddleOCR result exceeds size limit"
                        )
                    chunks.append(chunk)
        except DocumentExtractionIntegrationError:
            raise
        except httpx.HTTPError as exc:
            raise DocumentExtractionIntegrationError(
                "PaddleOCR result download failed"
            ) from exc
        return b"".join(chunks)


def _json_object(response: httpx.Response, operation: str) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise DocumentExtractionIntegrationError(f"{operation} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise DocumentExtractionIntegrationError(f"{operation} returned unexpected JSON")
    return payload


def _hostname_matches_pattern(hostname: str, pattern: str) -> bool:
    """匹配精确主机或单 DNS 标签内的 ``*``，避免通配符跨越域名层级。"""
    hostname_labels = hostname.split(".")
    pattern_labels = pattern.split(".")
    if len(hostname_labels) != len(pattern_labels):
        return False
    for hostname_label, pattern_label in zip(hostname_labels, pattern_labels):
        if not _SAFE_HOST_LABEL.fullmatch(hostname_label):
            return False
        if "*" not in pattern_label:
            if hostname_label != pattern_label:
                return False
            continue
        label_pattern = re.escape(pattern_label).replace(r"\*", r"[a-z0-9-]+")
        if re.fullmatch(label_pattern, hostname_label) is None:
            return False
    return True


def _parse_jsonl_result(content: bytes) -> OcrDocument:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentExtractionIntegrationError(
            "PaddleOCR result is not UTF-8 JSONL"
        ) from exc

    pages: list[dict] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DocumentExtractionIntegrationError(
                "PaddleOCR result contains invalid JSONL"
            ) from exc
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise DocumentExtractionIntegrationError(
                "PaddleOCR result line has no result object"
            )
        layout_pages = result.get("layoutParsingResults") or []
        if not isinstance(layout_pages, list):
            raise DocumentExtractionIntegrationError(
                "PaddleOCR layoutParsingResults must be a list"
            )
        pages.extend(page for page in layout_pages if isinstance(page, dict))

    if not pages:
        raise DocumentExtractionIntegrationError("PaddleOCR returned no pages")

    blocks: list[OcrBlock] = []
    for page_number, page in enumerate(pages, start=1):
        pruned = page.get("prunedResult") or {}
        items = pruned.get("parsing_res_list") or []
        if not isinstance(items, list):
            items = []
        ordered = sorted(
            (item for item in items if isinstance(item, dict)),
            key=lambda item: (
                item.get("block_order") is None,
                item.get("block_order") or 0,
            ),
        )
        page_blocks: list[OcrBlock] = []
        for item in ordered:
            block_text = str(item.get("block_content") or "").strip()
            if not block_text:
                continue
            source_id = f"P{page_number:03d}-B{len(page_blocks) + 1:03d}"
            page_blocks.append(
                OcrBlock(
                    source_id=source_id,
                    page_number=page_number,
                    text=block_text,
                    bbox=item.get("block_bbox"),
                    label=str(item.get("block_label") or "") or None,
                )
            )
        if not page_blocks:
            markdown = str((page.get("markdown") or {}).get("text") or "").strip()
            if markdown:
                page_blocks.append(
                    OcrBlock(
                        source_id=f"P{page_number:03d}-B001",
                        page_number=page_number,
                        text=markdown,
                    )
                )
        blocks.extend(page_blocks)

    if not blocks:
        raise DocumentExtractionIntegrationError("PaddleOCR returned no text blocks")
    return OcrDocument(blocks=tuple(blocks), page_count=len(pages))


def _content_type(filename: str) -> str:
    suffix = filename.lower().rsplit(".", maxsplit=1)[-1]
    return {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }.get(suffix, "application/octet-stream")
