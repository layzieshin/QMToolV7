from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    name: str
    occurred_at_utc: str
    correlation_id: str
    causation_id: str | None
    actor_user_id: str | None
    module_id: str
    payload: dict[str, Any]
    schema_version: int = 1

    @classmethod
    def create(
        cls,
        name: str,
        module_id: str,
        payload: dict[str, Any],
        actor_user_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> "EventEnvelope":
        return cls(
            event_id=str(uuid4()),
            name=name,
            occurred_at_utc=datetime.now(timezone.utc).isoformat(),
            correlation_id=correlation_id or str(uuid4()),
            causation_id=causation_id,
            actor_user_id=actor_user_id,
            module_id=module_id,
            payload=payload,
        )

