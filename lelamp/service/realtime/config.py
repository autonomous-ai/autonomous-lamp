"""Configuration for realtime voice agent providers.

All values are read from lelamp.config (environment variables).
"""

import lelamp.config as app_config
from lelamp.service.realtime.enums import GeminiVoice, Voice


class OpenAIConfig:
    api_key: str = app_config.REALTIME_OPENAI_API_KEY
    model: str = app_config.REALTIME_OPENAI_MODEL
    voice: Voice = Voice(app_config.REALTIME_OPENAI_VOICE)
    instructions: str = app_config.REALTIME_INSTRUCTIONS
    sample_rate: int = app_config.REALTIME_OPENAI_SAMPLE_RATE


class GeminiConfig:
    api_key: str = app_config.REALTIME_GEMINI_API_KEY
    model: str = app_config.REALTIME_GEMINI_MODEL
    voice: GeminiVoice = GeminiVoice(app_config.REALTIME_GEMINI_VOICE)
    instructions: str = app_config.REALTIME_INSTRUCTIONS
    sample_rate: int = app_config.REALTIME_GEMINI_SAMPLE_RATE
