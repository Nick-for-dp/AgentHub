from enum import StrEnum


class ResourceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DELETED = "DELETED"


class OrgUnitType(StrEnum):
    EXTERNAL_CUSTOMER = "EXTERNAL_CUSTOMER"
    INTERNAL_COMPANY = "INTERNAL_COMPANY"
    INTERNAL_DEPARTMENT = "INTERNAL_DEPARTMENT"


class UserType(StrEnum):
    EXTERNAL_CUSTOMER = "EXTERNAL_CUSTOMER"
    INTERNAL_EMPLOYEE = "INTERNAL_EMPLOYEE"


class APIKeyOwnerType(StrEnum):
    USER = "USER"
    ORG_UNIT = "ORG_UNIT"


class APIKeyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class EmbedSessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class SubjectType(StrEnum):
    USER = "USER"
    ORG_UNIT = "ORG_UNIT"
    API_KEY = "API_KEY"


class ResourceType(StrEnum):
    AGENT = "AGENT"
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"
    DOCUMENT = "DOCUMENT"
    API = "API"


class PolicyEffect(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class AgentType(StrEnum):
    QA = "QA"


class RuntimeType(StrEnum):
    DIFY = "DIFY"
    CUSTOM = "CUSTOM"


class PublishStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"


class Visibility(StrEnum):
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"
    PRIVATE = "PRIVATE"


class ProviderType(StrEnum):
    DIFY = "DIFY"
    CUSTOM = "CUSTOM"


class ParseStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class InvocationStatus(StrEnum):
    PENDING = "PENDING"
    STREAMING = "STREAMING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ConversationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class ConversationMessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class ConversationMessageStatus(StrEnum):
    STREAMING = "STREAMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class CallerType(StrEnum):
    USER = "USER"
    API_KEY = "API_KEY"


class OperationType(StrEnum):
    QA = "QA"


class LeadStatus(StrEnum):
    PROVISIONAL = "PROVISIONAL"
    IDENTIFIED = "IDENTIFIED"
    QUALIFIED = "QUALIFIED"
    CLOSED = "CLOSED"
    DISCARDED = "DISCARDED"


class LeadCaptureEventStatus(StrEnum):
    CAPTURED = "CAPTURED"
    IGNORED = "IGNORED"
    FAILED = "FAILED"


class EvaluationCaseType(StrEnum):
    QA = "QA"
    REGRESSION = "REGRESSION"
    BAD_CASE = "BAD_CASE"


class JudgeType(StrEnum):
    MANUAL = "MANUAL"
    LLM = "LLM"
