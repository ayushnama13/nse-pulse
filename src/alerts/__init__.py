"""Alert engine.

Two layers:

  * Sinks: send a message to a channel (telegram / email / discord / webhook).
  * Triggers: classes that check current state vs a rule and yield Alert objects.

A rule lives in the `alert_rules` table; one rule has one trigger_type and a
JSON payload. The runner walks active rules, fires each one through the
configured sinks, respects cooldown, and logs to `alert_events`.

Run via:
    python -m src.alerts.runner            # one pass
    python -m src.alerts.runner --watch    # loop every 60s
"""
from .types import Alert, Trigger  # noqa: F401
from .sinks import dispatch, available_sinks  # noqa: F401
from .runner import run_once, add_rule, list_rules, delete_rule  # noqa: F401
