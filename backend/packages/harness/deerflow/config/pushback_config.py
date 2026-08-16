"""Configuration for the pushback (informed-consent) middleware."""

from pydantic import BaseModel, Field


class PushbackConfig(BaseModel):
    """Configuration for deterministic decision pushback enforcement.

    When a user directive contradicts a recorded commitment (a prior
    user statement or a memory fact), the agent must state the tradeoff
    before executing. Execution is never blocked — the user's call is
    final; it is simply informed.
    """

    enabled: bool = Field(
        default=True,
        description="Whether the pushback middleware injects tradeoff nudges",
    )
    min_chars: int = Field(
        default=30,
        ge=10,
        le=2000,
        description="Minimum user message length for conflict detection",
    )
    lookback: int = Field(
        default=24,
        ge=4,
        le=100,
        description="How many prior messages to scan for recorded commitments",
    )
    hard_markers: list[str] = Field(
        default_factory=lambda: ["never", "do not", "don't", "avoid", "off the table", "no more", "stop using"],
        description="Commitment phrases that make a contradiction a hard conflict",
    )
    soft_markers: list[str] = Field(
        default_factory=lambda: ["always", "must", "prefer", "keep"],
        description="Commitment phrases that make a contradiction a soft conflict",
    )
    positive_verbs: list[str] = Field(
        default_factory=lambda: [
            "add", "use", "include", "enable", "write", "build", "generate",
            "create", "convert", "install", "import", "put", "do", "apply",
        ],
        description="Directive verbs that oppose a negative commitment",
    )
    negative_verbs: list[str] = Field(
        default_factory=lambda: [
            "remove", "delete", "disable", "skip", "drop", "stop", "ignore",
            "revert", "uninstall", "avoid",
        ],
        description="Directive verbs that oppose a positive commitment",
    )
    tradeoff_markers: list[str] = Field(
        default_factory=lambda: [
            "tradeoff", "trade-off", "risk", "consequence", "downside",
            "be aware", "if we do this", "if you confirm", "note that",
        ],
        description="Phrases in the agent's reply that discharge the pushback obligation",
    )


# Global configuration instance
_pushback_config: PushbackConfig = PushbackConfig()


def get_pushback_config() -> PushbackConfig:
    """Get the current pushback configuration."""
    return _pushback_config


def set_pushback_config(config: PushbackConfig) -> None:
    """Set the pushback configuration."""
    global _pushback_config
    _pushback_config = config


def load_pushback_config_from_dict(config_dict: dict) -> None:
    """Load pushback configuration from a dictionary."""
    global _pushback_config
    _pushback_config = PushbackConfig(**config_dict)


def reset_pushback_config() -> None:
    """Restore the pristine PushbackConfig() default."""
    global _pushback_config
    _pushback_config = PushbackConfig()
