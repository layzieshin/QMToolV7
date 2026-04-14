from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .event_envelope import EventEnvelope


Subscriber = Callable[[EventEnvelope], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Subscriber) -> None:
        self._subscribers[event_name].append(handler)

    def publish(self, event: EventEnvelope) -> None:
        for handler in self._subscribers.get(event.name, []):
            handler(event)

