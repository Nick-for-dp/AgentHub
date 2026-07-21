from enum import StrEnum


class DeploymentProfile(StrEnum):
    EXTERNAL = "external"
    INTERNAL = "internal"


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
    CONTRACT_REVIEW = "CONTRACT_REVIEW"
    RISK_ASSISTANT = "RISK_ASSISTANT"
    REPORT_EXTRACTION = "REPORT_EXTRACTION"
    DOCUMENT_WRITING = "DOCUMENT_WRITING"


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


class FileParseTaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ContractReviewTaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RiskAssessmentTaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_REVIEW = "WAITING_REVIEW"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DocumentTypeValidationStatus(StrEnum):
    MATCHED = "MATCHED"
    SUSPECTED = "SUSPECTED"
    UNVERIFIED = "UNVERIFIED"


class RiskReviewTargetKind(StrEnum):
    FIELD = "FIELD"
    DOCUMENT_TYPE = "DOCUMENT_TYPE"


class CounterpartyLevel(StrEnum):
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"
    A6 = "A6"
    A7 = "A7"


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
    CONTRACT_REVIEW = "CONTRACT_REVIEW"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"
    REPORT_EXTRACTION = "REPORT_EXTRACTION"
    DOCUMENT_WRITING = "DOCUMENT_WRITING"


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
