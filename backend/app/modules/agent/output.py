"""平台归一化输出抽象。

该模块定义 AgentHub 自有的归一化输出类型，屏蔽底层 runtime provider（如 Dify）
的专有输出结构。业务层（handler、后处理器、调用记录快照组装）统一依赖
``NormalizedAgentOutput``，不直接 import ``app.integrations.dify.*``。

问答 handler 内部调用 Dify 的 ``normalize_dify_final_output`` 并把结果转换为
``NormalizedAgentOutput``，对 endpoint 和后处理器隐藏 provider 来源。
"""

from typing import Any

from pydantic import BaseModel, Field


class AgentFollowupDecision(BaseModel):
    """追问决策，由 runtime 输出经 handler 归一化后供平台消费。

    字段语义与 Dify 输出契约一致，但类型属于平台自有，不依赖 Dify 包。
    """

    should_ask_followup: bool = False
    next_missing_field: str | None = None
    target_lead_id: str | None = None
    followup_goal: str | None = None
    followup_hint: str | None = None
    reason: str = ""


class NormalizedAgentOutput(BaseModel):
    """平台统一的 Agent 输出归一化结构。

    问答类 Agent 在流结束后把 runtime 最终输出归一化为本类型，供后处理器
    （线索收集等）和调用记录快照消费。非问答类 Agent 若未来需要后续处理，
    也应产出同一结构。
    """

    text: str
    lead_deltas: list[dict[str, Any]] = Field(default_factory=list)
    followup_decision: AgentFollowupDecision = Field(default_factory=AgentFollowupDecision)

    def to_public_dict(self) -> dict[str, Any]:
        """生成写入调用记录快照和前端可读的公开字典。"""
        return {
            "text": self.text,
            "lead_deltas": self.lead_deltas,
            "followup_decision": self.followup_decision.model_dump(),
        }