from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Tuple

from .context import RulesContext


@dataclass
class RuleProvider:
    name: str
    subscriptions: List[Tuple[str, str]] = field(default_factory=list)
    predicate: Callable[[Iterable[RulesContext], object], bool] | None = None
    group: str | None = None
    register_fn: Callable[[object, object, str], bool] | None = None
    unregister_fn: Callable[[object, object, str], None] | None = None

    def is_applicable(self, contexts: Iterable[RulesContext], game: object) -> bool:
        if self.predicate is None:
            return True
        try:
            return bool(self.predicate(contexts, game))
        except Exception:
            return False

    def register(self, game: object, event_system: object) -> bool:
        group_name = self.group or f"rule:{self.name}"
        registered = False
        if self.register_fn is not None:
            try:
                registered = bool(self.register_fn(game, event_system, group_name)) or registered
            except Exception:
                return registered
        if event_system is None:
            return registered
        for event_name, handler_name in list(self.subscriptions or []):
            try:
                handler = getattr(game, handler_name, None)
            except Exception:
                handler = None
            if not callable(handler):
                continue
            try:
                event_system.subscribe(event_name, handler, group=group_name)
                registered = True
            except Exception:
                continue
        return registered

    def unregister(self, game: object, event_system: object) -> None:
        group_name = self.group or f"rule:{self.name}"
        if self.unregister_fn is not None:
            try:
                self.unregister_fn(game, event_system, group_name)
            except Exception:
                pass
        if event_system is None:
            return
        try:
            if hasattr(event_system, "unsubscribe_group"):
                event_system.unsubscribe_group(group_name)
            elif hasattr(event_system, "disable_group"):
                event_system.disable_group(group_name)
        except Exception:
            pass


class RuleRegistry:
    def __init__(self, providers: Iterable[RuleProvider] | None = None):
        self.providers: List[RuleProvider] = list(providers or [])
        self._applied: set[str] = set()

    def register(self, provider: RuleProvider) -> None:
        if provider is None:
            return
        self.providers.append(provider)

    def apply(self, game: object) -> None:
        try:
            players = list(getattr(game, "players", []) or [])
        except Exception:
            players = []
        contexts = [RulesContext.from_player(p) for p in players]
        event_system = getattr(game, "event_system", None)
        for provider in self.providers:
            if provider is None:
                continue
            group_name = provider.group or f"rule:{provider.name}"
            applicable = provider.is_applicable(contexts, game)
            if applicable:
                if provider.name not in self._applied:
                    try:
                        registered = provider.register(game, event_system)
                        if registered:
                            self._applied.add(provider.name)
                    except Exception:
                        continue
                try:
                    if event_system is not None and hasattr(event_system, "enable_group"):
                        event_system.enable_group(group_name)
                except Exception:
                    pass
            else:
                if provider.name in self._applied:
                    try:
                        provider.unregister(game, event_system)
                    except Exception:
                        pass
                    self._applied.discard(provider.name)
