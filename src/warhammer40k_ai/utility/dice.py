import re
from dataclasses import dataclass
from typing import Optional, Union

# Utility Library for Dice Roll random values
from . import RNG
from .game_context import get_active_game, get_roll_context
import logging
logger = logging.getLogger(__name__)

# get result of a random dice roll, defaults to D6


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


def _build_legacy_request_spec(expr: str) -> tuple[dict, int]:
    normalized_expr = str(expr or "").strip()
    upper_expr = normalized_expr.upper()
    roll_ctx = str(get_roll_context() or "").strip()
    reason = (
        f"{roll_ctx}: {normalized_expr}"
        if roll_ctx
        else f"Legacy get_roll({normalized_expr})"
    )
    if upper_expr == "D33":
        return (
            {
                "dice_count": 2,
                "faces": 3,
                "display_kind": "d33",
                "roll_type": "legacy_get_roll",
                "reason": reason,
                "show_sum": True,
                "reroll_rules": [],
                "command_reroll_allowed": False,
            },
            0,
        )

    dice = DiceCollection.from_string(normalized_expr)
    spec = {
        "dice_count": int(dice.number),
        "faces": int(dice.die_faces),
        "roll_type": "legacy_get_roll",
        "reason": reason,
        "show_sum": True,
        "reroll_rules": [],
        "command_reroll_allowed": False,
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
    return spec, modifier


def _resolve_make_roll(game: object, request: object) -> None:
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


def _request_legacy_roll(expr: str) -> Optional[int]:
    game = get_active_game()
    if game is None:
        return None
    request_roll = getattr(game, "request_dice_roll", None)
    roll_manager = getattr(game, "roll_manager", None)
    if not callable(request_roll) or roll_manager is None:
        return None
    spec, modifier = _build_legacy_request_spec(expr)
    request = request_roll(
        player_id=_current_player_id(game),
        spec=spec,
        prompt=str(spec.get("reason") or "Roll dice"),
    )
    context = dict(getattr(request, "context", {}) or {})
    roll_id_raw = context.get("roll_id")
    if roll_id_raw is None:
        return None
    roll_id = int(roll_id_raw)
    state = roll_manager.get_roll(roll_id)
    if state is None:
        return None
    if str(getattr(state, "status", "")) != "rolled":
        _resolve_make_roll(game, request)
        state = roll_manager.get_roll(roll_id)
    if state is None or str(getattr(state, "status", "")) != "rolled":
        return None
    base_total = int(getattr(state, "total", 0) or 0)
    return int(base_total + int(modifier))

@dataclass
class DiceCollection:
    number: int = 0
    die_faces: int = 0
    modifier: int = 0

    @classmethod
    def from_string(cls, dice_string: str) -> 'DiceCollection':
        d_collection = cls()

        patterns = [
            r"(\d+)?D(\d+)(?:\s*\+\s*(\d+))?",
            r"(\d+)\s*\+\s*(\d+)?D(\d+)"
        ]

        for pattern in patterns:
            match = re.match(pattern, dice_string, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    d_collection.number = int(groups[0] or 1)
                    d_collection.die_faces = int(groups[1])
                    d_collection.modifier = int(groups[2] or 0)
                else:
                    d_collection.number = int(groups[1] or 1)
                    d_collection.die_faces = int(groups[2])
                    d_collection.modifier = int(groups[0] or 0)
                return d_collection

        raise ValueError(f"Invalid dice string: {dice_string}")

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
        return f"{self.number}D{self.die_faces}{'+' + str(self.modifier) if self.modifier > 0 else ''}"

    def __repr__(self) -> str:
        return f"DiceCollection({self.number}, {self.die_faces}, {self.modifier})"

def get_roll(data: str) -> Union[int, None]:
    try:
        try:
            requested = _request_legacy_roll(str(data or "").strip())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            requested = None
        if requested is not None:
            return int(requested)
        if str(data or "").strip().upper() == "D33":
            tens = get_dice_roll(3)
            ones = get_dice_roll(3)
            return int(int(tens) * 10 + int(ones))
        dice = DiceCollection.from_string(data)
        return dice.roll()
    except ValueError as e:
        logger.exception(f"ERROR: {e}")
        return None

if __name__ == "__main__":
    test_rolls = ["D6", "2D6", "D6+5", "2D6+5"]
    for roll in test_rolls:
        value = get_roll(roll)
        logger.info(f"Roll of {roll}: {value}")
