"""Audio conversion utilities for PCM16 codec."""

import base64

import numpy as np
import numpy.typing as npt


def float32_to_base64_pcm16(audio: npt.NDArray[np.float32]) -> str:
    """Convert float32 audio [-1.0, 1.0] to base64-encoded PCM16. Used by OpenAI."""
    clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = (clipped * 32767).astype(np.int16)
    return base64.b64encode(pcm16.tobytes()).decode()


def base64_pcm16_to_float32(b64_audio: str) -> npt.NDArray[np.float32]:
    """Convert base64-encoded PCM16 to float32 [-1.0, 1.0]. Used by OpenAI."""
    raw = base64.b64decode(b64_audio)
    pcm16 = np.frombuffer(raw, dtype=np.int16)
    return (pcm16.astype(np.float32) / 32767.0)


def float32_to_pcm16_bytes(audio: npt.NDArray[np.float32]) -> bytes:
    """Convert float32 audio [-1.0, 1.0] to raw PCM16 bytes. Used by Gemini."""
    clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = (clipped * 32767).astype(np.int16)
    return pcm16.tobytes()


def pcm16_bytes_to_float32(data: bytes) -> npt.NDArray[np.float32]:
    """Convert raw PCM16 bytes to float32 [-1.0, 1.0]. Used by Gemini."""
    pcm16 = np.frombuffer(data, dtype=np.int16)
    return (pcm16.astype(np.float32) / 32767.0)
