"""Loads YAML config files from `config/`. Single source of truth at runtime."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def get_config() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "config.yaml")


@lru_cache(maxsize=1)
def get_endpoints() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "endpoints.yaml")


@lru_cache(maxsize=1)
def get_holidays() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "holidays.yaml")


def project_root() -> Path:
    return PROJECT_ROOT


def resolve_path(rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()
