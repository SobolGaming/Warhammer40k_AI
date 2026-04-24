from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.ability_support import ABILITY_CODE_CHIVALRIC, army_has_ability_id
from ..utility.dice import get_roll
from ..utility.modifiers import Modifier, ModifierOp
from ..utility.entity_ids import get_entity_id


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
    return (text or "").replace("\u2019", "'").replace("\u00e2\u20ac\u2122", "'").strip().lower()


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
        self.used_deed_keys: set[str] = set()
        self.used_quality_keys: set[str] = set()
        self.fulfilled_quality_keys: set[str] = set()
        self.completed_oath_count = 0

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

    def _is_questoris_companions(self) -> bool:
        if self.army is None:
            return False
        mgr = getattr(self.army, "imperial_knights_detachments", None)
        check = getattr(mgr, "is_questoris_companions", None)
        return bool(callable(check) and check())

    def _available_deeds_for_selection(self) -> list[CodeChivalricDeed]:
        if not self._is_questoris_companions() or not bool(self.honoured):
            return list(CODE_CHIVALRIC_DEEDS)
        used = {str(k or "").strip().upper() for k in list(self.used_deed_keys or set()) if str(k or "").strip()}
        return [deed for deed in list(CODE_CHIVALRIC_DEEDS) if str(getattr(deed, "key", "") or "").strip().upper() not in used]

    def _available_qualities_for_selection(self) -> list[CodeChivalricQuality]:
        if not self._is_questoris_companions() or not bool(self.honoured):
            return list(CODE_CHIVALRIC_QUALITIES)
        used = {str(k or "").strip().upper() for k in list(self.used_quality_keys or set()) if str(k or "").strip()}
        return [
            quality for quality in list(CODE_CHIVALRIC_QUALITIES)
            if str(getattr(quality, "key", "") or "").strip().upper() not in used
        ]

    def get_active_quality_keys(self) -> list[str]:
        active = {str(v or "").strip().upper() for v in list(self.fulfilled_quality_keys or set()) if str(v or "").strip()}
        if str(self.selected_quality_key or "").strip():
            active.add(str(self.selected_quality_key or "").strip().upper())
        return sorted(active)

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
            mid = get_entity_id(model)
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
                    mid = get_entity_id(model)
                if mid in seen:
                    continue
                seen.add(mid)
                models.append(model)
        return models

    def get_eligible_character_models(self, *, game=None, player=None) -> list:
        return self._eligible_character_models(game=game, player=player)

    def select_deed(self, deed, *, random: bool = False, game=None, player=None) -> bool:
        if not self._army_has_code_chivalric():
            return False
        key = getattr(deed, "key", deed)
        key = str(key or "").strip().upper()
        if key not in DEED_BY_KEY:
            return False
        if self._is_questoris_companions() and bool(self.honoured):
            used = {str(v or "").strip().upper() for v in list(self.used_deed_keys or set()) if str(v or "").strip()}
            if key in used:
                return False
        self.selected_deed_key = key
        self.selected_deed_random = bool(random)
        self.used_deed_keys.add(str(key))
        if self.army is not None:
            try:
                setattr(self.army, "code_chivalric_deed_key", self.selected_deed_key)
            except Exception:
                pass
        return True

    def select_quality(self, quality, *, random: bool = False) -> bool:
        if not self._army_has_code_chivalric():
            return False
        key = getattr(quality, "key", quality)
        key = str(key or "").strip().upper()
        if key not in QUALITY_BY_KEY:
            return False
        if self._is_questoris_companions() and bool(self.honoured):
            used = {str(v or "").strip().upper() for v in list(self.used_quality_keys or set()) if str(v or "").strip()}
            if key in used:
                return False
        self.selected_quality_key = key
        self.selected_quality_random = bool(random)
        self.used_quality_keys.add(str(key))
        if self.army is not None:
            try:
                setattr(self.army, "code_chivalric_quality_key", self.selected_quality_key)
            except Exception:
                pass
        self.apply_quality_effects()
        return True

    def roll_deed(self, *, game=None, player=None) -> dict:
        roll = get_roll("D6")
        deed = next((d for d in CODE_CHIVALRIC_DEEDS if d.roll_min <= roll <= d.roll_max), None)
        if deed is None:
            deed = DEED_LAY_LOW
        if self._is_questoris_companions() and bool(self.honoured):
            available = list(self._available_deeds_for_selection() or [])
            if not available:
                return {"roll": roll, "deed": None}
            available_by_key = {
                str(getattr(entry, "key", "") or "").strip().upper(): entry
                for entry in available
                if str(getattr(entry, "key", "") or "").strip()
            }
            if str(getattr(deed, "key", "") or "").strip().upper() not in available_by_key:
                deed = available[0]
        self.select_deed(deed, random=True, game=game, player=player)
        return {"roll": roll, "deed": deed}

    def roll_quality(self) -> dict:
        roll = get_roll("D6")
        quality = next((q for q in CODE_CHIVALRIC_QUALITIES if q.roll_min <= roll <= q.roll_max), None)
        if quality is None:
            quality = QUALITY_VALOUR
        if self._is_questoris_companions() and bool(self.honoured):
            available = list(self._available_qualities_for_selection() or [])
            if not available:
                return {"roll": roll, "quality": None}
            available_by_key = {
                str(getattr(entry, "key", "") or "").strip().upper(): entry
                for entry in available
                if str(getattr(entry, "key", "") or "").strip()
            }
            if str(getattr(quality, "key", "") or "").strip().upper() not in available_by_key:
                quality = available[0]
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

        if player is None:
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_CHIVALRIC_OATH
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import get_entity_id
        except Exception:
            return

        army_id = get_entity_id(self.army) if self.army is not None else None
        queue = getattr(game, "decision_queue", None)

        if not self.selected_deed_key:
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_CHIVALRIC_OATH:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("oath_kind", "")) != "deed":
                        continue
                    if str(ctx.get("army_id", "")) == str(army_id):
                        return
            available_deeds = list(self._available_deeds_for_selection() or [])
            if not available_deeds:
                return
            req_options = [
                DecisionOption.create(
                    "Roll D6 (random)",
                    payload={"choice_key": "ROLL", "random": True, "oath_kind": "deed"},
                )
            ]
            for deed in available_deeds:
                key = getattr(deed, "key", None) or getattr(deed, "choice_key", None)
                name = getattr(deed, "name", None) or str(deed)
                summary = getattr(deed, "summary", "") or getattr(deed, "effect", "")
                if not key:
                    continue
                req_options.append(
                    DecisionOption.create(
                        name,
                        payload={"choice_key": str(key), "oath_kind": "deed", "summary": summary, "army_id": army_id},
                    )
                )
            req = DecisionRequest.create(
                DECISION_CHOOSE_CHIVALRIC_OATH,
                "Select Code Chivalric Deed.",
                player_id=getattr(player, "id", None),
                options=req_options,
                context={"oath_kind": "deed", "army_id": army_id},
            )
            if hasattr(game, "request_decision"):
                game.request_decision(req)
            return

        if not self.selected_quality_key:
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_CHIVALRIC_OATH:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("oath_kind", "")) != "quality":
                        continue
                    if str(ctx.get("army_id", "")) == str(army_id):
                        return
            available_qualities = list(self._available_qualities_for_selection() or [])
            if not available_qualities:
                return
            req_options = [
                DecisionOption.create(
                    "Roll D6 (random)",
                    payload={"choice_key": "ROLL", "random": True, "oath_kind": "quality"},
                )
            ]
            for quality in available_qualities:
                key = getattr(quality, "key", None) or getattr(quality, "choice_key", None)
                name = getattr(quality, "name", None) or str(quality)
                summary = getattr(quality, "summary", "") or getattr(quality, "effect", "")
                if not key:
                    continue
                req_options.append(
                    DecisionOption.create(
                        name,
                        payload={"choice_key": str(key), "oath_kind": "quality", "summary": summary, "army_id": army_id},
                    )
                )
            req = DecisionRequest.create(
                DECISION_CHOOSE_CHIVALRIC_OATH,
                "Select Code Chivalric Quality.",
                player_id=getattr(player, "id", None),
                options=req_options,
                context={"oath_kind": "quality", "army_id": army_id},
            )
            if hasattr(game, "request_decision"):
                game.request_decision(req)

    def apply_quality_effects(self) -> None:
        if self.army is None:
            return
        active_quality_keys = set(self.get_active_quality_keys())
        if not active_quality_keys:
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
            if QUALITY_EAGER.key in active_quality_keys:
                unit.add_characteristic_modifier(
                    "movement",
                    Modifier(ModifierOp.ADD, 2, source="code_chivalric:quality"),
                )
                sr["code_chivalric_advance_bonus"] = 1
                sr["code_chivalric_charge_bonus"] = 1
            if QUALITY_LEGACY.key in active_quality_keys:
                unit.add_characteristic_modifier(
                    "objective_control",
                    Modifier(ModifierOp.ADD, 2, source="code_chivalric:quality"),
                )
                unit.add_characteristic_modifier(
                    "leadership",
                    Modifier(ModifierOp.ADD, -1, source="code_chivalric:quality"),
                )
            sr["code_chivalric_quality_key"] = str(self.selected_quality_key or "")
            sr["code_chivalric_active_quality_keys"] = sorted(active_quality_keys)
            unit.special_rules = sr

    def quality_allows_rerolls(self) -> bool:
        return QUALITY_VALOUR.key in set(self.get_active_quality_keys())

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
            mid = get_entity_id(target_model)
        if str(mid) == str(self.deed_target_model_id):
            self.deed_target_destroyed = True

    def record_enemy_unit_destroyed(self) -> None:
        self.enemy_units_destroyed_this_round += 1

    def on_battle_round_start(self, battle_round: int) -> None:
        self.enemy_units_destroyed_this_round = 0

    def _notify_oath_fulfilled(self, *, is_additional_oath: bool, player=None) -> None:
        if self.army is None:
            return
        mgr = getattr(self.army, "imperial_knights_detachments", None)
        callback = getattr(mgr, "on_code_chivalric_oath_fulfilled", None) if mgr is not None else None
        if callable(callback):
            callback(player=player, is_additional_oath=bool(is_additional_oath))

    def _grant_honoured(self, *, player=None) -> None:
        if player is None and self.army is not None:
            player = getattr(self.army, "player", None)
        selected_quality = str(self.selected_quality_key or "").strip().upper()
        if selected_quality:
            self.fulfilled_quality_keys.add(selected_quality)
        is_additional = bool(self.honoured)
        if self.honoured:
            self.deed_completed = True
            self.completed_oath_count = int(self.completed_oath_count or 0) + 1
            self.apply_quality_effects()
            if self._is_questoris_companions() and player is not None:
                player.gain_command_points(1, exempt_from_guardrail=True, reason="Code Chivalric: Additional Oath")
            self._notify_oath_fulfilled(is_additional_oath=True, player=player)
            return

        self.honoured = True
        self.deed_completed = True
        self.completed_oath_count = int(self.completed_oath_count or 0) + 1
        if self.army is not None:
            try:
                setattr(self.army, "code_chivalric_honoured", True)
            except Exception:
                pass
        self.apply_quality_effects()
        self._notify_oath_fulfilled(is_additional_oath=is_additional, player=player)
        if player is None:
            return
        cp_gain = 3 if (self.selected_deed_random or self.selected_quality_random) else 2
        try:
            player.gain_command_points(cp_gain, exempt_from_guardrail=True, reason="Code Chivalric: Honoured")
        except Exception:
            pass

    def prepare_next_oath_selection(self, *, game=None, player=None) -> bool:
        if not self._is_questoris_companions():
            return False
        if not bool(self.honoured):
            return False
        if not bool(self.deed_completed):
            return False
        if not str(self.selected_deed_key or "").strip():
            return False
        if not str(self.selected_quality_key or "").strip():
            return False
        if not self._available_deeds_for_selection():
            return False
        if not self._available_qualities_for_selection():
            return False
        self.deed_completed = False
        self.selected_deed_key = None
        self.selected_quality_key = None
        self.selected_deed_random = False
        self.selected_quality_random = False
        self.deed_target_model_id = None
        self.deed_target_model_name = None
        self.deed_target_destroyed = False
        if self.army is not None:
            try:
                setattr(self.army, "code_chivalric_deed_key", "")
                setattr(self.army, "code_chivalric_quality_key", "")
                setattr(self.army, "code_chivalric_target_model_id", "")
                setattr(self.army, "code_chivalric_target_model_name", "")
            except Exception:
                pass
        self.apply_quality_effects()
        if game is not None and player is not None:
            self.on_read_mission_objectives(game=game, player=player)
        return True

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
