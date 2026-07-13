"""
Dify HTTP 客户端：封装对 Dify API 的所有 HTTP 调用。

平台中只有本文件可以直接发送 HTTP 请求到 Dify。
其他模块必须通过本客户端或 AgentRuntimeService 间接访问 Dify。

安全原则：
- Dify API Key 通过 HTTP Authorization Header 传递，不进入请求 body
- debug 日志必须对请求体和响应行做脱敏，防止凭据泄漏
- Dify 未配置时抛出明确异常，不返回模拟数据（保证调用记录审计可信）
"""

import json
import logging
import re
from collections.abc import AsyncIterator

import httpx

from app.core.config import get_settings
from app.core.exceptions import DifyIntegrationError, DifyNotConfiguredError
from app.core.security import sanitize_dict_for_log
from app.integrations.dify.schemas import (
    DifyChatChunk,
    DifyChatRequest,
    DifyWorkflowRunRequest,
    DifyWorkflowRunResult,
)
from app.integrations.dify.streaming import parse_sse_lines

logger = logging.getLogger(__name__)


def _sanitize_headers_for_log(headers: dict[str, str]) -> dict[str, str]:
    """对 HTTP 请求头做脱敏处理，替换 Authorization 等敏感头。

    HTTP header 名称大小写不敏感，本函数统一用小写比较。
    如果未来新增敏感 header，在此函数中追加。
    """
    safe = dict(headers)
    # 将 header key 转为小写进行比较（httpx 内部也使用小写 header）
    lower_headers = {k.lower(): k for k in safe}
    for sensitive in ("authorization",):
        original_key = lower_headers.get(sensitive)
        if original_key is not None:
            safe[original_key] = "Bearer ***"
    return safe


def _sanitize_sse_line_for_log(line: str) -> str:
    """对 SSE 行做结构化脱敏。

    核心原则：JSON 解析必须在截断之前完成。
    如果先截断再解析，超长合法 JSON 会因截断变成非法 JSON，
    从而绕过脱敏，导致敏感字段以原文形式泄漏到日志。

    策略：
    1. 非 data 行（keepalive 注释、空行等）：截断后直接返回。
    2. data: [DONE] 或空 data：截断后直接返回。
    3. data: + 合法 JSON：先解析完整 JSON → 脱敏 → 序列化 → 最后截断。
    4. data: + 非法 JSON（极少见）：截断后直接返回。

    这是防御性脱敏：即使 Dify 响应中意外回显了敏感字段
    （api_key、token 等），debug 日志也不会泄漏原始值。
    """
    import json

    # 非 data 行不包含结构化数据，直接截断返回
    if not line.startswith("data:"):
        return line[:500] if len(line) > 500 else line

    # 提取 "data: " 后面的内容，在完整原文上操作（尚未截断）
    raw = line[len("data:"):].lstrip()
    if not raw or raw == "[DONE]":
        # [DONE] 或空 data 不需要脱敏，但需截断
        return line[:500] if len(line) > 500 else line

    # 尝试解析 JSON —— 必须在完整 JSON 上解析，不能先截断
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # 非 JSON 的 data 行（极少见），截断后直接返回
        return line[:500] if len(line) > 500 else line

    # JSON 解析成功 → 脱敏 → 序列化
    safe_payload = sanitize_dict_for_log(payload)
    safe_raw = json.dumps(safe_payload, ensure_ascii=False)
    result = f"data: {safe_raw}"

    # 脱敏后的结果可能仍然很长（业务字段多），最后再做截断
    if len(result) > 500:
        result = result[:500]
    return result


