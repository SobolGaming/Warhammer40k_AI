"""Deterministic matchup-context compiler for tournament roster evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Mapping

from .army_build import ArmyBlueprint
from .build_capability_schema import canonical_json, json_safe
from .event_policy import EventPolicyDescriptor
from .tournament_field import TournamentFieldDistribution

MATCHUP_CONTEXT_SCHEMA_ID = "matchup_context_schema:tournament_matchup_context_v1"


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _required_text(value: object, *, field_name: str) -> str:
    text = _optional_text(value)
    if text is not None:
        return text
    raise ValueError(f"{field_name} is required.")


def _stable_dict(value: object, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping.")
    return dict(json_safe(dict(value)))


def _hash_matchup_context(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:16]
    return f"matchup_context:{digest}"


@dataclass(frozen=True)
class MatchupContext:
    rules_bundle_id: str
    event_policy_id: str
    field_distribution_id: str
    pairing_mode: str
    force_disposition_lock_mode: str
    secondary_selection_mode: str
    terrain_layout_mode: str
    round_count: int
    opponent_slices: tuple[dict[str, object], ...]
    mission_distribution: tuple[dict[str, object], ...]
    deployment_distribution: tuple[dict[str, object], ...]
    terrain_distribution: tuple[dict[str, object], ...]
    matchup_context_schema_id: str = MATCHUP_CONTEXT_SCHEMA_ID
    matchup_context_id: str = ""
    battle_size: str | None = None
    army_points_limit: int | None = None
    board_size: str | None = None
    army_blueprint_hash: str | None = None
    primary_detachment_type: str | None = None
    force_disposition: str | None = None
    allowed_force_dispositions: tuple[str, ...] = ()
    clock_policy: dict[str, object] = field(default_factory=dict)
    evaluation_budget: dict[str, object] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "matchup_context_schema_id",
            _required_text(
                self.matchup_context_schema_id,
                field_name="matchup_context_schema_id",
            ),
        )
        object.__setattr__(
            self,
            "rules_bundle_id",
            _required_text(self.rules_bundle_id, field_name="rules_bundle_id"),
        )
        object.__setattr__(
            self,
            "event_policy_id",
            _required_text(self.event_policy_id, field_name="event_policy_id"),
        )
        object.__setattr__(
            self,
            "field_distribution_id",
            _required_text(self.field_distribution_id, field_name="field_distribution_id"),
        )
        object.__setattr__(self, "pairing_mode", _required_text(self.pairing_mode, field_name="pairing_mode"))
        object.__setattr__(
            self,
            "force_disposition_lock_mode",
            _required_text(
                self.force_disposition_lock_mode,
                field_name="force_disposition_lock_mode",
            ),
        )
        object.__setattr__(
            self,
            "secondary_selection_mode",
            _required_text(
                self.secondary_selection_mode,
                field_name="secondary_selection_mode",
            ),
        )
        object.__setattr__(
            self,
            "terrain_layout_mode",
            _required_text(self.terrain_layout_mode, field_name="terrain_layout_mode"),
        )
        round_count = int(self.round_count)
        if round_count <= 0:
            raise ValueError("round_count must be positive.")
        object.__setattr__(self, "round_count", round_count)
        object.__setattr__(
            self,
            "opponent_slices",
            tuple(
                sorted(
                    (dict(json_safe(value)) for value in tuple(self.opponent_slices or ())),
                    key=lambda item: str(item.get("slice_id", "")),
                )
            ),
        )
        object.__setattr__(
            self,
            "mission_distribution",
            tuple(
                sorted(
                    (dict(json_safe(value)) for value in tuple(self.mission_distribution or ())),
                    key=lambda item: str(item.get("choice_id", "")),
                )
            ),
        )
        object.__setattr__(
            self,
            "deployment_distribution",
            tuple(
                sorted(
                    (
                        dict(json_safe(value))
                        for value in tuple(self.deployment_distribution or ())
                    ),
                    key=lambda item: str(item.get("choice_id", "")),
                )
            ),
        )
        object.__setattr__(
            self,
            "terrain_distribution",
            tuple(
                sorted(
                    (dict(json_safe(value)) for value in tuple(self.terrain_distribution or ())),
                    key=lambda item: str(item.get("choice_id", "")),
                )
            ),
        )
        object.__setattr__(self, "battle_size", _optional_text(self.battle_size))
        army_points_limit = self.army_points_limit
        if army_points_limit is not None:
            army_points_limit = int(army_points_limit)
            if army_points_limit <= 0:
                raise ValueError("army_points_limit must be positive when provided.")
        object.__setattr__(self, "army_points_limit", army_points_limit)
        object.__setattr__(self, "board_size", _optional_text(self.board_size))
        object.__setattr__(self, "army_blueprint_hash", _optional_text(self.army_blueprint_hash))
        object.__setattr__(
            self,
            "primary_detachment_type",
            _optional_text(self.primary_detachment_type),
        )
        object.__setattr__(self, "force_disposition", _optional_text(self.force_disposition))
        allowed_force_dispositions = tuple(
            sorted(
                {
                    _required_text(value, field_name="allowed_force_disposition")
                    for value in tuple(self.allowed_force_dispositions or ())
                }
            )
        )
        object.__setattr__(self, "allowed_force_dispositions", allowed_force_dispositions)
        object.__setattr__(
            self,
            "clock_policy",
            _stable_dict(self.clock_policy, field_name="clock_policy"),
        )
        evaluation_budget = self.evaluation_budget
        if evaluation_budget is not None:
            evaluation_budget = _stable_dict(evaluation_budget, field_name="evaluation_budget")
        object.__setattr__(self, "evaluation_budget", evaluation_budget)
        object.__setattr__(self, "metadata", _stable_dict(self.metadata, field_name="metadata"))
        matchup_context_id = _optional_text(self.matchup_context_id)
        if matchup_context_id is None:
            matchup_context_id = _hash_matchup_context(self._hash_payload())
        object.__setattr__(self, "matchup_context_id", matchup_context_id)

    def _hash_payload(self) -> dict[str, object]:
        payload = self.to_dict()
        payload["matchup_context_id"] = ""
        return payload

    def to_dict(self) -> dict[str, object]:
        return {
            "matchup_context_schema_id": self.matchup_context_schema_id,
            "matchup_context_id": self.matchup_context_id,
            "rules_bundle_id": self.rules_bundle_id,
            "event_policy_id": self.event_policy_id,
            "field_distribution_id": self.field_distribution_id,
            "pairing_mode": self.pairing_mode,
            "force_disposition_lock_mode": self.force_disposition_lock_mode,
            "secondary_selection_mode": self.secondary_selection_mode,
            "terrain_layout_mode": self.terrain_layout_mode,
            "round_count": self.round_count,
            "battle_size": self.battle_size,
            "army_points_limit": self.army_points_limit,
            "board_size": self.board_size,
            "army_blueprint_hash": self.army_blueprint_hash,
            "primary_detachment_type": self.primary_detachment_type,
            "force_disposition": self.force_disposition,
            "allowed_force_dispositions": list(self.allowed_force_dispositions),
            "clock_policy": dict(self.clock_policy),
            "evaluation_budget": (
                None if self.evaluation_budget is None else dict(self.evaluation_budget)
            ),
            "opponent_slices": [dict(item) for item in self.opponent_slices],
            "mission_distribution": [dict(item) for item in self.mission_distribution],
            "deployment_distribution": [dict(item) for item in self.deployment_distribution],
            "terrain_distribution": [dict(item) for item in self.terrain_distribution],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: "MatchupContext | Mapping[str, Any]") -> "MatchupContext":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("MatchupContext data must be a mapping or MatchupContext.")
        return cls(
            matchup_context_schema_id=data.get(
                "matchup_context_schema_id",
                MATCHUP_CONTEXT_SCHEMA_ID,
            ),
            matchup_context_id=data.get("matchup_context_id", ""),
            rules_bundle_id=data.get("rules_bundle_id", ""),
            event_policy_id=data.get("event_policy_id", ""),
            field_distribution_id=data.get("field_distribution_id", ""),
            pairing_mode=data.get("pairing_mode", ""),
            force_disposition_lock_mode=data.get("force_disposition_lock_mode", ""),
            secondary_selection_mode=data.get("secondary_selection_mode", ""),
            terrain_layout_mode=data.get("terrain_layout_mode", ""),
            round_count=data.get("round_count", 0),
            battle_size=data.get("battle_size"),
            army_points_limit=data.get("army_points_limit"),
            board_size=data.get("board_size"),
            army_blueprint_hash=data.get("army_blueprint_hash"),
            primary_detachment_type=data.get("primary_detachment_type"),
            force_disposition=data.get("force_disposition"),
            allowed_force_dispositions=tuple(data.get("allowed_force_dispositions", ()) or ()),
            clock_policy=data.get("clock_policy"),
            evaluation_budget=data.get("evaluation_budget"),
            opponent_slices=tuple(data.get("opponent_slices", ()) or ()),
            mission_distribution=tuple(data.get("mission_distribution", ()) or ()),
            deployment_distribution=tuple(data.get("deployment_distribution", ()) or ()),
            terrain_distribution=tuple(data.get("terrain_distribution", ()) or ()),
            metadata=data.get("metadata"),
        )


def compile_matchup_context(
    *,
    field_distribution: TournamentFieldDistribution | Mapping[str, Any],
    event_policy: EventPolicyDescriptor | Mapping[str, Any],
    army_blueprint: ArmyBlueprint | Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> MatchupContext:
    field = TournamentFieldDistribution.from_dict(field_distribution)
    policy = EventPolicyDescriptor.from_dict(event_policy)
    if field.event_policy_id != policy.event_policy_id:
        raise ValueError(
            "field_distribution.event_policy_id does not match event_policy.event_policy_id: "
            f"{field.event_policy_id!r} != {policy.event_policy_id!r}"
        )
    blueprint = None if army_blueprint is None else ArmyBlueprint.from_dict(army_blueprint)
    round_count = field.round_count or policy.max_rounds
    context_metadata = _stable_dict(metadata, field_name="metadata")
    if blueprint is not None:
        context_metadata.setdefault("faction", blueprint.faction)
    return MatchupContext(
        rules_bundle_id=field.rules_bundle_id,
        event_policy_id=policy.event_policy_id,
        field_distribution_id=field.field_distribution_id,
        pairing_mode=policy.pairing_mode,
        force_disposition_lock_mode=policy.force_disposition_lock_mode,
        secondary_selection_mode=policy.secondary_selection_mode,
        terrain_layout_mode=policy.terrain_layout_mode,
        round_count=round_count,
        battle_size=policy.battle_size or (None if blueprint is None else blueprint.battle_size),
        army_points_limit=(
            policy.army_points_limit
            or (None if blueprint is None else blueprint.points_limit)
        ),
        board_size=policy.board_size,
        army_blueprint_hash=(
            None if blueprint is None else blueprint.army_blueprint_hash
        ),
        primary_detachment_type=(
            None if blueprint is None else blueprint.primary_detachment_type
        ),
        force_disposition=(None if blueprint is None else blueprint.force_disposition),
        allowed_force_dispositions=(
            ()
            if blueprint is None
            else tuple(blueprint.allowed_force_dispositions)
        ),
        clock_policy=policy.clock_policy.to_dict(),
        evaluation_budget=(
            None if policy.evaluation_budget is None else policy.evaluation_budget.to_dict()
        ),
        opponent_slices=field.normalized_opponent_slices,
        mission_distribution=field.normalized_mission_distribution,
        deployment_distribution=field.normalized_deployment_distribution,
        terrain_distribution=field.normalized_terrain_distribution,
        metadata=context_metadata,
    )


__all__ = [
    "MATCHUP_CONTEXT_SCHEMA_ID",
    "MatchupContext",
    "compile_matchup_context",
]
