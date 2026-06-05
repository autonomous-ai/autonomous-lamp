"""Realtime orchestrator — manages voice agent lifecycle and turn processing.

Exposes a simple interface to the voice pipeline:
  - append_audio(frame) — streams audio to the model
  - commit_audio() — commits buffered audio so model processes it
  - stream_output() — yields outputs one by one as they arrive

The caller (voice_service) drives the orchestrator:
  1. Stream mic frames via append_audio()
  2. Call commit_audio() when done
  3. Iterate stream_output():
     - Yields AudioOutput / TextOutput / FunctionCallOutput chunks
     - Yields DelegateSignal if model called delegate_to_main (then stops)
"""

import asyncio
import logging
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

import lelamp.config as config
from lelamp.service.realtime.config import GeminiConfig, OpenAIConfig
from lelamp.service.realtime.models import (
    FunctionCallOutput,
    FunctionCallResultInput,
    OutputBase,
)
from lelamp.service.realtime.voice_agent.base import VoiceAgentBase

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 16000

DELEGATE_TOOL_NAME = "delegate_to_main"
DELEGATE_TOOL_DESCRIPTION = (
    "Call this when the user's request requires the main system — "
    "device control, music, scheduling, memory, skills, real-time facts, "
    "or anything beyond casual conversation. Takes no arguments."
)

DELEGATE_TOOL: dict[str, Any] = {
    "name": DELEGATE_TOOL_NAME,
    "description": DELEGATE_TOOL_DESCRIPTION,
    "parameters": {"type": "object", "properties": {}},
}


@dataclass
class DelegateSignal:
    """Yielded by stream_output() when the model calls delegate_to_main."""

    pass


class RealtimeOrchestrator:
    """Manages a single realtime voice agent session.

    Automatically registers the delegate_to_main tool so the model
    can signal that the user's request should be handled by the main
    flow (Lamp → OpenClaw).
    """

    def __init__(
        self,
        extra_tools: list[dict[str, Any]] | None = None,
    ) -> None:
        self._tools: list[dict[str, Any]] = [DELEGATE_TOOL] + (extra_tools or [])
        self._agent: VoiceAgentBase | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def available(self) -> bool:
        return self._agent is not None

    @property
    def sample_rate(self) -> int:
        """Target sample rate expected by the realtime provider."""
        if self._agent is not None:
            return self._agent.sample_rate
        return DEFAULT_SAMPLE_RATE

    def start(self) -> None:
        """Create the agent based on config and connect."""
        provider = config.REALTIME_PROVIDER.strip().lower()
        if provider in ("none", "off", "disabled", ""):
            logger.info("Realtime orchestrator disabled (provider=%s)", provider)
            return

        self._loop = asyncio.new_event_loop()

        if provider == "gemini":
            from lelamp.service.realtime.voice_agent.gemini_live import GeminiLiveAgent

            self._agent = GeminiLiveAgent(config=GeminiConfig(), tools=self._tools)

        elif provider == "openai":
            from lelamp.service.realtime.voice_agent.openai_realtime import OpenAIRealtimeAgent

            self._agent = OpenAIRealtimeAgent(config=OpenAIConfig(), tools=self._tools)

        else:
            logger.warning("Unknown realtime provider: %s — disabled", provider)
            return

        try:
            self._loop.run_until_complete(self._agent.connect())
            logger.info("Realtime orchestrator started (provider=%s)", provider)
        except Exception:
            logger.exception("Failed to connect realtime agent")
            self._agent = None

    def stop(self) -> None:
        """Disconnect the agent."""
        if self._agent is not None and self._loop is not None:
            try:
                self._loop.run_until_complete(self._agent.disconnect())
            except Exception:
                logger.exception("Failed to disconnect realtime agent")
            self._agent = None
        if self._loop is not None:
            self._loop.close()
            self._loop = None
        logger.info("Realtime orchestrator stopped")

    def append_audio(self, frame: npt.NDArray[np.float32]) -> None:
        """Stream a single audio frame to the model without committing."""
        if self._agent is None or self._loop is None:
            return
        self._loop.run_until_complete(self._agent.append_audio(frame))

    def commit_audio(self) -> None:
        """Commit buffered audio so the model processes it."""
        if self._agent is None or self._loop is None:
            return
        self._loop.run_until_complete(self._agent.commit_audio())

    def stream_output(self) -> Generator[OutputBase | DelegateSignal, None, None]:
        """Yield outputs from the model one by one as they arrive.

        Yields:
          - AudioOutput / TextOutput / FunctionCallOutput as they stream in
          - DelegateSignal if model called delegate_to_main (then stops)

        The generator returns (StopIteration) when the model's turn is done.
        """
        if self._agent is None or self._loop is None:
            return

        queue: asyncio.Queue[OutputBase | DelegateSignal | None] = asyncio.Queue()

        async def _produce() -> None:
            async for output in self._agent.receive(stop_on_done=True):
                if isinstance(output, FunctionCallOutput) and output.name == DELEGATE_TOOL_NAME:
                    logger.info("Model delegated to main flow")
                    await self._agent.send([
                        FunctionCallResultInput(
                            call_id=output.call_id,
                            output='{"result": "delegated"}',
                        )
                    ])
                    await queue.put(DelegateSignal())
                    return
                await queue.put(output)
            await queue.put(None)  # sentinel: turn done

        task = self._loop.create_task(_produce())

        try:
            while True:
                item = self._loop.run_until_complete(queue.get())
                if item is None:
                    break
                yield item
                if isinstance(item, DelegateSignal):
                    break
        finally:
            self._loop.run_until_complete(task)

    def send_function_result(self, call_id: str, output: str) -> None:
        """Send a function call result back to the model."""
        if self._agent is None or self._loop is None:
            return
        self._loop.run_until_complete(
            self._agent.send([FunctionCallResultInput(call_id=call_id, output=output)])
        )
