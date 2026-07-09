"""对话流 handler 抽象层。

chat endpoint 按 ``agent.type`` 选择对话流 handler，把具体的流式逻辑下沉到
handler 实现。endpoint 只负责鉴权、取 Agent、选 handler、写调用记录，不再
感知 runtime provider 的专有类型。

新增非问答对话类 Agent 时，实现 ``ChatHandler`` 协议并在 ``ChatHandlerRegistry``
注册即可，无需改动 chat endpoint 调用记录与产品会话协作链路。
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.core.enums import AgentType
from app.core.exceptions import UnsupportedRuntimeError
from app.modules.agent.models import Agent
from app.modules.auth.schemas import AuthenticatedSubject
from app.modules.conversation.models import Conversation, ConversationMessage
from app.modules.conversation.service import ConversationService
from app.modules.invocation.schemas import InvocationRecordFinish
from app.modules.agent.runtime import AgentRuntimeService


@dataclass
class ChatContext:
    """一次 chat 调用的上下文，由 endpoint 组装后传给 handler。

    handler 通过该上下文访问 runtime、产品会话和调用方信息，
    但不直接写调用记录（由 endpoint 在 finalize 阶段统一写入）。
    """

    agent: Agent
    subject: AuthenticatedSubject
    question: str
    provider_conversation_id: str | None
    platform_conversation: Conversation | None
    assistant_message: ConversationMessage | None
    known_lead_state: dict[str, Any]
    runtime_service: AgentRuntimeService
    conversation_service: ConversationService
    invocation_record_id: str | None = None
    provider_conversation_id_current: str | None = None


@runtime_checkable
class ChatHandler(Protocol):
    """对话流 handler 协议。

    handler 负责消费 runtime 流式 chunk、产出 SSE 事件字典、
    在流结束后归一化输出并运行后处理器，最终由 endpoint 调用
    ``build_finish`` 拿到调用记录快照。

    重要：handler 实例可持有单次请求的可变状态（answer 累积、node_trace 等）。
    注册表必须为每次 chat 调用创建新实例，禁止跨请求复用同一 handler。
    """

    def stream(self, ctx: ChatContext) -> AsyncIterator[dict[str, Any]]:
        """流式消费 runtime chunk，逐条 yield SSE 事件字典。

        handler 在流过程中累积 answer/thought/node_trace/metadata，
        并按需同步 provider_conversation_id 和更新 assistant 消息的中间状态。
        """
        ...

    def build_finish(
        self,
        *,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        latency_ms: int | None = None,
    ) -> InvocationRecordFinish:
        """构造调用记录完成快照。

        在流结束（成功/取消/异常）后由 endpoint 调用，把 handler 累积的
        run state 组装为 ``InvocationRecordFinish``，保持 ``retrieval`` /
        ``model`` / ``runtime`` 三段结构不变。
        """
        ...


# handler 工厂：无参可调用对象，每次调用返回新的 ChatHandler 实例
ChatHandlerFactory = Callable[[], ChatHandler]


class ChatHandlerRegistry:
    """按 ``agent.type`` 分发对话流 handler 的注册表。

    注册的是工厂而非实例：每次 ``select`` 都创建新 handler，保证并发 chat
    请求之间的流式累积状态（answer / node_trace 等）完全隔离。

    未注册的 agent type 返回明确错误，不静默退化为问答 handler，
    避免错误配置被隐藏。未指定 type 时回退为问答（向后兼容）。
    """

    def __init__(self, factories: dict[str, ChatHandlerFactory] | None = None):
        if factories is None:
            from app.modules.agent.handlers.qa_handler import QaChatHandler

            factories = {AgentType.QA.value: QaChatHandler}
        self._factories: dict[str, ChatHandlerFactory] = factories

    def select(self, agent: Agent) -> ChatHandler:
        """按 agent.type 创建新的 handler 实例；未指定回退问答，未注册抛错。"""
        raw_type = getattr(agent, "type", None)
        if raw_type is None:
            raw_type = AgentType.QA
        agent_type = raw_type.value if isinstance(raw_type, AgentType) else str(raw_type)
        factory = self._factories.get(agent_type)
        if factory is None:
            raise UnsupportedRuntimeError(f"unsupported agent type: {agent_type}")
        return factory()


_default_registry: ChatHandlerRegistry | None = None


def get_chat_handler_registry() -> ChatHandlerRegistry:
    """获取默认 handler 注册表（惰性初始化，避免循环 import）。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ChatHandlerRegistry()
    return _default_registry
