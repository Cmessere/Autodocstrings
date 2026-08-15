"""Resolves the project a CLI invocation is operating on: config, root, state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autodocstrings.config import Config, find_config, load_config
from autodocstrings.state import State, load_state, save_state


@dataclass
class Project:
    root: Path
    """Directory the config file was found in (or CWD, if no config file exists)."""
    config: Config
    config_path: Path | None

    @property
    def state_path(self) -> Path:
        return self.root / self.config.state_file

    def load_state(self) -> State:
        return load_state(self.state_path)

    def save_state(self, state: State) -> None:
        save_state(state, self.state_path)


def load_project(start: Path | None = None) -> Project:
    config_path = find_config(start)
    config = load_config(config_path)
    root = config_path.parent if config_path is not None else (start or Path.cwd())
    return Project(root=root.resolve(), config=config, config_path=config_path)
