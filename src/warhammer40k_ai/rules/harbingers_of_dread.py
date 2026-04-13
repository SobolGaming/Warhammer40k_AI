from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Iterable

from ..utility.ability_support import ABILITY_HARBINGERS_OF_DREAD, army_has_ability_id
from ..utility.dice import get_roll


@dataclass(frozen=True)
class DreadAbility:
    key: str
    name: str
    summary: str
    roll: Optional[int] = None
    is_aura: bool = False


DEATHLY_TERROR = DreadAbility(
    key="DEATHLY_TERROR",
    name="Deathly Terror (Aura)",
    summary="Enemy units within 9\" worsen Leadership by 1.",
    is_aura=True,
)
DESPAIR = DreadAbility(
    key="DESPAIR",
    name="Despair (Aura)",
    summary="Enemy units within 9\" worsen Leadership by 1 (cumulative with Deathly Terror).",
    roll=1,
    is_aura=True,
)
DOOM = DreadAbility(
    key="DOOM",
    name="Doom",
    summary="Add 1 to Wound rolls when targeting Battle-shocked units.",
    roll=2,
)
DARKNESS = DreadAbility(
    key="DARKNESS",
    name="Darkness",
    summary="Attacks against this model suffer -1 to hit if attacker is Battle-shocked or >18\" away.",
    roll=3,
)
DISMAY = DreadAbility(
    key="DISMAY",
    name="Dismay (Aura)",
    summary="Opponent Command phase: below Starting Strength enemy units within 9\" must take Battle-shock.",
    roll=4,
    is_aura=True,
)
DELIRIUM = DreadAbility(
    key="DELIRIUM",
    name="Delirium (Aura)",
    summary="Below Half-strength enemy units within 9\" that fail Battle-shock suffer D3 mortals.",
    roll=5,
    is_aura=True,
)
DOMINION = DreadAbility(
    key="DOMINION",
    name="Dominion",
    summary="Add 3\" to the range of this model's Aura abilities.",
    roll=6,
)

ROLLABLE_DREADS: tuple[DreadAbility, ...] = (
    DESPAIR,
    DOOM,
    DARKNESS,
    DISMAY,
    DELIRIUM,
    DOMINION,
)

DREAD_BY_ROLL = {d.roll: d for d in ROLLABLE_DREADS if d.roll is not None}
DREAD_DEFINITIONS = {d.key: d for d in (DEATHLY_TERROR,) + ROLLABLE_DREADS}


