"""任务型 Agent 的可插拔阶段协议与顺序执行辅助。

TaskHandler 的主路径固定为 ``preprocess -> core -> postprocess``。每个边界内部
可以声明有序步骤列表；任一步骤抛错都会立即短路，因此前处理失败不会调用 core，
core 失败也不会进入后处理主路径。

扩展某个任务型 Agent 时，只需把新的步骤挂入具体 handler 的步骤列表，不需要
修改通用 endpoint。阶段协议仅依赖平台 TaskContext 的结构约定，不依赖 Dify 等
provider 专有类型。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from app.modules.agent.task_handlers import TaskContext


@dataclass
class PreprocessResult:
    """前处理阶段输出，供 core / postprocess 消费。"""

    workflow_inputs: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def merged(self, other: "PreprocessResult") -> "PreprocessResult":
        """按步骤顺序合并输出；后运行步骤覆盖同名键。"""
        return PreprocessResult(
            workflow_inputs={**self.workflow_inputs, **other.workflow_inputs},
            extras={**self.extras, **other.extras},
        )


@dataclass
class CoreResult:
    """核心处理（runtime workflow）输出。"""

    outputs: dict[str, Any] = field(default_factory=dict)
    status: str | None = None
    error: str | None = None
    workflow_run_id: str | None = None
    total_tokens: int | None = None
    elapsed_time: float | None = None
    raw: Any = None


@dataclass
class PostprocessResult:
    """后处理阶段输出：业务 result 与写入 invocation 的素材。"""

    business_result: dict[str, Any] = field(default_factory=dict)
    output_for_invocation: dict[str, Any] = field(default_factory=dict)
    snapshot_runtime_extra: dict[str, Any] = field(default_factory=dict)
    token_usage: dict[str, Any] = field(default_factory=dict)

    def merged(self, other: "PostprocessResult") -> "PostprocessResult":
        """按步骤顺序合并后处理产物；后运行步骤可增补或覆盖顶层字段。"""
        return PostprocessResult(
            business_result={**self.business_result, **other.business_result},
            output_for_invocation={
                **self.output_for_invocation,
                **other.output_for_invocation,
            },
            snapshot_runtime_extra={
                **self.snapshot_runtime_extra,
                **other.snapshot_runtime_extra,
            },
            token_usage={**self.token_usage, **other.token_usage},
        )


class TaskPreprocessStep(Protocol):
    """前处理步骤协议。多个实现按声明顺序串联。"""

    def run(self, ctx: "TaskContext") -> PreprocessResult:
        """执行前处理；失败应抛业务异常，由模板方法标记任务失败。"""
        ...


class TaskCoreStep(Protocol):
    """核心处理步骤协议。当前合同审查实现只调用 AgentRuntime。"""

    async def run(self, ctx: "TaskContext", pre: PreprocessResult) -> CoreResult:
        """执行核心处理。"""
        ...


class TaskPostprocessStep(Protocol):
    """后处理步骤协议。多个实现按声明顺序串联。"""

    def run(
        self,
        ctx: "TaskContext",
        pre: PreprocessResult,
        core: CoreResult,
    ) -> PostprocessResult:
        """执行后处理；主产物失败应抛异常使任务进入 FAILED。"""
        ...


def run_preprocess_steps(
    steps: Sequence[TaskPreprocessStep],
    ctx: "TaskContext",
) -> PreprocessResult:
    """顺序执行前处理步骤，并合并各步产物。"""
    result = PreprocessResult()
    for step in steps:
        result = result.merged(step.run(ctx))
    return result


def run_postprocess_steps(
    steps: Sequence[TaskPostprocessStep],
    ctx: "TaskContext",
    pre: PreprocessResult,
    core: CoreResult,
) -> PostprocessResult:
    """顺序执行后处理步骤，并合并各步产物。"""
    result = PostprocessResult()
    for step in steps:
        result = result.merged(step.run(ctx, pre, core))
    return result


PreprocessCallable = Callable[["TaskContext"], PreprocessResult]
CoreCallable = Callable[["TaskContext", PreprocessResult], Awaitable[CoreResult]]
PostprocessCallable = Callable[
    ["TaskContext", PreprocessResult, CoreResult],
    PostprocessResult,
]


async def run_pipeline(
    *,
    preprocess: TaskPreprocessStep | PreprocessCallable,
    core: TaskCoreStep | CoreCallable,
    postprocess: TaskPostprocessStep | PostprocessCallable,
    ctx: "TaskContext",
) -> tuple[PreprocessResult, CoreResult, PostprocessResult]:
    """按三阶段顺序执行，任一阶段失败即短路。

    该辅助既接受带 ``run`` 方法的步骤对象，也接受 TaskHandler 暴露的三个边界
    方法，便于独立测试流水线顺序和失败策略。
    """
    preprocess_call = preprocess if callable(preprocess) else preprocess.run
    core_call = core if callable(core) else core.run
    postprocess_call = postprocess if callable(postprocess) else postprocess.run

    pre = preprocess_call(ctx)
    core_result = await core_call(ctx, pre)
    post = postprocess_call(ctx, pre, core_result)
    return pre, core_result, post
