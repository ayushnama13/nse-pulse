"""Alert engine runner — evaluates active rules, dispatches, logs results."""
from __future__ import annotations

import argparse
import json
import time as _time
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import delete as sql_delete, select

from ..storage.database import init_db, session_scope
from ..storage.models import AlertEvent, AlertRule
from .sinks import dispatch
from .triggers import REGISTRY


def _within_cooldown(rule: AlertRule) -> bool:
    if rule.last_fired_at is None:
        return False
    return datetime.utcnow() < rule.last_fired_at + timedelta(minutes=rule.cooldown_minutes)


def run_once() -> int:
    """Walk active rules, dispatch any that fire. Returns number of alerts sent."""
    init_db()
    fired = 0
    with session_scope() as s:
        rules = s.execute(
            select(AlertRule).where(AlertRule.enabled == 1)
        ).scalars().all()

    for rule in rules:
        if _within_cooldown(rule):
            continue
        fn = REGISTRY.get(rule.trigger_type)
        if fn is None:
            logger.warning("Unknown trigger type: {}", rule.trigger_type)
            continue
        try:
            payload = json.loads(rule.payload or "{}")
        except json.JSONDecodeError as e:
            logger.warning("Bad payload JSON for rule {}: {}", rule.name, e)
            continue
        sinks = [s.strip() for s in (rule.sinks or "log").split(",") if s.strip()]
        try:
            alerts = fn(rule.id, rule.name, payload, sinks)
        except Exception as e:
            logger.exception("Trigger {} raised: {}", rule.name, e)
            continue
        for alert in alerts:
            ok, err = dispatch(alert.sinks, alert.subject, alert.body)
            with session_scope() as s:
                s.add(AlertEvent(
                    rule_id=alert.rule_id, fired_at=alert.fired_at,
                    subject=alert.subject, body=alert.body[:4000],
                    sinks=",".join(alert.sinks), success=int(ok), error=err,
                ))
                # Touch cooldown.
                s.execute(
                    AlertRule.__table__.update()
                    .where(AlertRule.id == rule.id)
                    .values(last_fired_at=datetime.utcnow())
                )
            fired += 1
    if fired:
        logger.info("Alert runner: fired {} alert(s)", fired)
    return fired


# ---- Rule management ----

def add_rule(name: str, trigger_type: str, payload: dict, *,
             sinks: list[str] | None = None, cooldown_minutes: int = 60) -> int:
    if trigger_type not in REGISTRY:
        raise ValueError(f"unknown trigger_type: {trigger_type}")
    sinks_str = ",".join(sinks or ["log"])
    with session_scope() as s:
        existing = s.execute(select(AlertRule).where(AlertRule.name == name)).scalar_one_or_none()
        if existing:
            existing.trigger_type = trigger_type
            existing.payload = json.dumps(payload)
            existing.sinks = sinks_str
            existing.cooldown_minutes = cooldown_minutes
            existing.enabled = 1
            s.flush()
            return existing.id
        rule = AlertRule(name=name, trigger_type=trigger_type,
                         payload=json.dumps(payload), sinks=sinks_str,
                         cooldown_minutes=cooldown_minutes, enabled=1)
        s.add(rule)
        s.flush()
        return rule.id


def list_rules() -> list[dict]:
    with session_scope() as s:
        rows = s.execute(select(AlertRule).order_by(AlertRule.name)).scalars().all()
    return [
        {"id": r.id, "name": r.name, "trigger_type": r.trigger_type,
         "payload": r.payload, "sinks": r.sinks, "enabled": bool(r.enabled),
         "cooldown_minutes": r.cooldown_minutes, "last_fired_at": r.last_fired_at}
        for r in rows
    ]


def delete_rule(name: str) -> None:
    with session_scope() as s:
        s.execute(sql_delete(AlertRule).where(AlertRule.name == name))


def cli() -> None:
    p = argparse.ArgumentParser(description="NSE Pulse alert runner")
    p.add_argument("--watch", action="store_true", help="Loop forever, polling every --interval")
    p.add_argument("--interval", type=int, default=60, help="Seconds between passes in --watch")
    p.add_argument("--list", action="store_true", help="Print active rules and exit")
    args = p.parse_args()

    init_db()

    if args.list:
        for r in list_rules():
            print(r)
        return

    if args.watch:
        logger.info("Alert runner watching every {}s. Ctrl-C to stop.", args.interval)
        while True:
            try:
                run_once()
            except Exception as e:
                logger.exception("Alert runner pass failed: {}", e)
            _time.sleep(args.interval)
    else:
        n = run_once()
        print(f"Fired {n} alert(s).")


if __name__ == "__main__":
    cli()
