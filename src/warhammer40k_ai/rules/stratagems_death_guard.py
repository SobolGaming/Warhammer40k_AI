from __future__ import annotations

import logging
import re
from typing import Any

from ..utility.aura_utils import (
    distance_between_models_bases_3d,
    horizontal_distance_between_bases_2d,
    vertical_distance_between_bases,
)
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class DeathGuardStratagemMixin:
    @staticmethod
    def _dg_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _dg_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "")

    @staticmethod
    def _dg_phase_key(value: Any) -> str:
        text = str(value or "").strip().upper().replace(" ", "_")
        return re.sub(r"\s+", "_", text)

    def _dg_current_phase_key(self) -> str:
        phase = getattr(self.game, "phase", None) if getattr(self, "game", None) is not None else None
        phase_name = getattr(phase, "name", phase)
        if phase_name:
            return self._dg_phase_key(phase_name)
        return self._dg_phase_key(getattr(self, "_current_phase_name", "") or "")

    def _dg_current_turn(self) -> int:
        return int(getattr(getattr(self, "game", None), "turn", 0) or 0)

    def _dg_turn_owner_id(self) -> str:
        game = getattr(self, "game", None)
        if game is None:
            return str(getattr(self.player, "id", "") or "")
        get_current_player = getattr(game, "get_current_player", None)
        current_player = get_current_player() if callable(get_current_player) else None
        current_owner = str(getattr(current_player, "id", "") or "")
        return current_owner or str(getattr(self.player, "id", "") or "")

    def _dg_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "death_guard_detachments", None)

    def _is_champions_of_contagion_detachment(self) -> bool:
        mgr = self._dg_detachment_mgr()
        checker = getattr(mgr, "is_champions_of_contagion", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _dg_has_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        token = str(keyword or "").strip()
        if not token:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(token)):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and bool(has_kw(token)):
            return True
        return False

    def _dg_owned_by_player(self, unit: Any, player: Any) -> bool:
        root = self._dg_root(unit)
        if root is None or player is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        return getattr(army, "player", None) is player

    def _dg_is_death_guard_unit(self, unit: Any) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        if not self._dg_owned_by_player(root, self.player):
            return False
        return self._dg_has_keyword(root, "DEATH GUARD")

    def _dg_is_death_guard_character_unit(self, unit: Any) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        return self._dg_is_death_guard_unit(root) and self._dg_has_keyword(root, "CHARACTER")

    def _dg_is_attached_unit(self, unit: Any) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        members_fn = getattr(root, "get_attached_unit_members", None)
        members = list(members_fn() or []) if callable(members_fn) else [root]
        return len(list(members or [])) > 1

    def _dg_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        if require_targetable:
            active_fn = getattr(root, "is_active_for_rules", None)
            if callable(active_fn) and not bool(active_fn()):
                return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if str(getattr(root, "reserve_status", "deployed")) != "deployed":
            return False
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        return True

    def _dg_is_unit_engaged(self, unit: Any) -> bool:
        root = self._dg_root(unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if root is None or game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(within_engagement):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._dg_root(enemy)
            if enemy_root is None:
                continue
            if bool(within_engagement(root, enemy_root)):
                return True
        return False

    def _dg_unit_not_selected_for_phase_action(self, unit: Any, *, phase_key: str) -> bool:
        root = self._dg_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        phase_u = self._dg_phase_key(phase_key)
        if phase_u == "SHOOTING_PHASE":
            return not bool(getattr(round_state, "shot_this_round", False))
        if phase_u == "FIGHT_PHASE":
            return not bool(getattr(round_state, "fought_this_phase", False))
        return True

    def _dg_effective_cp_cost(self, stratagem, *, target_unit=None) -> int:
        cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        if hasattr(self.player, "apply_stratagem_cp_cost"):
            result = self.player.apply_stratagem_cp_cost(stratagem, target_unit=target_unit)
            cost = int(result.get("cost", cost))
        return int(cost)

    def _dg_finalize_use(self, stratagem, *, dequeue: bool) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _dg_append_temp_effect(self, unit: Any, effect: dict) -> None:
        root = self._dg_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        existing = list(sr.get("death_guard_temp_effects", []) or [])
        effect_id = str(effect.get("id", "") or "").strip()
        kept: list[dict] = []
        for entry in list(existing or []):
            if not isinstance(entry, dict):
                continue
            if effect_id and str(entry.get("id", "") or "").strip() == effect_id:
                continue
            kept.append(dict(entry))
        kept.append(dict(effect))
        kept.sort(key=lambda entry: str(entry.get("id", "") or ""))
        sr["death_guard_temp_effects"] = kept
        root.special_rules = sr

    def _dg_apply_temp_effects(
        self,
        unit: Any,
        *,
        detachment: str,
        phase_key: str,
        effects: list[dict],
    ) -> None:
        owner_id = self._dg_turn_owner_id()
        turn = self._dg_current_turn()
        unit_id = self._dg_sort_key(self._dg_root(unit))
        for index, entry in enumerate(list(effects or [])):
            if not isinstance(entry, dict):
                continue
            payload = dict(entry)
            payload.setdefault("detachment", str(detachment or ""))
            payload.setdefault("expires_mode", "phase")
            payload.setdefault("turn_owner_id", owner_id)
            payload.setdefault("turn", int(turn))
            payload.setdefault("expires_phase", str(phase_key or ""))
            effect_id = str(payload.get("id", "") or "").strip()
            if not effect_id:
                source_key = str(payload.get("source", "death_guard_effect") or "death_guard_effect").strip().lower()
                source_key = re.sub(r"[^a-z0-9]+", "_", source_key).strip("_") or "death_guard_effect"
                effect_id = f"{source_key}:{unit_id}:{int(turn)}:{str(phase_key or '').lower()}:{index}"
            payload["id"] = effect_id
            self._dg_append_temp_effect(unit, payload)

    @staticmethod
    def _dg_normalize_name(text: str) -> str:
        value = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
        return re.sub(r"\s+", " ", value).strip()

    def _dg_unit_contains_named_member(self, unit: Any, token: str) -> bool:
        root = self._dg_root(unit)
        token_norm = self._dg_normalize_name(token)
        if root is None or not token_norm:
            return False
        names = [getattr(root, "name", "")]
        members_fn = getattr(root, "get_attached_unit_members", None)
        members = list(members_fn() or []) if callable(members_fn) else [root]
        for member in list(members or []):
            names.append(getattr(member, "name", ""))
        for name in list(names or []):
            if token_norm in self._dg_normalize_name(name):
                return True
        return False

    @staticmethod
    def _dg_model_is_alive(model: Any) -> bool:
        if model is None:
            return False
        alive_attr = getattr(model, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    def _dg_alive_models(self, unit: Any) -> list[Any]:
        root = self._dg_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = list(getattr(root, "models", []) or [])
        alive = [model for model in list(models or []) if self._dg_model_is_alive(model)]
        alive.sort(key=self._dg_sort_key)
        return alive

    def _dg_unit_within_horizontal_vertical_of_unit(
        self,
        unit: Any,
        other_unit: Any,
        *,
        horizontal: float,
        vertical: float,
    ) -> bool:
        root = self._dg_root(unit)
        other_root = self._dg_root(other_unit)
        if root is None or other_root is None:
            return False
        source_models = list(self._dg_alive_models(root) or [])
        target_models = list(self._dg_alive_models(other_root) or [])
        if not source_models or not target_models:
            return False
        for source_model in list(source_models or []):
            for target_model in list(target_models or []):
                try:
                    h = float(horizontal_distance_between_bases_2d(source_model, target_model))
                    v = float(vertical_distance_between_bases(source_model, target_model))
                except (AttributeError, TypeError, ValueError):
                    continue
                if h <= float(horizontal) + 1e-6 and v <= float(vertical) + 1e-6:
                    return True
        return False

    def _dg_visible_enemy_candidates(
        self,
        source_unit: Any,
        *,
        max_distance: float,
        exclude_keywords_any: tuple[str, ...] = (),
    ) -> list[Any]:
        source_root = self._dg_root(source_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if source_root is None or game_map is None:
            return []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        los_check = getattr(source_root, "_attacking_unit_has_any_los_to_target_unit", None)
        seen: set[str] = set()
        candidates: list[Any] = []
        source_models = list(self._dg_alive_models(source_root) or [])
        for enemy in list(get_enemy_units(source_root) or []):
            enemy_root = self._dg_root(enemy)
            if enemy_root is None:
                continue
            if self._dg_owned_by_player(enemy_root, self.player):
                continue
            enemy_id = self._dg_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if not self._dg_on_battlefield(enemy_root, require_targetable=False):
                continue
            if exclude_keywords_any and any(self._dg_has_keyword(enemy_root, keyword) for keyword in list(exclude_keywords_any or ())):
                continue
            if callable(los_check):
                try:
                    if not bool(los_check(enemy_root, game_map)):
                        continue
                except (AttributeError, TypeError, ValueError):
                    continue
            in_range = False
            for source_model in list(source_models or []):
                for target_model in list(self._dg_alive_models(enemy_root) or []):
                    try:
                        distance = float(distance_between_models_bases_3d(source_model, target_model))
                    except (AttributeError, TypeError, ValueError):
                        continue
                    if distance <= float(max_distance) + 1e-6:
                        in_range = True
                        break
                if in_range:
                    break
            if in_range:
                candidates.append(enemy_root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_deaths_heads_enemy_candidates(self, source_unit: Any) -> list[Any]:
        return self._dg_visible_enemy_candidates(
            source_unit,
            max_distance=8.0,
            exclude_keywords_any=("VEHICLE",),
        )

    def _dg_mobile_vector_bodyguard_candidates(self, source_unit: Any) -> list[Any]:
        source_root = self._dg_root(source_unit)
        if source_root is None:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        candidates: list[Any] = []
        for entry in list(getattr(army, "units", []) or []):
            root = self._dg_root(entry)
            if root is None or root is source_root:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_on_battlefield(root, require_targetable=True):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if self._dg_is_attached_unit(root):
                continue
            can_attach_to = getattr(source_root, "can_attach_to", None)
            if not callable(can_attach_to) or not bool(can_attach_to(root)):
                continue
            if not self._dg_unit_within_horizontal_vertical_of_unit(source_root, root, horizontal=2.0, vertical=5.0):
                continue
            candidates.append(root)
        candidates.sort(key=self._dg_sort_key)
        return candidates

    def _dg_character_model_count(self, unit: Any) -> int:
        root = self._dg_root(unit)
        if root is None:
            return 0
        count = 0
        for model in list(self._dg_alive_models(root) or []):
            if bool(getattr(model, "is_character", False)):
                count += 1
                continue
            parent_unit = getattr(model, "parent_unit", None)
            if parent_unit is not None and self._dg_has_keyword(parent_unit, "CHARACTER"):
                count += 1
        return int(count)

    def _queue_champions_of_contagion_grotesque_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
        event_name: str,
    ) -> None:
        if not self._is_champions_of_contagion_detachment():
            return
        s = self.get_by_name("GROTESQUE FORTITUDE")
        if s is None:
            return
        if self.player.command_points < self._dg_effective_cp_cost(s):
            return
        if (s.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        if attacking_unit is None:
            return
        attacker_root = self._dg_root(attacking_unit)
        if attacker_root is None or self._dg_owned_by_player(attacker_root, self.player):
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._dg_root(unit)
            if root is None:
                continue
            root_id = self._dg_sort_key(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            if not self._dg_is_death_guard_unit(root):
                continue
            if not self._dg_is_attached_unit(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            candidates.append(root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == event_name
                and str(reaction.get("stratagem", "") or "").strip().upper() == "GROTESQUE FORTITUDE"
                and reaction.get("attacking_unit") is attacker_root
            ):
                return
        payload = {
            "event": event_name,
            "phase_name": str(phase_name or ""),
            "stratagem": s.name,
            "cp_cost": s.cp_cost,
            "attacking_unit": attacker_root,
            "candidates": list(candidates),
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_death_guard_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
        event_name: str,
    ) -> None:
        self._queue_champions_of_contagion_grotesque_reaction(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
            phase_name=phase_name,
            event_name=event_name,
        )

    def _clear_deaths_heads_if_expired(self, *, player=None, phase=None) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "COMMAND_PHASE":
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id or self.game is None:
            return
        for game_player in list(getattr(self.game, "players", []) or []):
            army = getattr(game_player, "army", None)
            units = list(getattr(army, "units", []) or []) if army is not None else []
            for unit in list(units or []):
                root = self._dg_root(unit)
                sr = getattr(root, "special_rules", None) if root is not None else None
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("deaths_heads_owner", "") or "") != owner_id:
                    continue
                if not bool(sr.get("deaths_heads_active", False)):
                    continue
                for key in (
                    "deaths_heads_active",
                    "deaths_heads_owner",
                    "deaths_heads_turn",
                    "deaths_heads_source",
                ):
                    sr.pop(key, None)
                root.special_rules = sr

    def _use_death_guard_stratagem(self, s, **kwargs):
        name_u = str(getattr(s, "name", "") or "").strip().upper()
        if name_u not in {
            "BLESSINGS OF FILTH",
            "DEATH'S HEADS",
            "GROTESQUE FORTITUDE",
            "MALIGNANCE MAGNIFIED",
            "MOBILE VECTOR",
            "RABID INFUSION",
        }:
            return None

        if not self._is_champions_of_contagion_detachment():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        phase_key = self._dg_phase_key(phase_name or self._dg_current_phase_key())
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None

        if name_u == "BLESSINGS OF FILTH":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: BLESSINGS OF FILTH: no target unit provided")
                return False
            if not self._dg_is_death_guard_unit(root):
                logger.error("ERROR: BLESSINGS OF FILTH: target must be a DEATH GUARD unit")
                return False
            if not self._dg_is_attached_unit(root):
                logger.error("ERROR: BLESSINGS OF FILTH: target must be an Attached unit")
                return False
            if not self._dg_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: BLESSINGS OF FILTH: target unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: BLESSINGS OF FILTH: target cannot be selected")
                return False
            if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                logger.error("ERROR: BLESSINGS OF FILTH: wrong phase")
                return False
            if phase_key == "SHOOTING_PHASE" and active_player is not self.player:
                logger.error("ERROR: BLESSINGS OF FILTH: Shooting phase use requires your turn")
                return False
            if not self._dg_unit_not_selected_for_phase_action(root, phase_key=phase_key):
                logger.error("ERROR: BLESSINGS OF FILTH: unit has already been selected this phase")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            attack_type = "ranged" if phase_key == "SHOOTING_PHASE" else "melee"
            self._dg_apply_temp_effects(
                root,
                detachment="champions_of_contagion",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "crit_hit_threshold",
                        "attack_type": attack_type,
                        "value": 5,
                        "source": str(s.name or "Blessings of Filth"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: BLESSINGS OF FILTH: target unit scores critical hits on unmodified 5+ this phase.")
            return True

        if name_u == "MALIGNANCE MAGNIFIED":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: MALIGNANCE MAGNIFIED: no target unit provided")
                return False
            if not self._dg_is_death_guard_unit(root):
                logger.error("ERROR: MALIGNANCE MAGNIFIED: target must be a DEATH GUARD unit")
                return False
            if not self._dg_is_attached_unit(root):
                logger.error("ERROR: MALIGNANCE MAGNIFIED: target must be an Attached unit")
                return False
            if not self._dg_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: MALIGNANCE MAGNIFIED: target unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: MALIGNANCE MAGNIFIED: target cannot be selected")
                return False
            if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                logger.error("ERROR: MALIGNANCE MAGNIFIED: wrong phase")
                return False
            if phase_key == "SHOOTING_PHASE" and active_player is not self.player:
                logger.error("ERROR: MALIGNANCE MAGNIFIED: Shooting phase use requires your turn")
                return False
            if not self._dg_unit_not_selected_for_phase_action(root, phase_key=phase_key):
                logger.error("ERROR: MALIGNANCE MAGNIFIED: unit has already been selected this phase")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            attack_type = "ranged" if phase_key == "SHOOTING_PHASE" else "melee"
            effects = [
                {
                    "effect": "hit_reroll",
                    "attack_type": attack_type,
                    "reroll_mode": "full",
                    "target_condition": "below_starting_strength",
                    "source": str(s.name or "Malignance Magnified"),
                },
                {
                    "effect": "wound_reroll",
                    "attack_type": attack_type,
                    "reroll_mode": "full",
                    "target_condition": "below_starting_strength",
                    "source": str(s.name or "Malignance Magnified"),
                },
            ]
            self._dg_apply_temp_effects(
                root,
                detachment="champions_of_contagion",
                phase_key=phase_key,
                effects=effects,
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: MALIGNANCE MAGNIFIED: target unit re-rolls hit and wound rolls vs targets below Starting Strength this phase.")
            return True

        if name_u == "GROTESQUE FORTITUDE":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "GROTESQUE FORTITUDE":
                        continue
                    root = self._dg_root(reaction.get("target_unit") or reaction.get("unit"))
                    if root is not None:
                        break
            if root is None:
                logger.error("ERROR: GROTESQUE FORTITUDE: no target unit provided")
                return False
            attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
            if attacking_unit is None:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "GROTESQUE FORTITUDE":
                        continue
                    attacking_unit = reaction.get("attacking_unit")
                    if attacking_unit is not None:
                        break
            attacker_root = self._dg_root(attacking_unit)
            if attacker_root is None:
                logger.error("ERROR: GROTESQUE FORTITUDE: missing attacking unit")
                return False
            if not self._dg_is_death_guard_unit(root):
                logger.error("ERROR: GROTESQUE FORTITUDE: target must be a DEATH GUARD unit")
                return False
            if not self._dg_is_attached_unit(root):
                logger.error("ERROR: GROTESQUE FORTITUDE: target must be an Attached unit")
                return False
            if not self._dg_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: GROTESQUE FORTITUDE: target unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: GROTESQUE FORTITUDE: target cannot be selected")
                return False
            if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                logger.error("ERROR: GROTESQUE FORTITUDE: wrong phase")
                return False
            if phase_key == "SHOOTING_PHASE" and active_player is self.player:
                logger.error("ERROR: GROTESQUE FORTITUDE: Shooting phase use requires your opponent's turn")
                return False
            if self._dg_owned_by_player(attacker_root, self.player):
                logger.error("ERROR: GROTESQUE FORTITUDE: attacking unit must be an enemy unit")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="champions_of_contagion",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "toughness_bonus",
                        "value": 2,
                        "source": str(s.name or "Grotesque Fortitude"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: GROTESQUE FORTITUDE: target unit gains +2 Toughness this phase.")
            return True

        if name_u == "RABID INFUSION":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            root = self._dg_root(unit)
            if root is None:
                logger.error("ERROR: RABID INFUSION: no target unit provided")
                return False
            if not self._dg_is_death_guard_unit(root):
                logger.error("ERROR: RABID INFUSION: target must be a DEATH GUARD unit")
                return False
            if not self._dg_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: RABID INFUSION: target unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                logger.error("ERROR: RABID INFUSION: target cannot be selected")
                return False
            if phase_key != "FIGHT_PHASE":
                logger.error("ERROR: RABID INFUSION: wrong phase")
                return False
            if self._dg_character_model_count(root) < 2:
                logger.error("ERROR: RABID INFUSION: target unit must include two Character models")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            self._dg_apply_temp_effects(
                root,
                detachment="champions_of_contagion",
                phase_key=phase_key,
                effects=[
                    {
                        "effect": "fight_first",
                        "source": str(s.name or "Rabid Infusion"),
                    }
                ],
            )
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: RABID INFUSION: target unit gains Fights First this phase.")
            return True

        if name_u == "MOBILE VECTOR":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            source_root = self._dg_root(unit)
            if source_root is None:
                logger.error("ERROR: MOBILE VECTOR: no source unit provided")
                return False
            if not self._dg_is_death_guard_character_unit(source_root):
                logger.error("ERROR: MOBILE VECTOR: source must be a DEATH GUARD CHARACTER unit")
                return False
            if not self._dg_on_battlefield(source_root, require_targetable=True):
                logger.error("ERROR: MOBILE VECTOR: source unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
                logger.error("ERROR: MOBILE VECTOR: source unit cannot be selected")
                return False
            if phase_key != "MOVEMENT_PHASE":
                logger.error("ERROR: MOBILE VECTOR: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: MOBILE VECTOR: not your turn")
                return False
            if getattr(source_root, "attached_to", None) is not None:
                logger.error("ERROR: MOBILE VECTOR: source unit is already leading a unit")
                return False
            bodyguard_unit = kwargs.get("bodyguard_unit") or kwargs.get("target_bodyguard_unit") or kwargs.get("other_unit")
            candidates = list(self._dg_mobile_vector_bodyguard_candidates(source_root) or [])
            if bodyguard_unit is None:
                if len(candidates) == 1:
                    bodyguard_unit = candidates[0]
                else:
                    logger.error("ERROR: MOBILE VECTOR: missing eligible bodyguard target")
                    return False
            bodyguard_root = self._dg_root(bodyguard_unit)
            if bodyguard_root is None or bodyguard_root not in candidates:
                logger.error("ERROR: MOBILE VECTOR: selected bodyguard unit is not eligible")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=source_root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            source_root.attach_to_unit(bodyguard_root)
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info(
                "INFO: MOBILE VECTOR: %s attached to %s.",
                getattr(source_root, "name", "Unit"),
                getattr(bodyguard_root, "name", "Unit"),
            )
            return True

        if name_u == "DEATH'S HEADS":
            unit = kwargs.get("unit") or kwargs.get("target_unit")
            source_root = self._dg_root(unit)
            if source_root is None:
                logger.error("ERROR: DEATH'S HEADS: no source unit provided")
                return False
            if not self._dg_is_death_guard_unit(source_root):
                logger.error("ERROR: DEATH'S HEADS: source must be a DEATH GUARD unit")
                return False
            if not self._dg_on_battlefield(source_root, require_targetable=True):
                logger.error("ERROR: DEATH'S HEADS: source unit must be on the battlefield")
                return False
            if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
                logger.error("ERROR: DEATH'S HEADS: source unit cannot be selected")
                return False
            if phase_key != "SHOOTING_PHASE":
                logger.error("ERROR: DEATH'S HEADS: wrong phase")
                return False
            if active_player is not self.player:
                logger.error("ERROR: DEATH'S HEADS: not your turn")
                return False
            if not self._dg_unit_contains_named_member(source_root, "Biologus Putrifier"):
                logger.error("ERROR: DEATH'S HEADS: source must be a Biologus Putrifier unit")
                return False
            if self._dg_is_unit_engaged(source_root):
                logger.error("ERROR: DEATH'S HEADS: source unit cannot be within Engagement Range")
                return False
            if not self._dg_unit_not_selected_for_phase_action(source_root, phase_key=phase_key):
                logger.error("ERROR: DEATH'S HEADS: source unit has already been selected to shoot")
                return False
            enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
            candidates = list(self._dg_deaths_heads_enemy_candidates(source_root) or [])
            if enemy_unit is None:
                if len(candidates) == 1:
                    enemy_unit = candidates[0]
                else:
                    logger.error("ERROR: DEATH'S HEADS: missing enemy target selection")
                    return False
            enemy_root = self._dg_root(enemy_unit)
            if enemy_root is None or enemy_root not in candidates:
                logger.error("ERROR: DEATH'S HEADS: selected enemy unit is not eligible")
                return False
            eff_cost = self._dg_effective_cp_cost(s, target_unit=source_root)
            if not self.player.spend_command_points(eff_cost, reason=f"Stratagem: {s.name}", source="stratagem"):
                return False
            sr = getattr(enemy_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["deaths_heads_active"] = True
            sr["deaths_heads_owner"] = str(getattr(self.player, "id", "") or "")
            sr["deaths_heads_turn"] = int(self._dg_current_turn())
            sr["deaths_heads_source"] = str(s.name or "Death's Heads")
            enemy_root.special_rules = sr
            self._dg_finalize_use(s, dequeue=bool(kwargs.get("dequeue")))
            logger.info("INFO: DEATH'S HEADS: target enemy unit gains all Plague effects until your next turn.")
            return True

        return None
