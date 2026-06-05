"""Enumerations for the realtime voice agent service."""

from lelamp.service.realtime.enums.gemini import GeminiThinkingLevel, GeminiVoice
from lelamp.service.realtime.enums.openai import (
    OpenAIReasoningEffort,
    OpenAITurnDetectionType,
    OpenAIVoice,
)
from lelamp.service.realtime.enums.shared import (
    InputEventTypeEnum,
    InputTypeEnum,
    OutputEventTypeEnum,
    OutputTypeEnum,
)

__all__ = [
    "InputTypeEnum",
    "OutputTypeEnum",
    "InputEventTypeEnum",
    "OutputEventTypeEnum",
    "OpenAITurnDetectionType",
    "OpenAIReasoningEffort",
    "OpenAIVoice",
    "GeminiThinkingLevel",
    "GeminiVoice",
]
