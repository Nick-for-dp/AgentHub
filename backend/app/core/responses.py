from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    code: str = "OK"
    message: str = "success"
    data: T | None = None
    request_id: str | None = None


def success(data: T | None = None, request_id: str | None = None) -> APIResponse[T]:
    return APIResponse(data=data, request_id=request_id)
