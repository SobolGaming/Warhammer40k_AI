import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

# Utility Library for Dice Roll random values
from . import RNG
from .game_context import get_active_game, get_roll_context
import logging
logger = logging.getLogger(__name__)

# get result of a random dice roll, defaults to D6

_DICE_RE = re.compile(
    r"""
    ^\s*
    (?P<count>\d*)\s*[dD]\s*(?P<faces>\d+)
    (?:
        \s*(?P<sign>[+-])\s*(?P<modifier>\d+)
    )?
    \s*$
    """,
    re.VERBOSE,
)
_PREFIX_MODIFIER_DICE_RE = re.compile(
    r"""
    ^\s*
    (?P<modifier>\d+)\s*\+\s*
    (?P<count>\d*)\s*[dD]\s*(?P<faces>\d+)
    \s*$
    """,
    re.VERBOSE,
)


_SUPPRESS_GET_ROLL_REQUESTS: ContextVar[bool] = ContextVar("_SUPPRESS_GET_ROLL_REQUESTS", default=False)


def get_dice_roll(size: int = 6) -> int:
    game = get_active_game()
    if game is not None:
        event_log = getattr(game, "event_log", None)
        if event_log is not None:
            if getattr(event_log, "mode", "record") == "replay":
                event = event_log.consume("dice_roll")
                value = int(event.payload.get("value", 0) or 0)
                rng = getattr(game, "random_source", None)
                if rng is not None:
                    expected = int(rng.randint(1, size))
                    if expected != value:
                        raise ValueError(
                            f"Replay dice roll mismatch: expected {expected}, got {value}."
                        )
                return value
            roll_context = get_roll_context()
            value = int(getattr(game, "random_source").randint(1, size))
            event_log.record(
                "dice_roll",
                payload={
                    "die_faces": int(size),
                    "value": int(value),
                    "context": roll_context,
                },
            )
            return value
        return int(getattr(game, "random_source").randint(1, size))
    return RNG.randint(1, size)


@contextmanager
def suppress_get_roll_requests():
    token = _SUPPRESS_GET_ROLL_REQUESTS.set(True)
    try:
        yield
    finally:
        _SUPPRESS_GET_ROLL_REQUESTS.reset(token)


def _roll_untracked_die(size: int, game: object | None = None) -> int:
    if game is not None:
        rng = getattr(game, "random_source", None)
        if rng is not None:
            return int(rng.randint(1, size))
    return int(RNG.randint(1, size))


def _roll_untracked_expr(expr: str, game: object | None = None) -> int:
    normalized_expr = str(expr or "").strip()
    if normalized_expr.upper() == "D33":
        tens = _roll_untracked_die(3, game)
        ones = _roll_untracked_die(3, game)
        return int(int(tens) * 10 + int(ones))
    dice = DiceCollection.from_string(normalized_expr)
    return int(sum(_roll_untracked_die(int(dice.die_faces), game) for _ in range(int(dice.number))) + int(dice.modifier))


def _current_player_id(game: object) -> Optional[str]:
    getter = getattr(game, "get_current_player", None)
    if not callable(getter):
        return None
    try:
        player = getter()
    except (AttributeError, IndexError, RuntimeError, TypeError):
        return None
    if player is None:
        return None
    player_id = getattr(player, "id", None)
    return str(player_id) if player_id is not None else None


def _resolve_roll_player_id(
    game: object | None,
    *,
    player: object | None = None,
    player_id: object | None = None,
) -> Optional[str]:
    if player_id is not None:
        return str(player_id)
    if player is not None:
        resolved = getattr(player, "id", None)
        return str(resolved) if resolved is not None else None
    if game is None:
        return None
    return _current_player_id(game)


def _build_get_roll_request_spec(
    expr: str,
    *,
    reason: Optional[str] = None,
    roll_type: Optional[str] = None,
    command_reroll_allowed: bool = False,
) -> dict:
    normalized_expr = str(expr or "").strip()
    upper_expr = normalized_expr.upper()
    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        roll_ctx = str(get_roll_context() or "").strip()
        normalized_reason = (
            f"{roll_ctx}: {normalized_expr}"
            if roll_ctx
            else f"get_roll({normalized_expr})"
        )
    normalized_roll_type = str(roll_type or "").strip() or "get_roll"
    if upper_expr == "D33":
        return {
            "dice_count": 2,
            "faces": 3,
            "display_kind": "d33",
            "roll_type": normalized_roll_type,
            "reason": normalized_reason,
            "show_sum": True,
            "reroll_rules": [],
            "command_reroll_allowed": bool(command_reroll_allowed),
        }

    dice = DiceCollection.from_string(normalized_expr)
    spec = {
        "dice_count": int(dice.number),
        "faces": int(dice.die_faces),
        "roll_type": normalized_roll_type,
        "reason": normalized_reason,
        "show_sum": True,
        "reroll_rules": [],
        "command_reroll_allowed": bool(command_reroll_allowed),
    }
    modifier = int(dice.modifier or 0)
    if modifier:
        reason_text = f"Dice expression modifier ({modifier:+d})"
        spec["sum_modifier"] = int(modifier)
        spec["sum_modifier_reasons"] = [reason_text]
        spec["sum_modifier_breakdown"] = [
            {
                "source": "Dice expression",
                "reason": reason_text,
                "value": int(modifier),
                "contributor_type": "rule",
            }
        ]
    return spec


