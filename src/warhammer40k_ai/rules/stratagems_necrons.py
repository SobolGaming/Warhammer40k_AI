from __future__ import annotations

import logging
from typing import Any, List, Optional

from ..utility import dice as dice_module
from ..utility.aura_utils import distance_between_models_bases_3d
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class NecronsStratagemMixin:
    _ANNIHILATION_LEGION_KEYWORDS = ("DESTROYER CULT", "FLAYED ONES")

    def _get_necrons_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else None
        return getattr(army, "necrons_detachments", None) if army is not None else None

    def _necrons_root(self, unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        return get_root() if callable(get_root) else unit

    def _necrons_current_turn(self) -> int:
        game = getattr(self, "game", None)
        if game is None:
            return 0
        try:
            return int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _necrons_owned_by_player(self, unit: Any) -> bool:
        root = self._necrons_root(unit)
        if root is None:
            return False
        get_army = getattr(root, "get_parent_army", None)
        army = get_army() if callable(get_army) else getattr(root, "parent_army", None)
        return getattr(army, "player", None) is self.player

    def _necrons_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._necrons_root(unit)
        if root is None:
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return False
        if require_targetable and self._unit_cannot_be_target_of_stratagem(root):
            return False
        return True

    def _is_hypercrypt_legion(self) -> bool:
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return False
        return bool(mgr.is_hypercrypt_legion())

    def _is_starshatter_arsenal(self) -> bool:
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return False
        return bool(mgr.is_starshatter_arsenal())

    def _is_annihilation_legion(self) -> bool:
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return False
        return bool(mgr.is_annihilation_legion())

    def _is_awakened_dynasty(self) -> bool:
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return False
        return bool(mgr.is_awakened_dynasty())

    def _necrons_entity_has_keyword(self, entity: Any, keyword: str) -> bool:
        mgr = self._get_necrons_mgr()
        if mgr is not None and callable(getattr(mgr, "_entity_has_keyword", None)):
            return bool(mgr._entity_has_keyword(entity, keyword))
        if entity is None:
            return False
        kw = str(keyword or "").strip()
        if not kw:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any(kw))
        raw = [str(value or "") for value in list(getattr(entity, "keywords", []) or [])]
        raw += [str(value or "") for value in list(getattr(entity, "faction_keywords", []) or [])]
        return kw.lower() in {value.lower() for value in raw if str(value).strip()}

    def _necrons_unit_contains_keyword(self, unit: Any, keyword: str) -> bool:
        mgr = self._get_necrons_mgr()
        if mgr is not None and callable(getattr(mgr, "_unit_contains_keyword", None)):
            return bool(mgr._unit_contains_keyword(unit, keyword))
        root = self._necrons_root(unit)
        if root is None:
            return False
        if self._necrons_entity_has_keyword(root, keyword):
            return True
        members_fn = getattr(root, "get_attached_unit_members", None)
        if not callable(members_fn):
            return False
        for member in list(members_fn() or []):
            if self._necrons_entity_has_keyword(member, keyword):
                return True
        return False

    def _necrons_iter_unit_models(self, unit: Any) -> list[Any]:
        mgr = self._get_necrons_mgr()
        if mgr is not None and callable(getattr(mgr, "_iter_unit_models", None)):
            return [model for model in list(mgr._iter_unit_models(unit) or []) if model is not None]
        root = self._necrons_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            return [model for model in list(get_models() or []) if model is not None]
        return [model for model in list(getattr(root, "models", []) or []) if model is not None]

    def _annihilation_legion_unit_eligible(
        self,
        unit: Any,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_reanimation: bool = False,
    ) -> bool:
        if not self._is_annihilation_legion():
            return False
        root = self._necrons_root(unit)
        if root is None:
            return False
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return False
        if not self._necrons_owned_by_player(root):
            return False
        if not self._necrons_on_battlefield(root):
            return False
        if not bool(mgr.unit_is_necrons(root)):
            return False
        has_destroyer_cult = bool(getattr(root, "has_any_keyword", lambda *_args: False)("DESTROYER CULT"))
        has_flayed_ones = bool(getattr(root, "has_any_keyword", lambda *_args: False)("FLAYED ONES"))
        if not has_destroyer_cult and not has_flayed_ones:
            return False
        round_state = getattr(root, "round_state", None)
        if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
            return False
        if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
            return False
        if require_reanimation:
            has_rp = getattr(root, "attached_unit_has_reanimation_protocols", None)
            if not callable(has_rp) or not bool(has_rp()):
                return False
        return True

    def _annihilation_legion_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_reanimation: bool = False,
    ) -> List[Any]:
        if not self._is_annihilation_legion():
            return []
        army = self.player.get_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        results: List[Any] = []
        seen: set[str] = set()
        for unit in units:
            root = self._necrons_root(unit)
            uid = str(get_entity_id(root) or "") if root is not None else ""
            if not uid or uid in seen:
                continue
            seen.add(uid)
            if not self._annihilation_legion_unit_eligible(
                root,
                require_not_shot=require_not_shot,
                require_not_fought=require_not_fought,
                require_reanimation=require_reanimation,
            ):
                continue
            results.append(root)
        results.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return results

    def _annihilation_legion_unit_in_candidates(self, unit: Any, candidates: list[Any]) -> bool:
        root = self._necrons_root(unit)
        if root is None:
            return False
        unit_id = str(get_entity_id(root) or "")
        return any(str(get_entity_id(self._necrons_root(candidate)) or "") == unit_id for candidate in list(candidates or []))

    def _annihilation_legion_is_engaged(self, unit: Any) -> bool:
        root = self._necrons_root(unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if root is None or game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._necrons_root(enemy)
            if enemy_root is None:
                continue
            if not self._necrons_on_battlefield(enemy_root, require_targetable=False):
                continue
            if bool(is_within_engagement(root, enemy_root)):
                return True
        return False

    def _capture_annihilation_legion_opponent_movement_phase_start_engagements(self, *, player: Any, phase: Any) -> None:
        tracker = {
            "phase": "",
            "turn": int(self._necrons_current_turn()),
            "by_enemy": {},
        }
        self._annihilation_legion_start_engagements = tracker

        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "MOVEMENT_PHASE":
            return
        if player is self.player:
            return
        if not self._is_annihilation_legion():
            return
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement):
            return

        by_enemy: dict[str, dict[str, Any]] = {}
        for friendly_root in self._annihilation_legion_candidates():
            friendly_id = str(get_entity_id(friendly_root) or "")
            if not friendly_id:
                continue
            for enemy_unit in list(get_enemy_units(friendly_root) or []):
                enemy_root = self._necrons_root(enemy_unit)
                enemy_id = str(get_entity_id(enemy_root) or "") if enemy_root is not None else ""
                if not enemy_id:
                    continue
                if self._necrons_owned_by_player(enemy_root):
                    continue
                if not self._necrons_on_battlefield(enemy_root, require_targetable=False):
                    continue
                if not bool(is_within_engagement(friendly_root, enemy_root)):
                    continue
                by_enemy.setdefault(enemy_id, {})[friendly_id] = friendly_root

        tracker["phase"] = "MOVEMENT_PHASE"
        tracker["turn"] = int(self._necrons_current_turn())
        tracker["by_enemy"] = {
            enemy_id: sorted(list(unit_map.values()), key=lambda item: str(get_entity_id(item) or ""))
            for enemy_id, unit_map in sorted(by_enemy.items(), key=lambda item: str(item[0] or ""))
        }

    def _annihilation_legion_start_phase_engaged_candidates_for_enemy(self, enemy_unit: Any) -> list[Any]:
        enemy_root = self._necrons_root(enemy_unit)
        enemy_id = str(get_entity_id(enemy_root) or "") if enemy_root is not None else ""
        if not enemy_id:
            return []
        tracker = getattr(self, "_annihilation_legion_start_engagements", None)
        if not isinstance(tracker, dict):
            return []
        if str(tracker.get("phase", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return []
        try:
            marked_turn = int(tracker.get("turn", 0) or 0)
        except (TypeError, ValueError):
            marked_turn = 0
        current_turn = int(self._necrons_current_turn())
        if marked_turn and current_turn and marked_turn != current_turn:
            return []
        by_enemy = tracker.get("by_enemy", {})
        if not isinstance(by_enemy, dict):
            return []
        results: list[Any] = []
        for unit in list(by_enemy.get(enemy_id, []) or []):
            root = self._necrons_root(unit)
            if not self._annihilation_legion_unit_eligible(root):
                continue
            results.append(root)
        results.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return results

    def _annihilation_legion_was_engaged_with_enemy_at_movement_phase_start(self, unit: Any, enemy_unit: Any) -> bool:
        return self._annihilation_legion_unit_in_candidates(
            unit,
            self._annihilation_legion_start_phase_engaged_candidates_for_enemy(enemy_unit),
        )

    def _annihilation_legion_fight_snapshot_store(self) -> dict[str, Any]:
        phase_name = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        current_turn = int(self._necrons_current_turn())
        tracker = getattr(self, "_annihilation_legion_fight_target_snapshots", None)
        tracker_turn = 0
        if isinstance(tracker, dict):
            try:
                tracker_turn = int(tracker.get("turn", 0) or 0)
            except (TypeError, ValueError):
                tracker_turn = 0
        if (
            not isinstance(tracker, dict)
            or str(tracker.get("phase", "") or "").strip().upper() != phase_name
            or tracker_turn != current_turn
        ):
            tracker = {
                "phase": phase_name,
                "turn": current_turn,
                "by_pair": {},
            }
            self._annihilation_legion_fight_target_snapshots = tracker
        return tracker

    def _capture_annihilation_legion_fight_targets_selected(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_annihilation_legion():
            return
        if str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        attacker_root = self._necrons_root(attacking_unit)
        if not self._annihilation_legion_unit_eligible(attacker_root, require_reanimation=True):
            return
        attacker_id = str(get_entity_id(attacker_root) or "")
        if not attacker_id:
            return
        tracker = self._annihilation_legion_fight_snapshot_store()
        by_pair = tracker.setdefault("by_pair", {})
        for target in list(target_units or []):
            target_root = self._necrons_root(target)
            target_id = str(get_entity_id(target_root) or "") if target_root is not None else ""
            if not target_id:
                continue
            is_below_half = getattr(target_root, "is_below_half_strength", None)
            by_pair[f"{attacker_id}:{target_id}"] = bool(is_below_half()) if callable(is_below_half) else False

    def _consume_annihilation_legion_fight_target_snapshot(self, *, attacking_unit: Any, target_unit: Any) -> Optional[bool]:
        attacker_root = self._necrons_root(attacking_unit)
        target_root = self._necrons_root(target_unit)
        attacker_id = str(get_entity_id(attacker_root) or "") if attacker_root is not None else ""
        target_id = str(get_entity_id(target_root) or "") if target_root is not None else ""
        if not attacker_id or not target_id:
            return None
        tracker = self._annihilation_legion_fight_snapshot_store()
        by_pair = tracker.get("by_pair", {})
        if not isinstance(by_pair, dict):
            return None
        return by_pair.pop(f"{attacker_id}:{target_id}", None)

    def _queue_annihilation_legion_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None or self.game is None:
            return
        if str(action or "").strip().lower() not in {"fall_back", "fallback"}:
            return
        if str(self._current_phase_name or "").strip().lower() != "movement phase":
            return
        if getattr(self.game, "get_current_player", lambda: None)() is self.player:
            return
        if not self._is_annihilation_legion():
            return
        stratagem = self.get_by_name("BLOOD-FUELLED CRUELTY")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in self._used_stratagems_this_phase:
            return
        enemy_root = self._necrons_root(unit)
        candidates = self._annihilation_legion_start_phase_engaged_candidates_for_enemy(enemy_root)
        if not candidates:
            return
        if not stratagem.can_use(self.player, self.game, moving_unit=enemy_root, phase_name="Movement phase"):
            return
        for reaction in list(self._pending_reactions or []):
            if (
                reaction.get("event") == "unit_move_ended"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "BLOOD-FUELLED CRUELTY"
                and reaction.get("enemy_unit") is enemy_root
            ):
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "action": "fall_back",
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_annihilation_legion_shooting_reactions(
        self,
        *,
        attacker_unit: Any,
        killing_models_by_target: dict | None,
    ) -> None:
        if attacker_unit is None or self.game is None:
            return
        if str(self._current_phase_name or "").strip().lower() != "shooting phase":
            return
        if getattr(self.game, "get_current_player", lambda: None)() is self.player:
            return
        if not self._is_annihilation_legion():
            return
        stratagem = self.get_by_name("INSANITY'S IRE")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in self._used_stratagems_this_phase:
            return
        enemy_root = self._necrons_root(attacker_unit)
        if enemy_root is None or self._necrons_owned_by_player(enemy_root):
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for target_unit, destroyed_models in dict(killing_models_by_target or {}).items():
            if not destroyed_models:
                continue
            target_root = self._necrons_root(target_unit)
            target_id = str(get_entity_id(target_root) or "") if target_root is not None else ""
            if not target_id or target_id in seen:
                continue
            if not self._annihilation_legion_unit_eligible(target_root):
                continue
            seen.add(target_id)
            candidates.append(target_root)
        if not candidates:
            return
        candidates.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        if not stratagem.can_use(self.player, self.game, attacker_unit=enemy_root, phase_name="Shooting phase"):
            return
        for reaction in list(self._pending_reactions or []):
            if (
                reaction.get("event") == "unit_shooting_resolved"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "INSANITY'S IRE"
                and reaction.get("enemy_unit") is enemy_root
            ):
                return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "attacker_unit": enemy_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_annihilation_legion_fight_attacks_resolved_reactions(
        self,
        *,
        unit: Any,
        target_unit: Any,
        killing_models_by_target: dict | None,
    ) -> None:
        if unit is None or self.game is None:
            return
        if str(self._current_phase_name or "").strip().lower() != "fight phase":
            return
        if not self._is_annihilation_legion():
            return
        stratagem = self.get_by_name("MURDEROUS REANIMATION")
        if stratagem is None:
            return
        if self.player.command_points < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_root = self._necrons_root(unit)
        if not self._annihilation_legion_unit_eligible(attacker_root, require_reanimation=True):
            return
        if not stratagem.can_use(self.player, self.game, unit=attacker_root, phase_name="Fight phase"):
            return
        targets: list[Any] = []
        seen_target_ids: set[str] = set()
        for candidate in [target_unit, *list(dict(killing_models_by_target or {}).keys())]:
            target_root = self._necrons_root(candidate)
            target_id = str(get_entity_id(target_root) or "") if target_root is not None else ""
            if not target_id or target_id in seen_target_ids:
                continue
            seen_target_ids.add(target_id)
            targets.append(target_root)
        should_queue = False
        qualifying_target = None
        for enemy_root in targets:
            if enemy_root is None or self._necrons_owned_by_player(enemy_root):
                continue
            was_below_half = self._consume_annihilation_legion_fight_target_snapshot(
                attacking_unit=attacker_root,
                target_unit=enemy_root,
            )
            is_alive = getattr(enemy_root, "is_alive", None)
            destroyed = not bool(is_alive()) if callable(is_alive) else False
            is_below_half = getattr(enemy_root, "is_below_half_strength", None)
            now_below_half = bool(is_below_half()) if callable(is_below_half) else False
            if destroyed or (was_below_half is False and now_below_half):
                should_queue = True
                qualifying_target = enemy_root
                break
        if not should_queue:
            return
        for reaction in list(self._pending_reactions or []):
            if (
                reaction.get("event") == "fight_attacks_resolved"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "MURDEROUS REANIMATION"
                and reaction.get("unit") is attacker_root
            ):
                return
        self._queue_reaction(
            {
                "event": "fight_attacks_resolved",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": attacker_root,
                "target_unit": attacker_root,
                "enemy_unit": qualifying_target,
                "candidates": [attacker_root],
            }
        )

    def _annihilation_legion_find_pending_reaction(self, stratagem_name: str, *, unit: Any = None) -> Optional[dict[str, Any]]:
        target_name = str(stratagem_name or "").strip().upper()
        target_unit_id = str(get_entity_id(self._necrons_root(unit)) or "") if unit is not None else ""
        for reaction in reversed(list(self._pending_reactions or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != target_name:
                continue
            if not target_unit_id:
                return reaction
            reaction_unit = reaction.get("unit") or reaction.get("target_unit")
            reaction_unit_id = str(get_entity_id(self._necrons_root(reaction_unit)) or "")
            if reaction_unit_id == target_unit_id:
                return reaction
        return None

    def _necrons_spend_cp(self, stratagem: Any, *, target_unit: Any) -> bool:
        eff_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit) or {}
            eff_cost = int(preview.get("cost", eff_cost))
        return bool(
            self.player.spend_command_points(
                eff_cost,
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Stratagem')}",
                source="stratagem",
            )
        )

    def _necrons_finalize_stratagem_use(self, stratagem: Any, *, dequeue: bool) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        self._used_stratagems_this_phase.add(str(getattr(stratagem, "name", "") or "").strip().upper())

    def _awakened_dynasty_unit_has_character_leading(self, unit: Any) -> bool:
        mgr = self._get_necrons_mgr()
        helper = getattr(mgr, "awakened_dynasty_unit_has_character_leading", None) if mgr is not None else None
        if callable(helper):
            return bool(helper(unit))
        root = self._necrons_root(unit)
        if root is None:
            return False
        for leader in list(getattr(root, "attached_leaders", []) or []):
            if leader is None or getattr(leader, "attached_to", None) is not root:
                continue
            is_alive = getattr(leader, "is_alive", None)
            if callable(is_alive) and not bool(is_alive()):
                continue
            if self._necrons_unit_contains_keyword(leader, "CHARACTER"):
                return True
        return False

    def _awakened_dynasty_unit_eligible(
        self,
        unit: Any,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_reanimation: bool = False,
        require_character_unit: bool = False,
    ) -> bool:
        if not self._is_awakened_dynasty():
            return False
        root = self._necrons_root(unit)
        if root is None:
            return False
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return False
        if not self._necrons_owned_by_player(root):
            return False
        if not self._necrons_on_battlefield(root):
            return False
        if not bool(mgr.unit_is_necrons(root)):
            return False
        round_state = getattr(root, "round_state", None)
        if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
            return False
        if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
            return False
        if require_reanimation:
            has_rp = getattr(root, "attached_unit_has_reanimation_protocols", None)
            if not callable(has_rp) or not bool(has_rp()):
                return False
        if require_character_unit and not self._necrons_unit_contains_keyword(root, "CHARACTER"):
            return False
        return True

    def _awakened_dynasty_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_reanimation: bool = False,
        require_character_unit: bool = False,
    ) -> list[Any]:
        if not self._is_awakened_dynasty():
            return []
        army = self.player.get_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        results: list[Any] = []
        seen: set[str] = set()
        for unit in units:
            root = self._necrons_root(unit)
            unit_id = str(get_entity_id(root) or "") if root is not None else ""
            if not unit_id or unit_id in seen:
                continue
            seen.add(unit_id)
            if not self._awakened_dynasty_unit_eligible(
                root,
                require_not_shot=require_not_shot,
                require_not_fought=require_not_fought,
                require_reanimation=require_reanimation,
                require_character_unit=require_character_unit,
            ):
                continue
            results.append(root)
        results.sort(key=lambda unit_obj: str(get_entity_id(unit_obj) or ""))
        return results

    def _awakened_dynasty_unit_in_candidates(self, unit: Any, candidates: list[Any]) -> bool:
        root = self._necrons_root(unit)
        if root is None:
            return False
        unit_id = str(get_entity_id(root) or "")
        return any(str(get_entity_id(self._necrons_root(candidate)) or "") == unit_id for candidate in list(candidates or []))

    def _awakened_dynasty_find_pending_reaction(
        self,
        stratagem_name: str,
        *,
        unit: Any = None,
        destroyed_model: Any = None,
    ) -> Optional[dict[str, Any]]:
        target_name = str(stratagem_name or "").strip().upper()
        target_unit_id = str(get_entity_id(self._necrons_root(unit)) or "") if unit is not None else ""
        target_model_id = str(get_entity_id(destroyed_model) or "") if destroyed_model is not None else ""
        for reaction in reversed(list(self._pending_reactions or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != target_name:
                continue
            if target_model_id:
                if str(reaction.get("destroyed_model_id", "") or "") == target_model_id:
                    return reaction
                continue
            if not target_unit_id:
                return reaction
            reaction_unit = reaction.get("unit") or reaction.get("target_unit") or reaction.get("destroyed_unit")
            reaction_unit_id = str(get_entity_id(self._necrons_root(reaction_unit)) or "")
            if reaction_unit_id == target_unit_id:
                return reaction
        return None

    def _awakened_dynasty_eternal_revenant_pending_returns(self) -> list[dict[str, Any]]:
        pending = getattr(self, "_awakened_dynasty_eternal_revenant_pending", None)
        if not isinstance(pending, list):
            pending = []
            self._awakened_dynasty_eternal_revenant_pending = pending
        return pending

    def _awakened_dynasty_eternal_revenant_used_model_ids(self) -> set[str]:
        used = getattr(self, "_awakened_dynasty_eternal_revenant_used_model_ids_set", None)
        if not isinstance(used, set):
            used = set()
            self._awakened_dynasty_eternal_revenant_used_model_ids_set = used
        return used

    def _awakened_dynasty_undying_legions_reanimation_bonus(
        self,
        *,
        root: Any,
        snapshot: Optional[dict[str, Any]] = None,
    ) -> int:
        root_id = str(get_entity_id(self._necrons_root(root)) or "")
        if isinstance(snapshot, dict) and root_id:
            try:
                return max(0, int(snapshot.get(root_id, 0) or 0))
            except (TypeError, ValueError):
                return 0
        return 1 if self._awakened_dynasty_unit_has_character_leading(root) else 0

    def _awakened_dynasty_model_anchor_position(self, model: Any) -> tuple[float, float, float] | None:
        if model is None:
            return None
        get_location = getattr(model, "get_location", None)
        if not callable(get_location):
            return None
        location = get_location()
        if location is None:
            return None
        try:
            return (float(location[0]), float(location[1]), float(location[2]))
        except (TypeError, ValueError, IndexError):
            return None

    def _awakened_dynasty_candidate_within_range_of_destroyed_model(
        self,
        candidate_unit: Any,
        destroyed_model: Any,
        *,
        range_inches: float,
    ) -> bool:
        root = self._necrons_root(candidate_unit)
        if root is None or destroyed_model is None:
            return False
        for source_model in self._necrons_iter_unit_models(root):
            if not bool(getattr(source_model, "is_alive", True)):
                continue
            if float(distance_between_models_bases_3d(source_model, destroyed_model)) <= float(range_inches) + 1e-6:
                return True
        return False

    def _queue_awakened_dynasty_model_destroyed_reactions(self, *, unit: Any, model: Any) -> None:
        if self.game is None or model is None or not self._is_awakened_dynasty():
            return
        destroyed_unit = getattr(model, "parent_unit", None) or unit
        if destroyed_unit is None or not self._necrons_owned_by_player(destroyed_unit):
            return
        if not self._necrons_unit_contains_keyword(destroyed_unit, "NECRONS"):
            return
        if not self._necrons_unit_contains_keyword(destroyed_unit, "INFANTRY"):
            return
        if not self._necrons_unit_contains_keyword(destroyed_unit, "CHARACTER"):
            return
        stratagem = self.get_by_name("PROTOCOL OF THE ETERNAL REVENANT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in self._used_stratagems_this_phase:
            return
        model_id = str(get_entity_id(model) or "")
        if model_id and model_id in self._awakened_dynasty_eternal_revenant_used_model_ids():
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            phase_name=self._current_phase_name,
            destroyed_unit=destroyed_unit,
            destroyed_model=model,
            candidates=[destroyed_unit],
        ):
            return
        for reaction in list(self._pending_reactions or []):
            if reaction.get("event") != "model_destroyed_before_removal":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "PROTOCOL OF THE ETERNAL REVENANT":
                continue
            if str(reaction.get("destroyed_model_id", "") or "") == model_id:
                return
        self._queue_reaction(
            {
                "event": "model_destroyed_before_removal",
                "phase_name": str(self._current_phase_name or ""),
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "destroyed_unit": destroyed_unit,
                "destroyed_model": model,
                "destroyed_model_id": model_id,
                "unit": destroyed_unit,
                "target_unit": destroyed_unit,
                "candidates": [destroyed_unit],
            }
        )

    def _queue_awakened_dynasty_undying_legions_reaction(
        self,
        *,
        attacker_unit: Any,
        candidates: list[Any],
        bonus_by_unit_id: dict[str, int],
        phase_name: str,
        event_name: str,
    ) -> None:
        if self.game is None or attacker_unit is None or not candidates:
            return
        stratagem = self.get_by_name("PROTOCOL OF THE UNDYING LEGIONS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in self._used_stratagems_this_phase:
            return
        enemy_root = self._necrons_root(attacker_unit)
        if enemy_root is None or self._necrons_owned_by_player(enemy_root):
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            attacker_unit=enemy_root,
            phase_name=phase_name,
            candidates=list(candidates),
        ):
            return
        for reaction in list(self._pending_reactions or []):
            if reaction.get("event") != event_name:
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "PROTOCOL OF THE UNDYING LEGIONS":
                continue
            if reaction.get("enemy_unit") is enemy_root:
                return
        payload = {
            "event": event_name,
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "attacker_unit": enemy_root,
            "candidates": list(candidates),
            "reanimation_bonus_by_unit_id": dict(bonus_by_unit_id),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_awakened_dynasty_shooting_reactions(
        self,
        *,
        attacker_unit: Any,
        killing_models_by_target: dict | None,
    ) -> None:
        if attacker_unit is None or self.game is None or not self._is_awakened_dynasty():
            return
        if str(self._current_phase_name or "").strip().lower() != "shooting phase":
            return
        if getattr(self.game, "get_current_player", lambda: None)() is self.player:
            return
        candidates: list[Any] = []
        bonus_by_unit_id: dict[str, int] = {}
        seen: set[str] = set()
        for target_unit, destroyed_models in dict(killing_models_by_target or {}).items():
            if not destroyed_models:
                continue
            target_root = self._necrons_root(target_unit)
            target_id = str(get_entity_id(target_root) or "") if target_root is not None else ""
            if not target_id or target_id in seen:
                continue
            if not self._awakened_dynasty_unit_eligible(target_root, require_reanimation=True):
                continue
            seen.add(target_id)
            candidates.append(target_root)
            bonus_by_unit_id[target_id] = 1 if self._awakened_dynasty_unit_has_character_leading(target_root) else 0
        candidates.sort(key=lambda unit_obj: str(get_entity_id(unit_obj) or ""))
        self._queue_awakened_dynasty_undying_legions_reaction(
            attacker_unit=attacker_unit,
            candidates=candidates,
            bonus_by_unit_id=bonus_by_unit_id,
            phase_name="Shooting phase",
            event_name="unit_shooting_resolved",
        )

    def _queue_awakened_dynasty_fight_attacks_resolved_reactions(
        self,
        *,
        unit: Any,
        target_unit: Any,
        killing_models_by_target: dict | None,
    ) -> None:
        if unit is None or self.game is None or not self._is_awakened_dynasty():
            return
        if str(self._current_phase_name or "").strip().lower() != "fight phase":
            return
        attacker_root = self._necrons_root(unit)
        if attacker_root is None or self._necrons_owned_by_player(attacker_root):
            return
        candidates: list[Any] = []
        bonus_by_unit_id: dict[str, int] = {}
        seen: set[str] = set()
        for candidate_unit, destroyed_models in dict(killing_models_by_target or {}).items():
            if not destroyed_models:
                continue
            target_root = self._necrons_root(candidate_unit)
            target_id = str(get_entity_id(target_root) or "") if target_root is not None else ""
            if not target_id or target_id in seen:
                continue
            if not self._awakened_dynasty_unit_eligible(target_root, require_reanimation=True):
                continue
            seen.add(target_id)
            candidates.append(target_root)
            bonus_by_unit_id[target_id] = 1 if self._awakened_dynasty_unit_has_character_leading(target_root) else 0
        if not candidates and target_unit is not None:
            target_root = self._necrons_root(target_unit)
            target_id = str(get_entity_id(target_root) or "") if target_root is not None else ""
            if target_id and self._awakened_dynasty_unit_eligible(target_root, require_reanimation=True):
                candidates.append(target_root)
                bonus_by_unit_id[target_id] = 1 if self._awakened_dynasty_unit_has_character_leading(target_root) else 0
        candidates.sort(key=lambda unit_obj: str(get_entity_id(unit_obj) or ""))
        self._queue_awakened_dynasty_undying_legions_reaction(
            attacker_unit=attacker_root,
            candidates=candidates,
            bonus_by_unit_id=bonus_by_unit_id,
            phase_name="Fight phase",
            event_name="fight_attacks_resolved",
        )

    def _queue_awakened_dynasty_unit_destroyed_reactions(
        self,
        *,
        destroyed_unit: Any,
        destroyed_by_unit: Any,
        last_model: Any,
    ) -> None:
        if self.game is None or destroyed_unit is None or destroyed_by_unit is None or not self._is_awakened_dynasty():
            return
        if str(self._current_phase_name or "").strip().lower() != "shooting phase":
            return
        if getattr(self.game, "get_current_player", lambda: None)() is self.player:
            return
        destroyed_root = self._necrons_root(destroyed_unit)
        enemy_root = self._necrons_root(destroyed_by_unit)
        mgr = self._get_necrons_mgr()
        if destroyed_root is None or enemy_root is None or mgr is None:
            return
        if not self._necrons_owned_by_player(destroyed_root) or self._necrons_owned_by_player(enemy_root):
            return
        if not bool(mgr.unit_is_necrons(destroyed_root)) or last_model is None:
            return
        stratagem = self.get_by_name("PROTOCOL OF THE VENGEFUL STARS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in self._used_stratagems_this_phase:
            return
        reactive_can_shoot = getattr(self.game, "_setup_reactive_can_shoot_target", None)
        candidates: list[Any] = []
        for candidate in self._awakened_dynasty_candidates(require_character_unit=True):
            if not self._awakened_dynasty_candidate_within_range_of_destroyed_model(
                candidate,
                last_model,
                range_inches=6.0,
            ):
                continue
            if callable(reactive_can_shoot) and not bool(reactive_can_shoot(candidate, enemy_root)):
                continue
            candidates.append(candidate)
        if not candidates:
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            attacker_unit=enemy_root,
            phase_name="Shooting phase",
            candidates=list(candidates),
        ):
            return
        for reaction in list(self._pending_reactions or []):
            if reaction.get("event") != "unit_destroyed":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "PROTOCOL OF THE VENGEFUL STARS":
                continue
            if reaction.get("enemy_unit") is enemy_root and reaction.get("destroyed_unit") is destroyed_root:
                return
        payload = {
            "event": "unit_destroyed",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "attacker_unit": enemy_root,
            "destroyed_unit": destroyed_root,
            "last_model": last_model,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _use_awakened_dynasty_conquering_tyrant(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PROTOCOL OF THE CONQUERING TYRANT: no target unit provided")
            return False
        root = self._necrons_root(unit)
        if root is None or not self._is_awakened_dynasty():
            return False
        if str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower() != "shooting phase":
            logger.error("ERROR: PROTOCOL OF THE CONQUERING TYRANT: wrong phase")
            return False
        if getattr(self.game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: PROTOCOL OF THE CONQUERING TYRANT: not your turn")
            return False
        candidates = candidates or self._awakened_dynasty_candidates(require_not_shot=True)
        if not self._awakened_dynasty_unit_eligible(root, require_not_shot=True):
            logger.error("ERROR: PROTOCOL OF THE CONQUERING TYRANT: target unit is not currently eligible")
            return False
        if not self._awakened_dynasty_unit_in_candidates(root, candidates):
            logger.error("ERROR: PROTOCOL OF THE CONQUERING TYRANT: target unit is not a valid candidate")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: PROTOCOL OF THE CONQUERING TYRANT: cannot be used in current state")
            return False
        if not self._necrons_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["awakened_dynasty_conquering_tyrant_active"] = True
        sr["awakened_dynasty_conquering_tyrant_reroll_mode"] = (
            "full" if self._awakened_dynasty_unit_has_character_leading(root) else "ones"
        )
        sr["awakened_dynasty_conquering_tyrant_expires_phase"] = "SHOOTING_PHASE"
        sr["awakened_dynasty_conquering_tyrant_turn"] = int(self._necrons_current_turn())
        sr["awakened_dynasty_conquering_tyrant_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["awakened_dynasty_conquering_tyrant_source"] = str(getattr(stratagem, "name", "") or "").strip()
        root.special_rules = sr
        self._necrons_finalize_stratagem_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PROTOCOL OF THE CONQUERING TYRANT: %s gains ranged hit rerolls within half range this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_awakened_dynasty_eternal_revenant(self, stratagem: Any, **kwargs) -> bool:
        destroyed_model = kwargs.get("destroyed_model")
        destroyed_unit = kwargs.get("destroyed_unit") or kwargs.get("unit") or kwargs.get("target_unit")
        pending = self._awakened_dynasty_find_pending_reaction(
            "PROTOCOL OF THE ETERNAL REVENANT",
            unit=destroyed_unit,
            destroyed_model=destroyed_model,
        )
        if isinstance(pending, dict):
            if destroyed_model is None:
                destroyed_model = pending.get("destroyed_model")
            if destroyed_unit is None:
                destroyed_unit = pending.get("destroyed_unit") or pending.get("unit") or pending.get("target_unit")
        if destroyed_model is None or destroyed_unit is None:
            logger.error("ERROR: PROTOCOL OF THE ETERNAL REVENANT: missing destroyed model context")
            return False
        if not self._is_awakened_dynasty():
            return False
        if not self._necrons_owned_by_player(destroyed_unit):
            logger.error("ERROR: PROTOCOL OF THE ETERNAL REVENANT: target must be from your army")
            return False
        if not self._necrons_unit_contains_keyword(destroyed_unit, "NECRONS"):
            logger.error("ERROR: PROTOCOL OF THE ETERNAL REVENANT: target must be NECRONS")
            return False
        if not self._necrons_unit_contains_keyword(destroyed_unit, "INFANTRY"):
            logger.error("ERROR: PROTOCOL OF THE ETERNAL REVENANT: target must be INFANTRY")
            return False
        if not self._necrons_unit_contains_keyword(destroyed_unit, "CHARACTER"):
            logger.error("ERROR: PROTOCOL OF THE ETERNAL REVENANT: target must be a CHARACTER model")
            return False
        model_id = str(get_entity_id(destroyed_model) or "")
        if model_id and model_id in self._awakened_dynasty_eternal_revenant_used_model_ids():
            logger.error("ERROR: PROTOCOL OF THE ETERNAL REVENANT: this model has already used the stratagem this battle")
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        if not stratagem.can_use(
            self.player,
            self.game,
            destroyed_unit=destroyed_unit,
            destroyed_model=destroyed_model,
            phase_name=phase_name,
            candidates=[destroyed_unit],
        ):
            logger.error("ERROR: PROTOCOL OF THE ETERNAL REVENANT: cannot be used in current state")
            return False
        if not self._necrons_spend_cp(stratagem, target_unit=destroyed_unit):
            return False
        try:
            starting_wounds = int(getattr(destroyed_model, "_base_wounds", 0) or 0)
        except (TypeError, ValueError):
            starting_wounds = 0
        if starting_wounds <= 0:
            try:
                starting_wounds = int(getattr(destroyed_model, "wounds", getattr(destroyed_model, "_wounds", 1)) or 1)
            except (TypeError, ValueError):
                starting_wounds = 1
        restored_wounds = max(1, (int(starting_wounds) + 1) // 2)
        phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if not phase_key:
            phase_key = str(phase_name or self._current_phase_name or "").strip().upper().replace(" ", "_")
        self._awakened_dynasty_eternal_revenant_pending_returns().append(
            {
                "phase": phase_key,
                "model": destroyed_model,
                "unit": destroyed_unit,
                "anchor_pos": self._awakened_dynasty_model_anchor_position(destroyed_model),
                "wounds": int(restored_wounds),
                "source": str(getattr(stratagem, "name", "") or "PROTOCOL OF THE ETERNAL REVENANT").strip(),
            }
        )
        if model_id:
            self._awakened_dynasty_eternal_revenant_used_model_ids().add(model_id)
        self._necrons_finalize_stratagem_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PROTOCOL OF THE ETERNAL REVENANT: %s will return at phase end with %d wound(s).",
            getattr(destroyed_model, "name", "Model"),
            int(restored_wounds),
        )
        return True

    def _use_awakened_dynasty_hungry_void(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PROTOCOL OF THE HUNGRY VOID: no target unit provided")
            return False
        root = self._necrons_root(unit)
        if root is None or not self._is_awakened_dynasty():
            return False
        if str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower() != "fight phase":
            logger.error("ERROR: PROTOCOL OF THE HUNGRY VOID: wrong phase")
            return False
        candidates = candidates or self._awakened_dynasty_candidates(require_not_fought=True)
        if not self._awakened_dynasty_unit_eligible(root, require_not_fought=True):
            logger.error("ERROR: PROTOCOL OF THE HUNGRY VOID: target unit is not currently eligible")
            return False
        if not self._awakened_dynasty_unit_in_candidates(root, candidates):
            logger.error("ERROR: PROTOCOL OF THE HUNGRY VOID: target unit is not a valid candidate")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Fight phase"):
            logger.error("ERROR: PROTOCOL OF THE HUNGRY VOID: cannot be used in current state")
            return False
        if not self._necrons_spend_cp(stratagem, target_unit=root):
            return False
        led = self._awakened_dynasty_unit_has_character_leading(root)
        for model in self._necrons_iter_unit_models(root):
            if not bool(getattr(model, "is_alive", True)):
                continue
            effects = getattr(model, "_temporary_effects", None)
            if not isinstance(effects, dict):
                effects = {}
                model._temporary_effects = effects
            entry = {
                "expires_phase": "FIGHT_PHASE",
                "melee_strength_bonus": 1,
                "melee_strength_bonus_source": str(getattr(stratagem, "name", "") or "PROTOCOL OF THE HUNGRY VOID").strip(),
            }
            if led:
                entry["melee_ap_bonus"] = 1
            effects["awakened_dynasty_hungry_void"] = entry
        self._necrons_finalize_stratagem_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PROTOCOL OF THE HUNGRY VOID: %s gains melee Strength%s this phase.",
            getattr(root, "name", "Unit"),
            " and AP" if led else "",
        )
        return True

    def _use_awakened_dynasty_sudden_storm(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PROTOCOL OF THE SUDDEN STORM: no target unit provided")
            return False
        root = self._necrons_root(unit)
        if root is None or not self._is_awakened_dynasty():
            return False
        if str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower() != "movement phase":
            logger.error("ERROR: PROTOCOL OF THE SUDDEN STORM: wrong phase")
            return False
        if getattr(self.game, "get_current_player", lambda: None)() is not self.player:
            logger.error("ERROR: PROTOCOL OF THE SUDDEN STORM: not your turn")
            return False
        candidates = candidates or self._awakened_dynasty_candidates()
        if not self._awakened_dynasty_unit_eligible(root):
            logger.error("ERROR: PROTOCOL OF THE SUDDEN STORM: target unit is not currently eligible")
            return False
        if not self._awakened_dynasty_unit_in_candidates(root, candidates):
            logger.error("ERROR: PROTOCOL OF THE SUDDEN STORM: target unit is not a valid candidate")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Movement phase"):
            logger.error("ERROR: PROTOCOL OF THE SUDDEN STORM: cannot be used in current state")
            return False
        if not self._necrons_spend_cp(stratagem, target_unit=root):
            return False
        for model in self._necrons_iter_unit_models(root):
            if not bool(getattr(model, "is_alive", True)):
                continue
            set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
            if not callable(set_keywords):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                set_keywords(
                    key="awakened_dynasty_sudden_storm_assault",
                    weapon_name=weapon_name,
                    keywords=["ASSAULT"],
                    source=str(getattr(stratagem, "name", "") or "PROTOCOL OF THE SUDDEN STORM").strip(),
                    expires_phase="SHOOTING_PHASE",
                    attack_type="ranged",
                )
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["awakened_dynasty_sudden_storm_assault_active"] = True
        sr["awakened_dynasty_sudden_storm_assault_expires_phase"] = "SHOOTING_PHASE"
        sr["awakened_dynasty_sudden_storm_assault_turn"] = int(self._necrons_current_turn())
        sr["awakened_dynasty_sudden_storm_assault_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["awakened_dynasty_sudden_storm_assault_source"] = str(getattr(stratagem, "name", "") or "").strip()
        if self._awakened_dynasty_unit_has_character_leading(root):
            sr["awakened_dynasty_sudden_storm_reroll_advance_active"] = True
            sr["awakened_dynasty_sudden_storm_reroll_advance_expires_phase"] = "MOVEMENT_PHASE"
            sr["awakened_dynasty_sudden_storm_reroll_advance_turn"] = int(self._necrons_current_turn())
            sr["awakened_dynasty_sudden_storm_reroll_advance_turn_owner"] = str(getattr(self.player, "id", "") or "")
            sr["awakened_dynasty_sudden_storm_reroll_advance_source"] = str(getattr(stratagem, "name", "") or "").strip()
        root.special_rules = sr
        self._necrons_finalize_stratagem_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PROTOCOL OF THE SUDDEN STORM: %s gains Assault on ranged weapons this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_awakened_dynasty_undying_legions(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._awakened_dynasty_find_pending_reaction(
            "PROTOCOL OF THE UNDYING LEGIONS",
            unit=unit,
        )
        if isinstance(pending, dict) and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PROTOCOL OF THE UNDYING LEGIONS: no target unit provided")
            return False
        root = self._necrons_root(unit)
        if root is None or not self._is_awakened_dynasty():
            return False
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if isinstance(pending, dict) else "")
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: PROTOCOL OF THE UNDYING LEGIONS: wrong phase")
            return False
        if phase_name == "shooting phase" and getattr(self.game, "get_current_player", lambda: None)() is self.player:
            logger.error("ERROR: PROTOCOL OF THE UNDYING LEGIONS: not opponent's Shooting phase")
            return False
        candidates = candidates or self._awakened_dynasty_candidates(require_reanimation=True)
        if not self._awakened_dynasty_unit_eligible(root, require_reanimation=True):
            logger.error("ERROR: PROTOCOL OF THE UNDYING LEGIONS: target unit is not currently eligible")
            return False
        if not self._awakened_dynasty_unit_in_candidates(root, candidates):
            logger.error("ERROR: PROTOCOL OF THE UNDYING LEGIONS: target unit is not a valid candidate")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            target_unit=root,
            phase_name=phase_label,
            attacker_unit=pending.get("attacker_unit") if isinstance(pending, dict) else None,
            candidates=list(candidates),
        ):
            logger.error("ERROR: PROTOCOL OF THE UNDYING LEGIONS: cannot be used in current state")
            return False
        if not self._necrons_spend_cp(stratagem, target_unit=root):
            return False
        snapshot = pending.get("reanimation_bonus_by_unit_id") if isinstance(pending, dict) else None
        bonus = self._awakened_dynasty_undying_legions_reanimation_bonus(root=root, snapshot=snapshot)
        roll = int(dice_module.get_roll("D3") or 0)
        total_wounds = int(roll) + int(bonus)
        if total_wounds > 0:
            game_map = getattr(self.game, "map", None)
            provider = getattr(game_map, "reanimation_allocation_provider", None) if game_map is not None else None
            is_human = bool(getattr(self.player, "has_control", lambda: False)())
            root.apply_reanimation_protocols(
                total_wounds,
                game_map=game_map,
                is_human=is_human,
                provider=provider,
                roll_expr="D3",
            )
        self._necrons_finalize_stratagem_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PROTOCOL OF THE UNDYING LEGIONS: %s reanimates %d wound(s) (%d + %d).",
            getattr(root, "name", "Unit"),
            int(total_wounds),
            int(roll),
            int(bonus),
        )
        return True

    def _use_awakened_dynasty_vengeful_stars(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._awakened_dynasty_find_pending_reaction(
            "PROTOCOL OF THE VENGEFUL STARS",
            unit=unit,
        )
        if isinstance(pending, dict):
            if enemy_unit is None:
                enemy_unit = pending.get("enemy_unit") or pending.get("attacker_unit")
            if not candidates:
                candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PROTOCOL OF THE VENGEFUL STARS: no target unit provided")
            return False
        root = self._necrons_root(unit)
        enemy_root = self._necrons_root(enemy_unit)
        if root is None or enemy_root is None or not self._is_awakened_dynasty():
            return False
        if str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower() != "shooting phase":
            logger.error("ERROR: PROTOCOL OF THE VENGEFUL STARS: wrong phase")
            return False
        if getattr(self.game, "get_current_player", lambda: None)() is self.player:
            logger.error("ERROR: PROTOCOL OF THE VENGEFUL STARS: not opponent's Shooting phase")
            return False
        candidates = candidates or self._awakened_dynasty_candidates(require_character_unit=True)
        if not self._awakened_dynasty_unit_eligible(root, require_character_unit=True):
            logger.error("ERROR: PROTOCOL OF THE VENGEFUL STARS: target unit is not currently eligible")
            return False
        if not self._awakened_dynasty_unit_in_candidates(root, candidates):
            logger.error("ERROR: PROTOCOL OF THE VENGEFUL STARS: target unit is not a valid candidate")
            return False
        reactive_can_shoot = getattr(self.game, "_setup_reactive_can_shoot_target", None)
        if callable(reactive_can_shoot) and not bool(reactive_can_shoot(root, enemy_root)):
            logger.error("ERROR: PROTOCOL OF THE VENGEFUL STARS: attacking unit is not an eligible reactive shooting target")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            target_unit=root,
            attacker_unit=enemy_root,
            phase_name="Shooting phase",
            candidates=list(candidates),
        ):
            logger.error("ERROR: PROTOCOL OF THE VENGEFUL STARS: cannot be used in current state")
            return False
        if not self._necrons_spend_cp(stratagem, target_unit=root):
            return False
        queue_shoot = getattr(self.game, "_queue_setup_reactive_shooting_decision", None)
        if not callable(queue_shoot):
            logger.error("ERROR: PROTOCOL OF THE VENGEFUL STARS: reactive shooting helper is unavailable")
            return False
        request = queue_shoot(
            player=self.player,
            unit=root,
            target_unit=enemy_root,
            source=str(getattr(stratagem, "name", "") or "PROTOCOL OF THE VENGEFUL STARS").strip(),
        )
        if request is None:
            logger.error("ERROR: PROTOCOL OF THE VENGEFUL STARS: failed to queue reactive shooting")
            return False
        self._necrons_finalize_stratagem_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PROTOCOL OF THE VENGEFUL STARS: %s can shoot at %s.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "enemy unit"),
        )
        return True

    def _queue_annihilation_legion_reactive_move(
        self,
        *,
        stratagem: Any,
        unit: Any,
        enemy_unit: Any,
        reactive_kind: str,
    ) -> bool:
        if self.game is None:
            return False
        root = self._necrons_root(unit)
        enemy_root = self._necrons_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        move_max = max(0, int(getattr(root, "movement", 0) or 0))
        request = self.game._queue_reactive_move_movement_decision(
            player=self.player,
            unit=root,
            max_distance=move_max,
            kind=str(reactive_kind or "annihilation_legion_reactive_move"),
            movement_type="reactive",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or "Annihilation Legion"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            allow_engagement_range=False,
            extra_context={
                "annihilation_legion_target_unit_id": str(get_entity_id(enemy_root) or ""),
                "annihilation_legion_target_unit_name": str(getattr(enemy_root, "name", "") or "enemy unit"),
            },
        )
        if request is None:
            logger.error(
                "ERROR: %s: failed to queue reactive Normal move for %s",
                getattr(stratagem, "name", "Annihilation Legion"),
                getattr(root, "name", "Unit"),
            )
            return False
        return True

    def _use_annihilation_legion_blood_fuelled_cruelty(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("moving_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._annihilation_legion_find_pending_reaction("BLOOD-FUELLED CRUELTY", unit=unit)
        if isinstance(pending, dict):
            if enemy_unit is None:
                enemy_unit = pending.get("enemy_unit") or pending.get("moving_unit")
            if not candidates:
                candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BLOOD-FUELLED CRUELTY: no target unit provided")
            return False

        root = self._necrons_root(unit)
        enemy_root = self._necrons_root(enemy_unit)
        if root is None or enemy_root is None or not self._is_annihilation_legion():
            return False
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if isinstance(pending, dict) else "")
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: BLOOD-FUELLED CRUELTY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: BLOOD-FUELLED CRUELTY: not opponent's Movement phase")
            return False
        if not self._annihilation_legion_unit_eligible(root):
            logger.error("ERROR: BLOOD-FUELLED CRUELTY: target is not an eligible Annihilation Legion unit")
            return False
        if not self._annihilation_legion_unit_in_candidates(
            root,
            candidates or self._annihilation_legion_start_phase_engaged_candidates_for_enemy(enemy_root),
        ):
            logger.error("ERROR: BLOOD-FUELLED CRUELTY: target unit did not start the phase engaged with the enemy unit")
            return False
        if not self._annihilation_legion_was_engaged_with_enemy_at_movement_phase_start(root, enemy_root):
            logger.error("ERROR: BLOOD-FUELLED CRUELTY: target unit was not engaged with the enemy unit at phase start")
            return False
        if self._necrons_owned_by_player(enemy_root):
            logger.error("ERROR: BLOOD-FUELLED CRUELTY: trigger unit must be enemy")
            return False
        if self._annihilation_legion_is_engaged(root):
            logger.error("ERROR: BLOOD-FUELLED CRUELTY: target unit is still within Engagement Range")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            moving_unit=enemy_root,
            phase_name="Movement phase",
        ):
            logger.error("ERROR: BLOOD-FUELLED CRUELTY: cannot be used in current state")
            return False
        if not self._necrons_spend_cp(stratagem, target_unit=root):
            return False

        roll = int(dice_module.get_roll("D6") or 0)
        mortal_wounds = 0
        if roll == 6:
            mortal_wounds = 3
        elif roll >= 2:
            mortal_wounds = int(dice_module.get_roll("D3") or 0)
        if mortal_wounds > 0:
            root._apply_mortal_wounds_to_unit(enemy_root, int(mortal_wounds), game_map=getattr(self.game, "map", None))
        if not self._queue_annihilation_legion_reactive_move(
            stratagem=stratagem,
            unit=root,
            enemy_unit=enemy_root,
            reactive_kind="annihilation_blood_fuelled_cruelty",
        ):
            return False

        self._necrons_finalize_stratagem_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BLOOD-FUELLED CRUELTY: %s can make a Normal move toward %s after inflicting %d mortal wounds.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "enemy unit"),
            int(mortal_wounds),
        )
        return True

    def _use_annihilation_legion_insanitys_ire(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._annihilation_legion_find_pending_reaction("INSANITY'S IRE", unit=unit)
        if isinstance(pending, dict):
            if enemy_unit is None:
                enemy_unit = pending.get("enemy_unit") or pending.get("attacker_unit")
            if not candidates:
                candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: INSANITY'S IRE: no target unit provided")
            return False

        root = self._necrons_root(unit)
        enemy_root = self._necrons_root(enemy_unit)
        if root is None or enemy_root is None or not self._is_annihilation_legion():
            return False
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if isinstance(pending, dict) else "")
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: INSANITY'S IRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: INSANITY'S IRE: not opponent's Shooting phase")
            return False
        if not self._annihilation_legion_unit_eligible(root):
            logger.error("ERROR: INSANITY'S IRE: target is not an eligible Annihilation Legion unit")
            return False
        if not self._annihilation_legion_unit_in_candidates(root, candidates):
            logger.error("ERROR: INSANITY'S IRE: target unit did not lose models to the triggering attacker")
            return False
        if self._necrons_owned_by_player(enemy_root):
            logger.error("ERROR: INSANITY'S IRE: attacking unit must be enemy")
            return False
        if self._annihilation_legion_is_engaged(root):
            logger.error("ERROR: INSANITY'S IRE: target unit is within Engagement Range")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            attacker_unit=enemy_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: INSANITY'S IRE: cannot be used in current state")
            return False
        if not self._necrons_spend_cp(stratagem, target_unit=root):
            return False
        if not self._queue_annihilation_legion_reactive_move(
            stratagem=stratagem,
            unit=root,
            enemy_unit=enemy_root,
            reactive_kind="annihilation_insanitys_ire",
        ):
            return False

        self._necrons_finalize_stratagem_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INSANITY'S IRE: %s can make a Normal move toward %s.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "enemy unit"),
        )
        return True

    def _use_annihilation_legion_murderous_reanimation(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = self._annihilation_legion_find_pending_reaction("MURDEROUS REANIMATION", unit=unit)
        if isinstance(pending, dict) and not candidates:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MURDEROUS REANIMATION: no target unit provided")
            return False
        root = self._necrons_root(unit)
        if root is None or not self._is_annihilation_legion():
            return False
        phase_name = str(
            kwargs.get("phase_name")
            or (pending.get("phase_name") if isinstance(pending, dict) else "")
            or self._current_phase_name
            or ""
        ).strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: MURDEROUS REANIMATION: wrong phase")
            return False
        if not self._annihilation_legion_unit_eligible(root, require_reanimation=True):
            logger.error("ERROR: MURDEROUS REANIMATION: target is not an eligible Annihilation Legion unit")
            return False
        if not self._annihilation_legion_unit_in_candidates(root, candidates):
            logger.error("ERROR: MURDEROUS REANIMATION: target unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: MURDEROUS REANIMATION: cannot be used in current state")
            return False
        if not self._necrons_spend_cp(stratagem, target_unit=root):
            return False
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            logger.error("ERROR: MURDEROUS REANIMATION: no map context")
            return False
        roll = int(dice_module.get_roll("D3") or 0)
        if roll > 0:
            provider = getattr(game_map, "reanimation_allocation_provider", None)
            is_human = bool(getattr(self.player, "has_control", lambda: False)())
            root.apply_reanimation_protocols(
                roll,
                game_map=game_map,
                is_human=is_human,
                provider=provider,
                roll_expr="D3",
            )
        self._necrons_finalize_stratagem_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MURDEROUS REANIMATION: %s reanimates after destroying or maiming its foe (rolled %d).",
            getattr(root, "name", "Unit"),
            int(roll),
        )
        return True

    def _use_annihilation_legion_pitiless_hunters(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PITILESS HUNTERS: no target unit provided")
            return False
        root = self._necrons_root(unit)
        if root is None or not self._is_annihilation_legion():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: PITILESS HUNTERS: wrong phase")
            return False
        if not self._annihilation_legion_unit_eligible(root, require_not_fought=True):
            logger.error("ERROR: PITILESS HUNTERS: target must be an eligible unit that has not fought this phase")
            return False
        if candidates and not self._annihilation_legion_unit_in_candidates(root, candidates):
            logger.error("ERROR: PITILESS HUNTERS: target unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: PITILESS HUNTERS: cannot be used in current state")
            return False
        if not self._necrons_spend_cp(stratagem, target_unit=root):
            return False
        special_rules = dict(getattr(root, "special_rules", None) or {})
        special_rules["stratagem_pile_in_distance_override"] = 6.0
        special_rules["stratagem_pile_in_expires_phase"] = "FIGHT_PHASE"
        special_rules["stratagem_pile_in_source"] = str(getattr(stratagem, "name", "") or "PITILESS HUNTERS")
        special_rules["stratagem_consolidate_distance_override"] = 6.0
        special_rules["stratagem_consolidate_expires_phase"] = "FIGHT_PHASE"
        special_rules["stratagem_consolidate_source"] = str(getattr(stratagem, "name", "") or "PITILESS HUNTERS")
        root.special_rules = special_rules
        self._necrons_finalize_stratagem_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PITILESS HUNTERS: %s can Pile-in and Consolidate up to 6\" this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_annihilation_legion_spoor_of_frailty(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: THE SPOOR OF FRAILTY: no target unit provided")
            return False
        root = self._necrons_root(unit)
        if root is None or not self._is_annihilation_legion():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: THE SPOOR OF FRAILTY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: THE SPOOR OF FRAILTY: only usable in your Shooting phase")
            return False
        require_not_shot = phase_name == "shooting phase"
        require_not_fought = phase_name == "fight phase"
        if not self._annihilation_legion_unit_eligible(
            root,
            require_not_shot=require_not_shot,
            require_not_fought=require_not_fought,
        ):
            logger.error("ERROR: THE SPOOR OF FRAILTY: target must be an eligible unit that has not acted this phase")
            return False
        if candidates and not self._annihilation_legion_unit_in_candidates(root, candidates):
            logger.error("ERROR: THE SPOOR OF FRAILTY: target unit is not currently eligible")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
            logger.error("ERROR: THE SPOOR OF FRAILTY: cannot be used in current state")
            return False
        if not self._necrons_spend_cp(stratagem, target_unit=root):
            return False
        special_rules = dict(getattr(root, "special_rules", None) or {})
        special_rules["annihilation_spoor_of_frailty_active"] = True
        special_rules["annihilation_spoor_of_frailty_owner"] = str(getattr(self.player, "id", "") or "")
        special_rules["annihilation_spoor_of_frailty_turn"] = int(self._necrons_current_turn())
        special_rules["annihilation_spoor_of_frailty_expires_phase"] = (
            "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        )
        special_rules["annihilation_spoor_of_frailty_source"] = str(getattr(stratagem, "name", "") or "THE SPOOR OF FRAILTY")
        root.special_rules = special_rules
        self._necrons_finalize_stratagem_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: THE SPOOR OF FRAILTY: %s gains offensive bonuses against damaged targets this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _resolve_awakened_dynasty_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_awakened_dynasty() or self.game is None:
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        pending_returns = self._awakened_dynasty_eternal_revenant_pending_returns()
        if not pending_returns:
            return
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return
        remaining: list[dict[str, Any]] = []
        for entry in list(pending_returns):
            if str(entry.get("phase", "") or "").strip().upper() != phase_name:
                remaining.append(entry)
                continue
            model = entry.get("model")
            return_unit = entry.get("unit") or getattr(model, "parent_unit", None)
            anchor_pos = entry.get("anchor_pos")
            if model is None or return_unit is None or anchor_pos is None:
                continue
            parent_bodyguard = getattr(return_unit, "attached_to", None)
            if parent_bodyguard is not None:
                parent_bodyguard.attached_leaders = [
                    leader
                    for leader in list(getattr(parent_bodyguard, "attached_leaders", []) or [])
                    if leader is not return_unit
                ]
                return_unit.attached_to = None
            try:
                restored_wounds = int(entry.get("wounds", 1) or 1)
            except (TypeError, ValueError):
                restored_wounds = 1
            model.wounds = int(restored_wounds)
            model._wounds = int(restored_wounds)
            models_lost = list(getattr(return_unit, "models_lost", []) or [])
            if model in models_lost:
                models_lost.remove(model)
                return_unit.models_lost = models_lost
            if model not in list(getattr(return_unit, "models", []) or []):
                return_unit.models.append(model)
            return_unit.deployed = True
            return_unit.reserve_status = "deployed"
            return_unit.embarked_in = None
            placement = self.game._find_closest_valid_reposition_position(
                return_unit,
                anchor_pos,
                game_map=game_map,
            )
            if placement is None:
                placement = anchor_pos
            model.set_location(float(placement[0]), float(placement[1]), float(placement[2]), 0.0)
            if return_unit not in list(getattr(game_map, "units", []) or []):
                placed = game_map.place_unit(return_unit)
                if not placed:
                    logger.error(
                        "ERROR: PROTOCOL OF THE ETERNAL REVENANT: failed to place %s at phase end",
                        getattr(return_unit, "name", "Unit"),
                    )
                    continue
            logger.info(
                "INFO: PROTOCOL OF THE ETERNAL REVENANT: returned %s with %d wound(s).",
                getattr(model, "name", "Model"),
                int(restored_wounds),
            )
        pending_returns[:] = remaining

    def _cleanup_awakened_dynasty_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_awakened_dynasty():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        army = self.player.get_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        seen: set[str] = set()
        for unit in units:
            root = self._necrons_root(unit)
            root_id = str(get_entity_id(root) or "") if root is not None else ""
            if not root_id or root_id in seen:
                continue
            seen.add(root_id)
            special_rules = getattr(root, "special_rules", None)
            if isinstance(special_rules, dict):
                cleanup_keys = (
                    "awakened_dynasty_conquering_tyrant",
                    "awakened_dynasty_sudden_storm_assault",
                    "awakened_dynasty_sudden_storm_reroll_advance",
                )
                for key_base in cleanup_keys:
                    expires_phase = str(special_rules.get(f"{key_base}_expires_phase", "") or "").strip().upper()
                    if not bool(special_rules.get(f"{key_base}_active")):
                        continue
                    if expires_phase and expires_phase != phase_name:
                        continue
                    for key in list(special_rules.keys()):
                        if key.startswith(f"{key_base}_"):
                            special_rules.pop(key, None)
                root.special_rules = special_rules
            if phase_name in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                for model in self._necrons_iter_unit_models(root):
                    effects = getattr(model, "_temporary_effects", None)
                    if not isinstance(effects, dict):
                        continue
                    if phase_name == "FIGHT_PHASE":
                        effects.pop("awakened_dynasty_hungry_void", None)
                    if phase_name == "SHOOTING_PHASE":
                        effects.pop("awakened_dynasty_sudden_storm_assault", None)

    def _cleanup_annihilation_legion_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_annihilation_legion():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        army = self.player.get_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        seen: set[str] = set()
        for unit in units:
            root = self._necrons_root(unit)
            root_id = str(get_entity_id(root) or "") if root is not None else ""
            if not root_id or root_id in seen:
                continue
            seen.add(root_id)
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            expires_phase = str(special_rules.get("annihilation_spoor_of_frailty_expires_phase", "") or "").strip().upper()
            if special_rules.get("annihilation_spoor_of_frailty_active") and (not expires_phase or expires_phase == phase_name):
                for key in (
                    "annihilation_spoor_of_frailty_active",
                    "annihilation_spoor_of_frailty_owner",
                    "annihilation_spoor_of_frailty_turn",
                    "annihilation_spoor_of_frailty_expires_phase",
                    "annihilation_spoor_of_frailty_source",
                ):
                    special_rules.pop(key, None)
                root.special_rules = special_rules

    def _use_necrons_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "PROTOCOL OF THE CONQUERING TYRANT" and self._is_awakened_dynasty():
            return self._use_awakened_dynasty_conquering_tyrant(stratagem, **kwargs)
        if name_u == "PROTOCOL OF THE ETERNAL REVENANT" and self._is_awakened_dynasty():
            return self._use_awakened_dynasty_eternal_revenant(stratagem, **kwargs)
        if name_u == "PROTOCOL OF THE HUNGRY VOID" and self._is_awakened_dynasty():
            return self._use_awakened_dynasty_hungry_void(stratagem, **kwargs)
        if name_u == "PROTOCOL OF THE SUDDEN STORM" and self._is_awakened_dynasty():
            return self._use_awakened_dynasty_sudden_storm(stratagem, **kwargs)
        if name_u == "PROTOCOL OF THE UNDYING LEGIONS" and self._is_awakened_dynasty():
            return self._use_awakened_dynasty_undying_legions(stratagem, **kwargs)
        if name_u == "PROTOCOL OF THE VENGEFUL STARS" and self._is_awakened_dynasty():
            return self._use_awakened_dynasty_vengeful_stars(stratagem, **kwargs)
        if name_u == "BLOOD-FUELLED CRUELTY" and self._is_annihilation_legion():
            return self._use_annihilation_legion_blood_fuelled_cruelty(stratagem, **kwargs)
        if name_u in {"INSANITY'S IRE", "INSANITY’S IRE"} and self._is_annihilation_legion():
            return self._use_annihilation_legion_insanitys_ire(stratagem, **kwargs)
        if name_u == "MURDEROUS REANIMATION" and self._is_annihilation_legion():
            return self._use_annihilation_legion_murderous_reanimation(stratagem, **kwargs)
        if name_u == "PITILESS HUNTERS" and self._is_annihilation_legion():
            return self._use_annihilation_legion_pitiless_hunters(stratagem, **kwargs)
        if name_u == "THE SPOOR OF FRAILTY" and self._is_annihilation_legion():
            return self._use_annihilation_legion_spoor_of_frailty(stratagem, **kwargs)
        return None

    def _starshatter_candidates(
        self,
        *,
        require_vehicle_or_mounted: bool = False,
        require_not_moved: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        exclude_monster: bool = False,
    ) -> List[Any]:
        if not self._is_starshatter_arsenal():
            return []
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return []
        army = self.player.get_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        candidates: List[Any] = []
        seen = set()
        for unit in units:
            if unit is None:
                continue
            root = unit.get_attached_unit_root()
            if root is None:
                continue
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            if not root.is_alive():
                continue
            if not getattr(root, "deployed", False):
                continue
            if getattr(root, "is_in_reserves", lambda: False)():
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not mgr.unit_is_necrons(root):
                continue
            if exclude_monster and mgr.unit_is_monster(root):
                continue
            if mgr.unit_is_titanic(root):
                continue
            if require_vehicle_or_mounted and not mgr.unit_is_vehicle_or_mounted(root):
                continue
            if require_not_moved and bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            candidates.append(root)
        return candidates

    def _starshatter_merciless_reclamation_candidates(self, phase_name: str | None = None) -> List[Any]:
        phase_key = str(phase_name or "").strip().lower()
        require_not_shot = "shooting" in phase_key
        require_not_fought = "fight" in phase_key
        return self._starshatter_candidates(
            require_vehicle_or_mounted=False,
            require_not_shot=require_not_shot,
            require_not_fought=require_not_fought,
            exclude_monster=True,
        )

    def _starshatter_dimensional_tunnel_candidates(self) -> List[Any]:
        return self._starshatter_candidates(require_vehicle_or_mounted=True)

    def _starshatter_chronoshift_candidates(self) -> List[Any]:
        return self._starshatter_candidates(require_vehicle_or_mounted=True, require_not_moved=True)

    def _unit_arrives_via_hyperphasing_this_phase(self, unit: Any) -> bool:
        if unit is None or self.game is None:
            return False
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("hyperphasing_arrival_pending", False)):
            return False
        owner_id = str(sr.get("hyperphasing_arrival_turn_owner", "") or "")
        if owner_id and owner_id != str(getattr(self.player, "id", "") or ""):
            return False
        try:
            current_player = getattr(self.game, "get_current_player", lambda: None)()
            current_player_id = str(getattr(current_player, "id", "") or "")
        except Exception:
            current_player_id = ""
        if current_player_id and current_player_id != str(getattr(self.player, "id", "") or ""):
            return False
        try:
            in_reserves = bool(getattr(root, "is_in_reserves", lambda: False)())
        except Exception:
            in_reserves = False
        return bool(in_reserves)

    def _hypercrypt_cosmic_precision_candidates(self) -> List[Any]:
        if not self._is_hypercrypt_legion():
            return []
        mgr = self._get_necrons_mgr()
        if mgr is None:
            return []
        army = self.player.get_army()
        units = list(getattr(army, "units", []) or []) if army is not None else []
        candidates: List[Any] = []
        seen = set()
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        for unit in units:
            if unit is None:
                continue
            root = unit.get_attached_unit_root()
            if root is None:
                continue
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            if not root.is_alive():
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not mgr.unit_is_necrons(root):
                continue
            has_any_keyword = getattr(root, "has_any_keyword", None)
            if callable(has_any_keyword) and bool(has_any_keyword("MONSTER")):
                continue
            if not bool(getattr(root, "is_in_reserves", lambda: False)()):
                continue
            if not bool(getattr(root, "can_arrive_from_reserves", lambda _t: False)(current_turn)):
                continue
            arrives_via_hyperphasing = self._unit_arrives_via_hyperphasing_this_phase(root)
            has_deep_strike = bool(getattr(root, "has_deep_strike", lambda: False)())
            if not arrives_via_hyperphasing and not has_deep_strike:
                continue
            candidates.append(root)
        candidates.sort(key=lambda u: str(get_entity_id(u) or ""))
        return candidates
