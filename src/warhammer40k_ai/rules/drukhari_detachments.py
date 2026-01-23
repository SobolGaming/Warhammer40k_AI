from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .detachment_manager import DetachmentManagerBase
from ..utility.dice import get_roll


@dataclass(frozen=True)
class CombatDrug:
    key: str
    name: str
    summary: str
    roll: int


ADRENALIGHT = CombatDrug(
    key="ADRENALIGHT",
    name="Adrenalight",
    summary="Wych Cult melee weapons gain +1 Attacks.",
    roll=1,
)
HYPEX = CombatDrug(
    key="HYPEX",
    name="Hypex",
    summary="Wych Cult models gain +2\" Move.",
    roll=2,
)
SERPENTIN = CombatDrug(
    key="SERPENTIN",
    name="Serpentin",
    summary="Wych Cult melee weapons improve Weapon Skill by 1.",
    roll=3,
)
PAINBRINGER = CombatDrug(
    key="PAINBRINGER",
    name="Painbringer",
    summary="Wych Cult models gain +1 Toughness.",
    roll=4,
)
GRAVE_LOTUS = CombatDrug(
    key="GRAVE_LOTUS",
    name="Grave Lotus",
    summary="Wych Cult melee weapons gain +1 Strength.",
    roll=5,
)
SPLINTERMIND = CombatDrug(
    key="SPLINTERMIND",
    name="Splintermind",
    summary="Wych Cult models improve Leadership by 1 and ranged weapons improve Ballistic Skill by 1.",
    roll=6,
)

COMBAT_DRUGS: tuple[CombatDrug, ...] = (
    ADRENALIGHT,
    HYPEX,
    SERPENTIN,
    PAINBRINGER,
    GRAVE_LOTUS,
    SPLINTERMIND,
)
COMBAT_DRUG_BY_KEY = {d.key: d for d in COMBAT_DRUGS}
COMBAT_DRUG_BY_ROLL = {d.roll: d for d in COMBAT_DRUGS}


class DrukhariDetachmentManager(DetachmentManagerBase):
    faction_id = "DRU"

    def __init__(self, army=None):
        super().__init__(army)
        self.combat_drug_active_keys: set[str] = set()
        self.combat_drug_active_round: Optional[int] = None
        self.combat_drug_used_keys: list[str] = []

    def is_spectacle_of_spite(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Spectacle of Spite")

    def _army_has_combat_drugs(self) -> bool:
        return self.is_spectacle_of_spite()

    def _is_active_round(self, game=None) -> bool:
        if self.combat_drug_active_round is None:
            return False
        if game is None:
            return True
        try:
            return int(getattr(game, "turn", 0) or 0) == int(self.combat_drug_active_round)
        except Exception:
            return False

    def _model_is_wych_cult(self, model) -> bool:
        if model is None:
            return False
        try:
            fn = getattr(model, "has_any_keyword", None)
            if callable(fn):
                if fn("WYCH CULT"):
                    return True
        except Exception:
            pass
        try:
            unit = getattr(model, "parent_unit", None)
        except Exception:
            unit = None
        return self._unit_has_keyword(unit, "WYCH CULT")

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

    def get_active_combat_drug_keys(self, *, game=None) -> set[str]:
        if not self._army_has_combat_drugs():
            return set()
        if not self._is_active_round(game=game):
            return set()
        return set(self.combat_drug_active_keys)

    def get_active_combat_drug_keys_for_model(self, model, *, game=None) -> set[str]:
        if not self._army_has_combat_drugs():
            return set()
        if not self._is_active_round(game=game):
            return set()
        if not self._model_is_wych_cult(model):
            return set()
        if not self._model_in_army(model):
            return set()
        return set(self.combat_drug_active_keys)

    def get_active_combat_drugs(self, *, game=None) -> list[CombatDrug]:
        keys = self.get_active_combat_drug_keys(game=game)
        return [COMBAT_DRUG_BY_KEY[k] for k in keys if k in COMBAT_DRUG_BY_KEY]

    def get_available_combat_drugs(self) -> list[CombatDrug]:
        if not self._army_has_combat_drugs():
            return []
        used = {str(k or "").strip().upper() for k in (self.combat_drug_used_keys or []) if str(k or "").strip()}
        return [d for d in COMBAT_DRUGS if d.key not in used]

    def can_select_combat_drugs(self, *, game=None) -> bool:
        if not self._army_has_combat_drugs():
            return False
        if self.combat_drug_active_round is not None and self._is_active_round(game=game) and self.combat_drug_active_keys:
            return False
        return True

    def select_combat_drug(self, drug, *, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_combat_drugs():
            return False
        key = getattr(drug, "key", drug)
        key = str(key or "").strip().upper()
        if key not in COMBAT_DRUG_BY_KEY:
            return False
        used = {str(k or "").strip().upper() for k in (self.combat_drug_used_keys or []) if str(k or "").strip()}
        if key in used:
            return False
        self.combat_drug_active_keys = {key}
        if battle_round is not None:
            try:
                self.combat_drug_active_round = int(battle_round)
            except Exception:
                pass
        self.combat_drug_used_keys.append(key)
        return True

    def roll_combat_drugs(self, *, battle_round: Optional[int] = None) -> dict:
        if not self._army_has_combat_drugs():
            return {"rolls": [], "selected": []}
        self.combat_drug_active_keys = set()
        rolls = [int(get_roll("D6")), int(get_roll("D6"))]
        selected = []
        for roll in rolls:
            drug = COMBAT_DRUG_BY_ROLL.get(int(roll))
            if drug is None:
                continue
            if drug.key in self.combat_drug_active_keys:
                continue
            self.combat_drug_active_keys.add(drug.key)
            selected.append(drug)
        if battle_round is not None:
            try:
                self.combat_drug_active_round = int(battle_round)
            except Exception:
                pass
        return {"rolls": rolls, "selected": selected}
