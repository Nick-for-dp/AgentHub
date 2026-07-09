"""问答 Agent 对话流 handler。

承载当前 ``chat.py`` endpoint 中问答专属的流式逻辑：消费 runtime chunk、
累积 answer/thought/node_trace、同步 provider_conversation_id、归一化 Dify
最终输出并转为平台 ``NormalizedAgentOutput``、运行后处理器链。

Dify 输出归一化只在本 handler 内部消化，endpoint 和后处理器不感知
``app.integrations.dify`` 的专有类型。

注意：本类实例持有单次请求的可变状态。必须通过 ``ChatHandlerRegistry.select``
为每次 chat 调用创建新实例，禁止跨请求复用。
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from app.core.enums import ConversationMessageStatus
from app.core.exceptions import DifyIntegrationError
from app.modules.agent.handlers import ChatContext
from app.modules.agent.handlers.postprocessors import PostprocessorChain
from app.modules.agent.output import NormalizedAgentOutput, AgentFollowupDecision
from app.modules.conversation.schemas import ConversationMessageUpdate
from app.modules.invocation.schemas import InvocationRecordFinish

logger = logging.getLogger(__name__)


class QaChatHandler:
    """问答 Agent 对话流 handler。

    生命周期：``stream`` 消费 chunk 并累积状态 → ``on_complete`` 归一化输出
    并运行后处理器 → ``build_finish`` 组装调用记录快照。
    endpoint 只在成功路径调用 ``on_complete``，取消/异常路径直接调 ``build_finish``。

    实例状态仅服务单次请求；注册表工厂每次 select 创建新实例以保证并发隔离。
    """

    def __init__(self, postprocessor_chain: PostprocessorChain | None = None):
        self._chain = postprocessor_chain or PostprocessorChain()
        self._output_parts: list[str] = []
        self._thought_parts: list[str] = []
        self._node_trace: list[dict] = []
        self._metadata: dict[str, Any] = {}
        self._provider_message_id: str | None = None
        self._final_workflow_outputs: dict[str, Any] | None = None
        self._normalized_output: NormalizedAgentOutput | None = None
        self._postprocessor_snapshot: dict[str, Any] = {}

    async def stream(self, ctx: ChatContext) -> AsyncIterator[dict[str, Any]]:
        """流式消费 runtime chunk，yield SSE 事件字典并累积内部状态。

        答案去重、thought 透传、节点事件累积和 provider_conversation_id
        同步逻辑与重构前 chat endpoint 保持一致。

        每次 stream 开始前重置内部累积状态，避免 handler 实例被误复用时
        前一次调用的 answer/thought/node_trace 泄漏到下一次。
        """
        self._reset()

        async for chunk in ctx.runtime_service.stream_chat(
            agent=ctx.agent,
            question=ctx.question,
            caller_id=ctx.subject.user_id or ctx.subject.api_key_id or "anonymous",
            conversation_id=ctx.provider_conversation_id,
            extra_inputs={"known_lead_state": ctx.known_lead_state},
        ):
            # message_end 的 metadata 存起来，供快照组装
            if chunk.metadata:
                self._metadata = chunk.metadata
            if chunk.workflow_outputs:
                self._final_workflow_outputs = chunk.workflow_outputs
            # 节点事件累积到 node_trace（用于审计快照）
            if chunk.node:
                self._node_trace.append(chunk.node)

            event_data: dict[str, Any] = {}
            if chunk.answer:
                self._output_parts.append(chunk.answer)
                event_data["answer"] = chunk.answer
            if chunk.thought:
                self._thought_parts.append(chunk.thought)
                event_data["thought"] = chunk.thought
            if chunk.conversation_id and ctx.platform_conversation is None:
                event_data["conversation_id"] = chunk.conversation_id
            if chunk.conversation_id and ctx.platform_conversation is not None:
                # 同步 provider_conversation_id 到平台会话
                ctx.provider_conversation_id_current = chunk.conversation_id
                ctx.conversation_service.update_provider_conversation_id(
                    ctx.platform_conversation,
                    chunk.conversation_id,
                    commit=False,
                )
                event_data["provider_conversation_id"] = chunk.conversation_id
            if chunk.message_id:
                self._provider_message_id = chunk.message_id
                event_data["message_id"] = chunk.message_id
            if chunk.node:
                event_data["event"] = chunk.node.get("event")
                event_data["node"] = {k: v for k, v in chunk.node.items() if k != "event"}
            if chunk.error:
                raise DifyIntegrationError(chunk.error)

            # 渐进更新 assistant 消息中间状态（仅登录用户有产品会话时）
            if ctx.assistant_message is not None and (
                chunk.answer or chunk.thought or chunk.node or chunk.message_id
            ):
                ctx.conversation_service.update_message(
                    ctx.assistant_message,
                    ConversationMessageUpdate(
                        content="".join(self._output_parts),
                        thought="".join(self._thought_parts) or None,
                        steps=self._node_trace,
                        provider_message_id=self._provider_message_id,
                        status=ConversationMessageStatus.STREAMING,
                    ),
                )
            if event_data:
                yield event_data

    def on_complete(self, ctx: ChatContext, lead_service) -> None:
        """流正常结束后：归一化输出 + 运行后处理器链。

        只在成功路径调用。取消/异常路径跳过此方法，直接调 ``build_finish``。
        """
        # 归一化 Dify 最终输出为平台类型，对 endpoint 和后处理器隐藏 provider
        self._normalized_output = self._normalize_output()
        # 如果归一化后文本与流式累积不同，以归一化结果为准
        if self._output_parts and "".join(self._output_parts) != self._normalized_output.text:
            self._output_parts[:] = [self._normalized_output.text]

        # 构造 lead capture context 并运行后处理器链
        if self._normalized_output.lead_deltas:
            lead_context = self._build_lead_context(ctx)
            self._chain.run(
                agent=ctx.agent,
                output=self._normalized_output,
                lead_context=lead_context,
                runtime_snapshot=self._postprocessor_snapshot,
                lead_service=lead_service,
            )

    def build_finish(
        self,
        *,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        latency_ms: int | None = None,
    ) -> InvocationRecordFinish:
        """把累积的 run state 组装为 ``InvocationRecordFinish``。

        保持 ``retrieval`` / ``model`` / ``runtime`` 三段结构不变
        （ADR-005 / ADR-013）。后处理器产出的子键合并到 ``runtime`` 段。
        """
        base_runtime_snapshot = {
            "runtime_type": getattr(self, "_base_runtime_type", None),
            "runtime_app_id": getattr(self, "_base_runtime_app_id", None),
        }
        runtime_snapshot = dict(base_runtime_snapshot)
        if self._node_trace:
            runtime_snapshot["node_trace"] = self._node_trace
        if self._metadata:
            runtime_snapshot["dify_metadata"] = self._metadata
        if self._normalized_output is not None:
            runtime_snapshot["dify_final_output"] = self._normalized_output.to_public_dict()
        # 后处理器链产出的子键（如 lead_capture_result）合并到 runtime 段
        if self._postprocessor_snapshot:
            runtime_snapshot.update(self._postprocessor_snapshot)

        retrieval_snapshot = {"resources": self._metadata.get("retriever_resources", [])}
        model_snapshot = (
            {
                "model_provider": self._metadata.get("model_provider"),
                "model_name": self._metadata.get("model_name"),
            }
            if any(k in self._metadata for k in ("model_provider", "model_name"))
            else {}
        )

        if self._normalized_output is not None:
            output_dict = {
                "answer": self._normalized_output.text,
                **self._normalized_output.to_public_dict(),
            }
        else:
            output_dict = {"answer": "".join(self._output_parts)}

        return InvocationRecordFinish(
            output=output_dict,
            token_usage=self._metadata.get("usage", {}),
            snapshot={
                "retrieval": retrieval_snapshot,
                "model": model_snapshot,
                "runtime": runtime_snapshot,
            },
            status=status,
            error_code=error_code,
            error_message=error_message,
            latency_ms=latency_ms,
        )

    def _normalize_output(self) -> NormalizedAgentOutput:
        """把 Dify workflow 最终输出归一化为平台 ``NormalizedAgentOutput``。

        Dify 专有的 ``normalize_dify_final_output`` 只在本方法内使用，
        转换结果为平台自有类型，对外不泄漏 Dify 结构。
        """
        # 延迟 import，避免模块级耦合 integrations.dify
        from app.integrations.dify.output import normalize_dify_final_output

        raw = (
            self._final_workflow_outputs
            if self._final_workflow_outputs is not None
            else {"text": "".join(self._output_parts)}
        )
        dify_output = normalize_dify_final_output(raw)
        return NormalizedAgentOutput(
            text=dify_output.text,
            lead_deltas=dify_output.lead_deltas,
            followup_decision=AgentFollowupDecision(
                should_ask_followup=dify_output.followup_decision.should_ask_followup,
                next_missing_field=dify_output.followup_decision.next_missing_field,
                target_lead_id=dify_output.followup_decision.target_lead_id,
                followup_goal=dify_output.followup_decision.followup_goal,
                followup_hint=dify_output.followup_decision.followup_hint,
                reason=dify_output.followup_decision.reason,
            ),
        )

    def _reset(self) -> None:
        """重置流式累积状态，作为误复用时的防御性清理。

        正常路径依赖注册表每次 select 创建新实例；本方法是双保险。
        """
        self._output_parts = []
        self._thought_parts = []
        self._node_trace = []
        self._metadata = {}
        self._provider_message_id = None
        self._final_workflow_outputs = None
        self._normalized_output = None
        self._postprocessor_snapshot = {}

    def set_base_runtime_snapshot(self, agent) -> None:
        """记录 base runtime 快照（runtime_type / runtime_app_id），用于 build_finish。"""
        self._base_runtime_type = agent.runtime_type
        self._base_runtime_app_id = agent.runtime_app_id

    @staticmethod
    def _build_lead_context(ctx: ChatContext):
        """从 chat 上下文构造 LeadCaptureContext。"""
        from app.modules.lead.schemas import LeadCaptureContext

        return LeadCaptureContext.from_chat(
            agent=ctx.agent,
            user_id=ctx.subject.user_id,
            org_unit_id=ctx.subject.org_unit_id,
            conversation=ctx.platform_conversation,
            assistant_message=ctx.assistant_message,
            invocation_record_id=getattr(ctx, "invocation_record_id", None),
        )
