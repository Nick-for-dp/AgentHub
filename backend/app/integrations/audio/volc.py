import logging
import asyncio
import json
from collections.abc import AsyncIterator
from uuid import uuid4

import websockets

from app.core.config import Settings
from app.integrations.audio.errors import AudioIntegrationError, AudioNotConfiguredError
from app.integrations.audio.schemas import AudioTranscriptionResult
from app.integrations.audio.volc_protocol import (
    TtsEvent,
    VolcMessageType,
    build_asr_audio_request,
    build_asr_full_client_request,
    build_tts_finish_connection,
    build_tts_send_text,
    parse_frame,
)
from app.integrations.audio.wav import split_pcm_chunks, wav_to_pcm16_mono_16k

logger = logging.getLogger(__name__)


class VolcAudioClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _require_config(self, *, tts: bool = False) -> None:
        if not self.settings.volc_audio_api_key:
            raise AudioNotConfiguredError("VOLC_AUDIO_API_KEY is not configured")
        if tts and not self.settings.volc_tts_speaker:
            raise AudioNotConfiguredError("VOLC_TTS_SPEAKER is not configured")

    def _headers(self, *, resource_id: str, request_id: str) -> dict[str, str]:
        return {
            "X-Api-Key": self.settings.volc_audio_api_key or "",
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": request_id,
            "X-Api-Connect-Id": request_id,
            "X-Api-Sequence": "-1",
        }

    async def transcribe_wav(
        self,
        *,
        content: bytes,
        user_id: str,
        filename: str | None = None,
    ) -> AudioTranscriptionResult:
        self._require_config()
        request_id = str(uuid4())
        pcm = wav_to_pcm16_mono_16k(content)
        chunks = split_pcm_chunks(pcm, sample_rate=self.settings.volc_asr_sample_rate)
        if not chunks:
            raise AudioIntegrationError("uploaded audio is empty")

        payload = {
            "user": {"uid": user_id},
            "audio": {
                "format": self.settings.volc_asr_audio_format,
                "rate": self.settings.volc_asr_sample_rate,
                "bits": 16,
                "channel": 1,
                "language": self.settings.volc_asr_language,
            },
            "request": {
                "model_name": "bigmodel",
                "enable_itn": True,
                "enable_punc": True,
                "result_type": "full",
            },
        }
        final_text = ""
        last_payload: dict = {}
        log_id: str | None = None

        try:
            async with websockets.connect(
                self.settings.volc_asr_ws_url,
                additional_headers=self._headers(
                    resource_id=self.settings.volc_asr_resource_id,
                    request_id=request_id,
                ),
                max_size=None,
            ) as ws:
                response_headers = getattr(ws, "response", None)
                if response_headers is not None:
                    log_id = response_headers.headers.get("X-Tt-Logid")
                await ws.send(build_asr_full_client_request(payload, sequence=1))
                for index, chunk in enumerate(chunks):
                    await ws.send(
                        build_asr_audio_request(
                            chunk,
                            sequence=index + 2,
                            is_last=index == len(chunks) - 1,
                        )
                    )
                    await asyncio.sleep(0)

                while True:
                    message = await ws.recv()
                    if not isinstance(message, bytes):
                        continue
                    frame = parse_frame(message)
                    if frame.message_type != VolcMessageType.FULL_SERVER_RESPONSE:
                        continue
                    data = frame.json_payload()
                    last_payload = data
                    text = (data.get("result") or {}).get("text")
                    if text:
                        final_text = text
                    if frame.flags == 0x3:
                        break
        except AudioIntegrationError:
            raise
        except Exception as exc:
            raise AudioIntegrationError(f"Volc ASR request failed: {exc}") from exc

        if not final_text:
            final_text = ((last_payload.get("result") or {}).get("text") or "").strip()
        return AudioTranscriptionResult(
            text=final_text.strip(),
            request_id=request_id,
            log_id=log_id,
            metadata={
                "filename": filename,
                "audio_duration_ms": (last_payload.get("audio_info") or {}).get("duration"),
            },
        )

    async def stream_speech(
        self,
        *,
        text: str,
        user_id: str,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        self._require_config(tts=True)
        request_id = str(uuid4())
        speaker = voice or self.settings.volc_tts_speaker
        payload = {
            "user": {"uid": user_id},
            "req_params": {
                "text": text,
                "speaker": speaker,
                "audio_params": {
                    "format": self.settings.volc_tts_audio_format,
                    "sample_rate": self.settings.volc_tts_sample_rate,
                },
                "additions": {
                    "disable_markdown_filter": False,
                },
            },
        }
        payload["req_params"]["additions"] = json.dumps(
            payload["req_params"]["additions"],
            ensure_ascii=False,
            separators=(",", ":"),
        )

        try:
            async with websockets.connect(
                self.settings.volc_tts_ws_url,
                additional_headers=self._headers(
                    resource_id=self.settings.volc_tts_resource_id,
                    request_id=request_id,
                ),
                max_size=None,
            ) as ws:
                await ws.send(build_tts_send_text(payload))
                finished = False
                while not finished:
                    message = await ws.recv()
                    if not isinstance(message, bytes):
                        continue
                    frame = parse_frame(message)
                    if frame.message_type == VolcMessageType.AUDIO_ONLY_RESPONSE and frame.event == TtsEvent.TTS_RESPONSE:
                        if frame.payload:
                            yield frame.payload
                    elif frame.event == TtsEvent.SESSION_FINISHED:
                        meta = frame.json_payload()
                        status_code = meta.get("status_code")
                        if status_code and status_code != 20000000:
                            raise AudioIntegrationError(f"Volc TTS failed: {meta.get('message') or status_code}")
                        finished = True
                try:
                    await ws.send(build_tts_finish_connection())
                except Exception:
                    logger.debug("failed to send Volc TTS finish connection", exc_info=True)
        except AudioIntegrationError:
            raise
        except Exception as exc:
            raise AudioIntegrationError(f"Volc TTS request failed: {exc}") from exc
