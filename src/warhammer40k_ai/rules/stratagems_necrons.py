from __future__ import annotations

import logging
from typing import Any, List, Optional

from ..utility import dice as dice_module
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
