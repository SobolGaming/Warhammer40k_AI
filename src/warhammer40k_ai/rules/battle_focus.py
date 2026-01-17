from __future__ import annotations

from typing import Optional

from ..utility.ability_support import ABILITY_BATTLE_FOCUS, army_has_ability_id


class BattleFocusManager:
    """
    Army Rule: Battle Focus.

    Tracks Battle Focus tokens and Agile Manoeuvre usage limits.
    """

    MANEUVER_SWIFT = "SWIFT_AS_THE_WIND"
    MANEUVER_FLITTING = "FLITTING_SHADOWS"
    MANEUVER_STAR_ENGINES = "STAR_ENGINES"
    MANEUVER_SUDDEN_STRIKE = "SUDDEN_STRIKE"
    MANEUVER_OPPORTUNITY = "OPPORTUNITY_SEIZED"
    MANEUVER_FADE_BACK = "FADE_BACK"

    def __init__(self, army=None):
        self.army = army
        self.tokens: int = 0
        self._battle_round: Optional[int] = None
        self._phase_key: Optional[tuple] = None
        self._units_used_this_phase: set[str] = set()
        self._maneuvers_used_this_phase: set[str] = set()

    def _army_has_battle_focus(self) -> bool:
        army = self.army
        if army is None:
            return False
        return army_has_ability_id(army, ABILITY_BATTLE_FOCUS)

    def is_warhost_detachment(self) -> bool:
        army = self.army
        mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
        if mgr is None:
            return False
        try:
            return bool(mgr.is_warhost_detachment())
        except Exception:
            return False

    def _unit_has_battle_focus(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if unit.has_any_keyword("ASURYANI") or unit.has_any_keyword("DRUKHARI"):
                return True
        except Exception:
            pass
        for obj in (unit, getattr(unit, "get_attached_unit_root", lambda: unit)()):
            try:
                for ab in (getattr(obj, "possible_abilities", []) or []):
                    if str(getattr(ab, "name", "") or "").strip().lower() == "battle focus":
                        return True
            except Exception:
                continue
        return False

    def _unit_id(self, unit) -> str:
        try:
            return str(getattr(unit, "_id", None) or id(unit))
        except Exception:
            return str(id(unit))

    def _sync_phase(self, game) -> None:
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        try:
            phase = getattr(game, "phase", None)
            pname = str(getattr(phase, "name", "") or phase or "")
        except Exception:
            pname = ""
        key = (br, pname.strip().upper())
        if self._phase_key != key:
            self._phase_key = key
            self._units_used_this_phase = set()
            self._maneuvers_used_this_phase = set()

    def _tokens_for_battlefield(self, game) -> int:
        size_name = ""
        try:
            size = getattr(getattr(game, "battlefield", None), "size", None)
            size_name = str(getattr(size, "name", "") or size or "")
        except Exception:
            size_name = ""
        size_name = size_name.strip().upper().replace(" ", "_")
        if "INCURSION" in size_name:
            return 2
        if "STRIKE_FORCE" in size_name or "STRIKEFORCE" in size_name:
            return 4
        if "ONSLAUGHT" in size_name:
            return 6

        # Fallback by points limit if battlefield size is unknown.
        try:
            pts = int(getattr(self.army, "points_limit", 0) or 0)
        except Exception:
            pts = 0
        if pts >= 3000:
            return 6
        if pts >= 2000:
            return 4
        if pts >= 1000:
            return 2
        return 0

    def _unit_on_battlefield_or_embarked(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if bool(getattr(unit, "deployed", False)) and str(getattr(unit, "reserve_status", "deployed")) == "deployed":
                return True
        except Exception:
            pass
        try:
            transport = getattr(unit, "embarked_in", None)
        except Exception:
            transport = None
        if transport is None:
            return False
        try:
            if bool(getattr(transport, "deployed", False)) and str(getattr(transport, "reserve_status", "deployed")) == "deployed":
                return True
        except Exception:
            return False
        return False

    def _bonus_tokens_from_timeless_strategist(self, game) -> int:
        army = self.army
        if army is None:
            return 0
        if not self.is_warhost_detachment():
            return 0
        bonus = 0
        for u in list(getattr(army, "units", []) or []):
            try:
                if not getattr(u, "is_alive", lambda: True)():
                    continue
            except Exception:
                pass
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            val = int(sr.get("enhancement_timeless_strategist_battle_focus_bonus", 0) or 0)
            if val <= 0:
                continue
            if not self._unit_on_battlefield_or_embarked(u):
                continue
            bonus += val
        return int(bonus)

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self._army_has_battle_focus():
            return
        if game is None:
            try:
                game = getattr(getattr(self.army, "player", None), "game", None)
            except Exception:
                game = None
        self.tokens = int(self._tokens_for_battlefield(game))
        if self.is_warhost_detachment():
            self.tokens += 1
        try:
            bonus = int(self._bonus_tokens_from_timeless_strategist(game))
        except Exception:
            bonus = 0
        if bonus:
            self.tokens += int(bonus)
            try:
                print(f"âœ¨ Timeless Strategist: +{bonus} Battle Focus token(s)")
            except Exception:
                pass
        self._battle_round = int(battle_round or 0)
        self._phase_key = None
        self._units_used_this_phase = set()
        self._maneuvers_used_this_phase = set()

    def _can_use_unit_this_phase(self, unit) -> bool:
        uid = self._unit_id(unit)
        return uid not in self._units_used_this_phase

    def _mark_used(self, unit, maneuver: str) -> None:
        uid = self._unit_id(unit)
        self._units_used_this_phase.add(uid)
        if maneuver != self.MANEUVER_SWIFT:
            self._maneuvers_used_this_phase.add(maneuver)

    def _maneuver_used_this_phase(self, maneuver: str) -> bool:
        if maneuver == self.MANEUVER_SWIFT:
            return False
        return maneuver in self._maneuvers_used_this_phase

    def _spend_token(self) -> bool:
        if int(self.tokens or 0) <= 0:
            return False
        self.tokens = int(self.tokens) - 1
        return True

    def _should_use(self, player, key: str, ctx: dict) -> bool:
        try:
            return bool(player._should_use_optional_ability(key, ctx))
        except Exception:
            return False

    def _choose_from_options(self, player, key: str, options: list, ctx: dict):
        try:
            chooser = getattr(player, "_choose_optional_value", None)
            if callable(chooser):
                choice = chooser(key, list(options), dict(ctx or {}))
                if isinstance(choice, bool):
                    return None
                if choice in options:
                    return choice
                # Allow selecting by unit name or index if options are units.
                if isinstance(choice, str):
                    for opt in options:
                        if str(getattr(opt, "name", "") or "").strip().lower() == choice.strip().lower():
                            return opt
                if isinstance(choice, int):
                    idx = int(choice)
                    if 0 <= idx < len(options):
                        return options[idx]
        except Exception:
            pass
        return None

    # ---------------- Query helpers (UI/agents) ----------------

    def get_move_maneuver_options(self, unit, action: str, game) -> list[str]:
        if unit is None or game is None:
            return []
        if not self._army_has_battle_focus():
            return []
        if not self._unit_has_battle_focus(unit):
            return []
        if int(self.tokens or 0) <= 0:
            return []
        self._sync_phase(game)
        if not self._can_use_unit_this_phase(unit):
            return []

        act = str(action or "").strip().lower()
        options: list[str] = []
        if act in ("move", "advance", "fall_back"):
            if not self._maneuver_used_this_phase(self.MANEUVER_SWIFT):
                options.append(self.MANEUVER_SWIFT)
            if not self._maneuver_used_this_phase(self.MANEUVER_FLITTING):
                options.append(self.MANEUVER_FLITTING)
            if act == "advance" and bool(getattr(unit, "is_vehicle", False)):
                if not self._maneuver_used_this_phase(self.MANEUVER_STAR_ENGINES):
                    options.append(self.MANEUVER_STAR_ENGINES)
        return options

    def can_use_flitting_on_charge(self, unit, game) -> bool:
        if unit is None or game is None:
            return False
        if not self._army_has_battle_focus():
            return False
        if not self._unit_has_battle_focus(unit):
            return False
        if int(self.tokens or 0) <= 0:
            return False
        self._sync_phase(game)
        if not self._can_use_unit_this_phase(unit):
            return False
        if self._maneuver_used_this_phase(self.MANEUVER_FLITTING):
            return False
        return True

    def can_use_flitting_on_setup(self, unit, game) -> bool:
        if unit is None or game is None:
            return False
        if not self._army_has_battle_focus():
            return False
        if not self._unit_has_battle_focus(unit):
            return False
        try:
            if not bool(getattr(game, "setup_complete", True)):
                return False
        except Exception:
            return False
        if int(self.tokens or 0) <= 0:
            return False
        self._sync_phase(game)
        if not self._can_use_unit_this_phase(unit):
            return False
        if self._maneuver_used_this_phase(self.MANEUVER_FLITTING):
            return False
        return True

    def can_use_sudden_strike(self, unit, game) -> bool:
        if unit is None or game is None:
            return False
        if not self._army_has_battle_focus():
            return False
        if not self._unit_has_battle_focus(unit):
            return False
        if int(self.tokens or 0) <= 0:
            return False
        self._sync_phase(game)
        if not self._can_use_unit_this_phase(unit):
            return False
        if self._maneuver_used_this_phase(self.MANEUVER_SUDDEN_STRIKE):
            return False
        return True

    def get_fade_back_candidates(self, hit_units: list, game) -> list:
        if not hit_units or game is None:
            return []
        if not self._army_has_battle_focus():
            return []
        if int(self.tokens or 0) <= 0:
            return []
        self._sync_phase(game)
        if self._maneuver_used_this_phase(self.MANEUVER_FADE_BACK):
            return []

        candidates = []
        for unit in hit_units:
            if unit is None:
                continue
            try:
                if not unit.is_alive() or not getattr(unit, "deployed", False):
                    continue
            except Exception:
                continue
            if not self._unit_has_battle_focus(unit):
                continue
            if bool(getattr(unit, "is_titanic", False)):
                continue
            if not self._can_use_unit_this_phase(unit):
                continue
            candidates.append(unit)
        return candidates

    def apply_maneuver(self, unit, maneuver: str, game) -> bool:
        if unit is None or game is None:
            return False
        if not self._army_has_battle_focus():
            return False
        if not self._unit_has_battle_focus(unit):
            return False
        self._sync_phase(game)
        before = int(self.tokens or 0)
        uid = self._unit_id(unit)
        used_before = uid in self._units_used_this_phase
        self._apply_maneuver(unit, maneuver, game)
        if int(self.tokens or 0) < before:
            return True
        return (uid in self._units_used_this_phase) and not used_before

    def apply_reactive_maneuver(self, unit, maneuver: str, game) -> bool:
        if unit is None or game is None:
            return False
        if not self._army_has_battle_focus():
            return False
        if not self._unit_has_battle_focus(unit):
            return False
        self._sync_phase(game)
        before = int(self.tokens or 0)
        uid = self._unit_id(unit)
        used_before = uid in self._units_used_this_phase
        self._apply_reactive_move(unit, maneuver, game)
        if int(self.tokens or 0) < before:
            return True
        return (uid in self._units_used_this_phase) and not used_before

    # ---------------- Trigger handlers ----------------

    def maybe_trigger_move_maneuvers(self, unit, action: str, game) -> None:
        if unit is None or game is None:
            return
        if not self._army_has_battle_focus():
            return
        if not self._unit_has_battle_focus(unit):
            return
        if int(self.tokens or 0) <= 0:
            return
        self._sync_phase(game)
        if not self._can_use_unit_this_phase(unit):
            return

        act = str(action or "").strip().lower()
        options: list[str] = []
        if act in ("move", "advance", "fall_back"):
            if not self._maneuver_used_this_phase(self.MANEUVER_SWIFT):
                options.append(self.MANEUVER_SWIFT)
            if not self._maneuver_used_this_phase(self.MANEUVER_FLITTING):
                options.append(self.MANEUVER_FLITTING)
            if act == "advance" and bool(getattr(unit, "is_vehicle", False)):
                if not self._maneuver_used_this_phase(self.MANEUVER_STAR_ENGINES):
                    options.append(self.MANEUVER_STAR_ENGINES)
        if not options:
            return

        player = getattr(self.army, "player", None)
        ctx = {
            "ability_name": "Battle Focus",
            "trigger": "move",
            "unit": getattr(unit, "name", "") or "",
            "action": act,
            "options": list(options),
            "tokens": int(self.tokens or 0),
        }

        chosen = None
        if len(options) == 1:
            key = f"BATTLE_FOCUS_{options[0]}"
            if self._should_use(player, key, ctx):
                chosen = options[0]
        else:
            chosen = self._choose_from_options(player, "BATTLE_FOCUS_MOVE_MANEUVER", options, ctx)
        if chosen:
            self._apply_maneuver(unit, chosen, game)

    def maybe_trigger_charge_maneuver(self, unit, target, game) -> None:
        if unit is None or game is None:
            return
        if not self._army_has_battle_focus():
            return
        if not self._unit_has_battle_focus(unit):
            return
        if int(self.tokens or 0) <= 0:
            return
        self._sync_phase(game)
        if not self._can_use_unit_this_phase(unit):
            return
        if self._maneuver_used_this_phase(self.MANEUVER_FLITTING):
            return

        player = getattr(self.army, "player", None)
        ctx = {
            "ability_name": "Battle Focus",
            "trigger": "charge_declared",
            "unit": getattr(unit, "name", "") or "",
            "target": getattr(target, "name", "") or "",
            "tokens": int(self.tokens or 0),
        }
        if self._should_use(player, "BATTLE_FOCUS_FLITTING_SHADOWS", ctx):
            self._apply_maneuver(unit, self.MANEUVER_FLITTING, game)

    def maybe_trigger_setup_maneuver(self, unit, game) -> None:
        if unit is None or game is None:
            return
        if not self._army_has_battle_focus():
            return
        if not self._unit_has_battle_focus(unit):
            return
        try:
            if not bool(getattr(game, "setup_complete", True)):
                return
        except Exception:
            pass
        if int(self.tokens or 0) <= 0:
            return
        self._sync_phase(game)
        if not self._can_use_unit_this_phase(unit):
            return
        if self._maneuver_used_this_phase(self.MANEUVER_FLITTING):
            return
        player = getattr(self.army, "player", None)
        ctx = {
            "ability_name": "Battle Focus",
            "trigger": "setup",
            "unit": getattr(unit, "name", "") or "",
            "tokens": int(self.tokens or 0),
        }
        if self._should_use(player, "BATTLE_FOCUS_FLITTING_SHADOWS", ctx):
            self._apply_maneuver(unit, self.MANEUVER_FLITTING, game)

    def maybe_trigger_sudden_strike(self, unit, game) -> None:
        if unit is None or game is None:
            return
        if not self._army_has_battle_focus():
            return
        if not self._unit_has_battle_focus(unit):
            return
        if int(self.tokens or 0) <= 0:
            return
        self._sync_phase(game)
        if not self._can_use_unit_this_phase(unit):
            return
        if self._maneuver_used_this_phase(self.MANEUVER_SUDDEN_STRIKE):
            return

        player = getattr(self.army, "player", None)
        ctx = {
            "ability_name": "Battle Focus",
            "trigger": "fight_selected",
            "unit": getattr(unit, "name", "") or "",
            "tokens": int(self.tokens or 0),
        }
        if self._should_use(player, "BATTLE_FOCUS_SUDDEN_STRIKE", ctx):
            self._apply_maneuver(unit, self.MANEUVER_SUDDEN_STRIKE, game)

    def maybe_trigger_opportunity_seized(self, moving_unit, game) -> None:
        if moving_unit is None or game is None:
            return
        if not self._army_has_battle_focus():
            return
        self._sync_phase(game)
        if self._maneuver_used_this_phase(self.MANEUVER_OPPORTUNITY):
            return
        if int(self.tokens or 0) <= 0:
            return

        return

    def maybe_trigger_fade_back(self, attacker_unit, target_unit, hits: int, game) -> None:
        if target_unit is None or game is None:
            return
        if not self._army_has_battle_focus():
            return
        try:
            if int(hits or 0) <= 0:
                return
        except Exception:
            return
        self._sync_phase(game)
        if self._maneuver_used_this_phase(self.MANEUVER_FADE_BACK):
            return
        if int(self.tokens or 0) <= 0:
            return
        if not self._unit_has_battle_focus(target_unit):
            return
        if bool(getattr(target_unit, "is_titanic", False)):
            return
        if not self._can_use_unit_this_phase(target_unit):
            return

        player = getattr(self.army, "player", None)
        ctx = {
            "ability_name": "Battle Focus",
            "trigger": "fade_back",
            "attacker": getattr(attacker_unit, "name", "") or "",
            "unit": getattr(target_unit, "name", "") or "",
            "hits": int(hits or 0),
            "tokens": int(self.tokens or 0),
        }
        if self._should_use(player, "BATTLE_FOCUS_FADE_BACK", ctx):
            self._apply_reactive_move(target_unit, self.MANEUVER_FADE_BACK, game)

    # ---------------- Effects ----------------

    def _apply_maneuver(self, unit, maneuver: str, game) -> None:
        if unit is None or game is None:
            return
        if not self._can_use_unit_this_phase(unit):
            return
        if self._maneuver_used_this_phase(maneuver):
            return
        if not self._spend_token():
            return

        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}

        phase = getattr(game, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "").strip().upper()
        try:
            current_player = getattr(game, "get_current_player", lambda: None)()
        except Exception:
            current_player = None
        current_player_name = str(getattr(current_player, "name", "") or "")

        if maneuver == self.MANEUVER_SWIFT:
            from ..utility.modifiers import Modifier, ModifierOp
            swift_bonus = 2
            if self.is_warhost_detachment():
                swift_bonus += 1
            unit.add_characteristic_modifier(
                "movement",
                Modifier(ModifierOp.ADD, swift_bonus, source="battle_focus:swift_as_the_wind"),
            )
            sr["battle_focus_swift_as_the_wind_expires_phase"] = phase_name
        elif maneuver == self.MANEUVER_FLITTING:
            sr["battle_focus_flitting_shadows_no_overwatch"] = True
            sr["battle_focus_flitting_shadows_turn_owner"] = current_player_name
        elif maneuver == self.MANEUVER_STAR_ENGINES:
            sr["battle_focus_star_engines_active"] = True
            sr["battle_focus_star_engines_turn_owner"] = current_player_name
        elif maneuver == self.MANEUVER_SUDDEN_STRIKE:
            sr["battle_focus_sudden_strike_expires_phase"] = phase_name

        unit.special_rules = sr
        self._mark_used(unit, maneuver)

    def _apply_reactive_move(self, unit, maneuver: str, game) -> None:
        if unit is None or game is None:
            return
        if not self._can_use_unit_this_phase(unit):
            return
        if self._maneuver_used_this_phase(maneuver):
            return
        if not self._spend_token():
            return

        try:
            from ..utility.dice import get_roll
            roll = int(get_roll("D6"))
        except Exception:
            roll = 1
        if self.is_warhost_detachment():
            roll += 1
        max_dist = int(roll) + 1
        phase = getattr(game, "phase", None)
        phase_name = str(getattr(phase, "name", "") or phase or "").strip().upper()

        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["battle_focus_reactive_move_max"] = max_dist
        sr["battle_focus_reactive_move_source"] = str(maneuver)
        sr["battle_focus_reactive_move_expires_phase"] = phase_name
        unit.special_rules = sr

        self._mark_used(unit, maneuver)

    def cleanup_on_phase_end(self, phase, player) -> None:
        pname = str(getattr(phase, "name", "") or phase or "").strip().upper()
        if not pname:
            return
        player_name = str(getattr(player, "name", "") or "")
        try:
            units = list(getattr(self.army, "units", []) or [])
        except Exception:
            units = []
        for u in units:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue

            # End-of-phase cleanup for Swift as the Wind and Sudden Strike.
            try:
                if str(sr.get("battle_focus_swift_as_the_wind_expires_phase", "") or "").strip().upper() == pname:
                    try:
                        u.remove_characteristic_modifiers_by_source("battle_focus:swift_as_the_wind")
                    except Exception:
                        pass
                    sr.pop("battle_focus_swift_as_the_wind_expires_phase", None)
            except Exception:
                pass
            try:
                if str(sr.get("battle_focus_sudden_strike_expires_phase", "") or "").strip().upper() == pname:
                    sr.pop("battle_focus_sudden_strike_expires_phase", None)
            except Exception:
                pass

            # Pending reactive moves expire at end of the current phase.
            try:
                if str(sr.get("battle_focus_reactive_move_expires_phase", "") or "").strip().upper() == pname:
                    for k in (
                        "battle_focus_reactive_move_max",
                        "battle_focus_reactive_move_source",
                        "battle_focus_reactive_move_expires_phase",
                    ):
                        sr.pop(k, None)
            except Exception:
                pass

            # End-of-turn cleanup (end of Fight phase for the current player).
            if pname == "FIGHT_PHASE":
                try:
                    if str(sr.get("battle_focus_flitting_shadows_turn_owner", "") or "") == player_name:
                        sr.pop("battle_focus_flitting_shadows_no_overwatch", None)
                        sr.pop("battle_focus_flitting_shadows_turn_owner", None)
                except Exception:
                    pass
                try:
                    if str(sr.get("battle_focus_star_engines_turn_owner", "") or "") == player_name:
                        sr.pop("battle_focus_star_engines_active", None)
                        sr.pop("battle_focus_star_engines_turn_owner", None)
                except Exception:
                    pass
        return
