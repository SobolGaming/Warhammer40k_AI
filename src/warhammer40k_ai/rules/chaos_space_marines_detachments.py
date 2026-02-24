from __future__ import annotations

from typing import Iterable

from ..utility.dice import get_roll
from .detachment_manager import DetachmentManagerBase


class ChaosSpaceMarinesDetachmentManager(DetachmentManagerBase):
    faction_id = "CSM"

    DETACHMENT_CABAL_OF_CHAOS = "Cabal of Chaos"
    DETACHMENT_CHAOS_CULT = "Chaos Cult"
    DETACHMENT_RENEGADE_RAIDERS = "Renegade Raiders"
    _DESPERATE_DEVOTION_ALLOWED_ACTIONS = {"move", "advance", "charge"}

    def is_cabal_of_chaos(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_CABAL_OF_CHAOS)

    def is_chaos_cult(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_CHAOS_CULT)

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
