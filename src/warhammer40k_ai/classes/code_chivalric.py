from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.ability_support import ABILITY_CODE_CHIVALRIC, army_has_ability_id
from ..utility.dice import get_roll
from ..utility.modifiers import Modifier, ModifierOp


@dataclass(frozen=True)
class CodeChivalricDeed:
    key: str
    name: str
    summary: str
    roll_min: int
    roll_max: int


@dataclass(frozen=True)
class CodeChivalricQuality:
    key: str
    name: str
    summary: str
    roll_min: int
    roll_max: int


DEED_LAY_LOW = CodeChivalricDeed(
    key="LAY_LOW",
    name="Lay Low the Tyrant",
    summary="Select one enemy CHARACTER model. Completed at the end of a turn if it is destroyed.",
    roll_min=1,
    roll_max=2,
)
DEED_RECLAIM = CodeChivalricDeed(
    key="RECLAIM",
    name="Reclaim the Realm",
    summary="Completed at the end of your opponent's turn if you control more objectives.",
    roll_min=3,
    roll_max=4,
)
DEED_TALLY = CodeChivalricDeed(
    key="TALLY",
    name="Reap a Great Tally",
    summary="Completed at end of battle round if enemy units destroyed this round exceed the round number.",
    roll_min=5,
    roll_max=6,
)

QUALITY_VALOUR = CodeChivalricQuality(
    key="VALOUR",
    name="Martial Valour",
    summary="Each time selected to shoot or fight, re-roll one Hit roll and one Wound roll.",
    roll_min=1,
    roll_max=2,
)
QUALITY_EAGER = CodeChivalricQuality(
    key="EAGER",
    name="Eager for the Challenge",
    summary='Add 2" Move and +1 to Advance and Charge rolls.',
    roll_min=3,
    roll_max=4,
)
QUALITY_LEGACY = CodeChivalricQuality(
    key="LEGACY",
    name="Unsullied Legacy",
    summary="Improve Objective Control by 2 and Leadership by 1.",
    roll_min=5,
    roll_max=6,
)

CODE_CHIVALRIC_DEEDS = (DEED_LAY_LOW, DEED_RECLAIM, DEED_TALLY)
CODE_CHIVALRIC_QUALITIES = (QUALITY_VALOUR, QUALITY_EAGER, QUALITY_LEGACY)

DEED_BY_KEY = {d.key: d for d in CODE_CHIVALRIC_DEEDS}
QUALITY_BY_KEY = {q.key: q for q in CODE_CHIVALRIC_QUALITIES}


def _norm(text: str) -> str:
    return (text or "").replace("’", "'").strip().lower()


