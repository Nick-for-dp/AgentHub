"""chat 后处理器链。

问答流结束后，后处理器链对归一化输出做副作用处理（如线索收集），
结果追加到 ``snapshot.runtime``。后处理器只消费平台自有类型
（``NormalizedAgentOutput``），不感知 runtime provider。

后处理器异常被捕获并记录为 warning，不影响调用记录的成功状态。
"""

import logging
from typing import Any

from app.core.enums import AgentType
from app.modules.agent.models import Agent
from app.modules.agent.output import NormalizedAgentOutput
from app.modules.lead.schemas import LeadCaptureContext

logger = logging.getLogger(__name__)


class PostprocessorChain:
    """后处理器链调度器。

    按 Agent 配置 ``config_snapshot.postprocessors`` 决定启用哪些后处理器。
    问答 Agent 默认启用 ``["lead_capture"]``，非问答默认空，显式配置覆盖默认。
    单个后处理器异常被捕获并记录 warning，不影响调用成功状态。
    """

    def __init__(self, postprocessors: dict[str, Any] | None = None):
        self._registry: dict[str, Any] = postprocessors or {
            "lead_capture": _LeadCaptureImpl(),
        }

    def resolve_names(self, agent: Agent) -> list[str]:
        """解析该 Agent 应执行的后处理器名列表。"""
        config = agent.config_snapshot or {}
        explicit = config.get("postprocessors")
        if explicit is not None:
            if isinstance(explicit, list):
                return [str(name) for name in explicit]
            return []
        # 未显式配置：问答默认启用线索收集，其他类型默认关闭
        raw_type = getattr(agent, "type", None)
        agent_type = raw_type.value if isinstance(raw_type, AgentType) else str(raw_type or AgentType.QA)
        if agent_type == AgentType.QA.value:
            return ["lead_capture"]
        return []

    def run(
        self,
        *,
        agent: Agent,
        output: NormalizedAgentOutput,
        lead_context: LeadCaptureContext,
        runtime_snapshot: dict[str, Any],
        lead_service,
    ) -> None:
        """按顺序执行后处理器，结果合并到 runtime_snapshot。

        单个后处理器抛异常被捕获并记录到 ``postprocessor_warnings``，
        不中断后续后处理器，也不回滚调用状态。
        """
        names = self.resolve_names(agent)
        warnings: list[dict[str, str]] = []
        for name in names:
            postprocessor = self._registry.get(name)
            if postprocessor is None:
                warnings.append({"name": name, "reason": "postprocessor not registered"})
                continue
            try:
                result = postprocessor.process(
                    agent=agent,
                    output=output,
                    lead_context=lead_context,
                    lead_service=lead_service,
                )
                if result:
                    runtime_snapshot.update(result)
            except Exception as exc:
                logger.warning("postprocessor %s failed: %s", name, exc, exc_info=True)
                warnings.append({"name": name, "reason": str(exc)})
        if warnings:
            existing = runtime_snapshot.get("postprocessor_warnings")
            if existing and isinstance(existing, list):
                existing.extend(warnings)
            else:
                runtime_snapshot["postprocessor_warnings"] = warnings


class _LeadCaptureImpl:
    """线索收集后处理器实现，封装对 LeadService 的调用。

    该类不 import ``app.integrations.dify``，只依赖平台
    ``NormalizedAgentOutput`` 和 ``LeadService``。
    """

    name = "lead_capture"

    def process(
        self,
        *,
        agent: Agent,
        output: NormalizedAgentOutput,
        lead_context: LeadCaptureContext,
        lead_service,
    ) -> dict[str, Any] | None:
        if not output.lead_deltas:
            return None
        # LeadService.capture_output 接收 NormalizedAgentOutput（平台类型）
        result = lead_service.capture_output(output=output, context=lead_context)
        return {"lead_capture_result": result.model_dump()}