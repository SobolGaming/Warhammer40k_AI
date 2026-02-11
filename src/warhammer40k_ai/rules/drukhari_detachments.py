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

    def _unit_attached_members(self, unit) -> list:
        if unit is None:
            return []
        try:
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else []
        except Exception:
            members = []
        if not members:
            members = [root]
        return [m for m in members if m is not None]

    def _unit_has_pharmacophex(self, unit) -> bool:
        if unit is None:
            return False
        try:
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get("enhancement_pharmacophex")):
                return True
        except Exception:
            pass
        try:
            enh = getattr(unit, "enhancement", None)
            if enh is None:
                return False
            enh_id = str(getattr(enh, "id", "") or "").strip()
            enh_name = str(getattr(enh, "name", "") or "").strip().lower()
            return enh_id == "000010580002" or enh_name == "pharmacophex"
        except Exception:
            return False

    def _unit_active_pharmacophex_key(self, unit, *, game=None) -> str:
        if unit is None:
            return ""
        try:
            sr = getattr(unit, "special_rules", None)
        except Exception:
            sr = None
        if not isinstance(sr, dict):
            return ""
        key = str(sr.get("enhancement_pharmacophex_drug_key", "") or "").strip().upper()
        if key not in COMBAT_DRUG_BY_KEY:
            return ""
        if game is None:
            return key
        try:
            marked_round = int(sr.get("enhancement_pharmacophex_round", 0) or 0)
        except Exception:
            marked_round = 0
        if marked_round and int(getattr(game, "turn", 0) or 0) != marked_round:
            return ""
        return key

    def get_pharmacophex_combat_drug_key_for_model(self, model, *, game=None) -> str:
        if model is None:
            return ""
        if not self._army_has_combat_drugs():
            return ""
        if not self._model_in_army(model):
            return ""
        try:
            unit = getattr(model, "parent_unit", None)
        except Exception:
            unit = None
        if unit is None:
            return ""
        members = self._unit_attached_members(unit)
        for member in members:
            if not self._unit_has_pharmacophex(member):
                continue
            key = self._unit_active_pharmacophex_key(member, game=game)
            if key:
                return key
        return ""

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
        keys = set(self.combat_drug_active_keys)
        extra = self.get_pharmacophex_combat_drug_key_for_model(model, game=game)
        if extra:
            keys.add(extra)
        return keys

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

    def trigger_pharmacophex_roll(self, *, battle_round: Optional[int] = None, game=None) -> list[dict]:
        if not self._army_has_combat_drugs():
            return []
        if self.army is None:
            return []
        active_army_keys = self.get_active_combat_drug_keys(game=game)
        out: list[dict] = []
        units = list(getattr(self.army, "units", []) or [])
        for unit in units:
            if unit is None or not self._unit_has_pharmacophex(unit):
                continue
            try:
                if not bool(getattr(unit, "is_alive", lambda: True)()):
                    continue
            except Exception:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr.pop("enhancement_pharmacophex_drug_key", None)
            sr.pop("enhancement_pharmacophex_round", None)
            sr.pop("enhancement_pharmacophex_roll", None)
            roll = int(get_roll("D6"))
            drug = COMBAT_DRUG_BY_ROLL.get(int(roll))
            selected_key = str(getattr(drug, "key", "") or "").strip().upper() if drug is not None else ""
            selected_name = str(getattr(drug, "name", "") or "").strip() if drug is not None else ""
            applied = bool(selected_key and selected_key not in active_army_keys)
            if applied:
                sr["enhancement_pharmacophex_drug_key"] = selected_key
                if battle_round is not None:
                    try:
                        sr["enhancement_pharmacophex_round"] = int(battle_round)
                    except Exception:
                        pass
                sr["enhancement_pharmacophex_roll"] = int(roll)
            unit.special_rules = sr
            out.append(
                {
                    "unit": unit,
                    "roll": int(roll),
                    "selected_key": selected_key,
                    "selected_name": selected_name,
                    "applied": bool(applied),
                }
            )
        return out
