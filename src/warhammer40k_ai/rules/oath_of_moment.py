from __future__ import annotations

from typing import Optional

from ..utility.ability_support import ABILITY_OATH_OF_MOMENT, army_has_ability_id
from ..utility.entity_ids import get_entity_id


class OathOfMomentManager:
    """
    Space Marines army rule: Oath of Moment.

    Each Command phase, select one enemy unit as the Oath target until your next Command phase.
    """

    def __init__(self, army=None):
        self.army = army
        self.oathOfMomentTargetUnitId: Optional[str] = None
        self.oathOfMomentTargetName: Optional[str] = None
        self.oathOfMomentSecondaryTargetUnitId: Optional[str] = None
        self.oathOfMomentSecondaryTargetName: Optional[str] = None
        self.extremisLevelThreatActive: bool = False
        self.extremisLevelThreatUsed: bool = False
        self.recalculatingUsedBattleRound: int = 0
        self.tomeOfEctocladesUsed: bool = False
        if self.army is not None:
            try:
                setattr(self.army, "oathOfMomentTargetUnitId", None)
                setattr(self.army, "oathOfMomentTargetName", None)
                setattr(self.army, "oathOfMomentSecondaryTargetUnitId", None)
                setattr(self.army, "oathOfMomentSecondaryTargetName", None)
                setattr(self.army, "extremisLevelThreatActive", False)
                setattr(self.army, "extremisLevelThreatUsed", False)
                setattr(self.army, "recalculatingUsedBattleRound", 0)
                setattr(self.army, "tomeOfEctocladesUsed", False)
            except Exception:
                pass

    def army_has_oath(self) -> bool:
        return self._army_has_oath()

    def _army_has_oath(self) -> bool:
        if self.army is None:
            return False
        try:
            mgr = getattr(self.army, "templar_vows", None)
            if mgr is not None and getattr(mgr, "_army_has_vows", lambda: False)():
                return False
        except Exception:
            pass
        if not army_has_ability_id(self.army, ABILITY_OATH_OF_MOMENT):
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "SM":
            return False
        # Fallback: if faction id is missing, require at least one ADEPTUS ASTARTES unit.
        if not faction_id:
            try:
                for unit in list(getattr(self.army, "units", []) or []):
                    if self._unit_is_adeptus_astartes(unit):
                        return True
            except Exception:
                return False
            return False
        return True

    def _unit_is_adeptus_astartes(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("ADEPTUS ASTARTES")
        except Exception:
            return False

    def _army_is_codex_detachment(self) -> bool:
        if self.army is None:
            return False
        mgr = getattr(self.army, "space_marines_detachments", None)
        if mgr is not None:
            try:
                return bool(mgr.is_codex_detachment())
            except Exception:
                return False
        return False

    def _army_has_divergent_chapter_keywords(self) -> bool:
        if self.army is None:
            return False
        mgr = getattr(self.army, "space_marines_detachments", None)
        if mgr is not None:
            try:
                return bool(mgr.has_divergent_chapter_keywords())
            except Exception:
                return False
        return False

    def _army_is_1st_company_task_force(self) -> bool:
        if self.army is None:
            return False
        mgr = getattr(self.army, "space_marines_detachments", None)
        if mgr is None:
            return False
        check = getattr(mgr, "is_1st_company_task_force", None)
        if not callable(check):
            return False
        return bool(check())

    def _army_is_hammer_of_avernii(self) -> bool:
        if self.army is None:
            return False
        mgr = getattr(self.army, "space_marines_detachments", None)
        if mgr is None:
            return False
        check = getattr(mgr, "is_hammer_of_avernii", None)
        if not callable(check):
            return False
        return bool(check())

    def _army_is_emperors_shield(self) -> bool:
        if self.army is None:
            return False
        mgr = getattr(self.army, "space_marines_detachments", None)
        if mgr is None:
            return False
        check = getattr(mgr, "is_emperors_shield", None)
        if not callable(check):
            return False
        return bool(check())

    def _unit_contains_name(self, unit, name_fragment: str) -> bool:
        if unit is None:
            return False
        target = str(name_fragment or "").strip().upper()
        if not target:
            return False
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None:
            return False
        members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else [root]
        if not members:
            members = [root]
        for member in members:
            if member is None:
                continue
            member_name = str(getattr(member, "name", "") or "").strip().upper()
            if target in member_name:
                return True
            for model in list(getattr(member, "models", []) or []):
                model_name = str(getattr(model, "name", "") or "").strip().upper()
                if target in model_name:
                    return True
        return False

    def _recalculating_source_units(self) -> list:
        army = self.army
        if army is None:
            return []
        matched = []
        seen = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            if root is None:
                continue
            root_id = str(getattr(root, "_id", "") or "")
            if root_id and root_id in seen:
                continue
            reserve_status = str(getattr(root, "reserve_status", "") or "").strip().lower()
            if reserve_status in {"reserves", "strategic_reserves"}:
                continue
            alive_fn = getattr(root, "is_alive", None)
            if callable(alive_fn) and not bool(alive_fn()):
                continue
            root_name = str(getattr(root, "name", "") or "").strip().upper()
            is_match = "CAANOK VAR" in root_name
            if not is_match:
                models = list(getattr(root, "models", []) or [])
                for model in models:
                    model_name = str(getattr(model, "name", "") or "").strip().upper()
                    if "CAANOK VAR" in model_name:
                        is_match = True
                        break
            if not is_match:
                continue
            if root_id:
                seen.add(root_id)
            matched.append(root)
        return matched

    def _army_has_caanok_var_on_battlefield(self) -> bool:
        return bool(self._recalculating_source_units())

    def wound_bonus_enabled(self) -> bool:
        if not self._army_has_oath():
            return False
        if not self._army_is_codex_detachment():
            return False
        if self._army_has_divergent_chapter_keywords():
            return False
        return True

    def clear_target(self) -> None:
        self.oathOfMomentTargetUnitId = None
        self.oathOfMomentTargetName = None
        if self.army is not None:
            try:
                setattr(self.army, "oathOfMomentTargetUnitId", None)
                setattr(self.army, "oathOfMomentTargetName", None)
            except Exception:
                pass

    def clear_secondary_target(self) -> None:
        self.oathOfMomentSecondaryTargetUnitId = None
        self.oathOfMomentSecondaryTargetName = None
        if self.army is not None:
            try:
                setattr(self.army, "oathOfMomentSecondaryTargetUnitId", None)
                setattr(self.army, "oathOfMomentSecondaryTargetName", None)
            except Exception:
                pass

    def clear_extremis_level_threat(self) -> None:
        self.extremisLevelThreatActive = False
        if self.army is not None:
            try:
                setattr(self.army, "extremisLevelThreatActive", False)
            except Exception:
                pass

    def _sync_extremis_level_threat_used(self) -> None:
        if self.army is not None:
            try:
                setattr(self.army, "extremisLevelThreatUsed", bool(self.extremisLevelThreatUsed))
            except Exception:
                pass

    def _sync_recalculating_used_battle_round(self) -> None:
        if self.army is not None:
            try:
                setattr(self.army, "recalculatingUsedBattleRound", int(self.recalculatingUsedBattleRound or 0))
            except Exception:
                pass

    def _sync_tome_of_ectoclades_used(self) -> None:
        if self.army is not None:
            try:
                setattr(self.army, "tomeOfEctocladesUsed", bool(self.tomeOfEctocladesUsed))
            except Exception:
                pass

    def mark_tome_of_ectoclades_used(self) -> None:
        self.tomeOfEctocladesUsed = True
        self._sync_tome_of_ectoclades_used()

    def can_activate_extremis_level_threat(self) -> bool:
        if not self._army_has_oath():
            return False
        if not self._army_is_1st_company_task_force():
            return False
        if bool(self.extremisLevelThreatUsed):
            return False
        return True

    def activate_extremis_level_threat(self, *, game=None, player=None) -> bool:
        if not self.can_activate_extremis_level_threat():
            return False
        if game is not None:
            try:
                phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
            except Exception:
                phase_name = ""
            if phase_name and phase_name != "COMMAND_PHASE":
                return False
            if player is not None:
                try:
                    if getattr(player, "get_army", lambda: None)() is not self.army:
                        return False
                except Exception:
                    return False
        self.extremisLevelThreatActive = True
        self.extremisLevelThreatUsed = True
        if self.army is not None:
            try:
                setattr(self.army, "extremisLevelThreatActive", True)
            except Exception:
                pass
        self._sync_extremis_level_threat_used()
        return True

    def extremis_level_threat_reroll_wound_applies(self, attacker_unit, target_unit) -> bool:
        if not bool(self.extremisLevelThreatActive):
            return False
        return self.can_reroll_hit(attacker_unit, target_unit)

    def calculated_annihilation_reroll_wound_ones_applies(self, attacker_unit, target_unit) -> bool:
        if not self._army_is_hammer_of_avernii():
            return False
        return self.can_reroll_hit(attacker_unit, target_unit)

    def wrath_of_dorn_reroll_wound_ones_applies(self, attacker_unit, target_unit) -> bool:
        if not self._army_is_emperors_shield():
            return False
        return self.can_reroll_hit(attacker_unit, target_unit)

    def wrath_of_dorn_reroll_wound_full_applies(self, attacker_unit, target_unit) -> bool:
        if not self._army_is_emperors_shield():
            return False
        if not self.can_reroll_hit(attacker_unit, target_unit):
            return False
        return self._unit_contains_name(attacker_unit, "DARNATH LYSANDER")

    def _current_battle_round(self, *, game=None) -> int:
        if game is not None:
            try:
                return int(getattr(game, "turn", 0) or 0)
            except Exception:
                return 0
        try:
            army_player = getattr(self.army, "player", None) if self.army is not None else None
            linked_game = getattr(army_player, "game", None)
            return int(getattr(linked_game, "turn", 0) or 0) if linked_game is not None else 0
        except Exception:
            return 0

    def _source_has_visibility_to_target(self, source_unit, target_unit, *, game=None) -> bool:
        if source_unit is None or target_unit is None:
            return False
        game_obj = game
        if game_obj is None:
            try:
                game_obj = getattr(getattr(source_unit.get_parent_army(), "player", None), "game", None)
            except Exception:
                game_obj = None
        game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        los_fn = getattr(source_unit, "_has_line_of_sight_to_target", None)
        if game_map is None or not callable(los_fn):
            return True
        try:
            models = list(source_unit.get_models_for_collision() or [])
        except Exception:
            models = list(getattr(source_unit, "models", []) or [])
        for model in models:
            if model is None or not getattr(model, "is_alive", True):
                continue
            try:
                if bool(los_fn(model, target_unit, game_map)):
                    return True
            except Exception:
                continue
        return False

    def _eligible_recalculating_targets(self, *, game=None, player=None) -> list:
        options = self._eligible_enemy_units(game=game, player=player)
        if not options:
            return []
        sources = self._recalculating_source_units()
        if not sources:
            return []
        visible = []
        for enemy in options:
            if any(self._source_has_visibility_to_target(source, enemy, game=game) for source in sources):
                visible.append(enemy)
        return visible

    def can_trigger_recalculating(self, destroyed_unit, *, game=None, player=None) -> bool:
        if not self._army_has_oath():
            return False
        if not self._army_is_hammer_of_avernii():
            return False
        if player is not None:
            try:
                if getattr(player, "get_army", lambda: None)() is not self.army:
                    return False
            except Exception:
                return False
        if not self._army_has_caanok_var_on_battlefield():
            return False
        if not self.is_oath_target(destroyed_unit):
            return False
        battle_round = self._current_battle_round(game=game)
        if battle_round > 0 and int(self.recalculatingUsedBattleRound or 0) == int(battle_round):
            return False
        return True

    def _pending_extremis_level_threat_request(self, *, game=None, army_id: str = "") -> bool:
        queue = getattr(game, "decision_queue", None) if game is not None else None
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "")) != "CONFIRM_YES_NO":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "extremis_level_threat":
                continue
            if army_id and str(ctx.get("army_id", "") or "") != army_id:
                continue
            return True
        return False

    def _pending_oath_of_moment_target_request(self, *, game=None, army_id: str = "") -> bool:
        queue = getattr(game, "decision_queue", None) if game is not None else None
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "oath_of_moment":
                continue
            target_slot = str(ctx.get("target_slot", "") or "primary").strip().lower() or "primary"
            if target_slot != "primary":
                continue
            if army_id and str(ctx.get("army_id", "") or "") != army_id:
                continue
            return True
        return False

    def _pending_tome_of_ectoclades_request(self, *, game=None, army_id: str = "") -> bool:
        queue = getattr(game, "decision_queue", None) if game is not None else None
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "oath_of_moment":
                continue
            target_slot = str(ctx.get("target_slot", "") or "").strip().lower()
            if target_slot != "secondary":
                continue
            if army_id and str(ctx.get("army_id", "") or "") != army_id:
                continue
            return True
        return False

    def _queue_extremis_level_threat_prompt(self, *, game=None, player=None) -> None:
        if game is None or player is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not self.can_activate_extremis_level_threat():
            return
        try:
            from ..engine.decision_kinds import DECISION_CONFIRM_YES_NO
            from ..engine.decisions import DecisionOption, DecisionRequest
        except Exception:
            return
        army_id = get_entity_id(self.army) if self.army is not None else ""
        if self._pending_extremis_level_threat_request(game=game, army_id=str(army_id or "")):
            return
        options = [
            DecisionOption.create(
                "Use",
                payload={"choice": True, "army_id": army_id},
            ),
            DecisionOption.create(
                "Skip",
                payload={"choice": False, "army_id": army_id},
            ),
        ]
        req = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            "Use Extremis-level Threat?",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "extremis_level_threat",
                "ability_name": "Extremis-level Threat",
                "army_id": army_id,
                "message": (
                    "Use Extremis-level Threat now? "
                    "Until your next Command phase, attacks against your Oath of Moment target can re-roll Wound rolls."
                ),
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)

    def queue_recalculating_prompt(self, destroyed_unit, *, game=None, player=None) -> bool:
        if game is None or player is None:
            return False
        if not bool(getattr(game, "is_authoritative", True)):
            return False
        if not self.can_trigger_recalculating(destroyed_unit, game=game, player=player):
            return False
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest
        except Exception:
            return False
        army_id = get_entity_id(self.army) if self.army is not None else ""
        if self._pending_oath_of_moment_target_request(game=game, army_id=str(army_id or "")):
            return False
        options = self._eligible_recalculating_targets(game=game, player=player)
        if not options:
            return False
        req_options = []
        for unit in options:
            req_options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(unit)},
                )
            )
        if not req_options:
            return False
        battle_round = self._current_battle_round(game=game)
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Recalculating: Select Oath of Moment target.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={
                "ability": "oath_of_moment",
                "ability_name": "Recalculating",
                "army_id": army_id,
                "battle_round": int(battle_round or 0),
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)
        self.recalculatingUsedBattleRound = int(battle_round or 0)
        self._sync_recalculating_used_battle_round()
        return True

    def _army_has_tome_of_ectoclades_available(self) -> bool:
        if self.army is None:
            return False
        if bool(self.tomeOfEctocladesUsed):
            return False
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_tome_of_ectoclades")):
                continue
            bearer = getattr(unit, "_get_enhancement_bearer_model", lambda: None)()
            if bearer is None:
                continue
            is_alive_attr = getattr(bearer, "is_alive", True)
            try:
                if not bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr):
                    continue
            except Exception:
                continue
            return True
        return False

    def _queue_tome_of_ectoclades_prompt(self, *, game=None, player=None, primary_target=None) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if self.army is None or player is None:
            return
        try:
            if getattr(player, "get_army", lambda: None)() is not self.army:
                return
        except Exception:
            return
        if not self._army_has_tome_of_ectoclades_available():
            return
        try:
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            phase_name = ""
        if phase_name and phase_name != "COMMAND_PHASE":
            return
        army_id = get_entity_id(self.army) if self.army is not None else ""
        if self._pending_tome_of_ectoclades_request(game=game, army_id=str(army_id or "")):
            return
        options = self._eligible_enemy_units(game=game, player=player)
        if not options:
            return
        primary_id = ""
        if primary_target is not None:
            try:
                primary_root = primary_target.get_attached_unit_root()
            except Exception:
                primary_root = primary_target
            primary_id = str(getattr(primary_root, "_id", "") or "")
        filtered = []
        for unit in list(options or []):
            uid = str(getattr(unit, "_id", "") or "")
            if primary_id and uid and uid == primary_id:
                continue
            filtered.append(unit)
        if not filtered:
            return
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest
        except Exception:
            return
        req_options = [DecisionOption.create("None", payload={"action": "skip", "target_slot": "secondary"})]
        for unit in filtered:
            req_options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(unit), "target_slot": "secondary"},
                )
            )
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "The Tome of Ectoclades: select a second Oath of Moment target.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={
                "ability": "oath_of_moment",
                "ability_name": "The Tome of Ectoclades",
                "army_id": army_id,
                "target_slot": "secondary",
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)

    def on_oath_target_destroyed(self, destroyed_unit, *, game=None, player=None) -> bool:
        if self.army is None:
            return False
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return False
        return bool(self.queue_recalculating_prompt(destroyed_unit, game=game, player=owner))

    def set_target(self, unit, *, game=None, player=None, source: str = "") -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            rid = getattr(root, "_id", None)
        except Exception:
            rid = None
        if not rid:
            return
        previous_target_id = str(self.oathOfMomentTargetUnitId or "")
        self.oathOfMomentTargetUnitId = rid
        try:
            self.oathOfMomentTargetName = str(getattr(root, "name", "") or "")
        except Exception:
            self.oathOfMomentTargetName = None
        if self.army is not None:
            try:
                setattr(self.army, "oathOfMomentTargetUnitId", self.oathOfMomentTargetUnitId)
                setattr(self.army, "oathOfMomentTargetName", self.oathOfMomentTargetName)
            except Exception:
                pass
        if previous_target_id and previous_target_id == str(rid):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        self._queue_tome_of_ectoclades_prompt(game=game, player=owner, primary_target=root)

    def set_secondary_target(self, unit) -> None:
        if unit is None:
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            rid = getattr(root, "_id", None)
        except Exception:
            rid = None
        if not rid:
            return
        self.oathOfMomentSecondaryTargetUnitId = str(rid)
        try:
            self.oathOfMomentSecondaryTargetName = str(getattr(root, "name", "") or "")
        except Exception:
            self.oathOfMomentSecondaryTargetName = None
        if self.army is not None:
            try:
                setattr(self.army, "oathOfMomentSecondaryTargetUnitId", self.oathOfMomentSecondaryTargetUnitId)
                setattr(self.army, "oathOfMomentSecondaryTargetName", self.oathOfMomentSecondaryTargetName)
            except Exception:
                pass

    def is_oath_target(self, target_unit) -> bool:
        if target_unit is None:
            return False
        if not self.oathOfMomentTargetUnitId and not self.oathOfMomentSecondaryTargetUnitId:
            return False
        try:
            root = target_unit.get_attached_unit_root()
        except Exception:
            root = target_unit
        try:
            tid = getattr(target_unit, "_id", None)
            rid = getattr(root, "_id", None)
        except Exception:
            tid = getattr(target_unit, "_id", None)
            rid = None
        ids = {str(tid or ""), str(rid or "")}
        primary_id = str(self.oathOfMomentTargetUnitId or "")
        secondary_id = str(self.oathOfMomentSecondaryTargetUnitId or "")
        return bool((primary_id and primary_id in ids) or (secondary_id and secondary_id in ids))

    def can_reroll_hit(self, attacker_unit, target_unit) -> bool:
        if not self._army_has_oath():
            return False
        if not self._unit_is_adeptus_astartes(attacker_unit):
            return False
        return self.is_oath_target(target_unit)

    def wound_bonus_applies(self, attacker_unit, target_unit) -> bool:
        if not self.can_reroll_hit(attacker_unit, target_unit):
            return False
        return self.wound_bonus_enabled()

    def _eligible_enemy_units(self, *, game=None, player=None) -> list:
        if game is None or player is None:
            return []
        try:
            enemy_units = list(game.get_enemy_units(player) or [])
        except Exception:
            enemy_units = []
        if not enemy_units:
            return []
        eligible = []
        seen = set()
        for unit in enemy_units:
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                if bool(getattr(root, "is_embarked", False)):
                    continue
            except Exception:
                pass
            try:
                if getattr(root, "embarked_in", None) is not None:
                    continue
            except Exception:
                pass
            try:
                rid = getattr(root, "_id", None)
            except Exception:
                rid = None
            if not rid or rid in seen:
                continue
            seen.add(rid)
            try:
                if hasattr(root, "is_alive") and callable(root.is_alive) and not root.is_alive():
                    continue
            except Exception:
                pass
            eligible.append(root)
        eligible.sort(key=lambda u: str(getattr(u, "name", "")))
        return eligible

    def get_eligible_enemy_units(self, *, game=None, player=None) -> list:
        return self._eligible_enemy_units(game=game, player=player)

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if self.army is None or player is None:
            return
        try:
            if getattr(player, "get_army", lambda: None)() is not self.army:
                return
        except Exception:
            return

        # Always clear at the start of the Command phase before new selection.
        self.clear_target()
        self.clear_secondary_target()
        self.clear_extremis_level_threat()

        if not self._army_has_oath():
            return

        options = self._eligible_enemy_units(game=game, player=player)
        if not options:
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest
        except Exception:
            return
        army_id = get_entity_id(self.army) if self.army is not None else None
        if self._pending_oath_of_moment_target_request(game=game, army_id=str(army_id or "")):
            return
        req_options = []
        for unit in options:
            req_options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(unit)},
                )
            )
        if not req_options:
            return
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select Oath of Moment target.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"ability": "oath_of_moment", "army_id": army_id},
        )
        if hasattr(game, "request_decision"):
            game.request_decision(req)
        self._queue_extremis_level_threat_prompt(game=game, player=player)
