"""
Agent 运行时抽象：封装 Agent 对底层 runtime（MVP 为 Dify）的调用。

业务层不直接调用 Dify HTTP API，也不依赖 Dify 专有 chunk 类型。调用路径统一为
业务模块 → AgentRuntimeService → AgentRuntime 实现 → DifyClient。

本模块负责：
1. 从 Agent 配置快照中提取运行时凭据（如 dify_api_key）
2. 构造安全的 Dify inputs（剔除敏感配置，只保留业务参数）
3. 按 runtime_type 选择运行时实现
4. 将 Dify 流式响应转换为平台统一 chunk 输出（含去重和思考过程透传）
"""

import logging
from dataclasses import dataclass, field
from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.core.enums import RuntimeType
from app.core.exceptions import UnsupportedRuntimeError
from app.core.security import SENSITIVE_CONFIG_KEYS
from app.integrations.dify.client import DifyClient
from app.integrations.dify.schemas import DifyChatRequest
from app.modules.agent.models import Agent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentRuntimeRequest:
    """平台统一 runtime 请求。

    Attributes:
        query: 用户问题或本次 Agent 调用的主输入文本。
        caller_id: 传给 runtime 的调用方标识，只用于隔离 provider 会话上下文。
        conversation_id: provider 会话 ID。网页登录用户的产品会话 ID 不放在这里。
        inputs: 传给 runtime workflow 的业务输入，必须由上层先剔除密钥等敏感字段。
    """

    query: str
    caller_id: str
    conversation_id: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRuntimeChunk:
    """平台统一 runtime 流式事件。

    该结构承接 Dify SSE 的 answer/thought/node/message_end 等信息，但字段名属于
    AgentHub 自有契约。业务层只能依赖本类型，不能直接依赖 DifyChatChunk。
    """

    event: str
    answer: str | None = None
    thought: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    node: dict[str, Any] | None = None
    workflow_outputs: dict[str, Any] | None = None
    error: str | None = None


class AgentRuntime(Protocol):
    """Agent runtime 实现协议。

    新增 runtime provider 时必须实现该协议，并在 AgentRuntimeService 的 registry
    中注册。业务模块不感知 provider 的 HTTP 协议、SDK 类型或鉴权细节。
    """

    def stream_chat(
        self,
        agent: Agent,
        request: AgentRuntimeRequest,
    ) -> AsyncIterator[AgentRuntimeChunk]:
        """流式执行对话类调用。

        Args:
            agent: 平台 Agent 配置。
            request: 平台统一 runtime 请求。

        Yields:
            AgentRuntimeChunk: 平台统一流式事件。
        """


class DifyRuntime:
    """Dify runtime 实现。

    只在本实现内把平台统一请求/事件转换为 Dify 的请求和 SSE chunk。这样合同审查、
    问答等业务 handler 都不需要 import Dify 专有类型。
    """

    def __init__(self, dify_client: DifyClient | None = None):
        self.dify_client = dify_client or DifyClient()

    def stream_chat(
        self,
        agent: Agent,
        request: AgentRuntimeRequest,
    ) -> AsyncIterator[AgentRuntimeChunk]:
        """流式调用 Agent 绑定的 Dify App，逐 chunk 返回平台统一事件。

        Dify SSE 可能返回累积答案（每个 chunk.answer 是当前完整文本）或增量答案
        （每个 chunk.answer 是新增片段），本方法统一转换为增量输出。

        Args:
            agent: 平台 Agent 记录（含 runtime_app_id 和 config_snapshot）。
            request: 平台统一 runtime 请求。

        Yields:
            AgentRuntimeChunk: 含增量 answer 和/或 thought 的结构化事件。
        """
        return self._stream_chat(agent, request)

    async def _stream_chat(
        self,
        agent: Agent,
        request: AgentRuntimeRequest,
    ) -> AsyncIterator[AgentRuntimeChunk]:
        dify_request = DifyChatRequest(
            query=request.query,
            user=request.caller_id,
            conversation_id=request.conversation_id,
            inputs=request.inputs,
        )
        # Dify 可能返回累积答案或增量答案，需要去重，只输出增量部分
        seen_answer = ""
        async for chunk in self.dify_client.stream_chat(
            agent.runtime_app_id or agent.code,
            dify_request,
            api_key=_extract_dify_api_key(agent),
        ):
            # message_end 的 answer 已由 parse_sse_lines 置为 None，跳过
            if chunk.event == "message_end":
                if chunk.conversation_id or chunk.message_id:
                    yield AgentRuntimeChunk(
                        event=chunk.event,
                        conversation_id=chunk.conversation_id,
                        message_id=chunk.message_id,
                        metadata=chunk.metadata,
                        workflow_outputs=chunk.workflow_outputs,
                    )
                continue

            has_thought = bool(chunk.thought)
            delta_answer: str | None = None

            if chunk.answer:
                if seen_answer and chunk.answer.startswith(seen_answer):
                    delta = chunk.answer[len(seen_answer):]
                else:
                    delta = chunk.answer
                if delta:
                    seen_answer += delta
                    delta_answer = delta

            # 有增量 answer、有 thought、有节点事件或有 error 时才输出
            if delta_answer or has_thought or chunk.node is not None or chunk.error is not None:
                yield AgentRuntimeChunk(
                    event=chunk.event,
                    answer=delta_answer,
                    thought=chunk.thought,
                    conversation_id=chunk.conversation_id,
                    message_id=chunk.message_id,
                    metadata=chunk.metadata,
                    node=chunk.node,
                    workflow_outputs=chunk.workflow_outputs,
                    error=chunk.error,
                )


