"""OpenAI Realtime voice agent implementation."""

import base64
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any, override

import cv2
import numpy as np
import numpy.typing as npt
from openai import AsyncOpenAI
from openai.resources.realtime.realtime import AsyncRealtimeConnection

from lelamp.service.realtime.config import OpenAIConfig
from lelamp.service.realtime.enums import TurnDetectionType
from lelamp.service.realtime.exceptions import OpenAIRealtimeError
from lelamp.service.realtime.models import (
    AudioInput,
    AudioOutput,
    FunctionCallOutput,
    FunctionCallResultInput,
    ImageInput,
    InputBase,
    OutputBase,
    TextInput,
    TextOutput,
)
from lelamp.service.realtime.utils import base64_pcm16_to_float32, float32_to_base64_pcm16
from lelamp.service.realtime.voice_agent.base import VoiceAgentBase

logger = logging.getLogger(__name__)


class OpenAIRealtimeAgent(VoiceAgentBase):

    def __init__(
        self,
        config: OpenAIConfig,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(tools=tools)
        self._config = config
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )
        self._connection: AsyncRealtimeConnection | None = None
        self._speech_stopped_at: float | None = None

    @override
    async def connect(self) -> None:
        logger.info("Connecting to OpenAI Realtime API (model=%s)", self._config.model)

        self._connection = await self._client.realtime.connect(
            model=self._config.model,
        ).enter()

        turn_detection = None
        if self._config.turn_detection_type is not None:
            td_type = self._config.turn_detection_type
            if td_type == TurnDetectionType.SERVER_VAD:
                turn_detection = {"type": "server_vad"}
            elif td_type == TurnDetectionType.SEMANTIC_VAD:
                turn_detection = {"type": "semantic_vad"}

        session_config: dict[str, Any] = {
            "type": "realtime",
            "instructions": self._config.instructions or "",
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": self._config.sample_rate},
                    "turn_detection": turn_detection,
                },
                "output": {
                    "format": {"type": "audio/pcm", "rate": self._config.sample_rate},
                    "voice": self._config.voice.value,
                },
            },
        }

        if self._tools:
            session_config["tools"] = self._tools
            session_config["tool_choice"] = "auto"

        if self._config.reasoning_effort is not None:
            session_config["reasoning"] = {
                "effort": self._config.reasoning_effort.value,
            }

        await self._connection.session.update(session=session_config)
        logger.info("OpenAI Realtime session open (voice=%s)", self._config.voice)

    @override
    async def disconnect(self) -> None:
        if self._connection is not None:
            logger.info("Disconnecting from OpenAI Realtime API")
            await self._connection.close()
            self._connection = None

    @override
    async def send(self, inputs: list[InputBase]) -> None:
        if self._connection is None:
            raise RuntimeError("Not connected")

        for inp in inputs:
            if isinstance(inp, TextInput):
                await self._connection.conversation.item.create(
                    item={
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": inp.text}],
                    }
                )

            elif isinstance(inp, AudioInput):
                b64_audio = float32_to_base64_pcm16(inp.audio)
                await self._connection.input_audio_buffer.append(audio=b64_audio)
                await self._connection.input_audio_buffer.commit()

            elif isinstance(inp, ImageInput):
                _, buf = cv2.imencode(".png", inp.image)
                b64_img = base64.b64encode(buf.tobytes()).decode("ascii")
                data_uri = f"data:image/png;base64,{b64_img}"
                await self._connection.conversation.item.create(
                    item={
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_image", "image_url": data_uri}],
                    }
                )

            elif isinstance(inp, FunctionCallResultInput):
                await self._connection.conversation.item.create(
                    item={
                        "type": "function_call_output",
                        "call_id": inp.call_id,
                        "output": inp.output,
                    }
                )

            else:
                raise ValueError(f"Unsupported input type: {type(inp)}")

        await self._connection.response.create()

    @override
    async def receive(
        self, *, stop_on_done: bool = True
    ) -> AsyncGenerator[OutputBase, None]:
        if self._connection is None:
            raise RuntimeError("Not connected")

        async for event in self._connection:
            match event.type:
                case "input_audio_buffer.speech_stopped":
                    self._speech_stopped_at = time.perf_counter()

                case "response.output_text.delta":
                    yield TextOutput(text=event.delta)

                case "response.output_audio.delta":
                    if self._speech_stopped_at is not None:
                        latency_ms = (time.perf_counter() - self._speech_stopped_at) * 1000
                        logger.info("Response latency: %.0fms", latency_ms)
                        self._speech_stopped_at = None
                    yield AudioOutput(audio=base64_pcm16_to_float32(event.delta))

                case "response.output_audio_transcript.delta":
                    yield TextOutput(text=event.delta)

                case "response.function_call_arguments.done":
                    logger.debug("Function call: %s (call_id=%s)", event.name, event.call_id)
                    yield FunctionCallOutput(
                        name=event.name,
                        arguments=event.arguments,
                        call_id=event.call_id,
                    )

                case "response.done":
                    logger.debug("Response complete")
                    if stop_on_done:
                        break

                case "error":
                    logger.error("Realtime API error: %s", event.error)
                    raise OpenAIRealtimeError(f"Realtime API error: {event.error}")

                case _:
                    pass

    @override
    async def commit_audio(self) -> None:
        if self._connection is None:
            raise RuntimeError("Not connected")
        await self._connection.input_audio_buffer.commit()

    @override
    async def append_audio(self, audio: npt.NDArray[np.float32]) -> None:
        if self._connection is None:
            raise RuntimeError("Not connected")

        b64_audio = float32_to_base64_pcm16(audio)
        await self._connection.input_audio_buffer.append(audio=b64_audio)
