"""Vision bridge configuration.

Routes image analysis to a vision-capable model when the main model
does not support vision (supports_vision: false).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VisionBridgeConfig(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Route images to a vision model when the main model is text-only.",
    )
    vision_model: str = Field(
        default="gemini-3.6-flash",
        description="Name of a model in config.yaml models that supports vision.",
    )
    prompt: str | None = Field(
        default=None,
        description="Optional custom prompt for the vision model. Defaults to a detailed description prompt.",
    )
