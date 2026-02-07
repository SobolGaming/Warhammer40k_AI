from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utility.entity_ids import get_entity_id


@dataclass(frozen=True)
class SecondaryPosture:
    mode: str
    discard_policy: str

    def to_dict(self) -> dict[str, str]:
        return {"mode": str(self.mode), "discard_policy": str(self.discard_policy)}


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
class Tier1Plan:
    plan_id: str
    battle_round: int
    player_id: str
    primary_hold_objective_ids: list[str] = field(default_factory=list)
    contest_objective_ids: list[str] = field(default_factory=list)
    deny_opponent_primary_next_round: bool = True
    secondary_posture: SecondaryPosture = field(
        default_factory=lambda: SecondaryPosture(mode="TACTICAL", discard_policy="discard_if_p_success_lt_0.35")
    )
    risk_posture: RiskPosture = field(default_factory=lambda: RiskPosture(variance="MEDIUM", aggression="MEDIUM"))
    cp_budget: CPBudgetPosture = field(default_factory=lambda: CPBudgetPosture(reserve_for_defense=1, max_offensive_spend_this_turn=1))
    unit_priority_tiers: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": str(self.plan_id),
            "battle_round": int(self.battle_round),
            "player_id": str(self.player_id),
            "primary_hold_objective_ids": list(self.primary_hold_objective_ids),
            "contest_objective_ids": list(self.contest_objective_ids),
            "deny_opponent_primary_next_round": bool(self.deny_opponent_primary_next_round),
            "secondary_posture": self.secondary_posture.to_dict(),
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
        for model in list(getattr(unit, "models", []) or []):
            value = getattr(model, "_movement", getattr(model, "movement", 0))
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


def build_heuristic_tier1_plan(game: object, player_id: str) -> Tier1Plan:
    player = _resolve_player(game, player_id)
    if player is None:
        raise ValueError(f"Cannot build Tier1 plan for unknown player_id: {player_id}")
    battle_round_getter = getattr(game, "get_battle_round", None)
    battle_round = int(battle_round_getter() if callable(battle_round_getter) else getattr(game, "turn", 0) or 0)
    objectives = _sorted_objectives(game)
    hold_ids: list[str] = []
    contest_ids: list[str] = []
    for objective in objectives:
        objective_id = str(getattr(objective, "id", "") or "")
        controller = getattr(objective, "controlling_player", None)
        controller_id = str(getattr(controller, "id", "") or "")
        if controller_id == str(player_id):
            hold_ids.append(objective_id)
        else:
            contest_ids.append(objective_id)

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
    plan_id = f"plan_r{battle_round}_{str(player_id)[:8]}"

    return Tier1Plan(
        plan_id=plan_id,
        battle_round=battle_round,
        player_id=str(player_id),
        primary_hold_objective_ids=hold_ids,
        contest_objective_ids=contest_ids,
        deny_opponent_primary_next_round=True,
        secondary_posture=SecondaryPosture(mode="TACTICAL", discard_policy="discard_if_p_success_lt_0.35"),
        risk_posture=risk_posture,
        cp_budget=CPBudgetPosture(
            reserve_for_defense=reserve_cp,
            max_offensive_spend_this_turn=offensive_cap,
        ),
        unit_priority_tiers=_unit_priority_tiers(player),
    )
