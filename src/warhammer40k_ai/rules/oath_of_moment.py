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
        self.extremisLevelThreatActive: bool = False
        self.extremisLevelThreatUsed: bool = False
        if self.army is not None:
            try:
                setattr(self.army, "oathOfMomentTargetUnitId", None)
                setattr(self.army, "oathOfMomentTargetName", None)
                setattr(self.army, "extremisLevelThreatActive", False)
                setattr(self.army, "extremisLevelThreatUsed", False)
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

    def set_target(self, unit) -> None:
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

    def is_oath_target(self, target_unit) -> bool:
        if target_unit is None:
            return False
        if not self.oathOfMomentTargetUnitId:
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
        return bool(self.oathOfMomentTargetUnitId in {tid, rid})

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
            from ..utility.entity_ids import get_entity_id
        except Exception:
            return
        army_id = get_entity_id(self.army) if self.army is not None else None
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = getattr(req, "context", {}) or {}
                if str(ctx.get("ability", "")) == "oath_of_moment" and str(ctx.get("army_id", "")) == str(army_id):
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
