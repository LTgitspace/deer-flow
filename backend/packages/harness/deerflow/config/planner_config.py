"""Configuration for the planner (plan-first) middleware."""

from pydantic import BaseModel, Field


class PlannerConfig(BaseModel):
    """Configuration for deterministic plan-first enforcement."""

    enabled: bool = Field(
        default=True,
        description="Whether the planner middleware injects plan-first nudges",
    )
    min_chars: int = Field(
        default=40,
        ge=10,
        le=2000,
        description="Minimum user message length for multi-step classification",
    )
    action_verbs: list[str] = Field(
        default_factory=lambda: [
            "add", "create", "implement", "build", "fix", "refactor",
            "update", "remove", "migrate", "write", "setup", "integrate",
            "replace", "convert",
        ],
        description="Action vocabulary; two distinct verbs in one message marks multi-step work",
    )
    min_plan_steps: int = Field(
        default=2,
        ge=2,
        le=10,
        description="Numbered lines required for a written plan to count",
    )
    file_extensions: list[str] = Field(
        default_factory=lambda: [
            "py", "ts", "tsx", "js", "jsx", "md", "yaml", "yml", "json",
            "rs", "go", "java", "cpp", "c", "h", "css", "html", "sql",
        ],
        description="File extensions whose repeated mention marks multi-step work",
    )


# Global configuration instance
_planner_config: PlannerConfig = PlannerConfig()


def get_planner_config() -> PlannerConfig:
    """Get the current planner configuration."""
    return _planner_config


def set_planner_config(config: PlannerConfig) -> None:
    """Set the planner configuration."""
    global _planner_config
    _planner_config = config


def load_planner_config_from_dict(config_dict: dict) -> None:
    """Load planner configuration from a dictionary."""
    global _planner_config
    _planner_config = PlannerConfig(**config_dict)


def reset_planner_config() -> None:
    """Restore the pristine PlannerConfig() default."""
    global _planner_config
    _planner_config = PlannerConfig()
