class VectorStoreClient:
    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        raise NotImplementedError("vector store provider is not configured")
