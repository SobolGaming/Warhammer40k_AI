from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Any, Iterable


@dataclass(frozen=True)
class RewardProfile:
    profile_id: str
    step_vp_delta_scale: float
    terminal_vp_delta_scale: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": str(self.profile_id),
            "step_vp_delta_scale": float(self.step_vp_delta_scale),
            "terminal_vp_delta_scale": float(self.terminal_vp_delta_scale),
        }


_PROFILES: dict[str, RewardProfile] = {
    "dense_vp_delta_v1": RewardProfile(
        profile_id="dense_vp_delta_v1",
        step_vp_delta_scale=0.1,
        terminal_vp_delta_scale=1.0,
    ),
    "terminal_vp_delta_v1": RewardProfile(
        profile_id="terminal_vp_delta_v1",
        step_vp_delta_scale=0.0,
        terminal_vp_delta_scale=1.0,
    ),
}


def list_reward_profile_ids() -> list[str]:
    return sorted(_PROFILES.keys())


def resolve_reward_profile(profile_id: str) -> RewardProfile:
    key = str(profile_id or "").strip().lower()
    profile = _PROFILES.get(key)
    if profile is None:
        raise ValueError(f"Unknown reward profile id: {profile_id}")
    return profile


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _record_game_id(record: dict[str, Any], *, fallback_index: int) -> str:
    game_id = str(record.get("game_id", "") or "").strip()
    if game_id:
        return game_id
    return f"unknown_game_{int(fallback_index)}"


def _score_by_player(record: dict[str, Any]) -> dict[str, int]:
    state = dict(record.get("omniscient_state", {}) or {})
    players = list(state.get("players", []) or [])
    scores: dict[str, int] = {}
    for player_entry in players:
        if not isinstance(player_entry, dict):
            continue
        player_id = str(player_entry.get("player_id", "") or "").strip()
        if not player_id:
            continue
        scores[player_id] = _safe_int(player_entry.get("score", 0))
    return scores


def _actor_player_id(record: dict[str, Any]) -> str:
    outcome = dict(record.get("outcome", {}) or {})
    immediate = dict(outcome.get("immediate_deltas", {}) or {})
    actor = str(immediate.get("actor_player_id", "") or "").strip()
    if actor:
        return actor
    state = dict(record.get("omniscient_state", {}) or {})
    return str(state.get("active_player_id", "") or "").strip()


def _opponent_score(actor_player_id: str, score_by_player: dict[str, int]) -> int:
    actor = str(actor_player_id or "").strip()
    if not actor:
        return 0
    opponents = [pid for pid in sorted(score_by_player.keys()) if pid != actor]
    if not opponents:
        return 0
    if len(opponents) == 1:
        return int(score_by_player.get(opponents[0], 0))
    return int(max(score_by_player.get(pid, 0) for pid in opponents))


def annotate_decision_records_with_rewards(
    records: Iterable[dict[str, Any]],
    *,
    profile_id: str = "dense_vp_delta_v1",
) -> list[dict[str, Any]]:
    """
    Add deterministic reward targets to DecisionRecords using a VP-delta profile.

    Notes:
    - `end_of_turn_return` is a dense per-decision shaping term from VP-delta step changes.
    - `end_of_game_return` is the final VP delta for the acting player in that game.
    """

    profile = resolve_reward_profile(profile_id)
    input_records = [dict(record or {}) for record in list(records or [])]
    if not input_records:
        return []

    game_records: dict[str, list[dict[str, Any]]] = {}
    for idx, record in enumerate(input_records):
        game_id = _record_game_id(record, fallback_index=idx)
        game_records.setdefault(game_id, []).append(record)

    final_scores_by_game: dict[str, dict[str, int]] = {}
    previous_scores_by_game: dict[str, dict[str, int]] = {}
    for game_id, game_list in game_records.items():
        first = game_list[0] if game_list else {}
        last = game_list[-1] if game_list else {}
        previous_scores_by_game[game_id] = _score_by_player(first)
        final_scores_by_game[game_id] = _score_by_player(last)

    annotated: list[dict[str, Any]] = []
    for idx, raw_record in enumerate(input_records):
        game_id = _record_game_id(raw_record, fallback_index=idx)
        current_scores = _score_by_player(raw_record)
        previous_scores = dict(previous_scores_by_game.get(game_id, {}) or {})
        final_scores = dict(final_scores_by_game.get(game_id, {}) or {})
        actor_player_id = _actor_player_id(raw_record)

        actor_now = int(current_scores.get(actor_player_id, 0))
        actor_prev = int(previous_scores.get(actor_player_id, actor_now))
        opponent_now = _opponent_score(actor_player_id, current_scores)
        opponent_prev = _opponent_score(actor_player_id, previous_scores)
        step_vp_delta = int((actor_now - actor_prev) - (opponent_now - opponent_prev))

        final_actor = int(final_scores.get(actor_player_id, actor_now))
        final_opponent = _opponent_score(actor_player_id, final_scores)
        final_vp_delta = int(final_actor - final_opponent)

        record = copy.deepcopy(raw_record)
        outcome = dict(record.get("outcome", {}) or {})
        immediate = dict(outcome.get("immediate_deltas", {}) or {})
        immediate["actor_player_id"] = str(actor_player_id)
        immediate["reward_profile_id"] = str(profile.profile_id)
        immediate["vp_delta_step"] = float(step_vp_delta)
        immediate["vp_delta_terminal"] = float(final_vp_delta)
        outcome["immediate_deltas"] = immediate
        outcome["end_of_turn_return"] = float(step_vp_delta * profile.step_vp_delta_scale)
        outcome["end_of_game_return"] = float(final_vp_delta * profile.terminal_vp_delta_scale)
        record["outcome"] = outcome
        annotated.append(record)

        previous_scores_by_game[game_id] = current_scores

    return annotated
