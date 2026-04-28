"""Lightweight in-process event bus for simulation monitor updates."""

import asyncio
from datetime import datetime
from typing import Any


class SimulationEventBus:
    """Broadcasts coarse simulation lifecycle events to connected SSE clients."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    async def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        event = {
            "type": event_type,
            "payload": payload or {},
            "timestamp": datetime.now().isoformat(),
        }
        stale_subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                stale_subscribers.append(queue)

        for queue in stale_subscribers:
            self._subscribers.discard(queue)

    async def subscribe(self):
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=32)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)


simulation_event_bus = SimulationEventBus()
