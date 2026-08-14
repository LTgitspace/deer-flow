"""Vision bridge: route images to a vision-capable model for text-only models.

When the main model does not support vision (e.g. DeepSeek V4 Flash), the
``view_image`` tool result (base64) cannot be consumed by the model. This
middleware intercepts completed ``view_image`` tool calls and instead:

1. Reads the image from disk
2. Sends it to a configured vision model (e.g. gemini-3.6-flash)
3. Gets a text description back
4. Injects the TEXT description as a hidden HumanMessage

The main model receives only the text description — no base64 payload, no
API format mismatch, no hallucination.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

logger = logging.getLogger(__name__)

_MAX_IMAGE_BYTES = 20 * 1024 * 1024
_VISION_BRIDGE_MESSAGE_ID_PREFIX = "vision-bridge:"
_VISION_BRIDGE_MARKER_KEY = "deerflow_vision_bridge"


class VisionBridgeMiddleware(AgentMiddleware[AgentState]):
    """Routes images to a vision model when the main model is text-only.

    Requires config:
      vision_bridge:
        enabled: true
        vision_model: gemini-3.6-flash   # any model name in config.yaml models
        prompt: "Describe this image in detail..."

    The middleware is only active when the main model does NOT support vision
    (supports_vision: false). When the main model supports vision, the normal
    ViewImageMiddleware handles base64 injection instead.
    """

    def __init__(self, vision_model: str, prompt: str | None = None) -> None:
        super().__init__()
        self._vision_model = vision_model
        self._prompt = prompt or (
            "Describe this image in detail for an AI assistant that cannot see images. "
            "Include: what is shown, colors, text, layout, objects, people, actions, "
            "and any details that would matter for answering a user's question."
        )

    # ── Detection helpers (mirror ViewImageMiddleware) ──

    @staticmethod
    def _get_last_assistant_message(messages: list) -> AIMessage | None:
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                return msg
        return None

    @staticmethod
    def _has_view_image_tool(message: AIMessage) -> bool:
        if not getattr(message, "tool_calls", None):
            return False
        return any(tc.get("name") == "view_image" for tc in message.tool_calls)

    @staticmethod
    def _all_tools_completed(messages: list, assistant_msg: AIMessage) -> bool:
        tool_call_ids = {tc.get("id") for tc in assistant_msg.tool_calls if tc.get("id")}
        try:
            assistant_idx = messages.index(assistant_msg)
        except ValueError:
            return False
        completed_ids = {
            msg.tool_call_id
            for msg in messages[assistant_idx + 1 :]
            if isinstance(msg, ToolMessage) and msg.tool_call_id
        }
        return tool_call_ids.issubset(completed_ids)

    def _collect_image_paths(self, messages: list, assistant_msg: AIMessage) -> list[str]:
        """Extract the image paths the agent requested via view_image."""
        paths: list[str] = []
        try:
            assistant_idx = messages.index(assistant_msg)
        except ValueError:
            return paths

        for msg in messages[assistant_idx + 1 :]:
            if not isinstance(msg, ToolMessage):
                continue
            # The view_image ToolMessage content is a data URL; the path is
            # in the tool call args. Match by tool_call_id instead.
            pass

        # Get paths from the tool call arguments
        for tc in assistant_msg.tool_calls:
            if tc.get("name") != "view_image":
                continue
            args = tc.get("args") or {}
            if isinstance(args, dict) and args.get("image_path"):
                paths.append(args["image_path"])
        return paths

    # ── Vision model call ──

    def _describe_image(self, image_path: str, thread_data: Any) -> str | None:
        """Send the image to the vision model and return a text description."""
        try:
            from deerflow.sandbox.tools import (
                resolve_and_validate_user_data_path,
                validate_local_tool_path,
            )

            validate_local_tool_path(image_path, thread_data, read_only=True)
            real_path = Path(resolve_and_validate_user_data_path(image_path, thread_data))
        except Exception as e:
            logger.warning("VisionBridge: path resolution failed for %s: %s", image_path, e)
            return None

        if not real_path.exists() or not real_path.is_file():
            logger.warning("VisionBridge: file not found: %s", real_path)
            return None

        size = real_path.stat().st_size
        if size > _MAX_IMAGE_BYTES:
            logger.warning("VisionBridge: image too large (%d bytes)", size)
            return None

        mime_type = mimetypes.guess_type(str(real_path))[0] or "image/jpeg"
        image_bytes = real_path.read_bytes()
        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"

        try:
            from deerflow.config.app_config import get_app_config
            from deerflow.models.factory import create_chat_model

            config = get_app_config()
            vision_llm = create_chat_model(
                self._vision_model,
                thinking_enabled=False,
                app_config=config,
                attach_tracing=False,
            )

            # Build multimodal content for the vision model
            result = vision_llm.invoke(
                [
                    SystemMessage(content="You are an image description service. Return only the description, no preamble."),
                    HumanMessage(
                        content=[
                            {"type": "text", "text": self._prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ]
                    ),
                ]
            )
            description = str(getattr(result, "content", "") or "").strip()
            if description:
                logger.info("VisionBridge: got description for %s (%d chars)", image_path, len(description))
                return description
        except Exception as e:
            logger.error("VisionBridge: vision model call failed for %s: %s", image_path, e)
        return None

    # ── Nudge injection ──

    def _inject_descriptions(self, messages: list, descriptions: list[tuple[str, str]]) -> list:
        """Inject the text descriptions as hidden context for the main model."""
        if not descriptions:
            return messages

        content_parts = [
            "[SYSTEM: Image descriptions from the vision bridge. "
            "You cannot see images directly, but these descriptions were generated "
            "by a vision-capable model. Use them to answer the user's question.]"
        ]
        for path, desc in descriptions:
            content_parts.append(f"\n--- Image: {path} ---\n{desc}")

        bridge_msg = HumanMessage(
            content="\n".join(content_parts),
            additional_kwargs={
                "hide_from_ui": True,
                _VISION_BRIDGE_MARKER_KEY: True,
            },
        )

        patched = list(messages)
        insert_at = len(patched)
        for i, msg in enumerate(patched):
            if isinstance(msg, HumanMessage) and not msg.additional_kwargs.get("hide_from_ui"):
                insert_at = i
                break
        patched.insert(insert_at, bridge_msg)
        return patched

    # ── Lifecycle hooks ──

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Any,
    ) -> ModelCallResult:
        messages = list(request.messages)
        state = request.state or {}

        last_ai = self._get_last_assistant_message(messages)
        if last_ai is None or not self._has_view_image_tool(last_ai):
            return handler(request)

        if not self._all_tools_completed(messages, last_ai):
            return handler(request)

        image_paths = self._collect_image_paths(messages, last_ai)
        if not image_paths:
            return handler(request)

        thread_data = state.get("thread_data")
        descriptions: list[tuple[str, str]] = []
        for path in image_paths:
            desc = self._describe_image(path, thread_data)
            if desc:
                descriptions.append((path, desc))

        if descriptions:
            patched = self._inject_descriptions(messages, descriptions)
            request = request.override(messages=patched)

        return handler(request)

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Any,
    ) -> ModelCallResult:
        messages = list(request.messages)
        state = request.state or {}

        last_ai = self._get_last_assistant_message(messages)
        if last_ai is None or not self._has_view_image_tool(last_ai):
            return await handler(request)

        if not self._all_tools_completed(messages, last_ai):
            return await handler(request)

        image_paths = self._collect_image_paths(messages, last_ai)
        if not image_paths:
            return await handler(request)

        thread_data = state.get("thread_data")
        descriptions: list[tuple[str, str]] = []
        for path in image_paths:
            desc = self._describe_image(path, thread_data)
            if desc:
                descriptions.append((path, desc))

        if descriptions:
            patched = self._inject_descriptions(messages, descriptions)
            request = request.override(messages=patched)

        return await handler(request)
