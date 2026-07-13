from dataclasses import dataclass

from app.core.enums import CounterpartyLevel
from app.modules.contract_review.rules.clause_matrix import (
    CLAUSE_CATEGORY_LABELS,
    CLAUSE_SENSITIVE_MATRIX,
)
from app.modules.contract_review.rules.counterparty_level_mapper import normalize_counterparty_level


@dataclass(frozen=True)
class ClauseJudgment:
    """单条条款的规则判定结果。"""

    clause_category: str
    matrix_clause: str
    counterparty_level: str
    is_sensitive: bool
    risk_level: str
    matched_rules: list[str]
    reason: str

    def to_dict(self) -> dict:
        """返回可写入 JSON 字段的普通字典。"""
        return {
            "clause_category": self.clause_category,
            "matrix_clause": self.matrix_clause,
            "counterparty_level": self.counterparty_level,
            "is_sensitive": self.is_sensitive,
            "risk_level": self.risk_level,
            "matched_rules": self.matched_rules,
            "reason": self.reason,
        }


class CreditClauseRuleEngine:
    """A1-A7 对手方等级规则引擎。

    输入是 Dify 抽取的标准条款分类和本次审查使用的对手方资信等级。输出只由后端
    确定性矩阵生成，Dify 的结果不得直接决定 ``is_sensitive``。
    """

    def judge(
        self,
        *,
        counterparty_level: str | CounterpartyLevel,
        clause_category: str,
    ) -> ClauseJudgment:
        """判断条款在指定对手方等级下是否敏感。

        未知条款分类按敏感处理，避免 LLM 分类漂移时误放行。
        """
        level = normalize_counterparty_level(counterparty_level)
        category = clause_category.strip()
        matrix_clause = CLAUSE_CATEGORY_LABELS.get(category, category or "unknown")
        is_known_category = category in CLAUSE_CATEGORY_LABELS
        is_sensitive = CLAUSE_SENSITIVE_MATRIX[level].get(category, True)
        rule_id = f"contract_clause:{level.value}:{category or 'unknown'}"
        if not is_known_category:
            return ClauseJudgment(
                clause_category=category,
                matrix_clause=matrix_clause,
                counterparty_level=level.value,
                is_sensitive=True,
                risk_level="HIGH",
                matched_rules=[rule_id],
                reason="条款分类未进入规则矩阵，按敏感条款处理。",
            )

        return ClauseJudgment(
            clause_category=category,
            matrix_clause=matrix_clause,
            counterparty_level=level.value,
            is_sensitive=is_sensitive,
            risk_level="HIGH" if is_sensitive else "LOW",
            matched_rules=[rule_id],
            reason=(
                f"对手方等级 {level.value} 下，{matrix_clause} 判定为"
                f"{'敏感条款' if is_sensitive else '非敏感条款'}。"
            ),
        )
