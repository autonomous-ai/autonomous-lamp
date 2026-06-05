"""Configuration for realtime voice agent providers.

All values are read from lelamp.config (environment variables).
"""

from typing import Optional

from pydantic import BaseModel

import lelamp.config as app_config
from lelamp.service.realtime.enums import (
    GeminiThinkingLevel,
    GeminiVoice,
    OpenAIReasoningEffort,
    OpenAITruncationType,
    OpenAITurnDetectionType,
    OpenAIVoice,
)

def _load_language() -> str | None:
    """Load language from Lamp's config.json (stt_language field)."""
    from lelamp.config import _lamp_cfg_get

    lang: str = _lamp_cfg_get("stt_language", "").strip()
    return lang if lang else None


def _parse_turn_detection(value: str) -> OpenAITurnDetectionType | None:
    """Parse LELAMP_REALTIME_TURN_DETECTION into an OpenAITurnDetectionType or None (off)."""
    v = value.strip().lower()
    if v in ("off", "none", ""):
        return None
    try:
        return OpenAITurnDetectionType(v)
    except ValueError:
        return OpenAITurnDetectionType.SERVER_VAD


class OpenAIConfig(BaseModel):
    api_key: str = app_config.REALTIME_OPENAI_API_KEY
    model: str = app_config.REALTIME_OPENAI_MODEL
    voice: OpenAIVoice = OpenAIVoice(app_config.REALTIME_OPENAI_VOICE)
    instructions: str = ""
    sample_rate: int = app_config.REALTIME_OPENAI_SAMPLE_RATE
    language: Optional[str] = _load_language()
    turn_detection_type: Optional[OpenAITurnDetectionType] = _parse_turn_detection(
        app_config.REALTIME_TURN_DETECTION
    )
    reasoning_effort: OpenAIReasoningEffort = OpenAIReasoningEffort(app_config.REALTIME_OPENAI_REASONING_EFFORT)
    truncation_type: OpenAITruncationType = OpenAITruncationType.RETENTION_RATIO
    truncation_retention_ratio: float = 0.5


class GeminiConfig(BaseModel):
    api_key: str = app_config.REALTIME_GEMINI_API_KEY
    model: str = app_config.REALTIME_GEMINI_MODEL
    voice: GeminiVoice = GeminiVoice(app_config.REALTIME_GEMINI_VOICE)
    instructions: str = ""
    sample_rate: int = app_config.REALTIME_GEMINI_SAMPLE_RATE
    language: Optional[str] = _load_language()
    use_language_codes: bool = app_config.REALTIME_GEMINI_USE_LANGUAGE_CODES
    thinking_level: GeminiThinkingLevel = GeminiThinkingLevel(app_config.REALTIME_GEMINI_THINKING_LEVEL)
    vad_enabled: bool = (
        app_config.REALTIME_TURN_DETECTION.strip().lower() not in ("off", "none", "")
    )
    context_window_compression: bool = True