def _sanitize_error_body_for_message(body: str) -> str:
    """对 Dify 非 2xx 响应体做脱敏，防止敏感字段泄漏到对外异常消息。

    策略：
    1. JSON 体：解析 → 结构化脱敏 → 序列化 → 截断。
    2. 非 JSON 体：正则匹配 api_key/token/password/Authorization 等关键词并替换为 ***。
    3. 最终结果截断至 200 字符，避免异常消息过长。
    """
    if not body:
        return ""

    # 尝试 JSON 解析和结构化脱敏
    try:
        payload = json.loads(body)
        safe = sanitize_dict_for_log(payload)
        return json.dumps(safe, ensure_ascii=False)[:200]
    except json.JSONDecodeError:
        pass

    # 非 JSON：防御性关键词脱敏。先处理 Bearer 头，避免通用规则只替换
    # "Authorization:" 前缀后留下 token 内容。
    sanitized = re.sub(
        r"(authorization\s*:\s*bearer\s+)[^\s&]+",
        r"\1***",
        body,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"(api_key|token|password|secret|authorization)\s*[=:]\s*[^\s&]+",
        r"\1=***",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized[:200]


class DifyClient:
    """Dify HTTP 客户端。

    负责：
    - 管理 Dify Base URL 和全局 API Key（从环境变量读取）
    - 构造并发送流式聊天请求
    - 解析 SSE 响应为 DifyChatChunk 序列
    - 未配置或调用失败时抛出平台标准异常

    允许 Agent 级 Key 覆盖全局 Key（通过 api_key 参数），
    实现不同 Agent 使用不同 Dify App 独立鉴权。
    """

    def __init__(self) -> None:
        settings = get_settings()
        raw = str(settings.dify_base_url).rstrip("/") if settings.dify_base_url else ""
        # 如果用户已配置 /v1 路径前缀，去掉它，由 client 统一追加
        # 例如用户配了 "https://dify.example.com/v1"，我们去重为 "https://dify.example.com"
        if raw.endswith("/v1"):
            raw = raw[: -len("/v1")]
        self.base_url = raw
        # 全局 Dify API Key（Agent 级 Key 优先级更高，见 stream_chat 的 api_key 参数）
        self.api_key = settings.dify_api_key

    async def stream_chat(
        self,
        runtime_app_id: str,
        payload: DifyChatRequest,
        api_key: str | None = None,
    ) -> AsyncIterator[DifyChatChunk]:
        """流式调用 Dify Chat API，返回 SSE 事件 chunk 的异步迭代器。

        Args:
            runtime_app_id: Dify App ID（对应平台 Agent 的 runtime_app_id）
            payload: Dify Chat 请求体（query、inputs、user 等）
            api_key: Agent 级 Dify API Key。如果为 None，使用全局 DIFY_API_KEY。

        Yields:
            DifyChatChunk: 解析后的 SSE 事件

        Raises:
            DifyNotConfiguredError: Dify Base URL 或 API Key 未配置
            DifyIntegrationError: Dify 返回非 2xx 状态码
        """
        # 优先使用 Agent 级 Key，未配置则回退全局 Key
        effective_key = api_key or self.api_key

        # ── 未配置检查：直接抛出异常，不返回模拟数据 ──────────
        # 这里不返回 mock 文本的原因：
        # 调用记录 (agent_invocation_record) 是平台审计的核心数据源，
        # 未配置时返回假成功会污染成功率统计，导致运维无法发现配置问题。
        if not self.base_url or not effective_key:
            raise DifyNotConfiguredError(
                "Dify integration is not configured. "
                "Please set DIFY_BASE_URL and DIFY_API_KEY in environment variables."
            )

        # ── 构造请求 ──────────────────────────────────────────
        # Authorization header 传递 API Key，不会出现在 Dify workflow inputs 中
        headers = {"Authorization": f"Bearer {effective_key}"}
        url = f"{self.base_url}/v1/chat-messages"
        body = payload.model_dump(exclude_none=True)

        # debug 日志：脱敏后输出，确保不泄漏凭据
        if logger.isEnabledFor(logging.DEBUG):
            safe_body = sanitize_dict_for_log(body)
            safe_headers = _sanitize_headers_for_log(headers)
            logger.debug(
                "Dify request url=%s headers=%s body=%s",
                url,
                safe_headers,
                safe_body,
            )

        # ── 发起流式请求 ──────────────────────────────────────
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=body,
            ) as response:
                # Dify 返回非 2xx 时，httpx 会抛出 HTTPStatusError
                # 对于 stream() 响应，body 尚未读取，直接访问 .text 会抛出
                # ResponseNotRead。必须先 aread() 读取响应体再访问。 修复来源：R-016
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    await exc.response.aread()
                    sanitized = _sanitize_error_body_for_message(exc.response.text or "")
                    message = f"Dify returned HTTP {exc.response.status_code}"
                    if sanitized:
                        message = f"{message}: {sanitized}"
                    raise DifyIntegrationError(message) from exc

                # 逐行解析 SSE 事件
                async for line in response.aiter_lines():
                    # debug 日志：对 SSE 行做结构化脱敏后再输出
                    # 只做截断是不够的——如果 Dify 响应 JSON 中回显了
                    # api_key/token 等字段，截断无法阻止泄漏。
                    # 先尝试解析 JSON payload，脱敏后重新序列化输出。
                    if logger.isEnabledFor(logging.DEBUG):
                        safe_line = _sanitize_sse_line_for_log(line)
                        logger.debug("Dify SSE: %s", safe_line)
                    chunk = parse_sse_lines(line)
                    if chunk:
                        yield chunk

    async def run_workflow(
        self,
        runtime_app_id: str,
        payload: DifyWorkflowRunRequest,
        api_key: str | None = None,
    ) -> DifyWorkflowRunResult:
        """阻塞式调用 Dify Workflow API。

        Args:
            runtime_app_id: Dify App ID，仅用于日志和调用方追踪；Dify Workflow API
                的鉴权由 API Key 决定。
            payload: Workflow 请求体，通常包含 inputs、user、response_mode=blocking。
            api_key: Workflow 对应的 Dify API Key。为空时回退全局 ``DIFY_API_KEY``。

        Returns:
            DifyWorkflowRunResult: 标准化后的 Dify workflow 结果，保留原始响应。

        Raises:
            DifyNotConfiguredError: Dify Base URL 或 API Key 未配置。
            DifyIntegrationError: Dify 返回非 2xx 状态码。
        """
        effective_key = api_key or self.api_key
        if not self.base_url or not effective_key:
            raise DifyNotConfiguredError(
                "Dify integration is not configured. "
                "Please set DIFY_BASE_URL and DIFY_API_KEY in environment variables."
            )

        headers = {"Authorization": f"Bearer {effective_key}"}
        url = f"{self.base_url}/v1/workflows/run"
        body = payload.model_dump(exclude_none=True)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Dify workflow request app_id=%s url=%s headers=%s body=%s",
                runtime_app_id,
                url,
                _sanitize_headers_for_log(headers),
                sanitize_dict_for_log(body),
            )

        async with httpx.AsyncClient(timeout=None) as client:
            try:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                sanitized = _sanitize_error_body_for_message(exc.response.text or "")
                message = f"Dify returned HTTP {exc.response.status_code}"
                if sanitized:
                    message = f"{message}: {sanitized}"
                raise DifyIntegrationError(message) from exc
            except httpx.HTTPError as exc:
                raise DifyIntegrationError(f"Dify workflow request failed: {exc}") from exc

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise DifyIntegrationError("Dify workflow returned non-JSON response") from exc
        if not isinstance(response_payload, dict):
            raise DifyIntegrationError("Dify workflow returned unexpected response")
        return DifyWorkflowRunResult.from_response(response_payload)
