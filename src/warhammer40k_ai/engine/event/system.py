from typing import Callable, Iterable
import logging
logger = logging.getLogger(__name__)


class EventSystem:
    def __init__(self):
        self.subscribers = {}
        self._group_enabled = {}

    def subscribe(self, event_name: str, callback: Callable, group: str | None = None):
        grp = group or "default"
        self.subscribers.setdefault(event_name, []).append((callback, grp))
        self._group_enabled.setdefault(grp, True)

    def subscribe_group(self, group: str, event_name: str, callback: Callable) -> None:
        self.subscribe(event_name, callback, group=group)

    def unsubscribe(self, event_name: str, callback: Callable | None = None, group: str | None = None) -> None:
        if event_name not in self.subscribers:
            return
        remaining = []
        for cb, grp in self.subscribers.get(event_name, []):
            if callback is not None and cb is not callback:
                remaining.append((cb, grp))
                continue
            if group is not None and grp != group:
                remaining.append((cb, grp))
                continue
        self.subscribers[event_name] = remaining

    def unsubscribe_group(self, group: str) -> None:
        if not group:
            return
        for event_name in list(self.subscribers.keys()):
            items = self.subscribers.get(event_name, [])
            self.subscribers[event_name] = [(cb, grp) for cb, grp in items if grp != group]
        self._group_enabled.pop(group, None)

    def set_group_enabled(self, group: str, enabled: bool) -> None:
        self._group_enabled[group] = bool(enabled)

    def enable_group(self, group: str) -> None:
        self.set_group_enabled(group, True)

    def disable_group(self, group: str) -> None:
        self.set_group_enabled(group, False)

    def is_group_enabled(self, group: str) -> bool:
        return bool(self._group_enabled.get(group, True))

    def publish(self, event_name: str, *, _target_groups: Iterable[str] | None = None, **kwargs):
        try:
            logger.info(f"Event publish: {event_name} -> {kwargs}")
        except Exception:
            pass
        lifecycle = getattr(self, "lifecycle", None)
        if lifecycle is not None:
            try:
                if not lifecycle.should_dispatch(event_name, kwargs):
                    return
            except Exception:
                pass
        target_groups = set(_target_groups) if _target_groups is not None else None
        for callback, group in self.subscribers.get(event_name, []):
            if target_groups is not None and group not in target_groups:
                continue
            if not self.is_group_enabled(group):
                continue
            try:
                callback(**kwargs)
            except Exception as e:
                try:
                    logger.exception(f"Event callback error for '{event_name}': {e}")
                except Exception:
                    pass
