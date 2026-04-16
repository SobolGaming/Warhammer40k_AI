from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..utility.entity_ids import get_entity_id
from .combat_timing import CombatEngagementState, unit_engagement_state


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


def _unit_id(unit: object | None) -> str:
    return str(get_entity_id(unit) or "").strip()


def _owner_player_id(unit: object | None) -> str:
    if unit is None:
        return ""
    army_getter = getattr(unit, "get_parent_army", None)
    army = army_getter() if callable(army_getter) else getattr(unit, "parent_army", None)
    player = getattr(army, "player", None) if army is not None else None
    return str(getattr(player, "id", "") or "").strip()


def _unit_is_alive(unit: object | None) -> bool:
    if unit is None:
        return False
    alive_attr = getattr(unit, "is_alive", None)
    if callable(alive_attr):
        return bool(alive_attr())
    return bool(alive_attr)


def _unit_should_fight_first(unit: object | None) -> bool:
    if unit is None:
        return False
    fight_first_getter = getattr(unit, "should_fight_first", None)
    if callable(fight_first_getter):
        return bool(fight_first_getter())
    fallback = getattr(unit, "has_fight_first", None)
    if callable(fallback):
        return bool(fallback())
    return False


def _unit_charged_this_turn(unit: object | None) -> bool:
    round_state = getattr(unit, "round_state", None) if unit is not None else None
    if round_state is None:
        return False
    return bool(
        getattr(round_state, "charged_this_round", False)
        or getattr(round_state, "declared_charge_this_round", False)
        or getattr(round_state, "attempted_charge_this_round", False)
    )


def _enemy_units_for_unit(game: object, unit: object | None) -> list[object]:
    game_map = getattr(game, "map", None)
    if game_map is None or unit is None:
        return []
    getter = getattr(game_map, "get_enemy_units", None)
    if callable(getter):
        try:
            enemy_units = list(getter(unit) or [])
        except TypeError:
            enemy_units = []
    else:
        own_army_getter = getattr(unit, "get_parent_army", None)
        own_army = own_army_getter() if callable(own_army_getter) else getattr(unit, "parent_army", None)
        enemy_units = []
        for other_unit in list(getattr(game_map, "units", []) or []):
            if other_unit is None:
                continue
            other_army_getter = getattr(other_unit, "get_parent_army", None)
            other_army = (
                other_army_getter() if callable(other_army_getter) else getattr(other_unit, "parent_army", None)
            )
            if own_army is not None and other_army is own_army:
                continue
            enemy_units.append(other_unit)
    enemy_units.sort(key=lambda candidate: _unit_id(candidate))
    return enemy_units


def unit_engaged_now(game: object, unit: object | None) -> bool:
    if unit is None:
        return False
    root = _canonical_unit(unit)
    for enemy_unit in _enemy_units_for_unit(game, root):
        enemy_root = _canonical_unit(enemy_unit)
        if enemy_root is None or not _unit_is_alive(enemy_root):
            continue
        if unit_engagement_state(root, enemy_root, game=game) is not CombatEngagementState.UNENGAGED:
            return True
    return False


@dataclass(frozen=True)
class FightEntitlement:
    unit_id: str
    owner_player_id: str
    stage_name: str
    engaged_at_step_start: bool
    charged_this_turn: bool
    fight_first: bool
    eligible_due_to_prior_engagement: bool
    overrun_available: bool
    consolidate_entitled: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "unit_id": str(self.unit_id or ""),
            "owner_player_id": str(self.owner_player_id or ""),
            "stage_name": str(self.stage_name or ""),
            "engaged_at_step_start": bool(self.engaged_at_step_start),
            "charged_this_turn": bool(self.charged_this_turn),
            "fight_first": bool(self.fight_first),
            "eligible_due_to_prior_engagement": bool(self.eligible_due_to_prior_engagement),
            "overrun_available": bool(self.overrun_available),
            "consolidate_entitled": bool(self.consolidate_entitled),
        }


@dataclass(frozen=True)
class FightEntitlementSnapshot:
    stage_name: str
    rules_bundle_id: str
    edition_family: str
    entries: tuple[FightEntitlement, ...]

    def entry_for(self, unit: object | None) -> FightEntitlement | None:
        unit_id = _unit_id(_canonical_unit(unit))
        if not unit_id:
            return None
        for entry in self.entries:
            if str(entry.unit_id or "") == unit_id:
                return entry
        return None

    def stage_unit_ids_for_player(self, player: object | None) -> tuple[str, ...]:
        player_id = str(getattr(player, "id", "") or "").strip()
        return tuple(
            entry.unit_id
            for entry in self.entries
            if player_id and str(entry.owner_player_id or "") == player_id
        )

    def overrun_available_for(self, unit: object | None, *, game: object) -> bool:
        entry = self.entry_for(unit)
        if entry is None or not bool(entry.overrun_available):
            return False
        return not unit_engaged_now(game, unit)

    def to_dict(self) -> dict[str, object]:
        return {
            "stage_name": str(self.stage_name or ""),
            "rules_bundle_id": str(self.rules_bundle_id or ""),
            "edition_family": str(self.edition_family or ""),
            "entries": [entry.to_dict() for entry in self.entries],
        }


def build_fight_entitlement_snapshot(
    game: object,
    *,
    units: Iterable[object],
    stage_name: str,
    rules_bundle_id: str,
    edition_family: str,
    overrun_enabled: bool,
) -> FightEntitlementSnapshot:
    canonical_units: list[object] = []
    seen: set[str] = set()
    for unit in list(units or []):
        root = _canonical_unit(unit)
        unit_id = _unit_id(root)
        if not unit_id or unit_id in seen:
            continue
        seen.add(unit_id)
        canonical_units.append(root)
    canonical_units.sort(key=_unit_id)

    entries = []
    for unit in canonical_units:
        engaged_at_step_start = unit_engaged_now(game, unit)
        charged_this_turn = _unit_charged_this_turn(unit)
        fight_first = _unit_should_fight_first(unit)
        eligible_due_to_prior_engagement = bool(engaged_at_step_start or charged_this_turn or fight_first)
        entries.append(
            FightEntitlement(
                unit_id=_unit_id(unit),
                owner_player_id=_owner_player_id(unit),
                stage_name=str(stage_name or ""),
                engaged_at_step_start=bool(engaged_at_step_start),
                charged_this_turn=bool(charged_this_turn),
                fight_first=bool(fight_first),
                eligible_due_to_prior_engagement=bool(eligible_due_to_prior_engagement),
                overrun_available=bool(overrun_enabled and eligible_due_to_prior_engagement),
                consolidate_entitled=bool(eligible_due_to_prior_engagement),
            )
        )
    return FightEntitlementSnapshot(
        stage_name=str(stage_name or ""),
        rules_bundle_id=str(rules_bundle_id or ""),
        edition_family=str(edition_family or ""),
        entries=tuple(entries),
    )


__all__ = [
    "FightEntitlement",
    "FightEntitlementSnapshot",
    "build_fight_entitlement_snapshot",
    "unit_engaged_now",
]
