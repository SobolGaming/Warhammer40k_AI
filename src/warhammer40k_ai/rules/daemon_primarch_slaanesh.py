from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.aura_utils import unit_within_range_of_unit


@dataclass(frozen=True)
class DaemonPrimarchSlaaneshOption:
    key: str
    name: str
    summary: str


DAEMON_PRIMARCH_NAME = "Daemon Primarch of Slaanesh"
BEGUILING_FORM_NAME = "Beguiling Form"
DAEMONIC_SPEED_NAME = "Daemonic Speed"
ENTHRALLING_HYPNOSIS_NAME = "Enthralling Hypnosis (Aura)"

KEY_BEGUILING_FORM = "BEGUILING_FORM"
KEY_DAEMONIC_SPEED = "DAEMONIC_SPEED"
KEY_ENTHRALLING_HYPNOSIS = "ENTHRALLING_HYPNOSIS"

BEGUILING_FORM = DaemonPrimarchSlaaneshOption(
    key=KEY_BEGUILING_FORM,
    name=BEGUILING_FORM_NAME,
    summary="Each time a model makes an attack that targets this model, subtract 1 from the Hit roll.",
)
DAEMONIC_SPEED = DaemonPrimarchSlaaneshOption(
    key=KEY_DAEMONIC_SPEED,
    name=DAEMONIC_SPEED_NAME,
    summary="This model has the Fights First ability.",
)
ENTHRALLING_HYPNOSIS = DaemonPrimarchSlaaneshOption(
    key=KEY_ENTHRALLING_HYPNOSIS,
    name=ENTHRALLING_HYPNOSIS_NAME,
    summary='Enemy units within 6" that are selected to Fall Back must pass a Leadership test or remain stationary.',
)

DAEMON_PRIMARCH_SLAANESH_OPTIONS: tuple[DaemonPrimarchSlaaneshOption, ...] = (
    BEGUILING_FORM,
    DAEMONIC_SPEED,
    ENTHRALLING_HYPNOSIS,
)

_ACTIVE_KEY = "daemon_primarch_slaanesh_active_key"
_ACTIVE_START_ROUND = "daemon_primarch_slaanesh_active_start_round"
_ACTIVE_UNTIL_ROUND = "daemon_primarch_slaanesh_active_until_round"
_ACTIVE_UNTIL_PLAYER = "daemon_primarch_slaanesh_active_until_player_id"


def _norm_name(text: str) -> str:
    return (text or "").replace("\u2019", "'").replace("\u00e2\u20ac\u2122", "'").strip().lower()


def _unit_has_daemon_primarch(unit) -> bool:
    if unit is None:
        return False
    try:
        for ab in (getattr(unit, "possible_abilities", []) or []):
            if _norm_name(getattr(ab, "name", "")) == _norm_name(DAEMON_PRIMARCH_NAME):
                return True
    except Exception:
        return False
    return False


def _get_game_for_unit(unit):
    try:
        army = unit.get_parent_army()
        return getattr(getattr(army, "player", None), "game", None)
    except Exception:
        return None


def _ensure_special_rules(unit) -> dict:
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    return sr


def _invalidate_daemon_primarch_caches(unit) -> None:
    try:
        root = unit.get_attached_unit_root()
    except Exception:
        root = unit
    cache = getattr(root, "_ability_cache", None)
    if not isinstance(cache, dict):
        return
    for key in list(cache.keys()):
        if key == "fight_first" or str(key).startswith("target_hit_penalty:"):
            cache.pop(key, None)
    root._ability_cache = cache


def ability_name_to_key(name: str) -> Optional[str]:
    norm = _norm_name(name)
    if norm == _norm_name(BEGUILING_FORM_NAME):
        return KEY_BEGUILING_FORM
    if norm == _norm_name(DAEMONIC_SPEED_NAME):
        return KEY_DAEMONIC_SPEED
    if norm == _norm_name(ENTHRALLING_HYPNOSIS_NAME):
        return KEY_ENTHRALLING_HYPNOSIS
    return None


