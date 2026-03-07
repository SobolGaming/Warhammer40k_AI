from __future__ import annotations

from typing import Optional

from ..utility.ability_support import ABILITY_FOR_THE_GREATER_GOOD, army_has_ability_id
from ..utility.entity_ids import get_entity_id


class ForTheGreaterGoodManager:
    """
    T'au Empire army rule: For the Greater Good.

    - Select Observer units at the start of your Shooting phase.
    - Each Observer marks one visible enemy as Spotted until end of phase.
    - Guided units (non-Observers with the ability) gain +1 BS vs Spotted targets.
    - If the Observer had MARKERLIGHT, Guided attacks also gain Ignores Cover.
    """
    _COORDINATED_EXPLOITATION_FLAG = "enhancement_coordinated_exploitation"
    _COORDINATED_EXPLOITATION_ID = "000008811002"
    _COORDINATED_EXPLOITATION_NAME = "coordinated exploitation"
    _COORDINATED_EXPLOITATION_VALUE_KEY = "enhancement_coordinated_exploitation_sustained_hits_value"

    def __init__(self, army=None):
        self.army = army
        self._observer_unit_ids: set[str] = set()
        self._observer_to_target: dict[str, str] = {}
        self._spotted_by: dict[str, str] = {}
        self._spotted_markerlight: dict[str, bool] = {}
        self._spotted_coordinated_exploitation: dict[str, int] = {}

    def reset_for_phase(self) -> None:
        self._observer_unit_ids = set()
        self._observer_to_target = {}
        self._spotted_by = {}
        self._spotted_markerlight = {}
        self._spotted_coordinated_exploitation = {}

    def on_shooting_phase_start(self, *, game=None, player=None) -> None:
        self.reset_for_phase()

    def on_shooting_phase_end(self, *, game=None, player=None) -> None:
        self.reset_for_phase()

    def _army_has_ftgg(self) -> bool:
        army = self.army
        if army is None:
            return False
        try:
            faction_id = str(getattr(army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "TAU":
            return False
        if army_has_ability_id(army, ABILITY_FOR_THE_GREATER_GOOD):
            return True
        if not faction_id:
            for unit in list(getattr(army, "units", []) or []):
                if self._unit_has_ftgg(unit):
                    return True
        return False

    @staticmethod
    def _unit_id(unit) -> str:
        if unit is None:
            return ""
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        return get_entity_id(root)

    @staticmethod
    def _unit_is_alive(unit) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive):
                return bool(unit.is_alive())
        except Exception:
            return True
        try:
            return bool(getattr(unit, "is_alive", True))
        except Exception:
            return True

    @staticmethod
    def _unit_is_embarked(unit) -> bool:
        if unit is None:
            return False
        try:
            return bool(getattr(unit, "is_embarked", False))
        except Exception:
            return False

    @staticmethod
    def _unit_is_battle_shocked(unit) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "is_battle_shocked") and callable(unit.is_battle_shocked):
                return bool(unit.is_battle_shocked())
        except Exception:
            return False
        try:
            return bool(getattr(unit, "is_battle_shocked", False))
        except Exception:
            return False

    @staticmethod
    def _unit_is_fortification(unit) -> bool:
        if unit is None:
            return False
        try:
            return bool(getattr(unit, "is_fortification", False))
        except Exception:
            return False

    @staticmethod
    def _unit_has_markerlight(unit) -> bool:
        if unit is None:
            return False
        try:
            return bool(unit.has_any_keyword("MARKERLIGHT"))
        except Exception:
            return False

    @staticmethod
    def _unit_has_named_ability(unit, ability_name: str) -> bool:
        if unit is None:
            return False
        needle = str(ability_name or "").strip().lower()
        if not needle:
            return False
        try:
            for ab in list(getattr(unit, "possible_abilities", []) or []):
                if str(getattr(ab, "name", "") or "").strip().lower() == needle:
                    return True
        except Exception:
            return False
        return False

    def _unit_has_ftgg(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_named_ability(unit, "for the greater good"):
            return True
        try:
            if unit.has_any_keyword("T'AU EMPIRE"):
                return True
            if unit.has_any_keyword("TAU EMPIRE"):
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _attached_root(unit):
        if unit is None:
            return None
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        return root

    @staticmethod
    def _enhancement_bearer_alive(unit) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "") if isinstance(sr, dict) else ""
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                if model_id != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                return bool(alive_attr() if callable(alive_attr) else alive_attr)
            return False
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            return get_bearer() is not None
        return False

    def _coordinated_exploitation_sustained_value(self, observer) -> int:
        root = self._attached_root(observer)
        if root is None:
            return 0
        leaders = list(getattr(root, "attached_leaders", []) or [])
        if not leaders:
            return 0

        checker = getattr(root, "_attached_unit_has_active_enhancement", None)
        if callable(checker):
            if not bool(
                checker(
                    self._COORDINATED_EXPLOITATION_FLAG,
                    enhancement_id=self._COORDINATED_EXPLOITATION_ID,
                    enhancement_name=self._COORDINATED_EXPLOITATION_NAME,
                )
            ):
                return 0

        best = 0
        for leader in leaders:
            sr = getattr(leader, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            has_rule = bool(sr.get(self._COORDINATED_EXPLOITATION_FLAG))
            if not has_rule:
                enh = getattr(leader, "enhancement", None)
                if enh is not None:
                    enh_id = str(getattr(enh, "id", "") or "").strip()
                    enh_name = str(getattr(enh, "name", "") or "").strip().lower()
                    has_rule = bool(
                        enh_id == self._COORDINATED_EXPLOITATION_ID
                        or enh_name == self._COORDINATED_EXPLOITATION_NAME
                    )
            if not has_rule:
                continue
            if not self._enhancement_bearer_alive(leader):
                continue
            try:
                val = int(sr.get(self._COORDINATED_EXPLOITATION_VALUE_KEY, 1) or 1)
            except Exception:
                val = 1
            best = max(best, max(1, val))
        return int(best)

    def _unit_is_visible_to_unit(self, observer, target, *, game=None) -> bool:
        if observer is None or target is None:
            return False
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return True
        try:
            observer_models = list(getattr(observer, "models", []) or [])
            target_models = list(getattr(target, "models", []) or [])
        except Exception:
            return True
        if not observer_models or not target_models:
            return True
        can_see = getattr(game_map, "can_model_see_model", None)
        if not callable(can_see):
            return True
        for om in observer_models:
            try:
                if not getattr(om, "is_alive", True):
                    continue
            except Exception:
                continue
            for tm in target_models:
                try:
                    if not getattr(tm, "is_alive", True):
                        continue
                except Exception:
                    continue
                try:
                    if can_see(om, tm):
                        return True
                except Exception:
                    continue
        return False

    def _iter_ranged_profiles(self, unit) -> list:
        profiles = []
        if unit is None:
            return profiles
        try:
            models = list(getattr(unit, "models", []) or [])
        except Exception:
            models = []
        for m in models:
            try:
                if not getattr(m, "is_alive", True):
                    continue
            except Exception:
                pass
            wargear = list(getattr(m, "wargear", []) or [])
            for wg in wargear:
                try:
                    if hasattr(wg, "is_ranged") and callable(getattr(wg, "is_ranged")) and not wg.is_ranged():
                        continue
                except Exception:
                    pass
                try:
                    for prof in list(getattr(wg, "profiles", {}).values()):
                        profiles.append(prof)
                except Exception:
                    continue
        return profiles

    def _unit_is_eligible_observer(self, unit, *, game=None, player=None) -> bool:
        if unit is None or not self._unit_has_ftgg(unit):
            return False
        if not self._unit_is_alive(unit):
            return False
        if self._unit_is_fortification(unit):
            return False
        if self._unit_is_battle_shocked(unit):
            return False
        if self._unit_is_embarked(unit):
            return False
        try:
            if not bool(getattr(unit, "deployed", True)):
                return False
            if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
                return False
        except Exception:
            pass
        action_lock_active = False
        allow_shoot_while_action = False
        try:
            action_lock_active = bool(getattr(getattr(unit, "round_state", None), "action_locked_until_turn_end", False))
            if action_lock_active:
                army = unit.get_parent_army() if hasattr(unit, "get_parent_army") else None
                sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
                if sm_mgr is not None and getattr(sm_mgr, "seekers_companions_allow_shoot_while_action", None):
                    allow_shoot_while_action = bool(
                        sm_mgr.seekers_companions_allow_shoot_while_action(
                            unit,
                            game=game,
                        )
                    )
                if not allow_shoot_while_action:
                    allow_fn = getattr(unit, "allows_shoot_while_started_action_from_unit_contains_rule", None)
                    if callable(allow_fn):
                        allow_shoot_while_action = bool(allow_fn(game=game))
                if not allow_shoot_while_action:
                    return False
            if bool(getattr(getattr(unit, "round_state", None), "shot_this_round", False)):
                action_shoot_exception_available = bool(
                    action_lock_active
                    and allow_shoot_while_action
                    and (not bool(getattr(getattr(unit, "round_state", None), "action_permitted_shoot_used", False)))
                )
                if not action_shoot_exception_available:
                    return False
        except Exception:
            pass
        profiles = self._iter_ranged_profiles(unit)
        if not profiles:
            return False
        try:
            if bool(getattr(getattr(unit, "round_state", None), "fell_back_this_round", False)):
                for prof in profiles:
                    try:
                        if unit.can_shoot_after_fall_back(prof):
                            return True
                    except Exception:
                        continue
                return False
            if bool(getattr(getattr(unit, "round_state", None), "advanced_this_round", False)):
                for prof in profiles:
                    try:
                        if unit.can_shoot_after_advance(prof):
                            return True
                    except Exception:
                        continue
                return False
        except Exception:
            pass
        game_map = getattr(game, "map", None) if game is not None else None
        for prof in profiles:
            try:
                if hasattr(unit, "can_shoot_in_engagement_range") and game_map is not None:
                    if not unit.can_shoot_in_engagement_range(game_map, prof):
                        continue
                return True
            except Exception:
                return True
        return False

    def get_eligible_observers(self, *, game=None, player=None) -> list:
        if not self._army_has_ftgg():
            return []
        if game is not None and player is not None:
            try:
                if getattr(game, "get_current_player", lambda: None)() is not player:
                    return []
            except Exception:
                pass
        out = []
        for unit in list(getattr(self.army, "units", []) or []):
            uid = self._unit_id(unit)
            if not uid:
                continue
            if uid in self._observer_unit_ids:
                continue
            if self._unit_is_eligible_observer(unit, game=game, player=player):
                out.append(unit)
        out.sort(key=lambda u: str(getattr(u, "name", "")))
        return out

    def get_eligible_spotted_targets(self, observer, *, game=None, player=None) -> list:
        if observer is None:
            return []
        if game is None or player is None:
            return []
        try:
            enemy_units = list(game.get_enemy_units(player) or [])
        except Exception:
            enemy_units = []
        out = []
        seen = set()
        for unit in enemy_units:
            if not self._unit_is_alive(unit):
                continue
            if self._unit_is_embarked(unit):
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            uid = self._unit_id(root)
            if not uid or uid in seen:
                continue
            seen.add(uid)
            if uid in self._spotted_by:
                continue
            if not self._unit_is_visible_to_unit(observer, root, game=game):
                continue
            out.append(root)
        out.sort(key=lambda u: str(getattr(u, "name", "")))
        return out

    def mark_spotted(self, observer, target, *, game=None, player=None) -> bool:
        if observer is None or target is None:
            return False
        if not self._army_has_ftgg():
            return False
        if not self._unit_is_eligible_observer(observer, game=game, player=player):
            return False
        obs_id = self._unit_id(observer)
        tgt_id = self._unit_id(target)
        if not obs_id or not tgt_id:
            return False
        if obs_id in self._observer_unit_ids:
            return False
        if tgt_id in self._spotted_by:
            return False
        if game is not None and not self._unit_is_visible_to_unit(observer, target, game=game):
            return False
        self._observer_unit_ids.add(obs_id)
        self._observer_to_target[obs_id] = tgt_id
        self._spotted_by[tgt_id] = obs_id
        self._spotted_markerlight[tgt_id] = self._unit_has_markerlight(observer)
        coordinated_sustained = self._coordinated_exploitation_sustained_value(observer)
        if coordinated_sustained > 0:
            self._spotted_coordinated_exploitation[tgt_id] = coordinated_sustained
        return True

    def is_observer(self, unit) -> bool:
        uid = self._unit_id(unit)
        return bool(uid and uid in self._observer_unit_ids)

    def is_spotted(self, target) -> bool:
        tid = self._unit_id(target)
        return bool(tid and tid in self._spotted_by)

    def guided_attack_bonus(self, attacker_unit, target_unit) -> dict:
        if attacker_unit is None or target_unit is None:
            return {}
        if not self._army_has_ftgg():
            return {}
        if not self._unit_has_ftgg(attacker_unit):
            return {}
        if self.is_observer(attacker_unit):
            return {}
        if not self.is_spotted(target_unit):
            return {}
        game = None
        try:
            army = attacker_unit.get_parent_army()
        except Exception:
            army = None
        if army is not None:
            try:
                game = getattr(getattr(army, "player", None), "game", None)
            except Exception:
                game = None
        if game is not None:
            try:
                if not bool(getattr(game, "is_shooting_phase", lambda: False)()):
                    return {}
                if getattr(game, "get_current_player", lambda: None)() is not getattr(army, "player", None):
                    return {}
            except Exception:
                pass
        tid = self._unit_id(target_unit)
        out = {
            "bs_improve": 1,
            "ignores_cover": bool(self._spotted_markerlight.get(tid, False)),
        }
        if self._unit_has_named_ability(attacker_unit, "precise targeting"):
            out["reroll_hit_full"] = True
            out["reroll_hit_full_reason"] = "Precise Targeting"
        coordinated_sustained = int(self._spotted_coordinated_exploitation.get(tid, 0) or 0)
        if coordinated_sustained > 0:
            out["sustained_hits_value"] = coordinated_sustained
        return out
