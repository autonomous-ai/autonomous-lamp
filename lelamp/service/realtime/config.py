"""Configuration for realtime voice agent providers.

All values are read from lelamp.config (environment variables).
"""

from pathlib import Path
from typing import Optional

import lelamp.config as app_config
from lelamp.service.realtime.enums import (
    GeminiThinkingLevel,
    GeminiVoice,
    OpenAIReasoningEffort,
    OpenAITurnDetectionType,
    OpenAIVoice,
)

_RESOURCES_DIR = Path(__file__).parent / "resources"
_DEFAULT_PROMPT_PATH = _RESOURCES_DIR / "system_prompt.md"


def _load_instructions() -> str:
    """Load instructions from env var or fall back to default prompt file."""
    env_instructions: str = app_config.REALTIME_INSTRUCTIONS
    if env_instructions:
        return env_instructions
    try:
        return _DEFAULT_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


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


class OpenAIConfig:
    api_key: str = app_config.REALTIME_OPENAI_API_KEY
    model: str = app_config.REALTIME_OPENAI_MODEL
    voice: OpenAIVoice = OpenAIVoice(app_config.REALTIME_OPENAI_VOICE)
    instructions: str = _load_instructions()
    sample_rate: int = app_config.REALTIME_OPENAI_SAMPLE_RATE
    language: Optional[str] = _load_language()
    turn_detection_type: Optional[OpenAITurnDetectionType] = _parse_turn_detection(
        app_config.REALTIME_TURN_DETECTION
    )
    reasoning_effort: OpenAIReasoningEffort = OpenAIReasoningEffort.XHIGH


class GeminiConfig:
    api_key: str = app_config.REALTIME_GEMINI_API_KEY
    model: str = app_config.REALTIME_GEMINI_MODEL
    voice: GeminiVoice = GeminiVoice(app_config.REALTIME_GEMINI_VOICE)
    instructions: str = _load_instructions()
    sample_rate: int = app_config.REALTIME_GEMINI_SAMPLE_RATE
    language: Optional[str] = _load_language()
    thinking_level: GeminiThinkingLevel = GeminiThinkingLevel.HIGH
    vad_enabled: bool = (
        app_config.REALTIME_TURN_DETECTION.strip().lower() not in ("off", "none", "")
    )
