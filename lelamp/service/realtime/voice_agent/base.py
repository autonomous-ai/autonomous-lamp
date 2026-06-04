"""Abstract base class for realtime voice agents."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

import numpy as np
import numpy.typing as npt

from lelamp.service.realtime.models import InputBase, OutputBase


class VoiceAgentBase(ABC):
    """Minimal interface for a realtime voice agent.

    Lifecycle: connect → (append_audio / commit_audio / send + receive) → disconnect.
    Supports async context manager for automatic cleanup.
    """

    def __init__(self, tools: list[dict[str, Any]] | None = None):
        self._tools: list[dict[str, Any]] = tools or []

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the realtime provider."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection."""

    @abstractmethod
    async def send(self, inputs: list[InputBase]) -> None:
        """Send one or more inputs (text, image, function result).

        Does NOT handle audio — use append_audio + commit_audio for that.
        """

    @abstractmethod
    async def receive(self, *, stop_on_done: bool = True) -> AsyncGenerator[OutputBase, None]:
        """Async generator yielding output chunks until the turn is done.

        Yields TextOutput, AudioOutput, or FunctionCallOutput.
        """
        yield  # type: ignore  # make this a generator

    @abstractmethod
    async def append_audio(self, audio: npt.NDArray[np.float32]) -> None:
        """Stream a single audio frame without committing.

        Used for continuous mic streaming. Frames are buffered until
        commit_audio() is called.
        """

    @abstractmethod
    async def commit_audio(self) -> None:
        """Commit the buffered audio so the model processes it.

        OpenAI Realtime requires explicit commit; Gemini processes
        audio incrementally (commit is a no-op).
        """

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        return False
