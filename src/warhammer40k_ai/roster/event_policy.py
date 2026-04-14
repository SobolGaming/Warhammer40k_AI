"""Tournament event-policy schema for roster evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Mapping

from .build_capability_schema import canonical_json, json_safe

EVENT_POLICY_SCHEMA_ID = "event_policy_schema:tournament_event_policy_v1"
_FORCE_DISPOSITION_LOCK_MODES = {"event_locked", "round_locked", "flexible"}
_PAIRING_MODES = {"iid", "swiss"}


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _required_text(value: object, *, field_name: str) -> str:
    text = _optional_text(value)
    if text is not None:
        return text
    raise ValueError(f"{field_name} is required.")


def _optional_positive_int(value: object, *, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    number = int(value)
    if number <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return number


def _positive_int(value: object, *, field_name: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return number


def _mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping.")
    return dict(value)


def _stable_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    return dict(json_safe(dict(value or {})))


def _ordered_unique_texts(values: object, *, field_name: str) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in tuple(values or ()):
        text = _required_text(value, field_name=field_name)
        if text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return tuple(ordered)


def _hash_event_policy(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:16]
    return f"event_policy:{digest}"


@dataclass(frozen=True)
class SourceReference:
    label: str
    url: str
    published_on: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _required_text(self.label, field_name="label"))
        object.__setattr__(self, "url", _required_text(self.url, field_name="url"))
        object.__setattr__(self, "published_on", _optional_text(self.published_on))
        object.__setattr__(self, "note", _optional_text(self.note))

    def to_dict(self) -> dict[str, str | None]:
        return {
            "label": self.label,
            "url": self.url,
            "published_on": self.published_on,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: "SourceReference | Mapping[str, Any]") -> "SourceReference":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("SourceReference data must be a mapping or SourceReference.")
        return cls(
            label=data.get("label", ""),
            url=data.get("url", ""),
            published_on=data.get("published_on"),
            note=data.get("note"),
        )


@dataclass(frozen=True)
class ClockMilestone:
    remaining_minutes: int
    label: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "remaining_minutes",
            _positive_int(self.remaining_minutes, field_name="remaining_minutes"),
        )
        object.__setattr__(self, "label", _required_text(self.label, field_name="label"))

    def to_dict(self) -> dict[str, int | str]:
        return {
            "remaining_minutes": self.remaining_minutes,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: "ClockMilestone | Mapping[str, Any]") -> "ClockMilestone":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("ClockMilestone data must be a mapping or ClockMilestone.")
        return cls(
            remaining_minutes=data.get("remaining_minutes", 0),
            label=data.get("label", ""),
        )


@dataclass(frozen=True)
class ClockPolicy:
    clock_mode: str
    round_time_minutes: int
    chess_clock_policy: str
    pregame_minutes: int | None = None
    per_player_time_minutes: int | None = None
    milestones: tuple[ClockMilestone, ...] = ()
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "clock_mode", _required_text(self.clock_mode, field_name="clock_mode"))
        object.__setattr__(
            self,
            "round_time_minutes",
            _positive_int(self.round_time_minutes, field_name="round_time_minutes"),
        )
        object.__setattr__(
            self,
            "chess_clock_policy",
            _required_text(self.chess_clock_policy, field_name="chess_clock_policy"),
        )
        object.__setattr__(
            self,
            "pregame_minutes",
            _optional_positive_int(self.pregame_minutes, field_name="pregame_minutes"),
        )
        object.__setattr__(
            self,
            "per_player_time_minutes",
            _optional_positive_int(
                self.per_player_time_minutes,
                field_name="per_player_time_minutes",
            ),
        )
        milestones = tuple(
            sorted(
                (ClockMilestone.from_dict(value) for value in tuple(self.milestones or ())),
                key=lambda item: (-item.remaining_minutes, item.label),
            )
        )
        object.__setattr__(self, "milestones", milestones)
        object.__setattr__(self, "notes", _optional_text(self.notes))
        object.__setattr__(self, "metadata", _stable_dict(_mapping(self.metadata, field_name="metadata")))

    def to_dict(self) -> dict[str, object]:
        return {
            "clock_mode": self.clock_mode,
            "round_time_minutes": self.round_time_minutes,
            "chess_clock_policy": self.chess_clock_policy,
            "pregame_minutes": self.pregame_minutes,
            "per_player_time_minutes": self.per_player_time_minutes,
            "milestones": [milestone.to_dict() for milestone in self.milestones],
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: "ClockPolicy | Mapping[str, Any]") -> "ClockPolicy":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("ClockPolicy data must be a mapping or ClockPolicy.")
        return cls(
            clock_mode=data.get("clock_mode", ""),
            round_time_minutes=data.get("round_time_minutes", 0),
            chess_clock_policy=data.get("chess_clock_policy", ""),
            pregame_minutes=data.get("pregame_minutes"),
            per_player_time_minutes=data.get("per_player_time_minutes"),
            milestones=tuple(data.get("milestones", ()) or ()),
            notes=data.get("notes"),
            metadata=_mapping(data.get("metadata"), field_name="clock_policy.metadata"),
        )


@dataclass(frozen=True)
class EvaluationBudget:
    time_budget_ms: int | None = None
    opponent_sample_cap: int | None = None
    pairing_sample_cap: int | None = None
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "time_budget_ms",
            _optional_positive_int(self.time_budget_ms, field_name="time_budget_ms"),
        )
        object.__setattr__(
            self,
            "opponent_sample_cap",
            _optional_positive_int(
                self.opponent_sample_cap,
                field_name="opponent_sample_cap",
            ),
        )
        object.__setattr__(
            self,
            "pairing_sample_cap",
            _optional_positive_int(
                self.pairing_sample_cap,
                field_name="pairing_sample_cap",
            ),
        )
        object.__setattr__(self, "notes", _optional_text(self.notes))
        object.__setattr__(self, "metadata", _stable_dict(_mapping(self.metadata, field_name="metadata")))

    def to_dict(self) -> dict[str, object]:
        return {
            "time_budget_ms": self.time_budget_ms,
            "opponent_sample_cap": self.opponent_sample_cap,
            "pairing_sample_cap": self.pairing_sample_cap,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: "EvaluationBudget | Mapping[str, Any]") -> "EvaluationBudget":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("EvaluationBudget data must be a mapping or EvaluationBudget.")
        return cls(
            time_budget_ms=data.get("time_budget_ms"),
            opponent_sample_cap=data.get("opponent_sample_cap"),
            pairing_sample_cap=data.get("pairing_sample_cap"),
            notes=data.get("notes"),
            metadata=_mapping(data.get("metadata"), field_name="evaluation_budget.metadata"),
        )


@dataclass(frozen=True)
class MissionPolicy:
    mission_pack_id: str
    mission_generation_mode: str
    deployment_generation_mode: str
    secondary_selection_mode: str
    twists_mode: str
    asymmetric_war_mode: str
    challenge_mode: str
    objective_marker_mode: str | None = None
    terrain_layout_mode: str | None = None
    terrain_layout_count_per_pairing: int | None = None
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mission_pack_id",
            _required_text(self.mission_pack_id, field_name="mission_pack_id"),
        )
        object.__setattr__(
            self,
            "mission_generation_mode",
            _required_text(
                self.mission_generation_mode,
                field_name="mission_generation_mode",
            ),
        )
        object.__setattr__(
            self,
            "deployment_generation_mode",
            _required_text(
                self.deployment_generation_mode,
                field_name="deployment_generation_mode",
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
            "twists_mode",
            _required_text(self.twists_mode, field_name="twists_mode"),
        )
        object.__setattr__(
            self,
            "asymmetric_war_mode",
            _required_text(
                self.asymmetric_war_mode,
                field_name="asymmetric_war_mode",
            ),
        )
        object.__setattr__(
            self,
            "challenge_mode",
            _required_text(self.challenge_mode, field_name="challenge_mode"),
        )
        object.__setattr__(self, "objective_marker_mode", _optional_text(self.objective_marker_mode))
        object.__setattr__(self, "terrain_layout_mode", _optional_text(self.terrain_layout_mode))
        object.__setattr__(
            self,
            "terrain_layout_count_per_pairing",
            _optional_positive_int(
                self.terrain_layout_count_per_pairing,
                field_name="terrain_layout_count_per_pairing",
            ),
        )
        object.__setattr__(self, "notes", _optional_text(self.notes))
        object.__setattr__(self, "metadata", _stable_dict(_mapping(self.metadata, field_name="metadata")))

    def to_dict(self) -> dict[str, object]:
        return {
            "mission_pack_id": self.mission_pack_id,
            "mission_generation_mode": self.mission_generation_mode,
            "deployment_generation_mode": self.deployment_generation_mode,
            "secondary_selection_mode": self.secondary_selection_mode,
            "twists_mode": self.twists_mode,
            "asymmetric_war_mode": self.asymmetric_war_mode,
            "challenge_mode": self.challenge_mode,
            "objective_marker_mode": self.objective_marker_mode,
            "terrain_layout_mode": self.terrain_layout_mode,
            "terrain_layout_count_per_pairing": self.terrain_layout_count_per_pairing,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: "MissionPolicy | Mapping[str, Any]") -> "MissionPolicy":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("MissionPolicy data must be a mapping or MissionPolicy.")
        return cls(
            mission_pack_id=data.get("mission_pack_id", ""),
            mission_generation_mode=data.get("mission_generation_mode", ""),
            deployment_generation_mode=data.get("deployment_generation_mode", ""),
            secondary_selection_mode=data.get("secondary_selection_mode", ""),
            twists_mode=data.get("twists_mode", ""),
            asymmetric_war_mode=data.get("asymmetric_war_mode", ""),
            challenge_mode=data.get("challenge_mode", ""),
            objective_marker_mode=data.get("objective_marker_mode"),
            terrain_layout_mode=data.get("terrain_layout_mode"),
            terrain_layout_count_per_pairing=data.get("terrain_layout_count_per_pairing"),
            notes=data.get("notes"),
            metadata=_mapping(data.get("metadata"), field_name="mission_policy.metadata"),
        )


@dataclass(frozen=True)
class EventPolicyDescriptor:
    event_policy_id: str
    force_disposition_lock_mode: str
    secondary_selection_mode: str
    terrain_layout_mode: str
    clock_policy: ClockPolicy
    pairing_mode: str
    roster_submission_mode: str
    max_rounds: int
    event_policy_schema_id: str = EVENT_POLICY_SCHEMA_ID
    battle_size: str | None = None
    army_points_limit: int | None = None
    board_size: str | None = None
    mission_policy: MissionPolicy | None = None
    evaluation_budget: EvaluationBudget | None = None
    format_name: str | None = None
    battle_ready_required: bool | None = None
    pairing_tiebreakers: tuple[str, ...] = ()
    ranking_tiebreakers: tuple[str, ...] = ()
    source_references: tuple[SourceReference, ...] = ()
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "event_policy_schema_id",
            _required_text(
                self.event_policy_schema_id,
                field_name="event_policy_schema_id",
            ),
        )
        force_disposition_lock_mode = _required_text(
            self.force_disposition_lock_mode,
            field_name="force_disposition_lock_mode",
        )
        if force_disposition_lock_mode not in _FORCE_DISPOSITION_LOCK_MODES:
            raise ValueError(
                "force_disposition_lock_mode must be one of "
                f"{sorted(_FORCE_DISPOSITION_LOCK_MODES)}."
            )
        object.__setattr__(self, "force_disposition_lock_mode", force_disposition_lock_mode)
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
        object.__setattr__(self, "clock_policy", ClockPolicy.from_dict(self.clock_policy))
        pairing_mode = _required_text(self.pairing_mode, field_name="pairing_mode")
        if pairing_mode not in _PAIRING_MODES:
            raise ValueError(f"pairing_mode must be one of {sorted(_PAIRING_MODES)}.")
        object.__setattr__(self, "pairing_mode", pairing_mode)
        object.__setattr__(
            self,
            "roster_submission_mode",
            _required_text(
                self.roster_submission_mode,
                field_name="roster_submission_mode",
            ),
        )
        object.__setattr__(self, "max_rounds", _positive_int(self.max_rounds, field_name="max_rounds"))
        object.__setattr__(self, "battle_size", _optional_text(self.battle_size))
        object.__setattr__(
            self,
            "army_points_limit",
            _optional_positive_int(self.army_points_limit, field_name="army_points_limit"),
        )
        object.__setattr__(self, "board_size", _optional_text(self.board_size))
        mission_policy = None
        if self.mission_policy is not None:
            mission_policy = MissionPolicy.from_dict(self.mission_policy)
            if mission_policy.secondary_selection_mode != self.secondary_selection_mode:
                raise ValueError(
                    "mission_policy.secondary_selection_mode must match "
                    "EventPolicyDescriptor.secondary_selection_mode."
                )
            if (
                mission_policy.terrain_layout_mode is not None
                and mission_policy.terrain_layout_mode != self.terrain_layout_mode
            ):
                raise ValueError(
                    "mission_policy.terrain_layout_mode must match "
                    "EventPolicyDescriptor.terrain_layout_mode when provided."
                )
        object.__setattr__(self, "mission_policy", mission_policy)
        evaluation_budget = None
        if self.evaluation_budget is not None:
            evaluation_budget = EvaluationBudget.from_dict(self.evaluation_budget)
        object.__setattr__(self, "evaluation_budget", evaluation_budget)
        object.__setattr__(self, "format_name", _optional_text(self.format_name))
        battle_ready_required = self.battle_ready_required
        if battle_ready_required is not None:
            battle_ready_required = bool(battle_ready_required)
        object.__setattr__(self, "battle_ready_required", battle_ready_required)
        object.__setattr__(
            self,
            "pairing_tiebreakers",
            _ordered_unique_texts(
                self.pairing_tiebreakers,
                field_name="pairing_tiebreaker",
            ),
        )
        object.__setattr__(
            self,
            "ranking_tiebreakers",
            _ordered_unique_texts(
                self.ranking_tiebreakers,
                field_name="ranking_tiebreaker",
            ),
        )
        source_references = tuple(
            SourceReference.from_dict(value) for value in tuple(self.source_references or ())
        )
        object.__setattr__(self, "source_references", source_references)
        object.__setattr__(self, "notes", _optional_text(self.notes))
        object.__setattr__(self, "metadata", _stable_dict(_mapping(self.metadata, field_name="metadata")))
        event_policy_id = _optional_text(self.event_policy_id)
        if event_policy_id is None:
            event_policy_id = _hash_event_policy(self._hash_payload())
        object.__setattr__(self, "event_policy_id", event_policy_id)

    def _hash_payload(self) -> dict[str, object]:
        payload = self.to_dict()
        payload["event_policy_id"] = ""
        return payload

    def to_dict(self) -> dict[str, object]:
        return {
            "event_policy_schema_id": self.event_policy_schema_id,
            "event_policy_id": self.event_policy_id,
            "force_disposition_lock_mode": self.force_disposition_lock_mode,
            "secondary_selection_mode": self.secondary_selection_mode,
            "terrain_layout_mode": self.terrain_layout_mode,
            "clock_policy": self.clock_policy.to_dict(),
            "pairing_mode": self.pairing_mode,
            "roster_submission_mode": self.roster_submission_mode,
            "max_rounds": self.max_rounds,
            "battle_size": self.battle_size,
            "army_points_limit": self.army_points_limit,
            "board_size": self.board_size,
            "mission_policy": None if self.mission_policy is None else self.mission_policy.to_dict(),
            "evaluation_budget": (
                None if self.evaluation_budget is None else self.evaluation_budget.to_dict()
            ),
            "format_name": self.format_name,
            "battle_ready_required": self.battle_ready_required,
            "pairing_tiebreakers": list(self.pairing_tiebreakers),
            "ranking_tiebreakers": list(self.ranking_tiebreakers),
            "source_references": [reference.to_dict() for reference in self.source_references],
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: "EventPolicyDescriptor | Mapping[str, Any]",
    ) -> "EventPolicyDescriptor":
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError("EventPolicyDescriptor data must be a mapping or EventPolicyDescriptor.")
        return cls(
            event_policy_schema_id=data.get(
                "event_policy_schema_id",
                EVENT_POLICY_SCHEMA_ID,
            ),
            event_policy_id=data.get("event_policy_id", ""),
            force_disposition_lock_mode=data.get("force_disposition_lock_mode", ""),
            secondary_selection_mode=data.get("secondary_selection_mode", ""),
            terrain_layout_mode=data.get("terrain_layout_mode", ""),
            clock_policy=data.get("clock_policy", {}),
            pairing_mode=data.get("pairing_mode", ""),
            roster_submission_mode=data.get("roster_submission_mode", ""),
            max_rounds=data.get("max_rounds", 0),
            battle_size=data.get("battle_size"),
            army_points_limit=data.get("army_points_limit"),
            board_size=data.get("board_size"),
            mission_policy=data.get("mission_policy"),
            evaluation_budget=data.get("evaluation_budget"),
            format_name=data.get("format_name"),
            battle_ready_required=data.get("battle_ready_required"),
            pairing_tiebreakers=tuple(data.get("pairing_tiebreakers", ()) or ()),
            ranking_tiebreakers=tuple(data.get("ranking_tiebreakers", ()) or ()),
            source_references=tuple(data.get("source_references", ()) or ()),
            notes=data.get("notes"),
            metadata=_mapping(data.get("metadata"), field_name="event_policy.metadata"),
        )


def chapter_approved_10e_event_policy() -> EventPolicyDescriptor:
    """Current official 10th-style singles example as of April 14, 2026."""

    return EventPolicyDescriptor(
        event_policy_id="event_policy:chapter_approved_10e_singles_v1",
        force_disposition_lock_mode="flexible",
        secondary_selection_mode="fixed_or_tactical",
        terrain_layout_mode="recommended_pack_layout",
        clock_policy=ClockPolicy(
            clock_mode="shared_round",
            round_time_minutes=165,
            chess_clock_policy="not_used",
            pregame_minutes=15,
            milestones=(
                ClockMilestone(remaining_minutes=165, label="start_round"),
                ClockMilestone(remaining_minutes=160, label="pregame_complete"),
                ClockMilestone(remaining_minutes=150, label="deployment_complete"),
                ClockMilestone(remaining_minutes=110, label="battle_round_1_complete"),
                ClockMilestone(remaining_minutes=75, label="battle_round_2_complete"),
                ClockMilestone(remaining_minutes=45, label="battle_round_3_complete"),
                ClockMilestone(remaining_minutes=25, label="battle_round_4_complete"),
                ClockMilestone(remaining_minutes=5, label="judge_permission_for_new_round"),
            ),
            notes=(
                "Round duration and milestones match the February 2025 Warhammer World "
                "Grand Tournament player pack."
            ),
        ),
        pairing_mode="swiss",
        roster_submission_mode="submitted_fixed_list",
        max_rounds=5,
        battle_size="Strike Force",
        army_points_limit=2000,
        board_size='44" x 60"',
        mission_policy=MissionPolicy(
            mission_pack_id="mission_pack:chapter_approved_2025_26_v1_4",
            mission_generation_mode="pre_generated_tournament_pool",
            deployment_generation_mode="paired_with_primary_mission",
            secondary_selection_mode="fixed_or_tactical",
            twists_mode="not_used",
            asymmetric_war_mode="not_used",
            challenge_mode="not_used",
            objective_marker_mode="flat_40mm_passable",
            terrain_layout_mode="recommended_pack_layout",
            notes=(
                "Current official Tournament Companion v1.4 excludes Asymmetric War, "
                "Twists, and Challenger cards from the tournament packet."
            ),
        ),
        evaluation_budget=EvaluationBudget(
            pairing_sample_cap=128,
            opponent_sample_cap=64,
            time_budget_ms=25000,
            notes="Deterministic headless-evaluation default for offline roster assessment.",
        ),
        format_name="Current official 10th-style singles",
        battle_ready_required=True,
        pairing_tiebreakers=("record", "win_path", "random_within_record"),
        ranking_tiebreakers=("record", "opponent_win_record", "total_victory_points"),
        source_references=(
            SourceReference(
                label="Chapter Approved Tournament Companion v1.4",
                url=(
                    "https://assets.warhammer-community.com/"
                    "eng_07-01_warhammer_40000_core_rules_chapter_approved_tournament-"
                    "companion-sqc1af88bj-vzxhp9xmid.pdf"
                ),
                note="Current official tournament baseline accessed April 14, 2026.",
            ),
            SourceReference(
                label="Warhammer World Grand Tournament pack",
                url=(
                    "https://warhammerworld.warhammer-community.com/wp-content/uploads/"
                    "sites/15/2025/02/nQFpBT92eJZsn85n.pdf"
                ),
                published_on="2025-02",
                note="Used for a concrete five-round, 165-minute singles event example.",
            ),
        ),
        notes=(
            "Represents a concrete current 10th-style singles event shape with Swiss-style "
            "pairings, 2,000-point Strike Force rosters, Battle Ready scoring, and the "
            "official Chapter Approved tournament mission packet."
        ),
    )


def preview_new40k_event_policy() -> EventPolicyDescriptor:
    """Preview 11e-style event-policy example from April 2026 preview articles."""

    return EventPolicyDescriptor(
        event_policy_id="event_policy:preview_new40k_locked_force_disposition_v1",
        force_disposition_lock_mode="event_locked",
        secondary_selection_mode="fixed_or_tactical_persistent_draw",
        terrain_layout_mode="mission_pairing_recommended_layouts",
        clock_policy=ClockPolicy(
            clock_mode="shared_round",
            round_time_minutes=165,
            chess_clock_policy="organizer_defined",
            pregame_minutes=15,
            notes=(
                "No official preview event pack has been published as of April 14, 2026, "
                "so the round clock shape inherits a current five-round GT example."
            ),
        ),
        pairing_mode="swiss",
        roster_submission_mode="submitted_fixed_list_with_force_disposition",
        max_rounds=5,
        battle_size="Strike Force",
        army_points_limit=2000,
        board_size='44" x 60"',
        mission_policy=MissionPolicy(
            mission_pack_id="mission_pack:preview_new40k_adepticon_2026",
            mission_generation_mode="force_disposition_pairing_matrix",
            deployment_generation_mode="mission_paired_deployment",
            secondary_selection_mode="fixed_or_tactical_persistent_draw",
            twists_mode="optional",
            asymmetric_war_mode="not_applicable",
            challenge_mode="not_applicable",
            terrain_layout_mode="mission_pairing_recommended_layouts",
            terrain_layout_count_per_pairing=3,
            notes=(
                "Preview articles describe five Force Dispositions, tournament-side event "
                "locking at list submission, and three recommended terrain layouts per "
                "mission pairing."
            ),
        ),
        evaluation_budget=EvaluationBudget(
            pairing_sample_cap=128,
            opponent_sample_cap=64,
            time_budget_ms=25000,
            notes="Matches the default offline roster-evaluation budget until a final event pack exists.",
        ),
        format_name="Preview new40k singles",
        pairing_tiebreakers=("record", "win_path", "random_within_record"),
        ranking_tiebreakers=("record", "opponent_win_record", "total_victory_points"),
        source_references=(
            SourceReference(
                label="#New40k – How your army affects your mission",
                url="https://www.warhammer-community.com/en-gb/articles/oefzq9fg/new40k-how-your-army-affects-your-mission/",
                published_on="2026-04-03",
                note=(
                    "Preview source for Force Dispositions, tournament-side disposition "
                    "locking, secondary cadence, and paired mission/deployment logic."
                ),
            ),
            SourceReference(
                label="#New40k – Take cover with updated terrain rules",
                url="https://www.warhammer-community.com/articles/xlppkx5s/new40k-take-cover-with-updated-terrain-rules",
                published_on="2026-04-08",
                note="Preview source for terrain-layout recommendations by mission pairing.",
            ),
        ),
        notes=(
            "This is a preview-labeled example, not a claim about a final released event "
            "packet. Force-disposition locking and mission-pairing semantics are sourced "
            "from April 2026 preview articles; round count and general GT frame are "
            "inferred from current official singles norms."
        ),
        metadata={"preview_status": "inferred_until_official_event_pack"},
    )


__all__ = [
    "ClockMilestone",
    "ClockPolicy",
    "EVENT_POLICY_SCHEMA_ID",
    "EvaluationBudget",
    "EventPolicyDescriptor",
    "MissionPolicy",
    "SourceReference",
    "chapter_approved_10e_event_policy",
    "preview_new40k_event_policy",
]
