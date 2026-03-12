from __future__ import annotations

import logging
import re
from typing import Any, Optional

from ..utility import dice as dice_module
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

    def _orks_is_beast_snagga_unit(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        return self._orks_unit_contains_keyword(root, "BEAST SNAGGA")

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
        if self._orks_is_players_turn():
            return

        if phase_label == "shooting phase":
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
            stratagem_names=("SPEEDIEST FREEKS",),
            detachment_check=self._is_kult_of_speed_detachment,
            target_matcher=self._orks_is_speed_freeks_or_trukk,
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

    def _queue_orks_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if str(getattr(phase, "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
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

    def _queue_orks_move_started_reactions(self, *, unit: Any, action: str) -> None:
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
        self._queue_orks_taktikal_retreat_move_end_reaction(unit=unit, action=action)

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

        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind=str(reactive_move_kind or "reactive_reposition"),
            movement_type="reactive",
            source=str(getattr(stratagem, "name", "") or stratagem_name),
            moving_unit=moving_root,
            range_value=int(max_distance_to_enemy) if max_distance_to_enemy is not None else None,
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

    def _use_orks_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        name_norm = self._orks_normalize_name(getattr(stratagem, "name", "") or "")
        if name_u == "ARMED TO DATEEF":
            return self._use_orks_armed_to_dateef(stratagem, **kwargs)
        if name_u == "GET STUCK IN, LADZ!" or name_norm == "get stuck in ladz":
            return self._use_orks_get_stuck_in_ladz(stratagem, **kwargs)
        if name_u == "GRAB AND BASH" or name_norm == "grab and bash":
            return self._use_orks_grab_and_bash(stratagem, **kwargs)
        if name_u == "INSTINCTIVE HUNTERS":
            return self._use_orks_instinctive_hunters(stratagem, **kwargs)
        if name_u == "DED SNEAKY":
            return self._use_orks_ded_sneaky(stratagem, **kwargs)
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
        if name_norm == "where d ya fink you re going":
            return self._use_orks_where_dya_fink_youre_going(stratagem, **kwargs)
        if name_u == "KRUMP AND RUN":
            return self._use_orks_krump_and_run(stratagem, **kwargs)
        if name_u == "ON TO DA NEXT":
            return self._use_orks_on_to_da_next(stratagem, **kwargs)
        if name_norm == "more gitz over ere":
            return self._use_orks_more_gitz_over_ere(stratagem, **kwargs)
        return None

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

        roll = max(0, int(dice_module.get_roll("D3") or 0)) + 2
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