class CodeChivalricManager:
    """
    Imperial Knights army rule: Code Chivalric.

    At the end of Read Mission Objectives, select one Deed and one Quality (or roll for each).
    The first time the Deed is completed the army becomes Honoured and gains 2CP (or 3CP if
    either selection was random).
    """

    def __init__(self, army=None):
        self.army = army
        self.selected_deed_key: Optional[str] = None
        self.selected_quality_key: Optional[str] = None
        self.selected_deed_random = False
        self.selected_quality_random = False
        self.deed_target_model_id: Optional[str] = None
        self.deed_target_model_name: Optional[str] = None
        self.deed_target_destroyed = False
        self.honoured = False
        self.deed_completed = False
        self.enemy_units_destroyed_this_round = 0

    def _army_has_code_chivalric(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "QI":
            return False
        if army_has_ability_id(self.army, ABILITY_CODE_CHIVALRIC):
            return True
        for unit in list(getattr(self.army, "units", []) or []):
            if self._unit_has_code_chivalric(unit):
                return True
        return False

    def _unit_has_code_chivalric(self, unit) -> bool:
        if unit is None:
            return False
        try:
            found, _ = unit._find_ability_with_patterns(["code chivalric"])
            if found:
                return True
        except Exception:
            pass
        for ab in (list(getattr(unit, "possible_abilities", []) or []) + list(getattr(unit, "abilities", []) or [])):
            try:
                name = ab if isinstance(ab, str) else getattr(ab, "name", "")
                if "code chivalric" in _norm(name):
                    return True
            except Exception:
                continue
        return False

    def _resolve_game(self, player=None, game=None):
        if game is not None:
            return game
        if player is None:
            try:
                player = getattr(self.army, "player", None)
            except Exception:
                player = None
        try:
            return getattr(player, "game", None) if player is not None else None
        except Exception:
            return None

    def get_selected_deed(self) -> Optional[CodeChivalricDeed]:
        return DEED_BY_KEY.get(self.selected_deed_key) if self.selected_deed_key else None

    def get_selected_quality(self) -> Optional[CodeChivalricQuality]:
        return QUALITY_BY_KEY.get(self.selected_quality_key) if self.selected_quality_key else None

    def deed_requires_character_target(self) -> bool:
        return self.selected_deed_key == DEED_LAY_LOW.key

    def set_deed_target_model(self, model) -> bool:
        if model is None:
            return False
        try:
            mid = getattr(model, "id", None) or getattr(model, "_id", None)
        except Exception:
            mid = None
        if not mid:
            mid = str(id(model))
        self.deed_target_model_id = str(mid)
        try:
            self.deed_target_model_name = str(getattr(model, "name", "") or "")
        except Exception:
            self.deed_target_model_name = None
        self.deed_target_destroyed = False
        if self.army is not None:
            try:
                setattr(self.army, "code_chivalric_target_model_id", self.deed_target_model_id)
                setattr(self.army, "code_chivalric_target_model_name", self.deed_target_model_name)
            except Exception:
                pass
        return True

    def _eligible_character_models(self, *, game=None, player=None) -> list:
        game = self._resolve_game(player=player, game=game)
        if game is None or player is None:
            return []
        try:
            enemy_units = list(game.get_enemy_units(player) or [])
        except Exception:
            enemy_units = []
        if not enemy_units:
            return []
        models = []
        seen = set()
        for unit in enemy_units:
            try:
                unit_models = unit.get_models_for_collision()
            except Exception:
                unit_models = list(getattr(unit, "models", []) or [])
            for model in unit_models:
                try:
                    if not getattr(model, "is_alive", True):
                        continue
                    if not bool(getattr(model, "is_character", False)):
                        continue
                except Exception:
                    continue
                try:
                    mid = getattr(model, "id", None) or getattr(model, "_id", None)
                except Exception:
                    mid = None
                if not mid:
                    mid = str(id(model))
                if mid in seen:
                    continue
                seen.add(mid)
                models.append(model)
        return models

    def get_eligible_character_models(self, *, game=None, player=None) -> list:
        return self._eligible_character_models(game=game, player=player)

    def _pick_best_character_target(self, options: list) -> Optional[object]:
        if not options:
            return None

        def _score(m) -> int:
            try:
                unit = getattr(m, "parent_unit", None)
                if unit is not None:
                    return int(unit.get_unit_cost())
            except Exception:
                pass
            try:
                unit = getattr(m, "parent_unit", None)
                return int(getattr(unit, "points", 0) or 0)
            except Exception:
                return 0

        return max(options, key=lambda m: (_score(m), str(getattr(m, "name", ""))))

    def select_deed(self, deed, *, random: bool = False, game=None, player=None) -> bool:
        if not self._army_has_code_chivalric():
            return False
        key = getattr(deed, "key", deed)
        key = str(key or "").strip().upper()
        if key not in DEED_BY_KEY:
            return False
        self.selected_deed_key = key
        self.selected_deed_random = bool(random)
        if self.army is not None:
            try:
                setattr(self.army, "code_chivalric_deed_key", self.selected_deed_key)
            except Exception:
                pass
        if key == DEED_LAY_LOW.key and not self.deed_target_model_id:
            options = self._eligible_character_models(game=game, player=player)
            if options:
                pick = self._pick_best_character_target(options)
                if pick is not None:
                    self.set_deed_target_model(pick)
        return True

    def select_quality(self, quality, *, random: bool = False) -> bool:
        if not self._army_has_code_chivalric():
            return False
        key = getattr(quality, "key", quality)
        key = str(key or "").strip().upper()
        if key not in QUALITY_BY_KEY:
            return False
        self.selected_quality_key = key
        self.selected_quality_random = bool(random)
        if self.army is not None:
            try:
                setattr(self.army, "code_chivalric_quality_key", self.selected_quality_key)
            except Exception:
                pass
        self.apply_quality_effects()
        return True

    def roll_deed(self, *, game=None, player=None) -> dict:
        roll = int(get_roll("D6"))
        deed = next((d for d in CODE_CHIVALRIC_DEEDS if d.roll_min <= roll <= d.roll_max), None)
        if deed is None:
            deed = DEED_LAY_LOW
        self.select_deed(deed, random=True, game=game, player=player)
        return {"roll": roll, "deed": deed}

    def roll_quality(self) -> dict:
        roll = int(get_roll("D6"))
        quality = next((q for q in CODE_CHIVALRIC_QUALITIES if q.roll_min <= roll <= q.roll_max), None)
        if quality is None:
            quality = QUALITY_VALOUR
        self.select_quality(quality, random=True)
        return {"roll": roll, "quality": quality}

    def on_read_mission_objectives(self, *, game=None, player=None) -> None:
        if not self._army_has_code_chivalric():
            return
        if self.selected_deed_key and self.selected_quality_key:
            return
        game = self._resolve_game(player=player, game=game)
        if player is None and self.army is not None:
            player = getattr(self.army, "player", None)
        is_human = False
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human:
            return
        deed_res = self.roll_deed(game=game, player=player)
        self.roll_quality()
        if deed_res.get("deed", None) == DEED_LAY_LOW and not self.deed_target_model_id:
            options = self._eligible_character_models(game=game, player=player)
            if options:
                pick = self._pick_best_character_target(options)
                if pick is not None:
                    self.set_deed_target_model(pick)

    def apply_quality_effects(self) -> None:
        if self.army is None or not self.selected_quality_key:
            return
        for unit in list(getattr(self.army, "units", []) or []):
            if not self._unit_has_code_chivalric(unit):
                continue
            try:
                unit.remove_characteristic_modifiers_by_source("code_chivalric")
            except Exception:
                pass
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            for key in list(sr.keys()):
                if str(key).startswith("code_chivalric_"):
                    sr.pop(key, None)
            if self.selected_quality_key == QUALITY_EAGER.key:
                unit.add_characteristic_modifier(
                    "movement",
                    Modifier(ModifierOp.ADD, 2, source="code_chivalric:quality"),
                )
                sr["code_chivalric_advance_bonus"] = 1
                sr["code_chivalric_charge_bonus"] = 1
            elif self.selected_quality_key == QUALITY_LEGACY.key:
                unit.add_characteristic_modifier(
                    "objective_control",
                    Modifier(ModifierOp.ADD, 2, source="code_chivalric:quality"),
                )
                unit.add_characteristic_modifier(
                    "leadership",
                    Modifier(ModifierOp.ADD, -1, source="code_chivalric:quality"),
                )
            sr["code_chivalric_quality_key"] = self.selected_quality_key
            unit.special_rules = sr

    def quality_allows_rerolls(self) -> bool:
        return self.selected_quality_key == QUALITY_VALOUR.key

    def can_use_reroll(self, model, *, kind: str) -> bool:
        if not self.quality_allows_rerolls():
            return False
        try:
            unit = getattr(model, "parent_unit", None)
        except Exception:
            unit = None
        if unit is None or not self._unit_has_code_chivalric(unit):
            return False
        try:
            if kind == "hit":
                return bool(getattr(model, "can_use_code_chivalric_reroll", lambda *_a: False)("hit"))
            if kind == "wound":
                return bool(getattr(model, "can_use_code_chivalric_reroll", lambda *_a: False)("wound"))
        except Exception:
            return False
        return False

    def grant_rerolls_for_unit(self, unit) -> None:
        if not self.quality_allows_rerolls():
            return
        if not self._unit_has_code_chivalric(unit):
            return
        try:
            models = unit.get_models_for_collision()
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        for model in models:
            try:
                if not getattr(model, "is_alive", True):
                    continue
            except Exception:
                continue
            try:
                model.grant_code_chivalric_rerolls()
            except Exception:
                continue

    def clear_rerolls_for_unit(self, unit) -> None:
        try:
            models = unit.get_models_for_collision()
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        for model in models:
            try:
                model.clear_code_chivalric_rerolls()
            except Exception:
                continue

    def on_unit_selected_to_shoot(self, unit) -> None:
        self.grant_rerolls_for_unit(unit)

    def on_unit_selected_to_fight(self, unit) -> None:
        self.grant_rerolls_for_unit(unit)

    def on_unit_shooting_resolved(self, unit) -> None:
        self.clear_rerolls_for_unit(unit)

    def on_fight_sequence_complete(self, unit) -> None:
        self.clear_rerolls_for_unit(unit)

    def on_model_destroyed(self, target_model) -> None:
        if not self.deed_target_model_id or self.deed_completed:
            return
        try:
            mid = getattr(target_model, "id", None) or getattr(target_model, "_id", None)
        except Exception:
            mid = None
        if not mid:
            mid = str(id(target_model))
        if str(mid) == str(self.deed_target_model_id):
            self.deed_target_destroyed = True

    def record_enemy_unit_destroyed(self) -> None:
        self.enemy_units_destroyed_this_round += 1

    def on_battle_round_start(self, battle_round: int) -> None:
        self.enemy_units_destroyed_this_round = 0

    def _grant_honoured(self, *, player=None) -> None:
        if self.honoured:
            return
        self.honoured = True
        self.deed_completed = True
        if self.army is not None:
            try:
                setattr(self.army, "code_chivalric_honoured", True)
            except Exception:
                pass
        if player is None and self.army is not None:
            player = getattr(self.army, "player", None)
        if player is None:
            return
        cp_gain = 3 if (self.selected_deed_random or self.selected_quality_random) else 2
        try:
            player.gain_command_points(cp_gain, exempt_from_guardrail=True, reason="Code Chivalric: Honoured")
        except Exception:
            pass

    def check_end_of_turn(self, *, game=None, turn_ending_player=None) -> None:
        if not self._army_has_code_chivalric():
            return
        if self.deed_completed:
            return
        deed = self.get_selected_deed()
        if deed is None:
            return
        if deed.key == DEED_LAY_LOW.key and self.deed_target_destroyed:
            self._grant_honoured(player=getattr(self.army, "player", None))
        elif deed.key == DEED_RECLAIM.key:
            if turn_ending_player is None:
                return
            try:
                if getattr(self.army, "player", None) is turn_ending_player:
                    return
            except Exception:
                pass
            game = self._resolve_game(player=getattr(self.army, "player", None), game=game)
            if game is None:
                return
            ours = self._count_objectives_controlled(game, getattr(self.army, "player", None))
            theirs = self._count_objectives_controlled(game, turn_ending_player)
            if ours > theirs:
                self._grant_honoured(player=getattr(self.army, "player", None))

    def check_end_of_battle_round(self, *, game=None, battle_round: int = 0) -> None:
        if not self._army_has_code_chivalric():
            return
        if self.deed_completed:
            return
        deed = self.get_selected_deed()
        if deed is None or deed.key != DEED_TALLY.key:
            return
        try:
            br = int(battle_round or 0)
        except Exception:
            br = 0
        if br <= 0:
            return
        if self.enemy_units_destroyed_this_round > br:
            self._grant_honoured(player=getattr(self.army, "player", None))

    def _count_objectives_controlled(self, game, player) -> int:
        if game is None or player is None:
            return 0
        count = 0
        for obj in list(getattr(getattr(game, "map", None), "objectives", []) or []):
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            try:
                if hasattr(loc, "update_control"):
                    loc.update_control(game)
            except Exception:
                pass
            if getattr(loc, "controlling_player", None) is player:
                count += 1
        return count
