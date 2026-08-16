"""Configuration for the token forensics middleware."""

from pydantic import BaseModel, Field


class TokenForensicsConfig(BaseModel):
    """Configuration for per-turn token decomposition logging."""

    enabled: bool = Field(
        default=True,
        description="Whether the token forensics middleware logs per-turn decompositions",
    )
    warn_input_tokens: int = Field(
        default=15000,
        ge=100,
        description="Input token count at or above which the decomposition logs at WARNING level",
    )


# Global configuration instance
_token_forensics_config: TokenForensicsConfig = TokenForensicsConfig()


def get_token_forensics_config() -> TokenForensicsConfig:
    """Get the current token forensics configuration."""
    return _token_forensics_config


def set_token_forensics_config(config: TokenForensicsConfig) -> None:
    """Set the token forensics configuration."""
    global _token_forensics_config
    _token_forensics_config = config


def load_token_forensics_config_from_dict(config_dict: dict) -> None:
    """Load token forensics configuration from a dictionary."""
    global _token_forensics_config
    _token_forensics_config = TokenForensicsConfig(**config_dict)


def reset_token_forensics_config() -> None:
    """Restore the pristine TokenForensicsConfig() default."""
    global _token_forensics_config
    _token_forensics_config = TokenForensicsConfig()
