"""旧 Dify 命名兼容入口；新代码使用 ``workflow_input``。"""

from app.modules.contract_review.workflow_input import (
    CONTRACT_REVIEW_CONTEXT_SCHEMA_VERSION,
    ContractReviewWorkflowInput,
    build_contract_review_workflow_input,
)

ContractReviewDifyInput = ContractReviewWorkflowInput
build_contract_review_dify_input = build_contract_review_workflow_input

__all__ = [
    "CONTRACT_REVIEW_CONTEXT_SCHEMA_VERSION",
    "ContractReviewDifyInput",
    "ContractReviewWorkflowInput",
    "build_contract_review_dify_input",
    "build_contract_review_workflow_input",
]
