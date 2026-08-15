"""Config model, discovery, and loading for autodocstrings.

The config file (default name: ``autodocstrings.config.json``) is optional —
every field has a default, so a project with no config file at all still
works, using the defaults below.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

CONFIG_FILENAME = "autodocstrings.config.json"

DEFAULT_INCLUDE = ["**/*"]
DEFAULT_EXCLUDE = [
    "**/node_modules/**",
    "**/.venv/**",
    "**/venv/**",
    "**/__pycache__/**",
    "**/dist/**",
    "**/build/**",
    "**/.git/**",
]

DEFAULT_LANGUAGES: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "typescript",
    ".jsx": "typescript",
    ".mjs": "typescript",
}

PythonConvention = Literal["google", "numpy", "sphinx"]
TypeScriptConvention = Literal["jsdoc", "tsdoc"]
Verbosity = Literal["minimal", "standard", "detailed"]
HookMode = Literal["off", "warn", "block"]
ParamsPolicy = Literal["when_non_obvious", "always", "never"]


class ConventionsConfig(BaseModel):
    """Docstring convention to use per language."""

    model_config = ConfigDict(extra="forbid")

    python: PythonConvention = "google"
    typescript: TypeScriptConvention = "tsdoc"


class NoisePolicyConfig(BaseModel):
    """Knobs controlling how much the agent is allowed to write."""

    model_config = ConfigDict(extra="forbid")

    document_trivial: bool = False
    params: ParamsPolicy = "when_non_obvious"
    include_examples: bool = False


class HookConfig(BaseModel):
    """Git hook behavior."""

    model_config = ConfigDict(extra="forbid")

    mode: HookMode = "warn"
    block_on: list[Literal["stale", "never_started"]] = Field(
        default_factory=lambda: ["stale", "never_started"]
    )


class InitConfig(BaseModel):
    """Behavior of `autodoc init`'s first scan."""

    model_config = ConfigDict(extra="forbid")

    trust_existing: bool = True


class Config(BaseModel):
    """Top-level autodocstrings configuration."""

    model_config = ConfigDict(extra="forbid")

    include: list[str] = Field(default_factory=lambda: list(DEFAULT_INCLUDE))
    exclude: list[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUDE))
    languages: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_LANGUAGES))
    conventions: ConventionsConfig = Field(default_factory=ConventionsConfig)
    verbosity: Verbosity = "standard"
    noise_policy: NoisePolicyConfig = Field(default_factory=NoisePolicyConfig)
    hook: HookConfig = Field(default_factory=HookConfig)
    init: InitConfig = Field(default_factory=InitConfig)
    state_file: str = ".autodocstrings/state.json"


class ConfigError(Exception):
    """Raised when a config file fails to parse or validate.

    ``str(error)`` is a human-readable message naming the offending field(s),
    suitable for printing directly to the user.
    """


def find_config(start: Path | None = None, filename: str = CONFIG_FILENAME) -> Path | None:
    """Walk up from `start` (default: CWD) looking for a config file.

    Mirrors how tools like npm find `package.json`: check the current
    directory, then each parent, until the filesystem root.
    """
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    return None


def _format_validation_error(exc: ValidationError, source: Path) -> str:
    lines = [f"Invalid config at {source}:"]
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"]) or "<root>"
        lines.append(f"  - {field}: {error['msg']}")
    return "\n".join(lines)


def load_config(path: Path | None = None) -> Config:
    """Load and validate a config file, or return defaults if none is found.

    Raises `ConfigError` with a message naming the invalid field(s) if the
    file exists but is malformed or fails validation.
    """
    resolved = path if path is not None else find_config()
    if resolved is None:
        return Config()

    try:
        raw_text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Could not read config file at {resolved}: {exc}") from exc

    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in config file at {resolved}: {exc}") from exc

    try:
        return Config.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error(exc, resolved)) from exc


def export_json_schema() -> dict:
    """Return the JSON Schema for `Config`, for `docs/config.schema.json`."""
    return Config.model_json_schema()
