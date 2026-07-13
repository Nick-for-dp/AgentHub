from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FULL_CONTEXT_SCHEMA_VERSION = "contract_full_context_input_v1"


class ContextSourceBlock(BaseModel):
    """全文上下文实验使用的标准化 block。

    该结构来自 ``ParsedDocumentV1.blocks``，但只保留全文实验需要的字段。
    ``order``、页码和 reader 细节继续留在原始解析 snapshot 中，后端可通过
    ``block_id`` 回查。
    """

    model_config = ConfigDict(extra="forbid")

    block_id: str = Field(min_length=1)
    block_type: str = Field(min_length=1)
    section_id: str | None = None
    section_title: str | None = None
    text: str = ""


class FilteredContextBlock(BaseModel):
    """被保守过滤器排除的 block 记录。"""

    model_config = ConfigDict(extra="forbid")

    block_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ContractFullContextInput(BaseModel):
    """合同全文上下文实验的 Dify 输入。

    ``context_text`` 是带 ``block_id`` 锚点的全文文本，供 1M 上下文窗口模型一次性
    抽取候选条款并分类。``included_block_ids`` 和 ``filtered_blocks`` 用于审计、
    高亮回链和实验对比。
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["contract_full_context_input_v1"] = FULL_CONTEXT_SCHEMA_VERSION
    file_parse_task_id: str = Field(min_length=1)
    contract_type: str = Field(min_length=1)
    context_text: str = ""
    included_block_ids: list[str] = Field(default_factory=list)
    filtered_block_ids: list[str] = Field(default_factory=list)
    filtered_blocks: list[FilteredContextBlock] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

