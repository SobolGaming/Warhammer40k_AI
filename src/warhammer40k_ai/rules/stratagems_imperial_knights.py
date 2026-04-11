from __future__ import annotations

from typing import Any, Optional
import logging

from ..utility import dice as dice_module
from ..utility.entity_ids import maybe_entity_id

logger = logging.getLogger(__name__)


class ImperialKnightsStratagemMixin:
    @staticmethod
    def _ik_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _ik_sort_key(unit: Any) -> str:
        return str(maybe_entity_id(unit) or "")

    def _ik_detachment_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "imperial_knights_detachments", None)

    def _is_valourstrike_lance(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_valourstrike_lance", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_gate_warden_lance(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_gate_warden_lance", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_questor_forgepact(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_questor_forgepact", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_questoris_companions(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_questoris_companions", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_spearhead_at_arms(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_spearhead_at_arms", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _ik_normalize_name(value: str) -> str:
        return str(value or "").replace("\u2019", "'").strip().upper()

    @staticmethod
    def _ik_phase_name_key(value: Any) -> str:
        return str(value or "").replace("_", " ").strip().lower()

    @staticmethod
    def _ik_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _ik_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _ik_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return True
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(unit, "is_in_reserves", False))

    def _ik_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._ik_is_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _is_imperial_knights_unit(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "_unit_is_imperial_knights", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if callable(has_any_keyword):
            return bool(has_any_keyword("IMPERIAL KNIGHTS"))
        return str(getattr(root, "faction_id", "") or "").strip().upper() == "QI"

    @staticmethod
    def _ik_has_any_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and has_any(keyword):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and has_kw(keyword):
            return True
        return False

    def _ik_is_armiger_unit(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None or not self._is_imperial_knights_unit(root):
            return False
        if self._ik_has_any_keyword(root, "ARMIGER"):
            return True
        return "ARMIGER" in str(getattr(root, "name", "") or "").strip().upper()

    def _ik_is_titanic_unit(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None or not self._is_imperial_knights_unit(root):
            return False
        if self._ik_has_any_keyword(root, "TITANIC"):
            return True
        return bool(getattr(root, "is_titanic", False))

    def _imperial_knights_vow_of_retribution_candidates(self) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    @staticmethod
    def _ik_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    @staticmethod
    def _ik_selected_to_fight_this_phase(unit: Any) -> bool:
        return bool(getattr(getattr(unit, "round_state", None), "fought_this_phase", False))

    def _ik_unit_in_engagement_range(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._ik_root(enemy)
            if enemy_root is None:
                continue
            if not self._ik_on_battlefield(enemy_root, require_targetable=False):
                continue
            if bool(is_within_engagement(root, enemy_root)):
                return True
        return False

    def _imperial_knights_gate_warden_drive_them_out_candidates(self, *, phase_name: str = "") -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        phase_key = self._ik_phase_name_key(phase_name or self._current_phase_name)
        if phase_key not in {"shooting phase", "fight phase"}:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if phase_key == "shooting phase" and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if phase_key == "fight phase" and self._ik_selected_to_fight_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_gate_warden_fortress_candidates(self) -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        mgr = self._ik_detachment_mgr()
        on_line = getattr(mgr, "is_unit_on_dauntless_defensive_line", None) if mgr is not None else None
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None or not callable(on_line):
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._ik_is_titanic_unit(root):
                continue
            if not bool(on_line(root, game=self.game, game_map=getattr(self.game, "map", None) if self.game is not None else None)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_gate_warden_lancebreaker_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        attacker_root = self._ik_root(attacking_unit)
        if attacker_root is None or self._ik_owned_by_player(attacker_root, self.player):
            return []
        mgr = self._ik_detachment_mgr()
        on_line = getattr(mgr, "is_unit_on_dauntless_defensive_line", None) if mgr is not None else None
        if not callable(on_line):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not bool(on_line(root, game=self.game, game_map=getattr(self.game, "map", None) if self.game is not None else None)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_gate_warden_marshal_candidates(self) -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if self._ik_selected_to_move_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_gate_warden_steadfast_candidates(self) -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        mgr = self._ik_detachment_mgr()
        on_line = getattr(mgr, "is_unit_on_dauntless_defensive_line", None) if mgr is not None else None
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None or not callable(on_line):
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if self._ik_selected_to_fight_this_phase(root):
                continue
            if not bool(on_line(root, game=self.game, game_map=getattr(self.game, "map", None) if self.game is not None else None)):
                continue
            if not self._ik_unit_in_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_gate_warden_titanic_bombardment_candidates(self) -> list[Any]:
        if not self._is_gate_warden_lance():
            return []
        mgr = self._ik_detachment_mgr()
        on_line = getattr(mgr, "is_unit_on_dauntless_defensive_line", None) if mgr is not None else None
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None or not callable(on_line):
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_imperial_knights_unit(root) or not self._ik_is_titanic_unit(root):
                continue
            if not bool(on_line(root, game=self.game, game_map=getattr(self.game, "map", None) if self.game is not None else None)):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if not bool(getattr(getattr(root, "round_state", None), "remained_stationary_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_full_tilt_candidates(self) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if self._ik_selected_to_move_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_run_them_through_candidates(self) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if self._ik_selected_to_fight_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    @staticmethod
    def _ik_normalize_weapon_name(value: str) -> str:
        name = str(value or "").replace("\u2019", "'").replace("\u0192?T", "'").strip().lower()
        return " ".join(name.split())

    @classmethod
    def _ik_is_feet_weapon_name(cls, value: str) -> bool:
        name = cls._ik_normalize_weapon_name(value)
        return ("armoured feet" in name) or ("titanic feet" in name)

    @staticmethod
    def _ik_model_is_alive(model: Any) -> bool:
        if model is None:
            return False
        checker = getattr(model, "is_alive", None)
        if callable(checker):
            return bool(checker())
        try:
            return int(getattr(model, "wounds", 1) or 0) > 0
        except (TypeError, ValueError):
            return True

    @classmethod
    def _ik_model_has_feet_melee_weapon(cls, model: Any) -> bool:
        for weapon in list(getattr(model, "wargear", []) or []):
            is_melee = getattr(weapon, "is_melee", None)
            if callable(is_melee):
                if not bool(is_melee()):
                    continue
            elif str(getattr(weapon, "type", "") or "").strip().lower() != "melee":
                continue
            if cls._ik_is_feet_weapon_name(getattr(weapon, "name", "")):
                return True
        return False

    def _ik_select_thunderstomp_model(self, unit: Any, *, requested_model: Any = None) -> Any:
        root = self._ik_root(unit)
        if root is None:
            return None
        models = list(getattr(root, "models", []) or [])
        if not models:
            return None
        if requested_model is not None:
            wanted_id = str(maybe_entity_id(requested_model) or "")
            for model in models:
                model_id = str(maybe_entity_id(model) or "")
                if model is not requested_model and (not wanted_id or not model_id or model_id != wanted_id):
                    continue
                if not self._ik_model_is_alive(model):
                    return None
                if not self._ik_model_has_feet_melee_weapon(model):
                    return None
                return model
            return None
        ordered_models = sorted(models, key=lambda m: str(maybe_entity_id(m) or ""))
        for model in ordered_models:
            if not self._ik_model_is_alive(model):
                continue
            if not self._ik_model_has_feet_melee_weapon(model):
                continue
            return model
        return None

    def _imperial_knights_thunderstomp_candidates(self) -> list[Any]:
        units = self._imperial_knights_run_them_through_candidates()
        out: list[Any] = []
        for root in list(units or []):
            if self._ik_select_thunderstomp_model(root) is None:
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    @staticmethod
    def _ik_unit_in_candidates(root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = str(maybe_entity_id(root) or "")
        for cand in list(candidates or []):
            cand_root = cand
            get_root = getattr(cand, "get_attached_unit_root", None)
            if callable(get_root):
                cand_root = get_root()
            if cand_root is root:
                return True
            cid = str(maybe_entity_id(cand_root) or "")
            if rid and cid and rid == cid:
                return True
        return False

    def _ik_distance_between_units(self, source_unit: Any, target_unit: Any) -> Optional[float]:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        get_dist = getattr(game_map, "get_distance_between_units", None) if game_map is not None else None
        if not callable(get_dist):
            return None
        source_root = self._ik_root(source_unit)
        target_root = self._ik_root(target_unit)
        if source_root is None or target_root is None:
            return None
        try:
            return float(get_dist(source_root, target_root))
        except (TypeError, ValueError):
            return None

    def _imperial_knights_tactical_foil_candidates(
        self,
        *,
        enemy_unit: Any,
        action: str = "",
    ) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        if enemy_unit is None:
            return []
        action_key = str(action or "").strip().lower()
        if action_key and action_key not in {"move", "advance", "fall_back"}:
            return []
        enemy_root = self._ik_root(enemy_unit)
        if enemy_root is None:
            return []
        if self._ik_owned_by_player(enemy_root, self.player):
            return []
        if not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return []

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            dist = self._ik_distance_between_units(root, enemy_root)
            if dist is None or float(dist) > 9.0 + 1e-6:
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _ik_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        enemy_unit: Any = None,
    ) -> bool:
        wanted_name = self._ik_normalize_name(stratagem_name)
        wanted_phase = str(phase_name or "").strip().lower()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name):
                continue
            if self._ik_normalize_name(str(reaction.get("stratagem", "") or "")) != wanted_name:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != wanted_phase:
                continue
            if enemy_unit is not None and self._ik_root(reaction.get("enemy_unit")) is not self._ik_root(enemy_unit):
                continue
            return True
        return False

    def _imperial_knights_let_duty_be_your_shield_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_spearhead_at_arms():
            return []
        attacker_root = self._ik_root(attacking_unit)
        if attacker_root is None:
            return []
        if self._ik_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._ik_is_armiger_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_exemplars_wisdom_friendly_candidates(self, *, source_unit: Any = None) -> list[Any]:
        if not self._is_spearhead_at_arms():
            return []
        source_root = self._ik_root(source_unit)
        if source_root is None:
            return []
        source_id = self._ik_sort_key(source_root)
        if not source_id:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if root is source_root:
                continue
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if not self._ik_is_armiger_unit(root):
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("bondsman_active")):
                continue
            if str(sr.get("bondsman_source_unit_id", "") or "").strip() != source_id:
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_exemplars_wisdom_enemy_candidates(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> list[Any]:
        if not self._is_spearhead_at_arms():
            return []
        attacker_root = self._ik_root(attacker_unit)
        if attacker_root is None or not self._ik_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        if isinstance(hits_by_target, dict):
            for unit, hits in list(hits_by_target.items()):
                try:
                    if int(hits or 0) <= 0:
                        continue
                except (TypeError, ValueError):
                    continue
                root = self._ik_root(unit)
                if root is None:
                    continue
                uid = self._ik_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                if self._ik_owned_by_player(root, self.player):
                    continue
                if not self._ik_on_battlefield(root, require_targetable=True):
                    continue
                out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _queue_imperial_knights_spearhead_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_spearhead_at_arms():
            return
        if self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacker_root = self._ik_root(attacking_unit)
        if attacker_root is None or self._ik_owned_by_player(attacker_root, self.player):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        stratagem = self.get_by_name("LET DUTY BE YOUR SHIELD")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_root,
        ):
            return
        candidates = self._imperial_knights_let_duty_be_your_shield_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_imperial_knights_spearhead_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> None:
        if not self._is_spearhead_at_arms():
            return
        if self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        attacker_root = self._ik_root(attacker_unit)
        if attacker_root is None:
            return
        if not self._ik_owned_by_player(attacker_root, self.player):
            return
        if not self._ik_on_battlefield(attacker_root, require_targetable=True):
            return
        if not self._ik_is_titanic_unit(attacker_root):
            return

        stratagem = self.get_by_name("EXEMPLAR'S WISDOM") or self.get_by_name("EXEMPLAR’S WISDOM")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_root,
        ):
            return
        friendly_candidates = self._imperial_knights_exemplars_wisdom_friendly_candidates(source_unit=attacker_root)
        if not friendly_candidates:
            return
        enemy_candidates = self._imperial_knights_exemplars_wisdom_enemy_candidates(
            attacker_unit=attacker_root,
            hits_by_target=hits_by_target,
        )
        if not enemy_candidates:
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": attacker_root,
            "source_unit": attacker_root,
            "friendly_candidates": friendly_candidates,
            "enemy_candidates": enemy_candidates,
            "hits_by_target": hits_by_target,
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
            payload["target_unit"] = enemy_candidates[0]
        self._queue_reaction(payload)

    def _queue_imperial_knights_gate_warden_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_gate_warden_lance() or player is self.player:
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "CHARGE_PHASE":
            return
        stratagem = self.get_by_name("FORTRESS OF INTIMIDATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._imperial_knights_gate_warden_fortress_candidates()
        if not candidates:
            return
        if self._ik_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Charge phase",
        ):
            return
        payload = {
            "event": "phase_start",
            "phase_name": "Charge phase",
            "phase": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _process_imperial_knights_gate_warden_charge_declared(
        self,
        *,
        charging_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_gate_warden_lance():
            return
        if self._ik_phase_name_key(self._current_phase_name) != "charge phase":
            return
        charging_root = self._ik_root(charging_unit)
        if charging_root is None or self._ik_owned_by_player(charging_root, self.player):
            return
        if not self._ik_on_battlefield(charging_root, require_targetable=False):
            return
        mgr = self._ik_detachment_mgr()
        effect_state = getattr(mgr, "_gate_warden_temporary_effect_state", None) if mgr is not None else None
        if not callable(effect_state):
            return
        active_target = None
        for unit in list(target_units or []):
            target_root = self._ik_root(unit)
            if target_root is None or not self._ik_owned_by_player(target_root, self.player):
                continue
            if not self._ik_on_battlefield(target_root, require_targetable=True):
                continue
            effect_root, effect_rules = effect_state(
                target_root,
                prefix="gate_warden_fortress_of_intimidation",
                game=self.game,
            )
            if effect_root is None or effect_rules is None:
                continue
            active_target = effect_root
            break
        if active_target is None:
            return
        sr = getattr(charging_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["battle_shock_test_modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0) - 1
        reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
        reasons.append("FORTRESS OF INTIMIDATION")
        sr["battle_shock_test_modifier_reasons"] = reasons
        charging_root.special_rules = sr
        take_test = getattr(charging_root, "take_battle_shock_test", None)
        if callable(take_test):
            take_test(int(getattr(self.game, "turn", 0) or 0))

    def _queue_imperial_knights_gate_warden_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_gate_warden_lance():
            return
        if self._ik_phase_name_key(self._current_phase_name) != "fight phase":
            return
        attacker_root = self._ik_root(attacking_unit)
        if attacker_root is None or self._ik_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("LANCEBREAKER")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._imperial_knights_gate_warden_lancebreaker_candidates(
            attacking_unit=attacker_root,
            target_units=list(target_units or []),
        )
        if not candidates:
            return
        if self._ik_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacker_root,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_imperial_knights_spearhead_phase_end_effects(self, *, phase: Any = None) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if phase_name == "MOVEMENT_PHASE":
                exp = str(sr.get("gate_warden_marshal_the_defence_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_marshal_the_defence_active") is True and (not exp or exp == phase_name):
                    remove_modifiers = getattr(root, "remove_characteristic_modifiers_by_source", None)
                    if callable(remove_modifiers):
                        remove_modifiers("stratagem:imperial_knights_marshal_the_defence")
                    for key in (
                        "gate_warden_marshal_the_defence_active",
                        "gate_warden_marshal_the_defence_expires_phase",
                        "gate_warden_marshal_the_defence_turn_owner",
                        "gate_warden_marshal_the_defence_turn",
                        "gate_warden_marshal_the_defence_source",
                    ):
                        sr.pop(key, None)
            if phase_name == "SHOOTING_PHASE":
                exp = str(sr.get("imperial_knights_exemplars_wisdom_expires_phase", "") or "").strip().upper()
                if sr.get("imperial_knights_exemplars_wisdom_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "imperial_knights_exemplars_wisdom_active",
                        "imperial_knights_exemplars_wisdom_ap_bonus",
                        "imperial_knights_exemplars_wisdom_target_id",
                        "imperial_knights_exemplars_wisdom_source_unit_id",
                        "imperial_knights_exemplars_wisdom_expires_phase",
                        "imperial_knights_exemplars_wisdom_turn_owner",
                        "imperial_knights_exemplars_wisdom_turn",
                        "imperial_knights_exemplars_wisdom_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("gate_warden_drive_them_out_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_drive_them_out_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "gate_warden_drive_them_out_active",
                        "gate_warden_drive_them_out_crit_hit_threshold",
                        "gate_warden_drive_them_out_expires_phase",
                        "gate_warden_drive_them_out_turn_owner",
                        "gate_warden_drive_them_out_turn",
                        "gate_warden_drive_them_out_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("gate_warden_titanic_bombardment_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_titanic_bombardment_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "gate_warden_titanic_bombardment_active",
                        "gate_warden_titanic_bombardment_sustained_hits",
                        "gate_warden_titanic_bombardment_expires_phase",
                        "gate_warden_titanic_bombardment_turn_owner",
                        "gate_warden_titanic_bombardment_turn",
                        "gate_warden_titanic_bombardment_source",
                    ):
                        sr.pop(key, None)
            if phase_name == "FIGHT_PHASE":
                exp = str(sr.get("gate_warden_drive_them_out_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_drive_them_out_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "gate_warden_drive_them_out_active",
                        "gate_warden_drive_them_out_crit_hit_threshold",
                        "gate_warden_drive_them_out_expires_phase",
                        "gate_warden_drive_them_out_turn_owner",
                        "gate_warden_drive_them_out_turn",
                        "gate_warden_drive_them_out_source",
                    ):
                        sr.pop(key, None)
                exp = str(sr.get("gate_warden_steadfast_superiority_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_steadfast_superiority_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "gate_warden_steadfast_superiority_active",
                        "gate_warden_steadfast_superiority_expires_phase",
                        "gate_warden_steadfast_superiority_turn_owner",
                        "gate_warden_steadfast_superiority_turn",
                        "gate_warden_steadfast_superiority_source",
                    ):
                        sr.pop(key, None)
            if phase_name == "CHARGE_PHASE":
                exp = str(sr.get("gate_warden_fortress_of_intimidation_expires_phase", "") or "").strip().upper()
                if sr.get("gate_warden_fortress_of_intimidation_active") is True and (not exp or exp == phase_name):
                    for key in (
                        "gate_warden_fortress_of_intimidation_active",
                        "gate_warden_fortress_of_intimidation_battle_shock_modifier",
                        "gate_warden_fortress_of_intimidation_expires_phase",
                        "gate_warden_fortress_of_intimidation_turn_owner",
                        "gate_warden_fortress_of_intimidation_turn",
                        "gate_warden_fortress_of_intimidation_source",
                    ):
                        sr.pop(key, None)
            root.special_rules = sr

    def _queue_imperial_knights_valourstrike_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_valourstrike_lance():
            return
        if unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "fall_back"}:
            return
        enemy_root = self._ik_root(unit)
        if enemy_root is None:
            return
        if self._ik_owned_by_player(enemy_root, self.player):
            return
        if not self._ik_is_alive(enemy_root) or not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        stratagem = self.get_by_name("TACTICAL FOIL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            enemy_unit=enemy_root,
        ):
            return

        candidates = self._imperial_knights_tactical_foil_candidates(enemy_unit=enemy_root, action=action_key)
        if not candidates:
            return

        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "action": action_key,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _ik_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return bool(
            self.player.spend_command_points(
                int(cp_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _ik_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u:
                used.add(name_u)
            normalized = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
            if normalized:
                used.add(normalized)

    def _use_imperial_knights_valourstrike_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = self._ik_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u == "DRIVE THEM OUT!":
            return self._use_gate_warden_drive_them_out(stratagem, **kwargs)
        if name_u == "FORTRESS OF INTIMIDATION":
            return self._use_gate_warden_fortress_of_intimidation(stratagem, **kwargs)
        if name_u == "LANCEBREAKER":
            return self._use_gate_warden_lancebreaker(stratagem, **kwargs)
        if name_u == "MARSHAL THE DEFENCE":
            return self._use_gate_warden_marshal_the_defence(stratagem, **kwargs)
        if name_u == "STEADFAST SUPERIORITY":
            return self._use_gate_warden_steadfast_superiority(stratagem, **kwargs)
        if name_u == "TITANIC BOMBARDMENT":
            return self._use_gate_warden_titanic_bombardment(stratagem, **kwargs)
        if name_u == "VOW OF RETRIBUTION":
            return self._use_valourstrike_vow_of_retribution(stratagem, **kwargs)
        if name_u == "FULL TILT":
            return self._use_valourstrike_full_tilt(stratagem, **kwargs)
        if name_u == "RUN THEM THROUGH!":
            return self._use_valourstrike_run_them_through(stratagem, **kwargs)
        if name_u == "THUNDERSTOMP":
            return self._use_valourstrike_thunderstomp(stratagem, **kwargs)
        if name_u == "TACTICAL FOIL":
            return self._use_valourstrike_tactical_foil(stratagem, **kwargs)
        if name_u == "LET DUTY BE YOUR SHIELD":
            return self._use_spearhead_let_duty_be_your_shield(stratagem, **kwargs)
        if name_u == "EXEMPLAR'S WISDOM":
            return self._use_spearhead_exemplars_wisdom(stratagem, **kwargs)
        return None

    def _use_gate_warden_drive_them_out(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: DRIVE THEM OUT!: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_key == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: DRIVE THEM OUT!: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DRIVE THEM OUT!: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: DRIVE THEM OUT!: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: DRIVE THEM OUT!: target must be an IMPERIAL KNIGHTS unit")
            return False
        eligible = candidates or self._imperial_knights_gate_warden_drive_them_out_candidates(phase_name=phase_key)
        if eligible and not self._ik_unit_in_candidates(root, eligible):
            logger.error("ERROR: DRIVE THEM OUT!: target is not currently eligible")
            return False
        if phase_key == "shooting phase" and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: DRIVE THEM OUT!: target has already shot this phase")
            return False
        if phase_key == "fight phase" and self._ik_selected_to_fight_this_phase(root):
            logger.error("ERROR: DRIVE THEM OUT!: target has already fought this phase")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["gate_warden_drive_them_out_active"] = True
        sr["gate_warden_drive_them_out_crit_hit_threshold"] = 5
        sr["gate_warden_drive_them_out_expires_phase"] = "SHOOTING_PHASE" if phase_key == "shooting phase" else "FIGHT_PHASE"
        sr["gate_warden_drive_them_out_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["gate_warden_drive_them_out_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["gate_warden_drive_them_out_source"] = str(getattr(stratagem, "name", "") or "DRIVE THEM OUT!")
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DRIVE THEM OUT!: %s scores critical hits on 5+ when attacking enemies on the defensive line this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_gate_warden_fortress_of_intimidation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._ik_normalize_name(str(reaction.get("stratagem", "") or "")) != "FORTRESS OF INTIMIDATION":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FORTRESS OF INTIMIDATION: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "charge phase":
            logger.error("ERROR: FORTRESS OF INTIMIDATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: FORTRESS OF INTIMIDATION: not opponent's Charge phase")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: FORTRESS OF INTIMIDATION: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._ik_is_titanic_unit(root):
            logger.error("ERROR: FORTRESS OF INTIMIDATION: target must be a Titanic unit")
            return False
        eligible = candidates or self._imperial_knights_gate_warden_fortress_candidates()
        if eligible and not self._ik_unit_in_candidates(root, eligible):
            logger.error("ERROR: FORTRESS OF INTIMIDATION: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["gate_warden_fortress_of_intimidation_active"] = True
        sr["gate_warden_fortress_of_intimidation_battle_shock_modifier"] = -1
        sr["gate_warden_fortress_of_intimidation_expires_phase"] = "CHARGE_PHASE"
        sr["gate_warden_fortress_of_intimidation_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["gate_warden_fortress_of_intimidation_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["gate_warden_fortress_of_intimidation_source"] = str(
            getattr(stratagem, "name", "") or "FORTRESS OF INTIMIDATION"
        )
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FORTRESS OF INTIMIDATION: enemies charging %s take Battle-shock tests at -1 this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_gate_warden_lancebreaker(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if unit is None or attacking_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._ik_normalize_name(str(reaction.get("stratagem", "") or "")) != "LANCEBREAKER":
                    continue
                unit = unit or reaction.get("unit") or reaction.get("target_unit")
                attacking_unit = attacking_unit or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: LANCEBREAKER: no target unit provided")
            return False
        root = self._ik_root(unit)
        attacker_root = self._ik_root(attacking_unit)
        if root is None or attacker_root is None:
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "fight phase":
            logger.error("ERROR: LANCEBREAKER: wrong phase")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: LANCEBREAKER: target unit is not yours")
            return False
        if self._ik_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: LANCEBREAKER: attacking unit must be enemy")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._ik_on_battlefield(attacker_root, require_targetable=False):
            return False
        eligible = candidates or self._imperial_knights_gate_warden_lancebreaker_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if eligible and not self._ik_unit_in_candidates(root, eligible):
            logger.error("ERROR: LANCEBREAKER: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        self._append_defensive_effect(
            root,
            "defensive_wound_mods",
            {
                "value": 1,
                "attack_type": "any",
                "expires_phase": "FIGHT_PHASE",
                "source": str(getattr(stratagem, "name", "") or "LANCEBREAKER"),
                "requires_strength_gt_toughness": True,
            },
        )
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: LANCEBREAKER: %s imposes -1 to wound against stronger attacks this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_gate_warden_marshal_the_defence(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "movement phase":
            logger.error("ERROR: MARSHAL THE DEFENCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MARSHAL THE DEFENCE: not your Movement phase")
            return False
        selected_units = kwargs.get("selected_units") or kwargs.get("units") or kwargs.get("target_units")
        if selected_units is None:
            single_unit = kwargs.get("unit") or kwargs.get("target_unit")
            selected_units = [single_unit] if single_unit is not None else []
        selected_roots_raw = list(selected_units or [])
        candidates = list(kwargs.get("candidates") or self._imperial_knights_gate_warden_marshal_candidates())
        selected_roots: list[Any] = []
        seen: set[str] = set()
        for unit in selected_roots_raw:
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            selected_roots.append(root)
        if not selected_roots and len(candidates) == 1:
            selected_roots = [candidates[0]]
        if not selected_roots:
            logger.error("ERROR: MARSHAL THE DEFENCE: no target units provided")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: MARSHAL THE DEFENCE: may target up to two units")
            return False
        for root in selected_roots:
            if not self._ik_unit_in_candidates(root, candidates):
                logger.error("ERROR: MARSHAL THE DEFENCE: one or more selected units are not eligible")
                return False
        if not self._ik_spend_cp(stratagem, target_unit=selected_roots[0]):
            return False
        from ..utility.modifiers import Modifier, ModifierOp

        for root in selected_roots:
            remove_modifiers = getattr(root, "remove_characteristic_modifiers_by_source", None)
            if callable(remove_modifiers):
                remove_modifiers("stratagem:imperial_knights_marshal_the_defence")
            add_modifier = getattr(root, "add_characteristic_modifier", None)
            if callable(add_modifier):
                add_modifier(
                    "movement",
                    Modifier(ModifierOp.ADD, 3, source="stratagem:imperial_knights_marshal_the_defence"),
                )
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["gate_warden_marshal_the_defence_active"] = True
            sr["gate_warden_marshal_the_defence_expires_phase"] = "MOVEMENT_PHASE"
            sr["gate_warden_marshal_the_defence_turn_owner"] = str(getattr(self.player, "id", "") or "")
            sr["gate_warden_marshal_the_defence_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
            sr["gate_warden_marshal_the_defence_source"] = str(
                getattr(stratagem, "name", "") or "MARSHAL THE DEFENCE"
            )
            root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MARSHAL THE DEFENCE: %d unit(s) gain +3\" Move this phase.",
            len(selected_roots),
        )
        return True

    def _use_gate_warden_steadfast_superiority(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "fight phase":
            logger.error("ERROR: STEADFAST SUPERIORITY: wrong phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._imperial_knights_gate_warden_steadfast_candidates())
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: STEADFAST SUPERIORITY: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: STEADFAST SUPERIORITY: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["gate_warden_steadfast_superiority_active"] = True
        sr["gate_warden_steadfast_superiority_expires_phase"] = "FIGHT_PHASE"
        sr["gate_warden_steadfast_superiority_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["gate_warden_steadfast_superiority_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["gate_warden_steadfast_superiority_source"] = str(
            getattr(stratagem, "name", "") or "STEADFAST SUPERIORITY"
        )
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: STEADFAST SUPERIORITY: %s re-rolls melee Hit rolls this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_gate_warden_titanic_bombardment(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_gate_warden_lance():
            return False
        phase_key = self._ik_phase_name_key(kwargs.get("phase_name") or self._current_phase_name)
        if phase_key != "shooting phase":
            logger.error("ERROR: TITANIC BOMBARDMENT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: TITANIC BOMBARDMENT: not your Shooting phase")
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or self._imperial_knights_gate_warden_titanic_bombardment_candidates())
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TITANIC BOMBARDMENT: no target unit provided")
            return False
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: TITANIC BOMBARDMENT: target is not currently eligible")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["gate_warden_titanic_bombardment_active"] = True
        sr["gate_warden_titanic_bombardment_sustained_hits"] = 2
        sr["gate_warden_titanic_bombardment_expires_phase"] = "SHOOTING_PHASE"
        sr["gate_warden_titanic_bombardment_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["gate_warden_titanic_bombardment_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["gate_warden_titanic_bombardment_source"] = str(
            getattr(stratagem, "name", "") or "TITANIC BOMBARDMENT"
        )
        root.special_rules = sr
        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TITANIC BOMBARDMENT: %s gains [SUSTAINED HITS 2] on ranged weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_spearhead_let_duty_be_your_shield(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_spearhead_at_arms():
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacker_unit = kwargs.get("attacker_unit") or kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._ik_normalize_name(str(reaction.get("stratagem", "") or "")) != "LET DUTY BE YOUR SHIELD":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                attacker_unit = attacker_unit or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: no target unit provided")
            return False
        if attacker_unit is None:
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: missing attacking unit context")
            return False

        root = self._ik_root(unit)
        attacker_root = self._ik_root(attacker_unit)
        if root is None or attacker_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: not opponent's Shooting phase")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: target is not currently eligible")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._ik_is_armiger_unit(root):
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: target must be an Armiger unit")
            return False
        if self._ik_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: LET DUTY BE YOUR SHIELD: attacking unit must be enemy")
            return False
        if not self._ik_on_battlefield(attacker_root, require_targetable=False):
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False
        if not self._apply_armour_of_contempt(root, attacker_root, amount=1):
            return False

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: LET DUTY BE YOUR SHIELD: %s worsens AP by 1 against attacks from %s.",
            getattr(root, "name", "Unit"),
            getattr(attacker_root, "name", "Enemy unit"),
        )
        return True

    def _use_spearhead_exemplars_wisdom(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_spearhead_at_arms():
            return False

        source_unit = kwargs.get("source_unit") or kwargs.get("unit")
        selected_units = kwargs.get("selected_units") or kwargs.get("units") or kwargs.get("friendly_units")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_unit")
        friendly_candidates = list(kwargs.get("friendly_candidates") or [])
        enemy_candidates = list(kwargs.get("enemy_candidates") or kwargs.get("candidates") or [])
        hits_by_target = kwargs.get("hits_by_target")
        if source_unit is None or not friendly_candidates or not enemy_candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._ik_normalize_name(str(reaction.get("stratagem", "") or "")) != "EXEMPLAR'S WISDOM":
                    continue
                source_unit = source_unit or reaction.get("source_unit") or reaction.get("unit")
                if selected_units is None:
                    selected_units = reaction.get("selected_units") or reaction.get("friendly_units")
                enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("target_unit")
                if not friendly_candidates:
                    friendly_candidates = list(reaction.get("friendly_candidates") or [])
                if not enemy_candidates:
                    enemy_candidates = list(reaction.get("enemy_candidates") or reaction.get("candidates") or [])
                if hits_by_target is None:
                    hits_by_target = reaction.get("hits_by_target")
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        source_root = self._ik_root(source_unit)
        if source_root is None:
            logger.error("ERROR: EXEMPLAR'S WISDOM: missing Titanic source unit")
            return False
        selected_roots_raw = list(selected_units) if isinstance(selected_units, (list, tuple, set)) else ([selected_units] if selected_units is not None else [])
        selected_roots: list[Any] = []
        seen_selected: set[str] = set()
        for unit in list(selected_roots_raw or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen_selected:
                continue
            if uid:
                seen_selected.add(uid)
            selected_roots.append(root)
        if not selected_roots and len(friendly_candidates) == 1:
            selected_roots = [friendly_candidates[0]]
        enemy_root = self._ik_root(enemy_unit)
        if enemy_root is None and len(enemy_candidates) == 1:
            enemy_root = self._ik_root(enemy_candidates[0])
        if not selected_roots:
            logger.error("ERROR: EXEMPLAR'S WISDOM: no bonded Armiger targets selected")
            return False
        if enemy_root is None:
            logger.error("ERROR: EXEMPLAR'S WISDOM: no enemy target selected")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: EXEMPLAR'S WISDOM: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: EXEMPLAR'S WISDOM: not your Shooting phase")
            return False
        if not self._ik_owned_by_player(source_root, self.player):
            logger.error("ERROR: EXEMPLAR'S WISDOM: source unit is not yours")
            return False
        if not self._ik_on_battlefield(source_root, require_targetable=True):
            return False
        if not self._ik_is_titanic_unit(source_root):
            logger.error("ERROR: EXEMPLAR'S WISDOM: source must be a Titanic Imperial Knights unit")
            return False
        if not bool(getattr(getattr(source_root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: EXEMPLAR'S WISDOM: source must have just shot")
            return False
        eligible_friendly = friendly_candidates or self._imperial_knights_exemplars_wisdom_friendly_candidates(source_unit=source_root)
        for root in list(selected_roots):
            if not self._ik_unit_in_candidates(root, eligible_friendly):
                logger.error("ERROR: EXEMPLAR'S WISDOM: one or more selected Armiger units are not eligible")
                return False
        if self._ik_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: EXEMPLAR'S WISDOM: enemy target is invalid")
            return False
        eligible_enemy = enemy_candidates or self._imperial_knights_exemplars_wisdom_enemy_candidates(
            attacker_unit=source_root,
            hits_by_target=hits_by_target,
        )
        if eligible_enemy and not self._ik_unit_in_candidates(enemy_root, eligible_enemy):
            logger.error("ERROR: EXEMPLAR'S WISDOM: enemy target was not hit by the Titanic model")
            return False
        if not self._ik_on_battlefield(enemy_root, require_targetable=True):
            return False
        if not self._ik_spend_cp(stratagem, target_unit=source_root):
            return False

        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        enemy_id = self._ik_sort_key(enemy_root)
        source_id = self._ik_sort_key(source_root)
        for root in list(selected_roots):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["imperial_knights_exemplars_wisdom_active"] = True
            sr["imperial_knights_exemplars_wisdom_ap_bonus"] = 1
            sr["imperial_knights_exemplars_wisdom_target_id"] = enemy_id
            sr["imperial_knights_exemplars_wisdom_source_unit_id"] = source_id
            sr["imperial_knights_exemplars_wisdom_expires_phase"] = "SHOOTING_PHASE"
            sr["imperial_knights_exemplars_wisdom_turn_owner"] = owner_id
            sr["imperial_knights_exemplars_wisdom_turn"] = turn
            sr["imperial_knights_exemplars_wisdom_source"] = str(getattr(stratagem, "name", "") or "EXEMPLAR'S WISDOM")
            root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: EXEMPLAR'S WISDOM: %d Armiger unit(s) improve AP by 1 against %s this phase.",
            len(selected_roots),
            getattr(enemy_root, "name", "Enemy unit"),
        )
        return True

    def _use_valourstrike_vow_of_retribution(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: VOW OF RETRIBUTION: wrong phase")
            return False

        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: VOW OF RETRIBUTION: not your Shooting phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: VOW OF RETRIBUTION: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False

        candidates = self._imperial_knights_vow_of_retribution_candidates()
        if root not in candidates:
            logger.error(
                "ERROR: VOW OF RETRIBUTION: target must be an IMPERIAL KNIGHTS unit on the battlefield that has not shot"
            )
            return False

        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["vow_of_retribution_active"] = True
        sr["vow_of_retribution_expires_phase"] = "SHOOTING_PHASE"
        sr["vow_of_retribution_owner"] = str(getattr(self.player, "id", "") or "")
        sr["vow_of_retribution_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["vow_of_retribution_source"] = str(getattr(stratagem, "name", "") or "VOW OF RETRIBUTION")
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: VOW OF RETRIBUTION: {getattr(root, 'name', 'Unit')} gains Lethal Hits with ranged weapons this phase."
        )
        return True

    def _use_valourstrike_full_tilt(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: FULL TILT: wrong phase")
            return False

        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FULL TILT: not your Movement phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FULL TILT: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: FULL TILT: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: FULL TILT: target must be an IMPERIAL KNIGHTS unit")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: FULL TILT: target is not currently eligible")
            return False
        if self._ik_selected_to_move_this_phase(root):
            logger.error("ERROR: FULL TILT: target has already been selected to move this phase")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        from ..utility.modifiers import Modifier, ModifierOp

        root.remove_characteristic_modifiers_by_source("stratagem:imperial_knights_full_tilt")
        root.add_characteristic_modifier(
            "movement",
            Modifier(ModifierOp.ADD, 2, source="stratagem:imperial_knights_full_tilt"),
        )

        effect_tag = "stratagem:imperial_knights_full_tilt"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        adv_mods = list(sr.get("advance_roll_modifiers", []) or [])
        adv_mods = [
            entry
            for entry in adv_mods
            if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == effect_tag)
        ]
        adv_mods.append(
            {
                "value": 2,
                "source": str(getattr(stratagem, "name", "") or "FULL TILT"),
                "tag": effect_tag,
            }
        )
        sr["advance_roll_modifiers"] = adv_mods
        sr["full_tilt_active"] = True
        sr["full_tilt_expires_phase"] = "MOVEMENT_PHASE"
        sr["full_tilt_owner"] = str(getattr(self.player, "id", "") or "")
        sr["full_tilt_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["full_tilt_source"] = str(getattr(stratagem, "name", "") or "FULL TILT")
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FULL TILT: %s gains +2\" Move and +2 to Advance rolls this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_valourstrike_run_them_through(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: RUN THEM THROUGH!: wrong phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RUN THEM THROUGH!: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: RUN THEM THROUGH!: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: RUN THEM THROUGH!: target must be an IMPERIAL KNIGHTS unit")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: RUN THEM THROUGH!: target is not currently eligible")
            return False
        if self._ik_selected_to_fight_this_phase(root):
            logger.error("ERROR: RUN THEM THROUGH!: target has already been selected to fight this phase")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_knights_run_them_through_active"] = True
        sr["imperial_knights_run_them_through_expires_phase"] = "FIGHT_PHASE"
        sr["imperial_knights_run_them_through_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["imperial_knights_run_them_through_source"] = str(getattr(stratagem, "name", "") or "RUN THEM THROUGH!")
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RUN THEM THROUGH!: %s gains [LANCE] on melee weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_valourstrike_thunderstomp(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: THUNDERSTOMP: wrong phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        model = kwargs.get("model") or kwargs.get("target_model")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and model is not None:
            unit = getattr(model, "parent_unit", None)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: THUNDERSTOMP: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: THUNDERSTOMP: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: THUNDERSTOMP: target must be an IMPERIAL KNIGHTS model")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: THUNDERSTOMP: target is not currently eligible")
            return False
        if self._ik_selected_to_fight_this_phase(root):
            logger.error("ERROR: THUNDERSTOMP: target has already been selected to fight this phase")
            return False

        chosen_model = self._ik_select_thunderstomp_model(root, requested_model=model)
        if chosen_model is None:
            logger.error("ERROR: THUNDERSTOMP: selected model must be an IMPERIAL KNIGHTS model with armoured/titanic feet")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_knights_thunderstomp_active"] = True
        sr["imperial_knights_thunderstomp_expires_phase"] = "FIGHT_PHASE"
        sr["imperial_knights_thunderstomp_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["imperial_knights_thunderstomp_source"] = str(getattr(stratagem, "name", "") or "THUNDERSTOMP")
        sr["imperial_knights_thunderstomp_model_id"] = str(maybe_entity_id(chosen_model) or "")
        sr["imperial_knights_thunderstomp_armoured_feet_attacks"] = 8
        sr["imperial_knights_thunderstomp_titanic_feet_attacks"] = 12
        sr["imperial_knights_thunderstomp_ap_bonus"] = 1
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: THUNDERSTOMP: %s gains enhanced Armoured/Titanic Feet profiles this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_valourstrike_tactical_foil(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("moving_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "TACTICAL FOIL":
                    continue
                from_pending = True
                unit = reaction.get("unit") or reaction.get("target_unit")
                enemy_unit = enemy_unit or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("action", reaction.get("action"))
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TACTICAL FOIL: no target unit provided")
            return False

        root = self._ik_root(unit)
        enemy_root = self._ik_root(enemy_unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: TACTICAL FOIL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: TACTICAL FOIL: not opponent's Movement phase")
            return False
        action_key = str(kwargs.get("action") or kwargs.get("trigger") or "").strip().lower()
        if action_key and action_key not in {"move", "advance", "fall_back"}:
            logger.error("ERROR: TACTICAL FOIL: invalid trigger action")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: TACTICAL FOIL: target is not currently eligible")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: TACTICAL FOIL: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: TACTICAL FOIL: target must be an IMPERIAL KNIGHTS unit")
            return False
        if enemy_root is None:
            logger.error("ERROR: TACTICAL FOIL: missing enemy trigger unit")
            return False
        if self._ik_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: TACTICAL FOIL: trigger unit is not enemy")
            return False
        if not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return False
        dist = self._ik_distance_between_units(root, enemy_root)
        if dist is None or float(dist) > 9.0 + 1e-6:
            logger.error("ERROR: TACTICAL FOIL: target must be within 9\" of the enemy unit")
            return False
        if not from_pending and not action_key:
            logger.error("ERROR: TACTICAL FOIL: missing movement trigger context")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: TACTICAL FOIL: reactive move queue is unavailable")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        move_max = max(0, int(dice_module.get_roll("D6") or 0))
        req = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(move_max),
            kind="tactical_foil",
            movement_type="reactive",
            source=stratagem.name,
            moving_unit=enemy_root,
        )
        if req is None:
            logger.error("ERROR: TACTICAL FOIL: failed to queue reactive move")
            return False

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TACTICAL FOIL: %s can make a Normal move up to %d\".",
            getattr(root, "name", "Unit"),
            int(move_max),
        )
        return True