def _resolve_roll_request(game: object, request: object) -> None:
    resolve_fn = getattr(game, "resolve_decision", None)
    if not callable(resolve_fn):
        return
    decision_id = str(getattr(request, "decision_id", "") or "")
    if not decision_id:
        return
    option_id = ""
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action_id", "") or "") == "roll":
            option_id = str(getattr(option, "option_id", "") or "")
            break
    if not option_id and getattr(request, "options", None):
        option_id = str(getattr(request.options[0], "option_id", "") or "")
    if not option_id:
        return
    from ..engine.decisions import DecisionResult

    resolve_fn(
        DecisionResult(
            decision_id=decision_id,
            player_id=getattr(request, "player_id", None),
            option_id=option_id,
            payload={},
        )
    )

@dataclass
class DiceCollection:
    number: int = 0
    die_faces: int = 0
    modifier: int = 0

    @classmethod
    def from_string(cls, dice_string: str) -> 'DiceCollection':
        raw = str(dice_string or "").strip()
        match = _DICE_RE.match(raw)
        prefix_match = None if match else _PREFIX_MODIFIER_DICE_RE.match(raw)
        if match:
            count = int(match.group("count") or 1)
            faces = int(match.group("faces"))
            modifier = int(match.group("modifier") or 0)
            if match.group("sign") == "-":
                modifier = -modifier
            return cls(count, faces, modifier)
        if prefix_match:
            count = int(prefix_match.group("count") or 1)
            faces = int(prefix_match.group("faces"))
            modifier = int(prefix_match.group("modifier") or 0)
            return cls(count, faces, modifier)
        raise ValueError(f"Invalid dice string: {dice_string!r}")

    def roll(self) -> int:
        roll_value = sum(get_dice_roll(self.die_faces) for _ in range(self.number)) + self.modifier
        #print(f"Roll of {self}: {roll_value}")
        return roll_value

    def roll_detailed(self) -> tuple[int, list[int]]:
        """Roll dice and return both total and individual dice results"""
        individual_rolls = [get_dice_roll(self.die_faces) for _ in range(self.number)]
        total = sum(individual_rolls) + self.modifier
        return total, individual_rolls

    def min(self) -> int:
        return self.number + self.modifier

    def max(self) -> int:
        return self.number * self.die_faces + self.modifier

    def stat_average(self) -> float:
        return (self.number * (self.die_faces + 1) / 2) + self.modifier

    def __str__(self) -> str:
        modifier = ""
        if self.modifier > 0:
            modifier = f"+{self.modifier}"
        elif self.modifier < 0:
            modifier = str(self.modifier)
        return f"{self.number}D{self.die_faces}{modifier}"

    def __repr__(self) -> str:
        return f"DiceCollection({self.number}, {self.die_faces}, {self.modifier})"

def get_roll(
    data: str,
    *,
    game: object | None = None,
    player: object | None = None,
    player_id: object | None = None,
    reason: Optional[str] = None,
    roll_type: Optional[str] = None,
    command_reroll_allowed: bool = False,
) -> int:
    normalized_expr = str(data or "").strip()
    active_game = game if game is not None else get_active_game()
    if bool(_SUPPRESS_GET_ROLL_REQUESTS.get()):
        return int(_roll_untracked_expr(normalized_expr, active_game))
    request_roll = getattr(active_game, "request_dice_roll", None) if active_game is not None else None
    roll_manager = getattr(active_game, "roll_manager", None) if active_game is not None else None
    if callable(request_roll) and roll_manager is not None:
        spec = _build_get_roll_request_spec(
            normalized_expr,
            reason=reason,
            roll_type=roll_type,
            command_reroll_allowed=command_reroll_allowed,
        )
        request = request_roll(
            player_id=_resolve_roll_player_id(active_game, player=player, player_id=player_id),
            spec=spec,
            prompt=str(spec.get("reason") or "Roll dice"),
        )
        context = dict(getattr(request, "context", {}) or {})
        roll_id_raw = context.get("roll_id")
        if roll_id_raw is None:
            raise RuntimeError(f"Dice roll request for {normalized_expr!r} did not provide a roll_id.")
        roll_id = int(roll_id_raw)
        state = roll_manager.get_roll(roll_id)
        if state is None:
            raise RuntimeError(f"Dice roll request {roll_id} for {normalized_expr!r} was not found.")
        if str(getattr(state, "status", "")) != "rolled":
            _resolve_roll_request(active_game, request)
            state = roll_manager.get_roll(roll_id)
        if state is None or str(getattr(state, "status", "")) != "rolled":
            raise RuntimeError(f"Dice roll request {roll_id} for {normalized_expr!r} was not resolved.")
        base_total = int(getattr(state, "total", 0) or 0)
        modifier = int(spec.get("sum_modifier", 0) or 0)
        return int(base_total + modifier)
    if normalized_expr.upper() == "D33":
        tens = get_dice_roll(3)
        ones = get_dice_roll(3)
        return int(int(tens) * 10 + int(ones))
    dice = DiceCollection.from_string(normalized_expr)
    return int(dice.roll())

if __name__ == "__main__":
    test_rolls = ["D6", "2D6", "D6+5", "2D6+5"]
    for roll in test_rolls:
        value = get_roll(roll)
        logger.info(f"Roll of {roll}: {value}")
