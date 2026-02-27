from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.ability_support import ABILITY_DOCTRINA_IMPERATIVES, army_has_ability_id


@dataclass(frozen=True)
class DoctrinaImperative:
    key: str
    name: str
    summary: str


PROTECTOR_IMPERATIVE = DoctrinaImperative(
    key="PROTECTOR",
    name="Protector Imperative",
    summary=(
        "Ranged weapons gain Heavy; improve BS by 1; melee attacks targeting affected "
        "Battleline/near-Battleline units suffer -1 to hit."
    ),
)
CONQUEROR_IMPERATIVE = DoctrinaImperative(
    key="CONQUEROR",
    name="Conqueror Imperative",
    summary=(
        "Ranged weapons gain Assault; improve WS by 1; attacks by affected "
        "Battleline/near-Battleline units improve AP by 1."
    ),
)

DOCTRINA_OPTIONS: tuple[DoctrinaImperative, ...] = (
    PROTECTOR_IMPERATIVE,
    CONQUEROR_IMPERATIVE,
)
DOCTRINA_BY_KEY = {d.key: d for d in DOCTRINA_OPTIONS}


class DoctrinaImperativesManager:
    """
    Adeptus Mechanicus army rule: Doctrina Imperatives.

    At the start of each battle round, select one Imperative. It is active for
    the entire battle round and affects units with the Doctrina Imperatives ability.
    """

    def __init__(self, army=None):
        self.army = army
        self.active_imperative_key: Optional[str] = None
        self.active_round: Optional[int] = None

    def _army_has_doctrina(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "ADM":
            return False
        if army_has_ability_id(self.army, ABILITY_DOCTRINA_IMPERATIVES):
            return True
        # Fallback: detect any unit with the ability text.
        for unit in list(getattr(self.army, "units", []) or []):
            if self._unit_has_doctrina(unit):
                return True
        return False

    def _unit_has_doctrina(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "has_doctrina_imperatives") and unit.has_doctrina_imperatives():
                return True
        except Exception:
            pass
        try:
            found, _ab = unit._find_ability_with_patterns(["doctrina imperatives"])
            if found:
                return True
        except Exception:
            pass
        for ab in (list(getattr(unit, "possible_abilities", []) or []) + list(getattr(unit, "abilities", []) or [])):
            try:
                if isinstance(ab, str):
                    name = ab
                else:
                    name = getattr(ab, "name", "")
                if "doctrina imperatives" in str(name or "").lower():
                    return True
            except Exception:
                continue
        return False

    def _resolve_game(self, unit=None, game=None):
        if game is not None:
            return game
        if unit is not None:
            try:
                army = unit.get_parent_army()
            except Exception:
                army = None
        else:
            army = self.army
        try:
            return getattr(getattr(army, "player", None), "game", None)
        except Exception:
            return None

    def _is_active_round(self, game=None) -> bool:
        if self.active_round is None:
            return False
        if game is None:
            return True
        try:
            return int(getattr(game, "turn", 0) or 0) == int(self.active_round)
        except Exception:
            return False

    def get_active_imperative(self, *, game=None) -> Optional[DoctrinaImperative]:
        if not self._army_has_doctrina():
            return None
        if not self.active_imperative_key:
            return None
        if not self._is_active_round(game=game):
            return None
        return DOCTRINA_BY_KEY.get(self.active_imperative_key)

    def get_active_imperative_for_unit(self, unit, *, game=None) -> Optional[DoctrinaImperative]:
        if not self._unit_has_doctrina(unit):
            return None
        game = self._resolve_game(unit=unit, game=game)
        return self.get_active_imperative(game=game)

    def _haloscreed_cognitive_reinforcement_applies(self, unit) -> bool:
        if self.army is None or unit is None:
            return False
        adm_mgr = getattr(self.army, "adeptus_mechanicus_detachments", None)
        if adm_mgr is None:
            return False
        checker = getattr(adm_mgr, "haloscreed_cognitive_reinforcement_applies", None)
        if not callable(checker):
            return False
        return bool(checker(unit))

    def _skitarii_cantic_thrallnet_applies(self, unit, *, game=None) -> bool:
        if self.army is None or unit is None:
            return False
        adm_mgr = getattr(self.army, "adeptus_mechanicus_detachments", None)
        if adm_mgr is None:
            return False
        checker = getattr(adm_mgr, "skitarii_cantic_thrallnet_applies", None)
        if not callable(checker):
            return False
        return bool(checker(unit, game=game))

    def get_active_imperative_keys_for_unit(self, unit, *, game=None) -> set[str]:
        active_keys: set[str] = set()
        game = self._resolve_game(unit=unit, game=game)
        if self._haloscreed_cognitive_reinforcement_applies(unit) or self._skitarii_cantic_thrallnet_applies(unit, game=game):
            active_keys.add(PROTECTOR_IMPERATIVE.key)
            active_keys.add(CONQUEROR_IMPERATIVE.key)
        if not self._unit_has_doctrina(unit):
            return active_keys
        imperative = self.get_active_imperative(game=game)
        if imperative is not None:
            active_keys.add(str(imperative.key))
        return active_keys

    def select_imperative(self, imperative, *, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_doctrina():
            return False
        key = getattr(imperative, "key", imperative)
        key = str(key or "").strip().upper()
        if key not in DOCTRINA_BY_KEY:
            return False
        self.active_imperative_key = key
        if battle_round is not None:
            try:
                self.active_round = int(battle_round)
            except Exception:
                pass
        return True

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self._army_has_doctrina():
            return
        try:
            br = int(battle_round or 0)
        except Exception:
            return
        if self.active_round == br:
            return
        if game is not None:
            if not bool(getattr(game, "is_authoritative", True)):
                return
            try:
                from ..engine.decision_kinds import DECISION_CHOOSE_DOCTRINA
                from ..engine.decisions import DecisionOption, DecisionRequest
                from ..utility.entity_ids import get_entity_id
            except Exception:
                return
            army_id = get_entity_id(self.army) if self.army is not None else None
            queue = getattr(game, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_DOCTRINA:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("army_id", "")) == str(army_id) and int(ctx.get("battle_round", br) or br) == br:
                        return
            options = list(DOCTRINA_OPTIONS)
            req_options = [
                DecisionOption.create(
                    opt.name,
                    payload={"choice_key": opt.key, "summary": opt.summary, "army_id": army_id},
                )
                for opt in options
            ]
            if not req_options:
                return
            req = DecisionRequest.create(
                DECISION_CHOOSE_DOCTRINA,
                "Select a Doctrina Imperative.",
                player_id=getattr(getattr(self.army, "player", None), "id", None),
                options=req_options,
                context={"army_id": army_id, "battle_round": br},
            )
            if hasattr(game, "request_decision"):
                game.request_decision(req)
            return
        return

    def _unit_is_adm_battleline(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if not bool(getattr(unit, "is_battleline", False)):
                return False
        except Exception:
            return False
        try:
            return bool(unit.has_any_keyword("ADEPTUS MECHANICUS"))
        except Exception:
            return False

    def _unit_in_battleline_network(self, unit, *, game=None, game_map=None) -> bool:
        if unit is None:
            return False
        try:
            if bool(getattr(unit, "is_battleline", False)):
                return True
        except Exception:
            pass
        if game_map is None:
            game = self._resolve_game(unit=unit, game=game)
            game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return False
        try:
            friends = list(game_map.get_friendly_units(unit))
        except Exception:
            friends = []
        for friend in friends:
            if friend is None or friend is unit:
                continue
            try:
                if hasattr(friend, "is_alive") and callable(friend.is_alive) and not friend.is_alive():
                    continue
            except Exception:
                pass
            if not self._unit_is_adm_battleline(friend):
                continue
            try:
                dist = float(game_map.get_distance_between_units(unit, friend))
            except Exception:
                dist = 999.0
            if dist <= 6.0:
                return True
        return False

    def protector_melee_hit_penalty_applies(self, target_unit, *, game=None, game_map=None) -> bool:
        active_keys = self.get_active_imperative_keys_for_unit(target_unit, game=game)
        if PROTECTOR_IMPERATIVE.key not in active_keys:
            return False
        return self._unit_in_battleline_network(target_unit, game=game, game_map=game_map)

    def conqueror_ap_bonus_applies(self, attacker_unit, *, game=None, game_map=None) -> bool:
        active_keys = self.get_active_imperative_keys_for_unit(attacker_unit, game=game)
        if CONQUEROR_IMPERATIVE.key not in active_keys:
            return False
        return self._unit_in_battleline_network(attacker_unit, game=game, game_map=game_map)

    def protector_heavy_applies(self, attacker_unit, *, game=None) -> bool:
        active_keys = self.get_active_imperative_keys_for_unit(attacker_unit, game=game)
        if PROTECTOR_IMPERATIVE.key not in active_keys:
            return False
        return True

    def conqueror_assault_applies(self, attacker_unit, *, game=None) -> bool:
        active_keys = self.get_active_imperative_keys_for_unit(attacker_unit, game=game)
        if CONQUEROR_IMPERATIVE.key not in active_keys:
            return False
        return True
