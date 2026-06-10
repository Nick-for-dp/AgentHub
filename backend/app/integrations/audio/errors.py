from fastapi import status

from app.core.exceptions import AgentHubError


class AudioNotConfiguredError(AgentHubError):
    def __init__(self, message: str = "audio integration is not configured"):
        super().__init__("AUDIO_NOT_CONFIGURED", message, status.HTTP_503_SERVICE_UNAVAILABLE)


class AudioIntegrationError(AgentHubError):
    def __init__(self, message: str = "audio integration error"):
        super().__init__("AUDIO_INTEGRATION_ERROR", message, status.HTTP_502_BAD_GATEWAY)

