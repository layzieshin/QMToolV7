"""Incident ID generation: YYYYMMDD_NNNN based on report date."""
from __future__ import annotations

from datetime import datetime


def report_date_key(reported_at: datetime) -> str:
    return reported_at.strftime("%Y%m%d")


def format_incident_id(reported_at: datetime, seq: int) -> str:
    return f"{report_date_key(reported_at)}_{seq:04d}"
