from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utility.entity_ids import get_entity_id
from ..utility.unit_models import alive_unit_group_models


@dataclass(frozen=True)
class RiskPosture:
    variance: str
    aggression: str

    def to_dict(self) -> dict[str, str]:
        return {"variance": str(self.variance), "aggression": str(self.aggression)}


@dataclass(frozen=True)
class CPBudgetPosture:
    reserve_for_defense: int
    max_offensive_spend_this_turn: int

    def to_dict(self) -> dict[str, int]:
        return {
            "reserve_for_defense": int(self.reserve_for_defense),
            "max_offensive_spend_this_turn": int(self.max_offensive_spend_this_turn),
        }


@dataclass(frozen=True)
class ResourcePosture:
    cp_spend_profile: str
    preserve_command_reactions: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "cp_spend_profile": str(self.cp_spend_profile),
            "preserve_command_reactions": bool(self.preserve_command_reactions),
        }


@dataclass(frozen=True)
class Tier1ScoringWindow:
    window_id: str
    owner: str
    phase: str
    urgency: str

    def to_dict(self) -> dict[str, str]:
        return {
            "window_id": str(self.window_id),
            "owner": str(self.owner),
            "phase": str(self.phase),
            "urgency": str(self.urgency),
        }


@dataclass(frozen=True)
class Tier1Opportunity:
    opportunity_id: str
    kind: str
    source_ref: str
    target_region_id: str
    horizon: str
    estimated_value: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": str(self.opportunity_id),
            "kind": str(self.kind),
            "source_ref": str(self.source_ref),
            "target_region_id": str(self.target_region_id),
            "horizon": str(self.horizon),
            "estimated_value": float(self.estimated_value),
        }


@dataclass(frozen=True)
class Tier1Plan:
    plan_id: str
    battle_round: int
    player_id: str
    scoring_windows: list[Tier1ScoringWindow] = field(default_factory=list)
    priority_opportunities: list[Tier1Opportunity] = field(default_factory=list)
    denial_opportunities: list[Tier1Opportunity] = field(default_factory=list)
    staging_regions: list[str] = field(default_factory=list)
    action_enablement_goals: list[str] = field(default_factory=list)
    resource_posture: ResourcePosture = field(
        default_factory=lambda: ResourcePosture(cp_spend_profile="BALANCED", preserve_command_reactions=True)
    )
    risk_posture: RiskPosture = field(default_factory=lambda: RiskPosture(variance="MEDIUM", aggression="MEDIUM"))
    cp_budget: CPBudgetPosture = field(
        default_factory=lambda: CPBudgetPosture(reserve_for_defense=1, max_offensive_spend_this_turn=1)
    )
    unit_priority_tiers: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": str(self.plan_id),
            "battle_round": int(self.battle_round),
            "player_id": str(self.player_id),
            "scoring_windows": [window.to_dict() for window in list(self.scoring_windows or [])],
            "priority_opportunities": [opp.to_dict() for opp in list(self.priority_opportunities or [])],
            "denial_opportunities": [opp.to_dict() for opp in list(self.denial_opportunities or [])],
            "staging_regions": sorted({str(region) for region in list(self.staging_regions or []) if str(region)}),
            "action_enablement_goals": sorted(
                {str(goal) for goal in list(self.action_enablement_goals or []) if str(goal)}
            ),
            "resource_posture": self.resource_posture.to_dict(),
            "risk_posture": self.risk_posture.to_dict(),
            "cp_budget": self.cp_budget.to_dict(),
            "unit_priority_tiers": {
                str(key): list(values) for key, values in sorted((self.unit_priority_tiers or {}).items())
            },
        }


def _sorted_objectives(game: object) -> list[object]:
    game_map = getattr(game, "map", None)
    objectives = list(getattr(game_map, "objectives", []) or [])
    return sorted(objectives, key=lambda objective: str(getattr(objective, "id", "") or ""))


def _resolve_player(game: object, player_id: str):
    for player in list(getattr(game, "players", []) or []):
        if str(getattr(player, "id", "") or "") == str(player_id or ""):
            return player
    return None


def _score_for(player: object) -> int:
    get_score = getattr(player, "get_score", None)
    return int(get_score() if callable(get_score) else getattr(player, "score", 0) or 0)


def _unit_priority_tiers(player: object) -> dict[str, list[str]]:
    army = getattr(player, "army", None)
    units = sorted(list(getattr(army, "units", []) or []), key=lambda unit: str(get_entity_id(unit)))
    p0: list[str] = []
    p1: list[str] = []
    p2: list[str] = []
    for unit in units:
        deployed = bool(getattr(unit, "deployed", True))
        if not deployed:
            continue
        max_move = 0
        for model in alive_unit_group_models(unit, include_pending=False):
            value = getattr(model, "_movement", None)
            if value is None:
                value = getattr(model, "movement", 0)
            try:
                max_move = max(max_move, int(value or 0))
            except (TypeError, ValueError):
                continue
        unit_id = str(get_entity_id(unit))
        if max_move >= 10:
            p0.append(unit_id)
        elif max_move >= 6:
            p1.append(unit_id)
        else:
            p2.append(unit_id)
    return {"P0": p0, "P1": p1, "P2": p2}


