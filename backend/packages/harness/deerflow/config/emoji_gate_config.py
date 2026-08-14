"""Configuration for the emoji gate middleware."""

from pydantic import BaseModel, Field


class EmojiGateConfig(BaseModel):
    """Configuration for deterministic emoji-free technical output enforcement."""

    enabled: bool = Field(
        default=True,
        description="Whether the emoji gate middleware injects correction nudges",
    )
    allow_in_chat: bool = Field(
        default=True,
        description="True: allow emojis in casual visible chat; only code blocks, file writes, and configs are gated. False: gate everything.",
    )


# Global configuration instance
_emoji_gate_config: EmojiGateConfig = EmojiGateConfig()


def get_emoji_gate_config() -> EmojiGateConfig:
    """Get the current emoji gate configuration."""
    return _emoji_gate_config


def set_emoji_gate_config(config: EmojiGateConfig) -> None:
    """Set the emoji gate configuration."""
    global _emoji_gate_config
    _emoji_gate_config = config


def load_emoji_gate_config_from_dict(config_dict: dict) -> None:
    """Load emoji gate configuration from a dictionary."""
    global _emoji_gate_config
    _emoji_gate_config = EmojiGateConfig(**config_dict)


def reset_emoji_gate_config() -> None:
    """Restore the pristine EmojiGateConfig() default."""
    global _emoji_gate_config
    _emoji_gate_config = EmojiGateConfig()
