import json
from pathlib import Path

import pytest

from autodocstrings.config import (
    Config,
    ConfigError,
    export_json_schema,
    find_config,
    load_config,
)


def test_defaults() -> None:
    config = Config()
    assert config.verbosity == "standard"
    assert config.conventions.python == "google"
    assert config.conventions.typescript == "tsdoc"
    assert config.hook.mode == "warn"
    assert config.init.trust_existing is True
    assert config.state_file == ".autodocstrings/state.json"
    assert ".py" in config.languages


def test_find_config_walks_up_parents(tmp_path: Path) -> None:
    (tmp_path / "autodocstrings.config.json").write_text("{}", encoding="utf-8")
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    found = find_config(start=nested)
    assert found == tmp_path / "autodocstrings.config.json"


def test_find_config_returns_none_when_absent(tmp_path: Path) -> None:
    assert find_config(start=tmp_path) is None


def test_load_config_merges_partial_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "autodocstrings.config.json"
    config_path.write_text(
        json.dumps({"verbosity": "minimal", "conventions": {"python": "numpy"}}),
        encoding="utf-8",
    )
    config = load_config(path=config_path)
    assert config.verbosity == "minimal"
    assert config.conventions.python == "numpy"
    # Untouched fields keep their defaults.
    assert config.conventions.typescript == "tsdoc"
    assert config.hook.mode == "warn"


def test_load_config_no_config_file_anywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config == Config()


def test_invalid_json_raises_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "autodocstrings.config.json"
    config_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid JSON"):
        load_config(path=config_path)


def test_invalid_field_value_names_the_field(tmp_path: Path) -> None:
    config_path = tmp_path / "autodocstrings.config.json"
    config_path.write_text(json.dumps({"verbosity": "extremely-loud"}), encoding="utf-8")
    with pytest.raises(ConfigError) as excinfo:
        load_config(path=config_path)
    assert "verbosity" in str(excinfo.value)


def test_unknown_field_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "autodocstrings.config.json"
    config_path.write_text(json.dumps({"totally_made_up_field": True}), encoding="utf-8")
    with pytest.raises(ConfigError) as excinfo:
        load_config(path=config_path)
    assert "totally_made_up_field" in str(excinfo.value)


def test_json_schema_round_trips_against_model() -> None:
    schema = export_json_schema()
    assert schema["title"] == "Config"
    # Every field on the model should show up as a schema property.
    for field_name in Config.model_fields:
        assert field_name in schema["properties"]
