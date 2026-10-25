from __future__ import annotations

from pathlib import Path

import yaml


_ROOT = Path(__file__).resolve().parents[2]


def _load_symbols(config_path: str = "config/symbols.yaml") -> dict:
    return yaml.safe_load((_ROOT / config_path).read_text())


def get_fno_symbols(config_path: str = "config/symbols.yaml") -> list[str]:
    return _load_symbols(config_path).get("fno_symbols", [])


def get_index_list(config_path: str = "config/symbols.yaml") -> list[str]:
    return _load_symbols(config_path).get("index_list", [])


def get_option_chain_indices(config_path: str = "config/symbols.yaml") -> list[str]:
    return _load_symbols(config_path).get("option_chain_indices", [])


def get_watchlist(config_path: str = "config/symbols.yaml") -> list[str]:
    return _load_symbols(config_path).get("watchlist", [])
