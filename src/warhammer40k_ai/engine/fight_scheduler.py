from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from ..utility.entity_ids import get_entity_id
from .combat_timing import fight_phase_starting_player, profile_for_game
from .fight_entitlements import FightEntitlementSnapshot, build_fight_entitlement_snapshot
from .unit_turn_provenance import status_tokens_on_unit


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

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": str(self.stage.value),
            "rules_bundle_id": str(self.rules_bundle_id or ""),
            "edition_family": str(self.edition_family or ""),
            "is_attack_stage": bool(self.is_attack_stage),
        }


@dataclass(frozen=True)
class FightStageDecisionBoundary:
    boundary_id: str
    stage: FightSchedulerStage
    player_id: str
    unit_id: str = ""
    decision_category: str = ""
    entitlement_snapshot: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "boundary_id": str(self.boundary_id or ""),
            "stage": str(self.stage.value),
            "player_id": str(self.player_id or ""),
            "unit_id": str(self.unit_id or ""),
            "decision_category": str(self.decision_category or ""),
            "entitlement_snapshot": dict(self.entitlement_snapshot or {}),
        }


@dataclass(frozen=True)
class FightSchedulerTraceEvent:
    event_id: str
    event_kind: str
    stage: FightSchedulerStage
    payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": str(self.event_id or ""),
            "event_kind": str(self.event_kind or ""),
            "stage": str(self.stage.value),
            "payload": dict(self.payload or {}),
        }


def _unit_id(unit: object | None) -> str:
    return str(get_entity_id(unit) or "").strip()


