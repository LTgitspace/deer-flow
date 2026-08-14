"""Configuration for the metacognition (think-first) middleware."""

from pydantic import BaseModel, Field


class MetacognitionConfig(BaseModel):
    """Configuration for deterministic think-first enforcement."""

    enabled: bool = Field(
        default=True,
        description="Whether the metacognition middleware injects think-first nudges",
    )
    min_complexity_chars: int = Field(
        default=60,
        ge=10,
        le=2000,
        description="User message length (chars) at or above which a prompt is classified complex",
    )
    triggers: list[str] = Field(
        default_factory=lambda: [
            "analyze", "design", "architecture", "compare", "explain",
            "why", "plan", "debug", "optimize", "prove", "evaluate",
            "tradeoff", "refactor", "implement", "build",
        ],
        description="Vocabulary that marks a prompt as reasoning-requiring (with a minimum length)",
    )
    min_trigger_chars: int = Field(
        default=30,
        ge=10,
        le=2000,
        description="Minimum message length for trigger-word classification",
    )
    min_question_chars: int = Field(
        default=20,
        ge=5,
        le=2000,
        description="Minimum message length for question-mark classification",
    )


# Global configuration instance
_metacognition_config: MetacognitionConfig = MetacognitionConfig()


def get_metacognition_config() -> MetacognitionConfig:
    """Get the current metacognition configuration."""
    return _metacognition_config


def set_metacognition_config(config: MetacognitionConfig) -> None:
    """Set the metacognition configuration."""
    global _metacognition_config
    _metacognition_config = config


def load_metacognition_config_from_dict(config_dict: dict) -> None:
    """Load metacognition configuration from a dictionary."""
    global _metacognition_config
    _metacognition_config = MetacognitionConfig(**config_dict)


def reset_metacognition_config() -> None:
    """Restore the pristine MetacognitionConfig() default.

    Public API so tests can return the global singleton to its clean state,
    mirroring reset_title_config().
    """
    global _metacognition_config
    _metacognition_config = MetacognitionConfig()
