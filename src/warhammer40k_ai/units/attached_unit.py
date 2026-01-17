from __future__ import annotations

from typing import List, Any


class AttachedUnitView:
    """
    Lightweight proxy that makes an Attached unit (Bodyguard + Leaders) look like a single unit.

    This is intentionally minimal: it exists so UI dialogs (deployment/movement) and coherency checks
    can operate over a combined `.models` list without mutating the underlying Unit objects.
    """

    def __init__(self, root_unit: Any):
        self._root = root_unit

        # Snapshot members at construction time (so indices remain stable through a dialog session)
        members = []
        try:
            members = list(root_unit.get_attached_unit_members())
        except Exception:
            members = [root_unit]
        self._members = [m for m in members if m is not None]

        # Flatten model list
        models: List[Any] = []
        for u in self._members:
            try:
                models.extend(list(getattr(u, "models", []) or []))
            except Exception:
                continue
        self.models = models

    @property
    def root(self) -> Any:
        return self._root

    @property
    def members(self) -> List[Any]:
        return list(self._members)

    @property
    def name(self) -> str:
        try:
            return f"{self._root.name} (Attached)"
        except Exception:
            return "Attached Unit"

    def __getattr__(self, item: str) -> Any:
        # Delegate everything else to the root unit
        return getattr(self._root, item)


