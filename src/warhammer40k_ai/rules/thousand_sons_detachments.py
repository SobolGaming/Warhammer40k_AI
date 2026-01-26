from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .detachment_manager import DetachmentManagerBase


@dataclass(frozen=True)
class GrandCovenAbility:
    key: str
    name: str
    summary: str


IMBUED_MANIFESTATION = GrandCovenAbility(
    key="IMBUED_MANIFESTATION",
    name="Imbued Manifestation",
    summary='Add 6" to the Range characteristic of ranged Psychic weapons.',
)
PSYCHIC_MAELSTROM = GrandCovenAbility(
    key="PSYCHIC_MAELSTROM",
    name="Psychic Maelstrom",
    summary="Each time a Psychic weapon attacks, add 1 to the Wound roll.",
)
WRATH_OF_THE_IMMATERIUM = GrandCovenAbility(
    key="WRATH_OF_THE_IMMATERIUM",
    name="Wrath of the Immaterium",
    summary="Psychic weapons gain [Devastating Wounds].",
)

GRAND_COVEN_ABILITIES: tuple[GrandCovenAbility, ...] = (
    IMBUED_MANIFESTATION,
    PSYCHIC_MAELSTROM,
    WRATH_OF_THE_IMMATERIUM,
)
GRAND_COVEN_BY_KEY = {a.key: a for a in GRAND_COVEN_ABILITIES}


class ThousandSonsDetachmentManager(DetachmentManagerBase):
    faction_id = "TS"

    def __init__(self, army=None):
        super().__init__(army)
        self.grand_coven_active_key: Optional[str] = None
        self.grand_coven_active_round: Optional[int] = None
        self.grand_coven_used_keys: list[str] = []

    def is_grand_coven(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Grand Coven")

    def _army_has_grand_coven(self) -> bool:
        return self.is_grand_coven()

    def _is_active_round(self, game=None) -> bool:
        if self.grand_coven_active_round is None:
            return False
        if game is None:
            return True
        try:
            return int(getattr(game, "turn", 0) or 0) == int(self.grand_coven_active_round)
        except Exception:
            return False

    def _model_is_thousand_sons(self, model) -> bool:
        if model is None:
            return False
        try:
            fn = getattr(model, "has_any_keyword", None)
            if callable(fn) and fn("THOUSAND SONS"):
                return True
        except Exception:
            pass
        try:
            unit = getattr(model, "parent_unit", None)
        except Exception:
            unit = None
        return self._unit_has_keyword_or_faction(unit, "THOUSAND SONS", faction_id=self.faction_id)

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        try:
            unit = getattr(model, "parent_unit", None)
        except Exception:
            unit = None
        if unit is None:
            return False
        try:
            return unit.get_parent_army() is self.army
        except Exception:
            return False

    def get_available_grand_coven_abilities(self) -> list[GrandCovenAbility]:
        if not self._army_has_grand_coven():
            return []
        used = {str(k or "").strip().upper() for k in (self.grand_coven_used_keys or []) if str(k or "").strip()}
        return [a for a in GRAND_COVEN_ABILITIES if a.key not in used]

    def can_select_grand_coven(self, *, game=None) -> bool:
        if not self._army_has_grand_coven():
            return False
        if self.grand_coven_active_round is not None and self._is_active_round(game=game) and self.grand_coven_active_key:
            return False
        return bool(self.get_available_grand_coven_abilities())

    def select_grand_coven(self, ability, *, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_grand_coven():
            return False
        key = getattr(ability, "key", ability)
        key = str(key or "").strip().upper()
        if key not in GRAND_COVEN_BY_KEY:
            return False
        used = {str(k or "").strip().upper() for k in (self.grand_coven_used_keys or []) if str(k or "").strip()}
        if key in used:
            return False
        self.grand_coven_active_key = key
        if battle_round is not None:
            try:
                self.grand_coven_active_round = int(battle_round)
            except Exception:
                pass
        self.grand_coven_used_keys.append(key)
        return True

    def get_active_grand_coven(self, *, game=None) -> Optional[GrandCovenAbility]:
        if not self._army_has_grand_coven():
            return None
        if not self.grand_coven_active_key:
            return None
        if not self._is_active_round(game=game):
            return None
        return GRAND_COVEN_BY_KEY.get(self.grand_coven_active_key)

    def _grand_coven_applies(self, model, *, game=None) -> bool:
        if not self._army_has_grand_coven():
            return False
        if not self._is_active_round(game=game):
            return False
        if not self._model_is_thousand_sons(model):
            return False
        if not self._model_in_army(model):
            return False
        return True

    def grand_coven_psychic_range_bonus(self, model, weapon_profile=None, *, game=None) -> int:
        active = self.get_active_grand_coven(game=game)
        if active is None or active.key != IMBUED_MANIFESTATION.key:
            return 0
        if not self._grand_coven_applies(model, game=game):
            return 0
        if weapon_profile is None:
            return 0
        try:
            if not bool(getattr(weapon_profile, "is_psychic", lambda: False)()):
                return 0
        except Exception:
            return 0
        try:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_ranged = bool(parent is not None and getattr(parent, "is_ranged", lambda: False)())
        except Exception:
            is_ranged = False
        if not is_ranged:
            return 0
        return 6

    def grand_coven_psychic_wound_bonus(self, model, weapon_profile=None, *, game=None) -> int:
        active = self.get_active_grand_coven(game=game)
        if active is None or active.key != PSYCHIC_MAELSTROM.key:
            return 0
        if not self._grand_coven_applies(model, game=game):
            return 0
        if weapon_profile is None:
            return 0
        try:
            if not bool(getattr(weapon_profile, "is_psychic", lambda: False)()):
                return 0
        except Exception:
            return 0
        return 1

    def grand_coven_devastating_wounds(self, model, weapon_profile=None, *, game=None) -> bool:
        active = self.get_active_grand_coven(game=game)
        if active is None or active.key != WRATH_OF_THE_IMMATERIUM.key:
            return False
        if not self._grand_coven_applies(model, game=game):
            return False
        if weapon_profile is None:
            return False
        try:
            return bool(getattr(weapon_profile, "is_psychic", lambda: False)())
        except Exception:
            return False

    def is_rubricae_phalanx(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Rubricae Phalanx")

    def _model_is_rubricae(self, model) -> bool:
        if model is None:
            return False
        try:
            fn = getattr(model, "has_any_keyword", None)
            if callable(fn) and fn("RUBRICAE"):
                return True
        except Exception:
            pass
        try:
            unit = getattr(model, "parent_unit", None)
        except Exception:
            unit = None
        return self._unit_has_keyword(unit, "RUBRICAE")

    def rubricae_phalanx_armor_save_bonus(
        self,
        model,
        *,
        damage_characteristic: Optional[int] = None,
    ) -> int:
        """
        Detachment ability: All is Dust (Rubricae Phalanx).

        Each time an attack with an unmodified Damage characteristic of 1 is allocated to a
        Rubricae model from your army, add 1 to any armour saving throw made against that attack.
        """
        if not self.is_rubricae_phalanx():
            return 0
        if damage_characteristic is None:
            return 0
        try:
            if int(damage_characteristic) != 1:
                return 0
        except Exception:
            return 0
        if not self._model_is_rubricae(model):
            return 0
        if not self._model_in_army(model):
            return 0
        return 1