class HarbingersOfDreadManager:
    """
    Chaos Knights army rule: Harbingers of Dread.

    Deathly Terror is always active. At the start of battle rounds 1, 3, and 5,
    select one additional Dread ability or roll 2D6 to randomly select two.
    """

    def __init__(self, army=None):
        self.army = army
        self.active_dread_keys: set[str] = {DEATHLY_TERROR.key}
        self.last_selection_round: Optional[int] = None

    def _army_has_harbingers(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id:
            return faction_id == "QT"
        if army_has_ability_id(self.army, ABILITY_HARBINGERS_OF_DREAD):
            return True
        if not faction_id:
            for unit in list(getattr(self.army, "units", []) or []):
                if self._unit_is_chaos_knights(unit):
                    return True
        return False

    def _unit_is_chaos_knights(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return bool(unit.has_any_keyword("CHAOS KNIGHTS"))
        except Exception:
            return False

    def _unit_is_valid_source(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_is_chaos_knights(unit):
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            return False
        try:
            if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
                return False
        except Exception:
            pass
        return True

    def get_active_dread_abilities(self) -> list[DreadAbility]:
        out = []
        for key in sorted(self.active_dread_keys):
            if key in DREAD_DEFINITIONS:
                out.append(DREAD_DEFINITIONS[key])
        return out

    def get_available_dread_abilities(self) -> list[DreadAbility]:
        return [d for d in ROLLABLE_DREADS if d.key not in self.active_dread_keys]

    def _extra_dread_keys_for_source_unit(self, unit) -> set[str]:
        if unit is None or not self._unit_is_chaos_knights(unit):
            return set()
        try:
            unit_army = unit.get_parent_army()
        except Exception:
            unit_army = None
        if unit_army is not self.army:
            return set()
        ck_mgr = getattr(unit_army, "chaos_knights_detachments", None) if unit_army is not None else None
        getter = getattr(ck_mgr, "helhunt_extra_dread_keys_for_unit", None) if ck_mgr is not None else None
        if not callable(getter):
            return set()
        keys: set[str] = set()
        for value in list(getter(unit) or []):
            key = str(value or "").strip().upper()
            if key in DREAD_DEFINITIONS:
                keys.add(key)
        return keys

    def is_dread_active(self, key: str, *, unit=None) -> bool:
        if not self._army_has_harbingers():
            return False
        if not key:
            return False
        key_upper = str(key).strip().upper()
        if unit is not None and not self._unit_is_chaos_knights(unit):
            return False
        if key_upper in {k.upper() for k in self.active_dread_keys}:
            return True
        if unit is None:
            return False
        return key_upper in self._extra_dread_keys_for_source_unit(unit)

    def get_aura_range(self, *, unit=None) -> float:
        return 12.0 if self.is_dread_active(DOMINION.key, unit=unit) else 9.0

    def select_dread_ability(self, ability, *, battle_round: Optional[int] = None) -> bool:
        if not self._army_has_harbingers():
            return False
        if ability is None:
            return False
        key = getattr(ability, "key", ability)
        key = str(key or "").strip().upper()
        if key == DEATHLY_TERROR.key:
            return False
        if key not in DREAD_DEFINITIONS:
            return False
        if key in self.active_dread_keys:
            return False
        self.active_dread_keys.add(key)
        if battle_round is not None:
            try:
                self.last_selection_round = int(battle_round)
            except Exception:
                pass
        return True

    def roll_dread_abilities(self, *, battle_round: Optional[int] = None) -> dict:
        if not self._army_has_harbingers():
            return {"rolls": [], "selected": []}

        rolls = [int(get_roll("D6")), int(get_roll("D6"))]
        selected = []
        for roll in rolls:
            dread = DREAD_BY_ROLL.get(int(roll))
            if dread is None:
                continue
            if dread.key in self.active_dread_keys:
                continue
            self.active_dread_keys.add(dread.key)
            selected.append(dread)

        if battle_round is not None:
            try:
                self.last_selection_round = int(battle_round)
            except Exception:
                pass

        return {"rolls": rolls, "selected": selected}

    def apply_roll_results(
        self,
        *,
        rolls: Optional[Iterable[int]] = None,
        selected_keys: Optional[Iterable[str]] = None,
        battle_round: Optional[int] = None,
    ) -> dict:
        if not self._army_has_harbingers():
            return {"rolls": [], "selected": []}
        roll_list = [int(r) for r in list(rolls or []) if r is not None]
        selected = []
        if selected_keys:
            for key in list(selected_keys or []):
                k = str(key or "").strip().upper()
                if not k or k in self.active_dread_keys:
                    continue
                dread = DREAD_DEFINITIONS.get(k)
                if dread is None:
                    continue
                self.active_dread_keys.add(dread.key)
                selected.append(dread)
        if roll_list:
            for roll in roll_list:
                dread = DREAD_BY_ROLL.get(int(roll))
                if dread is None:
                    continue
                if dread.key in self.active_dread_keys:
                    continue
                self.active_dread_keys.add(dread.key)
                selected.append(dread)
        if battle_round is not None:
            try:
                self.last_selection_round = int(battle_round)
            except Exception:
                pass
        return {"rolls": roll_list, "selected": selected}

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self._army_has_harbingers():
            return
        try:
            br = int(battle_round or 0)
        except Exception:
            return
        if br not in (1, 3, 5):
            return
        if self.last_selection_round == br:
            return
        if not self.get_available_dread_abilities():
            self.last_selection_round = br
            return

        player = None
        try:
            player = getattr(self.army, "player", None)
        except Exception:
            player = None

        if game is not None:
            if not bool(getattr(game, "is_authoritative", True)):
                return
            try:
                from ..engine.decision_kinds import DECISION_CHOOSE_HARBINGER
                from ..engine.decisions import DecisionOption, DecisionRequest
                from ..utility.entity_ids import get_entity_id
            except Exception:
                return
            army_id = get_entity_id(self.army) if self.army is not None else None
            queue = getattr(game, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_HARBINGER:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("army_id", "")) == str(army_id) and int(ctx.get("battle_round", br) or br) == br:
                        return
            available = list(self.get_available_dread_abilities())
            if not available:
                return
            req_options = []
            try:
                from ..utility.dice import get_roll
                rolls = [int(get_roll("D6")), int(get_roll("D6"))]
            except Exception:
                rolls = []
            selected_keys = []
            if rolls:
                for roll in rolls:
                    dread = DREAD_BY_ROLL.get(int(roll))
                    if dread is None or dread.key in self.active_dread_keys:
                        continue
                    if dread.key not in selected_keys:
                        selected_keys.append(dread.key)
            req_options.append(
                DecisionOption.create(
                    "Roll 2D6 (randomly select two)",
                    payload={
                        "choice_key": "ROLL",
                        "random": True,
                        "rolls": rolls,
                        "selected_keys": list(selected_keys),
                        "army_id": army_id,
                    },
                )
            )
            for dread in available:
                req_options.append(
                    DecisionOption.create(
                        dread.name,
                        payload={"choice_key": dread.key, "summary": dread.summary, "army_id": army_id},
                    )
                )
            req = DecisionRequest.create(
                DECISION_CHOOSE_HARBINGER,
                "Select Harbingers of Dread.",
                player_id=getattr(player, "id", None),
                options=req_options,
                context={"army_id": army_id, "battle_round": br},
            )
            if hasattr(game, "request_decision"):
                game.request_decision(req)
            return
        return

    @staticmethod
    def leadership_auras_for_unit(unit, *, game_map=None) -> set[str]:
        if unit is None:
            return set()

        if game_map is None:
            try:
                army = unit.get_parent_army()
                game = getattr(getattr(army, "player", None), "game", None)
                game_map = getattr(game, "map", None) if game is not None else None
            except Exception:
                game_map = None

        if game_map is None:
            return set()

        try:
            enemy_units = list(game_map.get_enemy_units(unit))
        except Exception:
            try:
                unit_army = unit.get_parent_army()
            except Exception:
                unit_army = None
            try:
                enemy_units = [
                    u for u in list(getattr(game_map, "units", []) or [])
                    if getattr(u, "get_parent_army", lambda: None)() is not unit_army
                ]
            except Exception:
                enemy_units = []

        if not enemy_units:
            return set()

        try:
            from ..utility.aura_utils import unit_within_range_of_point_3d, unit_within_range_of_unit
            from ..utility.entity_ids import get_entity_id
        except Exception:
            return set()

        active: set[str] = set()
        checked_armies: set[str] = set()
        for enemy in enemy_units:
            try:
                enemy_army = enemy.get_parent_army()
            except Exception:
                enemy_army = None
            if enemy_army is None:
                continue
            try:
                key = get_entity_id(enemy_army)
            except Exception:
                key = ""
            if key in checked_armies:
                continue
            checked_armies.add(key)

            mgr = getattr(enemy_army, "harbingers_of_dread", None)
            if mgr is None or not getattr(mgr, "_army_has_harbingers", lambda: False)():
                continue

            for source in list(getattr(enemy_army, "units", []) or []):
                if not mgr._unit_is_valid_source(source):
                    continue
                aura_range = mgr.get_aura_range(unit=source)
                try:
                    if unit_within_range_of_unit(source, unit, aura_range, use_attached_aggregate=True):
                        if mgr.is_dread_active(DEATHLY_TERROR.key, unit=source):
                            active.add(DEATHLY_TERROR.key)
                        if mgr.is_dread_active(DESPAIR.key, unit=source):
                            active.add(DESPAIR.key)
                        break
                except Exception:
                    continue

            enemy_player = getattr(enemy_army, "player", None)
            if enemy_player is None:
                continue
            for objective in list(getattr(game_map, "objectives", []) or []):
                if objective is None:
                    continue
                loc = getattr(objective, "location", None)
                if loc is None or bool(getattr(loc, "removed", False)):
                    continue
                sticky_source = str(getattr(loc, "sticky_source", "") or "").strip().lower()
                if sticky_source != "traitoris_tyrants_shadow":
                    continue
                if getattr(loc, "controlling_player", None) is not enemy_player:
                    continue
                try:
                    point = (float(getattr(loc, "x", 0.0)), float(getattr(loc, "y", 0.0)))
                except (TypeError, ValueError):
                    continue
                if not unit_within_range_of_point_3d(unit, point, 9.0, use_attached_aggregate=True):
                    continue
                if mgr.is_dread_active(DEATHLY_TERROR.key):
                    active.add(DEATHLY_TERROR.key)
                break

        return active
