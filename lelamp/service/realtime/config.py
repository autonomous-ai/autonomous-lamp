"""Configuration for realtime voice agent providers.

All values are read from lelamp.config (environment variables).
"""

from typing import Optional

import lelamp.config as app_config
from lelamp.service.realtime.enums import GeminiVoice, TurnDetectionType, Voice


def _parse_turn_detection(value: str) -> Optional[TurnDetectionType]:
    """Parse LELAMP_REALTIME_TURN_DETECTION into a TurnDetectionType or None (off)."""
    v = value.strip().lower()
    if v in ("off", "none", ""):
        return None
    try:
        return TurnDetectionType(v)
    except ValueError:
        return TurnDetectionType.SERVER_VAD


class OpenAIConfig:
    api_key: str = app_config.REALTIME_OPENAI_API_KEY
    model: str = app_config.REALTIME_OPENAI_MODEL
    voice: Voice = Voice(app_config.REALTIME_OPENAI_VOICE)
    instructions: str = app_config.REALTIME_INSTRUCTIONS
    sample_rate: int = app_config.REALTIME_OPENAI_SAMPLE_RATE
    turn_detection_type: Optional[TurnDetectionType] = _parse_turn_detection(
        app_config.REALTIME_TURN_DETECTION
    )
    reasoning_effort = None


class GeminiConfig:
    api_key: str = app_config.REALTIME_GEMINI_API_KEY
    model: str = app_config.REALTIME_GEMINI_MODEL
    voice: GeminiVoice = GeminiVoice(app_config.REALTIME_GEMINI_VOICE)
    instructions: str = app_config.REALTIME_INSTRUCTIONS
    sample_rate: int = app_config.REALTIME_GEMINI_SAMPLE_RATE
    vad_enabled: bool = _parse_turn_detection(app_config.REALTIME_TURN_DETECTION) is not None