def _region_id(objective_id: str) -> str:
    return f"region:objective:{str(objective_id or '')}"


def _score_source_id(objective_id: str) -> str:
    return f"score_source:objective:{str(objective_id or '')}"


def build_heuristic_tier1_plan(game: object, player_id: str) -> Tier1Plan:
    player = _resolve_player(game, player_id)
    if player is None:
        raise ValueError(f"Cannot build Tier1 plan for unknown player_id: {player_id}")
    battle_round_getter = getattr(game, "get_battle_round", None)
    battle_round = int(battle_round_getter() if callable(battle_round_getter) else getattr(game, "turn", 0) or 0)
    objectives = _sorted_objectives(game)
    priority_opportunities: list[Tier1Opportunity] = []
    denial_opportunities: list[Tier1Opportunity] = []
    for objective in objectives:
        objective_id = str(getattr(objective, "id", "") or "")
        controller = getattr(objective, "controlling_player", None)
        controller_id = str(getattr(controller, "id", "") or "")
        source_ref = _score_source_id(objective_id)
        region_id = _region_id(objective_id)
        if controller_id == str(player_id):
            priority_opportunities.append(
                Tier1Opportunity(
                    opportunity_id=f"opp_hold_{objective_id}",
                    kind="SCORING_SOURCE",
                    source_ref=source_ref,
                    target_region_id=region_id,
                    horizon="NEXT_SCORE_WINDOW",
                    estimated_value=4.0,
                )
            )
        else:
            denial_opportunities.append(
                Tier1Opportunity(
                    opportunity_id=f"opp_deny_{objective_id}",
                    kind="DENY_SOURCE",
                    source_ref=source_ref,
                    target_region_id=region_id,
                    horizon="NEXT_OPPONENT_SCORE_WINDOW",
                    estimated_value=3.0,
                )
            )
            priority_opportunities.append(
                Tier1Opportunity(
                    opportunity_id=f"opp_capture_{objective_id}",
                    kind="SCORING_SOURCE",
                    source_ref=source_ref,
                    target_region_id=region_id,
                    horizon="NEXT_SCORE_WINDOW",
                    estimated_value=2.5,
                )
            )

    opponent_scores: list[int] = []
    for other in list(getattr(game, "players", []) or []):
        if other is player:
            continue
        opponent_scores.append(_score_for(other))
    my_score = _score_for(player)
    lead = my_score - max(opponent_scores) if opponent_scores else my_score
    if lead >= 5:
        risk_posture = RiskPosture(variance="LOW", aggression="MEDIUM")
    elif lead <= -5:
        risk_posture = RiskPosture(variance="HIGH", aggression="HIGH")
    else:
        risk_posture = RiskPosture(variance="MEDIUM", aggression="MEDIUM")

    command_points = int(getattr(player, "command_points", 0) or 0)
    reserve_cp = min(2, max(0, command_points))
    offensive_cap = max(0, command_points - reserve_cp)
    if command_points <= 1:
        resource_posture = ResourcePosture(cp_spend_profile="CONSERVATIVE", preserve_command_reactions=True)
    elif command_points >= 4:
        resource_posture = ResourcePosture(cp_spend_profile="AGGRESSIVE", preserve_command_reactions=False)
    else:
        resource_posture = ResourcePosture(cp_spend_profile="BALANCED", preserve_command_reactions=True)
    plan_id = f"plan_r{battle_round}_{str(player_id)[:8]}"

    scoring_windows = [
        Tier1ScoringWindow(
            window_id=f"window_r{battle_round}_next_primary",
            owner=str(player_id),
            phase="COMMAND",
            urgency="HIGH",
        )
    ]

    staging_regions = sorted({opp.target_region_id for opp in denial_opportunities[:2]})
    action_enablement_goals = [f"enable_action_site:{region}" for region in staging_regions]

    return Tier1Plan(
        plan_id=plan_id,
        battle_round=battle_round,
        player_id=str(player_id),
        scoring_windows=scoring_windows,
        priority_opportunities=priority_opportunities,
        denial_opportunities=denial_opportunities,
        staging_regions=staging_regions,
        action_enablement_goals=action_enablement_goals,
        resource_posture=resource_posture,
        risk_posture=risk_posture,
        cp_budget=CPBudgetPosture(
            reserve_for_defense=reserve_cp,
            max_offensive_spend_this_turn=offensive_cap,
        ),
        unit_priority_tiers=_unit_priority_tiers(player),
    )
