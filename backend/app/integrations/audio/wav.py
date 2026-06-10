import io
import wave

from app.integrations.audio.errors import AudioIntegrationError


def wav_to_pcm16_mono_16k(content: bytes) -> bytes:
    """Extract PCM from a WAV container and validate the ASR-compatible shape."""
    try:
        with wave.open(io.BytesIO(content), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except wave.Error as exc:
        raise AudioIntegrationError("uploaded audio must be WAV PCM") from exc

    if channels != 1 or sample_width != 2 or sample_rate != 16000:
        raise AudioIntegrationError("uploaded WAV must be 16kHz mono pcm_s16le")
    return frames


def split_pcm_chunks(
    pcm: bytes,
    *,
    sample_rate: int = 16000,
    bytes_per_sample: int = 2,
    channels: int = 1,
    chunk_ms: int = 200,
) -> list[bytes]:
    frame_size = bytes_per_sample * channels
    bytes_per_ms = sample_rate * frame_size // 1000
    chunk_size = max(frame_size, bytes_per_ms * chunk_ms)
    chunks = [pcm[i: i + chunk_size] for i in range(0, len(pcm), chunk_size)]
    return [chunk for chunk in chunks if chunk]