def _iter_unit_candidates(candidate_units: object | None) -> list[object]:
    if candidate_units is None or isinstance(candidate_units, str | bytes):
        return []
    if not isinstance(candidate_units, Iterable):
        return []
    return [unit for unit in list(candidate_units) if unit is not None]


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
        self._pile_in_queue_by_stage: dict[FightSchedulerStage, list[str]] = {}
        self._pile_in_units_by_id: dict[str, object] = {}
        self._completed_pile_ins_by_stage: dict[FightSchedulerStage, set[str]] = {}
        self.stage_history: list[FightSchedulerTraceEvent] = []

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
                self._capture_pile_in_stage(FightSchedulerStage.PILE_IN_ACTIVE)
                if self.has_pending_pile_ins(FightSchedulerStage.PILE_IN_ACTIVE):
                    return self.state
                self.state = self._with_stage(FightSchedulerStage.PILE_IN_REACTIVE)
                continue
            if self.state.stage == FightSchedulerStage.PILE_IN_REACTIVE:
                self._capture_pile_in_stage(FightSchedulerStage.PILE_IN_REACTIVE)
                if self.has_pending_pile_ins(FightSchedulerStage.PILE_IN_REACTIVE):
                    return self.state
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

    def is_pile_in_stage(self) -> bool:
        return self.state.stage in {
            FightSchedulerStage.PILE_IN_ACTIVE,
            FightSchedulerStage.PILE_IN_REACTIVE,
        }

    def current_stage_player(self) -> object | None:
        if self.state.stage == FightSchedulerStage.PILE_IN_ACTIVE:
            return self.current_player
        if self.state.stage == FightSchedulerStage.PILE_IN_REACTIVE:
            return self.opponent_player
        if self.state.stage == FightSchedulerStage.CONSOLIDATE_BATCH:
            return self.current_player
        return self.current_stage_starting_player()

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

    def must_fight_next_units(self, *, fought_units: set[object]) -> tuple[object, ...]:
        if not self.state.is_attack_stage:
            return ()
        units: list[object] = []
        seen: set[str] = set()
        for player in (self.current_player, self.opponent_player):
            for unit in self.eligible_units_for_player(player, fought_units=fought_units):
                unit_id = _unit_id(unit)
                if not unit_id or unit_id in seen:
                    continue
                if self._unit_has_status_token_kind(unit, "must_fight_next"):
                    seen.add(unit_id)
                    units.append(unit)
        units.sort(key=_unit_id)
        return tuple(units)

    def refresh_stage_injections(self, *, fought_units: set[object]) -> None:
        if self.state.stage != FightSchedulerStage.FIGHTS_FIRST:
            return
        added: list[str] = []
        for player in (self.current_player, self.opponent_player):
            player_id = str(getattr(player, "id", "") or "").strip()
            if not player_id:
                continue
            current = list(self._stage_units_by_player.get(player_id, ()))
            current_ids = {_unit_id(unit) for unit in current}
            for unit in self._army_units_for_player(player):
                root = _canonical_unit(unit)
                unit_id = _unit_id(root)
                if not unit_id or unit_id in current_ids:
                    continue
                if root in fought_units or not _unit_is_alive(root):
                    continue
                if not self._unit_has_status_token_kind(root, "fights_first"):
                    continue
                current.append(root)
                current_ids.add(unit_id)
                added.append(unit_id)
            current.sort(key=_unit_id)
            self._stage_units_by_player[player_id] = tuple(current)
        if added:
            self._record_trace(
                "fights_first_injection",
                added_unit_ids=sorted(added),
            )

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
        self._record_trace("consolidate_queued", unit_id=unit_id)

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
        self._record_trace("consolidate_resolved", unit_id=unit_id)

    def has_pending_consolidates(self) -> bool:
        return self.next_consolidate_unit() is not None

    def next_pile_in_unit(self, stage: FightSchedulerStage | None = None) -> object | None:
        stage_key = stage or self.state.stage
        self._capture_pile_in_stage(stage_key)
        completed = self._completed_pile_ins_by_stage.setdefault(stage_key, set())
        for unit_id in list(self._pile_in_queue_by_stage.get(stage_key, []) or []):
            if unit_id in completed:
                continue
            unit = self._pile_in_units_by_id.get(unit_id)
            if unit is None or not _unit_is_alive(unit):
                completed.add(unit_id)
                continue
            return unit
        return None

    def mark_pile_in_resolved(self, unit: object | None, stage: FightSchedulerStage | None = None) -> None:
        stage_key = stage or self.state.stage
        unit_id = _unit_id(_canonical_unit(unit))
        if not unit_id:
            return
        completed = self._completed_pile_ins_by_stage.setdefault(stage_key, set())
        completed.add(unit_id)
        self._record_trace("pile_in_resolved", unit_id=unit_id, pile_in_stage=str(stage_key.value))

    def has_pending_pile_ins(self, stage: FightSchedulerStage | None = None) -> bool:
        return self.next_pile_in_unit(stage) is not None

    def consolidate_decision_categories(self, unit: object | None) -> tuple[str, ...]:
        if unit is None:
            return ()
        return ("consolidate_to_engage", "consolidate_to_objective")

    def stage_decision_boundary(
        self,
        *,
        player: object | None = None,
        unit: object | None = None,
        decision_category: str = "",
    ) -> FightStageDecisionBoundary:
        stage = self.state.stage
        player_id = str(getattr(player, "id", "") or "").strip()
        unit_id = _unit_id(_canonical_unit(unit)) if unit is not None else ""
        parts = [
            str(stage.value),
            player_id,
            unit_id,
            str(decision_category or ""),
            str(self.profile.rules_bundle_id or ""),
        ]
        boundary_id = "fight_stage:" + ":".join(part for part in parts if part)
        entitlement_payload = self.entitlement_snapshot.to_dict() if self.entitlement_snapshot is not None else None
        return FightStageDecisionBoundary(
            boundary_id=boundary_id,
            stage=stage,
            player_id=player_id,
            unit_id=unit_id,
            decision_category=str(decision_category or ""),
            entitlement_snapshot=entitlement_payload,
        )

    def decision_context(self) -> dict[str, object]:
        return {
            "scheduler_state": self.state.to_dict(),
            "entitlement_snapshot": self.entitlement_snapshot.to_dict()
            if self.entitlement_snapshot is not None
            else None,
            "pending_pile_in_unit_ids": {
                str(stage.value): [
                    unit_id
                    for unit_id in list(self._pile_in_queue_by_stage.get(stage, []) or [])
                    if unit_id not in self._completed_pile_ins_by_stage.get(stage, set())
                ]
                for stage in (FightSchedulerStage.PILE_IN_ACTIVE, FightSchedulerStage.PILE_IN_REACTIVE)
            },
            "pending_consolidate_unit_ids": [
                unit_id
                for unit_id in list(self._consolidate_queue or [])
                if unit_id not in self._completed_consolidates
            ],
            "stage_history": [event.to_dict() for event in self.stage_history],
        }

    def _with_stage(self, stage: FightSchedulerStage) -> FightSchedulerState:
        state = FightSchedulerState(
            stage=stage,
            rules_bundle_id=str(self.profile.rules_bundle_id or ""),
            edition_family=str(self.profile.edition_family or ""),
        )
        self._record_trace(
            "stage_started",
            stage_override=stage,
            previous_stage=str(self.state.stage.value),
            stage=str(stage.value),
        )
        return state

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
        self._record_trace(
            "entitlement_snapshot_captured",
            stage_name=str(stage_name or ""),
            unit_ids=[entry.unit_id for entry in self.entitlement_snapshot.entries],
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
        for unit in _iter_unit_candidates(getter(player)):
            root = _canonical_unit(unit)
            unit_id = _unit_id(root)
            if not unit_id or unit_id in seen:
                continue
            seen.add(unit_id)
            live_units.append(root)
        if self.state.stage == FightSchedulerStage.FIGHTS_FIRST:
            for unit in self._army_units_for_player(player):
                root = _canonical_unit(unit)
                unit_id = _unit_id(root)
                if not unit_id or unit_id in seen:
                    continue
                if not self._unit_has_status_token_kind(root, "fights_first"):
                    continue
                seen.add(unit_id)
                live_units.append(root)
        live_units.sort(key=_unit_id)
        return live_units

    def _capture_pile_in_stage(self, stage: FightSchedulerStage) -> None:
        if stage not in {FightSchedulerStage.PILE_IN_ACTIVE, FightSchedulerStage.PILE_IN_REACTIVE}:
            return
        if stage in self._pile_in_queue_by_stage:
            return
        player = self.current_player if stage == FightSchedulerStage.PILE_IN_ACTIVE else self.opponent_player
        units = self._all_pile_in_units_for_player(player)
        unit_ids: list[str] = []
        for unit in units:
            unit_id = _unit_id(unit)
            if not unit_id:
                continue
            self._pile_in_units_by_id[unit_id] = unit
            unit_ids.append(unit_id)
        unit_ids.sort()
        self._pile_in_queue_by_stage[stage] = unit_ids
        self._completed_pile_ins_by_stage.setdefault(stage, set())
        self._record_trace("pile_in_stage_captured", pile_in_stage=str(stage.value), unit_ids=list(unit_ids))

    def _all_pile_in_units_for_player(self, player: object | None) -> list[object]:
        units: list[object] = []
        seen: set[str] = set()
        for getter_name in ("get_fight_first_units", "get_remaining_combatant_units"):
            getter = getattr(self.game, getter_name, None)
            if callable(getter):
                candidates = _iter_unit_candidates(getter(player))
            else:
                candidates = []
            for unit in candidates:
                root = _canonical_unit(unit)
                unit_id = _unit_id(root)
                if not unit_id or unit_id in seen:
                    continue
                if not _unit_is_alive(root):
                    continue
                seen.add(unit_id)
                units.append(root)
        units.sort(key=_unit_id)
        return units

    def _army_units_for_player(self, player: object | None) -> list[object]:
        if player is None:
            return []
        army_getter = getattr(player, "get_army", None)
        army = army_getter() if callable(army_getter) else getattr(player, "army", None)
        units = _iter_unit_candidates(getattr(army, "units", None))
        units.sort(key=_unit_id)
        return units

    @staticmethod
    def _unit_has_status_token_kind(unit: object | None, condition_kind: str) -> bool:
        kind = str(condition_kind or "").strip()
        return any(str(token.condition_kind or "") == kind for token in status_tokens_on_unit(unit))

    def _record_trace(
        self,
        event_kind: str,
        *,
        stage_override: FightSchedulerStage | None = None,
        **payload: object,
    ) -> None:
        event_id = f"fight_scheduler:{len(self.stage_history) + 1:04d}:{event_kind}"
        stage = stage_override or (
            self.state.stage if isinstance(self.state.stage, FightSchedulerStage) else FightSchedulerStage.COMPLETE
        )
        event_payload = {
            key: value
            for key, value in dict(payload or {}).items()
            if value is not None
        }
        self.stage_history.append(
            FightSchedulerTraceEvent(
                event_id=event_id,
                event_kind=str(event_kind or ""),
                stage=stage,
                payload=event_payload,
            )
        )


__all__ = [
    "FightScheduler",
    "FightSchedulerTraceEvent",
    "FightStageDecisionBoundary",
    "FightSchedulerStage",
    "FightSchedulerState",
]
