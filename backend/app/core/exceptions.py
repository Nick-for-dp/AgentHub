"""
平台统一异常体系。

所有业务异常继承自 AgentHubError，由 register_exception_handlers 统一拦截
并转换为标准 JSON 响应格式：{"code": "...", "message": "...", "request_id": "..."}。

每条异常对应一个 HTTP 状态码和语义化错误码，方便前端和外部调用方识别。
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AgentHubError(Exception):
    """平台所有业务异常的基类。

    子类只需定义 code（语义化错误码）和 status_code（HTTP 状态码），
    无需重复实现 handler 逻辑。
    """

    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AgentHubError):
    """资源不存在：请求的 Agent、知识库、用户等在数据库中未找到。"""
    def __init__(self, message: str = "resource not found"):
        super().__init__("NOT_FOUND", message, status.HTTP_404_NOT_FOUND)


class UnauthorizedError(AgentHubError):
    """未认证：缺少 API Key、Key 无效、Key 已过期或被禁用。"""
    def __init__(self, message: str = "unauthorized"):
        super().__init__("UNAUTHORIZED", message, status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AgentHubError):
    """无权限：身份有效但缺少执行该操作所需的权限策略或 scope。"""
    def __init__(self, message: str = "forbidden"):
        super().__init__("FORBIDDEN", message, status.HTTP_403_FORBIDDEN)


class ConflictError(AgentHubError):
    """资源冲突：如重复的 agent code、重复的手机号等。"""
    def __init__(self, message: str = "resource conflict"):
        super().__init__("CONFLICT", message, status.HTTP_409_CONFLICT)


class BadRequestError(AgentHubError):
    """请求参数不符合业务约束：用于 Pydantic 字段校验之外的业务参数错误。"""
    def __init__(self, message: str = "bad request"):
        super().__init__("BAD_REQUEST", message, status.HTTP_400_BAD_REQUEST)


class FeatureNotImplementedError(AgentHubError):
    """能力尚未完成：用于已注册契约但还未接入完整业务实现的 MVP 骨架接口。"""
    def __init__(self, message: str = "feature not implemented"):
        super().__init__("FEATURE_NOT_IMPLEMENTED", message, status.HTTP_501_NOT_IMPLEMENTED)


class UnsupportedRuntimeError(AgentHubError):
    """不支持的 Agent runtime：Agent 配置引用了当前平台未注册的运行时类型。"""
    def __init__(self, message: str = "unsupported agent runtime"):
        super().__init__("UNSUPPORTED_RUNTIME", message, status.HTTP_400_BAD_REQUEST)


class DifyNotConfiguredError(AgentHubError):
    """Dify 集成未配置：DIFY_BASE_URL 或 DIFY_API_KEY 未在环境变量中设置。

    这是一个系统级错误，表示平台无法调用外部 Agent 运行时。
    调用记录会被标记为 FAILED，便于运维排查。
    """
    def __init__(self, message: str = "Dify integration is not configured"):
        super().__init__("DIFY_NOT_CONFIGURED", message, status.HTTP_503_SERVICE_UNAVAILABLE)


class DifyIntegrationError(AgentHubError):
    """Dify 调用失败：Dify 返回非 2xx 状态码、连接超时、或响应格式异常。

    与 DifyNotConfiguredError 区别：本异常表示 Dify 已配置但调用过程出错。
    调用记录会被标记为 FAILED，并包含 Dify 返回的原始错误信息。
    """
    def __init__(self, message: str = "Dify integration error"):
        super().__init__("DIFY_INTEGRATION_ERROR", message, status.HTTP_502_BAD_GATEWAY)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AgentHubError)
    async def agenthub_error_handler(request: Request, exc: AgentHubError) -> JSONResponse:
        request_id = request.headers.get("x-request-id")
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "request_id": request_id},
        )
