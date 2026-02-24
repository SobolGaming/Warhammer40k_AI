from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .detachment_manager import DetachmentManagerBase
from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id


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
    DETACHMENT_COVENITE_COTERIE = "Covenite Coterie"
    DETACHMENT_KABALITE_CARTEL = "Kabalite Cartel"
    DETACHMENT_REALSPACE_RAIDERS = "Realspace Raiders"
    DETACHMENT_REAPERS_WAGER = "Reaper's Wager"
    ALLIANCE_OF_AGONY_SOURCE = "Alliance of Agony"
    CALLOUS_COMPETITION_SOURCE = "Callous Competition"
    CALLOUS_COMPETITION_SIDE_DRUKHARI = "DRUKHARI"
    CALLOUS_COMPETITION_SIDE_HARLEQUINS = "HARLEQUINS"
    MURDEROUS_AGENDA_CONTRACT_TROPHY_HUNTERS = "TROPHY_HUNTERS"
    MURDEROUS_AGENDA_CONTRACT_SOW_FEAR_AND_TERROR = "SOW_FEAR_AND_TERROR"
    MURDEROUS_AGENDA_CONTRACT_SHOW_OF_STRENGTH = "SHOW_OF_STRENGTH"
    MURDEROUS_AGENDA_SOURCE = "Murderous Agenda"

    def __init__(self, army=None):
        super().__init__(army)
        self.combat_drug_active_keys: set[str] = set()
        self.combat_drug_active_round: Optional[int] = None
        self.combat_drug_used_keys: list[str] = []
        self.murderous_agenda_contract_key: str = ""
        self.murderous_agenda_contract_target_unit_id: str = ""
        self.murderous_agenda_contract_completed: bool = False
        self.murderous_agenda_reward_paid: bool = False
        self.alliance_of_agony_applied: bool = False
        self.alliance_of_agony_tokens_awarded: int = 0
        self.callous_competition_initialized: bool = False
        self.callous_competition_winning_side: str = ""

    def is_covenite_coterie(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_COVENITE_COTERIE)

    def is_kabalite_cartel(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_KABALITE_CARTEL)

    def is_realspace_raiders(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_REALSPACE_RAIDERS)

    def is_reapers_wager(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_REAPERS_WAGER)

    def is_spectacle_of_spite(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Spectacle of Spite")

    @staticmethod
    def _unit_root(unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    def _unit_in_army(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None or self.army is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _unit_is_haemonculus_covens(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return self._unit_has_keyword(root, "HAEMONCULUS COVENS")

    def _unit_root_id(self, unit) -> str:
        root = self._unit_root(unit)
        if root is None:
            return ""
        return str(get_entity_id(root) or "")

    def _unit_name_matches(self, unit, unit_name: str) -> bool:
        if unit is None:
            return False
        expected = self._norm(unit_name)
        actual = self._norm(str(getattr(unit, "name", "") or ""))
        if not expected or not actual:
            return False
        if actual == expected:
            return True
        if actual.endswith("s") and actual[:-1] == expected:
            return True
        if expected.endswith("s") and expected[:-1] == actual:
            return True
        return False

    def _model_side_for_callous_competition(self, model, *, unit=None) -> str:
        if model is not None:
            if self._model_has_keyword(model, self.CALLOUS_COMPETITION_SIDE_HARLEQUINS):
                return self.CALLOUS_COMPETITION_SIDE_HARLEQUINS
            if self._model_has_keyword(model, self.CALLOUS_COMPETITION_SIDE_DRUKHARI):
                return self.CALLOUS_COMPETITION_SIDE_DRUKHARI
        source_unit = unit
        if source_unit is None and model is not None:
            source_unit = getattr(model, "parent_unit", None)
        return self._unit_side_for_callous_competition(source_unit)

    def _unit_side_for_callous_competition(self, unit) -> str:
        root = self._unit_root(unit)
        if root is None:
            return ""
        is_harlequins = self._unit_has_keyword(root, self.CALLOUS_COMPETITION_SIDE_HARLEQUINS)
        is_drukhari = self._unit_has_keyword(root, self.CALLOUS_COMPETITION_SIDE_DRUKHARI)
        if is_harlequins and not is_drukhari:
            return self.CALLOUS_COMPETITION_SIDE_HARLEQUINS
        if is_drukhari and not is_harlequins:
            return self.CALLOUS_COMPETITION_SIDE_DRUKHARI
        return ""

    def _callous_competition_side_is_winning(self, side: str) -> bool:
        side_norm = str(side or "").strip().upper()
        winning = str(self.callous_competition_winning_side or "").strip().upper()
        if side_norm not in {
            self.CALLOUS_COMPETITION_SIDE_DRUKHARI,
            self.CALLOUS_COMPETITION_SIDE_HARLEQUINS,
        }:
            return False
        if winning not in {
            self.CALLOUS_COMPETITION_SIDE_DRUKHARI,
            self.CALLOUS_COMPETITION_SIDE_HARLEQUINS,
        }:
            return False
        return side_norm == winning

    def initialize_callous_competition(self, *, battle_round: int, player=None) -> bool:
        if not self.is_reapers_wager():
            return False
        if self.army is None:
            return False
        if self.callous_competition_initialized:
            return False
        if int(battle_round or 0) != 1:
            return False
        if player is not None and getattr(self.army, "player", None) is not player:
            return False
        self.callous_competition_winning_side = self.CALLOUS_COMPETITION_SIDE_DRUKHARI
        self.callous_competition_initialized = True
        return True

    def on_enemy_unit_destroyed(self, unit, *, destroyed_by_unit=None, destroyed_by_model=None, game=None) -> bool:
        del unit
        del game
        if not self.is_reapers_wager():
            return False
        if not self.callous_competition_initialized:
            return False
        if self.army is None:
            return False

        attacker_unit = self._unit_root(destroyed_by_unit)
        attacker_model = destroyed_by_model
        if attacker_model is not None and not self._model_in_army(attacker_model):
            attacker_model = None
        if attacker_unit is not None and not self._unit_in_army(attacker_unit):
            attacker_unit = None
        if attacker_unit is None and attacker_model is None:
            return False

        side = self._unit_side_for_callous_competition(attacker_unit)
        if not side:
            side = self._model_side_for_callous_competition(attacker_model, unit=attacker_unit)
        if side not in {
            self.CALLOUS_COMPETITION_SIDE_DRUKHARI,
            self.CALLOUS_COMPETITION_SIDE_HARLEQUINS,
        }:
            return False
        self.callous_competition_winning_side = side
        return True

    def callous_competition_hit_reroll_ones(self, model, *, unit=None) -> tuple[bool, str]:
        if not self.is_reapers_wager():
            return False, ""
        if not self.callous_competition_initialized:
            return False, ""
        if model is None:
            return False, ""
        if not self._model_in_army(model):
            return False, ""
        side = self._model_side_for_callous_competition(model, unit=unit)
        if side not in {
            self.CALLOUS_COMPETITION_SIDE_DRUKHARI,
            self.CALLOUS_COMPETITION_SIDE_HARLEQUINS,
        }:
            return False, ""
        return True, self.CALLOUS_COMPETITION_SOURCE

    def callous_competition_wound_reroll_ones(self, model, *, unit=None) -> tuple[bool, str]:
        if not self.is_reapers_wager():
            return False, ""
        if not self.callous_competition_initialized:
            return False, ""
        if model is None:
            return False, ""
        if not self._model_in_army(model):
            return False, ""
        side = self._model_side_for_callous_competition(model, unit=unit)
        if side not in {
            self.CALLOUS_COMPETITION_SIDE_DRUKHARI,
            self.CALLOUS_COMPETITION_SIDE_HARLEQUINS,
        }:
            return False, ""
        if self._callous_competition_side_is_winning(side):
            return False, ""
        return True, self.CALLOUS_COMPETITION_SOURCE

    def _unit_on_battlefield(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        if getattr(root, "embarked_in", None) is not None:
            return False
        in_reserves = getattr(root, "is_in_reserves", None)
        if callable(in_reserves) and bool(in_reserves()):
            return False
        reserve_status = str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower()
        return reserve_status == "deployed"

    def _army_has_combat_drugs(self) -> bool:
        return self.is_spectacle_of_spite()

    def stitchflesh_abominations_defensive_wound_mod_entry(self, target_unit) -> Optional[dict]:
        if not self.is_covenite_coterie():
            return None
        root = self._unit_root(target_unit)
        if root is None:
            return None
        if not self._unit_in_army(root):
            return None
        if not self._unit_is_haemonculus_covens(root):
            return None
        return {
            "value": 1,
            "attack_type": "any",
            "source": "Stitchflesh Abominations",
            "requires_strength_gt_toughness": True,
            "tag": "detachment:stitchflesh_abominations",
        }

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

    @classmethod
    def _murderous_agenda_contract_name(cls, contract_key: str) -> str:
        key = str(contract_key or "").strip().upper()
        if key == cls.MURDEROUS_AGENDA_CONTRACT_TROPHY_HUNTERS:
            return "Trophy Hunters"
        if key == cls.MURDEROUS_AGENDA_CONTRACT_SOW_FEAR_AND_TERROR:
            return "Sow Fear and Terror"
        if key == cls.MURDEROUS_AGENDA_CONTRACT_SHOW_OF_STRENGTH:
            return "Show of Strength"
        return key

    @classmethod
    def _murderous_agenda_contract_keys(cls) -> tuple[str, ...]:
        return (
            cls.MURDEROUS_AGENDA_CONTRACT_TROPHY_HUNTERS,
            cls.MURDEROUS_AGENDA_CONTRACT_SOW_FEAR_AND_TERROR,
            cls.MURDEROUS_AGENDA_CONTRACT_SHOW_OF_STRENGTH,
        )

    def _murderous_agenda_has_selection(self) -> bool:
        return bool(self.murderous_agenda_contract_key and self.murderous_agenda_contract_target_unit_id)

    def _iter_attached_members(self, unit) -> list:
        root = self._unit_root(unit)
        if root is None:
            return []
        members_fn = getattr(root, "get_attached_unit_members", None)
        if callable(members_fn):
            members = list(members_fn() or [])
            if members:
                return [m for m in members if m is not None]
        return [root]

    def _iter_unique_army_attached_members(self) -> list:
        if self.army is None:
            return []
        seen: set[str] = set()
        out: list = []
        for unit in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            for member in self._iter_attached_members(root):
                member_root = self._unit_root(member)
                if member_root is None:
                    continue
                key = self._unit_root_id(member_root) or f"obj:{id(member_root)}"
                if key in seen:
                    continue
                seen.add(key)
                out.append(member_root)
        return out

    def _army_has_member_with_keyword_or_name(self, *, keyword: str, unit_name: str) -> bool:
        for member in self._iter_unique_army_attached_members():
            if keyword and self._unit_has_keyword(member, keyword):
                return True
            if unit_name and self._unit_name_matches(member, unit_name):
                return True
        return False

    def _alliance_of_agony_token_amount(self) -> int:
        has_archon = self._army_has_member_with_keyword_or_name(keyword="ARCHON", unit_name="Archon")
        has_kabalite_warriors = self._army_has_member_with_keyword_or_name(
            keyword="KABALITE WARRIORS",
            unit_name="Kabalite Warriors",
        )
        has_succubus = self._army_has_member_with_keyword_or_name(keyword="SUCCUBUS", unit_name="Succubus")
        has_wyches = self._army_has_member_with_keyword_or_name(keyword="WYCHES", unit_name="Wyches")
        has_haemonculus = self._army_has_member_with_keyword_or_name(keyword="HAEMONCULUS", unit_name="Haemonculus")
        has_wracks = self._army_has_member_with_keyword_or_name(keyword="WRACKS", unit_name="Wracks")

        combos = 0
        if has_archon and has_kabalite_warriors:
            combos += 1
        if has_succubus and has_wyches:
            combos += 1
        if has_haemonculus and has_wracks:
            combos += 1
        return int(combos * 2)

    def apply_alliance_of_agony(self, *, battle_round: int, game=None, player=None) -> int:
        if not self.is_realspace_raiders():
            return 0
        if self.army is None:
            return 0
        if self.alliance_of_agony_applied:
            return 0
        if int(battle_round or 0) != 1:
            return 0
        if player is not None and getattr(self.army, "player", None) is not player:
            return 0

        token_amount = self._alliance_of_agony_token_amount()
        gained = 0
        pfp = getattr(self.army, "power_from_pain", None)
        gain_tokens = getattr(pfp, "gain_tokens", None) if pfp is not None else None
        if token_amount > 0 and callable(gain_tokens):
            gained = int(gain_tokens(token_amount, reason=self.ALLIANCE_OF_AGONY_SOURCE) or 0)
        self.alliance_of_agony_tokens_awarded = int(gained)
        self.alliance_of_agony_applied = True
        return int(gained)

    def _unit_is_character_only(self, unit) -> bool:
        members = self._iter_attached_members(unit)
        if not members:
            return False
        for member in members:
            if not self._unit_has_keyword(member, "CHARACTER"):
                return False
        return True

    def _unit_has_alive_non_character_models(self, unit) -> bool:
        for member in self._iter_attached_members(unit):
            if self._unit_has_keyword(member, "CHARACTER"):
                continue
            for model in list(getattr(member, "models", []) or []):
                if bool(getattr(model, "is_alive", False)):
                    return True
        return False

    @staticmethod
    def _model_has_keyword(model, keyword: str) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(keyword)):
            return True
        has_keyword = getattr(model, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword(keyword)):
            return True
        return False

    def _model_is_kabal_or_blades_for_hire(self, model) -> bool:
        if model is None:
            return False
        if self._model_has_keyword(model, "KABAL"):
            return True
        if self._model_has_keyword(model, "BLADES FOR HIRE"):
            return True
        unit = getattr(model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return False
        return bool(self._unit_has_keyword(root, "KABAL") or self._unit_has_keyword(root, "BLADES FOR HIRE"))

    def _collect_murderous_agenda_candidates(self, contract_key: str, *, game=None, player=None) -> list:
        key = str(contract_key or "").strip().upper()
        if key not in self._murderous_agenda_contract_keys():
            return []
        if not self.is_kabalite_cartel():
            return []
        if game is None or player is None:
            return []
        get_enemy_units = getattr(game, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []

        candidates = []
        seen_ids: set[str] = set()
        for enemy in list(get_enemy_units(player) or []):
            root = self._unit_root(enemy)
            if root is None:
                continue
            root_id = self._unit_root_id(root)
            if not root_id or root_id in seen_ids:
                continue
            seen_ids.add(root_id)
            if not self._unit_on_battlefield(root):
                continue
            if key == self.MURDEROUS_AGENDA_CONTRACT_TROPHY_HUNTERS:
                if not self._unit_has_keyword(root, "CHARACTER"):
                    continue
            elif key == self.MURDEROUS_AGENDA_CONTRACT_SOW_FEAR_AND_TERROR:
                if not (self._unit_has_keyword(root, "INFANTRY") or self._unit_has_keyword(root, "MOUNTED")):
                    continue
                if self._unit_is_character_only(root):
                    continue
            elif key == self.MURDEROUS_AGENDA_CONTRACT_SHOW_OF_STRENGTH:
                if not (self._unit_has_keyword(root, "MONSTER") or self._unit_has_keyword(root, "VEHICLE")):
                    continue
            candidates.append(root)
        candidates.sort(key=lambda unit: (self._norm(getattr(unit, "name", "")), self._unit_root_id(unit)))
        return candidates

    def build_murderous_agenda_request(self, *, game=None, player=None):
        if not self.is_kabalite_cartel():
            return None
        if game is None or player is None or self.army is None:
            return None
        if getattr(self.army, "player", None) is not player:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        if self._murderous_agenda_has_selection():
            return None
        battle_round = int(getattr(game, "turn", 0) or 0)
        if battle_round != 1:
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_MURDEROUS_AGENDA
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_MURDEROUS_AGENDA:
                    continue
                if str(getattr(req, "player_id", "") or "") != str(getattr(player, "id", "") or ""):
                    continue
                return None

        options = []
        candidate_bindings = []
        for contract_key in self._murderous_agenda_contract_keys():
            candidates = self._collect_murderous_agenda_candidates(contract_key, game=game, player=player)
            contract_name = self._murderous_agenda_contract_name(contract_key)
            for candidate in candidates:
                target_unit_id = self._unit_root_id(candidate)
                if not target_unit_id:
                    continue
                candidate_bindings.append({"contract_key": contract_key, "target_unit_id": target_unit_id})
                options.append(
                    DecisionOption.create(
                        f"{contract_name}: {str(getattr(candidate, 'name', 'Unit') or 'Unit')}",
                        payload={"contract_key": contract_key, "target_unit_id": target_unit_id},
                    )
                )
        if not options:
            return None
        army_id = str(get_entity_id(self.army) or "")
        return DecisionRequest.create(
            DECISION_CHOOSE_MURDEROUS_AGENDA,
            "Murderous Agenda: select a Contract and target unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "murderous_agenda",
                "ability_name": self.MURDEROUS_AGENDA_SOURCE,
                "army_id": army_id,
                "battle_round": battle_round,
                "candidate_bindings": list(candidate_bindings),
            },
        )

    def murderous_agenda_selection_is_valid(self, contract_key: str, target_unit_id: str, *, game=None, player=None) -> tuple[bool, str]:
        if not self.is_kabalite_cartel():
            return False, "Murderous Agenda requires the Kabalite Cartel detachment."
        if self._murderous_agenda_has_selection():
            return False, "Murderous Agenda has already been selected."
        key = str(contract_key or "").strip().upper()
        if key not in self._murderous_agenda_contract_keys():
            return False, "Murderous Agenda selection has an invalid contract."
        tid = str(target_unit_id or "").strip()
        if not tid:
            return False, "Murderous Agenda selection requires a target unit."
        candidates = self._collect_murderous_agenda_candidates(key, game=game, player=player)
        candidate_ids = {self._unit_root_id(unit) for unit in candidates}
        if tid not in candidate_ids:
            return False, "Murderous Agenda selection target is not eligible for the chosen contract."
        return True, ""

    def select_murderous_agenda(self, contract_key: str, target_unit_id: str, *, game=None, player=None) -> bool:
        valid, _reason = self.murderous_agenda_selection_is_valid(contract_key, target_unit_id, game=game, player=player)
        if not valid:
            return False
        self.murderous_agenda_contract_key = str(contract_key or "").strip().upper()
        self.murderous_agenda_contract_target_unit_id = str(target_unit_id or "").strip()
        self.murderous_agenda_contract_completed = False
        self.murderous_agenda_reward_paid = False
        return True

    def _resolve_unit_by_id(self, unit_id: str, *, game=None):
        uid = str(unit_id or "").strip()
        if not uid:
            return None
        if game is not None:
            registry = getattr(game, "entity_registry", None)
            if registry is not None:
                get_fn = getattr(registry, "get", None)
                if callable(get_fn):
                    unit = get_fn(uid, kind="unit")
                    if unit is not None:
                        return unit
        return None

    def _murderous_agenda_target_destroyed(self, target_unit) -> bool:
        root = self._unit_root(target_unit)
        if root is None:
            return True
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive):
            return not bool(is_alive())
        return not any(bool(getattr(model, "is_alive", False)) for model in list(getattr(root, "models", []) or []))

    def resolve_murderous_agenda_completion(self, *, game=None) -> bool:
        if not self.is_kabalite_cartel():
            return False
        if not self._murderous_agenda_has_selection() or self.murderous_agenda_contract_completed:
            return False
        target_unit = self._resolve_unit_by_id(self.murderous_agenda_contract_target_unit_id, game=game)
        completed = self._murderous_agenda_target_destroyed(target_unit)
        if (
            not completed
            and self.murderous_agenda_contract_key == self.MURDEROUS_AGENDA_CONTRACT_SOW_FEAR_AND_TERROR
            and target_unit is not None
        ):
            completed = not self._unit_has_alive_non_character_models(target_unit)
        if not completed:
            return False
        self.murderous_agenda_contract_completed = True
        if not self.murderous_agenda_reward_paid:
            pfp = getattr(self.army, "power_from_pain", None) if self.army is not None else None
            gain_tokens = getattr(pfp, "gain_tokens", None) if pfp is not None else None
            if callable(gain_tokens):
                gain_tokens(3, reason=f"{self.MURDEROUS_AGENDA_SOURCE} completed")
            self.murderous_agenda_reward_paid = True
        return True

    def murderous_agenda_weapon_keyword_bonuses(self, model, target_unit) -> list[dict]:
        if not self.is_kabalite_cartel():
            return []
        if not self._murderous_agenda_has_selection() or self.murderous_agenda_contract_completed:
            return []
        if model is None or target_unit is None:
            return []
        if not self._model_in_army(model):
            return []
        if not self._model_is_kabal_or_blades_for_hire(model):
            return []

        target_root = self._unit_root(target_unit)
        if target_root is None:
            return []
        rules: list[dict] = []
        contract_key = str(self.murderous_agenda_contract_key or "").strip().upper()
        target_id = self._unit_root_id(target_root)

        if contract_key == self.MURDEROUS_AGENDA_CONTRACT_TROPHY_HUNTERS:
            if target_id and target_id == str(self.murderous_agenda_contract_target_unit_id or ""):
                rules.append(
                    {
                        "attack_type": "any",
                        "keyword": "PRECISION",
                        "source": f"{self.MURDEROUS_AGENDA_SOURCE} ({self._murderous_agenda_contract_name(contract_key)})",
                    }
                )
        elif contract_key == self.MURDEROUS_AGENDA_CONTRACT_SOW_FEAR_AND_TERROR:
            if self._unit_has_keyword(target_root, "INFANTRY") or self._unit_has_keyword(target_root, "MOUNTED"):
                rules.append(
                    {
                        "attack_type": "any",
                        "keyword": "SUSTAINED HITS 1",
                        "source": f"{self.MURDEROUS_AGENDA_SOURCE} ({self._murderous_agenda_contract_name(contract_key)})",
                    }
                )
        elif contract_key == self.MURDEROUS_AGENDA_CONTRACT_SHOW_OF_STRENGTH:
            if self._unit_has_keyword(target_root, "MONSTER") or self._unit_has_keyword(target_root, "VEHICLE"):
                rules.append(
                    {
                        "attack_type": "any",
                        "keyword": "LETHAL HITS",
                        "source": f"{self.MURDEROUS_AGENDA_SOURCE} ({self._murderous_agenda_contract_name(contract_key)})",
                    }
                )
        return rules

    def on_battle_round_start(self, *, battle_round: int, game=None, player=None) -> None:
        if self.army is None:
            return
        if player is not None and getattr(self.army, "player", None) is not player:
            return
        if int(battle_round or 0) == 1:
            self.apply_alliance_of_agony(battle_round=battle_round, game=game, player=player)
            self.initialize_callous_competition(battle_round=battle_round, player=player)

        if self.is_kabalite_cartel():
            if game is None or player is None:
                return
            if int(battle_round or 0) != 1:
                return
            if self._murderous_agenda_has_selection():
                return
            request = self.build_murderous_agenda_request(game=game, player=player)
            if request is not None and hasattr(game, "request_decision"):
                game.request_decision(request)

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if game is None or player is None or self.army is None:
            return
        if getattr(self.army, "player", None) is not player:
            return
        if self.is_kabalite_cartel():
            self.resolve_murderous_agenda_completion(game=game)
