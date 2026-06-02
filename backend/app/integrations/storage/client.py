from dataclasses import dataclass


@dataclass(frozen=True)
class StoredObject:
    uri: str
    size: int | None = None
    content_type: str | None = None


class StorageClient:
    async def put_object(self, key: str, content: bytes, content_type: str | None = None) -> StoredObject:
        raise NotImplementedError("storage provider is not configured")
