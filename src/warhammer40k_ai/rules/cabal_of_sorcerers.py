from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utility.ability_support import ABILITY_CABAL_OF_SORCERERS, army_has_ability_id
from ..utility.dice import get_roll, DiceCollection


@dataclass(frozen=True)
class CabalRitual:
    key: str
    name: str
    warp_charge: int
    summary: str
    target_kind: str  # "enemy" or "friendly"


RITUAL_DESTINYS_RUIN = CabalRitual(
    key="DESTINYS_RUIN",
    name="Destiny's Ruin",
    warp_charge=5,
    summary="Enemy within 24\" and visible; TS/SL attacks re-roll hit rolls of 1 (10+ full re-roll).",
    target_kind="enemy",
)
RITUAL_TEMPORAL_SURGE = CabalRitual(
    key="TEMPORAL_SURGE",
    name="Temporal Surge",
    warp_charge=6,
    summary="Friendly TS/SL within 24\" and visible, not in engagement; Normal move D6\" (10+ 6\") and no charge this turn.",
    target_kind="friendly",
)
RITUAL_DOOMBOLT = CabalRitual(
    key="DOOMBOLT",
    name="Doombolt",
    warp_charge=7,
    summary="Enemy within 24\" and visible suffers D3 mortals (11+ D3+3). Lone Operative only within 12\".",
    target_kind="enemy",
)
RITUAL_TWIST_OF_FATE = CabalRitual(
    key="TWIST_OF_FATE",
    name="Twist of Fate",
    warp_charge=9,
    summary="Enemy within 24\" and visible; TS/SL attacks improve AP by 1 (12+ by 2) until end of phase.",
    target_kind="enemy",
)

DEFAULT_RITUALS: tuple[CabalRitual, ...] = (
    RITUAL_DESTINYS_RUIN,
    RITUAL_TEMPORAL_SURGE,
    RITUAL_DOOMBOLT,
    RITUAL_TWIST_OF_FATE,
)


