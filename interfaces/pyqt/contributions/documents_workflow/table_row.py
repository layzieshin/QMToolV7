"""Workflow table row wrapper (documents workflow UI)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowTableRow:
    state: object
    active_version: int | None

    def __getattr__(self, item: str) -> object:
        return getattr(self.state, item)
