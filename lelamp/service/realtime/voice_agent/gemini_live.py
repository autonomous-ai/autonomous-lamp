"""Gemini Live voice agent implementation."""

import json
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack
from typing import Any, override

import cv2
import numpy as np
import numpy.typing as npt
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from google.genai.live import AsyncSession
from websockets.exceptions import ConnectionClosed

from lelamp.service.realtime.config import GeminiConfig
from lelamp.service.realtime.exceptions import GeminiLiveError
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
from lelamp.service.realtime.utils import float32_to_pcm16_bytes, pcm16_bytes_to_float32
from lelamp.service.realtime.voice_agent.base import VoiceAgentBase

logger = logging.getLogger(__name__)


class GeminiLiveAgent(VoiceAgentBase):

    def __init__(
        self,
        config: GeminiConfig,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(tools=tools)
        self._config = config
        self._client = genai.Client(api_key=config.api_key)
        self._session: AsyncSession | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._resumption_handle: str | None = None
        self._speech_ended_at: float | None = None
        self._first_audio_received: bool = False

    def _build_config(self) -> types.LiveConnectConfig:
        live_config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self._config.voice.value,
                    )
                )
            ),
            system_instruction=self._config.instructions or "",
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        if self._tools:
            declarations = [
                types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    parameters=tool.get("parameters"),
                )
                for tool in self._tools
            ]
            live_config.tools = [types.Tool(function_declarations=declarations)]

        if self._resumption_handle is not None:
            live_config.session_resumption = types.SessionResumptionConfig(
                handle=self._resumption_handle,
            )

        return live_config

    @override
    async def connect(self) -> None:
        logger.info("Connecting to Gemini Live API (model=%s)", self._config.model)
        self._exit_stack = AsyncExitStack()
        self._session = await self._exit_stack.enter_async_context(
            self._client.aio.live.connect(
                model=self._config.model,
                config=self._build_config(),
            )
        )
        logger.info("Gemini Live session open (voice=%s)", self._config.voice)

    async def reconnect(self) -> None:
        logger.info("Reconnecting with resumption handle")
        await self.disconnect()
        await self.connect()

    @override
    async def disconnect(self) -> None:
        if self._exit_stack is not None:
            logger.info("Disconnecting from Gemini Live API")
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None

    @override
    async def send(self, inputs: list[InputBase]) -> None:
        if self._session is None:
            raise RuntimeError("Not connected")

        for inp in inputs:
            if isinstance(inp, TextInput):
                await self._session.send_client_content(
                    turns=types.Content(
                        parts=[types.Part(text=inp.text)],
                        role="user",
                    ),
                    turn_complete=True,
                )

            elif isinstance(inp, AudioInput):
                pcm_bytes = float32_to_pcm16_bytes(inp.audio)
                await self._session.send_realtime_input(
                    audio=types.Blob(
                        data=pcm_bytes,
                        mime_type=f"audio/pcm;rate={self._config.sample_rate}",
                    )
                )

            elif isinstance(inp, ImageInput):
                _, buf = cv2.imencode(".jpg", inp.image)
                await self._session.send_realtime_input(
                    video=types.Blob(
                        data=buf.tobytes(),
                        mime_type="image/jpeg",
                    )
                )

            elif isinstance(inp, FunctionCallResultInput):
                await self._session.send_tool_response(
                    function_responses=[
                        types.FunctionResponse(
                            id=inp.call_id,
                            response=json.loads(inp.output),
                        )
                    ]
                )

            else:
                raise ValueError(f"Unsupported input type: {type(inp)}")

    @override
    async def receive(
        self, *, stop_on_done: bool = True
    ) -> AsyncGenerator[OutputBase, None]:
        if self._session is None:
            raise RuntimeError("Not connected")

        self._first_audio_received = False

        while True:
            try:
                async for message in self._session.receive():
                    if message.server_content:
                        content = message.server_content

                        if content.model_turn and content.model_turn.parts:
                            for part in content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    if not self._first_audio_received:
                                        self._first_audio_received = True
                                        if self._speech_ended_at is not None:
                                            latency_ms = (time.perf_counter() - self._speech_ended_at) * 1000
                                            logger.info("Response latency: %.0fms", latency_ms)
                                            self._speech_ended_at = None
                                    yield AudioOutput(
                                        audio=pcm16_bytes_to_float32(part.inline_data.data),
                                    )
                                elif part.text:
                                    yield TextOutput(text=part.text)

                        if content.output_transcription and content.output_transcription.text:
                            yield TextOutput(text=content.output_transcription.text)

                        if content.interrupted:
                            logger.debug("Response interrupted")
                            self._first_audio_received = False

                        if content.turn_complete:
                            logger.debug("Turn complete")
                            self._first_audio_received = False
                            if stop_on_done:
                                return

                    elif message.tool_call and message.tool_call.function_calls:
                        for fc in message.tool_call.function_calls:
                            logger.debug("Function call: %s (call_id=%s)", fc.name, fc.id)
                            yield FunctionCallOutput(
                                name=fc.name or "",
                                arguments=json.dumps(fc.args) if fc.args else "{}",
                                call_id=fc.id or "",
                            )

                    if message.session_resumption_update:
                        update = message.session_resumption_update
                        if update.new_handle:
                            self._resumption_handle = update.new_handle

                    if message.go_away:
                        logger.warning("Server go_away (time_left=%s), reconnecting...", message.go_away.time_left)
                        await self.reconnect()
                        break

            except (ConnectionClosed, genai_errors.APIError) as e:
                logger.warning("Connection lost (%s), reconnecting...", e)
                await self.reconnect()
                continue

    @override
    async def commit_audio(self) -> None:
        # Gemini processes audio incrementally — no explicit commit needed.
        pass

    @override
    async def append_audio(self, audio: npt.NDArray[np.float32]) -> None:
        if self._session is None:
            raise RuntimeError("Not connected")

        self._speech_ended_at = time.perf_counter()
        pcm_bytes = float32_to_pcm16_bytes(audio)
        await self._session.send_realtime_input(
            audio=types.Blob(
                data=pcm_bytes,
                mime_type=f"audio/pcm;rate={self._config.sample_rate}",
            )
        )