class AgentRuntimeService:
    """Agent 运行时路由服务。

    保留 ``stream_chat`` 的旧调用签名，兼容现有问答接口；内部按 Agent 的
    ``runtime_type`` 选择具体 runtime 实现。后续合同审查 handler 会复用同一
    runtime registry，而不是直接调用 DifyClient。
    """

    def __init__(
        self,
        dify_client: DifyClient | None = None,
        runtime_registry: dict[str, AgentRuntime] | None = None,
    ):
        self.runtime_registry = runtime_registry or {
            RuntimeType.DIFY.value: DifyRuntime(dify_client=dify_client),
        }

    @staticmethod
    def _extract_api_key(agent: Agent) -> str | None:
        """从 Agent 配置快照中提取 Dify API Key。

        每个 Agent 可以在 config_snapshot.dify_api_key 中存储自己的 Dify 凭据。
        如果 Agent 未配置，则 DifyClient 回退使用全局 DIFY_API_KEY 环境变量。
        这样不同 Agent 可以调用不同的 Dify App，并具有独立的鉴权。
        """
        return _extract_dify_api_key(agent)

    @staticmethod
    def _build_safe_inputs(config_snapshot: dict | None) -> dict:
        """从 Agent 配置快照中剔除敏感字段，只保留业务 inputs。

        config_snapshot 中可能包含 dify_api_key、运行时配置等平台内部字段，
        这些字段是给平台 runtime 层使用的，不应作为 Dify workflow 的 inputs 参数。
        本方法过滤掉 SENSITIVE_CONFIG_KEYS（如 dify_api_key），
        确保传给 Dify 的 inputs 中不包含凭据信息。

        Args:
            config_snapshot: Agent 的完整配置快照。

        Returns:
            安全的 inputs 字典（不包含敏感配置 Key）。
        """
        return _build_safe_inputs(config_snapshot)

    def _select_runtime(self, agent: Agent) -> AgentRuntime:
        """按 Agent runtime_type 选择 runtime 实现。

        Args:
            agent: 平台 Agent 记录。

        Returns:
            已注册的 AgentRuntime 实现。

        Raises:
            UnsupportedRuntimeError: Agent 配置了当前平台未注册的 runtime_type。
        """
        raw_runtime_type = getattr(agent, "runtime_type", RuntimeType.DIFY)
        if isinstance(raw_runtime_type, RuntimeType):
            runtime_type = raw_runtime_type.value
        elif isinstance(raw_runtime_type, str):
            runtime_type = raw_runtime_type
        else:
            # 历史测试替身或旧数据对象可能没有显式 runtime_type；平台默认按 Dify 处理。
            runtime_type = RuntimeType.DIFY.value
        runtime = self.runtime_registry.get(runtime_type)
        if runtime is None:
            raise UnsupportedRuntimeError(f"unsupported runtime type: {runtime_type}")
        return runtime

    async def stream_chat(
        self,
        agent: Agent,
        question: str,
        caller_id: str,
        conversation_id: str | None = None,
        extra_inputs: dict | None = None,
    ) -> AsyncIterator[AgentRuntimeChunk]:
        """流式执行对话类 Agent 调用。

        Args:
            agent: 平台 Agent 记录（含 runtime_type/runtime_app_id/config_snapshot）。
            question: 用户问题。
            caller_id: 调用者标识，用于 provider 侧隔离不同用户会话。
            conversation_id: provider 会话 ID，用于多轮对话续接。
            extra_inputs: 本次调用追加的业务输入，例如问答线索状态。

        Yields:
            AgentRuntimeChunk: 平台统一流式事件。
        """
        safe_inputs = self._build_safe_inputs(agent.config_snapshot)
        if extra_inputs:
            safe_inputs = {**safe_inputs, **extra_inputs}
        request = AgentRuntimeRequest(
            query=question,
            caller_id=caller_id,
            conversation_id=conversation_id,
            inputs=safe_inputs,
        )
        async for chunk in self._select_runtime(agent).stream_chat(agent, request):
            yield chunk


def _extract_dify_api_key(agent: Agent) -> str | None:
    """从 Agent 配置中提取 Dify API Key。

    这是 DifyRuntime 的 provider 私有配置读取逻辑。当前保留在 runtime 模块，
    是为了兼容既有 AgentRuntimeService 单元测试；业务层不得调用本函数。
    """
    return (agent.config_snapshot or {}).get("dify_api_key")


def _build_safe_inputs(config_snapshot: dict | None) -> dict:
    """构造传给 runtime workflow 的安全业务输入。

    Args:
        config_snapshot: Agent 的完整配置快照。

    Returns:
        已剔除敏感 Key 的浅拷贝字典。
    """
    if not config_snapshot:
        return {}
    return {
        key: value
        for key, value in config_snapshot.items()
        if key not in SENSITIVE_CONFIG_KEYS
    }
