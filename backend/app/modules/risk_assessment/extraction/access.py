from app.core.enums import Visibility
from app.core.exceptions import ForbiddenError
from app.modules.auth.schemas import AuthenticatedSubject


def assert_risk_document_extraction_access(*, agent, subject: AuthenticatedSubject) -> None:
    """一期风控抽取只允许内部可见 Agent 的已登录内部用户调用。"""
    raw_visibility = getattr(agent, "visibility", None)
    visibility = (
        raw_visibility.value if isinstance(raw_visibility, Visibility) else str(raw_visibility)
    )
    if visibility != Visibility.INTERNAL.value:
        raise ForbiddenError("risk document extraction requires an internal agent")
    if not subject.user_id or not subject.org_unit_id or subject.caller_type.upper() != "USER":
        raise ForbiddenError("risk document extraction requires an authenticated internal user")