def get_active_daemon_primarch_key(unit, *, game=None, battle_round: Optional[int] = None) -> Optional[str]:
    if unit is None:
        return None
    if not _unit_has_daemon_primarch(unit):
        return None
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        return None
    key = str(sr.get(_ACTIVE_KEY, "") or "").strip().upper()
    if not key:
        return None
    stored_until = sr.get(_ACTIVE_UNTIL_ROUND)
    if battle_round is None:
        if game is None:
            game = _get_game_for_unit(unit)
        try:
            battle_round = int(getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = None
    if battle_round is not None and stored_until is not None:
        try:
            if int(battle_round or 0) > int(stored_until or 0):
                return None
        except Exception:
            return None
    return key


def unit_has_active_daemon_primarch(unit, key: str, *, game=None, battle_round: Optional[int] = None) -> bool:
    if unit is None:
        return False
    key = str(key or "").strip().upper()
    if not key:
        return False
    return get_active_daemon_primarch_key(unit, game=game, battle_round=battle_round) == key


def set_active_daemon_primarch_slaanesh(
    unit,
    key: str,
    *,
    start_round: int,
    expires_round: int,
    opponent_player_id: Optional[str] = None,
) -> None:
    if unit is None:
        return
    if not _unit_has_daemon_primarch(unit):
        return
    sr = _ensure_special_rules(unit)
    sr[_ACTIVE_KEY] = str(key or "").strip().upper()
    sr[_ACTIVE_START_ROUND] = int(start_round or 0)
    sr[_ACTIVE_UNTIL_ROUND] = int(expires_round or 0)
    sr[_ACTIVE_UNTIL_PLAYER] = str(opponent_player_id or "")
    unit.special_rules = sr
    _invalidate_daemon_primarch_caches(unit)


def clear_active_daemon_primarch_slaanesh(unit) -> None:
    if unit is None:
        return
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        return
    sr.pop(_ACTIVE_KEY, None)
    sr.pop(_ACTIVE_START_ROUND, None)
    sr.pop(_ACTIVE_UNTIL_ROUND, None)
    sr.pop(_ACTIVE_UNTIL_PLAYER, None)
    unit.special_rules = sr
    _invalidate_daemon_primarch_caches(unit)


def _unit_is_valid_daemon_primarch_source(unit) -> bool:
    if unit is None:
        return False
    if not _unit_has_daemon_primarch(unit):
        return False
    try:
        if hasattr(unit, "is_alive") and callable(unit.is_alive):
            if not unit.is_alive():
                return False
    except Exception:
        return False
    try:
        if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
            return False
    except Exception:
        return False
    try:
        if str(getattr(unit, "reserve_status", "deployed")) != "deployed":
            return False
    except Exception:
        pass
    return True


def daemon_primarch_slaanesh_units(army) -> list:
    if army is None:
        return []
    units = []
    for unit in list(getattr(army, "units", []) or []):
        if unit is None:
            continue
        if _unit_has_daemon_primarch(unit):
            units.append(unit)
    return units


def daemon_primarch_slaanesh_selectable_units(army) -> list:
    if army is None:
        return []
    units = []
    for unit in list(getattr(army, "units", []) or []):
        if not _unit_is_valid_daemon_primarch_source(unit):
            continue
        units.append(unit)
    return units


def enthralling_hypnosis_sources_for_unit(unit, *, game_map=None, battle_round: Optional[int] = None) -> list:
    if unit is None:
        return []
    if game_map is None:
        try:
            game = _get_game_for_unit(unit)
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
    if game_map is None:
        return []
    sources = []
    for enemy in list(game_map.get_enemy_units(unit) or []):
        if not _unit_is_valid_daemon_primarch_source(enemy):
            continue
        if not unit_has_active_daemon_primarch(enemy, KEY_ENTHRALLING_HYPNOSIS, battle_round=battle_round):
            continue
        try:
            if unit_within_range_of_unit(enemy, unit, 6.0, use_attached_aggregate=True):
                sources.append(enemy)
        except Exception:
            continue
    return sources


class DaemonPrimarchSlaaneshManager:
    """Fulgrim: select one Daemon Primarch of Slaanesh ability in opponent Command phase."""

    def __init__(self, army=None):
        self.army = army

    def get_daemon_primarch_units(self) -> list:
        return daemon_primarch_slaanesh_selectable_units(self.army)

    def on_opponent_command_phase_start(self, opponent_player, *, game=None) -> None:
        if self.army is None:
            return
        if game is None:
            try:
                game = getattr(getattr(self.army, "player", None), "game", None)
            except Exception:
                game = None
        units = daemon_primarch_slaanesh_units(self.army)
        if not units:
            return
        try:
            br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        except Exception:
            br = 0
        opp_id = getattr(opponent_player, "id", None) if opponent_player is not None else None
        expires_round = int(br or 0) + 1 if br else 0

        for unit in units:
            clear_active_daemon_primarch_slaanesh(unit)
            if game is None or not bool(getattr(game, "is_authoritative", True)):
                continue
            if not _unit_is_valid_daemon_primarch_source(unit):
                continue
            try:
                from ..engine.decision_kinds import DECISION_CHOOSE_DAEMON_PRIMARCH_SLAANESH
                from ..engine.decisions import DecisionOption, DecisionRequest
                from ..utility.entity_ids import get_entity_id
            except Exception:
                continue
            unit_id = get_entity_id(unit)
            queue = getattr(game, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_DAEMON_PRIMARCH_SLAANESH:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("unit_id", "")) == str(unit_id):
                        break
                else:
                    req_options = [
                        DecisionOption.create(
                            opt.name,
                            payload={"choice_key": opt.key, "summary": opt.summary, "unit_id": unit_id},
                        )
                        for opt in DAEMON_PRIMARCH_SLAANESH_OPTIONS
                    ]
                    if not req_options:
                        continue
                    req = DecisionRequest.create(
                        DECISION_CHOOSE_DAEMON_PRIMARCH_SLAANESH,
                        "Select Daemon Primarch of Slaanesh ability.",
                        player_id=getattr(getattr(self.army, "player", None), "id", None),
                        options=req_options,
                        context={
                            "unit_id": unit_id,
                            "battle_round": int(br or 0),
                            "opponent_player_id": opp_id,
                            "expires_round": int(expires_round or 0),
                        },
                    )
                    if hasattr(game, "request_decision"):
                        game.request_decision(req)
