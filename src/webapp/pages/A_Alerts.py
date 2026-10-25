"""Alert rules: configure triggers + sinks, fire on demand, view history."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import streamlit as st
from sqlalchemy import select

from src.alerts import runner as alert_runner, sinks as alert_sinks
from src.alerts.triggers import REGISTRY as TRIGGER_REGISTRY
from src.storage.database import session_scope
from src.storage.models import AlertEvent


st.set_page_config(page_title="Alerts", layout="wide")
st.title("Alerts")

st.subheader("Add / update rule")
with st.form("add_rule"):
    name = st.text_input("Name", value="")
    trigger_type = st.selectbox("Trigger", options=list(TRIGGER_REGISTRY))
    sinks = st.multiselect("Sinks", options=alert_sinks.available_sinks(),
                            default=["log"])
    cooldown = st.number_input("Cooldown (minutes)", min_value=0, value=60)
    payload_str = st.text_area("Payload (JSON)",
                                value='{"expression": "rs_rating >= 90"}',
                                height=120,
                                help="See src/alerts/triggers.py for payload schemas.")
    submitted = st.form_submit_button("Save rule")
    if submitted:
        try:
            payload = json.loads(payload_str)
            rid = alert_runner.add_rule(name, trigger_type, payload,
                                         sinks=sinks, cooldown_minutes=int(cooldown))
            st.success(f"Saved rule (id={rid}).")
        except Exception as e:
            st.exception(e)

st.divider()
st.subheader("Active rules")
rules = alert_runner.list_rules()
if not rules:
    st.caption("None yet.")
else:
    st.dataframe(pd.DataFrame(rules), use_container_width=True, hide_index=True)

st.divider()
col1, col2 = st.columns(2)
with col1:
    if st.button("Run one pass now", type="primary"):
        n = alert_runner.run_once()
        st.success(f"Fired {n} alert(s).")
with col2:
    delete_name = st.text_input("Delete rule by name", value="")
    if st.button("Delete") and delete_name:
        alert_runner.delete_rule(delete_name)
        st.warning(f"Deleted '{delete_name}'.")
        st.experimental_rerun()

st.divider()
st.subheader("Recent events")
with session_scope() as s:
    events = pd.read_sql(
        select(AlertEvent).order_by(AlertEvent.fired_at.desc()).limit(50),
        s.connection(),
    )
st.dataframe(events, use_container_width=True, hide_index=True, height=400)
