"""Shared types for the alert engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class Alert:
    rule_id: int
    rule_name: str
    subject: str
    body: str
    sinks: list[str]
    fired_at: datetime = field(default_factory=datetime.utcnow)


class Trigger(Protocol):
    """All triggers implement evaluate(payload) -> list[Alert pieces]."""
    name: str

    def evaluate(self, rule_id: int, rule_name: str, payload: dict, sinks: list[str]
                 ) -> list[Alert]: ...
