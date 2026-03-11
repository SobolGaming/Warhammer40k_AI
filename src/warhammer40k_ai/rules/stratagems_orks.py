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

    def _use_orks_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "ARMED TO DATEEF":
            return self._use_orks_armed_to_dateef(stratagem, **kwargs)
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
        if name_u == "ORKS IS STILL ORKS":
            return self._use_orks_is_still_orks(stratagem, **kwargs)
        if name_u == "SPESHUL SHELLS":
            return self._use_orks_speshul_shells(stratagem, **kwargs)
        if name_u == "DAT'S OURS":
            return self._use_orks_dats_ours(stratagem, **kwargs)
        if name_u == "HUGE SHOW-OFFS":
            return self._use_orks_huge_show_offs(stratagem, **kwargs)
        if name_u == "COME ON LADZ!":
            return self._use_orks_come_on_ladz(stratagem, **kwargs)
        return None

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
