from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.enums import CallerType
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.responses import APIResponse, success
from app.integrations.audio.errors import AudioNotConfiguredError
from app.integrations.audio.schemas import AudioTranscriptionResult, SpeechSynthesisRequest
from app.integrations.audio.volc import VolcAudioClient
from app.modules.auth.dependencies import get_current_subject
from app.modules.auth.schemas import AuthenticatedSubject

router = APIRouter()

MAX_AUDIO_UPLOAD_BYTES = 15 * 1024 * 1024

# 语音接口 scope：API Key 默认只用于问答（invoke），不得因持有问答权限顺带调用语音。
# 只有显式签发了对应 scope 的 API Key 才能调用语音转写/合成。
AUDIO_TRANSCRIBE_SCOPE = "audio:transcribe"
AUDIO_SPEECH_SCOPE = "audio:speech"


def _audio_user_id(subject: AuthenticatedSubject) -> str:
    if subject.caller_type == CallerType.USER and subject.user_id:
        return subject.user_id
    if subject.caller_type == CallerType.API_KEY and subject.api_key_id:
        return subject.api_key_id
    raise UnauthorizedError("audio requires authenticated subject")


def _require_audio_scope(subject: AuthenticatedSubject, scope: str) -> None:
    """收紧 API Key 对语音接口的访问。

    Cookie 登录用户和 iframe embed 用户（api_key_id 为空）由会话本身授权，不受 scope 限制。
    API Key 调用者必须显式持有对应语音 scope（或通配 *），否则返回 403。
    """
    if subject.api_key_id is None:
        return
    if scope not in subject.scopes and "*" not in subject.scopes:
        raise ForbiddenError("api key scope does not allow this audio action")


@router.post("/transcriptions", response_model=APIResponse[AudioTranscriptionResult])
async def transcribe_audio(
    file: UploadFile = File(...),
    subject: AuthenticatedSubject = Depends(get_current_subject),
) -> APIResponse[AudioTranscriptionResult]:
    _require_audio_scope(subject, AUDIO_TRANSCRIBE_SCOPE)
    content = await file.read()
    if len(content) > MAX_AUDIO_UPLOAD_BYTES:
        from app.integrations.audio.errors import AudioIntegrationError

        raise AudioIntegrationError("uploaded audio exceeds 15MB")
    result = await VolcAudioClient(get_settings()).transcribe_wav(
        content=content,
        user_id=_audio_user_id(subject),
        filename=file.filename,
    )
    return success(result)


@router.post("/speech")
async def synthesize_speech(
    payload: SpeechSynthesisRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
) -> StreamingResponse:
    _require_audio_scope(subject, AUDIO_SPEECH_SCOPE)
    settings = get_settings()
    if not settings.volc_audio_api_key:
        raise AudioNotConfiguredError("VOLC_AUDIO_API_KEY is not configured")
    if not settings.volc_tts_speaker and not payload.voice:
        raise AudioNotConfiguredError("VOLC_TTS_SPEAKER is not configured")
    stream = VolcAudioClient(settings).stream_speech(
        text=payload.text,
        user_id=_audio_user_id(subject),
        voice=payload.voice,
    )
    media_type = "audio/mpeg" if settings.volc_tts_audio_format == "mp3" else "application/octet-stream"
    return StreamingResponse(stream, media_type=media_type)
