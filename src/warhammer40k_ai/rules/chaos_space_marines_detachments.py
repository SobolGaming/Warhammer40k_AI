from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from ..utility.dice import get_roll
from .detachment_manager import DetachmentManagerBase


@dataclass(frozen=True)
class ExperimentalAugmentation:
    key: str
    name: str
    summary: str
    roll: int


CHOLINERGIC_ACCELERANTS = ExperimentalAugmentation(
    key="CHOLINERGIC_ACCELERANTS",
    name="Cholinergic Accelerants",
    summary="Add 1 to the Attacks characteristic of melee weapons equipped by this model.",
    roll=1,
)
HYPERADRENAL_INFUSION = ExperimentalAugmentation(
    key="HYPERADRENAL_INFUSION",
    name="Hyperadrenal Infusion",
    summary="Add 2\" to the Move characteristic of this model.",
    roll=2,
)
PARANEURAL_REACTIONS = ExperimentalAugmentation(
    key="PARANEURAL_REACTIONS",
    name="Paraneural Reactions",
    summary="Improve Weapon Skill of melee weapons equipped by this model by 1.",
    roll=3,
)
SUPRACUTANEOUS_CHITINATION = ExperimentalAugmentation(
    key="SUPRACUTANEOUS_CHITINATION",
    name="Supracutaneous Chitination",
    summary="Improve the Toughness characteristic of this model by 1.",
    roll=4,
)
MACROTENSILE_SINEWS = ExperimentalAugmentation(
    key="MACROTENSILE_SINEWS",
    name="Macrotensile Sinews",
    summary="Add 1 to the Strength characteristic of melee weapons equipped by this model.",
    roll=5,
)
OPHTHALMIC_ENHANCEMENT = ExperimentalAugmentation(
    key="OPHTHALMIC_ENHANCEMENT",
    name="Ophthalmic Enhancement",
    summary="Improve Ballistic Skill of ranged weapons equipped by this model by 1.",
    roll=6,
)

EXPERIMENTAL_AUGMENTATIONS: tuple[ExperimentalAugmentation, ...] = (
    CHOLINERGIC_ACCELERANTS,
    HYPERADRENAL_INFUSION,
    PARANEURAL_REACTIONS,
    SUPRACUTANEOUS_CHITINATION,
    MACROTENSILE_SINEWS,
    OPHTHALMIC_ENHANCEMENT,
)
EXPERIMENTAL_AUGMENTATION_BY_KEY = {a.key: a for a in EXPERIMENTAL_AUGMENTATIONS}
EXPERIMENTAL_AUGMENTATION_BY_ROLL = {a.roll: a for a in EXPERIMENTAL_AUGMENTATIONS}


