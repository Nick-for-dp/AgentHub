"""合同审查结构化 workflow 输入边界。"""

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.integrations.file_reader.structure.schema import ParsedDocumentV1
from app.modules.contract_review.context_experiment.builder import build_full_context_input

CONTRACT_REVIEW_CONTEXT_SCHEMA_VERSION = "contract_review_full_context_v1"


class ContractReviewWorkflowInput(BaseModel):
    """合同审查 MVP 正式 workflow 输入。

    后端把解析后的全部正文 block 渲染为带 ``block_id`` 锚点的
    ``context_text``。模型 workflow 只负责条款抽取与分类；敏感性判断、规则命中
    和高亮 offset 均由 AgentHub 后端生成。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["contract_review_full_context_v1"] = (
        CONTRACT_REVIEW_CONTEXT_SCHEMA_VERSION
    )
    file_parse_task_id: str = Field(min_length=1)
    contract_type: str = Field(min_length=1)
    context_text: str

    def to_workflow_inputs(self) -> dict[str, Any]:
        """返回 runtime workflow start node 需要的顶层 inputs。"""
        return {
            "file_parse_task_id": self.file_parse_task_id,
            "contract_type": self.contract_type,
            "context_text": self.context_text,
        }


def build_contract_review_workflow_input(
    *,
    file_parse_task_id: str,
    contract_type: str,
    parsed_document: ParsedDocumentV1 | Mapping[str, Any],
) -> ContractReviewWorkflowInput:
    """用全文无过滤策略构建合同审查 workflow 输入。"""
    full_context = build_full_context_input(
        file_parse_task_id=file_parse_task_id,
        contract_type=contract_type,
        parsed_document=parsed_document,
        filter_mode="none",
    )
    return ContractReviewWorkflowInput(
        file_parse_task_id=file_parse_task_id,
        contract_type=contract_type,
        context_text=full_context.context_text,
    )
