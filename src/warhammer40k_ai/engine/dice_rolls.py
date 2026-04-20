from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

from .roll_explanation import apply_roll_explanation


RollHandler = Callable[[object, "DiceRollState"], Any]

_ROLL_HANDLERS: dict[str, RollHandler] = {}


def register_roll_handler(key: str, handler: RollHandler) -> None:
    if not key:
        raise ValueError("Roll handler key required.")
    if key in _ROLL_HANDLERS:
        raise ValueError(f"Roll handler already registered: {key}")
    _ROLL_HANDLERS[key] = handler


def get_roll_handler(key: str) -> Optional[RollHandler]:
    if not key:
        return None
    return _ROLL_HANDLERS.get(key)


def _now() -> float:
    try:
        return time.time()
    except Exception:
        return 0.0


def _die_id(roll_id: int, index: int) -> str:
    return f"{int(roll_id)}:{int(index)}"


def _compare(value: int, target: int, op: str) -> bool:
    if op == "gte":
        return value >= target
    if op == "gt":
        return value > target
    if op == "lte":
        return value <= target
    if op == "lt":
        return value < target
    if op == "eq":
        return value == target
    if op == "ne":
        return value != target
    return value >= target


def _per_die_success(value: int, spec: dict) -> Optional[bool]:
    if not isinstance(spec, dict):
        return None
    fail_on = spec.get("fail_on")
    if isinstance(fail_on, list) and fail_on:
        return int(value) not in {int(v) for v in fail_on}
    target = spec.get("target")
    if target is None:
        return None
    try:
        target_val = int(target)
    except Exception:
        return None
    op = str(spec.get("target_op", "gte") or "gte").strip().lower()
    return _compare(int(value), target_val, op)


def _sum_success(total: int, spec: dict) -> Optional[bool]:
    if not isinstance(spec, dict):
        return None
    target = spec.get("sum_target")
    if target is None:
        return None
    try:
        target_val = int(target)
    except Exception:
        return None
    op = str(spec.get("sum_op", "gte") or "gte").strip().lower()
    return _compare(int(total), target_val, op)


def _sorted_die_ids(dice: Iterable[dict]) -> List[str]:
    items = list(dice or [])
    items.sort(key=lambda d: (int(d.get("value", 0) or 0), str(d.get("die_id", ""))))
    return [str(d.get("die_id", "")) for d in items]


def _sum_base_dice(dice: Iterable[dict]) -> int:
    total = 0
    for die in list(dice or []):
        if bool(die.get("is_derived", False)):
            continue
        try:
            total += int(die.get("value", 0) or 0)
        except Exception:
            continue
    return int(total)


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _clamp_die(value: int, faces: int) -> int:
    low = 1
    high = max(1, int(faces or 1))
    return max(low, min(high, int(value or 0)))


