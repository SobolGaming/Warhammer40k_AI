from __future__ import annotations

import logging
import re
from typing import Any, Optional

from ..utility import dice as dice_module
from ..utility.aura_utils import unit_wholly_within_range_of_unit
from ..utility.event_bus import append_action, append_dice
from ..utility.entity_ids import get_entity_id
from ..utility.modifiers import Modifier, ModifierOp

logger = logging.getLogger(__name__)


class OrksStratagemMixin:
    @staticmethod
    def _orks_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _orks_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "")

    def _orks_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "orks_detachments", None)

    def _is_war_horde_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        if mgr is None:
            return False
        return bool(mgr.is_war_horde())

    def _is_green_tide_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        checker = getattr(mgr, "is_green_tide", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_bully_boyz_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        checker = getattr(mgr, "is_bully_boyz", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_da_big_hunt_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        checker = getattr(mgr, "is_da_big_hunt", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_dread_mob_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        checker = getattr(mgr, "is_dread_mob", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_freebooter_krew_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        checker = getattr(mgr, "is_freebooter_krew", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_kult_of_speed_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        checker = getattr(mgr, "is_kult_of_speed", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_more_dakka_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        checker = getattr(mgr, "is_more_dakka", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_taktikal_brigade_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        checker = getattr(mgr, "is_taktikal_brigade", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_speedwaaagh_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        checker = getattr(mgr, "is_speedwaaagh", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_blitz_brigade_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        checker = getattr(mgr, "is_blitz_brigade", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _orks_normalize_name(text: str) -> str:
        value = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
        return re.sub(r"\s+", " ", value).strip()

    def _is_orks_unit(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        if parent_army is not None and parent_army is not army:
            return False
        has_any_kw = getattr(root, "has_any_keyword", None)
        has_orks_kw = bool(has_any_kw("ORKS")) if callable(has_any_kw) else False
        root_faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if not has_orks_kw and root_faction_id != "ORK":
            return False
        return True

    @staticmethod
    def _orks_has_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and has_any(keyword):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and has_kw(keyword):
            return True
        return False

    def _orks_unit_contains_keyword(self, unit: Any, keyword: str) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if self._orks_has_keyword(root, keyword):
            return True
        members_fn = getattr(root, "get_attached_unit_members", None)
        members = list(members_fn() or []) if callable(members_fn) else [root]
        for member in list(members or []):
            if self._orks_has_keyword(member, keyword):
                return True
        return False

    def _orks_unit_contains_any_keyword(self, unit: Any, keywords: tuple[str, ...]) -> bool:
        for keyword in list(keywords or ()):
            if self._orks_unit_contains_keyword(unit, str(keyword or "")):
                return True
        return False

    def _orks_unit_name_contains(self, unit: Any, token: str) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        name_norm = self._orks_normalize_name(getattr(root, "name", ""))
        token_norm = self._orks_normalize_name(token)
        if not token_norm:
            return False
        return token_norm in name_norm

    @staticmethod
    def _orks_phase_label(value: Any) -> str:
        text = str(value or "").strip().lower().replace("_", " ")
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def _orks_phase_key(value: Any) -> str:
        text = str(value or "").strip().upper()
        return re.sub(r"\s+", "_", text)

    def _orks_current_phase_label(self) -> str:
        phase = getattr(self.game, "phase", None) if getattr(self, "game", None) is not None else None
        phase_name = getattr(phase, "name", phase)
        if phase_name:
            return self._orks_phase_label(phase_name)
        return self._orks_phase_label(getattr(self, "_current_phase_name", "") or "")

    def _orks_current_phase_key(self) -> str:
        phase = getattr(self.game, "phase", None) if getattr(self, "game", None) is not None else None
        phase_name = getattr(phase, "name", phase)
        if phase_name:
            return self._orks_phase_key(phase_name)
        return self._orks_phase_key(getattr(self, "_current_phase_name", "") or "")

    def _orks_current_turn(self) -> int:
        return int(getattr(getattr(self, "game", None), "turn", 0) or 0)

    def _orks_player_id(self) -> str:
        return str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")

    def _orks_turn_owner_id(self) -> str:
        game = getattr(self, "game", None)
        if game is None:
            return self._orks_player_id()
        get_current_player = getattr(game, "get_current_player", None)
        current_player = get_current_player() if callable(get_current_player) else None
        current_owner = str(getattr(current_player, "id", "") or get_entity_id(current_player) or "")
        return current_owner or self._orks_player_id()

    def _orks_is_players_turn(self) -> bool:
        game = getattr(self, "game", None)
        if game is None:
            return False
        current = getattr(game, "get_current_player", lambda: None)()
        return current is self.player

    def _orks_is_unit_engaged(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if root is None or game_map is None:
            return False
        enemies_fn = getattr(game_map, "get_enemy_units", None)
        within_fn = getattr(game_map, "is_within_engagement_range", None)
        if not callable(enemies_fn) or not callable(within_fn):
            return False
        for enemy in list(enemies_fn(root) or []):
            enemy_root = self._orks_root(enemy)
            if enemy_root is None:
                continue
            if within_fn(root, enemy_root):
                return True
        return False

    def _orks_unit_not_selected_for_phase_action(self, unit: Any, *, phase_key: str) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        phase_u = self._orks_phase_key(phase_key)
        if phase_u == "SHOOTING_PHASE":
            return not bool(getattr(round_state, "shot_this_round", False))
        if phase_u == "FIGHT_PHASE":
            return not bool(getattr(round_state, "fought_this_phase", False))
        if phase_u == "MOVEMENT_PHASE":
            return not any(
                bool(getattr(round_state, attr, False))
                for attr in (
                    "moved_this_round",
                    "advanced_this_round",
                    "fell_back_this_round",
                )
            )
        return True

    @staticmethod
    def _orks_effect_matches_detachment(effect: dict, *, detachment: str) -> bool:
        if not isinstance(effect, dict):
            return False
        expected = str(effect.get("detachment", "") or "").strip().lower()
        return bool(expected and expected == str(detachment or "").strip().lower())

    def _orks_append_temp_effect(self, unit: Any, effect: dict) -> None:
        root = self._orks_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        existing = list(sr.get("orks_temp_effects", []) or [])
        effect_id = str(effect.get("id", "") or "").strip()
        kept: list[dict] = []
        for entry in existing:
            if not isinstance(entry, dict):
                continue
            if effect_id and str(entry.get("id", "") or "").strip() == effect_id:
                continue
            kept.append(dict(entry))
        kept.append(dict(effect))
        kept.sort(key=lambda entry: str(entry.get("id", "") or ""))
        sr["orks_temp_effects"] = kept
        root.special_rules = sr

    def _orks_apply_temp_effects(self, unit: Any, *, detachment: str, effects: list[dict]) -> None:
        phase_key = self._orks_current_phase_key()
        owner_id = self._orks_turn_owner_id()
        turn = self._orks_current_turn()
        for index, entry in enumerate(list(effects or [])):
            if not isinstance(entry, dict):
                continue
            payload = dict(entry)
            payload.setdefault("detachment", str(detachment))
            effect_id = str(payload.get("id", "") or "").strip()
            if not effect_id:
                source_key = str(payload.get("source", "orks_effect") or "orks_effect").strip().lower().replace(" ", "_")
                effect_id = f"{source_key}:{index}"
            payload["id"] = effect_id
            payload.setdefault("turn_owner_id", owner_id)
            payload.setdefault("turn", int(turn))
            if payload.get("expires_mode") == "phase":
                payload.setdefault("expires_phase", phase_key)
            self._orks_append_temp_effect(unit, payload)

    def _orks_collect_owned_units(self) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        units: list[Any] = []
        for entry in list(getattr(army, "units", []) or []):
            root = self._orks_root(entry)
            if root is None:
                continue
            uid = self._orks_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._orks_owned_by_player(root, self.player):
                continue
            units.append(root)
        units.sort(key=self._orks_sort_key)
        return units

    def _orks_offensive_candidates(
        self,
        *,
        require_targetable: bool = True,
        keyword_any: tuple[str, ...] = (),
        keyword_exclude_any: tuple[str, ...] = (),
        name_exclude_any: tuple[str, ...] = (),
        require_not_selected_phase: str = "",
    ) -> list[Any]:
        phase_key = self._orks_phase_key(require_not_selected_phase)
        results: list[Any] = []
        for root in self._orks_collect_owned_units():
            if not self._orks_on_battlefield(root, require_targetable=require_targetable):
                continue
            if not self._is_orks_unit(root):
                continue
            if keyword_any and not self._orks_unit_contains_any_keyword(root, tuple(keyword_any)):
                continue
            if keyword_exclude_any and self._orks_unit_contains_any_keyword(root, tuple(keyword_exclude_any)):
                continue
            if name_exclude_any and any(self._orks_unit_name_contains(root, token) for token in list(name_exclude_any or ())):
                continue
            if phase_key and not self._orks_unit_not_selected_for_phase_action(root, phase_key=phase_key):
                continue
            results.append(root)
        results.sort(key=self._orks_sort_key)
        return results

    def _orks_war_horde_ere_we_go_candidates(self) -> list[Any]:
        if not self._is_war_horde_detachment():
            return []
        return self._orks_offensive_candidates(
            require_targetable=True,
            keyword_any=("INFANTRY",),
        )

    def _orks_war_horde_unbridled_carnage_candidates(self) -> list[Any]:
        if not self._is_war_horde_detachment():
            return []
        return self._orks_offensive_candidates(
            require_targetable=True,
            require_not_selected_phase="Fight phase",
        )

    def _orks_war_horde_mob_rule_tool_action_context(self) -> dict[str, Any]:
        if not self._is_war_horde_detachment():
            return {}
        mob_candidates = list(getattr(self, "_mob_rule_mob_candidates", lambda: [])() or [])
        support_candidates = getattr(self, "_mob_rule_battleshocked_candidates", None)
        support_by_unit: dict[str, list[Any]] = {}
        filtered: list[Any] = []
        for mob_unit in list(mob_candidates or []):
            mob_root = self._orks_root(mob_unit)
            if mob_root is None or not callable(support_candidates):
                continue
            candidates = list(support_candidates(mob_root) or [])
            if not candidates:
                continue
            support_by_unit[self._orks_sort_key(mob_root)] = candidates
            filtered.append(mob_root)
        filtered.sort(key=self._orks_sort_key)
        return {
            "candidates": filtered,
            "secondary_optional": False,
            "support_candidates_by_unit": support_by_unit,
        }

    def _orks_active_loot_objective_point(self):
        mgr = self._orks_detachment_mgr()
        resolver = getattr(mgr, "_active_here_be_loot_objective_point", None) if mgr is not None else None
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        objective_data = resolver(game=game, game_map=game_map) if callable(resolver) else None
        if not isinstance(objective_data, tuple):
            return None
        _objective, point = objective_data
        return point

    def _orks_unit_within_active_loot_objective(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        point = self._orks_active_loot_objective_point()
        if point is None:
            return False
        is_within = getattr(root, "is_within_objective_range", None)
        if not callable(is_within):
            return False
        return bool(is_within(point))

    def _orks_unit_waaagh_override_candidates(self, *, require_loot_objective_range: bool) -> list[Any]:
        candidates = self._orks_offensive_candidates(
            require_targetable=True,
            keyword_exclude_any=("GRETCHIN",),
        )
        if not bool(require_loot_objective_range):
            return candidates
        kept: list[Any] = []
        for root in list(candidates or []):
            if self._orks_unit_within_active_loot_objective(root):
                kept.append(root)
        kept.sort(key=self._orks_sort_key)
        return kept

    def _orks_charge_end_mortal_wound_source_candidates(self, *, target_matcher) -> list[Any]:
        candidates = self._orks_offensive_candidates(require_targetable=True)
        kept: list[Any] = []
        for root in list(candidates or []):
            if not bool(target_matcher(root)):
                continue
            if not bool(getattr(getattr(root, "round_state", None), "charged_this_round", False)):
                continue
            if not self._orks_charge_end_mortal_wound_enemy_candidates(root):
                continue
            kept.append(root)
        kept.sort(key=self._orks_sort_key)
        return kept

    def _orks_ded_killy_construction_candidates(self) -> list[Any]:
        if not self._is_speedwaaagh_detachment():
            return []
        return self._orks_offensive_candidates(
            require_targetable=True,
            keyword_any=("SPEED FREEKS", "TRUKK"),
            require_not_selected_phase="Fight phase",
        )

    def _orks_unit_used_speedwaaagh_turbo_this_turn(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        mgr = self._orks_detachment_mgr()
        active_fn = getattr(mgr, "speedwaaagh_turbo_boostas_active", None) if mgr is not None else None
        if callable(active_fn):
            return bool(active_fn(root, game=getattr(self, "game", None)))
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("speedwaaagh_turbo_boostas_active")):
            return False
        owner_id = str(sr.get("speedwaaagh_turbo_boostas_turn_owner", "") or "").strip()
        if owner_id and owner_id != self._orks_turn_owner_id():
            return False
        try:
            effect_turn = int(sr.get("speedwaaagh_turbo_boostas_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        current_turn = self._orks_current_turn()
        return not bool(effect_turn and current_turn and effect_turn != current_turn)

    def _orks_on_da_move_candidates(self) -> list[Any]:
        if not self._is_speedwaaagh_detachment():
            return []
        candidates = self._orks_offensive_candidates(
            require_targetable=True,
            require_not_selected_phase="Movement phase",
        )
        kept = [
            root
            for root in list(candidates or [])
            if not self._orks_unit_used_speedwaaagh_turbo_this_turn(root)
        ]
        kept.sort(key=self._orks_sort_key)
        return kept

    def _orks_speshul_ammo_candidates(self) -> list[Any]:
        if not self._is_speedwaaagh_detachment():
            return []
        return self._orks_offensive_candidates(
            require_targetable=True,
            require_not_selected_phase="Shooting phase",
        )

    def _orks_armoured_duellists_candidates(self) -> list[Any]:
        if not self._is_blitz_brigade_detachment():
            return []
        return self._orks_offensive_candidates(
            require_targetable=True,
            keyword_any=("VEHICLE",),
            require_not_selected_phase="Shooting phase",
        )

    def _orks_blitz_brigade_wagon_or_rig_not_moved_candidates(self) -> list[Any]:
        if not self._is_blitz_brigade_detachment():
            return []
        candidates = self._orks_offensive_candidates(
            require_targetable=True,
            require_not_selected_phase="Movement phase",
        )
        kept = [unit for unit in list(candidates or []) if self._orks_is_battlewagon_kill_rig_or_hunta_rig(unit)]
        kept.sort(key=self._orks_sort_key)
        return kept

    def _orks_is_transport_unit(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        return bool(getattr(root, "is_transport", False)) or self._orks_unit_contains_keyword(root, "TRANSPORT")

    def _orks_mount_up_transport_can_embark(self, *, transport: Any, passenger: Any) -> bool:
        transport_root = self._orks_root(transport)
        passenger_root = self._orks_root(passenger)
        if transport_root is None or passenger_root is None or transport_root is passenger_root:
            return False
        if not self._orks_owned_by_player(transport_root, self.player):
            return False
        if not self._orks_owned_by_player(passenger_root, self.player):
            return False
        if not self._orks_on_battlefield(transport_root, require_targetable=True):
            return False
        if not self._orks_on_battlefield(passenger_root, require_targetable=True):
            return False
        if not self._is_orks_unit(passenger_root):
            return False
        if not self._orks_unit_contains_keyword(passenger_root, "INFANTRY"):
            return False
        if self._orks_is_unit_engaged(passenger_root):
            return False
        if not self._orks_is_transport_unit(transport_root):
            return False
        can_transport = getattr(transport_root, "can_transport", None)
        if not callable(can_transport):
            return False
        try:
            if not bool(can_transport(passenger_root)):
                return False
        except (AttributeError, TypeError, ValueError, RuntimeError):
            return False
        if not unit_wholly_within_range_of_unit(transport_root, passenger_root, 6.0):
            return False
        return True

    def _orks_mount_up_ladz_candidates(self) -> tuple[list[Any], dict[str, list[Any]]]:
        if not self._is_blitz_brigade_detachment():
            return ([], {})

        owned_units = self._orks_collect_owned_units()
        passengers = [
            unit
            for unit in owned_units
            if self._is_orks_unit(unit)
            and self._orks_unit_contains_keyword(unit, "INFANTRY")
            and self._orks_on_battlefield(unit, require_targetable=True)
            and not self._orks_is_unit_engaged(unit)
        ]
        transports = [
            unit
            for unit in owned_units
            if self._orks_is_transport_unit(unit)
            and self._orks_on_battlefield(unit, require_targetable=True)
        ]
        passengers.sort(key=self._orks_sort_key)
        transports.sort(key=self._orks_sort_key)

        transport_candidates: list[Any] = []
        passenger_map: dict[str, list[Any]] = {}
        for transport in transports:
            embarkable = [
                passenger
                for passenger in passengers
                if self._orks_mount_up_transport_can_embark(transport=transport, passenger=passenger)
            ]
            if not embarkable:
                continue
            embarkable.sort(key=self._orks_sort_key)
            transport_candidates.append(transport)
            passenger_map[self._orks_sort_key(transport)] = embarkable
        transport_candidates.sort(key=self._orks_sort_key)
        return (transport_candidates, passenger_map)

    def _orks_run_em_down_other_candidates(self, source_unit: Any) -> list[Any]:
        source_root = self._orks_root(source_unit)
        if source_root is None:
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        source_id = self._orks_sort_key(source_root)
        for unit in self._orks_collect_owned_units():
            root = self._orks_root(unit)
            if root is None:
                continue
            unit_id = self._orks_sort_key(root)
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            if root is source_root or (source_id and unit_id == source_id):
                continue
            if not self._orks_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_orks_unit(root):
                continue
            if not self._orks_unit_contains_any_keyword(root, ("VEHICLE", "MONSTER")):
                continue
            distance = self._orks_distance_between_units(source_root, root)
            if distance is None or float(distance) > 6.0 + 1e-6:
                continue
            candidates.append(root)
        candidates.sort(key=self._orks_sort_key)
        return candidates

    def _orks_resolve_unit_list(self, raw_units: Any) -> list[Any]:
        if raw_units is None:
            return []
        values = list(raw_units) if isinstance(raw_units, (list, tuple, set)) else [raw_units]
        seen: set[str] = set()
        resolved: list[Any] = []
        for unit in values:
            root = self._orks_root(unit)
            if root is None:
                continue
            unit_id = self._orks_sort_key(root)
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            resolved.append(root)
        resolved.sort(key=self._orks_sort_key)
        return resolved

    def _orks_charge_end_mortal_wound_enemy_candidates(self, source_unit: Any) -> list[Any]:
        source_root = self._orks_root(source_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if source_root is None or game_map is None:
            return []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(within_engagement):
            return []
        seen: set[str] = set()
        candidates: list[Any] = []
        for enemy_unit in list(get_enemy_units(source_root) or []):
            enemy_root = self._orks_root(enemy_unit)
            if enemy_root is None:
                continue
            if self._orks_owned_by_player(enemy_root, self.player):
                continue
            if not self._orks_on_battlefield(enemy_root, require_targetable=False):
                continue
            if not bool(within_engagement(source_root, enemy_root)):
                continue
            enemy_id = self._orks_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            candidates.append(enemy_root)
        candidates.sort(key=self._orks_sort_key)
        return candidates

    def _orks_alive_models(self, unit: Any) -> list[Any]:
        root = self._orks_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = list(getattr(root, "models", []) or [])
        alive = [model for model in models if bool(getattr(model, "is_alive", True))]
        alive.sort(key=self._orks_sort_key)
        return alive

    def _orks_models_within_engagement_count(self, source_unit: Any, enemy_unit: Any) -> int:
        source_root = self._orks_root(source_unit)
        enemy_root = self._orks_root(enemy_unit)
        if source_root is None or enemy_root is None:
            return 0
        from ..utility.aura_utils import model_within_engagement_range_of_unit

        count = 0
        for model in self._orks_alive_models(source_root):
            if model_within_engagement_range_of_unit(model, enemy_root):
                count += 1
        return int(count)

    def _orks_charge_end_mortal_roll_count(
        self,
        source_unit: Any,
        enemy_unit: Any,
        *,
        count_mode: str,
        bonus_dice: int = 0,
    ) -> int:
        mode = str(count_mode or "").strip().lower()
        if mode == "unit_models":
            base_count = len(self._orks_alive_models(source_unit))
        elif mode == "engagement_models":
            base_count = self._orks_models_within_engagement_count(source_unit, enemy_unit)
        else:
            base_count = 0
        total = int(base_count) + int(bonus_dice or 0)
        return max(0, int(total))

    def _orks_unit_has_active_waaagh(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        waaagh_mgr = getattr(army, "waaagh", None) if army is not None else None
        unit_is_affected = getattr(waaagh_mgr, "unit_is_affected", None) if waaagh_mgr is not None else None
        if not callable(unit_is_affected):
            return False
        return bool(unit_is_affected(root, game=getattr(self, "game", None)))

    def _orks_enemy_is_da_big_hunt_prey(self, enemy_unit: Any) -> bool:
        enemy_root = self._orks_root(enemy_unit)
        if enemy_root is None:
            return False
        mgr = self._orks_detachment_mgr()
        prey_check = getattr(mgr, "is_da_big_hunt_prey_target", None) if mgr is not None else None
        if not callable(prey_check):
            return False
        return bool(prey_check(enemy_root))

    def _orks_roll_capped_mortal_wounds(
        self,
        *,
        roll_count: int,
        success_on: int,
        max_mortal_wounds: int = 6,
    ) -> tuple[list[int], int]:
        count = max(0, int(roll_count or 0))
        threshold = max(2, min(6, int(success_on or 0)))
        cap = max(0, int(max_mortal_wounds or 0))
        rolls = [dice_module.get_roll("D6") for _ in range(count)]
        successes = sum(1 for roll in rolls if int(roll or 0) >= threshold)
        return rolls, min(int(successes), cap)

    def _orks_resolve_charge_end_mortal_wounds(
        self,
        *,
        source_unit: Any,
        enemy_unit: Any,
        count_mode: str,
        success_on: int,
        success_on_if_waaagh: int | None = None,
        extra_dice_if_prey: int = 0,
        max_mortal_wounds: int = 6,
    ) -> dict[str, Any]:
        source_root = self._orks_root(source_unit)
        enemy_root = self._orks_root(enemy_unit)
        if source_root is None or enemy_root is None:
            return {
                "roll_count": 0,
                "success_on": int(success_on or 0),
                "rolls": [],
                "mortal_wounds": 0,
                "extra_dice": 0,
            }
        success_threshold = int(success_on or 0)
        if success_on_if_waaagh is not None and self._orks_unit_has_active_waaagh(source_root):
            success_threshold = int(success_on_if_waaagh or success_on)
        bonus_dice = 0
        if int(extra_dice_if_prey or 0) > 0 and self._orks_enemy_is_da_big_hunt_prey(enemy_root):
            bonus_dice = int(extra_dice_if_prey or 0)
        roll_count = self._orks_charge_end_mortal_roll_count(
            source_root,
            enemy_root,
            count_mode=str(count_mode or ""),
            bonus_dice=int(bonus_dice),
        )
        rolls, mortal_wounds = self._orks_roll_capped_mortal_wounds(
            roll_count=int(roll_count),
            success_on=int(success_threshold),
            max_mortal_wounds=int(max_mortal_wounds),
        )
        if int(mortal_wounds or 0) > 0:
            apply_mortal_wounds = getattr(source_root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal_wounds):
                apply_mortal_wounds(
                    enemy_root,
                    int(mortal_wounds),
                    game_map=getattr(getattr(self, "game", None), "map", None),
                )
        return {
            "roll_count": int(roll_count),
            "success_on": int(success_threshold),
            "rolls": list(rolls),
            "mortal_wounds": int(mortal_wounds),
            "extra_dice": int(bonus_dice),
        }

    def _orks_end_of_opponent_fight_phase_strategic_reserves_candidates(self, *, target_matcher) -> list[Any]:
        candidates = self._orks_offensive_candidates(require_targetable=True)
        kept: list[Any] = []
        for root in list(candidates or []):
            if not bool(target_matcher(root)):
                continue
            if self._orks_is_unit_engaged(root):
                continue
            kept.append(root)
        kept.sort(key=self._orks_sort_key)
        return kept

    def _orks_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        place_fn = getattr(root, "enter_strategic_reserves_midgame", None)
        if callable(place_fn):
            return bool(place_fn(game=game, game_map=game_map, reason=reason))

        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            if member is None:
                continue
            set_status = getattr(member, "set_reserve_status", None)
            if callable(set_status):
                set_status("strategic_reserves")
            else:
                setattr(member, "reserve_status", "strategic_reserves")
            mark_midgame = getattr(member, "mark_entered_reserves_midgame", None)
            if callable(mark_midgame):
                mark_midgame(game=game)
            if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                setattr(member, "_aircraft_return_turn", int(getattr(game, "turn", 0) or 0) + 1 if game is not None else 0)
            member.deployed = True
            member.reserve_turn_deployed = None
            member.arrived_from_reserves_this_turn = False
            if game_map is not None and isinstance(getattr(game_map, "units", None), list) and member in game_map.units:
                game_map.units.remove(member)
        return True

    def _orks_apply_unit_waaagh_override(self, unit: Any, *, source_name: str) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        waaagh_mgr = getattr(army, "waaagh", None) if army is not None else None
        apply_override = getattr(waaagh_mgr, "apply_unit_override_until_next_command_phase", None) if waaagh_mgr is not None else None
        if not callable(apply_override):
            return False
        return bool(
            apply_override(
                root,
                player=self.player,
                source=str(source_name or "Waaagh override"),
            )
        )

    def _orks_owned_by_player(self, unit: Any, player: Any) -> bool:
        root = self._orks_root(unit)
        if root is None or player is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    def _orks_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive):
            if not bool(is_alive()):
                return False
        elif not bool(getattr(root, "is_alive", True)):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        if getattr(root, "embarked_in", None) is not None:
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _orks_unit_is_boyz(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if self._orks_has_keyword(root, "BOYZ"):
            return True
        return "BOYZ" in str(getattr(root, "name", "") or "").strip().upper()

    def _orks_model_is_character(self, model: Any) -> bool:
        if model is None:
            return False
        is_character = getattr(model, "is_character", None)
        if callable(is_character):
            if bool(is_character()):
                return True
        elif bool(is_character):
            return True
        if self._orks_has_keyword(model, "CHARACTER"):
            return True
        parent = getattr(model, "parent_unit", None)
        return bool(parent is not None and self._orks_has_keyword(parent, "CHARACTER"))

    def _orks_returnable_destroyed_non_character_models(self, unit: Any) -> list[Any]:
        root = self._orks_root(unit)
        if root is None:
            return []
        destroyed_pool = list(getattr(root, "models_lost", []) or [])
        can_return = getattr(root, "_horrors_can_return_model", None)
        candidates: list[Any] = []
        for model in destroyed_pool:
            if model is None:
                continue
            if self._orks_model_is_character(model):
                continue
            if callable(can_return) and not bool(can_return(model)):
                continue
            candidates.append(model)
        return sorted(candidates, key=self._orks_sort_key)

    def _orks_unit_in_candidates(self, unit: Any, candidates: list[Any]) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        root_id = self._orks_sort_key(root)
        for candidate in list(candidates or []):
            candidate_root = self._orks_root(candidate)
            if candidate_root is None:
                continue
            if candidate_root is root:
                return True
            if root_id and self._orks_sort_key(candidate_root) == root_id:
                return True
        return False

    def _orks_green_tide_come_on_ladz_candidates(self) -> list[Any]:
        if not self._is_green_tide_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._orks_root(unit)
            if root is None:
                continue
            uid = self._orks_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._orks_owned_by_player(root, self.player):
                continue
            if not self._orks_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_orks_unit(root):
                continue
            if not self._orks_unit_is_boyz(root):
                continue
            if not self._orks_returnable_destroyed_non_character_models(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._orks_sort_key)

    def _orks_resolve_unit_list(self, selected: Any) -> list[Any]:
        if selected is None:
            return []
        raw = list(selected) if isinstance(selected, (list, tuple, set)) else [selected]
        seen: set[str] = set()
        roots: list[Any] = []
        for item in raw:
            root = self._orks_root(item)
            if root is None:
                continue
            root_id = self._orks_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            roots.append(root)
        roots.sort(key=self._orks_sort_key)
        return roots

    def _orks_green_tide_boyz_candidates(self, *, require_not_selected_phase: str = "") -> list[Any]:
        if not self._is_green_tide_detachment():
            return []
        candidates = self._orks_offensive_candidates(
            require_targetable=True,
            require_not_selected_phase=require_not_selected_phase,
        )
        kept: list[Any] = []
        for root in list(candidates or []):
            if self._orks_unit_is_boyz(root):
                kept.append(root)
        kept.sort(key=self._orks_sort_key)
        return kept

    def _orks_green_tide_competitive_streak_candidates(self) -> list[Any]:
        return self._orks_green_tide_boyz_candidates(require_not_selected_phase="Fight phase")

    def _orks_green_tide_bulldozer_brutality_candidates(self) -> list[Any]:
        candidates = self._orks_green_tide_boyz_candidates(require_not_selected_phase="Fight phase")
        kept: list[Any] = []
        for root in list(candidates or []):
            if not self._orks_is_unit_engaged(root):
                continue
            kept.append(root)
        kept.sort(key=self._orks_sort_key)
        return kept

    def _orks_green_tide_tide_of_muscle_candidates(self) -> list[Any]:
        candidates = self._orks_green_tide_boyz_candidates()
        kept: list[Any] = []
        for root in list(candidates or []):
            round_state = getattr(root, "round_state", None)
            if bool(getattr(round_state, "attempted_charge_this_round", False)):
                continue
            kept.append(root)
        kept.sort(key=self._orks_sort_key)
        return kept

    def _orks_green_tide_braggin_rights_pairs(self) -> list[tuple[Any, Any]]:
        units = self._orks_green_tide_boyz_candidates()
        pairs: list[tuple[Any, Any]] = []
        for idx, first in enumerate(list(units or [])):
            for second in units[idx + 1 :]:
                distance = self._orks_distance_between_units(first, second)
                if distance is None or float(distance) > 6.0 + 1e-6:
                    continue
                root_a, root_b = sorted([first, second], key=self._orks_sort_key)
                pairs.append((root_a, root_b))
        pairs.sort(key=lambda pair: (self._orks_sort_key(pair[0]), self._orks_sort_key(pair[1])))
        return pairs

    def _orks_green_tide_pair_in_candidates(
        self,
        first_unit: Any,
        second_unit: Any,
        candidates: list[tuple[Any, Any]],
    ) -> bool:
        first_root = self._orks_root(first_unit)
        second_root = self._orks_root(second_unit)
        if first_root is None or second_root is None:
            return False
        pair_ids = tuple(sorted([self._orks_sort_key(first_root), self._orks_sort_key(second_root)]))
        for item in list(candidates or []):
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            cand_a = self._orks_root(item[0])
            cand_b = self._orks_root(item[1])
            if cand_a is None or cand_b is None:
                continue
            cand_ids = tuple(sorted([self._orks_sort_key(cand_a), self._orks_sort_key(cand_b)]))
            if pair_ids == cand_ids:
                return True
        return False

    def _orks_green_tide_effectively_counts_as_ten(self, unit: Any, *, scope: str) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        fn = getattr(root, "orks_effectively_counts_as_ten_models", None)
        if not callable(fn):
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        return bool(fn(str(scope or ""), game=game, game_map=game_map))

    @staticmethod
    def _unit_is_grots(unit: Any) -> bool:
        if unit is None:
            return False
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            if has_any_keyword("Grots") or has_any_keyword("Grot") or has_any_keyword("Gretchin"):
                return True
        return False

    def _orks_unit_is_grots_vehicle(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if not self._orks_unit_contains_keyword(root, "VEHICLE"):
            return False
        return bool(self._orks_unit_contains_any_keyword(root, ("GROT", "GROTS", "GRETCHIN")))

    def _orks_unit_is_walker_or_grots_vehicle(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if self._orks_unit_contains_keyword(root, "WALKER"):
            return True
        return self._orks_unit_is_grots_vehicle(root)

    def _orks_unit_is_mek_or_walker_or_grots_vehicle(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if self._orks_unit_contains_keyword(root, "MEK"):
            return True
        return self._orks_unit_is_walker_or_grots_vehicle(root)

    def _orks_temp_combat_choice_spec(self, *, stratagem_name: str, source_name: str) -> dict:
        source = str(source_name or stratagem_name or "Orks stratagem").strip() or "Orks stratagem"
        key = self._orks_normalize_name(stratagem_name)
        if key == "fight proppa":
            return {
                "detachment": "taktikal_brigade",
                "choices": [
                    {
                        "key": "sustained_hits_1",
                        "label": "[SUSTAINED HITS 1]",
                        "effects": [
                            {
                                "id": "fight_proppa:sustained_hits_1",
                                "source": source,
                                "effect": "keyword",
                                "attack_type": "melee",
                                "keyword": "SUSTAINED HITS 1",
                                "expires_mode": "phase",
                            }
                        ],
                    },
                    {
                        "key": "lethal_hits",
                        "label": "[LETHAL HITS]",
                        "effects": [
                            {
                                "id": "fight_proppa:lethal_hits",
                                "source": source,
                                "effect": "keyword",
                                "attack_type": "melee",
                                "keyword": "LETHAL HITS",
                                "expires_mode": "phase",
                            }
                        ],
                    },
                ],
            }
        if key == "dakka dakka dakka":
            return {
                "detachment": "dread_mob",
                "choices": [
                    {
                        "key": "normal",
                        "label": "Normal: re-roll Hit rolls of 1",
                        "effects": [
                            {
                                "id": "dakka_dakka_dakka:normal:hit_reroll",
                                "source": source,
                                "effect": "hit_reroll",
                                "attack_type": "ranged",
                                "reroll_mode": "ones",
                                "expires_mode": "phase",
                            }
                        ],
                    },
                    {
                        "key": "push_it",
                        "label": "Push It: full Hit re-rolls + [HAZARDOUS]",
                        "effects": [
                            {
                                "id": "dakka_dakka_dakka:push_it:hit_reroll",
                                "source": source,
                                "effect": "hit_reroll",
                                "attack_type": "ranged",
                                "reroll_mode": "full",
                                "expires_mode": "phase",
                            },
                            {
                                "id": "dakka_dakka_dakka:push_it:hazardous",
                                "source": source,
                                "effect": "keyword",
                                "attack_type": "ranged",
                                "keyword": "HAZARDOUS",
                                "expires_mode": "phase",
                            },
                        ],
                    },
                ],
            }
        if key == "bigger shells for bigger gitz":
            return {
                "detachment": "dread_mob",
                "choices": [
                    {
                        "key": "normal",
                        "label": "Normal: +1 to Wound vs MONSTER/VEHICLE",
                        "effects": [
                            {
                                "id": "bigger_shells_for_bigger_gitz:normal:wound_bonus",
                                "source": source,
                                "effect": "wound_bonus",
                                "attack_type": "ranged",
                                "value": 1,
                                "target_keywords_any": ["MONSTER", "VEHICLE"],
                                "expires_mode": "phase",
                            }
                        ],
                    },
                    {
                        "key": "push_it",
                        "label": "Push It: +1 to Wound/+1 Damage vs MONSTER/VEHICLE + [HAZARDOUS]",
                        "effects": [
                            {
                                "id": "bigger_shells_for_bigger_gitz:push_it:wound_bonus",
                                "source": source,
                                "effect": "wound_bonus",
                                "attack_type": "ranged",
                                "value": 1,
                                "target_keywords_any": ["MONSTER", "VEHICLE"],
                                "expires_mode": "phase",
                            },
                            {
                                "id": "bigger_shells_for_bigger_gitz:push_it:damage_bonus",
                                "source": source,
                                "effect": "damage_bonus",
                                "attack_type": "ranged",
                                "value": 1,
                                "target_keywords_any": ["MONSTER", "VEHICLE"],
                                "expires_mode": "phase",
                            },
                            {
                                "id": "bigger_shells_for_bigger_gitz:push_it:hazardous",
                                "source": source,
                                "effect": "keyword",
                                "attack_type": "ranged",
                                "keyword": "HAZARDOUS",
                                "expires_mode": "phase",
                            },
                        ],
                    },
                ],
            }
        if key == "klankin klaws":
            return {
                "detachment": "dread_mob",
                "choices": [
                    {
                        "key": "normal",
                        "label": "Normal: +2 Strength (melee)",
                        "effects": [
                            {
                                "id": "klankin_klaws:normal:strength_bonus",
                                "source": source,
                                "effect": "strength_bonus",
                                "attack_type": "melee",
                                "value": 2,
                                "expires_mode": "phase",
                            }
                        ],
                    },
                    {
                        "key": "push_it",
                        "label": "Push It: +2 Strength/+1 Damage (melee) + [HAZARDOUS]",
                        "effects": [
                            {
                                "id": "klankin_klaws:push_it:strength_bonus",
                                "source": source,
                                "effect": "strength_bonus",
                                "attack_type": "melee",
                                "value": 2,
                                "expires_mode": "phase",
                            },
                            {
                                "id": "klankin_klaws:push_it:damage_bonus",
                                "source": source,
                                "effect": "damage_bonus",
                                "attack_type": "melee",
                                "value": 1,
                                "expires_mode": "phase",
                            },
                            {
                                "id": "klankin_klaws:push_it:hazardous",
                                "source": source,
                                "effect": "keyword",
                                "attack_type": "melee",
                                "keyword": "HAZARDOUS",
                                "expires_mode": "phase",
                            },
                        ],
                    },
                ],
            }
        return {}

    def _orks_build_temp_combat_choice_request(self, *, stratagem_name: str, unit: Any, choice_spec: dict) -> Any:
        game = getattr(self, "game", None)
        if game is None:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        request_decision = getattr(game, "request_decision", None)
        queue = getattr(game, "decision_queue", None)
        if not callable(request_decision) and (queue is None or not hasattr(queue, "add")):
            return None

        root = self._orks_root(unit)
        if root is None:
            return None
        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            return None
        phase_name = self._orks_current_phase_key()
        player_id = str(getattr(self.player, "id", "") or "")
        normalized_stratagem = self._orks_normalize_name(stratagem_name)
        choices = list(choice_spec.get("choices", []) or [])
        if not choices:
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                if str(getattr(req, "player_id", "") or "") != player_id:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "orks_temp_combat_stratagem_choice":
                    continue
                if str(ctx.get("unit_id", "") or "") != unit_id:
                    continue
                if self._orks_normalize_name(str(ctx.get("stratagem_name", "") or "")) != normalized_stratagem:
                    continue
                if str(ctx.get("phase_name", "") or "") != phase_name:
                    continue
                return None

        option_entries = []
        for item in list(choices or []):
            key = str(item.get("key", "") or "").strip().lower()
            if not key:
                continue
            label = str(item.get("label", "") or key).strip() or key
            option_entries.append(
                DecisionOption.create(
                    label,
                    payload={
                        "unit_id": unit_id,
                        "stratagem_name": str(stratagem_name or "").strip(),
                        "choice_key": key,
                    },
                )
            )
        if not option_entries:
            return None
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{str(stratagem_name or '').strip() or 'Orks stratagem'}: choose mode for {getattr(root, 'name', 'Unit')}.",
            player_id=getattr(self.player, "id", None),
            options=option_entries,
            context={
                "ability": "orks_temp_combat_stratagem_choice",
                "ability_name": str(stratagem_name or "").strip() or "Orks stratagem",
                "army_id": str(get_entity_id(getattr(self.player, "army", None)) or ""),
                "unit_id": unit_id,
                "stratagem_name": str(stratagem_name or "").strip(),
                "phase_name": phase_name,
                "candidate_choice_keys": [
                    str(item.get("key", "") or "").strip().lower()
                    for item in list(choices or [])
                    if str(item.get("key", "") or "").strip()
                ],
                "optional": False,
            },
        )

    def _orks_submit_decision_request(self, request: Any) -> bool:
        if request is None:
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        request_decision = getattr(game, "request_decision", None)
        if callable(request_decision):
            request_decision(request)
            return True
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "add"):
            queue.add(request)
            return True
        return False

    def validate_orks_temp_combat_stratagem_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        stratagem_name: str = "",
    ) -> tuple[bool, str]:
        root = self._orks_root(unit)
        if root is None:
            return False, "Orks stratagem choice source unit was not found."
        if player is not None and player is not self.player:
            return False, "Orks stratagem choice must be resolved by the owning player."
        if not self._orks_owned_by_player(root, self.player):
            return False, "Orks stratagem choice source unit must belong to you."
        if not self._orks_on_battlefield(root, require_targetable=True):
            return False, "Orks stratagem choice source unit must be on the battlefield and targetable."
        if not self._is_orks_unit(root):
            return False, "Orks stratagem choice source unit must be an ORKS unit."

        resolved_name = str(stratagem_name or dict(payload or {}).get("stratagem_name", "") or "").strip()
        if not resolved_name:
            return False, "Orks stratagem choice requires stratagem_name."
        normalized_name = self._orks_normalize_name(resolved_name)
        choice_spec = self._orks_temp_combat_choice_spec(stratagem_name=resolved_name, source_name=resolved_name)
        if not isinstance(choice_spec, dict) or not choice_spec:
            return False, "Orks stratagem choice is not supported."

        expected_phase = str(phase_name or "").strip().upper()
        if expected_phase and game is not None:
            current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            if current_phase and current_phase != expected_phase:
                return False, "Orks stratagem choice request is no longer in the current phase."

        if normalized_name == "fight proppa":
            if not self._is_taktikal_brigade_detachment():
                return False, "FIGHT PROPPA requires Taktikal Brigade."
            if not self._orks_unit_contains_any_keyword(root, ("INFANTRY", "MOUNTED")):
                return False, "FIGHT PROPPA target must be an Orks Infantry or Orks Mounted unit."
            if not self._orks_unit_not_selected_for_phase_action(root, phase_key="FIGHT_PHASE"):
                return False, "FIGHT PROPPA target must not have been selected to fight this phase."
        elif normalized_name == "dakka dakka dakka":
            if not self._is_dread_mob_detachment():
                return False, "DAKKA! DAKKA! DAKKA! requires Dread Mob."
            if game is not None:
                get_current = getattr(game, "get_current_player", None)
                current_player = get_current() if callable(get_current) else None
                if current_player is not self.player:
                    return False, "DAKKA! DAKKA! DAKKA! can only be used in your Shooting phase."
            if not self._orks_unit_is_walker_or_grots_vehicle(root):
                return False, "DAKKA! DAKKA! DAKKA! target must be an Orks Walker or Grots Vehicle unit."
            if not self._orks_unit_not_selected_for_phase_action(root, phase_key="SHOOTING_PHASE"):
                return False, "DAKKA! DAKKA! DAKKA! target must not have been selected to shoot this phase."
        elif normalized_name == "bigger shells for bigger gitz":
            if not self._is_dread_mob_detachment():
                return False, "BIGGER SHELLS FOR BIGGER GITZ requires Dread Mob."
            if game is not None:
                get_current = getattr(game, "get_current_player", None)
                current_player = get_current() if callable(get_current) else None
                if current_player is not self.player:
                    return False, "BIGGER SHELLS FOR BIGGER GITZ can only be used in your Shooting phase."
            if not self._orks_unit_is_mek_or_walker_or_grots_vehicle(root):
                return False, "BIGGER SHELLS FOR BIGGER GITZ target must be a Mek, Orks Walker, or Grots Vehicle unit."
            if not self._orks_unit_not_selected_for_phase_action(root, phase_key="SHOOTING_PHASE"):
                return False, "BIGGER SHELLS FOR BIGGER GITZ target must not have been selected to shoot this phase."
        elif normalized_name == "klankin klaws":
            if not self._is_dread_mob_detachment():
                return False, "KLANKIN' KLAWS requires Dread Mob."
            if not self._orks_unit_contains_keyword(root, "WALKER"):
                return False, "KLANKIN' KLAWS target must be an Orks Walker unit."
            if not self._orks_unit_not_selected_for_phase_action(root, phase_key="FIGHT_PHASE"):
                return False, "KLANKIN' KLAWS target must not have been selected to fight this phase."
        else:
            return False, "Orks stratagem choice is not supported."

        choice_key = str(dict(payload or {}).get("choice_key", "") or "").strip().lower()
        if not choice_key:
            return False, "Orks stratagem choice requires choice_key."
        allowed_keys = {
            str(item.get("key", "") or "").strip().lower()
            for item in list(choice_spec.get("choices", []) or [])
            if str(item.get("key", "") or "").strip()
        }
        if choice_key not in allowed_keys:
            return False, "Selected choice is not an eligible option."
        return True, ""

    def apply_orks_temp_combat_stratagem_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        stratagem_name: str = "",
    ):
        valid, _reason = self.validate_orks_temp_combat_stratagem_choice(
            unit,
            payload,
            game=game,
            player=player,
            phase_name=phase_name,
            stratagem_name=stratagem_name,
        )
        if not valid:
            return None
        root = self._orks_root(unit)
        if root is None:
            return None

        resolved_name = str(stratagem_name or dict(payload or {}).get("stratagem_name", "") or "").strip()
        choice_spec = self._orks_temp_combat_choice_spec(stratagem_name=resolved_name, source_name=resolved_name)
        if not isinstance(choice_spec, dict) or not choice_spec:
            return None
        choice_key = str(dict(payload or {}).get("choice_key", "") or "").strip().lower()
        selected = None
        for item in list(choice_spec.get("choices", []) or []):
            if str(item.get("key", "") or "").strip().lower() == choice_key:
                selected = dict(item)
                break
        if selected is None:
            return None

        effects = [dict(entry) for entry in list(selected.get("effects", []) or []) if isinstance(entry, dict)]
        self._orks_apply_temp_effects(
            root,
            detachment=str(choice_spec.get("detachment", "") or ""),
            effects=effects,
        )
        return {
            "unit_id": str(get_entity_id(root) or ""),
            "unit_name": str(getattr(root, "name", "Unit") or "Unit"),
            "stratagem_name": resolved_name,
            "choice_key": choice_key,
            "choice_label": str(selected.get("label", "") or choice_key),
            "hazardous": any(
                str(entry.get("effect", "") or "").strip().lower() == "keyword"
                and str(entry.get("keyword", "") or "").strip().upper() == "HAZARDOUS"
                for entry in list(effects or [])
            ),
        }

    def _orks_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _orks_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._orks_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {str(getattr(stratagem, 'name', '') or '')}",
                source="stratagem",
            )
        )

    def _orks_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _orks_resolve_target_unit(self, stratagem_name: str, **kwargs) -> Any:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is not None:
            return target_unit
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                continue
            target_unit = reaction.get("target_unit") or reaction.get("unit")
            if target_unit is not None:
                return target_unit
        return None

    def _orks_validate_phase(
        self,
        *,
        expected_phases: tuple[str, ...],
        require_your_turn: bool = False,
        error_prefix: str,
    ) -> bool:
        current = self._orks_current_phase_label()
        allowed = {self._orks_phase_label(name) for name in list(expected_phases or ())}
        if current not in allowed:
            logger.error("ERROR: %s: wrong phase", error_prefix)
            return False
        if require_your_turn and not self._orks_is_players_turn():
            logger.error("ERROR: %s: not your turn", error_prefix)
            return False
        return True

    def _orks_validate_offensive_target(
        self,
        *,
        stratagem_name: str,
        target_unit: Any,
        candidates: list[Any],
        keyword_any: tuple[str, ...] = (),
        keyword_exclude_any: tuple[str, ...] = (),
        name_exclude_any: tuple[str, ...] = (),
        require_not_selected_phase: str = "",
    ) -> tuple[bool, Any]:
        root = self._orks_root(target_unit)
        if root is None:
            return False, None
        if not self._orks_owned_by_player(root, self.player):
            logger.error("ERROR: %s: target unit is not yours", stratagem_name)
            return False, None
        if not self._orks_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: %s: target must be on battlefield and targetable", stratagem_name)
            return False, None
        if not self._is_orks_unit(root):
            logger.error("ERROR: %s: target must be an ORKS unit", stratagem_name)
            return False, None
        if keyword_any and not self._orks_unit_contains_any_keyword(root, tuple(keyword_any)):
            logger.error("ERROR: %s: target does not match required keywords", stratagem_name)
            return False, None
        if keyword_exclude_any and self._orks_unit_contains_any_keyword(root, tuple(keyword_exclude_any)):
            logger.error("ERROR: %s: target has excluded keyword", stratagem_name)
            return False, None
        if name_exclude_any and any(self._orks_unit_name_contains(root, token) for token in list(name_exclude_any or ())):
            logger.error("ERROR: %s: target name is excluded", stratagem_name)
            return False, None
        phase_key = self._orks_phase_key(require_not_selected_phase)
        if phase_key and not self._orks_unit_not_selected_for_phase_action(root, phase_key=phase_key):
            logger.error("ERROR: %s: target has already acted this phase", stratagem_name)
            return False, None

        eligible = list(candidates or [])
        if not eligible:
            eligible = self._orks_offensive_candidates(
                require_targetable=True,
                keyword_any=tuple(keyword_any),
                keyword_exclude_any=tuple(keyword_exclude_any),
                name_exclude_any=tuple(name_exclude_any),
                require_not_selected_phase=require_not_selected_phase,
            )
        if eligible and not self._orks_unit_in_candidates(root, eligible):
            logger.error("ERROR: %s: selected unit is not currently eligible", stratagem_name)
            return False, None
        return True, root

    def _orks_get_available_stratagem_by_names(self, *names: str) -> Any:
        normalized = {
            self._orks_normalize_name(name)
            for name in list(names or ())
            if self._orks_normalize_name(name)
        }
        if not normalized:
            return None
        for stratagem in list(getattr(self, "available", []) or []):
            if self._orks_normalize_name(getattr(stratagem, "name", "")) in normalized:
                return stratagem
        return None

    @staticmethod
    def _orks_roll_value(notation: Any) -> int:
        token = str(notation or "").strip().upper()
        if not token:
            return 0
        match = re.fullmatch(r"(D[36])(?:\+(\d+))?", token)
        if match is not None:
            roll_value = max(0, dice_module.get_roll(match.group(1)))
            return int(roll_value) + int(match.group(2) or 0)
        if token.isdigit():
            return int(token)
        return 0

    def _orks_resolve_reactive_move_pre_move_rider(
        self,
        *,
        unit: Any,
        enemy_unit: Any,
        source_name: str,
        rider_spec: dict | None,
    ) -> dict[str, Any]:
        source_root = self._orks_root(unit)
        enemy_root = self._orks_root(enemy_unit)
        rider = dict(rider_spec or {})
        rider_kind = str(rider.get("effect", "") or rider.get("kind", "") or "").strip().lower()
        if source_root is None or enemy_root is None or rider_kind != "single_roll_mortal_wounds":
            return {}

        trigger_roll_notation = str(rider.get("trigger_roll", "") or "D6").strip().upper() or "D6"
        success_on = int(rider.get("success_on", 4) or 4)
        mortal_wounds_notation = str(rider.get("mortal_wounds", "") or "0").strip().upper() or "0"
        trigger_roll = int(self._orks_roll_value(trigger_roll_notation))
        success = int(trigger_roll) >= int(success_on)
        mortal_wounds = int(self._orks_roll_value(mortal_wounds_notation)) if success else 0

        if int(mortal_wounds) > 0:
            apply_mortal_wounds = getattr(source_root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal_wounds):
                apply_mortal_wounds(
                    enemy_root,
                    int(mortal_wounds),
                    game_map=getattr(getattr(self, "game", None), "map", None),
                )

        player = self.player
        source = str(source_name or "Reactive move rider").strip() or "Reactive move rider"
        append_dice(
            player,
            f"{source}: {trigger_roll_notation} roll = {int(trigger_roll)} "
            f"({'success' if success else 'fail'} on {int(success_on)}+).",
        )
        if success:
            append_dice(player, f"{source}: {mortal_wounds_notation} mortal wounds = {int(mortal_wounds)}.")
            append_action(
                player,
                f"{source}: {getattr(enemy_root, 'name', 'Enemy unit')} suffers "
                f"{int(mortal_wounds)} mortal wounds before {getattr(source_root, 'name', 'Unit')} moves.",
            )
        else:
            append_action(
                player,
                f"{source}: {getattr(enemy_root, 'name', 'Enemy unit')} avoids the mortal-wound rider; "
                f"{getattr(source_root, 'name', 'Unit')} can still make its Normal move.",
            )

        return {
            "effect": rider_kind,
            "trigger_roll": int(trigger_roll),
            "trigger_roll_notation": trigger_roll_notation,
            "success_on": int(success_on),
            "success": bool(success),
            "mortal_wounds": int(mortal_wounds),
            "mortal_wounds_notation": mortal_wounds_notation,
            "unit_id": self._orks_sort_key(source_root),
            "enemy_unit_id": self._orks_sort_key(enemy_root),
            "source": source,
        }

    def _orks_reaction_already_queued(self, *, event_name: str, stratagem_name: str, attacking_unit: Any) -> bool:
        target_name = str(stratagem_name or "").strip().upper()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip() != str(event_name or "").strip():
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != target_name:
                continue
            if reaction.get("attacking_unit") is attacking_unit:
                return True
        return False

    def _orks_reactive_shooting_loss_snapshots(self) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
        snapshots = getattr(self, "_orks_reactive_shooting_loss_snapshots_cache", None)
        if isinstance(snapshots, dict):
            return snapshots
        snapshots = {}
        setattr(self, "_orks_reactive_shooting_loss_snapshots_cache", snapshots)
        return snapshots

    def _orks_alive_model_count(self, unit: Any) -> int:
        root = self._orks_root(unit)
        if root is None:
            return 0
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        count = 0
        for model in models:
            if bool(getattr(model, "is_alive", False)):
                count += 1
        return count

    def _capture_orks_after_enemy_shoot_reactive_shooting_targets(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        stratagem_names: tuple[str, ...],
        detachment_check,
        target_matcher=None,
    ) -> None:
        if attacking_unit is None or not bool(detachment_check()):
            return
        if self._orks_current_phase_label() != "shooting phase":
            return
        if self._orks_is_players_turn():
            return
        attacker_root = self._orks_root(attacking_unit)
        if attacker_root is None or self._orks_owned_by_player(attacker_root, self.player):
            return
        stratagem = self._orks_get_available_stratagem_by_names(*stratagem_names)
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        attacker_key = str(self._attacker_unit_key(attacker_root) or "")
        if not attacker_key:
            return

        snapshot_by_unit: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._orks_root(unit)
            if root is None:
                continue
            uid = self._orks_sort_key(root)
            if not uid or uid in seen:
                continue
            seen.add(uid)
            if not self._orks_owned_by_player(root, self.player):
                continue
            if not self._orks_on_battlefield(root, require_targetable=False):
                continue
            if not self._is_orks_unit(root):
                continue
            if callable(target_matcher) and not bool(target_matcher(root)):
                continue
            models_before = self._orks_alive_model_count(root)
            if models_before <= 0:
                continue
            snapshot_by_unit[uid] = {
                "unit": root,
                "models_before": models_before,
            }
        if not snapshot_by_unit:
            return

        stratagem_key = self._orks_normalize_name(str(getattr(stratagem, "name", "") or stratagem_names[0]))
        snapshots = self._orks_reactive_shooting_loss_snapshots()
        stratagem_snapshots = snapshots.setdefault(stratagem_key, {})
        stratagem_snapshots[attacker_key] = snapshot_by_unit

    def _queue_orks_after_enemy_shoot_reactive_shooting_reaction(
        self,
        *,
        attacker_unit: Any,
        stratagem_names: tuple[str, ...],
        detachment_check,
        target_matcher=None,
    ) -> None:
        if attacker_unit is None or not bool(detachment_check()):
            return
        if self._orks_current_phase_label() != "shooting phase":
            return
        if self._orks_is_players_turn():
            return
        attacker_root = self._orks_root(attacker_unit)
        if attacker_root is None or self._orks_owned_by_player(attacker_root, self.player):
            return
        stratagem = self._orks_get_available_stratagem_by_names(*stratagem_names)
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        attacker_key = str(self._attacker_unit_key(attacker_root) or "")
        if not attacker_key:
            return

        stratagem_key = self._orks_normalize_name(str(getattr(stratagem, "name", "") or stratagem_names[0]))
        snapshots = self._orks_reactive_shooting_loss_snapshots()
        stratagem_snapshots = snapshots.get(stratagem_key)
        snapshot_by_unit: dict[str, dict[str, Any]] = {}
        if isinstance(stratagem_snapshots, dict):
            snapshot_by_unit = dict(stratagem_snapshots.pop(attacker_key, {}) or {})
            if not stratagem_snapshots:
                snapshots.pop(stratagem_key, None)
        if not snapshot_by_unit:
            return

        can_shoot_fn = getattr(getattr(self, "game", None), "_setup_reactive_can_shoot_target", None)
        if not callable(can_shoot_fn):
            return

        candidates: list[Any] = []
        for uid in sorted(snapshot_by_unit):
            entry = snapshot_by_unit.get(uid)
            if not isinstance(entry, dict):
                continue
            root = self._orks_root(entry.get("unit"))
            if root is None:
                continue
            if not self._orks_owned_by_player(root, self.player):
                continue
            if not self._orks_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_orks_unit(root):
                continue
            if callable(target_matcher) and not bool(target_matcher(root)):
                continue
            before = int(entry.get("models_before", 0) or 0)
            if before <= 0:
                continue
            if self._orks_alive_model_count(root) >= before:
                continue
            if not can_shoot_fn(root, attacker_root):
                continue
            candidates.append(root)
        candidates.sort(key=self._orks_sort_key)
        if not candidates:
            return

        stratagem_name = str(getattr(stratagem, "name", "") or stratagem_names[0]).strip()
        if self._orks_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem_name,
            attacking_unit=attacker_root,
        ):
            return

        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem_name,
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _orks_resolve_unit_shooting_resolved_reaction_context(
        self,
        stratagem_name: str,
        **kwargs,
    ) -> tuple[Any, Any, list[Any], str]:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        phase_name = str(kwargs.get("phase_name") or "").strip()

        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]

        normalized_name = self._orks_normalize_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != normalized_name:
                continue
            if target_unit is None:
                target_unit = reaction.get("target_unit") or reaction.get("unit")
            if attacking_unit is None:
                attacking_unit = reaction.get("enemy_unit") or reaction.get("attacking_unit") or reaction.get("attacker_unit")
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if not phase_name:
                phase_name = str(reaction.get("phase_name") or "").strip()
            if target_unit is None and len(candidates) == 1:
                target_unit = candidates[0]
            break

        return target_unit, attacking_unit, candidates, phase_name

    def _use_orks_after_enemy_shoot_reactive_shooting_stratagem(
        self,
        stratagem: Any,
        *,
        stratagem_name: str,
        detachment_check,
        target_matcher=None,
        target_error: str = "",
        **kwargs,
    ) -> bool:
        if not bool(detachment_check()):
            return False

        target_unit, attacking_unit, candidates, phase_name = self._orks_resolve_unit_shooting_resolved_reaction_context(
            stratagem_name,
            **kwargs,
        )
        if target_unit is None:
            logger.error("ERROR: %s: no target unit provided", stratagem_name)
            return False
        if not candidates:
            logger.error("ERROR: %s: no valid trigger context", stratagem_name)
            return False

        if self._orks_phase_label(phase_name or self._orks_current_phase_label()) != "shooting phase":
            logger.error("ERROR: %s: wrong phase", stratagem_name)
            return False
        if self._orks_is_players_turn():
            logger.error("ERROR: %s: not opponent's Shooting phase", stratagem_name)
            return False

        root = self._orks_root(target_unit)
        attacker_root = self._orks_root(attacking_unit)
        if root is None or attacker_root is None:
            logger.error("ERROR: %s: missing attacker context", stratagem_name)
            return False
        if not self._orks_owned_by_player(root, self.player):
            logger.error("ERROR: %s: target unit is not yours", stratagem_name)
            return False
        if not self._orks_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: %s: target must be on battlefield and targetable", stratagem_name)
            return False
        if not self._is_orks_unit(root):
            logger.error("ERROR: %s: target must be an ORKS unit", stratagem_name)
            return False
        if callable(target_matcher) and not bool(target_matcher(root)):
            logger.error("ERROR: %s: %s", stratagem_name, target_error or "target does not match required criteria")
            return False
        if candidates and not self._orks_unit_in_candidates(root, candidates):
            logger.error("ERROR: %s: target was not selected by the trigger", stratagem_name)
            return False
        if self._orks_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: %s: attacker is not enemy", stratagem_name)
            return False
        if not self._orks_on_battlefield(attacker_root, require_targetable=False):
            logger.error("ERROR: %s: attacker is not on the battlefield", stratagem_name)
            return False

        can_shoot_fn = getattr(getattr(self, "game", None), "_setup_reactive_can_shoot_target", None)
        if not callable(can_shoot_fn):
            logger.error("ERROR: %s: reactive shooting target validation unavailable", stratagem_name)
            return False
        if not can_shoot_fn(root, attacker_root):
            logger.error("ERROR: %s: attacker is not an eligible target", stratagem_name)
            return False

        queue_fn = getattr(getattr(self, "game", None), "_queue_setup_reactive_shooting_decision", None)
        if not callable(queue_fn):
            logger.error("ERROR: %s: reactive shooting decision queue unavailable", stratagem_name)
            return False

        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            enemy_unit=attacker_root,
            attacking_unit=attacker_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: %s: cannot be used in current state", stratagem_name)
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        request = queue_fn(
            player=self.player,
            unit=root,
            target_unit=attacker_root,
            source=str(getattr(stratagem, "name", "") or stratagem_name),
        )
        if request is None:
            logger.error("ERROR: %s: failed to queue reactive shooting decision", stratagem_name)
            return False
        request.context["call_dat_dakka_flow"] = True
        request.context["call_dat_dakka_enemy_unit_id"] = self._orks_sort_key(attacker_root)
        request.context["call_dat_dakka_unit_id"] = self._orks_sort_key(root)

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: %s: %s can shoot reactively into %s.",
            stratagem_name,
            getattr(root, "name", "Unit"),
            getattr(attacker_root, "name", "Enemy"),
        )
        return True

    def _capture_orks_more_dakka_call_dat_dakka_targets(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        self._capture_orks_after_enemy_shoot_reactive_shooting_targets(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
            stratagem_names=("CALL DAT DAKKA?",),
            detachment_check=self._is_more_dakka_detachment,
        )

    def _queue_orks_more_dakka_call_dat_dakka_reactions(self, *, attacker_unit: Any) -> None:
        self._queue_orks_after_enemy_shoot_reactive_shooting_reaction(
            attacker_unit=attacker_unit,
            stratagem_names=("CALL DAT DAKKA?",),
            detachment_check=self._is_more_dakka_detachment,
        )

    def _orks_target_selected_reaction_candidates(self, target_units: list[Any], *, matcher) -> list[Any]:
        seen: set[str] = set()
        candidates: list[Any] = []
        for unit in list(target_units or []):
            root = self._orks_root(unit)
            if root is None:
                continue
            uid = self._orks_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._orks_owned_by_player(root, self.player):
                continue
            if not self._orks_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_orks_unit(root):
                continue
            if not bool(matcher(root)):
                continue
            candidates.append(root)
        candidates.sort(key=self._orks_sort_key)
        return candidates

    def _orks_is_beast_snagga_infantry_or_mounted(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if not self._orks_unit_contains_keyword(root, "BEAST SNAGGA"):
            return False
        return self._orks_unit_contains_any_keyword(root, ("INFANTRY", "MOUNTED"))

    def _orks_is_nobz_or_meganobz_unit(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if self._orks_unit_contains_any_keyword(root, ("NOBZ", "MEGANOBZ")):
            return True
        return self._orks_unit_name_contains(root, "nobz") or self._orks_unit_name_contains(root, "meganobz")

    def _orks_is_beast_snagga_unit(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        return self._orks_unit_contains_keyword(root, "BEAST SNAGGA")

    def _orks_is_beast_snagga_mounted_unit(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if not self._orks_unit_contains_keyword(root, "BEAST SNAGGA"):
            return False
        return self._orks_unit_contains_keyword(root, "MOUNTED")

    def _orks_is_stormboyz_unit(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if self._orks_unit_contains_any_keyword(root, ("STORMBOYZ", "STORMBOY")):
            return True
        return self._orks_unit_name_contains(root, "stormboyz")

    def _orks_is_kommandos_or_stormboyz_unit(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if self._orks_unit_contains_any_keyword(root, ("KOMMANDOS", "KOMMANDO", "STORMBOYZ", "STORMBOY")):
            return True
        return self._orks_unit_name_contains(root, "kommandos") or self._orks_unit_name_contains(root, "stormboyz")

    def _orks_is_speed_freeks_or_trukk(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if self._orks_unit_contains_keyword(root, "SPEED FREEKS"):
            return True
        if self._orks_unit_contains_keyword(root, "TRUKK"):
            return True
        return self._orks_unit_name_contains(root, "trukk")

    def _orks_is_battlewagon_kill_rig_or_hunta_rig(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if self._orks_unit_contains_any_keyword(root, ("BATTLEWAGON", "KILL RIG", "HUNTA RIG")):
            return True
        return (
            self._orks_unit_name_contains(root, "battlewagon")
            or self._orks_unit_name_contains(root, "kill rig")
            or self._orks_unit_name_contains(root, "hunta rig")
        )

    def _orks_normalize_weapon_key(self, source_unit: Any, value: str) -> str:
        root = self._orks_root(source_unit)
        normalizer = getattr(root, "_normalize_keyword_phrase", None) if root is not None else None
        if callable(normalizer):
            try:
                return str(normalizer(value) or "")
            except Exception:
                return ""
        text = str(value or "").lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _orks_weapon_key_matches(candidate_key: str, key_set: set[str]) -> bool:
        key = str(candidate_key or "").strip()
        if not key:
            return False
        if key in key_set:
            return True
        if key.endswith("s") and key[:-1] in key_set:
            return True
        return f"{key}s" in key_set

    def _orks_indirect_weapon_keys(self, source_unit: Any) -> set[str]:
        source_root = self._orks_root(source_unit)
        if source_root is None:
            return set()
        keys: set[str] = set()
        for model in list(getattr(source_root, "models", []) or []):
            for wargear in list(getattr(model, "wargear", []) or []):
                is_ranged = getattr(wargear, "is_ranged", None)
                if callable(is_ranged) and not bool(is_ranged()):
                    continue
                profiles = getattr(wargear, "profiles", None)
                if not isinstance(profiles, dict):
                    continue
                for profile in list(profiles.values()):
                    is_indirect = getattr(profile, "is_indirect_fire", None)
                    if not callable(is_indirect) or not bool(is_indirect()):
                        continue
                    parent = getattr(profile, "parent_wargear", None)
                    weapon_name = str(getattr(parent, "name", "") or getattr(profile, "name", "") or "")
                    key = self._orks_normalize_weapon_key(source_root, weapon_name)
                    if key:
                        keys.add(key)
        return keys

    @staticmethod
    def _orks_hit_count(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, (list, tuple, set, dict)):
            return len(value)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _speedwaaagh_mobile_dakkastorm_target_hit_by_non_indirect(
        self,
        source_unit: Any,
        target_unit: Any,
        hit_models_by_target_weapon: Any,
    ) -> bool:
        if not isinstance(hit_models_by_target_weapon, dict):
            return True
        target_root = self._orks_root(target_unit)
        target_map = hit_models_by_target_weapon.get(target_unit)
        if target_map is None and target_root is not None:
            target_map = hit_models_by_target_weapon.get(target_root)
        if not isinstance(target_map, dict):
            return False
        indirect_keys = self._orks_indirect_weapon_keys(source_unit)
        for raw_key, models in list(target_map.items()):
            if not models:
                continue
            key = self._orks_normalize_weapon_key(source_unit, str(raw_key or ""))
            if not key:
                continue
            if not self._orks_weapon_key_matches(key, indirect_keys):
                return True
        return False

    def _speedwaaagh_mobile_dakkastorm_hit_candidates(
        self,
        source_unit: Any,
        hits_by_target: Any,
        hit_models_by_target_weapon: Any = None,
    ) -> list[Any]:
        source_root = self._orks_root(source_unit)
        if source_root is None:
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for target_unit, hits in list((hits_by_target or {}).items()):
            target_root = self._orks_root(target_unit)
            if target_root is None:
                continue
            if self._orks_hit_count(hits) <= 0:
                continue
            if not self._orks_on_battlefield(target_root, require_targetable=False):
                continue
            if self._orks_owned_by_player(target_root, self.player):
                continue
            if not self._speedwaaagh_mobile_dakkastorm_target_hit_by_non_indirect(
                source_root,
                target_root,
                hit_models_by_target_weapon,
            ):
                continue
            uid = self._orks_sort_key(target_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            candidates.append(target_root)
        return sorted(candidates, key=self._orks_sort_key)

    def _queue_speedwaaagh_mobile_dakkastorm_target_decision(
        self,
        *,
        stratagem: Any,
        source_unit: Any,
        candidates: list[Any],
    ) -> bool:
        if self.game is None:
            return False
        source_root = self._orks_root(source_unit)
        if source_root is None:
            return False
        candidate_units = [
            self._orks_root(candidate)
            for candidate in list(candidates or [])
            if self._orks_root(candidate) is not None
        ]
        candidate_units = sorted(candidate_units, key=self._orks_sort_key)
        if not candidate_units:
            return False

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [
            DecisionOption.create(
                str(getattr(candidate, "name", "Unit") or "Unit"),
                payload={"target_unit_id": get_entity_id(candidate)},
            )
            for candidate in candidate_units
        ]
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "MOBILE DAKKASTORM: select an enemy unit hit by non-Indirect Fire attacks.",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "orks_mobile_dakkastorm",
                "ability_name": str(getattr(stratagem, "name", "") or "MOBILE DAKKASTORM"),
                "attacker_unit_id": get_entity_id(source_root),
                "candidate_unit_ids": [get_entity_id(candidate) for candidate in candidate_units],
                "keyword_phrases": ["SPEED FREEKS", "TRUKK"],
                "strength_bonus": 2,
                "expires_phase": "SHOOTING_PHASE",
                "expires_timing": "PHASE_END",
            },
        )
        request_decision = getattr(self.game, "request_decision", None)
        if callable(request_decision):
            request_decision(request)
            return True
        return False

    def _orks_is_walker_or_grots_vehicle_not_titanic(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if self._orks_unit_contains_keyword(root, "TITANIC"):
            return False
        return self._orks_unit_is_walker_or_grots_vehicle(root)

    def _orks_unit_unmodified_toughness(self, unit: Any) -> int:
        root = self._orks_root(unit)
        if root is None:
            return 0
        models = list(getattr(root, "models", []) or [])
        if not models:
            return 0
        model = models[0]
        raw_value = getattr(model, "_base_toughness", None)
        if raw_value is None:
            raw_value = getattr(model, "_toughness", None)
        try:
            return int(raw_value or 0)
        except (TypeError, ValueError):
            return 0

    def _orks_stalkin_taktiks_defensive_effects(self, unit: Any, *, source_name: str) -> list[dict]:
        root = self._orks_root(unit)
        if root is None:
            return []
        effects = [
            {
                "key": "defensive_cover_bonuses",
                "value": 1,
                "attack_type": "ranged",
                "duration": "phase",
                "source": source_name,
            }
        ]
        if self._orks_unit_contains_keyword(root, "INFANTRY"):
            effects.append(
                {
                    "key": "defensive_hit_mods",
                    "value": 1,
                    "attack_type": "ranged",
                    "duration": "phase",
                    "source": source_name,
                }
            )
        return effects

    def _orks_speediest_freeks_defensive_effects(self, unit: Any, *, source_name: str) -> list[dict]:
        root = self._orks_root(unit)
        if root is None:
            return []
        invuln_value = 5
        if self._orks_unit_contains_keyword(root, "VEHICLE"):
            unmodified_toughness = self._orks_unit_unmodified_toughness(root)
            if unmodified_toughness > 0 and unmodified_toughness <= 8:
                invuln_value = 4
        return [
            {
                "key": "defensive_invuln_overrides",
                "value": int(invuln_value),
                "attack_type": "any",
                "duration": "phase",
                "source": source_name,
            }
        ]

    def _orks_extra_gubbinz_defensive_effects(self, *, source_name: str) -> list[dict]:
        return [
            {
                "key": "defensive_damage_reductions",
                "value": 1,
                "attack_type": "any",
                "duration": "phase",
                "source": source_name,
            }
        ]

    def _orks_dust_trails_defensive_effects(self, *, source_name: str) -> list[dict]:
        return [
            {
                "key": "defensive_cover_bonuses",
                "value": 1,
                "attack_type": "ranged",
                "duration": "phase",
                "source": source_name,
            }
        ]

    def _orks_impervious_defensive_effects(self, *, source_name: str) -> list[dict]:
        return [
            {
                "key": "defensive_wound_mods",
                "value": 1,
                "attack_type": "ranged",
                "duration": "phase",
                "source": source_name,
                "requires_strength_gt_toughness": True,
            }
        ]

    def _orks_apply_defensive_reaction_effects(
        self,
        unit: Any,
        *,
        attacking_unit: Any,
        phase_name: str,
        source_name: str,
        effects: list[dict],
    ) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        append_effect = getattr(self, "_append_defensive_effect", None)
        if not callable(append_effect):
            return False

        phase_key = self._orks_phase_key(phase_name)
        attacker_key = self._attacker_unit_key(attacking_unit) if attacking_unit is not None else None

        applied = False
        for spec in list(effects or []):
            if not isinstance(spec, dict):
                continue
            key = str(spec.get("key", "") or "").strip()
            if not key:
                continue
            duration = str(spec.get("duration", "phase") or "phase").strip().lower()
            entry = {
                "value": int(spec.get("value", 0) or 0),
                "attack_type": str(spec.get("attack_type", "any") or "any").strip().lower(),
                "source": str(spec.get("source", "") or source_name or "Orks defensive stratagem").strip(),
            }
            if duration == "phase":
                entry["expires_phase"] = phase_key
            elif duration == "attacker":
                if not attacker_key:
                    return False
                entry["attacker_key"] = attacker_key
            else:
                return False
            for field in (
                "exclude_allocated_model_keyword",
                "requires_strength_gt_toughness",
                "requires_leading_keyword",
                "requires_unit_contains_keyword",
            ):
                if field in spec:
                    entry[field] = spec[field]
            append_effect(root, key, entry)
            applied = True
        return applied

    def _orks_resolve_target_selected_reaction_context(self, stratagem_name: str, **kwargs) -> tuple[Any, Any, list[Any], str]:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        selected_targets = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        phase_name = str(kwargs.get("phase_name") or "").strip()

        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None and not candidates and len(selected_targets) == 1:
            target_unit = selected_targets[0]

        normalized_name = self._orks_normalize_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != normalized_name:
                continue
            if target_unit is None:
                target_unit = reaction.get("target_unit") or reaction.get("unit")
            if attacking_unit is None:
                attacking_unit = reaction.get("attacking_unit") or reaction.get("attacker_unit")
            if not selected_targets:
                selected_targets = list(reaction.get("target_units") or [])
            if not candidates:
                candidates = list(reaction.get("candidates") or reaction.get("target_units") or [])
            if not phase_name:
                phase_name = str(reaction.get("phase_name") or "").strip()
            if target_unit is None and len(candidates) == 1:
                target_unit = candidates[0]
            break

        return target_unit, attacking_unit, candidates, phase_name

    def _use_orks_target_selected_defensive_reaction(
        self,
        stratagem: Any,
        *,
        stratagem_name: str,
        expected_phases: tuple[str, ...],
        detachment_check,
        target_matcher,
        target_error: str,
        effect_builder,
        **kwargs,
    ) -> bool:
        if not bool(detachment_check()):
            return False

        target_unit, attacking_unit, candidates, phase_name = self._orks_resolve_target_selected_reaction_context(
            stratagem_name,
            **kwargs,
        )
        if target_unit is None:
            logger.error("ERROR: %s: no target unit provided", stratagem_name)
            return False

        phase_label = self._orks_phase_label(phase_name or self._orks_current_phase_label())
        allowed = {self._orks_phase_label(item) for item in list(expected_phases or ())}
        if phase_label not in allowed:
            logger.error("ERROR: %s: wrong phase", stratagem_name)
            return False
        if self._orks_is_players_turn():
            logger.error("ERROR: %s: not opponent's phase", stratagem_name)
            return False

        root = self._orks_root(target_unit)
        if root is None:
            return False
        if not self._orks_owned_by_player(root, self.player):
            logger.error("ERROR: %s: target unit is not yours", stratagem_name)
            return False
        if not self._orks_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: %s: target must be on battlefield and targetable", stratagem_name)
            return False
        if not self._is_orks_unit(root):
            logger.error("ERROR: %s: target must be an ORKS unit", stratagem_name)
            return False
        if candidates and not self._orks_unit_in_candidates(root, candidates):
            logger.error("ERROR: %s: target was not selected by the attacker", stratagem_name)
            return False

        attacker_root = self._orks_root(attacking_unit)
        if attacker_root is not None and self._orks_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: %s: attacker is not enemy", stratagem_name)
            return False

        if not bool(target_matcher(root)):
            logger.error("ERROR: %s: %s", stratagem_name, target_error)
            return False

        phase_title = "Shooting phase" if phase_label == "shooting phase" else "Fight phase"
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            attacking_unit=attacker_root,
            phase_name=phase_title,
        ):
            logger.error("ERROR: %s: cannot be used in current state", stratagem_name)
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or stratagem_name)
        effects = list(effect_builder(root, source_name=source_name) or [])
        if not effects:
            logger.error("ERROR: %s: no defensive effects configured", stratagem_name)
            return False
        if not self._orks_apply_defensive_reaction_effects(
            root,
            attacking_unit=attacker_root,
            phase_name=phase_title,
            source_name=source_name,
            effects=effects,
        ):
            logger.error("ERROR: %s: failed to apply defensive effects", stratagem_name)
            return False

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: %s: %s gains defensive effects this phase.", stratagem_name, getattr(root, "name", "Unit"))
        return True

    def _queue_single_orks_target_selected_defensive_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
        stratagem_names: tuple[str, ...],
        detachment_check,
        target_matcher,
    ) -> None:
        if not bool(detachment_check()):
            return
        stratagem = self._orks_get_available_stratagem_by_names(*stratagem_names)
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if (str(getattr(stratagem, "name", "") or "").strip().upper()) in set(self._used_stratagems_this_phase):
            return

        candidates = self._orks_target_selected_reaction_candidates(
            list(target_units or []),
            matcher=target_matcher,
        )
        if not candidates:
            return

        phase_label = self._orks_phase_label(phase_name)
        event_name = "shooting_targets_selected" if phase_label == "shooting phase" else "fight_targets_selected"
        stratagem_name = str(getattr(stratagem, "name", "") or stratagem_names[0]).strip()
        if self._orks_reaction_already_queued(
            event_name=event_name,
            stratagem_name=stratagem_name,
            attacking_unit=attacking_unit,
        ):
            return

        payload = {
            "event": event_name,
            "phase_name": "Shooting phase" if phase_label == "shooting phase" else "Fight phase",
            "stratagem": stratagem_name,
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_orks_target_selected_defensive_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
    ) -> None:
        if attacking_unit is None:
            return
        phase_label = self._orks_phase_label(phase_name)
        if phase_label not in {"shooting phase", "fight phase"}:
            return
        attacker_root = self._orks_root(attacking_unit)
        if attacker_root is None or self._orks_owned_by_player(attacker_root, self.player):
            return
        if phase_label == "shooting phase" and self._orks_is_players_turn():
            return

        if phase_label == "shooting phase":
            self._queue_single_orks_target_selected_defensive_reaction(
                attacking_unit=attacking_unit,
                target_units=list(target_units or []),
                phase_name=phase_name,
                stratagem_names=("GO GET 'EM!", "GO GET ’EM!"),
                detachment_check=self._is_green_tide_detachment,
                target_matcher=self._orks_unit_is_boyz,
            )
            self._queue_single_orks_target_selected_defensive_reaction(
                attacking_unit=attacking_unit,
                target_units=list(target_units or []),
                phase_name=phase_name,
                stratagem_names=("STALKIN' TAKTIKS", "STALKIN’ TAKTIKS"),
                detachment_check=self._is_da_big_hunt_detachment,
                target_matcher=self._orks_is_beast_snagga_infantry_or_mounted,
            )
            self._queue_single_orks_target_selected_defensive_reaction(
                attacking_unit=attacking_unit,
                target_units=list(target_units or []),
                phase_name=phase_name,
                stratagem_names=("EXTRA GUBBINZ",),
                detachment_check=self._is_dread_mob_detachment,
                target_matcher=self._orks_is_walker_or_grots_vehicle_not_titanic,
            )
            self._queue_single_orks_target_selected_defensive_reaction(
                attacking_unit=attacking_unit,
                target_units=list(target_units or []),
                phase_name=phase_name,
                stratagem_names=("DUST TRAILS",),
                detachment_check=self._is_speedwaaagh_detachment,
                target_matcher=self._is_orks_unit,
            )
            self._queue_single_orks_target_selected_defensive_reaction(
                attacking_unit=attacking_unit,
                target_units=list(target_units or []),
                phase_name=phase_name,
                stratagem_names=("IMPERVIOUS",),
                detachment_check=self._is_blitz_brigade_detachment,
                target_matcher=self._orks_is_battlewagon_kill_rig_or_hunta_rig,
            )

        self._queue_single_orks_target_selected_defensive_reaction(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
            phase_name=phase_name,
            stratagem_names=("SPEEDIEST FREEKS",),
            detachment_check=self._is_kult_of_speed_detachment,
            target_matcher=self._orks_is_speed_freeks_or_trukk,
        )
        self._queue_single_orks_target_selected_defensive_reaction(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
            phase_name=phase_name,
            stratagem_names=("TOO ARROGANT TO DIE",),
            detachment_check=self._is_bully_boyz_detachment,
            target_matcher=self._orks_is_nobz_or_meganobz_unit,
        )

    def _orks_unit_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        unit: Any,
    ) -> bool:
        expected_event = str(event_name or "").strip()
        expected_name = self._orks_normalize_name(stratagem_name)
        root = self._orks_root(unit)
        root_id = self._orks_sort_key(root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip() != expected_event:
                continue
            if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != expected_name:
                continue
            queued_unit = self._orks_root(reaction.get("target_unit") or reaction.get("unit"))
            queued_id = self._orks_sort_key(queued_unit)
            if queued_unit is root:
                return True
            if root_id and queued_id and root_id == queued_id:
                return True
        return False

    def _orks_phase_end_reaction_already_queued(self, *, stratagem_name: str) -> bool:
        expected = self._orks_normalize_name(stratagem_name)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip() != "phase_end":
                continue
            if self._orks_phase_label(reaction.get("phase_name")) != "fight phase":
                continue
            if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != expected:
                continue
            return True
        return False

    def _queue_single_orks_end_of_opponent_fight_phase_reserves_reaction(
        self,
        *,
        stratagem_names: tuple[str, ...],
        detachment_check,
        target_matcher,
    ) -> None:
        if not bool(detachment_check()):
            return
        stratagem = self._orks_get_available_stratagem_by_names(*stratagem_names)
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._orks_phase_end_reaction_already_queued(stratagem_name=str(getattr(stratagem, "name", "") or "")):
            return

        candidates = self._orks_end_of_opponent_fight_phase_strategic_reserves_candidates(target_matcher=target_matcher)
        if not candidates:
            return
        payload = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": str(getattr(stratagem, "name", "") or stratagem_names[0]),
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_orks_mount_up_ladz_phase_end_reaction(self) -> None:
        if not self._is_blitz_brigade_detachment():
            return
        stratagem = self._orks_get_available_stratagem_by_names("MOUNT UP, LADZ")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._orks_phase_end_reaction_already_queued(stratagem_name=str(getattr(stratagem, "name", "") or "")):
            return

        candidates, passenger_map = self._orks_mount_up_ladz_candidates()
        if not candidates:
            return
        payload: dict[str, Any] = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": str(getattr(stratagem, "name", "") or "MOUNT UP, LADZ"),
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "candidates": list(candidates),
            "transport_candidates": list(candidates),
            "embark_candidates_by_transport": passenger_map,
            "passenger_candidates_by_transport": passenger_map,
        }
        if len(candidates) == 1:
            transport = candidates[0]
            payload["unit"] = transport
            payload["target_unit"] = transport
            payload["transport_unit"] = transport
            passengers = list(passenger_map.get(self._orks_sort_key(transport)) or [])
            if passengers:
                payload["embark_candidates"] = passengers
                payload["passenger_candidates"] = passengers
        self._queue_reaction(payload, use_timer=False)

    def _queue_orks_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if str(getattr(phase, "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        self._queue_orks_mount_up_ladz_phase_end_reaction()
        if player is self.player:
            return
        self._queue_single_orks_end_of_opponent_fight_phase_reserves_reaction(
            stratagem_names=("INSTINCTIVE HUNTERS",),
            detachment_check=self._is_da_big_hunt_detachment,
            target_matcher=self._orks_is_beast_snagga_unit,
        )
        self._queue_single_orks_end_of_opponent_fight_phase_reserves_reaction(
            stratagem_names=("DED SNEAKY",),
            detachment_check=self._is_taktikal_brigade_detachment,
            target_matcher=self._orks_is_kommandos_or_stormboyz_unit,
        )
        self._queue_single_orks_end_of_opponent_fight_phase_reserves_reaction(
            stratagem_names=("EVASIVE MANOOVA",),
            detachment_check=self._is_speedwaaagh_detachment,
            target_matcher=self._orks_is_speed_freeks_or_trukk,
        )

    def _orks_too_arrogant_to_die_candidates(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any] | None,
    ) -> list[Any]:
        if not self._is_bully_boyz_detachment():
            return []
        phase_label = self._orks_current_phase_label()
        if phase_label not in {"shooting phase", "fight phase"}:
            return []
        attacker_root = self._orks_root(attacking_unit)
        if attacker_root is None or self._orks_owned_by_player(attacker_root, self.player):
            return []
        if phase_label == "shooting phase" and self._orks_is_players_turn():
            return []
        return self._orks_target_selected_reaction_candidates(
            list(target_units or []),
            matcher=self._orks_is_nobz_or_meganobz_unit,
        )

    def _orks_always_lookin_fer_a_fight_candidates(self, *, destroyed_by_unit: Any) -> list[Any]:
        if not self._is_bully_boyz_detachment():
            return []
        if self._orks_current_phase_label() != "fight phase":
            return []
        attacker_root = self._orks_root(destroyed_by_unit)
        if attacker_root is None:
            return []
        if not self._orks_owned_by_player(attacker_root, self.player):
            return []
        if not self._orks_on_battlefield(attacker_root, require_targetable=True):
            return []
        if bool(self._unit_cannot_be_target_of_stratagem(attacker_root)):
            return []
        if not self._is_orks_unit(attacker_root):
            return []
        if not self._orks_is_nobz_or_meganobz_unit(attacker_root):
            return []
        return [attacker_root]

    def _orks_cut_em_down_candidates(self, *, enemy_unit: Any) -> list[Any]:
        if not self._is_bully_boyz_detachment():
            return []
        if self._orks_current_phase_label() != "movement phase":
            return []
        if self._orks_is_players_turn():
            return []
        enemy_root = self._orks_root(enemy_unit)
        if enemy_root is None or self._orks_owned_by_player(enemy_root, self.player):
            return []
        if not self._orks_on_battlefield(enemy_root, require_targetable=False):
            return []
        game_map = getattr(getattr(self, "game", None), "map", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
        if not callable(within_engagement):
            return []

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._orks_root(unit)
            if root is None:
                continue
            uid = self._orks_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._orks_on_battlefield(root, require_targetable=True):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_orks_unit(root):
                continue
            if not self._orks_is_nobz_or_meganobz_unit(root):
                continue
            if not bool(within_engagement(root, enemy_root)):
                continue
            candidates.append(root)
        candidates.sort(key=self._orks_sort_key)
        return candidates

    def _queue_orks_bully_boyz_unit_destroyed_reactions(
        self,
        *,
        unit: Any,
        destroyed_by_unit: Any,
    ) -> None:
        if unit is None or destroyed_by_unit is None:
            return
        if not self._is_bully_boyz_detachment():
            return
        if self._orks_current_phase_label() != "fight phase":
            return

        destroyed_root = self._orks_root(unit)
        attacker_root = self._orks_root(destroyed_by_unit)
        if destroyed_root is None or attacker_root is None:
            return
        if self._orks_owned_by_player(destroyed_root, self.player):
            return

        candidates = self._orks_always_lookin_fer_a_fight_candidates(destroyed_by_unit=attacker_root)
        if not candidates:
            return
        stratagem = self._orks_get_available_stratagem_by_names(
            "ALWAYS LOOKIN' FER A FIGHT",
            "ALWAYS LOOKIN’ FER A FIGHT",
        )
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(self._used_stratagems_this_phase):
            return
        if self._orks_unit_reaction_already_queued(
            event_name="unit_destroyed",
            stratagem_name=str(getattr(stratagem, "name", "") or "ALWAYS LOOKIN’ FER A FIGHT"),
            unit=attacker_root,
        ):
            return

        payload = {
            "event": "unit_destroyed",
            "phase_name": "Fight phase",
            "stratagem": str(getattr(stratagem, "name", "") or "ALWAYS LOOKIN’ FER A FIGHT"),
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "destroyed_unit": destroyed_root,
            "destroyed_by_unit": attacker_root,
            "unit": attacker_root,
            "target_unit": attacker_root,
            "candidates": list(candidates),
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_orks_cut_em_down_move_started_reaction(self, *, unit: Any, action: str) -> None:
        if self._orks_normalize_move_action(action) != "fall_back":
            return
        enemy_root = self._orks_root(unit)
        if enemy_root is None:
            return

        candidates = self._orks_cut_em_down_candidates(enemy_unit=enemy_root)
        if not candidates:
            return
        stratagem = self._orks_get_available_stratagem_by_names("CUT'EM DOWN", "CUT’EM DOWN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(self._used_stratagems_this_phase):
            return
        if self._orks_reaction_already_queued(
            event_name="unit_move_started",
            stratagem_name=str(getattr(stratagem, "name", "") or "CUT’EM DOWN"),
            attacking_unit=enemy_root,
        ):
            return

        payload = {
            "event": "unit_move_started",
            "phase_name": "Movement phase",
            "stratagem": str(getattr(stratagem, "name", "") or "CUT’EM DOWN"),
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "unit": candidates[0] if len(candidates) == 1 else None,
            "target_unit": candidates[0] if len(candidates) == 1 else None,
            "moving_unit": enemy_root,
            "enemy_unit": enemy_root,
            "attacking_unit": enemy_root,
            "candidates": list(candidates),
            "action": "fall_back",
        }
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_orks_phase_end_effects(self, *, phase: Any) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"MOVEMENT_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"}:
            return

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return

        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._orks_root(unit)
            if root is None:
                continue
            uid = self._orks_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue

            changed = False
            if phase_key == "MOVEMENT_PHASE":
                source_name = self._orks_normalize_name(str(sr.get("enemy_fallback_desperate_escape_source", "") or ""))
                expires_phase = str(sr.get("enemy_fallback_desperate_escape_expires_phase", "") or "").strip().upper()
                if (
                    bool(sr.get("enemy_fallback_desperate_escape"))
                    and source_name == "cut em down"
                    and (not expires_phase or expires_phase == "MOVEMENT_PHASE")
                ):
                    for key in (
                        "enemy_fallback_desperate_escape",
                        "enemy_fallback_desperate_escape_exclude_monster_vehicle",
                        "enemy_fallback_desperate_escape_bs_penalty",
                        "enemy_fallback_desperate_escape_penalty",
                        "enemy_fallback_desperate_escape_target_enemy_id",
                        "enemy_fallback_desperate_escape_expires_phase",
                        "enemy_fallback_desperate_escape_turn_owner",
                        "enemy_fallback_desperate_escape_turn",
                        "enemy_fallback_desperate_escape_source",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True

            if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                expires_phase = str(sr.get("orks_too_arrogant_to_die_expires_phase", "") or "").strip().upper()
                if bool(sr.get("orks_too_arrogant_to_die_active")) and (not expires_phase or expires_phase == phase_key):
                    for key in (
                        "orks_too_arrogant_to_die_active",
                        "orks_too_arrogant_to_die_threshold",
                        "orks_too_arrogant_to_die_expires_phase",
                        "orks_too_arrogant_to_die_turn_owner",
                        "orks_too_arrogant_to_die_turn",
                        "orks_too_arrogant_to_die_source",
                    ):
                        if key in sr:
                            sr.pop(key, None)
                            changed = True
                    setattr(root, "_shoot_on_death_pending_models", [])
                if phase_key == "FIGHT_PHASE":
                    expires_phase = str(sr.get("orks_bulldozer_brutality_expires_phase", "") or "").strip().upper()
                    if bool(sr.get("orks_bulldozer_brutality_active")) and (not expires_phase or expires_phase == "FIGHT_PHASE"):
                        if bool(sr.get("orks_bulldozer_brutality_added_fight_within_3")) and "fight_within_3" in sr:
                            sr.pop("fight_within_3", None)
                            changed = True
                        if str(sr.get("fight_within_3_active_source", "") or "").strip() == "BULLDOZER BRUTALITY":
                            for key in ("fight_within_3_active", "fight_within_3_active_source"):
                                if key in sr:
                                    sr.pop(key, None)
                                    changed = True
                        for key in (
                            "orks_bulldozer_brutality_active",
                            "orks_bulldozer_brutality_expires_phase",
                            "orks_bulldozer_brutality_turn_owner",
                            "orks_bulldozer_brutality_turn",
                            "orks_bulldozer_brutality_source",
                            "orks_bulldozer_brutality_added_fight_within_3",
                        ):
                            if key in sr:
                                sr.pop(key, None)
                                changed = True
                if phase_key == "SHOOTING_PHASE":
                    expires_phase = str(sr.get("orks_go_get_em_expires_phase", "") or "").strip().upper()
                    if bool(sr.get("orks_go_get_em_active")) and (not expires_phase or expires_phase == "SHOOTING_PHASE"):
                        for key in (
                            "orks_go_get_em_active",
                            "orks_go_get_em_expires_phase",
                            "orks_go_get_em_turn_owner",
                            "orks_go_get_em_turn",
                            "orks_go_get_em_source",
                        ):
                            if key in sr:
                                sr.pop(key, None)
                                changed = True
                        for key in (
                            "orks_go_get_em_phase_key",
                            "orks_go_get_em_attacker_unit_id",
                            "orks_go_get_em_reroll_distance",
                        ):
                            if key in sr:
                                sr.pop(key, None)
                                changed = True

            if changed:
                root.special_rules = sr

    def _on_unit_shooting_resolved_speedwaaagh_mobile_dakkastorm(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_weapon=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self._is_speedwaaagh_detachment():
            return
        if self._orks_current_phase_key() != "SHOOTING_PHASE":
            return
        if not self._orks_is_players_turn():
            return
        source_root = self._orks_root(attacker_unit)
        if source_root is None:
            return
        if not self._orks_owned_by_player(source_root, self.player):
            return
        if not self._orks_on_battlefield(source_root, require_targetable=True):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
            return
        if not self._is_orks_unit(source_root):
            return
        if not self._orks_is_speed_freeks_or_trukk(source_root):
            return

        stratagem = self._orks_get_available_stratagem_by_names("MOBILE DAKKASTORM")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(self._used_stratagems_this_phase):
            return
        candidates = self._speedwaaagh_mobile_dakkastorm_hit_candidates(
            source_root,
            hits_by_target,
            hit_models_by_target_weapon,
        )
        if not candidates:
            return
        if self._orks_unit_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=str(getattr(stratagem, "name", "") or "MOBILE DAKKASTORM"),
            unit=source_root,
        ):
            return
        if not bool(
            stratagem.can_use(
                self.player,
                self.game,
                target_unit=source_root,
                unit=source_root,
                candidates=candidates,
                phase_name="Shooting phase",
            )
        ):
            return
        self._queue_reaction(
            {
                "event": "unit_shooting_resolved",
                "phase": "Shooting phase",
                "phase_name": "Shooting phase",
                "stratagem": str(getattr(stratagem, "name", "") or "MOBILE DAKKASTORM"),
                "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
                "unit": source_root,
                "target_unit": source_root,
                "candidates": list(candidates),
            },
            use_timer=False,
        )

    def _on_unit_shooting_resolved_orks_green_tide(self, attacker_unit=None, **_kwargs) -> None:
        if not self._is_green_tide_detachment():
            return
        if self._orks_phase_label(self._orks_current_phase_label()) != "shooting phase":
            return
        if self._orks_is_players_turn():
            return
        attacker_root = self._orks_root(attacker_unit)
        if attacker_root is None or self._orks_owned_by_player(attacker_root, self.player):
            return
        army_getter = getattr(self.player, "get_army", None)
        army = army_getter() if callable(army_getter) else getattr(self.player, "army", None)
        if army is None:
            return
        queued_units: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._orks_root(unit)
            if root is None:
                continue
            unit_id = self._orks_sort_key(root)
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            matches_attacker = getattr(root, "go_get_em_horde_move_attacker_matches", None)
            if not callable(matches_attacker) or not bool(matches_attacker(attacker_root, game=self.game)):
                continue
            can_horde_move = getattr(root, "can_horde_move", None)
            if not callable(can_horde_move):
                continue
            if not bool(can_horde_move(game=self.game, game_map=getattr(self.game, "map", None))):
                continue
            queued_units.append(root)
        queued_units.sort(key=self._orks_sort_key)
        for root in list(queued_units or []):
            player = getattr(root.get_parent_army(), "player", None)
            rule_fn = getattr(root, "get_go_get_em_horde_move_rule", None)
            rule = rule_fn(game=self.game) if callable(rule_fn) else None
            if not isinstance(rule, dict):
                rule = {}
            source = str(rule.get("source", "") or "GO GET 'EM!").strip() or "GO GET 'EM!"
            message = (
                f"{source}: After the attacker finishes shooting, roll one D6 and make a Normal move up to that distance.\n"
                "This unit must end that move as close as possible to the closest enemy unit and can move within Engagement Range of that unit."
            )
            if bool(rule.get("distance_reroll")):
                message += "\nThis unit can re-roll that D6 because it effectively counts as containing 10 or more models for stratagem checks."
            self.game._queue_reactive_move_confirmation(
                player=player,
                unit=root,
                kind="horde_move",
                movement_type="horde_move",
                source=source,
                message=message,
                attacker_unit=attacker_root,
            )

    def _queue_orks_move_started_reactions(self, *, unit: Any, action: str) -> None:
        self._queue_orks_cut_em_down_move_started_reaction(unit=unit, action=action)
        self._queue_orks_superfuelled_boiler_move_started_reaction(unit=unit, action=action)

    def _queue_orks_superfuelled_boiler_move_started_reaction(self, *, unit: Any, action: str) -> None:
        if unit is None:
            return
        if not self._is_dread_mob_detachment():
            return
        if self._orks_phase_label(getattr(self, "_current_phase_name", "")) != "movement phase":
            return
        if not self._orks_is_players_turn():
            return
        if self._orks_normalize_move_action(action) != "advance":
            return

        root = self._orks_root(unit)
        if root is None:
            return
        if not self._orks_owned_by_player(root, self.player):
            return
        if not self._orks_on_battlefield(root, require_targetable=True):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        if not self._is_orks_unit(root):
            return
        if not self._orks_unit_contains_keyword(root, "WALKER"):
            return

        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "moved_this_round", False)):
            return
        if bool(getattr(round_state, "advanced_this_round", False)):
            return
        if bool(getattr(round_state, "fell_back_this_round", False)):
            return

        stratagem = self._orks_get_available_stratagem_by_names("SUPERFUELLED BOILER")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(self._used_stratagems_this_phase):
            return
        if self._orks_unit_reaction_already_queued(
            event_name="unit_move_started",
            stratagem_name=str(getattr(stratagem, "name", "") or "SUPERFUELLED BOILER"),
            unit=root,
        ):
            return

        payload = {
            "event": "unit_move_started",
            "phase_name": "Movement phase",
            "stratagem": str(getattr(stratagem, "name", "") or "SUPERFUELLED BOILER"),
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "unit": root,
            "target_unit": root,
            "candidates": [root],
            "action": "advance",
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_orks_move_end_reactions(self, *, unit: Any, action: str) -> None:
        self._queue_orks_charge_end_mortal_wound_reactions(unit=unit, action=action)
        self._queue_orks_full_throttle_charge_end_reaction(unit=unit, action=action)
        self._queue_orks_squig_flingin_move_end_reaction(unit=unit, action=action)
        self._queue_orks_taktikal_retreat_move_end_reaction(unit=unit, action=action)

    def _orks_enemy_battleshock_candidates_within_distance(
        self,
        *,
        source_unit: Any,
        max_distance: float,
    ) -> list[Any]:
        source_root = self._orks_root(source_unit)
        if source_root is None:
            return []
        game_map = getattr(getattr(self, "game", None), "map", None)
        get_enemy_units = getattr(game_map, "get_enemy_units", None) if game_map is not None else None
        if not callable(get_enemy_units):
            return []

        seen: set[str] = set()
        candidates: list[Any] = []
        for enemy_unit in list(get_enemy_units(source_root) or []):
            enemy_root = self._orks_root(enemy_unit)
            if enemy_root is None:
                continue
            if self._orks_owned_by_player(enemy_root, self.player):
                continue
            if not self._orks_on_battlefield(enemy_root, require_targetable=False):
                continue
            distance = self._orks_distance_between_units(source_root, enemy_root)
            if distance is None or float(distance) > float(max_distance) + 1e-6:
                continue
            enemy_id = self._orks_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            candidates.append(enemy_root)
        candidates.sort(key=self._orks_sort_key)
        return candidates

    def _queue_single_orks_move_end_enemy_battleshock_reaction(
        self,
        *,
        unit: Any,
        action: str,
        stratagem_names: tuple[str, ...],
        detachment_check,
        source_matcher,
        max_distance: float,
    ) -> None:
        if unit is None:
            return
        if not bool(detachment_check()):
            return
        if self._orks_phase_label(getattr(self, "_current_phase_name", "")) != "movement phase":
            return
        if not self._orks_is_players_turn():
            return
        action_key = self._orks_normalize_move_action(action)
        if action_key not in {"move", "advance", "fall_back"}:
            return

        source_root = self._orks_root(unit)
        if source_root is None:
            return
        if not self._orks_owned_by_player(source_root, self.player):
            return
        if not self._orks_on_battlefield(source_root, require_targetable=True):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
            return
        if not self._is_orks_unit(source_root):
            return
        if not bool(source_matcher(source_root)):
            return

        stratagem = self._orks_get_available_stratagem_by_names(*stratagem_names)
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(self._used_stratagems_this_phase):
            return
        if self._orks_unit_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=str(getattr(stratagem, "name", "") or stratagem_names[0]),
            unit=source_root,
        ):
            return

        enemy_candidates = self._orks_enemy_battleshock_candidates_within_distance(
            source_unit=source_root,
            max_distance=float(max_distance),
        )
        if not enemy_candidates:
            return

        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": str(getattr(stratagem, "name", "") or stratagem_names[0]),
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "unit": source_root,
            "target_unit": source_root,
            "source_unit": source_root,
            "candidates": [source_root],
            "enemy_candidates": list(enemy_candidates),
            "action": action_key,
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_orks_squig_flingin_move_end_reaction(self, *, unit: Any, action: str) -> None:
        self._queue_single_orks_move_end_enemy_battleshock_reaction(
            unit=unit,
            action=action,
            stratagem_names=("SQUIG FLINGIN'",),
            detachment_check=self._is_kult_of_speed_detachment,
            source_matcher=self._orks_is_speed_freeks_or_trukk,
            max_distance=9.0,
        )

    def _queue_single_orks_charge_end_mortal_wound_reaction(
        self,
        *,
        unit: Any,
        action: str,
        stratagem_names: tuple[str, ...],
        detachment_check,
        source_matcher,
    ) -> None:
        if unit is None:
            return
        if not bool(detachment_check()):
            return
        if self._orks_phase_label(getattr(self, "_current_phase_name", "")) != "charge phase":
            return
        if not self._orks_is_players_turn():
            return
        if self._orks_normalize_move_action(action) != "charge":
            return

        source_root = self._orks_root(unit)
        if source_root is None:
            return
        if not self._orks_owned_by_player(source_root, self.player):
            return
        if not self._orks_on_battlefield(source_root, require_targetable=True):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
            return
        if not self._is_orks_unit(source_root):
            return
        if not bool(source_matcher(source_root)):
            return

        stratagem = self._orks_get_available_stratagem_by_names(*stratagem_names)
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(self._used_stratagems_this_phase):
            return
        if self._orks_unit_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=str(getattr(stratagem, "name", "") or stratagem_names[0]),
            unit=source_root,
        ):
            return

        enemy_candidates = self._orks_charge_end_mortal_wound_enemy_candidates(source_root)
        if not enemy_candidates:
            return

        payload = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": str(getattr(stratagem, "name", "") or stratagem_names[0]),
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "unit": source_root,
            "target_unit": source_root,
            "source_unit": source_root,
            "candidates": [source_root],
            "enemy_candidates": list(enemy_candidates),
            "action": "charge",
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_orks_charge_end_mortal_wound_reactions(self, *, unit: Any, action: str) -> None:
        self._queue_single_orks_charge_end_mortal_wound_reaction(
            unit=unit,
            action=action,
            stratagem_names=("CRUSHING IMPACT",),
            detachment_check=self._is_bully_boyz_detachment,
            source_matcher=self._orks_is_nobz_or_meganobz_unit,
        )
        self._queue_single_orks_charge_end_mortal_wound_reaction(
            unit=unit,
            action=action,
            stratagem_names=("UNSTOPPABLE MOMENTUM",),
            detachment_check=self._is_da_big_hunt_detachment,
            source_matcher=self._orks_is_beast_snagga_mounted_unit,
        )
        self._queue_single_orks_charge_end_mortal_wound_reaction(
            unit=unit,
            action=action,
            stratagem_names=("KRUNCHIN' DESCENT", "KRUNCHIN’ DESCENT"),
            detachment_check=self._is_taktikal_brigade_detachment,
            source_matcher=self._orks_is_stormboyz_unit,
        )

    def _queue_orks_full_throttle_charge_end_reaction(self, *, unit: Any, action: str) -> None:
        if unit is None:
            return
        if not self._is_kult_of_speed_detachment():
            return
        if self._orks_phase_label(getattr(self, "_current_phase_name", "")) != "charge phase":
            return
        if not self._orks_is_players_turn():
            return
        if self._orks_normalize_move_action(action) != "charge":
            return

        source_root = self._orks_root(unit)
        if source_root is None:
            return
        if not self._orks_owned_by_player(source_root, self.player):
            return
        if not self._orks_on_battlefield(source_root, require_targetable=True):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
            return
        if not self._orks_is_speed_freeks_unit(source_root):
            return
        if not self._orks_charge_end_mortal_wound_enemy_candidates(source_root):
            return

        stratagem = self._orks_get_available_stratagem_by_names("FULL THROTTLE!")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(self._used_stratagems_this_phase):
            return
        if self._orks_unit_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=str(getattr(stratagem, "name", "") or "FULL THROTTLE!"),
            unit=source_root,
        ):
            return

        payload = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": str(getattr(stratagem, "name", "") or "FULL THROTTLE!"),
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "unit": source_root,
            "target_unit": source_root,
            "source_unit": source_root,
            "candidates": [source_root],
            "action": "charge",
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_orks_taktikal_retreat_move_end_reaction(self, *, unit: Any, action: str) -> None:
        if unit is None:
            return
        if not self._is_taktikal_brigade_detachment():
            return
        if self._orks_phase_label(getattr(self, "_current_phase_name", "")) != "movement phase":
            return
        if not self._orks_is_players_turn():
            return
        if self._orks_normalize_move_action(action) != "fall_back":
            return

        root = self._orks_root(unit)
        if root is None:
            return
        if not self._orks_owned_by_player(root, self.player):
            return
        if not self._orks_on_battlefield(root, require_targetable=True):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        if not self._is_orks_unit(root):
            return

        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "fell_back_this_round", False)):
            return

        stratagem = self._orks_get_available_stratagem_by_names("TAKTIKAL RETREAT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(self._used_stratagems_this_phase):
            return
        if self._orks_unit_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=str(getattr(stratagem, "name", "") or "TAKTIKAL RETREAT"),
            unit=root,
        ):
            return

        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": str(getattr(stratagem, "name", "") or "TAKTIKAL RETREAT"),
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "unit": root,
            "target_unit": root,
            "candidates": [root],
            "action": "fall_back",
        }
        self._queue_reaction(payload, use_timer=False)

    def _orks_resolve_move_trigger_context(
        self,
        stratagem_name: str,
        **kwargs,
    ) -> tuple[Any, list[Any], str, str, bool]:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        action = str(kwargs.get("action") or kwargs.get("trigger") or "").strip()
        phase_name = str(kwargs.get("phase_name") or "").strip()
        from_pending = False
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]

        normalized_name = self._orks_normalize_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != normalized_name:
                continue
            from_pending = True
            if target_unit is None:
                target_unit = reaction.get("target_unit") or reaction.get("unit")
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if not action:
                action = str(reaction.get("action") or "").strip()
            if not phase_name:
                phase_name = str(reaction.get("phase_name") or "").strip()
            if target_unit is None and len(candidates) == 1:
                target_unit = candidates[0]
            break
        return target_unit, candidates, action, phase_name, from_pending

    def _orks_resolve_target_selected_context(
        self,
        stratagem_name: str,
        **kwargs,
    ) -> tuple[Any, Any, list[Any], str, bool]:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        phase_name = str(kwargs.get("phase_name") or "").strip()
        from_pending = False
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]

        normalized_name = self._orks_normalize_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != normalized_name:
                continue
            from_pending = True
            if target_unit is None:
                target_unit = reaction.get("target_unit") or reaction.get("unit")
            if attacking_unit is None:
                attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if not phase_name:
                phase_name = str(reaction.get("phase_name") or "").strip()
            if target_unit is None and len(candidates) == 1:
                target_unit = candidates[0]
            break
        return target_unit, attacking_unit, candidates, phase_name, from_pending

    def _orks_resolve_unit_destroyed_context(
        self,
        stratagem_name: str,
        **kwargs,
    ) -> tuple[Any, Any, Any, list[Any], str, bool]:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        destroyed_unit = kwargs.get("destroyed_unit")
        destroyed_by_unit = kwargs.get("destroyed_by_unit")
        candidates = list(kwargs.get("candidates") or [])
        phase_name = str(kwargs.get("phase_name") or "").strip()
        from_pending = False
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]

        normalized_name = self._orks_normalize_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != normalized_name:
                continue
            from_pending = True
            if target_unit is None:
                target_unit = reaction.get("target_unit") or reaction.get("unit")
            if destroyed_unit is None:
                destroyed_unit = reaction.get("destroyed_unit")
            if destroyed_by_unit is None:
                destroyed_by_unit = reaction.get("destroyed_by_unit")
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if not phase_name:
                phase_name = str(reaction.get("phase_name") or "").strip()
            if target_unit is None and len(candidates) == 1:
                target_unit = candidates[0]
            break
        return target_unit, destroyed_unit, destroyed_by_unit, candidates, phase_name, from_pending

    def _orks_resolve_move_end_enemy_battleshock_context(
        self,
        stratagem_name: str,
        **kwargs,
    ) -> tuple[Any, list[Any], Any, list[Any], str, str, bool]:
        source_unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("source_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
        enemy_candidates = list(kwargs.get("enemy_candidates") or [])
        action = str(kwargs.get("action") or kwargs.get("trigger") or "").strip()
        phase_name = str(kwargs.get("phase_name") or "").strip()
        from_pending = False

        if source_unit is None and len(candidates) == 1:
            source_unit = candidates[0]
        if enemy_unit is None and len(enemy_candidates) == 1:
            enemy_unit = enemy_candidates[0]

        normalized_name = self._orks_normalize_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != normalized_name:
                continue
            from_pending = True
            if source_unit is None:
                source_unit = reaction.get("target_unit") or reaction.get("unit") or reaction.get("source_unit")
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if enemy_unit is None:
                enemy_unit = reaction.get("enemy_unit") or reaction.get("target_enemy_unit")
            if not enemy_candidates:
                enemy_candidates = list(reaction.get("enemy_candidates") or [])
            if not action:
                action = str(reaction.get("action") or "").strip()
            if not phase_name:
                phase_name = str(reaction.get("phase_name") or "").strip()
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if enemy_unit is None and len(enemy_candidates) == 1:
                enemy_unit = enemy_candidates[0]
            break
        return source_unit, candidates, enemy_unit, enemy_candidates, action, phase_name, from_pending

    @staticmethod
    def _orks_normalize_move_action(action: Any) -> str:
        action_key = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        action_key = re.sub(r"_+", "_", action_key)
        if action_key in {"move", "normal_move"}:
            return "move"
        if action_key == "advance":
            return "advance"
        if action_key in {"fall_back", "fallback"}:
            return "fall_back"
        if action_key in {"charge", "charge_move"}:
            return "charge"
        return ""

    def _orks_distance_between_units(self, source_unit: Any, target_unit: Any) -> Optional[float]:
        source_root = self._orks_root(source_unit)
        target_root = self._orks_root(target_unit)
        if source_root is None or target_root is None:
            return None
        game_map = getattr(getattr(self, "game", None), "map", None)
        get_distance = getattr(game_map, "get_distance_between_units", None) if game_map is not None else None
        if not callable(get_distance):
            return None
        try:
            return float(get_distance(source_root, target_root))
        except (TypeError, ValueError):
            return None

    def _capture_orks_opponent_movement_phase_start_engagements(self, *, player: Any, phase: Any) -> None:
        tracker = {
            "phase": "",
            "turn": int(self._orks_current_turn()),
            "by_enemy": {},
        }
        self._orks_reactive_reposition_start_engagements = tracker

        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        if player is self.player:
            return
        if self._orks_is_players_turn():
            return
        if not (
            self._is_da_big_hunt_detachment()
            or self._is_freebooter_krew_detachment()
            or self._is_taktikal_brigade_detachment()
            or self._is_kult_of_speed_detachment()
        ):
            return

        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(within_engagement):
            return

        by_enemy: dict[str, dict[str, Any]] = {}
        for friendly_root in self._orks_collect_owned_units():
            if not self._orks_on_battlefield(friendly_root, require_targetable=False):
                continue
            if not self._is_orks_unit(friendly_root):
                continue
            friendly_id = self._orks_sort_key(friendly_root)
            if not friendly_id:
                continue
            for enemy_unit in list(get_enemy_units(friendly_root) or []):
                enemy_root = self._orks_root(enemy_unit)
                if enemy_root is None:
                    continue
                if self._orks_owned_by_player(enemy_root, self.player):
                    continue
                if not self._orks_on_battlefield(enemy_root, require_targetable=False):
                    continue
                enemy_id = self._orks_sort_key(enemy_root)
                if not enemy_id:
                    continue
                if not bool(within_engagement(friendly_root, enemy_root)):
                    continue
                by_enemy.setdefault(enemy_id, {})[friendly_id] = friendly_root

        tracker["phase"] = "MOVEMENT_PHASE"
        tracker["turn"] = int(self._orks_current_turn())
        tracker["by_enemy"] = {
            enemy_id: sorted(list(unit_map.values()), key=self._orks_sort_key)
            for enemy_id, unit_map in sorted(by_enemy.items(), key=lambda item: str(item[0] or ""))
        }

    def _orks_start_phase_engaged_candidates_for_enemy(self, enemy_unit: Any) -> list[Any]:
        enemy_root = self._orks_root(enemy_unit)
        enemy_id = self._orks_sort_key(enemy_root)
        if enemy_root is None or not enemy_id:
            return []
        tracker = getattr(self, "_orks_reactive_reposition_start_engagements", None)
        if not isinstance(tracker, dict):
            return []
        if str(tracker.get("phase", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return []
        try:
            marked_turn = int(tracker.get("turn", 0) or 0)
        except (TypeError, ValueError):
            marked_turn = 0
        current_turn = int(self._orks_current_turn())
        if marked_turn and current_turn and marked_turn != current_turn:
            return []
        by_enemy = tracker.get("by_enemy", {})
        if not isinstance(by_enemy, dict):
            return []
        seen: set[str] = set()
        results: list[Any] = []
        for unit in list(by_enemy.get(enemy_id, []) or []):
            root = self._orks_root(unit)
            if root is None:
                continue
            uid = self._orks_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._orks_owned_by_player(root, self.player):
                continue
            if not self._orks_on_battlefield(root, require_targetable=False):
                continue
            results.append(root)
        results.sort(key=self._orks_sort_key)
        return results

    def _orks_was_engaged_with_enemy_at_movement_phase_start(self, unit: Any, enemy_unit: Any) -> bool:
        return self._orks_unit_in_candidates(
            unit,
            self._orks_start_phase_engaged_candidates_for_enemy(enemy_unit),
        )

    def _orks_is_speed_freeks_unit(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        return self._orks_unit_contains_keyword(root, "SPEED FREEKS")

    def _orks_is_gretchin_unit(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        return bool(self._orks_unit_contains_any_keyword(root, ("GROT", "GROTS", "GRETCHIN")))

    def _orks_reactive_reposition_candidates(
        self,
        *,
        enemy_unit: Any,
        target_matcher,
        require_start_phase_engaged: bool,
        require_not_engaged_now: bool,
        max_distance_to_enemy: Optional[float] = None,
    ) -> list[Any]:
        enemy_root = self._orks_root(enemy_unit)
        if enemy_root is None:
            return []
        if self._orks_owned_by_player(enemy_root, self.player):
            return []
        if not self._orks_on_battlefield(enemy_root, require_targetable=False):
            return []

        source_units = (
            self._orks_start_phase_engaged_candidates_for_enemy(enemy_root)
            if require_start_phase_engaged
            else self._orks_collect_owned_units()
        )
        source_units = sorted(list(source_units or []), key=self._orks_sort_key)

        seen: set[str] = set()
        results: list[Any] = []
        for unit in source_units:
            root = self._orks_root(unit)
            if root is None:
                continue
            uid = self._orks_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._orks_owned_by_player(root, self.player):
                continue
            if not self._orks_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_orks_unit(root):
                continue
            if require_start_phase_engaged and not self._orks_was_engaged_with_enemy_at_movement_phase_start(root, enemy_root):
                continue
            if require_not_engaged_now and self._orks_is_unit_engaged(root):
                continue
            if max_distance_to_enemy is not None:
                distance = self._orks_distance_between_units(root, enemy_root)
                if distance is None or float(distance) > float(max_distance_to_enemy) + 1e-6:
                    continue
            if not bool(target_matcher(root)):
                continue
            results.append(root)
        results.sort(key=self._orks_sort_key)
        return results

    def _queue_single_orks_reactive_reposition_reaction(
        self,
        *,
        enemy_unit: Any,
        action_key: str,
        stratagem_names: tuple[str, ...],
        detachment_check,
        target_matcher,
        allowed_actions: tuple[str, ...],
        require_start_phase_engaged: bool,
        require_not_engaged_now: bool,
        max_distance_to_enemy: Optional[float] = None,
    ) -> None:
        if not bool(detachment_check()):
            return
        if action_key not in set(allowed_actions or ()):
            return
        enemy_root = self._orks_root(enemy_unit)
        if enemy_root is None:
            return
        if self._orks_owned_by_player(enemy_root, self.player):
            return
        if not self._orks_on_battlefield(enemy_root, require_targetable=False):
            return

        stratagem = self._orks_get_available_stratagem_by_names(*stratagem_names)
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in set(self._used_stratagems_this_phase):
            return
        if self._orks_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=str(getattr(stratagem, "name", "") or stratagem_names[0]),
            attacking_unit=enemy_root,
        ):
            return

        candidates = self._orks_reactive_reposition_candidates(
            enemy_unit=enemy_root,
            target_matcher=target_matcher,
            require_start_phase_engaged=require_start_phase_engaged,
            require_not_engaged_now=require_not_engaged_now,
            max_distance_to_enemy=max_distance_to_enemy,
        )
        if not candidates:
            return

        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": str(getattr(stratagem, "name", "") or stratagem_names[0]),
            "cp_cost": int(getattr(stratagem, "cp_cost", 0) or 0),
            "moving_unit": enemy_root,
            "enemy_unit": enemy_root,
            "action": action_key,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_orks_reactive_reposition_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None:
            return
        if self._orks_phase_label(getattr(self, "_current_phase_name", "")) != "movement phase":
            return
        if self._orks_is_players_turn():
            return
        action_key = self._orks_normalize_move_action(action)
        if action_key not in {"move", "advance", "fall_back"}:
            return
        enemy_root = self._orks_root(unit)
        if enemy_root is None:
            return
        if self._orks_owned_by_player(enemy_root, self.player):
            return
        if not self._orks_on_battlefield(enemy_root, require_targetable=False):
            return

        if action_key == "fall_back":
            self._queue_single_orks_reactive_reposition_reaction(
                enemy_unit=enemy_root,
                action_key=action_key,
                stratagem_names=("WHERE D'YA FINK YOU'RE GOING?", "WHERE D’YA FINK YOU’RE GOING?"),
                detachment_check=self._is_da_big_hunt_detachment,
                target_matcher=self._orks_is_beast_snagga_infantry_or_mounted,
                allowed_actions=("fall_back",),
                require_start_phase_engaged=True,
                require_not_engaged_now=True,
                max_distance_to_enemy=None,
            )
            self._queue_single_orks_reactive_reposition_reaction(
                enemy_unit=enemy_root,
                action_key=action_key,
                stratagem_names=("KRUMP AND RUN",),
                detachment_check=self._is_freebooter_krew_detachment,
                target_matcher=self._is_orks_unit,
                allowed_actions=("fall_back",),
                require_start_phase_engaged=True,
                require_not_engaged_now=True,
                max_distance_to_enemy=None,
            )
            self._queue_single_orks_reactive_reposition_reaction(
                enemy_unit=enemy_root,
                action_key=action_key,
                stratagem_names=("ON TO DA NEXT",),
                detachment_check=self._is_taktikal_brigade_detachment,
                target_matcher=self._is_orks_unit,
                allowed_actions=("fall_back",),
                require_start_phase_engaged=True,
                require_not_engaged_now=False,
                max_distance_to_enemy=None,
            )

        self._queue_single_orks_reactive_reposition_reaction(
            enemy_unit=enemy_root,
            action_key=action_key,
            stratagem_names=("MORE GITZ OVER 'ERE!", "MORE GITZ OVER ’ERE!"),
            detachment_check=self._is_kult_of_speed_detachment,
            target_matcher=self._orks_is_speed_freeks_unit,
            allowed_actions=("move", "advance", "fall_back"),
            require_start_phase_engaged=False,
            require_not_engaged_now=True,
            max_distance_to_enemy=9.0,
        )
        self._queue_single_orks_reactive_reposition_reaction(
            enemy_unit=enemy_root,
            action_key=action_key,
            stratagem_names=("CONNIVING RUNTS",),
            detachment_check=self._is_dread_mob_detachment,
            target_matcher=self._orks_is_gretchin_unit,
            allowed_actions=("move", "advance", "fall_back"),
            require_start_phase_engaged=False,
            require_not_engaged_now=True,
            max_distance_to_enemy=9.0,
        )

    def _orks_resolve_reactive_reposition_context(
        self,
        stratagem_name: str,
        **kwargs,
    ) -> tuple[Any, Any, list[Any], str, str, bool]:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        moving_unit = kwargs.get("moving_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        action = str(kwargs.get("action") or kwargs.get("trigger") or "").strip()
        phase_name = str(kwargs.get("phase_name") or "").strip()
        from_pending = False

        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]

        normalized_name = self._orks_normalize_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != normalized_name:
                continue
            from_pending = True
            if target_unit is None:
                target_unit = reaction.get("target_unit") or reaction.get("unit")
            if moving_unit is None:
                moving_unit = reaction.get("moving_unit") or reaction.get("enemy_unit")
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if not action:
                action = str(reaction.get("action") or "").strip()
            if not phase_name:
                phase_name = str(reaction.get("phase_name") or "").strip()
            if target_unit is None and len(candidates) == 1:
                target_unit = candidates[0]
            break
        return target_unit, moving_unit, candidates, action, phase_name, from_pending

    def _use_orks_reactive_reposition_stratagem(
        self,
        stratagem: Any,
        *,
        stratagem_name: str,
        detachment_check,
        target_matcher,
        target_error: str,
        allowed_actions: tuple[str, ...],
        require_start_phase_engaged: bool,
        require_not_engaged_now: bool,
        max_distance_to_enemy: Optional[float],
        reactive_move_kind: str,
        pre_move_rider: dict | None = None,
        **kwargs,
    ) -> bool:
        if not bool(detachment_check()):
            return False
        target_unit, moving_unit, candidates, action, phase_name, from_pending = self._orks_resolve_reactive_reposition_context(
            stratagem_name,
            **kwargs,
        )
        if target_unit is None:
            logger.error("ERROR: %s: no target unit provided", stratagem_name)
            return False
        phase_label = self._orks_phase_label(phase_name or self._orks_current_phase_label())
        if phase_label != "movement phase":
            logger.error("ERROR: %s: wrong phase", stratagem_name)
            return False
        if self._orks_is_players_turn():
            logger.error("ERROR: %s: not opponent's Movement phase", stratagem_name)
            return False
        action_key = self._orks_normalize_move_action(action)
        if not from_pending and not action_key:
            logger.error("ERROR: %s: missing movement trigger context", stratagem_name)
            return False
        if action_key not in set(allowed_actions or ()):
            logger.error("ERROR: %s: invalid trigger action", stratagem_name)
            return False

        root = self._orks_root(target_unit)
        if root is None:
            return False
        if not self._orks_owned_by_player(root, self.player):
            logger.error("ERROR: %s: target unit is not yours", stratagem_name)
            return False
        if not self._orks_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: %s: target must be on battlefield and targetable", stratagem_name)
            return False
        if not self._is_orks_unit(root):
            logger.error("ERROR: %s: target must be an ORKS unit", stratagem_name)
            return False
        if not bool(target_matcher(root)):
            logger.error("ERROR: %s: %s", stratagem_name, target_error)
            return False

        moving_root = self._orks_root(moving_unit)
        if moving_root is None:
            logger.error("ERROR: %s: missing enemy trigger unit", stratagem_name)
            return False
        if self._orks_owned_by_player(moving_root, self.player):
            logger.error("ERROR: %s: trigger unit is not enemy", stratagem_name)
            return False
        if not self._orks_on_battlefield(moving_root, require_targetable=False):
            logger.error("ERROR: %s: trigger unit is not on battlefield", stratagem_name)
            return False

        expected_candidates = list(candidates or [])
        if not expected_candidates:
            expected_candidates = self._orks_reactive_reposition_candidates(
                enemy_unit=moving_root,
                target_matcher=target_matcher,
                require_start_phase_engaged=require_start_phase_engaged,
                require_not_engaged_now=require_not_engaged_now,
                max_distance_to_enemy=max_distance_to_enemy,
            )
        if not expected_candidates or not self._orks_unit_in_candidates(root, expected_candidates):
            logger.error("ERROR: %s: selected unit is not currently eligible", stratagem_name)
            return False
        if require_start_phase_engaged and not self._orks_was_engaged_with_enemy_at_movement_phase_start(root, moving_root):
            logger.error("ERROR: %s: target was not within Engagement Range at phase start", stratagem_name)
            return False
        if require_not_engaged_now and self._orks_is_unit_engaged(root):
            logger.error("ERROR: %s: target must not be within Engagement Range", stratagem_name)
            return False
        if max_distance_to_enemy is not None:
            distance = self._orks_distance_between_units(root, moving_root)
            if distance is None or float(distance) > float(max_distance_to_enemy) + 1e-6:
                logger.error("ERROR: %s: target must be within %.1f\" of the enemy unit", stratagem_name, float(max_distance_to_enemy))
                return False

        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            moving_unit=moving_root,
            phase_name="Movement phase",
        ):
            logger.error("ERROR: %s: cannot be used in current state", stratagem_name)
            return False
        queue_move = getattr(getattr(self, "game", None), "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            logger.error("ERROR: %s: reactive move queue is unavailable", stratagem_name)
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        extra_context = None
        if isinstance(pre_move_rider, dict) and pre_move_rider:
            rider_result = self._orks_resolve_reactive_move_pre_move_rider(
                unit=root,
                enemy_unit=moving_root,
                source_name=str(getattr(stratagem, "name", "") or stratagem_name),
                rider_spec=pre_move_rider,
            )
            if rider_result:
                extra_context = {"pre_move_rider_result": rider_result}

        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind=str(reactive_move_kind or "reactive_reposition"),
            movement_type="reactive",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or stratagem_name),
            moving_unit=moving_root,
            range_value=int(max_distance_to_enemy) if max_distance_to_enemy is not None else None,
            extra_context=extra_context,
        )
        if request is None:
            logger.error("ERROR: %s: failed to queue reactive move", stratagem_name)
            return False

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: %s: %s can make a Normal move up to 6\".",
            stratagem_name,
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_mobile_dakkastorm(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_speedwaaagh_detachment():
            return False
        phase_label = self._orks_phase_label(kwargs.get("phase_name") or self._orks_current_phase_label())
        if phase_label != "shooting phase":
            logger.error("ERROR: MOBILE DAKKASTORM: wrong phase")
            return False
        if not self._orks_is_players_turn():
            logger.error("ERROR: MOBILE DAKKASTORM: not your Shooting phase")
            return False

        source_unit = kwargs.get("unit") or kwargs.get("source_unit") or kwargs.get("target_unit")
        pending = None
        if source_unit is None or not list(kwargs.get("candidates") or []):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != "mobile dakkastorm":
                    continue
                pending = reaction
                break
        if source_unit is None and pending is not None:
            source_unit = pending.get("unit") or pending.get("target_unit") or pending.get("source_unit")
        source_root = self._orks_root(source_unit)
        if source_root is None:
            logger.error("ERROR: MOBILE DAKKASTORM: no source unit provided")
            return False
        if not self._orks_owned_by_player(source_root, self.player):
            logger.error("ERROR: MOBILE DAKKASTORM: source unit is not yours")
            return False
        if not self._orks_on_battlefield(source_root, require_targetable=True):
            logger.error("ERROR: MOBILE DAKKASTORM: source unit must be on the battlefield")
            return False
        if not self._is_orks_unit(source_root):
            logger.error("ERROR: MOBILE DAKKASTORM: source unit must be ORKS")
            return False
        if not self._orks_is_speed_freeks_or_trukk(source_root):
            logger.error("ERROR: MOBILE DAKKASTORM: source unit must be SPEED FREEKS or TRUKK")
            return False
        if pending is None and not bool(getattr(getattr(source_root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: MOBILE DAKKASTORM: source unit has not shot")
            return False

        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        if not candidates:
            candidates = self._speedwaaagh_mobile_dakkastorm_hit_candidates(
                source_root,
                kwargs.get("hits_by_target") or {},
                kwargs.get("hit_models_by_target_weapon"),
            )
        candidates = [self._orks_root(candidate) for candidate in candidates if self._orks_root(candidate) is not None]
        candidates = sorted(candidates, key=self._orks_sort_key)
        if not candidates:
            logger.error("ERROR: MOBILE DAKKASTORM: no eligible enemy units were hit by non-Indirect Fire attacks")
            return False

        direct_target = kwargs.get("enemy_unit") or kwargs.get("quarry") or kwargs.get("selected_unit")
        if direct_target is not None:
            target_root = self._orks_root(direct_target)
            if target_root not in candidates:
                logger.error("ERROR: MOBILE DAKKASTORM: selected enemy unit is not eligible")
                return False
            mgr = self._orks_detachment_mgr()
            marker = getattr(mgr, "mark_speedwaaagh_mobile_dakkastorm_target", None) if mgr is not None else None
            if not callable(marker):
                logger.error("ERROR: MOBILE DAKKASTORM: detachment manager unavailable")
                return False
            if not self._orks_spend_cp(stratagem, target_unit=source_root):
                return False
            if not bool(
                marker(
                    target_root,
                    game=self.game,
                    player=self.player,
                    phase_name="SHOOTING_PHASE",
                    source=str(getattr(stratagem, "name", "") or "MOBILE DAKKASTORM"),
                )
            ):
                logger.error("ERROR: MOBILE DAKKASTORM: failed to mark target")
                return False
            self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: MOBILE DAKKASTORM: %s is vulnerable to SPEED FREEKS/TRUKK attacks.",
                getattr(target_root, "name", "Unit"),
            )
            return True

        request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
        if self.game is None or not callable(request_decision):
            logger.error("ERROR: MOBILE DAKKASTORM: no decision queue available")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=source_root):
            return False
        if not self._queue_speedwaaagh_mobile_dakkastorm_target_decision(
            stratagem=stratagem,
            source_unit=source_root,
            candidates=candidates,
        ):
            logger.error("ERROR: MOBILE DAKKASTORM: failed to queue target selection")
            return False
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: MOBILE DAKKASTORM: choose a hit enemy unit to mark.")
        return True

    def _use_orks_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        name_norm = self._orks_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u == "BULLDOZER BRUTALITY":
            return self._use_orks_bulldozer_brutality(stratagem, **kwargs)
        if name_u == "ARMED TO DATEEF":
            return self._use_orks_armed_to_dateef(stratagem, **kwargs)
        if name_u == "TOO ARROGANT TO DIE":
            return self._use_orks_too_arrogant_to_die(stratagem, **kwargs)
        if name_norm == "always lookin fer a fight":
            return self._use_orks_always_lookin_fer_a_fight(stratagem, **kwargs)
        if name_u == "GET STUCK IN, LADZ!" or name_norm == "get stuck in ladz":
            return self._use_orks_get_stuck_in_ladz(stratagem, **kwargs)
        if name_u == "GRAB AND BASH" or name_norm == "grab and bash":
            return self._use_orks_grab_and_bash(stratagem, **kwargs)
        if name_norm == "braggin rights":
            return self._use_orks_braggin_rights(stratagem, **kwargs)
        if name_u == "COMPETITIVE STREAK":
            return self._use_orks_competitive_streak(stratagem, **kwargs)
        if name_norm == "go get em":
            return self._use_orks_go_get_em(stratagem, **kwargs)
        if name_u == "TIDE OF MUSCLE":
            return self._use_orks_tide_of_muscle(stratagem, **kwargs)
        if name_norm == "cut em down":
            return self._use_orks_cut_em_down(stratagem, **kwargs)
        if name_u == "INSTINCTIVE HUNTERS":
            return self._use_orks_instinctive_hunters(stratagem, **kwargs)
        if name_u == "DED SNEAKY":
            return self._use_orks_ded_sneaky(stratagem, **kwargs)
        if name_u == "EVASIVE MANOOVA":
            return self._use_orks_evasive_manoova(stratagem, **kwargs)
        if name_u == "CRUSHING IMPACT":
            return self._use_orks_crushing_impact(stratagem, **kwargs)
        if name_u == "UNSTOPPABLE MOMENTUM":
            return self._use_orks_unstoppable_momentum(stratagem, **kwargs)
        if name_u == "FULL THROTTLE!":
            return self._use_orks_full_throttle(stratagem, **kwargs)
        if name_norm == "krunchin descent":
            return self._use_orks_krunchin_descent(stratagem, **kwargs)
        if name_u == "DRAG IT DOWN":
            return self._use_orks_drag_it_down(stratagem, **kwargs)
        if name_u == "BASH AND GRAB":
            return self._use_orks_bash_and_grab(stratagem, **kwargs)
        if name_u == "DECK FRAGGERS":
            return self._use_orks_deck_fraggers(stratagem, **kwargs)
        if name_u == "ROLLING LOOT-HEAP":
            return self._use_orks_rolling_loot_heap(stratagem, **kwargs)
        if name_u == "BLITZA FIRE":
            return self._use_orks_blitza_fire(stratagem, **kwargs)
        if name_u == "DAKKASTORM":
            return self._use_orks_dakkastorm(stratagem, **kwargs)
        if name_u == "CALL DAT DAKKA?" or name_norm == "call dat dakka":
            return self._use_orks_call_dat_dakka(stratagem, **kwargs)
        if name_norm == "squig flingin":
            return self._use_orks_squig_flingin(stratagem, **kwargs)
        if name_u == "LONG, UNCONTROLLED BURSTS":
            return self._use_orks_long_uncontrolled_bursts(stratagem, **kwargs)
        if name_u == "SUPERFUELLED BOILER":
            return self._use_orks_superfuelled_boiler(stratagem, **kwargs)
        if name_norm == "boardin rush":
            return self._use_orks_boardin_rush(stratagem, **kwargs)
        if name_u == "ORKS IS STILL ORKS":
            return self._use_orks_is_still_orks(stratagem, **kwargs)
        if name_u == "SPESHUL SHELLS":
            return self._use_orks_speshul_shells(stratagem, **kwargs)
        if name_norm == "mobile dakkastorm":
            return self._use_orks_mobile_dakkastorm(stratagem, **kwargs)
        if name_norm == "dat one s even bigga":
            return self._use_orks_dat_ones_even_bigga(stratagem, **kwargs)
        if name_u == "DAT'S OURS":
            return self._use_orks_dats_ours(stratagem, **kwargs)
        if name_u == "TAKTIKAL RETREAT":
            return self._use_orks_taktikal_retreat(stratagem, **kwargs)
        if name_u == "HUGE SHOW-OFFS":
            return self._use_orks_huge_show_offs(stratagem, **kwargs)
        if name_u == "COME ON LADZ!":
            return self._use_orks_come_on_ladz(stratagem, **kwargs)
        if name_u == "FIGHT PROPPA":
            return self._use_orks_fight_proppa(stratagem, **kwargs)
        if name_u == "DAKKA! DAKKA! DAKKA!":
            return self._use_orks_dakka_dakka_dakka(stratagem, **kwargs)
        if name_u == "BIGGER SHELLS FOR BIGGER GITZ":
            return self._use_orks_bigger_shells_for_bigger_gitz(stratagem, **kwargs)
        if name_norm == "klankin klaws":
            return self._use_orks_klankin_klaws(stratagem, **kwargs)
        if name_norm == "stalkin taktiks":
            return self._use_orks_stalkin_taktiks(stratagem, **kwargs)
        if name_u == "SPEEDIEST FREEKS":
            return self._use_orks_speediest_freeks(stratagem, **kwargs)
        if name_u == "EXTRA GUBBINZ":
            return self._use_orks_extra_gubbinz(stratagem, **kwargs)
        if name_u == "DUST TRAILS":
            return self._use_orks_dust_trails(stratagem, **kwargs)
        if name_u == "DED KILLY CONSTRUCTION":
            return self._use_orks_ded_killy_construction(stratagem, **kwargs)
        if name_u == "ON DA MOVE":
            return self._use_orks_on_da_move(stratagem, **kwargs)
        if name_u == "SPESHUL AMMO":
            return self._use_orks_speshul_ammo(stratagem, **kwargs)
        if name_u == "ARMOURED DUELLISTS":
            return self._use_orks_armoured_duellists(stratagem, **kwargs)
        if name_u == "IMPERVIOUS":
            return self._use_orks_impervious(stratagem, **kwargs)
        if name_u == "MEKANISED BRUTALITY":
            return self._use_orks_mekanised_brutality(stratagem, **kwargs)
        if name_u == "MOUNT UP, LADZ":
            return self._use_orks_mount_up_ladz(stratagem, **kwargs)
        if name_u == "RUN 'EM DOWN":
            return self._use_orks_run_em_down(stratagem, **kwargs)
        if name_norm == "where d ya fink you re going":
            return self._use_orks_where_dya_fink_youre_going(stratagem, **kwargs)
        if name_u == "KRUMP AND RUN":
            return self._use_orks_krump_and_run(stratagem, **kwargs)
        if name_u == "ON TO DA NEXT":
            return self._use_orks_on_to_da_next(stratagem, **kwargs)
        if name_u == "CONNIVING RUNTS":
            return self._use_orks_conniving_runts(stratagem, **kwargs)
        if name_norm == "more gitz over ere":
            return self._use_orks_more_gitz_over_ere(stratagem, **kwargs)
        return None

    def _orks_resolve_charge_end_mortal_context(
        self,
        stratagem_name: str,
        **kwargs,
    ) -> tuple[Any, list[Any], Any, list[Any], str, str, bool]:
        source_unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("source_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
        enemy_candidates = list(kwargs.get("enemy_candidates") or [])
        action = str(kwargs.get("action") or kwargs.get("trigger") or "").strip()
        phase_name = str(kwargs.get("phase_name") or "").strip()
        from_pending = False

        if source_unit is None and len(candidates) == 1:
            source_unit = candidates[0]
        if enemy_unit is None and len(enemy_candidates) == 1:
            enemy_unit = enemy_candidates[0]

        normalized_name = self._orks_normalize_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != normalized_name:
                continue
            from_pending = True
            if source_unit is None:
                source_unit = reaction.get("target_unit") or reaction.get("unit") or reaction.get("source_unit")
            if not candidates:
                candidates = list(reaction.get("candidates") or [])
            if enemy_unit is None:
                enemy_unit = reaction.get("enemy_unit") or reaction.get("target_enemy_unit")
            if not enemy_candidates:
                enemy_candidates = list(reaction.get("enemy_candidates") or [])
            if not action:
                action = str(reaction.get("action") or "").strip()
            if not phase_name:
                phase_name = str(reaction.get("phase_name") or "").strip()
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if enemy_unit is None and len(enemy_candidates) == 1:
                enemy_unit = enemy_candidates[0]
            break
        return source_unit, candidates, enemy_unit, enemy_candidates, action, phase_name, from_pending

    def _use_orks_charge_end_mortal_wound_stratagem(
        self,
        stratagem: Any,
        *,
        stratagem_name: str,
        detachment_check,
        source_matcher,
        source_error: str,
        count_mode: str,
        success_on: int,
        success_on_if_waaagh: int | None = None,
        extra_dice_if_prey: int = 0,
        **kwargs,
    ) -> bool:
        if not bool(detachment_check()):
            return False
        source_unit, candidates, enemy_unit, enemy_candidates, action, phase_name, from_pending = (
            self._orks_resolve_charge_end_mortal_context(stratagem_name, **kwargs)
        )
        if source_unit is None:
            logger.error("ERROR: %s: no target unit provided", stratagem_name)
            return False

        phase_label = self._orks_phase_label(phase_name or self._orks_current_phase_label())
        if phase_label != "charge phase":
            logger.error("ERROR: %s: wrong phase", stratagem_name)
            return False
        if not self._orks_is_players_turn():
            logger.error("ERROR: %s: not your Charge phase", stratagem_name)
            return False
        action_key = self._orks_normalize_move_action(action)
        if not from_pending and not action_key:
            logger.error("ERROR: %s: missing movement trigger context", stratagem_name)
            return False
        if action_key and action_key != "charge":
            logger.error("ERROR: %s: invalid trigger action", stratagem_name)
            return False

        source_root = self._orks_root(source_unit)
        if source_root is None:
            return False
        if not self._orks_owned_by_player(source_root, self.player):
            logger.error("ERROR: %s: target unit is not yours", stratagem_name)
            return False
        if not self._orks_on_battlefield(source_root, require_targetable=True):
            logger.error("ERROR: %s: target must be on battlefield and targetable", stratagem_name)
            return False
        if not self._is_orks_unit(source_root):
            logger.error("ERROR: %s: target must be an ORKS unit", stratagem_name)
            return False
        if not bool(source_matcher(source_root)):
            logger.error("ERROR: %s: %s", stratagem_name, source_error)
            return False
        charged_this_round = bool(getattr(getattr(source_root, "round_state", None), "charged_this_round", False))
        if action_key != "charge" and not charged_this_round:
            logger.error("ERROR: %s: target must have ended a Charge move this phase", stratagem_name)
            return False

        expected_sources = list(candidates or [])
        if not expected_sources:
            expected_sources = self._orks_charge_end_mortal_wound_source_candidates(target_matcher=source_matcher)
        if expected_sources and not self._orks_unit_in_candidates(source_root, expected_sources):
            logger.error("ERROR: %s: selected unit is not currently eligible", stratagem_name)
            return False

        enemy_roots = [self._orks_root(unit) for unit in list(enemy_candidates or [])]
        enemy_roots = [unit for unit in enemy_roots if unit is not None]
        if enemy_unit is None and len(enemy_roots) == 1:
            enemy_unit = enemy_roots[0]
        enemy_root = self._orks_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            enemy_roots = self._orks_charge_end_mortal_wound_enemy_candidates(source_root)
            if len(enemy_roots) == 1:
                enemy_root = enemy_roots[0]
            else:
                logger.error("ERROR: %s: no enemy unit within Engagement Range selected", stratagem_name)
                return False
        if self._orks_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: %s: selected enemy unit is not enemy", stratagem_name)
            return False
        if not self._orks_on_battlefield(enemy_root, require_targetable=False):
            logger.error("ERROR: %s: selected enemy unit must be on battlefield", stratagem_name)
            return False
        if enemy_roots and not self._orks_unit_in_candidates(enemy_root, enemy_roots):
            logger.error("ERROR: %s: selected enemy unit is not within Engagement Range", stratagem_name)
            return False
        game_map = getattr(getattr(self, "game", None), "map", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
        if callable(within_engagement) and not bool(within_engagement(source_root, enemy_root)):
            logger.error("ERROR: %s: selected enemy unit is not within Engagement Range", stratagem_name)
            return False

        bonus_dice = 0
        if int(extra_dice_if_prey or 0) > 0 and self._orks_enemy_is_da_big_hunt_prey(enemy_root):
            bonus_dice = int(extra_dice_if_prey or 0)
        roll_count = self._orks_charge_end_mortal_roll_count(
            source_root,
            enemy_root,
            count_mode=str(count_mode or ""),
            bonus_dice=int(bonus_dice),
        )
        if roll_count <= 0:
            logger.error("ERROR: %s: no qualifying models to roll dice for", stratagem_name)
            return False

        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=source_root,
            unit=source_root,
            enemy_unit=enemy_root,
            phase_name="Charge phase",
        ):
            logger.error("ERROR: %s: cannot be used in current state", stratagem_name)
            return False
        if not self._orks_spend_cp(stratagem, target_unit=source_root):
            return False

        result = self._orks_resolve_charge_end_mortal_wounds(
            source_unit=source_root,
            enemy_unit=enemy_root,
            count_mode=str(count_mode or ""),
            success_on=int(success_on or 0),
            success_on_if_waaagh=(
                int(success_on_if_waaagh) if success_on_if_waaagh is not None else None
            ),
            extra_dice_if_prey=int(extra_dice_if_prey or 0),
            max_mortal_wounds=6,
        )
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: %s: %s rolled %d D6 (%d+) and dealt %d mortal wound(s) to %s.",
            stratagem_name,
            getattr(source_root, "name", "Unit"),
            int(result.get("roll_count", 0) or 0),
            int(result.get("success_on", 0) or 0),
            int(result.get("mortal_wounds", 0) or 0),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_orks_crushing_impact(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_charge_end_mortal_wound_stratagem(
            stratagem,
            stratagem_name="CRUSHING IMPACT",
            detachment_check=self._is_bully_boyz_detachment,
            source_matcher=self._orks_is_nobz_or_meganobz_unit,
            source_error="target must be a Nobz or Meganobz unit",
            count_mode="engagement_models",
            success_on=5,
            success_on_if_waaagh=4,
            extra_dice_if_prey=0,
            **kwargs,
        )

    def _use_orks_unstoppable_momentum(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_charge_end_mortal_wound_stratagem(
            stratagem,
            stratagem_name="UNSTOPPABLE MOMENTUM",
            detachment_check=self._is_da_big_hunt_detachment,
            source_matcher=self._orks_is_beast_snagga_mounted_unit,
            source_error="target must be a Beast Snagga Mounted unit",
            count_mode="unit_models",
            success_on=4,
            success_on_if_waaagh=None,
            extra_dice_if_prey=3,
            **kwargs,
        )

    def _use_orks_krunchin_descent(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_charge_end_mortal_wound_stratagem(
            stratagem,
            stratagem_name="KRUNCHIN' DESCENT",
            detachment_check=self._is_taktikal_brigade_detachment,
            source_matcher=self._orks_is_stormboyz_unit,
            source_error="target must be a Stormboyz unit",
            count_mode="engagement_models",
            success_on=4,
            success_on_if_waaagh=None,
            extra_dice_if_prey=0,
            **kwargs,
        )

    def _use_orks_full_throttle(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_kult_of_speed_detachment():
            return False
        source_unit, candidates, _enemy_unit, _enemy_candidates, action, phase_name, from_pending = (
            self._orks_resolve_charge_end_mortal_context("FULL THROTTLE!", **kwargs)
        )
        if source_unit is None:
            logger.error("ERROR: FULL THROTTLE!: no target unit provided")
            return False

        phase_label = self._orks_phase_label(phase_name or self._orks_current_phase_label())
        if phase_label != "charge phase":
            logger.error("ERROR: FULL THROTTLE!: wrong phase")
            return False
        if not self._orks_is_players_turn():
            logger.error("ERROR: FULL THROTTLE!: not your Charge phase")
            return False
        action_key = self._orks_normalize_move_action(action)
        if not from_pending and not action_key:
            logger.error("ERROR: FULL THROTTLE!: missing movement trigger context")
            return False
        if action_key and action_key != "charge":
            logger.error("ERROR: FULL THROTTLE!: invalid trigger action")
            return False

        source_root = self._orks_root(source_unit)
        if source_root is None:
            return False
        if not self._orks_owned_by_player(source_root, self.player):
            logger.error("ERROR: FULL THROTTLE!: target unit is not yours")
            return False
        if not self._orks_on_battlefield(source_root, require_targetable=True):
            logger.error("ERROR: FULL THROTTLE!: target must be on battlefield and targetable")
            return False
        if not self._is_orks_unit(source_root):
            logger.error("ERROR: FULL THROTTLE!: target must be an ORKS unit")
            return False
        if not self._orks_is_speed_freeks_unit(source_root):
            logger.error("ERROR: FULL THROTTLE!: target must be a Speed Freeks unit")
            return False
        charged_this_round = bool(getattr(getattr(source_root, "round_state", None), "charged_this_round", False))
        if action_key != "charge" and not charged_this_round:
            logger.error("ERROR: FULL THROTTLE!: target must have ended a Charge move this phase")
            return False

        expected_sources = list(candidates or [])
        if not expected_sources:
            expected_sources = self._orks_charge_end_mortal_wound_source_candidates(
                target_matcher=self._orks_is_speed_freeks_unit,
            )
        if expected_sources and not self._orks_unit_in_candidates(source_root, expected_sources):
            logger.error("ERROR: FULL THROTTLE!: selected unit is not currently eligible")
            return False

        if not stratagem.can_use(self.player, self.game, target_unit=source_root, unit=source_root, phase_name="Charge phase"):
            logger.error("ERROR: FULL THROTTLE!: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=source_root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "FULL THROTTLE!").strip() or "FULL THROTTLE!"
        self._orks_apply_temp_effects(
            source_root,
            detachment="kult_of_speed",
            effects=[
                {
                    "id": "full_throttle:melee:wound_bonus",
                    "source": source_name,
                    "effect": "wound_bonus",
                    "attack_type": "melee",
                    "value": 1,
                    "expires_mode": "turn",
                }
            ],
        )
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FULL THROTTLE!: %s gains +1 to wound for melee attacks until end of turn.",
            getattr(source_root, "name", "Unit"),
        )
        return True

    def _use_orks_end_of_opponent_fight_phase_reserves_stratagem(
        self,
        stratagem: Any,
        *,
        stratagem_name: str,
        detachment_check,
        target_matcher,
        target_error: str,
        **kwargs,
    ) -> bool:
        if not bool(detachment_check()):
            return False
        if not self._orks_validate_phase(
            expected_phases=("Fight phase",),
            require_your_turn=False,
            error_prefix=stratagem_name,
        ):
            return False
        if self._orks_is_players_turn():
            logger.error("ERROR: %s: not opponent's Fight phase", stratagem_name)
            return False

        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._orks_end_of_opponent_fight_phase_strategic_reserves_candidates(target_matcher=target_matcher)

        target_unit = self._orks_resolve_target_unit(stratagem_name, **kwargs)
        if target_unit is None:
            if len(candidates) == 1:
                target_unit = candidates[0]
            else:
                logger.error("ERROR: %s: no target unit provided", stratagem_name)
                return False
        ok, root = self._orks_validate_offensive_target(
            stratagem_name=stratagem_name,
            target_unit=target_unit,
            candidates=candidates,
        )
        if not ok:
            return False
        if not bool(target_matcher(root)):
            logger.error("ERROR: %s: %s", stratagem_name, target_error)
            return False
        if self._orks_is_unit_engaged(root):
            logger.error("ERROR: %s: target must not be within Engagement Range", stratagem_name)
            return False
        if not candidates or not self._orks_unit_in_candidates(root, candidates):
            logger.error("ERROR: %s: selected unit is not currently eligible", stratagem_name)
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: %s: cannot be used in current state", stratagem_name)
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False
        source_name = str(getattr(stratagem, "name", "") or stratagem_name).strip() or stratagem_name
        if not self._orks_place_unit_into_strategic_reserves(root, reason=source_name):
            logger.error("ERROR: %s: failed to place target into Strategic Reserves", stratagem_name)
            return False

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: %s: %s placed into Strategic Reserves.",
            stratagem_name,
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_instinctive_hunters(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_end_of_opponent_fight_phase_reserves_stratagem(
            stratagem,
            stratagem_name="INSTINCTIVE HUNTERS",
            detachment_check=self._is_da_big_hunt_detachment,
            target_matcher=self._orks_is_beast_snagga_unit,
            target_error="target must be a Beast Snagga unit",
            **kwargs,
        )

    def _use_orks_ded_sneaky(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_end_of_opponent_fight_phase_reserves_stratagem(
            stratagem,
            stratagem_name="DED SNEAKY",
            detachment_check=self._is_taktikal_brigade_detachment,
            target_matcher=self._orks_is_kommandos_or_stormboyz_unit,
            target_error="target must be a Kommandos or Stormboyz unit",
            **kwargs,
        )

    def _use_orks_evasive_manoova(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_end_of_opponent_fight_phase_reserves_stratagem(
            stratagem,
            stratagem_name="EVASIVE MANOOVA",
            detachment_check=self._is_speedwaaagh_detachment,
            target_matcher=self._orks_is_speed_freeks_or_trukk,
            target_error="target must be a Speed Freeks or Trukk unit",
            **kwargs,
        )

    def _use_orks_unit_waaagh_override_stratagem(
        self,
        stratagem: Any,
        *,
        stratagem_name: str,
        require_loot_objective_range: bool,
        **kwargs,
    ) -> bool:
        if not self._orks_validate_phase(
            expected_phases=("Command phase",),
            require_your_turn=True,
            error_prefix=stratagem_name,
        ):
            return False
        target_unit = self._orks_resolve_target_unit(stratagem_name, **kwargs)
        if target_unit is None:
            logger.error("ERROR: %s: no target unit provided", stratagem_name)
            return False
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._orks_unit_waaagh_override_candidates(
                require_loot_objective_range=bool(require_loot_objective_range),
            )
        ok, root = self._orks_validate_offensive_target(
            stratagem_name=stratagem_name,
            target_unit=target_unit,
            candidates=candidates,
            keyword_exclude_any=("GRETCHIN",),
        )
        if not ok:
            return False
        if not candidates or not self._orks_unit_in_candidates(root, candidates):
            logger.error("ERROR: %s: selected unit is not currently eligible", stratagem_name)
            return False
        if require_loot_objective_range and not self._orks_unit_within_active_loot_objective(root):
            logger.error("ERROR: %s: target must be within range of the loot objective", stratagem_name)
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Command phase"):
            logger.error("ERROR: %s: cannot be used in current state", stratagem_name)
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False
        source_name = str(getattr(stratagem, "name", "") or stratagem_name).strip() or stratagem_name
        if not self._orks_apply_unit_waaagh_override(root, source_name=source_name):
            logger.error("ERROR: %s: failed to apply unit Waaagh override", stratagem_name)
            return False
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: %s: %s counts as having Waaagh active until your next Command phase.",
            stratagem_name,
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_get_stuck_in_ladz(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_more_dakka_detachment():
            return False
        return self._use_orks_unit_waaagh_override_stratagem(
            stratagem,
            stratagem_name="GET STUCK IN, LADZ!",
            require_loot_objective_range=False,
            **kwargs,
        )

    def _use_orks_grab_and_bash(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_freebooter_krew_detachment():
            return False
        return self._use_orks_unit_waaagh_override_stratagem(
            stratagem,
            stratagem_name="GRAB AND BASH",
            require_loot_objective_range=True,
            **kwargs,
        )

    def _use_orks_armed_to_dateef(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_bully_boyz_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Shooting phase", "Fight phase"),
            require_your_turn=False,
            error_prefix="ARMED TO DATEEF",
        ):
            return False
        phase_key = self._orks_current_phase_key()
        if phase_key == "SHOOTING_PHASE" and not self._orks_is_players_turn():
            logger.error("ERROR: ARMED TO DATEEF: not your Shooting phase")
            return False
        require_not_selected = "Shooting phase" if phase_key == "SHOOTING_PHASE" else "Fight phase"
        target_unit = self._orks_resolve_target_unit("ARMED TO DATEEF", **kwargs)
        if target_unit is None:
            logger.error("ERROR: ARMED TO DATEEF: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="ARMED TO DATEEF",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("NOBZ", "MEGANOBZ"),
            require_not_selected_phase=require_not_selected,
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=self._orks_current_phase_label().title()):
            logger.error("ERROR: ARMED TO DATEEF: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
        waaagh_mgr = getattr(army, "waaagh", None) if army is not None else None
        unit_is_affected = getattr(waaagh_mgr, "unit_is_affected", None) if waaagh_mgr is not None else None
        waaagh_active = bool(unit_is_affected(root, game=getattr(self, "game", None))) if callable(unit_is_affected) else False
        reroll_mode = "full" if waaagh_active else "ones"
        effects = [
            {
                "id": "armed_to_dateef:hit_reroll",
                "source": str(getattr(stratagem, "name", "") or "ARMED TO DATEEF"),
                "effect": "hit_reroll",
                "attack_type": "any",
                "reroll_mode": reroll_mode,
                "expires_mode": "phase",
            }
        ]
        self._orks_apply_temp_effects(root, detachment="bully_boyz", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ARMED TO DATEEF: %s gains %s hit re-rolls this phase.",
            getattr(root, "name", "Unit"),
            "full" if waaagh_active else "re-roll 1s",
        )
        return True

    def _use_orks_too_arrogant_to_die(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_bully_boyz_detachment():
            return False
        target_unit, attacking_unit, candidates, phase_name, from_pending = self._orks_resolve_target_selected_context(
            "TOO ARROGANT TO DIE",
            **kwargs,
        )
        if target_unit is None:
            logger.error("ERROR: TOO ARROGANT TO DIE: no target unit provided")
            return False
        if not from_pending and not candidates and not list(kwargs.get("target_units") or kwargs.get("targets") or []):
            logger.error("ERROR: TOO ARROGANT TO DIE: missing target selection context")
            return False

        phase_label = self._orks_phase_label(phase_name or self._orks_current_phase_label())
        if phase_label not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: TOO ARROGANT TO DIE: wrong phase")
            return False
        if phase_label == "shooting phase" and self._orks_is_players_turn():
            logger.error("ERROR: TOO ARROGANT TO DIE: not opponent's Shooting phase")
            return False

        attacker_root = self._orks_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: TOO ARROGANT TO DIE: missing attacking unit context")
            return False
        if self._orks_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: TOO ARROGANT TO DIE: attacking unit must be enemy")
            return False
        if not self._orks_on_battlefield(attacker_root, require_targetable=False):
            logger.error("ERROR: TOO ARROGANT TO DIE: attacking unit must be on battlefield")
            return False

        if not candidates:
            candidates = self._orks_too_arrogant_to_die_candidates(
                attacking_unit=attacker_root,
                target_units=kwargs.get("target_units") or kwargs.get("targets"),
            )
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="TOO ARROGANT TO DIE",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("NOBZ", "MEGANOBZ"),
        )
        if not ok:
            return False

        phase_title = "Shooting phase" if phase_label == "shooting phase" else "Fight phase"
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_title):
            logger.error("ERROR: TOO ARROGANT TO DIE: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        threshold = 3 if self._orks_unit_has_active_waaagh(root) else 5
        source_name = str(getattr(stratagem, "name", "") or "TOO ARROGANT TO DIE").strip() or "TOO ARROGANT TO DIE"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["orks_too_arrogant_to_die_active"] = True
        sr["orks_too_arrogant_to_die_threshold"] = int(max(2, min(6, threshold)))
        sr["orks_too_arrogant_to_die_expires_phase"] = "SHOOTING_PHASE" if phase_label == "shooting phase" else "FIGHT_PHASE"
        sr["orks_too_arrogant_to_die_turn_owner"] = self._orks_turn_owner_id()
        sr["orks_too_arrogant_to_die_turn"] = self._orks_current_turn()
        sr["orks_too_arrogant_to_die_source"] = source_name
        root.special_rules = sr

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TOO ARROGANT TO DIE: %s gains shoot/fight-on-death on %d+ until end of phase.",
            getattr(root, "name", "Unit"),
            int(threshold),
        )
        return True

    def _use_orks_always_lookin_fer_a_fight(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_bully_boyz_detachment():
            return False
        target_unit, destroyed_unit, destroyed_by_unit, candidates, phase_name, from_pending = (
            self._orks_resolve_unit_destroyed_context("ALWAYS LOOKIN’ FER A FIGHT", **kwargs)
        )
        if target_unit is None:
            logger.error("ERROR: ALWAYS LOOKIN' FER A FIGHT: no target unit provided")
            return False
        if not from_pending and (destroyed_unit is None or destroyed_by_unit is None):
            logger.error("ERROR: ALWAYS LOOKIN' FER A FIGHT: missing destroyed-unit trigger context")
            return False

        phase_label = self._orks_phase_label(phase_name or self._orks_current_phase_label())
        if phase_label != "fight phase":
            logger.error("ERROR: ALWAYS LOOKIN' FER A FIGHT: wrong phase")
            return False

        destroyed_root = self._orks_root(destroyed_unit)
        if destroyed_root is not None and self._orks_owned_by_player(destroyed_root, self.player):
            logger.error("ERROR: ALWAYS LOOKIN' FER A FIGHT: destroyed unit must be enemy")
            return False

        if not candidates:
            candidates = self._orks_always_lookin_fer_a_fight_candidates(destroyed_by_unit=destroyed_by_unit)
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="ALWAYS LOOKIN' FER A FIGHT",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("NOBZ", "MEGANOBZ"),
        )
        if not ok:
            return False

        attacker_root = self._orks_root(destroyed_by_unit)
        if attacker_root is not None and attacker_root is not root:
            if self._orks_sort_key(attacker_root) != self._orks_sort_key(root):
                logger.error("ERROR: ALWAYS LOOKIN' FER A FIGHT: target did not destroy the enemy unit")
                return False

        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: ALWAYS LOOKIN' FER A FIGHT: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        max_distance = 6 if self._orks_unit_has_active_waaagh(root) else 3 + dice_module.get_roll("D3")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current = float(sr.get("stratagem_consolidate_distance_override", 0) or 0)
        sr["stratagem_consolidate_distance_override"] = max(float(max_distance), current)
        sr["stratagem_consolidate_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_consolidate_source"] = str(getattr(stratagem, "name", "") or "ALWAYS LOOKIN’ FER A FIGHT")
        root.special_rules = sr

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ALWAYS LOOKIN' FER A FIGHT: %s can Consolidate up to %d\" this phase.",
            getattr(root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_orks_cut_em_down(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_bully_boyz_detachment():
            return False
        target_unit, moving_unit, candidates, action, phase_name, from_pending = self._orks_resolve_reactive_reposition_context(
            "CUT’EM DOWN",
            **kwargs,
        )
        if target_unit is None:
            logger.error("ERROR: CUT'EM DOWN: no target unit provided")
            return False

        phase_label = self._orks_phase_label(phase_name or self._orks_current_phase_label())
        if phase_label != "movement phase":
            logger.error("ERROR: CUT'EM DOWN: wrong phase")
            return False
        if self._orks_is_players_turn():
            logger.error("ERROR: CUT'EM DOWN: not opponent's Movement phase")
            return False
        action_key = self._orks_normalize_move_action(action)
        if not from_pending and not action_key:
            logger.error("ERROR: CUT'EM DOWN: missing movement trigger context")
            return False
        if action_key and action_key != "fall_back":
            logger.error("ERROR: CUT'EM DOWN: invalid trigger action")
            return False

        enemy_root = self._orks_root(moving_unit)
        if enemy_root is None:
            logger.error("ERROR: CUT'EM DOWN: missing enemy unit context")
            return False
        if self._orks_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: CUT'EM DOWN: enemy context is invalid")
            return False
        if not self._orks_on_battlefield(enemy_root, require_targetable=False):
            logger.error("ERROR: CUT'EM DOWN: enemy unit must be on battlefield")
            return False

        if not candidates:
            candidates = self._orks_cut_em_down_candidates(enemy_unit=enemy_root)
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="CUT'EM DOWN",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("NOBZ", "MEGANOBZ"),
        )
        if not ok:
            return False

        game_map = getattr(getattr(self, "game", None), "map", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
        if not callable(within_engagement) or not bool(within_engagement(root, enemy_root)):
            logger.error("ERROR: CUT'EM DOWN: target must be in Engagement Range of the falling-back unit")
            return False

        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: CUT'EM DOWN: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "CUT’EM DOWN").strip() or "CUT’EM DOWN"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["enemy_fallback_desperate_escape"] = True
        sr["enemy_fallback_desperate_escape_exclude_monster_vehicle"] = False
        sr["enemy_fallback_desperate_escape_penalty"] = 1 if self._orks_unit_has_active_waaagh(root) else 0
        sr["enemy_fallback_desperate_escape_target_enemy_id"] = get_entity_id(enemy_root)
        sr["enemy_fallback_desperate_escape_expires_phase"] = "MOVEMENT_PHASE"
        sr["enemy_fallback_desperate_escape_turn_owner"] = self._orks_turn_owner_id()
        sr["enemy_fallback_desperate_escape_turn"] = self._orks_current_turn()
        sr["enemy_fallback_desperate_escape_source"] = source_name
        root.special_rules = sr

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CUT'EM DOWN: %s will force Desperate Escape tests on %s.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_orks_drag_it_down(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_da_big_hunt_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Fight phase",),
            require_your_turn=False,
            error_prefix="DRAG IT DOWN",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("DRAG IT DOWN", **kwargs)
        if target_unit is None:
            logger.error("ERROR: DRAG IT DOWN: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="DRAG IT DOWN",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("BEAST SNAGGA",),
            require_not_selected_phase="Fight phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: DRAG IT DOWN: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "DRAG IT DOWN")
        effects = [
            {
                "id": "drag_it_down:melee_sustained_hits_1",
                "source": source_name,
                "effect": "keyword",
                "attack_type": "melee",
                "keyword": "SUSTAINED HITS 1",
                "expires_mode": "phase",
            },
            {
                "id": "drag_it_down:prey_crit_hit_5",
                "source": source_name,
                "effect": "crit_hit_threshold",
                "attack_type": "melee",
                "value": 5,
                "target_is_prey": True,
                "expires_mode": "phase",
            },
        ]
        self._orks_apply_temp_effects(root, detachment="da_big_hunt", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: DRAG IT DOWN: %s gains melee buffs this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_bash_and_grab(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_freebooter_krew_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Fight phase",),
            require_your_turn=False,
            error_prefix="BASH AND GRAB",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("BASH AND GRAB", **kwargs)
        if target_unit is None:
            logger.error("ERROR: BASH AND GRAB: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="BASH AND GRAB",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Fight phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: BASH AND GRAB: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        effects = [
            {
                "id": "bash_and_grab:wound_reroll_full_loot_objective",
                "source": str(getattr(stratagem, "name", "") or "BASH AND GRAB"),
                "effect": "wound_reroll",
                "attack_type": "melee",
                "reroll_mode": "full",
                "target_within_loot_objective": True,
                "expires_mode": "phase",
            }
        ]
        self._orks_apply_temp_effects(root, detachment="freebooter_krew", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: BASH AND GRAB: %s gains conditional wound re-rolls this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_deck_fraggers(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_freebooter_krew_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Shooting phase",),
            require_your_turn=True,
            error_prefix="DECK FRAGGERS",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("DECK FRAGGERS", **kwargs)
        if target_unit is None:
            logger.error("ERROR: DECK FRAGGERS: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="DECK FRAGGERS",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Shooting phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: DECK FRAGGERS: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        effects = [
            {
                "id": "deck_fraggers:blast_vs_infantry",
                "source": str(getattr(stratagem, "name", "") or "DECK FRAGGERS"),
                "effect": "keyword",
                "attack_type": "ranged",
                "keyword": "BLAST",
                "target_keywords_any": ["INFANTRY"],
                "expires_mode": "phase",
            }
        ]
        self._orks_apply_temp_effects(root, detachment="freebooter_krew", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: DECK FRAGGERS: %s gains BLAST vs INFANTRY this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_rolling_loot_heap(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_freebooter_krew_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Shooting phase",),
            require_your_turn=True,
            error_prefix="ROLLING LOOT-HEAP",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("ROLLING LOOT-HEAP", **kwargs)
        if target_unit is None:
            logger.error("ERROR: ROLLING LOOT-HEAP: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="ROLLING LOOT-HEAP",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Shooting phase",
        )
        if not ok:
            return False
        is_flash_gitz = self._orks_unit_contains_keyword(root, "FLASH GITZ") or self._orks_unit_name_contains(root, "flash gitz")
        if not is_flash_gitz:
            logger.error("ERROR: ROLLING LOOT-HEAP: target must be FLASH GITZ")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: ROLLING LOOT-HEAP: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        effects = [
            {
                "id": "rolling_loot_heap:anti_vehicle_4",
                "source": str(getattr(stratagem, "name", "") or "ROLLING LOOT-HEAP"),
                "effect": "keyword",
                "attack_type": "ranged",
                "keyword": "ANTI-VEHICLE 4+",
                "expires_mode": "phase",
            }
        ]
        self._orks_apply_temp_effects(root, detachment="freebooter_krew", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: ROLLING LOOT-HEAP: %s gains Anti-Vehicle 4+ this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_blitza_fire(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_kult_of_speed_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Shooting phase",),
            require_your_turn=True,
            error_prefix="BLITZA FIRE",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("BLITZA FIRE", **kwargs)
        if target_unit is None:
            logger.error("ERROR: BLITZA FIRE: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="BLITZA FIRE",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("SPEED FREEKS",),
            require_not_selected_phase="Shooting phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: BLITZA FIRE: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "BLITZA FIRE")
        effects = [
            {
                "id": "blitza_fire:lethal_hits",
                "source": source_name,
                "effect": "keyword",
                "attack_type": "ranged",
                "keyword": "LETHAL HITS",
                "expires_mode": "phase",
            },
            {
                "id": "blitza_fire:crit_hit_5_within_9",
                "source": source_name,
                "effect": "crit_hit_threshold",
                "attack_type": "ranged",
                "value": 5,
                "target_within_distance": 9.0,
                "expires_mode": "phase",
            },
        ]
        self._orks_apply_temp_effects(root, detachment="kult_of_speed", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: BLITZA FIRE: %s gains ranged buffs this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_dakkastorm(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_kult_of_speed_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Shooting phase",),
            require_your_turn=True,
            error_prefix="DAKKASTORM",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("DAKKASTORM", **kwargs)
        if target_unit is None:
            logger.error("ERROR: DAKKASTORM: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="DAKKASTORM",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("SPEED FREEKS",),
            require_not_selected_phase="Shooting phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: DAKKASTORM: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "DAKKASTORM")
        effects = [
            {
                "id": "dakkastorm:sustained_hits_1",
                "source": source_name,
                "effect": "keyword",
                "attack_type": "ranged",
                "keyword": "SUSTAINED HITS 1",
                "expires_mode": "phase",
            },
            {
                "id": "dakkastorm:sustained_hits_2_within_9",
                "source": source_name,
                "effect": "keyword",
                "attack_type": "ranged",
                "keyword": "SUSTAINED HITS 2",
                "target_within_distance": 9.0,
                "expires_mode": "phase",
            },
        ]
        self._orks_apply_temp_effects(root, detachment="kult_of_speed", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: DAKKASTORM: %s gains ranged Sustained Hits this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_long_uncontrolled_bursts(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_more_dakka_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Shooting phase",),
            require_your_turn=True,
            error_prefix="LONG, UNCONTROLLED BURSTS",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("LONG, UNCONTROLLED BURSTS", **kwargs)
        if target_unit is None:
            logger.error("ERROR: LONG, UNCONTROLLED BURSTS: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="LONG, UNCONTROLLED BURSTS",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Shooting phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: LONG, UNCONTROLLED BURSTS: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        effects = [
            {
                "id": "long_uncontrolled_bursts:ignores_cover",
                "source": str(getattr(stratagem, "name", "") or "LONG, UNCONTROLLED BURSTS"),
                "effect": "keyword",
                "attack_type": "ranged",
                "keyword": "IGNORES COVER",
                "expires_mode": "phase",
            }
        ]
        self._orks_apply_temp_effects(root, detachment="more_dakka", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: LONG, UNCONTROLLED BURSTS: %s gains Ignores Cover this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_call_dat_dakka(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_after_enemy_shoot_reactive_shooting_stratagem(
            stratagem,
            stratagem_name="CALL DAT DAKKA?",
            detachment_check=self._is_more_dakka_detachment,
            **kwargs,
        )

    def _use_orks_superfuelled_boiler(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_dread_mob_detachment():
            return False
        target_unit, candidates, action, phase_name, _from_pending = self._orks_resolve_move_trigger_context(
            "SUPERFUELLED BOILER",
            **kwargs,
        )
        if target_unit is None:
            logger.error("ERROR: SUPERFUELLED BOILER: no target unit provided")
            return False

        phase_label = self._orks_phase_label(phase_name or self._orks_current_phase_label())
        if phase_label != "movement phase":
            logger.error("ERROR: SUPERFUELLED BOILER: wrong phase")
            return False
        if not self._orks_is_players_turn():
            logger.error("ERROR: SUPERFUELLED BOILER: not your Movement phase")
            return False
        if self._orks_normalize_move_action(action) != "advance":
            logger.error("ERROR: SUPERFUELLED BOILER: invalid trigger action")
            return False

        ok, root = self._orks_validate_offensive_target(
            stratagem_name="SUPERFUELLED BOILER",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("WALKER",),
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: SUPERFUELLED BOILER: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "SUPERFUELLED BOILER")
        effects = [
            {
                "id": "superfuelled_boiler:reroll_advance",
                "source": source_name,
                "effect": "reroll_advance_roll",
                "expires_mode": "phase",
                "expires_phase": "",
            },
            {
                "id": "superfuelled_boiler:assault_ranged",
                "source": source_name,
                "effect": "assault_ranged",
                "attack_type": "ranged",
                "expires_mode": "phase",
                "expires_phase": "",
            },
        ]
        self._orks_apply_temp_effects(root, detachment="dread_mob", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SUPERFUELLED BOILER: %s gains Advance re-rolls and Assault on ranged weapons until end of turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_boardin_rush(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_freebooter_krew_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Movement phase",),
            require_your_turn=True,
            error_prefix="BOARDIN' RUSH",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("BOARDIN' RUSH", **kwargs)
        if target_unit is None:
            logger.error("ERROR: BOARDIN' RUSH: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="BOARDIN' RUSH",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Movement phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: BOARDIN' RUSH: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "BOARDIN' RUSH")
        effects = [
            {
                "id": "boardin_rush:advance_no_roll",
                "source": source_name,
                "effect": "advance_no_roll",
                "distance": 6,
                "expires_mode": "phase",
            }
        ]
        self._orks_apply_temp_effects(root, detachment="freebooter_krew", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BOARDIN' RUSH: %s uses fixed 6\" Advance distance until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_is_still_orks(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_more_dakka_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Fight phase",),
            require_your_turn=False,
            error_prefix="ORKS IS STILL ORKS",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("ORKS IS STILL ORKS", **kwargs)
        if target_unit is None:
            logger.error("ERROR: ORKS IS STILL ORKS: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="ORKS IS STILL ORKS",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Fight phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: ORKS IS STILL ORKS: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "ORKS IS STILL ORKS")
        effects = [
            {
                "id": "orks_is_still_orks:wound_reroll_ones",
                "source": source_name,
                "effect": "wound_reroll",
                "attack_type": "melee",
                "reroll_mode": "ones",
                "expires_mode": "phase",
            },
            {
                "id": "orks_is_still_orks:wound_reroll_full_objective",
                "source": source_name,
                "effect": "wound_reroll",
                "attack_type": "melee",
                "reroll_mode": "full",
                "target_within_objective": True,
                "expires_mode": "phase",
            },
        ]
        self._orks_apply_temp_effects(root, detachment="more_dakka", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: ORKS IS STILL ORKS: %s gains melee wound re-roll buffs this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_speshul_shells(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_more_dakka_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Shooting phase",),
            require_your_turn=True,
            error_prefix="SPESHUL SHELLS",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("SPESHUL SHELLS", **kwargs)
        if target_unit is None:
            logger.error("ERROR: SPESHUL SHELLS: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="SPESHUL SHELLS",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Shooting phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: SPESHUL SHELLS: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        effects = [
            {
                "id": "speshul_shells:closest_eligible_ap",
                "source": str(getattr(stratagem, "name", "") or "SPESHUL SHELLS"),
                "effect": "closest_eligible_ap_bonus",
                "attack_type": "ranged",
                "value": 1,
                "target_closest_eligible": True,
                "closest_max_distance": 18.0,
                "expires_mode": "phase",
            }
        ]
        self._orks_apply_temp_effects(root, detachment="more_dakka", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: SPESHUL SHELLS: %s gains AP bonus vs closest eligible targets within 18\" this phase.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_dat_ones_even_bigga(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_da_big_hunt_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Charge phase",),
            require_your_turn=True,
            error_prefix="DAT ONE'S EVEN BIGGA!",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("DAT ONE'S EVEN BIGGA!", **kwargs)
        if target_unit is None:
            logger.error("ERROR: DAT ONE'S EVEN BIGGA!: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="DAT ONE'S EVEN BIGGA!",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("BEAST SNAGGA",),
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Charge phase"):
            logger.error("ERROR: DAT ONE'S EVEN BIGGA!: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "DAT ONE'S EVEN BIGGA!")
        effects = [
            {
                "id": "dat_ones_even_bigga:charge_after_advance",
                "source": source_name,
                "effect": "charge_after_advance",
                "expires_mode": "phase",
            },
            {
                "id": "dat_ones_even_bigga:charge_after_fall_back",
                "source": source_name,
                "effect": "charge_after_fall_back",
                "expires_mode": "phase",
            },
            {
                "id": "dat_ones_even_bigga:charge_reroll_prey",
                "source": source_name,
                "effect": "charge_reroll",
                "target_is_prey": True,
                "expires_mode": "phase",
            },
        ]
        self._orks_apply_temp_effects(root, detachment="da_big_hunt", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DAT ONE'S EVEN BIGGA!: %s gains charge eligibility buffs and prey-gated charge re-rolls this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_dats_ours(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_taktikal_brigade_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Command phase",),
            require_your_turn=False,
            error_prefix="DAT'S OURS",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("DAT'S OURS", **kwargs)
        if target_unit is None:
            logger.error("ERROR: DAT'S OURS: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="DAT'S OURS",
            target_unit=target_unit,
            candidates=candidates,
        )
        if not ok:
            return False
        if not self._orks_is_unit_engaged(root):
            logger.error("ERROR: DAT'S OURS: target must be within Engagement Range of an enemy unit")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Command phase"):
            logger.error("ERROR: DAT'S OURS: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_key = "stratagem:orks_next_command_phase:dats_ours"
        root.add_characteristic_modifier(
            "objective_control",
            Modifier(ModifierOp.ADD, 1, source=f"{source_key}:oc"),
        )
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: DAT'S OURS: %s gains +1 Objective Control until the start of the next Command phase.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_move_end_enemy_battleshock_stratagem(
        self,
        stratagem: Any,
        *,
        stratagem_name: str,
        detachment_check,
        source_matcher,
        source_error: str,
        allowed_actions: tuple[str, ...],
        enemy_range: float,
        test_modifier: int,
        **kwargs,
    ) -> bool:
        if not bool(detachment_check()):
            return False
        source_unit, candidates, enemy_unit, enemy_candidates, action, phase_name, from_pending = (
            self._orks_resolve_move_end_enemy_battleshock_context(stratagem_name, **kwargs)
        )
        if source_unit is None:
            logger.error("ERROR: %s: no target unit provided", stratagem_name)
            return False

        phase_label = self._orks_phase_label(phase_name or self._orks_current_phase_label())
        if phase_label != "movement phase":
            logger.error("ERROR: %s: wrong phase", stratagem_name)
            return False
        if not self._orks_is_players_turn():
            logger.error("ERROR: %s: not your Movement phase", stratagem_name)
            return False
        action_key = self._orks_normalize_move_action(action)
        if not from_pending and not action_key:
            logger.error("ERROR: %s: missing movement trigger context", stratagem_name)
            return False
        if action_key not in set(allowed_actions or ()):
            logger.error("ERROR: %s: invalid trigger action", stratagem_name)
            return False

        ok, source_root = self._orks_validate_offensive_target(
            stratagem_name=stratagem_name,
            target_unit=source_unit,
            candidates=candidates,
        )
        if not ok:
            return False
        if not bool(source_matcher(source_root)):
            logger.error("ERROR: %s: %s", stratagem_name, source_error)
            return False
        round_state = getattr(source_root, "round_state", None)
        if action_key == "move" and not bool(getattr(round_state, "moved_this_round", False)):
            logger.error("ERROR: %s: target must have ended a Normal move this phase", stratagem_name)
            return False
        if action_key == "advance" and not bool(getattr(round_state, "advanced_this_round", False)):
            logger.error("ERROR: %s: target must have ended an Advance move this phase", stratagem_name)
            return False
        if action_key == "fall_back" and not bool(getattr(round_state, "fell_back_this_round", False)):
            logger.error("ERROR: %s: target must have ended a Fall Back move this phase", stratagem_name)
            return False

        expected_sources = list(candidates or [source_root])
        if expected_sources and not self._orks_unit_in_candidates(source_root, expected_sources):
            logger.error("ERROR: %s: selected unit is not currently eligible", stratagem_name)
            return False

        enemy_roots = [self._orks_root(unit) for unit in list(enemy_candidates or [])]
        enemy_roots = [unit for unit in enemy_roots if unit is not None]
        if enemy_unit is None and len(enemy_roots) == 1:
            enemy_unit = enemy_roots[0]
        enemy_root = self._orks_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            enemy_roots = self._orks_enemy_battleshock_candidates_within_distance(
                source_unit=source_root,
                max_distance=float(enemy_range),
            )
            if len(enemy_roots) == 1:
                enemy_root = enemy_roots[0]
            else:
                logger.error("ERROR: %s: no enemy unit within %.1f\" selected", stratagem_name, float(enemy_range))
                return False
        if self._orks_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: %s: selected enemy unit is not enemy", stratagem_name)
            return False
        if not self._orks_on_battlefield(enemy_root, require_targetable=False):
            logger.error("ERROR: %s: selected enemy unit must be on battlefield", stratagem_name)
            return False
        if enemy_roots and not self._orks_unit_in_candidates(enemy_root, enemy_roots):
            logger.error("ERROR: %s: selected enemy unit is not within %.1f\"", stratagem_name, float(enemy_range))
            return False
        distance = self._orks_distance_between_units(source_root, enemy_root)
        if distance is None or float(distance) > float(enemy_range) + 1e-6:
            logger.error("ERROR: %s: selected enemy unit is not within %.1f\"", stratagem_name, float(enemy_range))
            return False

        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=source_root,
            unit=source_root,
            enemy_unit=enemy_root,
            phase_name="Movement phase",
        ):
            logger.error("ERROR: %s: cannot be used in current state", stratagem_name)
            return False
        if not self._orks_spend_cp(stratagem, target_unit=source_root):
            return False

        force_test = getattr(enemy_root, "force_battle_shock_test", None)
        if not callable(force_test):
            logger.error("ERROR: %s: target unit cannot take a forced Battle-shock test", stratagem_name)
            return False
        force_test(
            int(self._orks_current_turn() or 1),
            modifier=int(test_modifier),
            source=str(getattr(stratagem, "name", "") or stratagem_name),
        )

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: %s: %s forces %s to take a Battle-shock test at %d.",
            stratagem_name,
            getattr(source_root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy"),
            int(test_modifier),
        )
        return True

    def _use_orks_squig_flingin(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_move_end_enemy_battleshock_stratagem(
            stratagem,
            stratagem_name="SQUIG FLINGIN'",
            detachment_check=self._is_kult_of_speed_detachment,
            source_matcher=self._orks_is_speed_freeks_or_trukk,
            source_error="target must be a Speed Freeks or Trukk unit",
            allowed_actions=("move", "advance", "fall_back"),
            enemy_range=9.0,
            test_modifier=-1,
            **kwargs,
        )

    def _use_orks_taktikal_retreat(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_taktikal_brigade_detachment():
            return False
        target_unit, candidates, action, phase_name, _from_pending = self._orks_resolve_move_trigger_context(
            "TAKTIKAL RETREAT",
            **kwargs,
        )
        if target_unit is None:
            logger.error("ERROR: TAKTIKAL RETREAT: no target unit provided")
            return False

        phase_label = self._orks_phase_label(phase_name or self._orks_current_phase_label())
        if phase_label != "movement phase":
            logger.error("ERROR: TAKTIKAL RETREAT: wrong phase")
            return False
        if not self._orks_is_players_turn():
            logger.error("ERROR: TAKTIKAL RETREAT: not your Movement phase")
            return False
        if self._orks_normalize_move_action(action) != "fall_back":
            logger.error("ERROR: TAKTIKAL RETREAT: invalid trigger action")
            return False

        ok, root = self._orks_validate_offensive_target(
            stratagem_name="TAKTIKAL RETREAT",
            target_unit=target_unit,
            candidates=candidates,
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: TAKTIKAL RETREAT: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "TAKTIKAL RETREAT")
        effects = [
            {
                "id": "taktikal_retreat:shoot_after_fall_back",
                "source": source_name,
                "effect": "shoot_after_fall_back",
                "expires_mode": "phase",
                "expires_phase": "",
            },
            {
                "id": "taktikal_retreat:charge_after_fall_back",
                "source": source_name,
                "effect": "charge_after_fall_back",
                "expires_mode": "phase",
                "expires_phase": "",
            },
        ]
        self._orks_apply_temp_effects(root, detachment="taktikal_brigade", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TAKTIKAL RETREAT: %s can shoot and charge after Falling Back until end of turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_huge_show_offs(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_more_dakka_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Command phase",),
            require_your_turn=True,
            error_prefix="HUGE SHOW-OFFS",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("HUGE SHOW-OFFS", **kwargs)
        if target_unit is None:
            logger.error("ERROR: HUGE SHOW-OFFS: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="HUGE SHOW-OFFS",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("WALKER",),
        )
        if not ok:
            return False
        if self._orks_unit_contains_keyword(root, "KILLA KANS") or self._orks_unit_name_contains(root, "killa kans"):
            logger.error("ERROR: HUGE SHOW-OFFS: Killa Kans are excluded")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Command phase"):
            logger.error("ERROR: HUGE SHOW-OFFS: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_key = "stratagem:orks_next_command_phase:huge_show_offs"
        root.add_characteristic_modifier("movement", Modifier(ModifierOp.ADD, 1, source=f"{source_key}:movement"))
        root.add_characteristic_modifier("leadership", Modifier(ModifierOp.ADD, 1, source=f"{source_key}:leadership"))
        root.add_characteristic_modifier("objective_control", Modifier(ModifierOp.ADD, 1, source=f"{source_key}:oc"))
        effects = [
            {
                "id": "huge_show_offs:hit_bonus",
                "source": str(getattr(stratagem, "name", "") or "HUGE SHOW-OFFS"),
                "effect": "hit_bonus",
                "attack_type": "any",
                "value": 1,
                "expires_mode": "next_command_phase",
                "expires_scope": "owner_command_phase",
            }
        ]
        self._orks_apply_temp_effects(root, detachment="more_dakka", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: HUGE SHOW-OFFS: %s gains +1 Move, +1 Leadership, +1 OC and +1 to hit until next Command phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_fight_proppa(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_taktikal_brigade_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Fight phase",),
            require_your_turn=False,
            error_prefix="FIGHT PROPPA",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("FIGHT PROPPA", **kwargs)
        if target_unit is None:
            logger.error("ERROR: FIGHT PROPPA: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="FIGHT PROPPA",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("INFANTRY", "MOUNTED"),
            require_not_selected_phase="Fight phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: FIGHT PROPPA: cannot be used in current state")
            return False
        choice_spec = self._orks_temp_combat_choice_spec(
            stratagem_name=str(getattr(stratagem, "name", "") or "FIGHT PROPPA"),
            source_name=str(getattr(stratagem, "name", "") or "FIGHT PROPPA"),
        )
        request = self._orks_build_temp_combat_choice_request(
            stratagem_name=str(getattr(stratagem, "name", "") or "FIGHT PROPPA"),
            unit=root,
            choice_spec=choice_spec,
        )
        if request is None:
            logger.error("ERROR: FIGHT PROPPA: failed to queue mode choice")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False
        if not self._orks_submit_decision_request(request):
            logger.error("ERROR: FIGHT PROPPA: failed to submit mode choice decision")
            return False
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: FIGHT PROPPA: queued mode choice for %s.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_dakka_dakka_dakka(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_dread_mob_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Shooting phase",),
            require_your_turn=True,
            error_prefix="DAKKA! DAKKA! DAKKA!",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("DAKKA! DAKKA! DAKKA!", **kwargs)
        if target_unit is None:
            logger.error("ERROR: DAKKA! DAKKA! DAKKA!: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="DAKKA! DAKKA! DAKKA!",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Shooting phase",
        )
        if not ok:
            return False
        if not self._orks_unit_is_walker_or_grots_vehicle(root):
            logger.error("ERROR: DAKKA! DAKKA! DAKKA!: target must be an Orks Walker or Grots Vehicle unit")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: DAKKA! DAKKA! DAKKA!: cannot be used in current state")
            return False
        choice_spec = self._orks_temp_combat_choice_spec(
            stratagem_name=str(getattr(stratagem, "name", "") or "DAKKA! DAKKA! DAKKA!"),
            source_name=str(getattr(stratagem, "name", "") or "DAKKA! DAKKA! DAKKA!"),
        )
        request = self._orks_build_temp_combat_choice_request(
            stratagem_name=str(getattr(stratagem, "name", "") or "DAKKA! DAKKA! DAKKA!"),
            unit=root,
            choice_spec=choice_spec,
        )
        if request is None:
            logger.error("ERROR: DAKKA! DAKKA! DAKKA!: failed to queue mode choice")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False
        if not self._orks_submit_decision_request(request):
            logger.error("ERROR: DAKKA! DAKKA! DAKKA!: failed to submit mode choice decision")
            return False
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: DAKKA! DAKKA! DAKKA!: queued mode choice for %s.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_bigger_shells_for_bigger_gitz(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_dread_mob_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Shooting phase",),
            require_your_turn=True,
            error_prefix="BIGGER SHELLS FOR BIGGER GITZ",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("BIGGER SHELLS FOR BIGGER GITZ", **kwargs)
        if target_unit is None:
            logger.error("ERROR: BIGGER SHELLS FOR BIGGER GITZ: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="BIGGER SHELLS FOR BIGGER GITZ",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Shooting phase",
        )
        if not ok:
            return False
        if not self._orks_unit_is_mek_or_walker_or_grots_vehicle(root):
            logger.error(
                "ERROR: BIGGER SHELLS FOR BIGGER GITZ: target must be a Mek, Orks Walker, or Grots Vehicle unit"
            )
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: BIGGER SHELLS FOR BIGGER GITZ: cannot be used in current state")
            return False
        choice_spec = self._orks_temp_combat_choice_spec(
            stratagem_name=str(getattr(stratagem, "name", "") or "BIGGER SHELLS FOR BIGGER GITZ"),
            source_name=str(getattr(stratagem, "name", "") or "BIGGER SHELLS FOR BIGGER GITZ"),
        )
        request = self._orks_build_temp_combat_choice_request(
            stratagem_name=str(getattr(stratagem, "name", "") or "BIGGER SHELLS FOR BIGGER GITZ"),
            unit=root,
            choice_spec=choice_spec,
        )
        if request is None:
            logger.error("ERROR: BIGGER SHELLS FOR BIGGER GITZ: failed to queue mode choice")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False
        if not self._orks_submit_decision_request(request):
            logger.error("ERROR: BIGGER SHELLS FOR BIGGER GITZ: failed to submit mode choice decision")
            return False
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BIGGER SHELLS FOR BIGGER GITZ: queued mode choice for %s.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_klankin_klaws(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_dread_mob_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Fight phase",),
            require_your_turn=False,
            error_prefix="KLANKIN' KLAWS",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("KLANKIN' KLAWS", **kwargs)
        if target_unit is None:
            logger.error("ERROR: KLANKIN' KLAWS: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="KLANKIN' KLAWS",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("WALKER",),
            require_not_selected_phase="Fight phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: KLANKIN' KLAWS: cannot be used in current state")
            return False
        choice_spec = self._orks_temp_combat_choice_spec(
            stratagem_name=str(getattr(stratagem, "name", "") or "KLANKIN' KLAWS"),
            source_name=str(getattr(stratagem, "name", "") or "KLANKIN' KLAWS"),
        )
        request = self._orks_build_temp_combat_choice_request(
            stratagem_name=str(getattr(stratagem, "name", "") or "KLANKIN' KLAWS"),
            unit=root,
            choice_spec=choice_spec,
        )
        if request is None:
            logger.error("ERROR: KLANKIN' KLAWS: failed to queue mode choice")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False
        if not self._orks_submit_decision_request(request):
            logger.error("ERROR: KLANKIN' KLAWS: failed to submit mode choice decision")
            return False
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: KLANKIN' KLAWS: queued mode choice for %s.", getattr(root, "name", "Unit"))
        return True

    def _use_orks_stalkin_taktiks(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_target_selected_defensive_reaction(
            stratagem,
            stratagem_name="STALKIN' TAKTIKS",
            expected_phases=("Shooting phase",),
            detachment_check=self._is_da_big_hunt_detachment,
            target_matcher=self._orks_is_beast_snagga_infantry_or_mounted,
            target_error="target must be a Beast Snagga Infantry or Beast Snagga Mounted unit",
            effect_builder=self._orks_stalkin_taktiks_defensive_effects,
            **kwargs,
        )

    def _use_orks_speediest_freeks(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_target_selected_defensive_reaction(
            stratagem,
            stratagem_name="SPEEDIEST FREEKS",
            expected_phases=("Shooting phase", "Fight phase"),
            detachment_check=self._is_kult_of_speed_detachment,
            target_matcher=self._orks_is_speed_freeks_or_trukk,
            target_error="target must be a Speed Freeks or Trukk unit",
            effect_builder=self._orks_speediest_freeks_defensive_effects,
            **kwargs,
        )

    def _use_orks_extra_gubbinz(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_target_selected_defensive_reaction(
            stratagem,
            stratagem_name="EXTRA GUBBINZ",
            expected_phases=("Shooting phase",),
            detachment_check=self._is_dread_mob_detachment,
            target_matcher=self._orks_is_walker_or_grots_vehicle_not_titanic,
            target_error="target must be an Orks Walker or Grots Vehicle unit (excluding TITANIC)",
            effect_builder=lambda _unit, *, source_name: self._orks_extra_gubbinz_defensive_effects(source_name=source_name),
            **kwargs,
        )

    def _use_orks_dust_trails(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_target_selected_defensive_reaction(
            stratagem,
            stratagem_name="DUST TRAILS",
            expected_phases=("Shooting phase",),
            detachment_check=self._is_speedwaaagh_detachment,
            target_matcher=self._is_orks_unit,
            target_error="target must be an ORKS unit",
            effect_builder=lambda _unit, *, source_name: self._orks_dust_trails_defensive_effects(source_name=source_name),
            **kwargs,
        )

    def _use_orks_ded_killy_construction(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_speedwaaagh_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Fight phase",),
            require_your_turn=True,
            error_prefix="DED KILLY CONSTRUCTION",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("DED KILLY CONSTRUCTION", **kwargs)
        if target_unit is None:
            logger.error("ERROR: DED KILLY CONSTRUCTION: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._orks_ded_killy_construction_candidates()
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="DED KILLY CONSTRUCTION",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("SPEED FREEKS", "TRUKK"),
            require_not_selected_phase="Fight phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: DED KILLY CONSTRUCTION: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "DED KILLY CONSTRUCTION").strip() or "DED KILLY CONSTRUCTION"
        effects = [
            {
                "id": "ded_killy_construction:lance",
                "source": source_name,
                "effect": "keyword",
                "attack_type": "melee",
                "keyword": "LANCE",
                "expires_mode": "phase",
            }
        ]
        if bool(getattr(getattr(root, "round_state", None), "charged_this_round", False)):
            effects.append(
                {
                    "id": "ded_killy_construction:charge_damage_bonus",
                    "source": source_name,
                    "effect": "damage_bonus",
                    "attack_type": "melee",
                    "value": 1,
                    "expires_mode": "phase",
                }
            )
        self._orks_apply_temp_effects(root, detachment="speedwaaagh", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DED KILLY CONSTRUCTION: %s gains melee [LANCE]%s until end of phase.",
            getattr(root, "name", "Unit"),
            " and +1 Damage" if len(effects) > 1 else "",
        )
        return True

    def _use_orks_on_da_move(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_speedwaaagh_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Movement phase",),
            require_your_turn=True,
            error_prefix="ON DA MOVE",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("ON DA MOVE", **kwargs)
        if target_unit is None:
            logger.error("ERROR: ON DA MOVE: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._orks_on_da_move_candidates()
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="ON DA MOVE",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Movement phase",
        )
        if not ok:
            return False
        if self._orks_unit_used_speedwaaagh_turbo_this_turn(root):
            logger.error("ERROR: ON DA MOVE: target used Turbo Boostas this turn")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: ON DA MOVE: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "ON DA MOVE").strip() or "ON DA MOVE"
        self._orks_apply_temp_effects(
            root,
            detachment="speedwaaagh",
            effects=[
                {
                    "id": "on_da_move:assault_ranged",
                    "source": source_name,
                    "effect": "assault_ranged",
                    "attack_type": "ranged",
                    "expires_mode": "turn",
                },
                {
                    "id": "on_da_move:shoot_after_fall_back",
                    "source": source_name,
                    "effect": "shoot_after_fall_back",
                    "attack_type": "any",
                    "expires_mode": "turn",
                },
                {
                    "id": "on_da_move:charge_after_advance",
                    "source": source_name,
                    "effect": "charge_after_advance",
                    "attack_type": "any",
                    "expires_mode": "turn",
                },
                {
                    "id": "on_da_move:charge_after_fall_back",
                    "source": source_name,
                    "effect": "charge_after_fall_back",
                    "attack_type": "any",
                    "expires_mode": "turn",
                },
            ],
        )
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ON DA MOVE: %s can shoot and charge after Advancing or Falling Back until end of turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_speshul_ammo(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_speedwaaagh_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Shooting phase",),
            require_your_turn=True,
            error_prefix="SPESHUL AMMO",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("SPESHUL AMMO", **kwargs)
        if target_unit is None:
            logger.error("ERROR: SPESHUL AMMO: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._orks_speshul_ammo_candidates()
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="SPESHUL AMMO",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Shooting phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: SPESHUL AMMO: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "SPESHUL AMMO").strip() or "SPESHUL AMMO"
        self._orks_apply_temp_effects(
            root,
            detachment="speedwaaagh",
            effects=[
                {
                    "id": "speshul_ammo:anti_monster_4",
                    "source": source_name,
                    "effect": "keyword",
                    "attack_type": "ranged",
                    "keyword": "ANTI-MONSTER 4+",
                    "weapon_exclude_keywords_any": ["TORRENT"],
                    "expires_mode": "phase",
                },
                {
                    "id": "speshul_ammo:anti_vehicle_4",
                    "source": source_name,
                    "effect": "keyword",
                    "attack_type": "ranged",
                    "keyword": "ANTI-VEHICLE 4+",
                    "weapon_exclude_keywords_any": ["TORRENT"],
                    "expires_mode": "phase",
                },
            ],
        )
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SPESHUL AMMO: %s gains [ANTI-MONSTER 4+] and [ANTI-VEHICLE 4+] on non-Torrent ranged weapons until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_armoured_duellists(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_blitz_brigade_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Shooting phase",),
            require_your_turn=True,
            error_prefix="ARMOURED DUELLISTS",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("ARMOURED DUELLISTS", **kwargs)
        if target_unit is None:
            logger.error("ERROR: ARMOURED DUELLISTS: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._orks_armoured_duellists_candidates()
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="ARMOURED DUELLISTS",
            target_unit=target_unit,
            candidates=candidates,
            keyword_any=("VEHICLE",),
            require_not_selected_phase="Shooting phase",
        )
        if not ok:
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: ARMOURED DUELLISTS: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "ARMOURED DUELLISTS").strip() or "ARMOURED DUELLISTS"
        effects = [
            {
                "id": "armoured_duellists:hit_bonus",
                "source": source_name,
                "effect": "hit_bonus",
                "attack_type": "ranged",
                "value": 1,
                "target_keywords_any": ["MONSTER", "VEHICLE"],
                "expires_mode": "phase",
            },
            {
                "id": "armoured_duellists:wound_bonus",
                "source": source_name,
                "effect": "wound_bonus",
                "attack_type": "ranged",
                "value": 1,
                "target_keywords_any": ["MONSTER", "VEHICLE"],
                "expires_mode": "phase",
            },
        ]
        self._orks_apply_temp_effects(root, detachment="blitz_brigade", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ARMOURED DUELLISTS: %s gains +1 to hit and wound vs MONSTER/VEHICLE targets this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_impervious(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_target_selected_defensive_reaction(
            stratagem,
            stratagem_name="IMPERVIOUS",
            expected_phases=("Shooting phase",),
            detachment_check=self._is_blitz_brigade_detachment,
            target_matcher=self._orks_is_battlewagon_kill_rig_or_hunta_rig,
            target_error="target must be a Battlewagon, Kill Rig or Hunta Rig unit",
            effect_builder=lambda _unit, *, source_name: self._orks_impervious_defensive_effects(
                source_name=source_name
            ),
            **kwargs,
        )

    def _orks_resolve_mount_up_ladz_context(
        self,
        stratagem_name: str,
        **kwargs,
    ) -> tuple[Any, Any, list[Any], dict[str, list[Any]] | None, str, bool]:
        unit_arg = kwargs.get("unit") or kwargs.get("target_unit")
        transport = (
            kwargs.get("transport_unit")
            or kwargs.get("transport")
            or kwargs.get("target_transport")
            or kwargs.get("target_transport_unit")
        )
        passenger = (
            kwargs.get("passenger_unit")
            or kwargs.get("embark_unit")
            or kwargs.get("infantry_unit")
        )
        if unit_arg is not None:
            unit_root = self._orks_root(unit_arg)
            if transport is None and self._orks_is_transport_unit(unit_root):
                transport = unit_root
            elif passenger is None:
                passenger = unit_root

        candidates = list(kwargs.get("candidates") or kwargs.get("transport_candidates") or [])
        embark_candidates = list(
            kwargs.get("embark_candidates")
            or kwargs.get("passenger_candidates")
            or kwargs.get("infantry_candidates")
            or []
        )
        passenger_map = (
            kwargs.get("embark_candidates_by_transport")
            or kwargs.get("passenger_candidates_by_transport")
        )
        phase_name = str(kwargs.get("phase_name") or "").strip()
        from_pending = False

        normalized_name = self._orks_normalize_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if self._orks_normalize_name(str(reaction.get("stratagem", "") or "")) != normalized_name:
                continue
            from_pending = True
            if transport is None:
                transport = (
                    reaction.get("transport_unit")
                    or reaction.get("transport")
                    or reaction.get("target_transport")
                    or reaction.get("unit")
                    or reaction.get("target_unit")
                )
            if passenger is None:
                passenger = (
                    reaction.get("passenger_unit")
                    or reaction.get("embark_unit")
                    or reaction.get("infantry_unit")
                )
            if not candidates:
                candidates = list(reaction.get("transport_candidates") or reaction.get("candidates") or [])
            if not embark_candidates:
                embark_candidates = list(
                    reaction.get("embark_candidates")
                    or reaction.get("passenger_candidates")
                    or reaction.get("infantry_candidates")
                    or []
                )
            if passenger_map is None:
                passenger_map = (
                    reaction.get("embark_candidates_by_transport")
                    or reaction.get("passenger_candidates_by_transport")
                )
            if not phase_name:
                phase_name = str(reaction.get("phase_name") or "").strip()
            break

        if transport is None and len(candidates) == 1:
            transport = candidates[0]
        transport_root = self._orks_root(transport)
        if transport_root is not None and not embark_candidates and hasattr(passenger_map, "get"):
            embark_candidates = list(passenger_map.get(self._orks_sort_key(transport_root)) or [])
        if passenger is None and len(embark_candidates) == 1:
            passenger = embark_candidates[0]
        return (transport, passenger, embark_candidates, passenger_map, phase_name, from_pending)

    def _use_orks_mount_up_ladz(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_blitz_brigade_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: MOUNT UP, LADZ: wrong phase")
            return False

        transport, passenger, embark_candidates, passenger_map, _phase_name, _from_pending = (
            self._orks_resolve_mount_up_ladz_context("MOUNT UP, LADZ", **kwargs)
        )
        transport_root = self._orks_root(transport)
        if transport_root is None:
            logger.error("ERROR: MOUNT UP, LADZ: no target transport provided")
            return False
        if not self._orks_owned_by_player(transport_root, self.player):
            logger.error("ERROR: MOUNT UP, LADZ: target transport is not yours")
            return False
        if not self._orks_on_battlefield(transport_root, require_targetable=True):
            logger.error("ERROR: MOUNT UP, LADZ: target transport must be on the battlefield and targetable")
            return False
        if not self._orks_is_transport_unit(transport_root):
            logger.error("ERROR: MOUNT UP, LADZ: target must be a friendly TRANSPORT")
            return False

        eligible_transports, eligible_map = self._orks_mount_up_ladz_candidates()
        if not self._orks_unit_in_candidates(transport_root, eligible_transports):
            logger.error("ERROR: MOUNT UP, LADZ: selected transport has no eligible ORKS INFANTRY passengers")
            return False
        if not embark_candidates:
            candidate_map = passenger_map if passenger_map is not None else eligible_map
            embark_candidates = list(candidate_map.get(self._orks_sort_key(transport_root)) or []) if hasattr(candidate_map, "get") else []
        if passenger is None and len(embark_candidates) == 1:
            passenger = embark_candidates[0]

        if passenger is not None:
            passenger_root = self._orks_root(passenger)
            if passenger_root is None:
                return False
            if not self._orks_unit_in_candidates(passenger_root, embark_candidates):
                logger.error("ERROR: MOUNT UP, LADZ: selected ORKS INFANTRY unit is not currently eligible")
                return False
            if not self._orks_mount_up_transport_can_embark(transport=transport_root, passenger=passenger_root):
                logger.error("ERROR: MOUNT UP, LADZ: selected ORKS INFANTRY unit cannot embark in that transport")
                return False
            embark_candidates = [passenger_root]
        if not embark_candidates:
            logger.error("ERROR: MOUNT UP, LADZ: no eligible ORKS INFANTRY unit can embark")
            return False

        queue_fn = getattr(self.game, "_queue_end_of_fight_embark_decision", None) if self.game is not None else None
        if not callable(queue_fn):
            logger.error("ERROR: MOUNT UP, LADZ: end-of-fight embark decision queue unavailable")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=transport_root, unit=transport_root, phase_name="Fight phase"):
            logger.error("ERROR: MOUNT UP, LADZ: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=transport_root):
            return False
        request = queue_fn(
            player=self.player,
            transport=transport_root,
            candidates=embark_candidates,
            spec={
                "source": str(getattr(stratagem, "name", "") or "MOUNT UP, LADZ"),
                "range": 6,
                "keyword": "ORKS",
                "allow_existing_passengers": True,
            },
        )
        if request is None:
            logger.error("ERROR: MOUNT UP, LADZ: no embark decision was queued")
            return False

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: MOUNT UP, LADZ: queued embark decision for a nearby eligible ORKS INFANTRY unit.")
        return True

    def _use_orks_mekanised_brutality(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_blitz_brigade_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Movement phase",),
            require_your_turn=True,
            error_prefix="MEKANISED BRUTALITY",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("MEKANISED BRUTALITY", **kwargs)
        if target_unit is None:
            logger.error("ERROR: MEKANISED BRUTALITY: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._orks_blitz_brigade_wagon_or_rig_not_moved_candidates()
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="MEKANISED BRUTALITY",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Movement phase",
        )
        if not ok:
            return False
        if not self._orks_is_battlewagon_kill_rig_or_hunta_rig(root):
            logger.error("ERROR: MEKANISED BRUTALITY: target must be a Battlewagon, Kill Rig or Hunta Rig unit")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: MEKANISED BRUTALITY: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr = dict(sr)
        source_name = str(getattr(stratagem, "name", "") or "MEKANISED BRUTALITY").strip() or "MEKANISED BRUTALITY"
        sr["blitz_brigade_mekanised_brutality_active"] = True
        sr["blitz_brigade_mekanised_brutality_source"] = source_name
        sr["blitz_brigade_mekanised_brutality_turn"] = int(self._orks_current_turn() or 0)
        sr["blitz_brigade_mekanised_brutality_turn_owner"] = self._orks_turn_owner_id()
        root.special_rules = sr

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MEKANISED BRUTALITY: units disembarking from %s after its Normal move can charge this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_run_em_down(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_blitz_brigade_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Movement phase",),
            require_your_turn=True,
            error_prefix="RUN 'EM DOWN",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("RUN 'EM DOWN", **kwargs)
        if target_unit is None:
            logger.error("ERROR: RUN 'EM DOWN: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._orks_blitz_brigade_wagon_or_rig_not_moved_candidates()
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="RUN 'EM DOWN",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Movement phase",
        )
        if not ok:
            return False
        if not self._orks_is_battlewagon_kill_rig_or_hunta_rig(root):
            logger.error("ERROR: RUN 'EM DOWN: target must be a Battlewagon, Kill Rig or Hunta Rig unit")
            return False

        raw_selected = (
            kwargs.get("selected_units")
            or kwargs.get("other_units")
            or kwargs.get("affected_units")
            or kwargs.get("target_units")
            or kwargs.get("units")
        )
        selected_units = self._orks_resolve_unit_list(raw_selected)
        for extra_key in ("secondary_unit", "support_unit", "other_unit"):
            extra_root = self._orks_root(kwargs.get(extra_key))
            if extra_root is not None:
                selected_units.extend(self._orks_resolve_unit_list([extra_root]))
        source_id = self._orks_sort_key(root)
        selected_units = [
            unit
            for unit in self._orks_resolve_unit_list(selected_units)
            if unit is not root and (not source_id or self._orks_sort_key(unit) != source_id)
        ]
        if len(selected_units) > 2:
            logger.error("ERROR: RUN 'EM DOWN: select no more than two other friendly ORKS VEHICLE or MONSTER units")
            return False

        eligible_others = self._orks_run_em_down_other_candidates(root)
        for selected in selected_units:
            if not self._orks_unit_in_candidates(selected, eligible_others):
                logger.error("ERROR: RUN 'EM DOWN: selected other units must be friendly ORKS VEHICLE or MONSTER units within 6\"")
                return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: RUN 'EM DOWN: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "RUN 'EM DOWN").strip() or "RUN 'EM DOWN"
        source_key = re.sub(r"[^a-z0-9]+", "_", self._orks_sort_key(root).lower()).strip("_") or "source"
        affected_units = [root] + selected_units
        for index, affected in enumerate(affected_units):
            self._orks_apply_temp_effects(
                affected,
                detachment="blitz_brigade",
                effects=[
                    {
                        "id": f"run_em_down:{source_key}:{index}:charge_after_advance",
                        "source": source_name,
                        "effect": "charge_after_advance",
                        "attack_type": "any",
                        "expires_mode": "turn",
                    }
                ],
            )

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RUN 'EM DOWN: %d Blitz Brigade unit(s) can declare a charge after Advancing this turn.",
            len(affected_units),
        )
        return True

    def _use_orks_where_dya_fink_youre_going(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_reactive_reposition_stratagem(
            stratagem,
            stratagem_name="WHERE D'YA FINK YOU'RE GOING?",
            detachment_check=self._is_da_big_hunt_detachment,
            target_matcher=self._orks_is_beast_snagga_infantry_or_mounted,
            target_error="target must be a Beast Snagga Infantry or Beast Snagga Mounted unit",
            allowed_actions=("fall_back",),
            require_start_phase_engaged=True,
            require_not_engaged_now=True,
            max_distance_to_enemy=None,
            reactive_move_kind="where_dya_fink_youre_going",
            **kwargs,
        )

    def _use_orks_krump_and_run(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_reactive_reposition_stratagem(
            stratagem,
            stratagem_name="KRUMP AND RUN",
            detachment_check=self._is_freebooter_krew_detachment,
            target_matcher=self._is_orks_unit,
            target_error="target must be an ORKS unit",
            allowed_actions=("fall_back",),
            require_start_phase_engaged=True,
            require_not_engaged_now=True,
            max_distance_to_enemy=None,
            reactive_move_kind="krump_and_run",
            **kwargs,
        )

    def _use_orks_on_to_da_next(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_reactive_reposition_stratagem(
            stratagem,
            stratagem_name="ON TO DA NEXT",
            detachment_check=self._is_taktikal_brigade_detachment,
            target_matcher=self._is_orks_unit,
            target_error="target must be an ORKS unit",
            allowed_actions=("fall_back",),
            require_start_phase_engaged=True,
            require_not_engaged_now=False,
            max_distance_to_enemy=None,
            reactive_move_kind="on_to_da_next",
            **kwargs,
        )

    def _use_orks_more_gitz_over_ere(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_reactive_reposition_stratagem(
            stratagem,
            stratagem_name="MORE GITZ OVER 'ERE!",
            detachment_check=self._is_kult_of_speed_detachment,
            target_matcher=self._orks_is_speed_freeks_unit,
            target_error="target must be a Speed Freeks unit",
            allowed_actions=("move", "advance", "fall_back"),
            require_start_phase_engaged=False,
            require_not_engaged_now=True,
            max_distance_to_enemy=9.0,
            reactive_move_kind="more_gitz_over_ere",
            **kwargs,
        )

    def _use_orks_conniving_runts(self, stratagem: Any, **kwargs) -> bool:
        return self._use_orks_reactive_reposition_stratagem(
            stratagem,
            stratagem_name="CONNIVING RUNTS",
            detachment_check=self._is_dread_mob_detachment,
            target_matcher=self._orks_is_gretchin_unit,
            target_error="target must be a Gretchin unit",
            allowed_actions=("move", "advance", "fall_back"),
            require_start_phase_engaged=False,
            require_not_engaged_now=True,
            max_distance_to_enemy=9.0,
            reactive_move_kind="conniving_runts",
            pre_move_rider={
                "effect": "single_roll_mortal_wounds",
                "trigger_roll": "D6",
                "success_on": 4,
                "mortal_wounds": "D3+1",
            },
            **kwargs,
        )

    def _use_orks_braggin_rights(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_green_tide_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Command phase",),
            require_your_turn=True,
            error_prefix="BRAGGIN' RIGHTS",
        ):
            return False

        normalized_pair_candidates: list[tuple[Any, Any]] = []
        seen_pair_keys: set[tuple[str, str]] = set()
        for item in list(kwargs.get("pair_candidates") or kwargs.get("candidates") or []):
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            first = self._orks_root(item[0])
            second = self._orks_root(item[1])
            if first is None or second is None:
                continue
            first, second = sorted([first, second], key=self._orks_sort_key)
            pair_key = (self._orks_sort_key(first), self._orks_sort_key(second))
            if pair_key in seen_pair_keys:
                continue
            seen_pair_keys.add(pair_key)
            normalized_pair_candidates.append((first, second))
        if not normalized_pair_candidates:
            normalized_pair_candidates = self._orks_green_tide_braggin_rights_pairs()

        selected_units = self._orks_resolve_unit_list(
            kwargs.get("target_units")
            or kwargs.get("units")
            or kwargs.get("selected_units")
        )
        if not selected_units:
            first = kwargs.get("unit") or kwargs.get("target_unit")
            second = kwargs.get("secondary_unit") or kwargs.get("other_unit") or kwargs.get("unit_b")
            if first is not None and second is not None:
                selected_units = self._orks_resolve_unit_list([first, second])
        if not selected_units:
            if len(normalized_pair_candidates) == 1:
                selected_units = self._orks_resolve_unit_list(
                    [normalized_pair_candidates[0][0], normalized_pair_candidates[0][1]]
                )
            else:
                logger.error("ERROR: BRAGGIN' RIGHTS: must select exactly two BOYZ units")
                return False
        if len(selected_units) != 2:
            logger.error("ERROR: BRAGGIN' RIGHTS: must select exactly two BOYZ units")
            return False
        first_root, second_root = sorted(selected_units, key=self._orks_sort_key)

        boyz_candidates = self._orks_green_tide_boyz_candidates()
        ok, first_root = self._orks_validate_offensive_target(
            stratagem_name="BRAGGIN' RIGHTS",
            target_unit=first_root,
            candidates=boyz_candidates,
        )
        if not ok or not self._orks_unit_is_boyz(first_root):
            logger.error("ERROR: BRAGGIN' RIGHTS: first target must be a BOYZ unit")
            return False
        ok, second_root = self._orks_validate_offensive_target(
            stratagem_name="BRAGGIN' RIGHTS",
            target_unit=second_root,
            candidates=boyz_candidates,
        )
        if not ok or not self._orks_unit_is_boyz(second_root):
            logger.error("ERROR: BRAGGIN' RIGHTS: second target must be a BOYZ unit")
            return False
        if first_root is second_root:
            logger.error("ERROR: BRAGGIN' RIGHTS: selected units must be different")
            return False
        if not self._orks_green_tide_pair_in_candidates(first_root, second_root, normalized_pair_candidates):
            logger.error("ERROR: BRAGGIN' RIGHTS: selected pair is not currently eligible")
            return False
        distance = self._orks_distance_between_units(first_root, second_root)
        if distance is None or float(distance) > 6.0 + 1e-6:
            logger.error("ERROR: BRAGGIN' RIGHTS: selected units must be within 6\" of each other")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=first_root,
            unit=first_root,
            target_units=[first_root, second_root],
            phase_name="Command phase",
        ):
            logger.error("ERROR: BRAGGIN' RIGHTS: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=first_root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "BRAGGIN' RIGHTS").strip() or "BRAGGIN' RIGHTS"
        first_id = self._orks_sort_key(first_root)
        second_id = self._orks_sort_key(second_root)
        pair_key = f"{first_id}:{second_id}"
        base_effect = {
            "source": source_name,
            "effect": "effective_model_count_floor",
            "value": 10,
            "effective_model_count_scopes": ["detachment", "enhancement", "stratagem"],
            "expires_mode": "next_command_phase",
            "expires_scope": "owner_command_phase",
            "while_within_distance": 6.0,
        }
        first_effect = dict(base_effect)
        first_effect["id"] = f"braggin_rights:{pair_key}:first"
        first_effect["while_within_distance_of_unit_id"] = second_id
        second_effect = dict(base_effect)
        second_effect["id"] = f"braggin_rights:{pair_key}:second"
        second_effect["while_within_distance_of_unit_id"] = first_id

        self._orks_apply_temp_effects(first_root, detachment="green_tide", effects=[first_effect])
        self._orks_apply_temp_effects(second_root, detachment="green_tide", effects=[second_effect])

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BRAGGIN' RIGHTS: %s and %s count as 10+ models for detachment/enhancement/stratagem checks while within 6\" until your next Command phase.",
            getattr(first_root, "name", "Unit"),
            getattr(second_root, "name", "Unit"),
        )
        return True

    def _use_orks_bulldozer_brutality(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_green_tide_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Fight phase",),
            require_your_turn=False,
            error_prefix="BULLDOZER BRUTALITY",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("BULLDOZER BRUTALITY", **kwargs)
        if target_unit is None:
            logger.error("ERROR: BULLDOZER BRUTALITY: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._orks_green_tide_bulldozer_brutality_candidates()
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="BULLDOZER BRUTALITY",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Fight phase",
        )
        if not ok:
            return False
        if not self._orks_unit_is_boyz(root):
            logger.error("ERROR: BULLDOZER BRUTALITY: target must be a BOYZ unit")
            return False
        if not self._orks_is_unit_engaged(root):
            logger.error("ERROR: BULLDOZER BRUTALITY: target must be within Engagement Range of an enemy unit")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: BULLDOZER BRUTALITY: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "BULLDOZER BRUTALITY").strip() or "BULLDOZER BRUTALITY"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if not sr.get("fight_within_3"):
            sr["fight_within_3"] = [{"name": source_name}]
            sr["orks_bulldozer_brutality_added_fight_within_3"] = True
        set_active = getattr(root, "set_fight_within_3_active", None)
        if callable(set_active):
            root.special_rules = sr
            set_active(True, source=source_name)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
        else:
            sr["fight_within_3_active"] = True
            sr["fight_within_3_active_source"] = source_name
        sr["orks_bulldozer_brutality_active"] = True
        sr["orks_bulldozer_brutality_expires_phase"] = "FIGHT_PHASE"
        sr["orks_bulldozer_brutality_turn_owner"] = self._orks_turn_owner_id()
        sr["orks_bulldozer_brutality_turn"] = self._orks_current_turn()
        sr["orks_bulldozer_brutality_source"] = source_name
        root.special_rules = sr

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BULLDOZER BRUTALITY: %s can fight with models within 3\" until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_orks_competitive_streak(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_green_tide_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Fight phase",),
            require_your_turn=False,
            error_prefix="COMPETITIVE STREAK",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("COMPETITIVE STREAK", **kwargs)
        if target_unit is None:
            logger.error("ERROR: COMPETITIVE STREAK: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._orks_green_tide_competitive_streak_candidates()
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="COMPETITIVE STREAK",
            target_unit=target_unit,
            candidates=candidates,
            require_not_selected_phase="Fight phase",
        )
        if not ok:
            return False
        if not self._orks_unit_is_boyz(root):
            logger.error("ERROR: COMPETITIVE STREAK: target must be a BOYZ unit")
            return False
        if not candidates or not self._orks_unit_in_candidates(root, candidates):
            logger.error("ERROR: COMPETITIVE STREAK: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: COMPETITIVE STREAK: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        reroll_mode = "full" if self._orks_green_tide_effectively_counts_as_ten(root, scope="stratagem") else "ones"
        root_id = self._orks_sort_key(root)
        effects = [
            {
                "id": f"competitive_streak:{root_id}:wound_reroll",
                "source": str(getattr(stratagem, "name", "") or "COMPETITIVE STREAK"),
                "effect": "wound_reroll",
                "attack_type": "melee",
                "reroll_mode": str(reroll_mode),
                "expires_mode": "phase",
            }
        ]
        self._orks_apply_temp_effects(root, detachment="green_tide", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: COMPETITIVE STREAK: %s gains melee wound re-roll mode '%s' until end of phase.",
            getattr(root, "name", "Unit"),
            reroll_mode,
        )
        return True

    def _use_orks_go_get_em(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_green_tide_detachment():
            return False
        target_unit, attacking_unit, candidates, phase_name, from_pending = self._orks_resolve_target_selected_context(
            "GO GET 'EM!",
            **kwargs,
        )
        if target_unit is None:
            logger.error("ERROR: GO GET 'EM!: no target unit provided")
            return False
        if not from_pending and not candidates and not list(kwargs.get("target_units") or kwargs.get("targets") or []):
            logger.error("ERROR: GO GET 'EM!: missing target selection context")
            return False

        phase_label = self._orks_phase_label(phase_name or self._orks_current_phase_label())
        if phase_label != "shooting phase":
            logger.error("ERROR: GO GET 'EM!: wrong phase")
            return False
        if self._orks_is_players_turn():
            logger.error("ERROR: GO GET 'EM!: not opponent's Shooting phase")
            return False

        attacker_root = self._orks_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: GO GET 'EM!: missing attacking unit context")
            return False
        if self._orks_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: GO GET 'EM!: attacking unit must be enemy")
            return False
        if not self._orks_on_battlefield(attacker_root, require_targetable=False):
            logger.error("ERROR: GO GET 'EM!: attacking unit must be on battlefield")
            return False

        if not candidates:
            candidates = self._orks_target_selected_reaction_candidates(
                list(kwargs.get("target_units") or kwargs.get("targets") or []),
                matcher=self._orks_unit_is_boyz,
            )
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="GO GET 'EM!",
            target_unit=target_unit,
            candidates=candidates,
        )
        if not ok:
            return False
        if not self._orks_unit_is_boyz(root):
            logger.error("ERROR: GO GET 'EM!: target must be a BOYZ unit")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: GO GET 'EM!: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "GO GET 'EM!").strip() or "GO GET 'EM!"
        activate_horde_move = getattr(root, "activate_go_get_em_horde_move", None)
        if callable(activate_horde_move):
            activate_horde_move(
                game=self.game,
                attacker_unit=attacker_root,
                can_reroll_distance=False,
                source=source_name,
            )
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["orks_go_get_em_active"] = True
        sr["orks_go_get_em_expires_phase"] = "SHOOTING_PHASE"
        sr["orks_go_get_em_turn_owner"] = self._orks_turn_owner_id()
        sr["orks_go_get_em_turn"] = self._orks_current_turn()
        sr["orks_go_get_em_source"] = source_name
        root.special_rules = sr

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: GO GET 'EM!: %s will make a post-shooting Horde move after %s finishes shooting; any D6 re-roll is checked after that shooting resolves.",
            getattr(root, "name", "Unit"),
            getattr(attacker_root, "name", "the attacker"),
        )
        return True

    def _use_orks_tide_of_muscle(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_green_tide_detachment():
            return False
        if not self._orks_validate_phase(
            expected_phases=("Charge phase",),
            require_your_turn=True,
            error_prefix="TIDE OF MUSCLE",
        ):
            return False
        target_unit = self._orks_resolve_target_unit("TIDE OF MUSCLE", **kwargs)
        if target_unit is None:
            logger.error("ERROR: TIDE OF MUSCLE: no target unit provided")
            return False
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._orks_green_tide_tide_of_muscle_candidates()
        ok, root = self._orks_validate_offensive_target(
            stratagem_name="TIDE OF MUSCLE",
            target_unit=target_unit,
            candidates=candidates,
        )
        if not ok:
            return False
        if not self._orks_unit_is_boyz(root):
            logger.error("ERROR: TIDE OF MUSCLE: target must be a BOYZ unit")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "attempted_charge_this_round", False)):
            logger.error("ERROR: TIDE OF MUSCLE: target has already declared a charge this phase")
            return False
        if not candidates or not self._orks_unit_in_candidates(root, candidates):
            logger.error("ERROR: TIDE OF MUSCLE: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Charge phase"):
            logger.error("ERROR: TIDE OF MUSCLE: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        root_id = self._orks_sort_key(root)
        effects: list[dict[str, Any]] = [
            {
                "id": f"tide_of_muscle:{root_id}:charge_bonus",
                "source": str(getattr(stratagem, "name", "") or "TIDE OF MUSCLE"),
                "effect": "charge_roll_bonus",
                "value": 1,
                "expires_mode": "phase",
            }
        ]
        if self._orks_green_tide_effectively_counts_as_ten(root, scope="stratagem"):
            effects.append(
                {
                    "id": f"tide_of_muscle:{root_id}:charge_reroll",
                    "source": str(getattr(stratagem, "name", "") or "TIDE OF MUSCLE"),
                    "effect": "charge_reroll",
                    "reroll_mode": "full",
                    "expires_mode": "phase",
                }
            )
        self._orks_apply_temp_effects(root, detachment="green_tide", effects=effects)
        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TIDE OF MUSCLE: %s gains +1 to Charge rolls%s until end of phase.",
            getattr(root, "name", "Unit"),
            " and Charge re-rolls" if len(effects) > 1 else "",
        )
        return True

    def _use_orks_come_on_ladz(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "COME ON LADZ!":
                    continue
                target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if target_unit is None:
            logger.error("ERROR: COME ON LADZ!: no target unit provided")
            return False

        root = self._orks_root(target_unit)
        if root is None:
            return False
        if not self._is_green_tide_detachment():
            return False

        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower().replace("_", " ")
        if phase_name != "command phase":
            logger.error("ERROR: COME ON LADZ!: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if getattr(self, "game", None) is not None else None
        if active_player is not self.player:
            logger.error("ERROR: COME ON LADZ!: not your Command phase")
            return False
        if not self._orks_owned_by_player(root, self.player):
            logger.error("ERROR: COME ON LADZ!: target unit is not yours")
            return False
        if not self._orks_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: COME ON LADZ!: target must be on the battlefield and targetable")
            return False
        if not self._is_orks_unit(root):
            logger.error("ERROR: COME ON LADZ!: target must be an ORKS unit")
            return False
        if not self._orks_unit_is_boyz(root):
            logger.error("ERROR: COME ON LADZ!: target must be a BOYZ unit")
            return False

        eligible = candidates or self._orks_green_tide_come_on_ladz_candidates()
        if not eligible or not self._orks_unit_in_candidates(root, eligible):
            logger.error("ERROR: COME ON LADZ!: selected unit is not currently eligible")
            return False

        returnable_models = self._orks_returnable_destroyed_non_character_models(root)
        if not returnable_models:
            logger.error("ERROR: COME ON LADZ!: no destroyed non-CHARACTER models can be returned")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Command phase"):
            logger.error("ERROR: COME ON LADZ!: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        roll = max(0, dice_module.get_roll("D3")) + 2
        max_return = min(int(roll), len(returnable_models))

        explicit_selection = any(
            key in kwargs for key in ("return_models", "chosen_models", "models", "return_model_ids")
        )
        selected_models: list[Any]
        if explicit_selection:
            selected_models = []
            selected_ids: set[str] = set()
            requested_models = kwargs.get("return_models") or kwargs.get("chosen_models") or kwargs.get("models") or []
            requested_ids = kwargs.get("return_model_ids") or []
            request_tokens = [str(get_entity_id(model) or "") for model in list(requested_models or []) if model is not None]
            request_tokens.extend([str(item or "") for item in list(requested_ids or []) if str(item or "")])
            for token in request_tokens:
                if not token or token in selected_ids:
                    continue
                matched = None
                for model in returnable_models:
                    if str(get_entity_id(model) or "") == token:
                        matched = model
                        break
                if matched is None:
                    logger.error("ERROR: COME ON LADZ!: one or more selected models are not returnable")
                    return False
                selected_models.append(matched)
                selected_ids.add(token)
            if len(selected_models) > max_return:
                selected_models = selected_models[:max_return]
        else:
            selected_models = list(returnable_models[:max_return])

        returned = 0
        return_models = getattr(root, "return_destroyed_bodyguard_models", None)
        if callable(return_models):
            returned = int(
                return_models(
                    max_return,
                    game_map=getattr(getattr(self, "game", None), "map", None),
                    chosen_models=selected_models,
                    wounds=None,
                    placement_source=str(stratagem.name or "COME ON LADZ!"),
                )
                or 0
            )
        else:
            return_full = getattr(self, "_return_destroyed_models_full", None)
            if callable(return_full):
                returned = int(
                    return_full(
                        root,
                        amount=max_return,
                        game_map=getattr(getattr(self, "game", None), "map", None),
                        skip_character=True,
                    )
                    or 0
                )

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: COME ON LADZ!: returned %d destroyed model(s) to %s.",
            int(returned),
            getattr(root, "name", "Unit"),
        )
        return True
