# Event system for the game and for agents to use Stratagems

from typing import Callable

class EventSystem:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_name: str, callback: Callable):
        self.subscribers.setdefault(event_name, []).append(callback)

    def publish(self, event_name: str, **kwargs):
        try:
            print(f"🔔 Event publish: {event_name} -> {kwargs}")
        except Exception:
            pass
        for callback in self.subscribers.get(event_name, []):
            try:
                callback(**kwargs)
            except Exception as e:
                try:
                    print(f"⚠️ Event callback error for '{event_name}': {e}")
                except Exception:
                    pass