from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..utility.entity_ids import get_entity_id
from .combat_timing import fight_phase_starting_player, profile_for_game
from .fight_entitlements import FightEntitlementSnapshot, build_fight_entitlement_snapshot


class FightSchedulerStage(str, Enum):
    PILE_IN_ACTIVE = "PILE_IN_ACTIVE"
    PILE_IN_REACTIVE = "PILE_IN_REACTIVE"
    FIGHTS_FIRST = "FIGHTS_FIRST"
    REMAINING_COMBATANTS = "REMAINING_COMBATANTS"
    CONSOLIDATE_BATCH = "CONSOLIDATE_BATCH"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class FightSchedulerState:
    stage: FightSchedulerStage
    rules_bundle_id: str
    edition_family: str

    @property
    def is_attack_stage(self) -> bool:
        return self.stage in {
            FightSchedulerStage.FIGHTS_FIRST,
            FightSchedulerStage.REMAINING_COMBATANTS,
        }


def _unit_id(unit: object | None) -> str:
    return str(get_entity_id(unit) or "").strip()


def _canonical_unit(unit: object | None) -> object | None:
    if unit is None:
        return None
    getter = getattr(unit, "get_attached_unit_root", None)
    if not callable(getter):
        return unit
    root = getter()
    if root is None:
        return unit
    models = getattr(root, "models", None)
    return root if isinstance(models, list) else unit


def _unit_is_alive(unit: object | None) -> bool:
    if unit is None:
        return False
    alive_attr = getattr(unit, "is_alive", None)
    if callable(alive_attr):
        return bool(alive_attr())
    return bool(alive_attr)


