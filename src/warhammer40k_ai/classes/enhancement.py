from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, Tuple

from warhammer40k_ai.classes.enhancement_effects import (
    EnhancementEffectSpec,
    apply_enhancement_effects,
    parse_enhancement_effects,
)


@dataclass(slots=True)
class Enhancement:
    """
    Rules/metadata container for a Detachment Enhancement (10e).

    Current engine usage:
    - Stored on a Character unit (`Unit.enhancement`)
    - Included in points cost (`Unit.get_unit_cost()`)
    - Displayed in UI panels

    Important: enhancement *rules effects* are not generally executed by the engine yet.
    """

    id: str
    name: str
    faction_id: str
    detachment: str
    detachment_id: str = ""
    points: int = 0
    legend: str = ""
    description: str = ""
    eligible_keywords: Set[str] = field(default_factory=set)
    _effects: Tuple[EnhancementEffectSpec, ...] = field(default_factory=tuple, repr=False)

    @classmethod
    def from_waha_dict(cls, data: dict) -> "Enhancement":
        # Wahapedia enhancements do not provide a structured eligibility keyword list.
        # We keep `eligible_keywords` empty to avoid enforcing incorrect restrictions.
        return cls(
            id=str(data.get("id", "") or ""),
            name=str(data.get("name", "") or ""),
            faction_id=str(data.get("faction_id", "") or ""),
            detachment=str(data.get("detachment", "") or ""),
            detachment_id=str(data.get("detachment_id", "") or ""),
            points=int(data.get("cost", 0) or 0),
            legend=str(data.get("legend", "") or ""),
            description=str(data.get("description", "") or ""),
            eligible_keywords=set(),
            _effects=tuple(parse_enhancement_effects(str(data.get("description", "") or ""))),
        )

    def get_effects(self) -> Tuple[EnhancementEffectSpec, ...]:
        if self._effects:
            return self._effects
        return tuple(parse_enhancement_effects(self.description))

    def apply_to_unit(self, unit) -> None:
        """
        Apply supported enhancement effects to the bearer unit.

        This is intentionally narrow/safe: only a few common patterns are supported,
        and everything else remains "Partial" support.
        """
        try:
            apply_enhancement_effects(unit, list(self.get_effects()))
        except Exception:
            # Never hard-fail list loading / army parsing due to a rules parsing miss.
            pass

    def __str__(self) -> str:
        return f"{self.name} ({self.points}pts) [{self.faction_id} / {self.detachment}]\n{self.description}"
