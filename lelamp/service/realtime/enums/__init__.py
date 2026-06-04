"""Enumerations for the realtime voice agent service."""

from enum import StrEnum


class InputTypeEnum(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    FUNCTION_CALL_RESULT = "function_call_result"


class OutputTypeEnum(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    FUNCTION_CALL = "function_call"


class TurnDetectionType(StrEnum):
    SERVER_VAD = "server_vad"
    SEMANTIC_VAD = "semantic_vad"


class ReasoningEffort(StrEnum):
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


class Voice(StrEnum):
    """OpenAI Realtime voices."""
    ALLOY = "alloy"
    ASH = "ash"
    BALLAD = "ballad"
    CORAL = "coral"
    ECHO = "echo"
    SAGE = "sage"
    SHIMMER = "shimmer"
    VERSE = "verse"
    MARIN = "marin"
    CEDAR = "cedar"


class GeminiVoice(StrEnum):
    """Gemini Live voices."""
    PUCK = "Puck"
    CHARON = "Charon"
    KORE = "Kore"
    FENRIR = "Fenrir"
    AOEDE = "Aoede"
