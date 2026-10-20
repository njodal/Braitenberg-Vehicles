"""Helpers shared by the YAML loaders (worlds, vehicle definitions, scenarios).

Every loader validates into dataclasses and fails fast with a ConfigError whose
message names the file and the offending key.
"""

from __future__ import annotations

from pathlib import Path

import yaml


class ConfigError(ValueError):
    """A world, vehicle definition or scenario file is missing, malformed or inconsistent."""


def read_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text())
    except FileNotFoundError as e:
        raise ConfigError(f"{path}: file not found") from e
    except OSError as e:
        raise ConfigError(f"{path}: cannot read file: {e.strerror}") from e
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: invalid YAML: {e}") from e


class Parser:
    """Validation helpers bound to one file, so every error names it."""

    def __init__(self, path: Path):
        self.path = path

    def error(self, key: str, message: str) -> ConfigError:
        return ConfigError(f"{self.path}: {key}: {message}")

    def mapping(self, value, key: str, required: set[str], optional: set[str] = frozenset()) -> dict:
        if not isinstance(value, dict):
            raise self.error(key or "(top level)", "must be a mapping")
        prefix = f"{key}." if key else ""
        for k in value:
            if k not in required | optional:
                raise self.error(prefix + str(k), "unknown key")
        for k in sorted(required):
            if k not in value:
                raise self.error(prefix + k, "missing required key")
        return value

    def items(self, value, key: str, wrapper: str) -> list[tuple[str, dict]]:
        """A list whose items are each wrapped in `- wrapper:`. Returns (item key, body) pairs."""
        if value is None:
            return []
        if not isinstance(value, list):
            raise self.error(key, "must be a list")
        result = []
        for i, item in enumerate(value):
            ikey = f"{key}[{i}]"
            if not (isinstance(item, dict) and len(item) == 1 and wrapper in item):
                raise self.error(ikey, f"each item must be wrapped in '- {wrapper}:'")
            result.append((f"{ikey}.{wrapper}", item[wrapper]))
        return result

    def number(self, value, key: str, positive: bool = False) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise self.error(key, "must be a number")
        if positive and value <= 0:
            raise self.error(key, "must be positive")
        return float(value)

    def integer(self, value, key: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise self.error(key, "must be an integer")
        return value

    def string(self, value, key: str) -> str:
        if not isinstance(value, str):
            raise self.error(key, "must be a string")
        return value

    def pair(self, value, key: str) -> tuple[float, float]:
        if not isinstance(value, list) or len(value) != 2:
            raise self.error(key, "must be a list [x, y]")
        x, y = (self.number(v, key) for v in value)
        return x, y

    def relative_path(self, value, key: str) -> Path:
        """A path relative to this file."""
        return (self.path.parent / self.string(value, key)).resolve()
