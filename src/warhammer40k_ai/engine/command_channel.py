from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol


class CommandChannel(Protocol):
    async def send(self, target_id: str, message: Any) -> None:
        ...

    async def broadcast(self, message: Any) -> None:
        ...


class InProcessCommandChannel:
    """In-process pub/sub transport for local authoritative runtimes."""

    def __init__(self) -> None:
        self._subscribers: dict[str, Callable[[Any], Awaitable[None] | None]] = {}

    def subscribe(self, subscriber_id: str, handler: Callable[[Any], Awaitable[None] | None]) -> None:
        key = str(subscriber_id or "").strip()
        if not key:
            raise ValueError("subscriber_id is required.")
        if key in self._subscribers:
            raise ValueError(f"Duplicate subscriber_id: {key}")
        self._subscribers[key] = handler

    def unsubscribe(self, subscriber_id: str) -> None:
        self._subscribers.pop(str(subscriber_id or ""), None)

    async def send(self, target_id: str, message: Any) -> None:
        key = str(target_id or "").strip()
        handler = self._subscribers.get(key)
        if handler is None:
            raise KeyError(f"Unknown subscriber: {key}")
        result = handler(message)
        if result is not None:
            await result

    async def broadcast(self, message: Any) -> None:
        for handler in list(self._subscribers.values()):
            result = handler(message)
            if result is not None:
                await result


class NetworkCommandChannel:
    """Transport-backed command channel adapter for websocket network runtime."""

    def __init__(self, transport_server: Any) -> None:
        self._transport = transport_server

    async def send(self, target_id: str, message: Any) -> None:
        await self._transport.send(target_id, message)

    async def broadcast(self, message: Any) -> None:
        await self._transport.broadcast(message)