class CabalOfSorcerersManager:
    """
    Thousand Sons army rule: Cabal of Sorcerers (Rituals).
    """

    def __init__(self, army=None):
        self.army = army
        self.used_rituals: set[str] = set()
        self.used_models: dict[str, int] = {}
        self._last_reset_key: Optional[tuple] = None

    @staticmethod
    def _normalize_text(value: object) -> str:
        import re

        text = str(value or "").lower()
        text = text.replace("\u2019", "'").replace("\u0192?T", "'")
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _ability_name_matches(cls, value: object, phrase: str) -> bool:
        want = cls._normalize_text(phrase)
        if not want:
            return False
        return want in cls._normalize_text(value)

    @staticmethod
    def _iter_unit_abilities(unit):
        for ab in (list(getattr(unit, "possible_abilities", []) or []) + list(getattr(unit, "abilities", []) or [])):
            if isinstance(ab, str):
                yield ab
            else:
                nm = getattr(ab, "name", "")
                desc = getattr(ab, "description", "")
                if nm:
                    yield nm
                if desc:
                    yield desc

    @staticmethod
    def _iter_model_abilities(model):
        abilities = getattr(model, "abilities", None)
        if not isinstance(abilities, dict):
            return
        for ab in abilities.values():
            if isinstance(ab, str):
                yield ab
            else:
                nm = getattr(ab, "name", "")
                desc = getattr(ab, "description", "")
                if nm:
                    yield nm
                if desc:
                    yield desc

    @classmethod
    def _unit_has_named_ability(cls, unit, phrase: str) -> bool:
        if unit is None:
            return False
        for text in cls._iter_unit_abilities(unit):
            if cls._ability_name_matches(text, phrase):
                return True
        return False

    @classmethod
    def _model_has_named_ability(cls, model, phrase: str) -> bool:
        if model is None:
            return False
        for text in cls._iter_model_abilities(model):
            if cls._ability_name_matches(text, phrase):
                return True
        unit = getattr(model, "parent_unit", None)
        return cls._unit_has_named_ability(unit, phrase)

    def _model_has_keyword(self, model, keyword: str) -> bool:
        if model is None or not keyword:
            return False
        kw = str(keyword).strip().upper()
        if not kw:
            return False
        has_kw = getattr(model, "has_keyword", None)
        if callable(has_kw):
            if has_kw(kw):
                return True
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        has_any_kw = getattr(unit, "has_any_keyword", None)
        if callable(has_any_kw):
            if has_any_kw(kw):
                return True
        has_kw_u = getattr(unit, "has_keyword", None)
        if callable(has_kw_u):
            return bool(has_kw_u(kw))
        return False

    def _ritual_attempt_limit_for_model(self, model) -> int:
        if self._model_has_named_ability(model, "Lord of the Planet of the Sorcerers"):
            return 2
        return 1

    def _spirit_snare_bonus_for_model(self, model) -> int:
        if model is None:
            return 0
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return 0
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return 0
        entries = sr.get("spirit_snare_ritual_bonus_by_model_id", {})
        if not isinstance(entries, dict):
            return 0
        model_id = str(getattr(model, "id", "") or getattr(model, "_id", ""))
        if not model_id:
            return 0
        try:
            value = int(entries.get(model_id, 0) or 0)
        except Exception:
            value = 0
        return max(0, min(2, value))

    def _immaterial_flare_channel_bonus(self, caster_model) -> int:
        if caster_model is None:
            return 0
        if not self._model_has_keyword(caster_model, "THOUSAND SONS"):
            return 0
        if not self._model_has_keyword(caster_model, "PSYKER"):
            return 0
        if self.army is None:
            return 0
        try:
            from ..utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return 0
        caster_unit = getattr(caster_model, "parent_unit", None)
        for unit in list(getattr(self.army, "units", []) or []):
            if not self._unit_is_available(unit):
                continue
            if not self._unit_has_named_ability(unit, "Immaterial Flare"):
                # Some model-only abilities are not reflected on unit-level entries.
                has_model_immaterial = False
                for model in list(getattr(unit, "models", []) or []):
                    if getattr(model, "is_alive", True) and self._model_has_named_ability(model, "Immaterial Flare"):
                        has_model_immaterial = True
                        break
                if not has_model_immaterial:
                    continue
            for model in list(getattr(unit, "models", []) or []):
                if not getattr(model, "is_alive", True):
                    continue
                if model is caster_model:
                    return 1
                # If ability is model-specific, enforce ownership to that model.
                if not self._model_has_named_ability(model, "Immaterial Flare") and not self._unit_has_named_ability(unit, "Immaterial Flare"):
                    continue
                try:
                    dist = float(distance_between_models_bases_3d(caster_model, model))
                except Exception:
                    continue
                if dist <= 6.0 + 1e-6:
                    return 1
            # Fast path for single-model aura units represented at unit level.
            if unit is caster_unit and self._unit_has_named_ability(unit, "Immaterial Flare"):
                return 1
        return 0

    def _ritual_test_bonus_for_model(self, model, *, channel: bool = False) -> int:
        bonus = 0
        if self._model_has_named_ability(model, "Arch-Sorcerer of Tzeentch"):
            bonus += 1
        if self._model_has_named_ability(model, "Lord of the Planet of the Sorcerers"):
            bonus += 2
        bonus += int(self._spirit_snare_bonus_for_model(model) or 0)

        immaterial_bonus = 0
        if channel:
            immaterial_bonus = int(self._immaterial_flare_channel_bonus(model) or 0)
        if immaterial_bonus:
            # Immaterial Flare is explicitly non-cumulative with other Psychic test modifiers.
            return int(max(immaterial_bonus, bonus))
        return int(bonus)

    def _army_has_cabal(self) -> bool:
        if self.army is None:
            return False
        return army_has_ability_id(self.army, ABILITY_CABAL_OF_SORCERERS)

    def _unit_has_cabal(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "has_cabal_of_sorcerers") and unit.has_cabal_of_sorcerers():
                return True
        except Exception:
            pass
        for ab in (list(getattr(unit, "possible_abilities", []) or []) + list(getattr(unit, "abilities", []) or [])):
            try:
                if isinstance(ab, str):
                    nm = ab
                else:
                    nm = getattr(ab, "name", "")
                if "cabal of sorcerers" in str(nm or "").lower():
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _model_id(model) -> str:
        if model is None:
            return ""
        return str(getattr(model, "id", "") or getattr(model, "_id", "") or "")

    def _model_is_enhancement_bearer(self, model, flag_key: str) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
            return False
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
        if not bearer_id:
            return True
        model_id = self._model_id(model)
        return bool(model_id and model_id == bearer_id)

    def _ritual_range_bonus_for_model(self, model) -> int:
        if self._model_is_enhancement_bearer(model, "enhancement_lord_of_forbidden_lore"):
            return 6
        return 0

    def _ritual_range_for_model(self, model) -> float:
        return float(24.0 + self._ritual_range_bonus_for_model(model))

    def _doombolt_lone_operative_range_for_model(self, model) -> float:
        return float(12.0 + self._ritual_range_bonus_for_model(model))

    @staticmethod
    def _incandaeum_once_key() -> str:
        return "incandaeum_doombolt_override"

    def _incandaeum_override_used(self, model) -> bool:
        if model is None:
            return True
        once_key = self._incandaeum_once_key()
        has_used = getattr(model, "has_used_once_per_battle", None)
        if callable(has_used):
            return bool(has_used(once_key))
        unit = getattr(model, "parent_unit", None)
        sr = getattr(unit, "special_rules", None) if unit is not None else None
        if not isinstance(sr, dict):
            return True
        used_ids = {str(v) for v in list(sr.get("enhancement_incandaeum_used_model_ids", []) or []) if str(v or "")}
        model_id = self._model_id(model)
        return bool(model_id and model_id in used_ids)

    def _mark_incandaeum_override_used(self, model) -> None:
        if model is None:
            return
        once_key = self._incandaeum_once_key()
        mark = getattr(model, "mark_used_once_per_battle", None)
        if callable(mark):
            mark(once_key, ability_name="Incandaeum", source="enhancement")
        unit = getattr(model, "parent_unit", None)
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        used_ids = {str(v) for v in list(sr.get("enhancement_incandaeum_used_model_ids", []) or []) if str(v or "")}
        model_id = self._model_id(model)
        if model_id:
            used_ids.add(model_id)
            sr["enhancement_incandaeum_used_model_ids"] = sorted(used_ids)
            unit.special_rules = sr

    def _incandaeum_can_override(self, model, ritual_key: str) -> bool:
        if str(ritual_key or "").strip().upper() != RITUAL_DOOMBOLT.key:
            return False
        if not self._model_is_enhancement_bearer(model, "enhancement_incandaeum"):
            return False
        return not self._incandaeum_override_used(model)

    def _log_ritual_result(self, ritual, caster_unit, caster_model, target_unit, result: dict) -> None:
        try:
            from ..utility.event_bus import append_action, append_dice
        except Exception:
            return
        player = getattr(self.army, "player", None)
        if player is None:
            return

        rolls = list(result.get("rolls") or [])
        total = int(result.get("total") or 0)
        rolls_text = " + ".join(str(r) for r in rolls) if rolls else "0"
        channel_tag = " (channeled)" if result.get("channeled") else ""
        try:
            warp_charge = int(getattr(ritual, "warp_charge", 0) or 0)
        except Exception:
            warp_charge = 0
        append_dice(
            player,
            f"Cabal of Sorcerers: {ritual.name} roll {rolls_text} = {total} (WC {warp_charge}){channel_tag}",
        )

        caster_name = getattr(caster_model, "name", None) or getattr(caster_unit, "name", "Caster")
        target_name = getattr(target_unit, "name", None) or "no target"
        status = "Success" if result.get("success") else "Failed"
        reason = str(result.get("reason") or "")
        if reason and not result.get("success"):
            status = f"Failed ({reason})"
        mw_self = int(result.get("mortal_wounds") or 0)
        mw_target = int(result.get("target_mortal_wounds") or 0)
        append_action(
            player,
            (
                f"Cabal of Sorcerers: {caster_name} used {ritual.name} on {target_name}: "
                f"{status}; mortals self {mw_self}, target {mw_target}"
            ),
        )

    def _publish_ritual_resolved(
        self, game, ritual, caster_unit, caster_model, target_unit, result: dict
    ) -> None:
        try:
            if game is None or getattr(game, "event_system", None) is None:
                return
            game.event_system.publish(
                "cabal_ritual_resolved",
                player=getattr(self.army, "player", None),
                ritual=ritual,
                caster_unit=caster_unit,
                caster_model=caster_model,
                target_unit=target_unit,
                result=dict(result or {}),
            )
        except Exception:
            return

    def _finalize_ritual_result(self, game, ritual, caster_unit, caster_model, target_unit, result: dict) -> dict:
        if result.get("rolls"):
            self._log_ritual_result(ritual, caster_unit, caster_model, target_unit, result)
            self._publish_ritual_resolved(game, ritual, caster_unit, caster_model, target_unit, result)
        return result

    def _reset_for_shooting_phase(self, game, player) -> None:
        try:
            key = (int(getattr(game, "turn", 0) or 0), str(getattr(player, "name", "") or ""))
        except Exception:
            key = None
        if key is None:
            return
        if self._last_reset_key != key:
            self.used_rituals.clear()
            self.used_models.clear()
            self._last_reset_key = key

    def on_shooting_phase_start(self, *, game=None, player=None) -> None:
        if not self._army_has_cabal():
            return
        if game is None or player is None:
            return
        try:
            if player is not getattr(self.army, "player", None):
                return
        except Exception:
            pass
        self._reset_for_shooting_phase(game, player)

    def get_available_rituals(self, caster_model=None) -> list[CabalRitual]:
        rituals = [r for r in DEFAULT_RITUALS if r.key not in self.used_rituals]
        if (
            caster_model is not None
            and RITUAL_DOOMBOLT.key in self.used_rituals
            and self._incandaeum_can_override(caster_model, RITUAL_DOOMBOLT.key)
        ):
            rituals.append(RITUAL_DOOMBOLT)
        return rituals

    def _model_is_available(self, model) -> bool:
        if model is None:
            return False
        try:
            if not getattr(model, "is_alive", True):
                return False
        except Exception:
            return False
        try:
            model_id = str(getattr(model, "id", "") or getattr(model, "_id", ""))
        except Exception:
            model_id = ""
        if model_id:
            used = int(self.used_models.get(model_id, 0) or 0)
            if used >= int(self._ritual_attempt_limit_for_model(model) or 1):
                return False
        return True

    def _unit_is_available(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            return False
        try:
            if not bool(getattr(unit, "deployed", True)):
                return False
        except Exception:
            return False
        try:
            if getattr(unit, "reserve_status", "deployed") != "deployed":
                return False
        except Exception:
            return False
        try:
            if bool(getattr(unit, "is_embarked", False)):
                return False
        except Exception:
            pass
        try:
            if getattr(unit, "embarked_in", None) is not None:
                return False
        except Exception:
            pass
        return True

    def get_eligible_casters(self, *, game=None, player=None) -> list[tuple]:
        if not self._army_has_cabal():
            return []
        if self.army is None:
            return []
        if player is None:
            try:
                player = getattr(self.army, "player", None)
            except Exception:
                player = None
        if game is None and player is not None:
            try:
                game = getattr(player, "game", None)
            except Exception:
                game = None
        if game is not None and hasattr(game, "is_shooting_phase"):
            try:
                if not game.is_shooting_phase():
                    return []
                if game.get_current_player() is not player:
                    return []
            except Exception:
                pass

        out = []
        for unit in list(getattr(self.army, "units", []) or []):
            if not self._unit_is_available(unit):
                continue
            if not self._unit_has_cabal(unit):
                continue
            for model in list(getattr(unit, "models", []) or []):
                if not self._model_is_available(model):
                    continue
                out.append((unit, model))
        return out

    def _distance_model_to_unit(self, model, unit) -> float:
        try:
            from ..utility.aura_utils import distance_between_models_bases_3d
        except Exception:
            return float("inf")
        best = float("inf")
        try:
            models = list(getattr(unit, "models", []) or [])
        except Exception:
            models = []
        for m in models:
            try:
                if not getattr(m, "is_alive", True):
                    continue
            except Exception:
                continue
            try:
                dist = float(distance_between_models_bases_3d(model, m))
            except Exception:
                dist = float("inf")
            if dist < best:
                best = dist
        return best

    def _model_can_see_unit(self, model, unit, game_map) -> bool:
        try:
            caster_unit = getattr(model, "parent_unit", None)
            if caster_unit is None:
                return False
            return bool(caster_unit._has_line_of_sight_to_target(model, unit, game_map))
        except Exception:
            return False

    def _eligible_enemy_targets(self, caster_model, game_map) -> list:
        if caster_model is None or game_map is None:
            return []
        caster_unit = getattr(caster_model, "parent_unit", None)
        if caster_unit is None:
            return []
        range_limit = self._ritual_range_for_model(caster_model)
        try:
            enemies = list(game_map.get_enemy_units(caster_unit))
        except Exception:
            enemies = []
        out = []
        for unit in enemies:
            if not self._unit_is_available(unit):
                continue
            if not self._model_can_see_unit(caster_model, unit, game_map):
                continue
            dist = self._distance_model_to_unit(caster_model, unit)
            if dist > range_limit:
                continue
            out.append(unit)
        return out

    def _eligible_friendly_targets(self, caster_model, game_map) -> list:
        if caster_model is None or game_map is None:
            return []
        caster_unit = getattr(caster_model, "parent_unit", None)
        if caster_unit is None:
            return []
        range_limit = self._ritual_range_for_model(caster_model)
        try:
            friends = list(game_map.get_friendly_units(caster_unit))
        except Exception:
            friends = []
        out = []
        for unit in friends:
            if not self._unit_is_available(unit):
                continue
            try:
                if not (unit.has_any_keyword("THOUSAND SONS") or unit.has_any_keyword("SCINTILLATING LEGIONS")):
                    continue
            except Exception:
                continue
            if not self._model_can_see_unit(caster_model, unit, game_map):
                continue
            dist = self._distance_model_to_unit(caster_model, unit)
            if dist > range_limit:
                continue
            out.append(unit)
        return out

    def get_eligible_targets(self, ritual: CabalRitual, caster_model, game_map) -> list:
        if ritual.target_kind == "friendly":
            targets = self._eligible_friendly_targets(caster_model, game_map)
            if not targets:
                return []
            # Must not be within engagement range of an enemy unit.
            filtered = []
            for unit in targets:
                try:
                    enemies = list(game_map.get_enemy_units(unit))
                except Exception:
                    enemies = []
                engaged = False
                for enemy in enemies:
                    try:
                        if game_map.is_within_engagement_range(unit, enemy):
                            engaged = True
                            break
                    except Exception:
                        continue
                if not engaged:
                    filtered.append(unit)
            return filtered

        targets = self._eligible_enemy_targets(caster_model, game_map)
        if ritual.key == RITUAL_DOOMBOLT.key:
            # Lone Operative can only be targeted within 12".
            lone_operative_range = self._doombolt_lone_operative_range_for_model(caster_model)
            filtered = []
            for unit in targets:
                try:
                    if unit.has_lone_operative():
                        dist = self._distance_model_to_unit(caster_model, unit)
                        if dist > lone_operative_range:
                            continue
                except Exception:
                    pass
                filtered.append(unit)
            return filtered
        return targets

    def _is_valid_target(self, ritual: CabalRitual, caster_model, target_unit, game_map) -> bool:
        if ritual is None:
            return False
        if ritual.target_kind == "friendly":
            return target_unit in self.get_eligible_targets(ritual, caster_model, game_map)
        if ritual.target_kind == "enemy":
            return target_unit in self.get_eligible_targets(ritual, caster_model, game_map)
        return False

    def _is_ts_or_scintillating(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return unit.has_any_keyword("THOUSAND SONS") or unit.has_any_keyword("SCINTILLATING LEGIONS")
        except Exception:
            return False

    def attempt_ritual(
        self,
        game,
        *,
        caster_model,
        ritual_key: str,
        target_unit=None,
        rolls: Optional[list[int]] = None,
        channel_decision: Optional[bool] = None,
        mortal_roll: Optional[int] = None,
    ) -> dict:
        result = {
            "success": False,
            "ritual_key": ritual_key,
            "rolls": [],
            "total": 0,
            "channeled": False,
            "mortal_wounds": 0,
            "target_mortal_wounds": 0,
            "reason": "",
        }
        if game is None or caster_model is None:
            result["reason"] = "missing game or caster"
            return result
        player = None
        try:
            player = getattr(getattr(self.army, "player", None), "name", None)
        except Exception:
            player = None

        ritual = next((r for r in DEFAULT_RITUALS if r.key == ritual_key), None)
        if ritual is None:
            result["reason"] = "unknown ritual"
            return result
        if not self._army_has_cabal():
            result["reason"] = "army lacks cabal"
            return result
        try:
            self._reset_for_shooting_phase(game, getattr(self.army, "player", None))
        except Exception:
            pass
        try:
            if hasattr(game, "is_shooting_phase") and not game.is_shooting_phase():
                result["reason"] = "not shooting phase"
                return result
            if hasattr(game, "get_current_player") and game.get_current_player() is not getattr(self.army, "player", None):
                result["reason"] = "not current player"
                return result
        except Exception:
            pass

        caster_unit = getattr(caster_model, "parent_unit", None)
        if caster_unit is None or not self._unit_has_cabal(caster_unit):
            result["reason"] = "caster lacks cabal"
            return result
        if not self._unit_is_available(caster_unit):
            result["reason"] = "caster unavailable"
            return result

        try:
            model_id = str(getattr(caster_model, "id", "") or getattr(caster_model, "_id", ""))
        except Exception:
            model_id = ""
        if model_id and int(self.used_models.get(model_id, 0) or 0) >= int(
            self._ritual_attempt_limit_for_model(caster_model) or 1
        ):
            result["reason"] = "model already used"
            return result
        incandaeum_override = False
        if ritual.key in self.used_rituals:
            if self._incandaeum_can_override(caster_model, ritual.key):
                incandaeum_override = True
            else:
                result["reason"] = "ritual already used"
                return result

        game_map = getattr(game, "map", None)
        if ritual.target_kind in ("enemy", "friendly"):
            if target_unit is None:
                result["reason"] = "missing target"
                return result
            if not self._is_valid_target(ritual, caster_model, target_unit, game_map):
                result["reason"] = "invalid target"
                return result

        # Mark the model/ritual as used as soon as we attempt the ritual.
        if model_id:
            current = int(self.used_models.get(model_id, 0) or 0)
            self.used_models[model_id] = current + 1
        self.used_rituals.add(ritual.key)
        if incandaeum_override:
            self._mark_incandaeum_override_used(caster_model)

        # Roll 2D6 first.
        provided_rolls = list(rolls or [])
        base_rolls = list(provided_rolls)
        while len(base_rolls) < 2:
            base_rolls.append(int(get_roll("D6") or 0))
        base_rolls = base_rolls[:2]
        total_rolls = list(base_rolls)

        # Decide whether to Channel the Warp (after seeing the 2D6 roll).
        channel = None
        if channel_decision is not None:
            channel = bool(channel_decision)
        else:
            channel = False
        if channel:
            if len(provided_rolls) >= 3:
                extra = int(provided_rolls[2])
            else:
                extra = int(get_roll("D6") or 0)
            total_rolls.append(extra)
        result["channeled"] = bool(channel)

        # Apply mortal wounds for doubles/triples only if Channel the Warp was used.
        if channel:
            if len(set(total_rolls)) < len(total_rolls):
                mw = mortal_roll
                if mw is None:
                    try:
                        mw, _dice = DiceCollection.from_string("D3").roll_detailed()
                    except Exception:
                        mw = 0
                result["mortal_wounds"] = int(mw or 0)
                try:
                    caster_unit._apply_mortal_wounds_to_unit(
                        caster_unit,
                        int(mw or 0),
                        game_map=game_map,
                        is_psychic_attack=True,
                    )
                except TypeError:
                    try:
                        caster_unit._apply_mortal_wounds_to_unit(
                            caster_unit,
                            int(mw or 0),
                            game_map=game_map,
                        )
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    if not getattr(caster_model, "is_alive", True):
                        result["reason"] = "caster destroyed"
                        result["rolls"] = total_rolls
                        result["total"] = int(sum(total_rolls))
                        return self._finalize_ritual_result(
                            game, ritual, caster_unit, caster_model, target_unit, result
                        )
                except Exception:
                    pass

        total = int(sum(total_rolls))
        total += int(self._ritual_test_bonus_for_model(caster_model, channel=bool(channel)) or 0)
        result["rolls"] = total_rolls
        result["total"] = total

        if total < int(ritual.warp_charge):
            result["reason"] = "failed test"
            return self._finalize_ritual_result(game, ritual, caster_unit, caster_model, target_unit, result)

        # Ritual effects
        if ritual.key == RITUAL_DESTINYS_RUIN.key:
            sr = getattr(target_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["cabal_destinys_ruin_mode"] = "full" if total >= 10 else "ones"
            sr["cabal_destinys_ruin_owner"] = str(getattr(self.army, "_id", "") or "")
            try:
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "SHOOTING_PHASE").strip().upper()
            except Exception:
                pname = "SHOOTING_PHASE"
            sr["cabal_destinys_ruin_expires_phase"] = pname
            target_unit.special_rules = sr

        elif ritual.key == RITUAL_TWIST_OF_FATE.key:
            sr = getattr(target_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["cabal_twist_of_fate_ap_bonus"] = 2 if total >= 12 else 1
            sr["cabal_twist_of_fate_owner"] = str(getattr(self.army, "_id", "") or "")
            try:
                pname = str(getattr(getattr(game, "phase", None), "name", "") or "SHOOTING_PHASE").strip().upper()
            except Exception:
                pname = "SHOOTING_PHASE"
            sr["cabal_twist_of_fate_expires_phase"] = pname
            target_unit.special_rules = sr

        elif ritual.key == RITUAL_DOOMBOLT.key:
            dmg = 0
            if total >= 11:
                try:
                    d3 = int(get_roll("D3") or 0)
                except Exception:
                    d3 = 0
                dmg = int(d3) + 3
            else:
                try:
                    dmg = int(get_roll("D3") or 0)
                except Exception:
                    dmg = 0
            try:
                target_unit._apply_mortal_wounds_to_unit(
                    target_unit,
                    int(dmg or 0),
                    game_map=game_map,
                    is_psychic_attack=True,
                )
            except TypeError:
                try:
                    target_unit._apply_mortal_wounds_to_unit(
                        target_unit,
                        int(dmg or 0),
                        game_map=game_map,
                    )
                except Exception:
                    pass
            except Exception:
                pass
            try:
                from .thousand_sons_psychic_marks import mark_target_hit_by_thousand_sons_psychic_attack

                owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
                if owner_id:
                    mark_target_hit_by_thousand_sons_psychic_attack(
                        game,
                        target_unit=target_unit,
                        owner_id=owner_id,
                    )
            except Exception:
                pass
            result["target_mortal_wounds"] = int(dmg or 0)

        elif ritual.key == RITUAL_TEMPORAL_SURGE.key:
            try:
                move_max = 6 if total >= 10 else int(get_roll("D6") or 0)
            except Exception:
                move_max = 0
            sr = getattr(target_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["cabal_temporal_surge_move_max"] = int(move_max or 0)
            sr["cabal_temporal_surge_no_charge_turn_owner"] = str(getattr(getattr(self.army, "player", None), "id", "") or "")
            sr["cabal_temporal_surge_no_charge_turn"] = int(getattr(game, "turn", 0) or 0)
            target_unit.special_rules = sr
            try:
                if game is not None and hasattr(game, "event_system"):
                    game.event_system.publish(
                        "cabal_temporal_surge_move",
                        player=getattr(self.army, "player", None),
                        unit=target_unit,
                        max_distance=int(move_max or 0),
                        caster=caster_unit,
                    )
            except Exception:
                pass

        result["success"] = True
        return self._finalize_ritual_result(game, ritual, caster_unit, caster_model, target_unit, result)
