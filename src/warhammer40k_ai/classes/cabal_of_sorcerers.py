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
        self.used_models: set[str] = set()
        self._last_reset_key: Optional[tuple] = None

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

    def _log_ritual_result(self, ritual, caster_unit, caster_model, target_unit, result: dict) -> None:
        try:
            from ..utility.event_bus import append_action, append_dice
        except Exception:
            return
        try:
            player_name = str(getattr(getattr(self.army, "player", None), "name", "") or "")
        except Exception:
            player_name = ""
        if not player_name:
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
            player_name,
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
            player_name,
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

    def get_available_rituals(self) -> list[CabalRitual]:
        return [r for r in DEFAULT_RITUALS if r.key not in self.used_rituals]

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
        if model_id and model_id in self.used_models:
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
            is_embarked = getattr(unit, "is_embarked", None)
            if callable(is_embarked) and bool(is_embarked()):
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
            if dist > 24.0:
                continue
            out.append(unit)
        return out

    def _eligible_friendly_targets(self, caster_model, game_map) -> list:
        if caster_model is None or game_map is None:
            return []
        caster_unit = getattr(caster_model, "parent_unit", None)
        if caster_unit is None:
            return []
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
            if dist > 24.0:
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
            filtered = []
            for unit in targets:
                try:
                    if unit.has_lone_operative():
                        dist = self._distance_model_to_unit(caster_model, unit)
                        if dist > 12.0:
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
        if model_id and model_id in self.used_models:
            result["reason"] = "model already used"
            return result
        if ritual.key in self.used_rituals:
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
            self.used_models.add(model_id)
        self.used_rituals.add(ritual.key)

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
            try:
                ctx = {"ritual": ritual.name, "rolls": list(base_rolls)}
                army_player = getattr(self.army, "player", None)
                if army_player is not None:
                    channel = bool(army_player._should_use_optional_ability("CABAL_CHANNEL_WARP", ctx))
            except Exception:
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
            sr["cabal_temporal_surge_no_charge_turn_owner"] = str(getattr(getattr(self.army, "player", None), "name", "") or "")
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