class ChaosSpaceMarinesDetachmentManager(DetachmentManagerBase):
    faction_id = "CSM"

    DETACHMENT_CABAL_OF_CHAOS = "Cabal of Chaos"
    DETACHMENT_CHAOS_CULT = "Chaos Cult"
    DETACHMENT_CREATIONS_OF_BILE = "Creations of Bile"
    DETACHMENT_RENEGADE_RAIDERS = "Renegade Raiders"
    _DESPERATE_DEVOTION_ALLOWED_ACTIONS = {"move", "advance", "charge"}
    _EXPERIMENTAL_AUGMENTATION_REROLL_MODES = {"keep", "reroll_first", "reroll_second", "reroll_both"}

    def __init__(self, army=None):
        super().__init__(army)
        self.experimental_augmentations_active_keys: set[str] = set()
        self.experimental_augmentations_selected: bool = False
        self.experimental_augmentations_selected_round: Optional[int] = None
        self.experimental_augmentations_selection_mode: str = ""
        self.experimental_augmentations_rolls: list[int] = []
        self.experimental_augmentations_pending_rolls: list[int] = []
        self.experimental_augmentations_pending_round: Optional[int] = None

    def is_cabal_of_chaos(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_CABAL_OF_CHAOS)

    def is_chaos_cult(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_CHAOS_CULT)

    def is_creations_of_bile(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_CREATIONS_OF_BILE)

    def is_renegade_raiders(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_RENEGADE_RAIDERS)

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

    @staticmethod
    def _unit_root_key(unit) -> str:
        root = ChaosSpaceMarinesDetachmentManager._unit_root(unit)
        if root is None:
            return ""
        unit_id = str(getattr(root, "_id", "") or "").strip()
        if unit_id:
            return unit_id
        return str(id(root))

    def _iter_unique_roots(self, units: Iterable) -> list:
        roots = []
        seen: set[str] = set()
        for unit in list(units or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            key = self._unit_root_key(root)
            if key in seen:
                continue
            seen.add(key)
            roots.append(root)
        return roots

    def _unit_in_army(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None or self.army is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _model_in_army(self, model) -> bool:
        if model is None:
            return False
        return self._unit_in_army(getattr(model, "parent_unit", None))

    def _unit_is_heretic_astartes(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return self._unit_has_keyword(root, "HERETIC ASTARTES")

    def _unit_is_damned(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return self._unit_has_keyword(root, "DAMNED")

    def _unit_has_dark_pacts(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False

        has_dark_pacts = getattr(root, "has_dark_pacts", None)
        if callable(has_dark_pacts) and bool(has_dark_pacts()):
            return True

        for container_name in ("possible_abilities", "abilities"):
            for ability in list(getattr(root, container_name, []) or []):
                if isinstance(ability, str):
                    name = ability
                else:
                    name = getattr(ability, "name", "")
                if "dark pact" in str(name or "").strip().lower():
                    return True
        return False

    def _unit_arrived_from_reserves_this_turn(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return bool(getattr(root, "arrived_from_reserves_this_turn", False))

    def _unit_on_battlefield(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        in_reserves = getattr(root, "is_in_reserves", None)
        if callable(in_reserves) and bool(in_reserves()):
            return False
        return True

    def _model_is_heretic_astartes(self, model) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any) and bool(has_any("HERETIC ASTARTES")):
            return True
        has_keyword = getattr(model, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("HERETIC ASTARTES")):
            return True
        return self._unit_is_heretic_astartes(getattr(model, "parent_unit", None))

    @staticmethod
    def _normalize_name(value: str) -> str:
        return " ".join(str(value or "").strip().lower().split())

    @classmethod
    def _is_fabius_bile_name(cls, value: str) -> bool:
        return cls._normalize_name(value) == "fabius bile"

    def _warlord_root(self):
        if self.army is None:
            return None
        warlord = getattr(self.army, "warlord", None)
        if warlord is None:
            for unit in list(getattr(self.army, "units", []) or []):
                if bool(getattr(unit, "is_warlord", False)):
                    warlord = unit
                    break
        return self._unit_root(warlord)

    def has_fabius_bile_warlord(self) -> bool:
        warlord = self._warlord_root()
        if warlord is None:
            return False
        if self._is_fabius_bile_name(getattr(warlord, "name", "")):
            return True
        members_fn = getattr(warlord, "get_attached_unit_members", None)
        if callable(members_fn):
            for member in list(members_fn() or []):
                if bool(getattr(member, "is_warlord", False)) and self._is_fabius_bile_name(getattr(member, "name", "")):
                    return True
        return False

    def _unit_is_creations_eligible(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_has_keyword(root, "HERETIC ASTARTES"):
            return False
        if not self._unit_has_keyword(root, "INFANTRY"):
            return False
        if self._unit_has_keyword(root, "DAMNED"):
            return False
        return True

    def _model_is_creations_eligible(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        return self._unit_is_creations_eligible(unit)

    @staticmethod
    def experimental_augmentations_catalog() -> tuple[ExperimentalAugmentation, ...]:
        return EXPERIMENTAL_AUGMENTATIONS

    @staticmethod
    def experimental_augmentation_name(key: str) -> str:
        aug = EXPERIMENTAL_AUGMENTATION_BY_KEY.get(str(key or "").strip().upper())
        if aug is None:
            return str(key or "").strip()
        return aug.name

    def describe_experimental_augmentation_keys(self, keys: Iterable[str]) -> list[str]:
        out: list[str] = []
        for key in list(keys or []):
            name = self.experimental_augmentation_name(str(key or "").strip().upper())
            if name and name not in out:
                out.append(name)
        return out

    def can_select_experimental_augmentations(self, *, game=None, battle_round: Optional[int] = None) -> bool:
        if not self.is_creations_of_bile():
            return False
        if self.experimental_augmentations_selected:
            return False
        if self.experimental_augmentations_pending_rolls:
            return False
        round_value = battle_round
        if round_value is None and game is not None:
            try:
                round_value = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                round_value = 0
        if round_value is not None and int(round_value or 0) > 1:
            return False
        return True

    @staticmethod
    def _dedupe_augmentation_keys(keys: Iterable[str]) -> list[str]:
        unique: list[str] = []
        for key in list(keys or []):
            norm = str(key or "").strip().upper()
            if norm not in EXPERIMENTAL_AUGMENTATION_BY_KEY:
                continue
            if norm in unique:
                continue
            unique.append(norm)
        return unique

    @staticmethod
    def _augmentation_keys_from_rolls(rolls: Iterable[int]) -> list[str]:
        keys: list[str] = []
        for roll in list(rolls or []):
            try:
                value = int(roll or 0)
            except (TypeError, ValueError):
                continue
            aug = EXPERIMENTAL_AUGMENTATION_BY_ROLL.get(value)
            if aug is None:
                continue
            keys.append(aug.key)
        return ChaosSpaceMarinesDetachmentManager._dedupe_augmentation_keys(keys)

    def _clear_pending_experimental_augmentation_rolls(self) -> None:
        self.experimental_augmentations_pending_rolls = []
        self.experimental_augmentations_pending_round = None

    def _finalize_experimental_augmentations(
        self,
        *,
        keys: Iterable[str],
        battle_round: Optional[int],
        mode: str,
        rolls: Optional[Iterable[int]] = None,
    ) -> None:
        final_keys = self._dedupe_augmentation_keys(keys)
        self.experimental_augmentations_active_keys = set(final_keys)
        self.experimental_augmentations_selected = True
        self.experimental_augmentations_selection_mode = str(mode or "").strip().lower() or "manual"
        if battle_round is not None:
            try:
                self.experimental_augmentations_selected_round = int(battle_round)
            except (TypeError, ValueError):
                self.experimental_augmentations_selected_round = None
        else:
            self.experimental_augmentations_selected_round = None
        self.experimental_augmentations_rolls = [int(v) for v in list(rolls or [])]
        self._clear_pending_experimental_augmentation_rolls()

    def select_experimental_augmentation(self, choice_key: str, *, battle_round: Optional[int] = None) -> bool:
        if not self.can_select_experimental_augmentations(battle_round=battle_round):
            return False
        key = str(choice_key or "").strip().upper()
        if key not in EXPERIMENTAL_AUGMENTATION_BY_KEY:
            return False
        self._finalize_experimental_augmentations(
            keys=[key],
            battle_round=battle_round,
            mode="manual",
            rolls=[],
        )
        return True

    def roll_experimental_augmentations_initial(self, *, battle_round: Optional[int] = None, game=None) -> dict:
        if not self.can_select_experimental_augmentations(game=game, battle_round=battle_round):
            return {"ok": False, "reason": "Experimental Augmentations cannot be selected right now."}
        rolls = [int(get_roll("D6") or 0), int(get_roll("D6") or 0)]
        selected_keys = self._augmentation_keys_from_rolls(rolls)
        fabius_warlord = bool(self.has_fabius_bile_warlord())
        if not fabius_warlord:
            self._finalize_experimental_augmentations(
                keys=selected_keys,
                battle_round=battle_round,
                mode="random",
                rolls=rolls,
            )
            return {
                "ok": True,
                "rolls": list(rolls),
                "selected_keys": list(selected_keys),
                "requires_reroll_choice": False,
                "finalized": True,
            }
        self.experimental_augmentations_pending_rolls = list(rolls)
        if battle_round is not None:
            try:
                self.experimental_augmentations_pending_round = int(battle_round)
            except (TypeError, ValueError):
                self.experimental_augmentations_pending_round = None
        else:
            self.experimental_augmentations_pending_round = None
        return {
            "ok": True,
            "rolls": list(rolls),
            "selected_keys": list(selected_keys),
            "requires_reroll_choice": True,
            "finalized": False,
        }

    def has_pending_experimental_augmentations_rolls(self) -> bool:
        return bool(self.experimental_augmentations_pending_rolls) and not self.experimental_augmentations_selected

    def resolve_experimental_augmentations_reroll(self, mode: str, *, battle_round: Optional[int] = None) -> dict:
        if not self.has_pending_experimental_augmentations_rolls():
            return {"ok": False, "reason": "No pending Experimental Augmentations rolls."}
        reroll_mode = str(mode or "").strip().lower()
        if reroll_mode not in self._EXPERIMENTAL_AUGMENTATION_REROLL_MODES:
            return {"ok": False, "reason": "Invalid Experimental Augmentations reroll mode."}

        original_rolls = list(self.experimental_augmentations_pending_rolls)
        updated_rolls = list(original_rolls)
        if reroll_mode in {"reroll_first", "reroll_both"}:
            updated_rolls[0] = int(get_roll("D6") or 0)
        if reroll_mode in {"reroll_second", "reroll_both"}:
            updated_rolls[1] = int(get_roll("D6") or 0)
        selected_keys = self._augmentation_keys_from_rolls(updated_rolls)

        selected_round = battle_round
        if selected_round is None:
            selected_round = self.experimental_augmentations_pending_round
        self._finalize_experimental_augmentations(
            keys=selected_keys,
            battle_round=selected_round,
            mode="random",
            rolls=updated_rolls,
        )
        return {
            "ok": True,
            "reroll_mode": reroll_mode,
            "original_rolls": original_rolls,
            "rolls": updated_rolls,
            "selected_keys": list(selected_keys),
            "finalized": True,
        }

    def get_active_experimental_augmentation_keys_for_model(self, model) -> set[str]:
        if not self.is_creations_of_bile():
            return set()
        if not self.experimental_augmentations_selected:
            return set()
        if not self._model_is_creations_eligible(model):
            return set()
        return set(self.experimental_augmentations_active_keys)

    def experimental_augmentations_movement_bonus(self, model=None, unit=None, *, game=None) -> tuple[int, str]:
        target_model = model
        if target_model is None and unit is not None:
            models = list(getattr(unit, "models", []) or [])
            if models:
                target_model = models[0]
        if target_model is None:
            return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(target_model)
        if HYPERADRENAL_INFUSION.key not in keys:
            return 0, ""
        return 2, HYPERADRENAL_INFUSION.name

    def experimental_augmentations_toughness_bonus(self, model=None, unit=None, *, game=None) -> tuple[int, str]:
        target_model = model
        if target_model is None and unit is not None:
            models = list(getattr(unit, "models", []) or [])
            if models:
                target_model = models[0]
        if target_model is None:
            return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(target_model)
        if SUPRACUTANEOUS_CHITINATION.key not in keys:
            return 0, ""
        return 1, SUPRACUTANEOUS_CHITINATION.name

    def experimental_augmentations_melee_attacks_bonus(self, model, weapon_profile=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee = getattr(parent, "is_melee", None) if parent is not None else None
            if not callable(is_melee) or not bool(is_melee()):
                return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(model)
        if CHOLINERGIC_ACCELERANTS.key not in keys:
            return 0, ""
        return 1, CHOLINERGIC_ACCELERANTS.name

    def experimental_augmentations_melee_skill_bonus(self, model, weapon_profile=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee = getattr(parent, "is_melee", None) if parent is not None else None
            if not callable(is_melee) or not bool(is_melee()):
                return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(model)
        if PARANEURAL_REACTIONS.key not in keys:
            return 0, ""
        return 1, PARANEURAL_REACTIONS.name

    def experimental_augmentations_ranged_skill_bonus(self, model, weapon_profile=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_ranged = getattr(parent, "is_ranged", None) if parent is not None else None
            if not callable(is_ranged) or not bool(is_ranged()):
                return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(model)
        if OPHTHALMIC_ENHANCEMENT.key not in keys:
            return 0, ""
        return 1, OPHTHALMIC_ENHANCEMENT.name

    def experimental_augmentations_melee_strength_bonus(self, model, weapon_profile=None) -> tuple[int, str]:
        if model is None:
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_melee = getattr(parent, "is_melee", None) if parent is not None else None
            if not callable(is_melee) or not bool(is_melee()):
                return 0, ""
        keys = self.get_active_experimental_augmentation_keys_for_model(model)
        if MACROTENSILE_SINEWS.key not in keys:
            return 0, ""
        return 1, MACROTENSILE_SINEWS.name

    def _resolve_game(self, *, game=None):
        if game is not None:
            return game
        if self.army is None:
            return None
        player = getattr(self.army, "player", None)
        if player is None:
            return None
        return getattr(player, "game", None)

    def _current_phase_name(self, *, game=None) -> str:
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return ""
        return str(getattr(getattr(resolved_game, "phase", None), "name", "") or "").strip().upper()

    def _current_turn(self, *, game=None) -> int:
        resolved_game = self._resolve_game(game=game)
        if resolved_game is None:
            return 0
        try:
            return int(getattr(resolved_game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _current_turn_owner_id(self, *, game=None, player=None) -> str:
        resolved_game = self._resolve_game(game=game)
        if resolved_game is not None:
            get_current_player = getattr(resolved_game, "get_current_player", None)
            if callable(get_current_player):
                current_player = get_current_player()
                owner_id = str(getattr(current_player, "id", "") or "").strip()
                if owner_id:
                    return owner_id
        if player is not None:
            owner_id = str(getattr(player, "id", "") or "").strip()
            if owner_id:
                return owner_id
        army_player = getattr(self.army, "player", None) if self.army is not None else None
        return str(getattr(army_player, "id", "") or "").strip()

    def desperate_devotion_can_trigger(self, unit, *, action: str, game=None) -> bool:
        if not self.is_chaos_cult():
            return False
        action_key = str(action or "").strip().lower()
        if action_key not in self._DESPERATE_DEVOTION_ALLOWED_ACTIONS:
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_in_army(root):
            return False
        if not self._unit_on_battlefield(root):
            return False
        if self._unit_arrived_from_reserves_this_turn(root):
            return False
        if not self._unit_is_damned(root):
            return False
        if not self._unit_has_dark_pacts(root):
            return False

        phase_name = self._current_phase_name(game=game)
        if action_key in {"move", "advance"}:
            return phase_name in {"", "MOVEMENT_PHASE"}
        if action_key == "charge":
            return phase_name in {"", "CHARGE_PHASE"}
        return False

    def activate_desperate_devotion(
        self,
        unit,
        *,
        action: str,
        game=None,
        player=None,
        ability_name: str = "Desperate Devotion",
    ) -> dict:
        action_key = str(action or "").strip().lower()
        root = self._unit_root(unit)
        if root is None:
            return {"ok": False, "reason": "Unit not found."}
        if not self.desperate_devotion_can_trigger(root, action=action_key, game=game):
            return {"ok": False, "reason": "Desperate Devotion cannot trigger for this unit/action."}

        leadership_fn = getattr(root, "pass_leadership_check", None)
        leadership_passed = True
        if callable(leadership_fn):
            leadership_passed = bool(leadership_fn())

        mortal_wounds = 0
        if not leadership_passed:
            try:
                mortal_wounds = int(get_roll("D3") or 0)
            except (TypeError, ValueError):
                mortal_wounds = 0
            if mortal_wounds <= 0:
                mortal_wounds = 1
            apply_mortal = getattr(root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal):
                resolved_game = self._resolve_game(game=game)
                apply_mortal(root, int(mortal_wounds), game_map=getattr(resolved_game, "map", None))

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["chaos_cult_desperate_devotion_active"] = True
        sr["chaos_cult_desperate_devotion_phase"] = self._current_phase_name(game=game)
        sr["chaos_cult_desperate_devotion_turn"] = self._current_turn(game=game)
        sr["chaos_cult_desperate_devotion_turn_owner"] = self._current_turn_owner_id(game=game, player=player)
        sr["chaos_cult_desperate_devotion_move_bonus"] = 2
        sr["chaos_cult_desperate_devotion_charge_bonus"] = 2
        sr["chaos_cult_desperate_devotion_source"] = str(ability_name or "Desperate Devotion").strip() or "Desperate Devotion"
        root.special_rules = sr

        return {
            "ok": True,
            "unit_id": self._unit_root_key(root),
            "action": action_key,
            "leadership_passed": bool(leadership_passed),
            "mortal_wounds": int(mortal_wounds),
        }

    def desperate_devotion_active(self, unit, *, game=None) -> bool:
        if not self.is_chaos_cult():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("chaos_cult_desperate_devotion_active", False)):
            return False
        expected_phase = str(sr.get("chaos_cult_desperate_devotion_phase", "") or "").strip().upper()
        expected_owner = str(sr.get("chaos_cult_desperate_devotion_turn_owner", "") or "").strip()
        try:
            expected_turn = int(sr.get("chaos_cult_desperate_devotion_turn", 0) or 0)
        except (TypeError, ValueError):
            expected_turn = 0

        current_phase = self._current_phase_name(game=game)
        current_owner = self._current_turn_owner_id(game=game)
        current_turn = self._current_turn(game=game)

        if expected_phase and current_phase and expected_phase != current_phase:
            return False
        if expected_owner and current_owner and expected_owner != current_owner:
            return False
        if expected_turn and current_turn and expected_turn != current_turn:
            return False
        return True

    def desperate_devotion_movement_bonus(self, model=None, unit=None, *, game=None) -> tuple[int, str]:
        target_unit = self._unit_root(unit)
        if target_unit is None:
            target_unit = self._unit_root(getattr(model, "parent_unit", None))
        if target_unit is None:
            return 0, ""
        if not self.desperate_devotion_active(target_unit, game=game):
            return 0, ""
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return 0, ""
        try:
            bonus = int(sr.get("chaos_cult_desperate_devotion_move_bonus", 2) or 0)
        except (TypeError, ValueError):
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("chaos_cult_desperate_devotion_source", "") or "Desperate Devotion").strip() or "Desperate Devotion"
        return int(bonus), source

    def desperate_devotion_charge_roll_bonus(self, unit, *, game=None) -> tuple[int, str]:
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self.desperate_devotion_active(root, game=game):
            return 0, ""
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return 0, ""
        try:
            bonus = int(sr.get("chaos_cult_desperate_devotion_charge_bonus", 2) or 0)
        except (TypeError, ValueError):
            bonus = 0
        if bonus <= 0:
            return 0, ""
        source = str(sr.get("chaos_cult_desperate_devotion_source", "") or "Desperate Devotion").strip() or "Desperate Devotion"
        return int(bonus), source

    @staticmethod
    def _is_traitor_guardsmen_squad(unit) -> bool:
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return name == "traitor guardsmen squad"

    @staticmethod
    def _unit_has_battleline_keyword(unit) -> bool:
        keywords = list(getattr(unit, "keywords", []) or [])
        for keyword in keywords:
            if str(keyword or "").strip().lower() == "battleline":
                return True
        return False

    def apply_chaos_cult_traitor_guardsmen_battleline_keywords(self, unit=None) -> None:
        if not self.is_chaos_cult():
            return
        units = [unit] if unit is not None else list(getattr(self.army, "units", []) or [])
        for root in self._iter_unique_roots(units):
            if not self._is_traitor_guardsmen_squad(root):
                continue
            if self._unit_has_battleline_keyword(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            keywords.append("Battleline")
            root.keywords = keywords

    def validate_detachment_rules(self) -> list[str]:
        if self.is_chaos_cult():
            self.apply_chaos_cult_traitor_guardsmen_battleline_keywords()
        return []

    def raiders_and_reavers_assault_applies(self, unit, weapon_profile=None) -> bool:
        if not self.is_renegade_raiders():
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        if not self._unit_is_heretic_astartes(root):
            return False
        if weapon_profile is None:
            return True
        parent = getattr(weapon_profile, "parent_wargear", None)
        if parent is None:
            return False
        return bool(getattr(parent, "is_ranged", lambda: False)())

    def raiders_and_reavers_ap_bonus(self, model, target_unit, *, game_map=None) -> int:
        if not self.is_renegade_raiders():
            return 0
        if model is None or target_unit is None or not self._model_in_army(model):
            return 0
        if not self._model_is_heretic_astartes(model):
            return 0
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return 0
        within_objective = getattr(unit, "_target_within_objective_range", None)
        if not callable(within_objective):
            return 0
        if bool(within_objective(target_unit, game_map)):
            return 1
        return 0
