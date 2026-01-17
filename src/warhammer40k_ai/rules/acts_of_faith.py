from __future__ import annotations

from typing import Optional, Tuple

from ..utility.ability_support import ABILITY_ACTS_OF_FAITH, army_has_ability_id
from ..utility.dice import get_roll, get_dice_roll
from ..utility.event_bus import append_dice
from ..utility.aura_utils import (
    unit_within_range_of_unit,
    distance_between_models_bases_3d,
)


class ActsOfFaithManager:
    """
    Adepta Sororitas army rule: Acts of Faith.

    - Maintain a shared Miracle dice pool.
    - Gain dice at battle round start and when Adepta Sororitas units are destroyed.
    - Allow each unit to perform one Act of Faith per phase (one die substitution).
    """

    def __init__(self, army=None):
        self.army = army
        self.miracle_dice: list[int] = []
        self._used_in_phase: dict[str, str] = {}

    def _army_has_rule(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "AS":
            return False
        if army_has_ability_id(self.army, ABILITY_ACTS_OF_FAITH):
            return True
        if not faction_id:
            for unit in list(getattr(self.army, "units", []) or []):
                if self._unit_has_rule(unit):
                    return True
        return False

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        try:
            return unit.get_parent_army() is self.army
        except Exception:
            return False

    @staticmethod
    def _unit_id(unit) -> str:
        if unit is None:
            return ""
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            return str(getattr(root, "_id", None) or id(root))
        except Exception:
            return str(id(root))

    @staticmethod
    def _phase_key(game) -> str:
        try:
            phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            phase = ""
        try:
            player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            player = None
        try:
            pid = str(getattr(player, "name", "") or getattr(player, "_id", "") or "")
        except Exception:
            pid = ""
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        if not phase:
            phase = "UNKNOWN"
        return f"{turn}:{pid}:{phase}"

    def _unit_has_rule(self, unit) -> bool:
        if unit is None:
            return False
        try:
            for ab in list(getattr(unit, "possible_abilities", []) or []):
                if str(getattr(ab, "name", "") or "").strip().lower() == "acts of faith":
                    return True
        except Exception:
            pass
        try:
            if unit.has_any_keyword("ADEPTA SORORITAS"):
                return True
        except Exception:
            pass
        return False

    def _unit_has_litany_of_deeds(self, unit) -> bool:
        if unit is None:
            return False
        try:
            for ab in list(getattr(unit, "possible_abilities", []) or []):
                name = str(getattr(ab, "name", "") or "").strip().lower()
                if name == "litany of deeds":
                    return True
        except Exception:
            pass
        return False

    def _iter_litany_sources(self) -> list:
        sources = []
        for unit in list(getattr(self.army, "units", []) or []):
            try:
                if not self._unit_has_litany_of_deeds(unit):
                    continue
            except Exception:
                continue
            try:
                if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                    continue
            except Exception:
                continue
            try:
                if not bool(getattr(unit, "deployed", True)):
                    continue
            except Exception:
                pass
            try:
                if bool(getattr(unit, "is_embarked", False)):
                    continue
            except Exception:
                pass
            sources.append(unit)
        return sources

    def _model_within_range_of_unit(self, source_unit, target_model, radius: float) -> bool:
        try:
            r = float(radius)
        except Exception:
            return False
        if r < 0:
            return False
        if source_unit is None or target_model is None:
            return False
        try:
            models = list(source_unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(source_unit, "models", []) or [])
        for sm in models:
            try:
                if not getattr(sm, "is_alive", True):
                    continue
            except Exception:
                continue
            try:
                if distance_between_models_bases_3d(sm, target_model) <= r + 1e-6:
                    return True
            except Exception:
                continue
        return False

    def _litany_allows_reroll(self, destroyed_unit=None, destroyed_model=None) -> bool:
        sources = self._iter_litany_sources()
        if not sources:
            return False
        for source in sources:
            try:
                if destroyed_model is not None and self._model_within_range_of_unit(source, destroyed_model, 12.0):
                    return True
            except Exception:
                pass
            try:
                if destroyed_unit is not None and unit_within_range_of_unit(source, destroyed_unit, 12.0):
                    return True
            except Exception:
                pass
        return False

    def can_use_act_of_faith(self, unit, *, game=None) -> bool:
        if not self._army_has_rule():
            return False
        if not self._unit_in_army(unit):
            return False
        if not self._unit_has_rule(unit):
            return False
        try:
            if bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            pass
        if not self.miracle_dice:
            return False
        phase_key = self._phase_key(game)
        uid = self._unit_id(unit)
        if phase_key and self._used_in_phase.get(uid) == phase_key:
            return False
        return True

    def _mark_used(self, unit, *, game=None) -> None:
        uid = self._unit_id(unit)
        phase_key = self._phase_key(game)
        if uid:
            self._used_in_phase[uid] = phase_key

    def _choose_miracle_die(self, unit, *, roll_type: str, dice_count: int, die_faces: int, game=None, needed=None) -> Optional[int]:
        if not self.can_use_act_of_faith(unit, game=game):
            return None
        pool = list(self.miracle_dice)
        if not pool:
            return None
        player = getattr(self.army, "player", None) if self.army is not None else None
        provider = getattr(getattr(game, "map", None), "miracle_dice_provider", None) if game is not None else None
        if callable(provider):
            try:
                chosen = provider(
                    player=player,
                    unit=unit,
                    roll_type=str(roll_type or ""),
                    dice_count=int(dice_count or 1),
                    die_faces=int(die_faces or 6),
                    pool=list(pool),
                    needed=needed,
                )
            except Exception:
                chosen = None
            try:
                chosen_val = int(chosen)
            except Exception:
                chosen_val = None
            if chosen_val is not None and chosen_val in pool:
                return chosen_val
            return None
        return None

    def _consume_miracle_die(self, unit, value: int, *, roll_type: str, game=None) -> bool:
        try:
            idx = self.miracle_dice.index(int(value))
        except Exception:
            return False
        self.miracle_dice.pop(idx)
        self._mark_used(unit, game=game)
        try:
            rt = str(roll_type or "").strip().lower()
            if rt not in {"advance", "charge", "hit", "wound", "save", "damage"}:
                player = getattr(self.army, "player", None)
                if player is not None:
                    append_dice(player.name, f"Miracle die used ({roll_type}): {int(value)}")
        except Exception:
            pass
        return True

    def resolve_roll(
        self,
        unit,
        *,
        roll_type: str,
        dice_count: int = 1,
        die_faces: int = 6,
        modifier: int = 0,
        game=None,
        needed=None,
    ) -> Tuple[int, list[int], bool]:
        """
        Roll dice for a unit, optionally substituting a Miracle die.

        Returns: (total_value, dice_list, miracle_used)
        """
        try:
            count = max(1, int(dice_count or 1))
        except Exception:
            count = 1
        try:
            faces = max(1, int(die_faces or 6))
        except Exception:
            faces = 6
        try:
            mod = int(modifier or 0)
        except Exception:
            mod = 0

        chosen = self._choose_miracle_die(
            unit,
            roll_type=roll_type,
            dice_count=count,
            die_faces=faces,
            game=game,
            needed=needed,
        )
        if chosen is not None and self._consume_miracle_die(unit, int(chosen), roll_type=roll_type, game=game):
            if count == 1:
                dice = [int(chosen)]
            else:
                other = [get_dice_roll(faces) for _ in range(count - 1)]
                dice = [int(chosen)] + other
            total = int(sum(dice) + mod)
            return total, dice, True

        dice = [get_dice_roll(faces) for _ in range(count)]
        total = int(sum(dice) + mod)
        return total, dice, False

    def _maybe_reroll_miracle_die(self, value: int, *, allow_reroll: bool, game=None) -> int:
        if not allow_reroll:
            return int(value or 0)
        player = getattr(self.army, "player", None) if self.army is not None else None
        provider = getattr(getattr(game, "map", None), "roll_reroll_provider", None) if game is not None else None
        if callable(provider):
            try:
                want = bool(provider(
                    player=player,
                    unit=None,
                    roll_type="miracle",
                    value=int(value or 0),
                    dice=None,
                    reason="Litany of Deeds",
                ))
            except Exception:
                want = False
            if not want:
                return int(value or 0)
        return int(get_roll("D6") or 0)

    def gain_miracle_die(self, *, game=None, allow_reroll: bool = False, reason: str = "") -> int:
        value = int(get_roll("D6") or 0)
        value = self._maybe_reroll_miracle_die(value, allow_reroll=allow_reroll, game=game)
        self.miracle_dice.append(int(value))
        try:
            player = getattr(self.army, "player", None)
            if player is not None:
                note = f"Miracle die gained: {int(value)}"
                if reason:
                    note = f"{note} ({reason})"
                append_dice(player.name, note)
        except Exception:
            pass
        return int(value)

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self._army_has_rule():
            return
        self.gain_miracle_die(game=game, allow_reroll=False, reason="Battle round start")

    def on_unit_destroyed(self, unit, *, game=None, game_map=None, last_model=None) -> None:
        if unit is None or not self._army_has_rule():
            return
        if not self._unit_in_army(unit):
            return
        if not self._unit_has_rule(unit):
            return
        allow_reroll = self._litany_allows_reroll(destroyed_unit=unit, destroyed_model=last_model)
        self.gain_miracle_die(game=game, allow_reroll=allow_reroll, reason="Unit destroyed")

    def on_model_destroyed(self, unit, model, *, game=None, game_map=None) -> None:
        if unit is None or model is None or not self._army_has_rule():
            return
        if not self._unit_in_army(unit):
            return
        enh = getattr(unit, "enhancement", None)
        name = ""
        enh_id = ""
        try:
            name = str(getattr(enh, "name", "") or "").strip().lower()
        except Exception:
            name = ""
        try:
            enh_id = str(getattr(enh, "id", "") or "").strip()
        except Exception:
            enh_id = ""
        if not (name == "saintly example" or enh_id == "000008470002"):
            return
        if getattr(model, "_saintly_example_triggered", False):
            return
        try:
            setattr(model, "_saintly_example_triggered", True)
        except Exception:
            pass

        try:
            extra = int(get_roll("D3") or 0)
        except Exception:
            extra = 0
        if extra <= 0:
            return
        allow_reroll = self._litany_allows_reroll(destroyed_unit=unit, destroyed_model=model)
        for _ in range(int(extra)):
            self.gain_miracle_die(game=game, allow_reroll=allow_reroll, reason="Saintly Example")