def _map_raw_d6_to_d3(raw_value: int) -> int:
    raw = _clamp_die(raw_value, 6)
    return int((raw + 1) // 2)


def _uses_d3_from_d6(spec: dict) -> bool:
    if not isinstance(spec, dict):
        return False
    mode = str(spec.get("value_mapping", "") or "").strip().lower()
    if mode in ("none", "direct_faces3"):
        return False
    if mode == "d3_from_d6":
        return True
    faces = _coerce_int(spec.get("faces", 6), default=6)
    return int(faces) == 3


def _resolve_player(game: object, player_id: Optional[str]):
    if player_id is None:
        return None
    registry = getattr(game, "entity_registry", None)
    if registry is None:
        registry = None
    try:
        found = registry.get(str(player_id), kind="player")
        if found is not None:
            return found
    except Exception:
        pass
    try:
        for player in list(getattr(game, "players", []) or []):
            try:
                pid = getattr(player, "id", None)
            except Exception:
                pid = None
            if pid is not None and str(pid) == str(player_id):
                return player
    except Exception:
        pass
    return None


def _resolve_unit(game: object, unit_id: Optional[str]):
    if unit_id is None:
        return None
    registry = getattr(game, "entity_registry", None)
    if registry is None:
        return None
    try:
        return registry.get(str(unit_id), kind="unit")
    except Exception:
        return None


def _command_reroll_is_available(game: object, state: "DiceRollState") -> bool:
    player = _resolve_player(game, getattr(state, "player_id", None))
    if player is None:
        return False
    mgr_strat = getattr(player, "stratagems", None)
    if mgr_strat is None:
        return False
    get_by_name = getattr(mgr_strat, "get_by_name", None)
    evaluate_availability = getattr(mgr_strat, "_evaluate_availability", None)
    if not callable(get_by_name) or not callable(evaluate_availability):
        return False

    strat = get_by_name("COMMAND RE-ROLL")
    if strat is None:
        return False

    phase_name = ""
    get_phase_label = getattr(game, "_current_phase_label", None)
    if callable(get_phase_label):
        try:
            phase_name = str(get_phase_label() or "")
        except Exception:
            phase_name = ""

    ctx: dict[str, object] = {"phase_name": phase_name}
    unit = _resolve_unit(game, getattr(state, "spec", {}).get("unit_id"))
    if unit is not None:
        ctx["unit"] = unit
        ctx["target_unit"] = unit

    is_active_turn = False
    get_current_player = getattr(game, "get_current_player", None)
    if callable(get_current_player):
        try:
            is_active_turn = bool(get_current_player() is player)
        except Exception:
            is_active_turn = False
    try:
        availability = evaluate_availability(strat, ctx, is_active_turn=is_active_turn)
    except Exception:
        return False
    return bool((availability or {}).get("available", False))


@dataclass
class DiceRollState:
    roll_id: int
    player_id: Optional[str]
    spec: dict
    status: str = "pending"
    dice: List[dict] = field(default_factory=list)
    total: Optional[int] = None
    sorted_ids: List[str] = field(default_factory=list)
    per_die_success: Dict[str, Optional[bool]] = field(default_factory=dict)
    sum_success: Optional[bool] = None
    reroll_options: List[dict] = field(default_factory=list)
    reroll_history: List[dict] = field(default_factory=list)
    created_at: float = field(default_factory=_now)
    resolved_at: Optional[float] = None
    final: bool = False

    def to_dict(self) -> dict:
        return {
            "roll_id": int(self.roll_id),
            "player_id": self.player_id,
            "spec": dict(self.spec or {}),
            "status": str(self.status or "pending"),
            "dice": [dict(d) for d in list(self.dice or [])],
            "total": self.total,
            "sorted_ids": list(self.sorted_ids or []),
            "per_die_success": dict(self.per_die_success or {}),
            "sum_success": self.sum_success,
            "reroll_options": [dict(r) for r in list(self.reroll_options or [])],
            "reroll_history": [dict(r) for r in list(self.reroll_history or [])],
            "created_at": float(self.created_at or 0.0),
            "resolved_at": self.resolved_at,
            "final": bool(self.final),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiceRollState":
        return cls(
            roll_id=int(data.get("roll_id", 0) or 0),
            player_id=data.get("player_id", None),
            spec=dict(data.get("spec", {}) or {}),
            status=str(data.get("status", "pending") or "pending"),
            dice=[dict(d) for d in list(data.get("dice", []) or [])],
            total=data.get("total", None),
            sorted_ids=list(data.get("sorted_ids", []) or []),
            per_die_success=dict(data.get("per_die_success", {}) or {}),
            sum_success=data.get("sum_success", None),
            reroll_options=[dict(r) for r in list(data.get("reroll_options", []) or [])],
            reroll_history=[dict(r) for r in list(data.get("reroll_history", []) or [])],
            created_at=float(data.get("created_at", 0.0) or 0.0),
            resolved_at=data.get("resolved_at", None),
            final=bool(data.get("final", False)),
        )


class DiceRollManager:
    def __init__(self):
        self.next_roll_id: int = 1
        self.rolls: dict[int, DiceRollState] = {}
        self._decision_to_roll: dict[str, int] = {}

    def to_dict(self) -> dict:
        return {
            "next_roll_id": int(self.next_roll_id),
            "rolls": [r.to_dict() for r in self.rolls.values()],
            "decision_to_roll": dict(self._decision_to_roll or {}),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiceRollManager":
        mgr = cls()
        mgr.next_roll_id = int(data.get("next_roll_id", 1) or 1)
        mgr.rolls = {}
        for item in list(data.get("rolls", []) or []):
            try:
                state = DiceRollState.from_dict(item)
            except Exception:
                continue
            mgr.rolls[state.roll_id] = state
        mgr._decision_to_roll = dict(data.get("decision_to_roll", {}) or {})
        return mgr

    def _new_roll_id(self) -> int:
        rid = int(self.next_roll_id)
        self.next_roll_id += 1
        return rid

    def _next_roll_outcome(self, state: DiceRollState, faces: int, game: object) -> dict:
        uses_d3_mapping = _uses_d3_from_d6(dict(getattr(state, "spec", {}) or {}))
        raw_faces = 6 if uses_d3_mapping else int(max(1, int(faces or 1)))
        seq = state.spec.get("roll_sequence", None) if isinstance(state.spec, dict) else None
        if isinstance(seq, list) and seq:
            try:
                idx = int(state.spec.get("roll_sequence_index", 0) or 0)
            except Exception:
                idx = 0
            if idx < len(seq):
                try:
                    seq_val = int(seq[idx] or 0)
                except Exception:
                    seq_val = 0
                try:
                    state.spec["roll_sequence_index"] = idx + 1
                except Exception:
                    pass
                if uses_d3_mapping:
                    # Preserve legacy deterministic fixtures that still provide mapped D3 values.
                    if 1 <= int(seq_val) <= 3:
                        mapped_val = _clamp_die(int(seq_val), 3)
                        raw_val = _clamp_die(int(mapped_val * 2 - 1), 6)
                    else:
                        raw_val = _clamp_die(int(seq_val), 6)
                        mapped_val = _map_raw_d6_to_d3(raw_val)
                    return {
                        "value": int(mapped_val),
                        "faces": 3,
                        "raw_value": int(raw_val),
                        "raw_faces": int(raw_faces),
                    }
                resolved = _clamp_die(int(seq_val), int(faces))
                return {
                    "value": int(resolved),
                    "faces": int(faces),
                    "raw_value": int(resolved),
                    "raw_faces": int(faces),
                }
        try:
            rng = getattr(game, "random_source", None)
            if rng is None:
                raise RuntimeError("Random source missing.")
            raw_val = int(rng.randint(1, int(raw_faces)))
        except Exception:
            raw_val = 1
        if uses_d3_mapping:
            mapped_val = _map_raw_d6_to_d3(raw_val)
            return {
                "value": int(mapped_val),
                "faces": 3,
                "raw_value": int(_clamp_die(raw_val, int(raw_faces))),
                "raw_faces": int(raw_faces),
            }
        resolved = _clamp_die(raw_val, int(faces))
        return {
            "value": int(resolved),
            "faces": int(faces),
            "raw_value": int(resolved),
            "raw_faces": int(faces),
        }

    def get_roll(self, roll_id: int) -> Optional[DiceRollState]:
        return self.rolls.get(int(roll_id))

    def get_roll_by_decision(self, decision_id: str) -> Optional[DiceRollState]:
        if not decision_id:
            return None
        rid = self._decision_to_roll.get(str(decision_id))
        if rid is None:
            return None
        return self.rolls.get(int(rid))

    def link_decision(self, decision_id: str, roll_id: int) -> None:
        if not decision_id:
            return
        self._decision_to_roll[str(decision_id)] = int(roll_id)

    def request_roll(
        self,
        game: object,
        *,
        player_id: Optional[str],
        spec: dict,
        prompt: Optional[str] = None,
    ):
        from .decisions import DecisionOption, DecisionRequest
        from .decision_kinds import DECISION_REQUEST_DICE_ROLL
        rid = self._new_roll_id()
        roll_spec = dict(spec or {})
        roll_spec.setdefault("dice_count", 1)
        roll_spec.setdefault("faces", 6)
        roll_spec.setdefault("reason", prompt or roll_spec.get("reason") or "Roll dice")
        roll_spec.setdefault("roll_type", roll_spec.get("roll_type") or "generic")
        if _uses_d3_from_d6(roll_spec):
            roll_spec.setdefault("value_mapping", "d3_from_d6")
            roll_spec.setdefault("raw_die_faces", 6)
        roll_spec = apply_roll_explanation(roll_spec)
        state = DiceRollState(
            roll_id=rid,
            player_id=player_id,
            spec=roll_spec,
            status="pending",
        )
        self.rolls[rid] = state
        options = [DecisionOption.create("Make Roll", payload={"action_id": "roll"})]
        req = DecisionRequest.create(
            DECISION_REQUEST_DICE_ROLL,
            str(roll_spec.get("reason") or "Roll dice"),
            player_id=player_id,
            options=options,
            context={
                "roll_id": int(rid),
                "roll_type": str(roll_spec.get("roll_type") or ""),
                "roll_spec": dict(roll_spec or {}),
            },
        )
        self.link_decision(req.decision_id, rid)
        if hasattr(game, "request_decision"):
            game.request_decision(req)
        return req

    def _build_dice(self, roll_id: int, values: List[Any], faces: int, *, derived: Optional[List[dict]] = None) -> List[dict]:
        dice = []
        for idx, val in enumerate(list(values or [])):
            if isinstance(val, dict):
                die_faces = _coerce_int(val.get("faces", faces), default=faces)
                raw_faces = _coerce_int(val.get("raw_faces", die_faces), default=die_faces)
                die_value = _clamp_die(_coerce_int(val.get("value", 1), default=1), die_faces)
                raw_value = _clamp_die(_coerce_int(val.get("raw_value", die_value), default=die_value), raw_faces)
            else:
                die_faces = int(faces)
                raw_faces = int(faces)
                die_value = _clamp_die(_coerce_int(val, default=1), die_faces)
                raw_value = int(die_value)
            die = {
                "die_id": _die_id(roll_id, idx),
                "value": int(die_value),
                "faces": int(die_faces),
                "raw_value": int(raw_value),
                "raw_faces": int(raw_faces),
                "is_derived": False,
                "derived_kind": None,
                "reroll_count": 0,
                "rerolled_from": None,
            }
            dice.append(die)
        for entry in list(derived or []):
            try:
                dval = int(entry.get("value", 0) or 0)
                dkind = entry.get("derived_kind")
            except Exception:
                dval = 0
                dkind = None
            die = {
                "die_id": str(entry.get("die_id") or _die_id(roll_id, len(dice))),
                "value": int(dval),
                "faces": int(entry.get("faces", faces) or faces),
                "raw_value": int(entry.get("raw_value", dval) or dval),
                "raw_faces": int(entry.get("raw_faces", entry.get("faces", faces) or faces) or (entry.get("faces", faces) or faces)),
                "is_derived": True,
                "derived_kind": dkind,
                "reroll_count": 0,
                "rerolled_from": None,
            }
            dice.append(die)
        return dice

    def _compute_success(self, state: DiceRollState) -> None:
        per_die = {}
        for die in list(state.dice or []):
            die_id = str(die.get("die_id", ""))
            if bool(die.get("is_derived", False)):
                per_die[die_id] = None
                continue
            per_die[die_id] = _per_die_success(int(die.get("value", 0) or 0), state.spec)
        state.per_die_success = per_die
        if state.total is not None:
            try:
                mod = int(state.spec.get("sum_modifier", 0) or 0)
            except Exception:
                mod = 0
            state.sum_success = _sum_success(int(state.total) + mod, state.spec)
        else:
            state.sum_success = None
        state.sorted_ids = _sorted_die_ids(state.dice)

    def _compute_reroll_options(self, game: object, state: DiceRollState) -> List[dict]:
        if state.final:
            return []
        rules = list(state.spec.get("reroll_rules", []) or [])
        options: List[dict] = []
        # Always include a "None" option if any reroll is possible.
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            mode = str(rule.get("mode", "none") or "none").strip().lower()
            if mode == "none":
                continue
            auto_select_all = bool(rule.get("auto_select_all", False))
            label = str(rule.get("label", "") or "Re-roll")
            source = str(rule.get("source", "") or "")
            allow_success = bool(rule.get("allow_success", False))
            max_select = rule.get("max_select")
            if max_select is None and mode in ("one", "single", "select"):
                max_select = 1
            eligible_values = rule.get("eligible_values")
            eligible_positions_raw = rule.get("eligible_positions", None)
            eligible_positions = None
            if isinstance(eligible_positions_raw, list):
                eligible_positions = set()
                for raw_pos in list(eligible_positions_raw or []):
                    try:
                        pos = int(raw_pos)
                    except Exception:
                        continue
                    if pos < 0:
                        continue
                    eligible_positions.add(pos)
            eligible_ids: List[str] = []
            if mode == "ones":
                mode = "values"
            for pos, die in enumerate(list(state.dice or [])):
                if eligible_positions is not None and pos not in eligible_positions:
                    continue
                if bool(die.get("is_derived", False)):
                    continue
                if int(die.get("reroll_count", 0) or 0) >= 1 and not bool(rule.get("allow_multiple", False)):
                    continue
                if not allow_success:
                    succ = state.per_die_success.get(str(die.get("die_id", "")))
                    if succ is True and mode not in ("all", "whole"):
                        # Skip successful dice unless rule allows it
                        continue
                if mode == "values":
                    values = [1]
                    if isinstance(eligible_values, list) and eligible_values:
                        values = [int(v) for v in eligible_values]
                    if int(die.get("value", 0) or 0) not in set(values):
                        continue
                if mode == "any":
                    pass
                eligible_ids.append(str(die.get("die_id", "")))
            if mode in ("all", "whole"):
                # "all" implies reroll whole pool, even if some dice already rerolled (allowed only if any eligible).
                eligible_ids = [
                    str(d.get("die_id", ""))
                    for pos, d in enumerate(list(state.dice or []))
                    if (
                        (eligible_positions is None or pos in eligible_positions)
                        and (not bool(d.get("is_derived", False)))
                        and int(d.get("reroll_count", 0) or 0) < 1
                    )
                ]
                if not eligible_ids:
                    continue
            if not eligible_ids and mode not in ("all", "whole"):
                continue
            options.append(
                {
                    "action_id": str(rule.get("action_id") or rule.get("key") or label),
                    "label": label,
                    "source": source,
                    "mode": mode,
                    "eligible_die_ids": eligible_ids,
                    "max_select": max_select,
                    "consume_cp": bool(rule.get("consume_cp", False)),
                    "is_command": bool(rule.get("is_command", False)),
                    "auto_select_all": bool(auto_select_all),
                }
            )
        # Command re-roll
        try:
            if bool(state.spec.get("command_reroll_allowed", False)) and _command_reroll_is_available(game, state):
                cmd_mode = str(state.spec.get("command_reroll_mode", "one") or "one").strip().lower()
                eligible_cmd = [
                    str(d.get("die_id", ""))
                    for d in list(state.dice or [])
                    if (not bool(d.get("is_derived", False))) and int(d.get("reroll_count", 0) or 0) < 1
                ]
                if eligible_cmd:
                    options.append(
                        {
                            "action_id": "command_reroll",
                            "label": "Command Re-roll",
                            "ability_key": "command_reroll",
                            "ability_name": "COMMAND RE-ROLL",
                            "stratagem_name": "COMMAND RE-ROLL",
                            "tool_id": "stratagem:command_reroll",
                            "tool_type": "stratagem",
                            "source": "command",
                            "mode": "whole" if cmd_mode in ("whole", "all") else "one",
                            "eligible_die_ids": eligible_cmd,
                            "max_select": 1 if cmd_mode not in ("whole", "all") else None,
                            "cp_cost": 1,
                            "consume_cp": True,
                            "is_command": True,
                            "semantic_tags": ["reroll", "command", "resource"],
                        }
                    )
        except Exception:
            pass
        if options:
            options.insert(0, {"action_id": "none", "label": "No re-roll", "source": "none", "mode": "none"})
        return options

    def resolve_roll(
        self,
        game: object,
        roll_id: int,
        *,
        result_payload: Optional[dict] = None,
        actor_player_id: Optional[str] = None,
    ) -> DiceRollState:
        state = self.rolls.get(int(roll_id))
        if state is None:
            raise RuntimeError("Roll state not found.")
        if state.status == "rolled":
            return state

        is_authoritative = bool(getattr(game, "is_authoritative", True))
        if not is_authoritative:
            if isinstance(result_payload, dict) and result_payload.get("roll_results"):
                return self.apply_roll_results(game, roll_id, result_payload.get("roll_results"), actor_player_id=actor_player_id)
            # Client wait for server result
            return state

        spec = dict(state.spec or {})
        dice_count = int(spec.get("dice_count", 1) or 1)
        faces = int(spec.get("faces", 6) or 6)
        fixed = list(spec.get("fixed_dice", []) or [])
        fixed_raw = list(spec.get("fixed_raw_dice", []) or [])
        uses_d3_mapping = _uses_d3_from_d6(spec)
        values: List[Any] = []
        for i in range(dice_count):
            if i < len(fixed) and fixed[i] is not None:
                if uses_d3_mapping:
                    mapped = _clamp_die(_coerce_int(fixed[i], default=1), 3)
                    if i < len(fixed_raw) and fixed_raw[i] is not None:
                        raw_val = _clamp_die(_coerce_int(fixed_raw[i], default=1), 6)
                    else:
                        raw_val = _clamp_die(int(mapped * 2 - 1), 6)
                    values.append(
                        {
                            "value": int(mapped),
                            "faces": 3,
                            "raw_value": int(raw_val),
                            "raw_faces": 6,
                        }
                    )
                else:
                    resolved = _clamp_die(_coerce_int(fixed[i], default=1), int(faces))
                    values.append(
                        {
                            "value": int(resolved),
                            "faces": int(faces),
                            "raw_value": int(resolved),
                            "raw_faces": int(faces),
                        }
                    )
                continue
            values.append(self._next_roll_outcome(state, faces, game))

        state.dice = self._build_dice(state.roll_id, values, faces, derived=list(spec.get("derived_dice", []) or []))
        state.total = int(_sum_base_dice(state.dice))
        if str(spec.get("display_kind", "") or "") == "d33":
            base_vals = [int(d.get("value", 0) or 0) for d in list(state.dice or []) if not bool(d.get("is_derived", False))]
            if len(base_vals) >= 2:
                state.total = int(base_vals[0] * 10 + base_vals[1])
        state.status = "rolled"
        state.resolved_at = _now()
        self._compute_success(state)
        state.reroll_options = self._compute_reroll_options(game, state)

        if state.reroll_options:
            self._queue_reroll_decision(game, state)
        else:
            self._finalize_roll(game, state)
        return state

    def apply_roll_results(
        self,
        game: object,
        roll_id: int,
        roll_results: dict,
        *,
        actor_player_id: Optional[str] = None,
    ) -> DiceRollState:
        state = self.rolls.get(int(roll_id))
        if state is None:
            raise RuntimeError("Roll state not found.")
        if not isinstance(roll_results, dict):
            return state
        dice_payload = roll_results.get("dice", None)
        if isinstance(dice_payload, list) and dice_payload:
            state.dice = [dict(d) for d in list(dice_payload or [])]
            for die in list(state.dice or []):
                if "raw_value" not in die:
                    die["raw_value"] = _coerce_int(die.get("value", 1), default=1)
                if "raw_faces" not in die:
                    die["raw_faces"] = _coerce_int(die.get("faces", 6), default=6)
        else:
            dice_values = list(roll_results.get("values", []) or [])
            faces = int(roll_results.get("faces", state.spec.get("faces", 6) or 6))
            uses_d3_mapping = _uses_d3_from_d6(dict(getattr(state, "spec", {}) or {}))
            normalized_values: List[Any] = []
            for value in list(dice_values or []):
                if isinstance(value, dict):
                    normalized_values.append(dict(value))
                    continue
                if uses_d3_mapping:
                    mapped = _clamp_die(_coerce_int(value, default=1), 3)
                    normalized_values.append(
                        {
                            "value": int(mapped),
                            "faces": 3,
                            "raw_value": int(_clamp_die(int(mapped * 2 - 1), 6)),
                            "raw_faces": 6,
                        }
                    )
                    continue
                resolved = _clamp_die(_coerce_int(value, default=1), int(faces))
                normalized_values.append(
                    {
                        "value": int(resolved),
                        "faces": int(faces),
                        "raw_value": int(resolved),
                        "raw_faces": int(faces),
                    }
                )
            state.dice = self._build_dice(
                state.roll_id,
                normalized_values,
                faces,
                derived=list(roll_results.get("derived_dice", []) or []),
            )
        state.total = int(roll_results.get("total", _sum_base_dice(state.dice)))
        if str(state.spec.get("display_kind", "") or "") == "d33":
            base_vals = [int(d.get("value", 0) or 0) for d in list(state.dice or []) if not bool(d.get("is_derived", False))]
            if len(base_vals) >= 2:
                state.total = int(base_vals[0] * 10 + base_vals[1])
        state.status = "rolled"
        state.resolved_at = _now()
        self._compute_success(state)
        state.reroll_options = list(roll_results.get("reroll_options", []) or [])
        # Clients should not enqueue new decisions; rely on server broadcasts.
        if bool(getattr(game, "is_authoritative", True)):
            if state.reroll_options:
                self._queue_reroll_decision(game, state)
            else:
                self._finalize_roll(game, state)
        else:
            if not state.reroll_options:
                self._finalize_roll(game, state)
        return state

    def _queue_reroll_decision(self, game: object, state: DiceRollState) -> None:
        from .decisions import DecisionOption, DecisionRequest
        from .decision_kinds import DECISION_SELECT_DICE_REROLL
        if state.final:
            return
        options = []
        for opt in list(state.reroll_options or []):
            action_id = str(opt.get("action_id", "") or "")
            label = str(opt.get("label", "") or "")
            if not action_id:
                continue
            options.append(DecisionOption.create(label, payload=dict(opt or {})))
        if not options:
            self._finalize_roll(game, state)
            return
        req = DecisionRequest.create(
            DECISION_SELECT_DICE_REROLL,
            f"Re-roll options: {state.spec.get('reason', 'Roll')}",
            player_id=state.player_id,
            options=options,
            context={
                "roll_id": int(state.roll_id),
                "roll_spec": dict(state.spec or {}),
            },
        )
        self.link_decision(req.decision_id, state.roll_id)
        if hasattr(game, "request_decision"):
            game.request_decision(req)

    def _auto_pick_reroll_action(self, game: object, state: DiceRollState) -> tuple[str, list[str] | None]:
        """Best-effort auto selection for rerolls in headless mode."""
        if state is None:
            return ("none", [])
        options = list(state.reroll_options or [])
        spec = dict(getattr(state, "spec", {}) or {})
        player_obj = _resolve_player(game, state.player_id)
        unit_obj = _resolve_unit(game, spec.get("unit_id"))
        provider = None
        is_human = False
        try:
            game_map = getattr(game, "map", None)
            provider = getattr(game_map, "roll_reroll_provider", None)
        except Exception:
            provider = None
        try:
            if player_obj is not None and bool(getattr(player_obj, "has_control", lambda: False)()):
                is_human = True
        except Exception:
            is_human = False

        def _select_ids(opt: dict) -> list[str]:
            mode = str(opt.get("mode", "") or "")
            eligible = [str(d) for d in list(opt.get("eligible_die_ids", []) or [])]
            failed = [
                die_id
                for die_id in eligible
                if state.per_die_success.get(die_id, None) is False
            ]
            if mode in ("all", "whole"):
                return eligible
            if mode in ("values", "ones", "any"):
                return failed or eligible
            if mode in ("one", "single", "select"):
                if failed:
                    return [failed[0]]
                if eligible:
                    return [eligible[0]]
                return []
            return eligible

        if callable(provider):
            for opt in options:
                action_id = str(opt.get("action_id", ""))
                if action_id in ("none", "command_reroll"):
                    continue
                reason = str(opt.get("label", "") or spec.get("reason", "") or "Re-roll")
                needed = spec.get("target", None)
                if needed is None:
                    needed = spec.get("sum_target", None)
                dice_vals = [int(d.get("value", 0) or 0) for d in list(state.dice or []) if not bool(d.get("is_derived", False))]
                try:
                    want = bool(
                        provider(
                            player=player_obj,
                            unit=unit_obj,
                            roll_type=str(spec.get("roll_type", "") or ""),
                            value=int(state.total or 0),
                            dice=dice_vals,
                            needed=needed,
                            success=state.sum_success,
                            reason=reason,
                            allow_reroll=True,
                        )
                    )
                except Exception:
                    want = False
                if want:
                    selected = _select_ids(opt)
                    return (action_id, selected)
            return ("none", [])
        # Prefer non-command rerolls.
        for opt in options:
            if str(opt.get("action_id", "")) in ("none", "command_reroll"):
                continue
            action_id = str(opt.get("action_id", ""))
            mode = str(opt.get("mode", "") or "")
            eligible = [str(d) for d in list(opt.get("eligible_die_ids", []) or [])]
            if not eligible:
                continue
            failed = [
                die_id
                for die_id in eligible
                if state.per_die_success.get(die_id, None) is False
            ]
            if mode in ("all", "whole"):
                if failed:
                    return (action_id, eligible)
                continue
            if mode in ("values", "ones", "any"):
                # Prefer rerolling eligible failures.
                if failed:
                    return (action_id, failed)
                return (action_id, eligible)
            if mode in ("one", "single", "select"):
                if failed:
                    return (action_id, [failed[0]])
                return (action_id, [eligible[0]])
            # Fallback: select all eligible.
            return (action_id, eligible)
        return ("none", [])

    def apply_reroll(
        self,
        game: object,
        roll_id: int,
        *,
        action_id: str,
        selected_die_ids: Optional[List[str]] = None,
        actor_player_id: Optional[str] = None,
    ) -> DiceRollState:
        state = self.rolls.get(int(roll_id))
        if state is None:
            raise RuntimeError("Roll state not found.")
        if state.status != "rolled":
            return state
        if state.final:
            return state
        action = None
        for opt in list(state.reroll_options or []):
            if str(opt.get("action_id", "")) == str(action_id):
                action = dict(opt)
                break
        if action is None or str(action.get("mode", "")) == "none":
            self._finalize_roll(game, state)
            return state

        mode = str(action.get("mode", "") or "")
        eligible = set(action.get("eligible_die_ids", []) or [])
        chosen = []
        if mode in ("all", "whole"):
            chosen = list(eligible)
        else:
            requested = list(selected_die_ids or [])
            for die_id in requested:
                if die_id in eligible:
                    chosen.append(die_id)
        max_select = action.get("max_select")
        if max_select is not None:
            try:
                max_val = int(max_select)
                chosen = chosen[:max_val]
            except Exception:
                pass
        if not chosen:
            self._finalize_roll(game, state)
            return state

        faces = int(state.spec.get("faces", 6) or 6)
        rerolled_ids: list[str] = []
        for die in list(state.dice or []):
            die_id = str(die.get("die_id", ""))
            if die_id not in chosen:
                continue
            if int(die.get("reroll_count", 0) or 0) >= 1:
                continue
            outcome = dict(self._next_roll_outcome(state, faces, game) or {})
            new_val = _coerce_int(outcome.get("value", 1), default=1)
            new_faces = _coerce_int(outcome.get("faces", faces), default=faces)
            new_raw_val = _coerce_int(outcome.get("raw_value", new_val), default=new_val)
            new_raw_faces = _coerce_int(outcome.get("raw_faces", new_faces), default=new_faces)
            die["rerolled_from"] = int(die.get("value", 0) or 0)
            die["raw_rerolled_from"] = int(die.get("raw_value", die.get("value", 0)) or die.get("value", 0) or 0)
            die["value"] = int(new_val)
            die["faces"] = int(max(1, new_faces))
            die["raw_value"] = int(new_raw_val)
            die["raw_faces"] = int(max(1, new_raw_faces))
            die["reroll_count"] = int(die.get("reroll_count", 0) or 0) + 1
            rerolled_ids.append(die_id)

        state.total = int(_sum_base_dice(state.dice))
        if str(state.spec.get("display_kind", "") or "") == "d33":
            base_vals = [int(d.get("value", 0) or 0) for d in list(state.dice or []) if not bool(d.get("is_derived", False))]
            if len(base_vals) >= 2:
                state.total = int(base_vals[0] * 10 + base_vals[1])
        self._compute_success(state)
        state.reroll_history.append(
            {
                "action_id": str(action_id),
                "selected": list(chosen),
                "time": _now(),
            }
        )
        if rerolled_ids:
            from ..utility.event_bus import append_action
            player_obj = _resolve_player(game, actor_player_id or state.player_id)
            if player_obj is not None:
                label = str(action.get("label", "") or action_id or "Re-roll")
                reason = str(state.spec.get("reason", "") or "Roll")
                append_action(player_obj, f"{label}: re-rolled {reason}.")
        state.reroll_options = self._compute_reroll_options(game, state)
        try:
            event_system = getattr(game, "event_system", None)
            if event_system is not None:
                player_obj = _resolve_player(game, actor_player_id)
                event_system.publish(
                    "roll_rerolled",
                    player=player_obj,
                    roll_id=int(state.roll_id),
                    action_id=str(action_id),
                    selected=list(chosen),
                    dice=[int(d.get("value", 0) or 0) for d in list(state.dice or [])],
                    raw_dice=[
                        int(d.get("raw_value", d.get("value", 0)) or d.get("value", 0) or 0)
                        for d in list(state.dice or [])
                    ],
                    total=int(state.total or 0),
                    reason=str(state.spec.get("reason", "") or ""),
                )
        except Exception:
            pass
        if state.reroll_options:
            self._queue_reroll_decision(game, state)
        else:
            self._finalize_roll(game, state)
        return state

    def _finalize_roll(self, game: object, state: DiceRollState) -> None:
        if state.final:
            return
        state.final = True
        handler_key = str(state.spec.get("handler_key", "") or "")
        handler_payload = dict(state.spec.get("handler_payload", {}) or {})
        if handler_key:
            handler = get_roll_handler(handler_key)
            if handler is not None:
                try:
                    handler(game, state)
                except Exception:
                    pass
        self._publish_roll_made(game, state)
        # No further decisions; roll complete

    def _publish_roll_made(self, game: object, state: DiceRollState) -> None:
        if not bool(getattr(game, "is_authoritative", True)):
            return
        event_system = getattr(game, "event_system", None)
        if event_system is None:
            return
        spec = dict(getattr(state, "spec", {}) or {})
        player_obj = _resolve_player(game, state.player_id)
        unit_obj = _resolve_unit(game, spec.get("unit_id"))
        mapped_dice = [
            int(d.get("value", 0) or 0)
            for d in list(state.dice or [])
            if not bool(d.get("is_derived", False))
        ]
        raw_dice = [
            int(d.get("raw_value", d.get("value", 0)) or d.get("value", 0) or 0)
            for d in list(state.dice or [])
            if not bool(d.get("is_derived", False))
        ]
        mapping_mode = str(spec.get("value_mapping", "") or "").strip().lower()
        try:
            event_system.publish(
                "roll_made",
                player=player_obj,
                unit=unit_obj,
                roll_type=str(spec.get("roll_type", "") or ""),
                value=int(state.total or 0),
                reroll=None,
                dice=mapped_dice,
                raw_dice=raw_dice,
                dice_mapping=mapping_mode if mapping_mode else None,
                roll_id=int(state.roll_id),
                reason=str(spec.get("reason", "") or ""),
                needed=spec.get("target", spec.get("sum_target", None)),
                success=state.sum_success,
                faces=int(spec.get("faces", 6) or 6),
                dice_ids=[str(d.get("die_id", "")) for d in list(state.dice or [])],
                per_die_success=dict(state.per_die_success or {}),
                sum_success=state.sum_success,
                reroll_locked=True,
                kept_indices=list(spec.get("kept_indices", []) or []) if spec.get("kept_indices", None) is not None else None,
                dropped_indices=list(spec.get("dropped_indices", []) or []) if spec.get("dropped_indices", None) is not None else None,
                target_unit_ids=list(spec.get("target_unit_ids", []) or []),
            )
        except Exception:
            pass

    def export_roll_results(self, roll_id: int) -> dict:
        state = self.rolls.get(int(roll_id))
        if state is None:
            return {}
        return {
            "roll_id": int(state.roll_id),
            "faces": int(state.spec.get("faces", 6) or 6),
            "values": [int(d.get("value", 0) or 0) for d in list(state.dice or [])],
            "raw_values": [int(d.get("raw_value", d.get("value", 0)) or d.get("value", 0) or 0) for d in list(state.dice or [])],
            "dice": [dict(d) for d in list(state.dice or [])],
            "total": int(state.total or 0),
            "reroll_options": [dict(r) for r in list(state.reroll_options or [])],
            "derived_dice": [dict(d) for d in list(state.dice or []) if bool(d.get("is_derived", False))],
        }

    def add_derived_dice(self, roll_id: int, derived: list[dict]) -> None:
        """Append derived dice to a resolved roll and refresh success/ordering."""
        state = self.rolls.get(int(roll_id))
        if state is None or state.status != "rolled":
            return
        if not derived:
            return
        base_faces = int(state.spec.get("faces", 6) or 6)
        for entry in list(derived or []):
            try:
                dval = int(entry.get("value", 0) or 0)
            except Exception:
                dval = 0
            die = {
                "die_id": str(entry.get("die_id") or _die_id(state.roll_id, len(state.dice or []))),
                "value": int(dval),
                "faces": int(entry.get("faces", base_faces) or base_faces),
                "raw_value": int(entry.get("raw_value", dval) or dval),
                "raw_faces": int(entry.get("raw_faces", entry.get("faces", base_faces) or base_faces) or (entry.get("faces", base_faces) or base_faces)),
                "is_derived": True,
                "derived_kind": entry.get("derived_kind"),
                "reroll_count": 0,
                "rerolled_from": None,
            }
            state.dice.append(die)
        state.total = int(_sum_base_dice(state.dice))
        if str(state.spec.get("display_kind", "") or "") == "d33":
            base_vals = [int(d.get("value", 0) or 0) for d in list(state.dice or []) if not bool(d.get("is_derived", False))]
            if len(base_vals) >= 2:
                state.total = int(base_vals[0] * 10 + base_vals[1])
        self._compute_success(state)


# Ensure default roll handlers are registered.
from . import roll_handlers  # noqa: E402,F401
