"""合同审查 CRUD 旧模块兼容入口。

新代码应从 ``app.modules.contract_review.service`` 导入 ``ContractReviewService``。
本模块只保留旧名称别名，避免已有本地脚本在迁移窗口内立即失效；不再维护第二份
CRUD 实现。
"""

from app.modules.contract_review.service import (
    CONTRACT_REVIEW_INVOKE_SCOPE,
    ContractReviewService,
)

ContractReviewHandler = ContractReviewService

__all__ = [
    "CONTRACT_REVIEW_INVOKE_SCOPE",
    "ContractReviewHandler",
    "ContractReviewService",
]
