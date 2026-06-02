class LLMClient:
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError("llm provider is not configured")
