"""旧 Dify 命名兼容入口；新代码使用 ``workflow_output``。"""

from app.modules.contract_review.workflow_output import (
    CLAUSE_EXTRACTION_SCHEMA_VERSION,
    ContractClauseExtraction,
    ExtractedClause,
    parse_contract_clause_extraction,
)

__all__ = [
    "CLAUSE_EXTRACTION_SCHEMA_VERSION",
    "ContractClauseExtraction",
    "ExtractedClause",
    "parse_contract_clause_extraction",
]
