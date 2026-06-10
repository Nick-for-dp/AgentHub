import gzip
import json
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from app.integrations.audio.errors import AudioIntegrationError


class VolcMessageType(IntEnum):
    FULL_CLIENT_REQUEST = 0x1
    AUDIO_ONLY_REQUEST = 0x2
    FULL_SERVER_RESPONSE = 0x9
    AUDIO_ONLY_RESPONSE = 0xB
    ERROR = 0xF


class VolcFlags(IntEnum):
    NONE = 0x0
    POS_SEQUENCE = 0x1
    LAST_NO_SEQUENCE = 0x2
    NEG_SEQUENCE = 0x3
    WITH_EVENT = 0x4


class VolcSerialization(IntEnum):
    RAW = 0x0
    JSON = 0x1


class VolcCompression(IntEnum):
    NONE = 0x0
    GZIP = 0x1


class TtsEvent(IntEnum):
    FINISH_CONNECTION = 2
    CONNECTION_FINISHED = 52
    SESSION_FINISHED = 152
    TTS_SENTENCE_START = 350
    TTS_SENTENCE_END = 351
    TTS_RESPONSE = 352


@dataclass(frozen=True)
class VolcFrame:
    message_type: int
    flags: int
    serialization: int
    compression: int
    payload: bytes
    sequence: int | None = None
    event: int | None = None
    session_id: str | None = None
    error_code: int | None = None

    def json_payload(self) -> dict[str, Any]:
        if not self.payload:
            return {}
        try:
            return json.loads(self.payload.decode("utf-8"))
        except Exception as exc:
            raise AudioIntegrationError("failed to parse audio provider JSON payload") from exc


def _header(
    *,
    message_type: int,
    flags: int,
    serialization: int,
    compression: int,
) -> bytes:
    return bytes([
        0x11,
        ((message_type & 0x0F) << 4) | (flags & 0x0F),
        ((serialization & 0x0F) << 4) | (compression & 0x0F),
        0x00,
    ])


def _encode_payload(payload: bytes, compression: int) -> bytes:
    return gzip.compress(payload) if compression == VolcCompression.GZIP else payload


def _decode_payload(payload: bytes, compression: int) -> bytes:
    return gzip.decompress(payload) if compression == VolcCompression.GZIP and payload else payload


def json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def build_asr_full_client_request(payload: dict[str, Any], *, sequence: int = 1) -> bytes:
    body = _encode_payload(json_bytes(payload), VolcCompression.GZIP)
    return (
        _header(
            message_type=VolcMessageType.FULL_CLIENT_REQUEST,
            flags=VolcFlags.POS_SEQUENCE,
            serialization=VolcSerialization.JSON,
            compression=VolcCompression.GZIP,
        )
        + struct.pack(">i", sequence)
        + struct.pack(">I", len(body))
        + body
    )


def build_asr_audio_request(audio: bytes, *, sequence: int, is_last: bool) -> bytes:
    body = _encode_payload(audio, VolcCompression.GZIP)
    frame_sequence = -abs(sequence) if is_last else abs(sequence)
    return (
        _header(
            message_type=VolcMessageType.AUDIO_ONLY_REQUEST,
            flags=VolcFlags.NEG_SEQUENCE if is_last else VolcFlags.POS_SEQUENCE,
            serialization=VolcSerialization.RAW,
            compression=VolcCompression.GZIP,
        )
        + struct.pack(">i", frame_sequence)
        + struct.pack(">I", len(body))
        + body
    )


def build_tts_send_text(payload: dict[str, Any]) -> bytes:
    body = json_bytes(payload)
    return (
        _header(
            message_type=VolcMessageType.FULL_CLIENT_REQUEST,
            flags=VolcFlags.NONE,
            serialization=VolcSerialization.JSON,
            compression=VolcCompression.NONE,
        )
        + struct.pack(">I", len(body))
        + body
    )


def build_tts_finish_connection() -> bytes:
    payload = b"{}"
    return (
        _header(
            message_type=VolcMessageType.FULL_CLIENT_REQUEST,
            flags=VolcFlags.WITH_EVENT,
            serialization=VolcSerialization.JSON,
            compression=VolcCompression.NONE,
        )
        + struct.pack(">I", TtsEvent.FINISH_CONNECTION)
        + struct.pack(">I", len(payload))
        + payload
    )


def parse_frame(data: bytes) -> VolcFrame:
    if len(data) < 8:
        raise AudioIntegrationError("audio provider returned an invalid frame")

    first, second, third, _reserved = data[:4]
    header_size = (first & 0x0F) * 4
    if len(data) < header_size + 4:
        raise AudioIntegrationError("audio provider returned a truncated frame")

    message_type = (second >> 4) & 0x0F
    flags = second & 0x0F
    serialization = (third >> 4) & 0x0F
    compression = third & 0x0F
    offset = header_size
    sequence: int | None = None
    event: int | None = None
    session_id: str | None = None
    error_code: int | None = None

    if message_type == VolcMessageType.ERROR:
        error_code = struct.unpack(">I", data[offset: offset + 4])[0]
        offset += 4
        size = struct.unpack(">I", data[offset: offset + 4])[0]
        offset += 4
        payload = data[offset: offset + size]
        raise AudioIntegrationError(f"audio provider error {error_code}: {payload.decode('utf-8', errors='ignore')}")

    if flags in (VolcFlags.POS_SEQUENCE, VolcFlags.NEG_SEQUENCE):
        sequence = struct.unpack(">i", data[offset: offset + 4])[0]
        offset += 4

    if flags == VolcFlags.WITH_EVENT:
        event = struct.unpack(">I", data[offset: offset + 4])[0]
        offset += 4
        if len(data) >= offset + 4:
            session_len = struct.unpack(">I", data[offset: offset + 4])[0]
            offset += 4
            if session_len:
                session_id = data[offset: offset + session_len].decode("utf-8", errors="ignore")
                offset += session_len

    if len(data) < offset + 4:
        payload = b""
    else:
        size = struct.unpack(">I", data[offset: offset + 4])[0]
        offset += 4
        payload = data[offset: offset + size]

    payload = _decode_payload(payload, compression)
    return VolcFrame(
        message_type=message_type,
        flags=flags,
        serialization=serialization,
        compression=compression,
        payload=payload,
        sequence=sequence,
        event=event,
        session_id=session_id,
        error_code=error_code,
    )