class FightScheduler:
    def __init__(self, game: object, *, current_player: object, opponent_player: object) -> None:
        self.game = game
        self.current_player = current_player
        self.opponent_player = opponent_player
        self.profile = profile_for_game(game)
        self.state = FightSchedulerState(
            stage=FightSchedulerStage.COMPLETE,
            rules_bundle_id=str(self.profile.rules_bundle_id or ""),
            edition_family=str(self.profile.edition_family or ""),
        )
        self.entitlement_snapshot: FightEntitlementSnapshot | None = None
        self._stage_units_by_player: dict[str, tuple[object, ...]] = {}
        self._consolidate_queue: list[str] = []
        self._consolidate_units_by_id: dict[str, object] = {}
        self._completed_consolidates: set[str] = set()

    def start(self) -> FightSchedulerState:
        if str(self.profile.pile_in_batch_mode or "").strip().lower() == "player_batch":
            self.state = FightSchedulerState(
                stage=FightSchedulerStage.PILE_IN_ACTIVE,
                rules_bundle_id=str(self.profile.rules_bundle_id or ""),
                edition_family=str(self.profile.edition_family or ""),
            )
        else:
            self.state = FightSchedulerState(
                stage=FightSchedulerStage.FIGHTS_FIRST,
                rules_bundle_id=str(self.profile.rules_bundle_id or ""),
                edition_family=str(self.profile.edition_family or ""),
            )
        return self.advance_to_actionable_stage()

    def advance_to_actionable_stage(self) -> FightSchedulerState:
        while True:
            if self.state.stage == FightSchedulerStage.PILE_IN_ACTIVE:
                self.state = self._with_stage(FightSchedulerStage.PILE_IN_REACTIVE)
                continue
            if self.state.stage == FightSchedulerStage.PILE_IN_REACTIVE:
                self.state = self._with_stage(FightSchedulerStage.FIGHTS_FIRST)
            if self.state.stage == FightSchedulerStage.FIGHTS_FIRST:
                if self.entitlement_snapshot is None or str(self.entitlement_snapshot.stage_name or "") != "fight_first":
                    self._capture_attack_stage("fight_first")
                if self.has_units_in_current_stage():
                    return self.state
                self.state = self._with_stage(FightSchedulerStage.REMAINING_COMBATANTS)
                continue
            if self.state.stage == FightSchedulerStage.REMAINING_COMBATANTS:
                if self.entitlement_snapshot is None or str(self.entitlement_snapshot.stage_name or "") != "remaining_combatants":
                    self._capture_attack_stage("remaining_combatants")
                if self.has_units_in_current_stage():
                    return self.state
                if self.uses_consolidate_batch() and self.has_pending_consolidates():
                    self.state = self._with_stage(FightSchedulerStage.CONSOLIDATE_BATCH)
                    return self.state
                self.state = self._with_stage(FightSchedulerStage.COMPLETE)
                return self.state
            if self.state.stage == FightSchedulerStage.CONSOLIDATE_BATCH:
                if self.has_pending_consolidates():
                    return self.state
                self.state = self._with_stage(FightSchedulerStage.COMPLETE)
                return self.state
            return self.state

    def complete_current_stage(self) -> FightSchedulerState:
        if self.state.stage == FightSchedulerStage.PILE_IN_ACTIVE:
            self.state = self._with_stage(FightSchedulerStage.PILE_IN_REACTIVE)
        elif self.state.stage == FightSchedulerStage.PILE_IN_REACTIVE:
            self.state = self._with_stage(FightSchedulerStage.FIGHTS_FIRST)
            self.entitlement_snapshot = None
        elif self.state.stage == FightSchedulerStage.FIGHTS_FIRST:
            self.state = self._with_stage(FightSchedulerStage.REMAINING_COMBATANTS)
            self.entitlement_snapshot = None
        elif self.state.stage == FightSchedulerStage.REMAINING_COMBATANTS:
            if self.uses_consolidate_batch() and self.has_pending_consolidates():
                self.state = self._with_stage(FightSchedulerStage.CONSOLIDATE_BATCH)
            else:
                self.state = self._with_stage(FightSchedulerStage.COMPLETE)
        elif self.state.stage == FightSchedulerStage.CONSOLIDATE_BATCH:
            self.state = self._with_stage(FightSchedulerStage.COMPLETE)
        return self.advance_to_actionable_stage()

    def attack_stage_name(self) -> str:
        if self.state.stage == FightSchedulerStage.FIGHTS_FIRST:
            return "fight_first"
        if self.state.stage == FightSchedulerStage.REMAINING_COMBATANTS:
            return "remaining_combatants"
        return ""

    def current_stage_starting_player(self) -> object | None:
        stage_name = self.attack_stage_name()
        if not stage_name:
            return None
        return fight_phase_starting_player(
            self.game,
            self.current_player,
            self.opponent_player,
            stage_name=stage_name,
        )

    def uses_preview_stage_snapshots(self) -> bool:
        return bool(self.profile.overrun_enabled)

    def uses_consolidate_batch(self) -> bool:
        return str(self.profile.consolidate_batch_mode or "").strip().lower() == "end_batch"

    def has_units_in_current_stage(self) -> bool:
        if not self.state.is_attack_stage:
            return False
        return any(bool(units) for units in self._stage_units_by_player.values())

    def eligible_units_for_player(self, player: object, *, fought_units: set[object]) -> list[object]:
        player_id = str(getattr(player, "id", "") or "").strip()
        if not player_id:
            return []
        if self.state.is_attack_stage and self.uses_preview_stage_snapshots():
            candidates = list(self._stage_units_by_player.get(player_id, ()))
        else:
            candidates = self._live_stage_units_for_player(player)
        eligible: list[object] = []
        for unit in candidates:
            root = _canonical_unit(unit)
            if root is None or not _unit_is_alive(root):
                continue
            if root in fought_units:
                continue
            eligible.append(root)
        eligible.sort(key=_unit_id)
        return eligible

    def entry_for(self, unit: object | None):
        if self.entitlement_snapshot is None:
            return None
        return self.entitlement_snapshot.entry_for(unit)

    def overrun_available_for(self, unit: object | None) -> bool:
        if self.entitlement_snapshot is None:
            return False
        return self.entitlement_snapshot.overrun_available_for(unit, game=self.game)

    def queue_consolidate(self, unit: object | None) -> None:
        root = _canonical_unit(unit)
        unit_id = _unit_id(root)
        if not unit_id or unit_id in self._consolidate_units_by_id:
            return
        self._consolidate_units_by_id[unit_id] = root
        self._consolidate_queue.append(unit_id)
        self._consolidate_queue.sort()

    def next_consolidate_unit(self) -> object | None:
        for unit_id in list(self._consolidate_queue):
            if unit_id in self._completed_consolidates:
                continue
            unit = self._consolidate_units_by_id.get(unit_id)
            if unit is None or not _unit_is_alive(unit):
                self._completed_consolidates.add(unit_id)
                continue
            return unit
        return None

    def mark_consolidate_resolved(self, unit: object | None) -> None:
        unit_id = _unit_id(_canonical_unit(unit))
        if not unit_id:
            return
        self._completed_consolidates.add(unit_id)

    def has_pending_consolidates(self) -> bool:
        return self.next_consolidate_unit() is not None

    def _with_stage(self, stage: FightSchedulerStage) -> FightSchedulerState:
        return FightSchedulerState(
            stage=stage,
            rules_bundle_id=str(self.profile.rules_bundle_id or ""),
            edition_family=str(self.profile.edition_family or ""),
        )

    def _capture_attack_stage(self, stage_name: str) -> None:
        current_units = self._live_stage_units_for_player(self.current_player)
        opponent_units = self._live_stage_units_for_player(self.opponent_player)
        self._stage_units_by_player = {
            str(getattr(self.current_player, "id", "") or ""): tuple(current_units),
            str(getattr(self.opponent_player, "id", "") or ""): tuple(opponent_units),
        }
        self.entitlement_snapshot = build_fight_entitlement_snapshot(
            self.game,
            units=[*current_units, *opponent_units],
            stage_name=stage_name,
            rules_bundle_id=str(self.profile.rules_bundle_id or ""),
            edition_family=str(self.profile.edition_family or ""),
            overrun_enabled=bool(self.profile.overrun_enabled),
        )

    def _live_stage_units_for_player(self, player: object) -> list[object]:
        if self.state.stage == FightSchedulerStage.FIGHTS_FIRST:
            getter = getattr(self.game, "get_fight_first_units", None)
        else:
            getter = getattr(self.game, "get_remaining_combatant_units", None)
        if not callable(getter):
            return []
        live_units: list[object] = []
        seen: set[str] = set()
        for unit in list(getter(player) or []):
            root = _canonical_unit(unit)
            unit_id = _unit_id(root)
            if not unit_id or unit_id in seen:
                continue
            seen.add(unit_id)
            live_units.append(root)
        live_units.sort(key=_unit_id)
        return live_units


__all__ = [
    "FightScheduler",
    "FightSchedulerStage",
    "FightSchedulerState",
]
