"""
Agent 运行时服务：封装 Agent 对底层 runtime（MVP 为 Dify）的调用。

业务层不直接调用 Dify HTTP API，而是通过本服务 → DifyClient 的路径。
本服务负责：
1. 从 Agent 配置快照中提取运行时凭据（如 dify_api_key）
2. 构造安全的 Dify inputs（剔除敏感配置，只保留业务参数）
3. 将 Dify 流式响应转换为统一 chunk 输出（含去重和思考过程透传）
"""

import logging
from collections.abc import AsyncIterator

from app.core.security import SENSITIVE_CONFIG_KEYS
from app.integrations.dify.client import DifyClient
from app.integrations.dify.schemas import DifyChatChunk, DifyChatRequest
from app.modules.agent.models import Agent

logger = logging.getLogger(__name__)


class AgentRuntimeService:
    """Agent 运行时服务。

    MVP 仅封装 Dify 调用；未来可扩展为支持多种 runtime 的路由。
    """

    def __init__(self, dify_client: DifyClient | None = None):
        self.dify_client = dify_client or DifyClient()

    @staticmethod
    def _extract_api_key(agent: Agent) -> str | None:
        """从 Agent 配置快照中提取 Dify API Key。

        每个 Agent 可以在 config_snapshot.dify_api_key 中存储自己的 Dify 凭据。
        如果 Agent 未配置，则 DifyClient 回退使用全局 DIFY_API_KEY 环境变量。
        这样不同 Agent 可以调用不同的 Dify App，并具有独立的鉴权。
        """
        return (agent.config_snapshot or {}).get("dify_api_key")

    @staticmethod
    def _build_safe_inputs(config_snapshot: dict | None) -> dict:
        """从 Agent 配置快照中剔除敏感字段，只保留业务 inputs。

        config_snapshot 中可能包含 dify_api_key、运行时配置等平台内部字段，
        这些字段是给平台 runtime 层使用的，不应作为 Dify workflow 的 inputs 参数。
        本方法过滤掉 SENSITIVE_CONFIG_KEYS（如 dify_api_key），
        确保传给 Dify 的 inputs 中不包含凭据信息。

        Args:
            config_snapshot: Agent 的完整配置快照

        Returns:
            安全的 inputs 字典（不包含敏感配置 Key）
        """
        if not config_snapshot:
            return {}
        return {
            k: v for k, v in config_snapshot.items()
            if k not in SENSITIVE_CONFIG_KEYS
        }

    async def stream_chat(
        self,
        agent: Agent,
        question: str,
        caller_id: str,
        conversation_id: str | None = None,
        extra_inputs: dict | None = None,
    ) -> AsyncIterator[DifyChatChunk]:
        """流式调用 Agent 绑定的 Dify App，逐 chunk 返回结构化事件。

        Dify SSE 可能返回累积答案（每个 chunk.answer 是当前完整文本）或
        增量答案（每个 chunk.answer 是新增片段），本方法统一转换为增量输出。

        Args:
            agent: 平台 Agent 记录（含 runtime_app_id 和 config_snapshot）
            question: 用户问题
            caller_id: 调用者标识（用于 Dify 的 user 参数，区分不同用户会话）
            conversation_id: Dify 会话 ID（用于多轮对话续接）

        Yields:
            DifyChatChunk：含增量 answer 和/或 thought 的结构化事件
        """
        dify_api_key = self._extract_api_key(agent)
        safe_inputs = self._build_safe_inputs(agent.config_snapshot)
        if extra_inputs:
            safe_inputs = {**safe_inputs, **extra_inputs}

        request = DifyChatRequest(
            query=question,
            user=caller_id,
            conversation_id=conversation_id,
            inputs=safe_inputs,
        )
        # Dify 可能返回累积答案或增量答案，需要去重，只输出增量部分
        seen_answer = ""
        async for chunk in self.dify_client.stream_chat(
            agent.runtime_app_id or agent.code,
            request,
            api_key=dify_api_key,
        ):
            # message_end 的 answer 已由 parse_sse_lines 置为 None，跳过
            if chunk.event == "message_end":
                if chunk.conversation_id or chunk.message_id:
                    yield DifyChatChunk(
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
                # 增量去重：用累加文本 seen_answer 比较，而不是上一轮原始 answer
                if seen_answer and chunk.answer.startswith(seen_answer):
                    delta = chunk.answer[len(seen_answer):]
                else:
                    delta = chunk.answer
                if delta:
                    seen_answer += delta
                    delta_answer = delta

            # 有增量 answer、有 thought、有节点事件或有 error 时才输出
            if delta_answer or has_thought or chunk.node is not None or chunk.error is not None:
                yield DifyChatChunk(
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
