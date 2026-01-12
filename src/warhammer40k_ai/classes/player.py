# This is the player that gets put onto a Battlefield and has an Army

import logging
from typing import Any
from enum import Enum, auto
from .army import Army
from .unit import Unit
from warhammer40k_ai.classes.map import Objective
from .mission_cards import PrimaryMissionCard, SecondaryMissionCard, default_secondary_deck
from warhammer40k_ai.utility.calcs import get_dist

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class PlayerType(Enum):
    AI = auto()
    HUMAN = auto()
    RANDOM = auto()
    NULL = auto()


class Player:
    def __init__(self, name: str, player_type: PlayerType = PlayerType.NULL, army: Army = None):
        self.name = name
        if player_type not in (PlayerType.AI, PlayerType.HUMAN):
            raise ValueError(f"Invalid player type: {player_type}")
        self.type = player_type
        self.round: int = 0
        self.command_points: int = 0  # Players start with 0 Command Points in 10th edition
        self.army: Army = army
        # ---- Victory Points (VP) ----
        # Total VP scored across the battle (capped by mission pack rules in Game awarding logic).
        self.score: int = 0
        # Breakdown by source (kept in-sync by Game awarding logic).
        self.vp_primary: int = 0
        self.vp_secondary: int = 0
        self.vp_battle_ready: int = 0
        # Chronological VP log entries (most recent last).
        self.vp_history: list[dict[str, Any]] = []
        # Chronological CP log entries (most recent last).
        self.cp_history: list[dict[str, Any]] = []
        # Battle Ready (painted) bonus: assume TRUE by default per project rules.
        self.is_battle_ready: bool = True
        # Mission cards
        self.primary_mission: PrimaryMissionCard | None = None
        self.secondary_deck: list[SecondaryMissionCard] = []
        self.active_secondaries: list[SecondaryMissionCard] = []
        self.discarded_secondaries: list[SecondaryMissionCard] = []
        # Set the player reference on the army
        if self.army:
            self.army.set_player(self)

        # Core rules: CP gain guardrail (Warhammer Community).
        # Per battle round, a player cannot gain more than 1 CP from sources other than the normal +1CP
        # at the start of their own Command phase, unless an ability explicitly exempts it.
        self.cp_gained_this_battle_round_excluding_normal_command_cp: int = 0
        self._cp_gain_guardrail_battle_round: int | None = None
        # Generic per-battle-round ability usage (e.g. "Once per battle round..." reactions)
        self._ability_used_battle_round: dict[str, int] = {}
        # Optional synchronous decision hook for UI/AI.
        # Signature: fn(player, key: str, context: dict) -> bool
        # If None, optional abilities are NOT auto-used (conservative default).
        self.decision_hook = None
        # One-shot overrides that dialogs can set to drive immediate decisions without requiring
        # a persistent decision_hook. Entries are consumed on first read.
        self._next_optional_decisions: dict[str, bool] = {}
        # One-shot selection overrides for optional ability choices.
        self._next_optional_selections: dict[str, object] = {}
        #print(f"Player {self.name} created with army: {self.army}")
    
    def set_army(self, army: Army) -> None:
        self.army = army
        army.set_player(self)

    def set_game(self, game) -> None:
        """Set the game reference for this player."""
        self.game = game
        try:
            # Lazily attach stratagem manager when a game is set
            from .stratagems import StratagemManager
            self.stratagems = StratagemManager(self)
        except Exception:
            # Do not fail hard if wiring is incomplete
            self.stratagems = None

    def _sync_cp_gain_guardrail_battle_round(self) -> None:
        """Reset per-battle-round CP gain guardrail counter when battle round advances."""
        try:
            br = int(getattr(self.game, "turn", 0) or 0)
        except Exception:
            br = None
        if br is None or br <= 0:
            return
        if self._cp_gain_guardrail_battle_round != br:
            self._cp_gain_guardrail_battle_round = br
            self.cp_gained_this_battle_round_excluding_normal_command_cp = 0

    def get_army(self) -> Army | None:
        return self.army

    def has_unit(self, unit: Unit) -> bool:
        return unit in self.army.units

    def has_units(self) -> bool:
        return len(self.army.units) > 0

    def get_score(self) -> int:
        return self.score

    def add_score(self, points: int) -> None:
        self.score += points

    def get_vp_breakdown(self) -> dict:
        """Return a simple VP breakdown dict. Game logic is the authoritative scorer."""
        return {
            "total": int(self.score or 0),
            "primary": int(self.vp_primary or 0),
            "secondary": int(self.vp_secondary or 0),
            "battle_ready": int(self.vp_battle_ready or 0),
        }
    
    def gain_command_points(self, amount: int = 1, *, is_normal_command_phase_gain: bool = False,
                            exempt_from_guardrail: bool = False, reason: str | None = None) -> int:
        """
        Gain command points, enforcing the core CP gain guardrail:
        - The normal +1CP at the start of your own Command phase is always allowed and does not count.
        - All other CP gains are limited to a maximum of +1 CP per battle round unless exempt.

        Returns the number of CP actually gained (may be less than requested).
        """
        try:
            amount = int(amount or 0)
        except Exception:
            amount = 0
        if amount <= 0:
            return 0

        # Keep battle-round counter fresh
        try:
            self._sync_cp_gain_guardrail_battle_round()
        except Exception:
            pass

        if is_normal_command_phase_gain:
            self.command_points += amount
            self._record_cp_change(amount, reason=reason or "Normal Command phase CP", source="gain")
            return amount

        if exempt_from_guardrail:
            self.command_points += amount
            self._record_cp_change(amount, reason=reason or "Command Points gained", source="gain")
            return amount

        # Guardrail: max +1 CP per battle round from non-normal sources.
        if int(self.cp_gained_this_battle_round_excluding_normal_command_cp or 0) >= 1:
            return 0

        gained = min(amount, 1)
        self.command_points += gained
        self.cp_gained_this_battle_round_excluding_normal_command_cp += 1
        self._record_cp_change(gained, reason=reason or "Command Points gained", source="gain")
        return gained

    def get_normal_command_phase_cp_gain(self) -> int:
        """
        Return the normal CP gained at the start of this player's Command phase.

        Core rules are typically +1CP, but we keep this as an overridable lookup to support
        mission/faction-level variations without hard-coding in Game flow.
        """
        return 1

    def get_command_phase_bonus_cp_gain(self) -> int:
        """
        Return bonus CP gained during *this player's own* Command phase due to abilities while alive.

        This bonus is NOT the normal Command phase CP and is therefore subject to the per-battle-round guardrail.
        """
        army = self.get_army()
        if army is None:
            return 0
        fn = getattr(army, "get_command_phase_bonus_cp_gain", None)
        if callable(fn):
            return int(fn() or 0)
        return 0

    def gain_normal_command_phase_cp(self) -> int:
        """Grant the normal CP at the start of this player's Command phase (does not count toward guardrail)."""
        return self.gain_command_points(self.get_normal_command_phase_cp_gain(), is_normal_command_phase_gain=True, reason="Normal Command phase CP")

    def gain_command_point(self) -> None:
        """Legacy wrapper: gain 1 CP subject to the guardrail (non-normal source)."""
        self.gain_command_points(1)
    
    def spend_command_points(self, amount: int, *, reason: str | None = None, source: str | None = None) -> bool:
        """Spend command points if available"""
        try:
            amount = int(amount or 0)
        except Exception:
            amount = 0
        if amount <= 0:
            return False
        if self.command_points >= amount:
            self.command_points -= amount
            self._record_cp_change(-amount, reason=reason or "Command Points spent", source=source or "spend")
            try:
                if str(source or "").strip().lower() == "stratagem" or "stratagem:" in str(reason or "").lower():
                    from ..utility.event_bus import append_action
                    pname = getattr(self, "name", "Player")
                    strat_name = ""
                    try:
                        if "stratagem:" in str(reason or "").lower():
                            strat_name = str(reason).split(":", 1)[1].strip()
                    except Exception:
                        strat_name = ""
                    if strat_name:
                        append_action(pname, f"Stratagem used: {strat_name} ({amount} CP)")
                    else:
                        append_action(pname, f"Stratagem used ({amount} CP)")
            except Exception:
                pass
            return True
        return False

    def _record_cp_change(self, delta: int, *, reason: str | None = None, source: str | None = None) -> None:
        try:
            delta = int(delta or 0)
        except Exception:
            delta = 0
        if delta == 0:
            return
        try:
            if not hasattr(self, "cp_history") or self.cp_history is None:
                self.cp_history = []
        except Exception:
            return

        game = getattr(self, "game", None)
        try:
            round_val = int(getattr(game, "get_battle_round", lambda: 0)() or 0) if game is not None else 0
        except Exception:
            round_val = 0
        phase_label = None
        try:
            if game is not None and hasattr(game, "_current_phase_label"):
                phase_label = game._current_phase_label()
        except Exception:
            phase_label = None
        if not phase_label:
            try:
                phase = getattr(game, "phase", None) if game is not None else None
                if hasattr(phase, "name"):
                    phase_label = str(phase.name).replace("_", " ").title()
                elif phase is not None:
                    phase_label = str(phase)
            except Exception:
                phase_label = None
        if not phase_label:
            phase_label = "Unknown Phase"

        entry = {
            "round": round_val,
            "phase": phase_label,
            "delta": delta,
            "current": int(getattr(self, "command_points", 0) or 0),
            "reason": reason,
            "source": source,
        }
        try:
            self.cp_history.append(entry)
        except Exception:
            pass

    # ---------------- Stratagem CP modifiers (e.g. Direct the Slaughter) ----------------

    def _battle_round(self) -> int:
        try:
            return int(getattr(self.game, "turn", 0) or 0)
        except Exception:
            return 0

    def _preview_direct_the_slaughter_discount(self, *, target_unit=None) -> int:
        """
        Direct the Slaughter:
        Once per battle round, one model from your army with this ability can use it when a friendly
        WORLD EATERS unit within 12" of that model is targeted with a Stratagem. If it does,
        reduce the CP cost of that Stratagem by 1CP.

        Engine behavior: if eligible and beneficial, we will auto-apply this discount when paying CP.
        """
        if target_unit is None:
            return 0
        try:
            army = self.get_army()
        except Exception:
            army = None
        we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
            return 0
        try:
            if not target_unit.has_any_keyword("WORLD EATERS"):
                return 0
        except Exception:
            return 0

        br = self._battle_round()
        if br <= 0:
            return 0
        if int(self._ability_used_battle_round.get("DIRECT_THE_SLAUGHTER", 0) or 0) == br:
            return 0

        army = self.get_army()
        if army is None:
            return 0
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return 0

        try:
            from warhammer40k_ai.utility.aura_utils import unit_within_range_of_unit
        except Exception:
            return 0

        for u in list(getattr(army, "units", []) or []):
            try:
                if not u.is_alive():
                    continue
            except Exception:
                continue
            has_ability = False
            for ab in (getattr(u, "possible_abilities", []) or []):
                nm = str(getattr(ab, "name", "") or "").strip().lower()
                if nm == "direct the slaughter":
                    has_ability = True
                    break
            if not has_ability:
                continue
            # Range check to the targeted unit
            try:
                if unit_within_range_of_unit(u, target_unit, 12.0, use_attached_aggregate=True):
                    return 1
            except Exception:
                continue
        return 0

    def _target_unit_has_gift_of_foresight(self, target_unit) -> bool:
        if target_unit is None:
            return False
        try:
            members = list(target_unit.get_attached_unit_members())
        except Exception:
            members = [target_unit]
        for u in members:
            try:
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                if not sr.get("enhancement_free_command_reroll_once_per_battle_round", False):
                    continue
            except Exception:
                continue
            try:
                alive = bool(u.is_alive())
            except Exception:
                try:
                    alive = any(getattr(m, "is_alive", True) for m in (getattr(u, "models", []) or []))
                except Exception:
                    alive = True
            if not alive:
                continue
            return True
        return False

    def _preview_gift_of_foresight_discount(self, *, stratagem=None, target_unit=None) -> int:
        """
        Gift of Foresight (Warhost):
        Once per battle round, you can target the bearer's unit with Command Re-roll for 0CP.
        """
        if stratagem is None or target_unit is None:
            return 0
        try:
            army = self.get_army()
        except Exception:
            army = None
        mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
        if mgr is None or not getattr(mgr, "is_warhost_detachment", lambda: False)():
            return 0
        try:
            name = str(getattr(stratagem, "name", "") or "").strip().lower()
        except Exception:
            name = ""
        if name != "command re-roll" and name != "command reroll" and name != "command re-roll":
            return 0
        if not self._target_unit_has_gift_of_foresight(target_unit):
            return 0
        br = self._battle_round()
        if br <= 0:
            return 0
        if int(self._ability_used_battle_round.get("GIFT_OF_FORESIGHT", 0) or 0) == br:
            return 0
        return 1

    def _preview_master_of_the_pageant_discount(self, *, stratagem=None, target_unit=None) -> int:
        """
        Master of the Pageant (Court of the Phoenician):
        Once per battle round, when you target a FULGRIM unit with Sinuous Breach or
        Prideful Superiority, reduce the CP cost by 1.
        """
        if stratagem is None or target_unit is None:
            return 0
        try:
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        except Exception:
            name_u = ""
        if name_u not in ("SINUOUS BREACH", "PRIDEFUL SUPERIORITY"):
            return 0
        try:
            if not target_unit.has_any_keyword("FULGRIM"):
                return 0
        except Exception:
            return 0
        try:
            army = self.get_army()
        except Exception:
            army = None
        mgr = getattr(army, "emperors_children", None) if army is not None else None
        if mgr is None or not getattr(mgr, "is_court_of_the_phoenician", lambda: False)():
            return 0
        try:
            if not mgr.is_emperors_children_unit(target_unit):
                return 0
        except Exception:
            return 0
        br = self._battle_round()
        if br <= 0:
            return 0
        try:
            if int(getattr(mgr, "master_of_pageant_used_round", 0) or 0) == br:
                return 0
        except Exception:
            return 0
        return 1

    def _should_use_optional_ability(self, key: str, context: dict) -> bool:
        """
        Ask the registered decision hook whether to use an optional ability.
        Conservative default: False (do not auto-spend limited resources).
        """
        k = (key or "").strip().upper()
        if k:
            # One-shot override from UI dialog / upstream controller
            if isinstance(getattr(self, "_next_optional_decisions", None), dict) and k in self._next_optional_decisions:
                try:
                    return bool(self._next_optional_decisions.pop(k))
                except Exception:
                    # If pop fails, default to False
                    try:
                        del self._next_optional_decisions[k]
                    except Exception:
                        pass
                    return False
        fn = getattr(self, "decision_hook", None)
        if callable(fn):
            try:
                return bool(fn(self, k or (key or ""), dict(context or {})))
            except Exception:
                return False
        return False

    def _choose_optional_value(self, key: str, options: list, context: dict):
        """
        Ask the decision hook for a concrete choice from a list of options.
        Conservative default: None (no automatic selection).
        """
        k = (key or "").strip().upper()
        if k:
            if isinstance(getattr(self, "_next_optional_selections", None), dict) and k in self._next_optional_selections:
                try:
                    return self._next_optional_selections.pop(k)
                except Exception:
                    try:
                        del self._next_optional_selections[k]
                    except Exception:
                        pass
                    return None
        fn = getattr(self, "decision_hook", None)
        if callable(fn):
            try:
                choice = fn(self, k or (key or ""), dict(context or {}))
                if isinstance(choice, bool):
                    return None
                return choice
            except Exception:
                return None
        return None

    def set_next_optional_decision(self, key: str, value: bool) -> None:
        """Set a one-shot decision override consumed by the next matching optional ability query."""
        k = (key or "").strip().upper()
        if not k:
            return
        if not isinstance(getattr(self, "_next_optional_decisions", None), dict):
            self._next_optional_decisions = {}
        self._next_optional_decisions[k] = bool(value)

    def set_next_optional_selection(self, key: str, value) -> None:
        """Set a one-shot selection override consumed by the next matching optional choice query."""
        k = (key or "").strip().upper()
        if not k:
            return
        if not isinstance(getattr(self, "_next_optional_selections", None), dict):
            self._next_optional_selections = {}
        self._next_optional_selections[k] = value

    def preview_stratagem_cp_cost(self, stratagem, *, target_unit=None, assume_optional_discounts: bool | None = None) -> dict:
        """
        Preview effective CP cost without consuming any once-per-round ability usage.

        NOTE:
        - If `assume_optional_discounts` is True, include available optional discounts in the preview.
        - If False, do not include optional discounts.
        - If None, include optional discounts only if a decision hook exists (meaning UI/AI can decide).
        """
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        discount = 0
        reasons: list[str] = []

        if assume_optional_discounts is None:
            # Default behavior:
            # - If a decision hook exists, assume optional discounts may be used (UI/AI can decide).
            # - Otherwise, assume optional discounts only if a one-shot override explicitly opts in.
            assume_optional_discounts = bool(callable(getattr(self, "decision_hook", None)))
            if not assume_optional_discounts:
                try:
                    overrides = getattr(self, "_next_optional_decisions", {}) or {}
                    if isinstance(overrides, dict):
                        if "DIRECT_THE_SLAUGHTER" in overrides:
                            assume_optional_discounts = bool(overrides.get("DIRECT_THE_SLAUGHTER", False))
                        elif "GIFT_OF_FORESIGHT" in overrides:
                            assume_optional_discounts = bool(overrides.get("GIFT_OF_FORESIGHT", False))
                        elif "MASTER_OF_THE_PAGEANT" in overrides:
                            assume_optional_discounts = bool(overrides.get("MASTER_OF_THE_PAGEANT", False))
                except Exception:
                    assume_optional_discounts = False

        if assume_optional_discounts:
            dts = self._preview_direct_the_slaughter_discount(target_unit=target_unit)
            if dts:
                discount += int(dts)
                reasons.append("Direct the Slaughter: -1CP (once per battle round)")

        gof = self._preview_gift_of_foresight_discount(stratagem=stratagem, target_unit=target_unit)
        if gof:
            discount += int(gof)
            reasons.append("Gift of Foresight: Command Re-roll for 0CP (once per battle round)")

        mop = self._preview_master_of_the_pageant_discount(stratagem=stratagem, target_unit=target_unit)
        if mop:
            discount += int(mop)
            reasons.append("Master of the Pageant: -1CP (once per battle round)")

        cost = max(0, base - discount)
        return {"base": base, "discount": discount, "cost": cost, "reasons": reasons}

    def apply_stratagem_cp_cost(self, stratagem, *, target_unit=None) -> dict:
        """
        Compute effective CP cost and CONSUME any once-per-battle-round discounts that are applied.
        """
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        # For application, we still compute "available" discounts (even if declined), but affordability uses applied discount.
        preview = self.preview_stratagem_cp_cost(stratagem, target_unit=target_unit, assume_optional_discounts=True)
        available_discount = int(preview.get("discount", 0) or 0)

        applied_discount = 0
        reasons: list[str] = []

        # Decide whether to apply Direct the Slaughter if available.
        dts_available = bool(self._preview_direct_the_slaughter_discount(target_unit=target_unit))
        if dts_available:
            ctx = {
                "ability_name": "Direct the Slaughter",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("DIRECT_THE_SLAUGHTER", ctx):
                applied_discount = 1
                reasons.append("Direct the Slaughter: -1CP (used)")
                br = self._battle_round()
                if br > 0:
                    self._ability_used_battle_round["DIRECT_THE_SLAUGHTER"] = br

        # Decide whether to apply Gift of Foresight if available.
        gof_available = bool(self._preview_gift_of_foresight_discount(stratagem=stratagem, target_unit=target_unit))
        if gof_available:
            ctx = {
                "ability_name": "Gift of Foresight",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            use_gof = True
            try:
                overrides = getattr(self, "_next_optional_decisions", {}) or {}
                has_override = isinstance(overrides, dict) and "GIFT_OF_FORESIGHT" in overrides
            except Exception:
                has_override = False
            if callable(getattr(self, "decision_hook", None)) or has_override:
                use_gof = self._should_use_optional_ability("GIFT_OF_FORESIGHT", ctx)
            if use_gof:
                applied_discount += 1
                reasons.append("Gift of Foresight: Command Re-roll for 0CP (used)")
                br = self._battle_round()
                if br > 0:
                    self._ability_used_battle_round["GIFT_OF_FORESIGHT"] = br
                try:
                    print(f"✨ Gift of Foresight: {self.name} uses Command Re-roll for 0CP.")
                except Exception:
                    pass

        # Decide whether to apply Master of the Pageant if available.
        mop_available = bool(self._preview_master_of_the_pageant_discount(stratagem=stratagem, target_unit=target_unit))
        if mop_available:
            ctx = {
                "ability_name": "Master of the Pageant",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            use_mop = True
            try:
                overrides = getattr(self, "_next_optional_decisions", {}) or {}
                has_override = isinstance(overrides, dict) and "MASTER_OF_THE_PAGEANT" in overrides
            except Exception:
                has_override = False
            if callable(getattr(self, "decision_hook", None)) or has_override:
                use_mop = self._should_use_optional_ability("MASTER_OF_THE_PAGEANT", ctx)
            if use_mop:
                applied_discount += 1
                reasons.append("Master of the Pageant: -1CP (used)")
                br = self._battle_round()
                try:
                    army = self.get_army()
                except Exception:
                    army = None
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is not None and br > 0:
                    try:
                        mgr.master_of_pageant_used_round = br
                    except Exception:
                        pass

        cost = max(0, base - applied_discount)
        return {
            "base": base,
            "discount": applied_discount,
            "available_discount": available_discount,
            "cost": cost,
            "reasons": reasons or list(preview.get("reasons", []) or []),
        }

    def compute_average_distance(self, objective: Objective) -> float:
        """Compute the average distance of the player's alive units to the objective."""
        distances = []
        for unit in self.get_army().units:
            if unit.is_alive() and unit.deployed:
                # Find the model closest to the objective
                obj_pos = (objective.location.x, objective.location.y, objective.location.z)
                closest_distance = float('inf')

                for model in unit.models:
                    if model.is_alive:
                        model_pos = model.get_location()
                        distance = get_dist(model_pos[0] - obj_pos[0],
                                          model_pos[1] - obj_pos[1],
                                          model_pos[2] - obj_pos[2])
                        if distance < closest_distance:
                            closest_distance = distance

                if closest_distance != float('inf'):
                    distances.append(closest_distance)
        return sum(distances) / len(distances) if distances else 0.0

    # ---------- Mission card helpers ----------

    def set_primary_mission(self, primary: PrimaryMissionCard) -> None:
        self.primary_mission = primary

    def set_secondary_deck(self, cards: list[SecondaryMissionCard] | None = None) -> None:
        # Use provided or default deck
        if cards is not None:
            self.secondary_deck = list(cards)
        else:
            self.secondary_deck = default_secondary_deck()
            # Shuffle for randomness if not already shuffled upstream
            try:
                import random
                random.shuffle(self.secondary_deck)
            except Exception:
                pass
        self.active_secondaries = []
        self.discarded_secondaries = []

    def ensure_secondary_deck_initialized(self) -> None:
        if not self.secondary_deck and not self.active_secondaries and not self.discarded_secondaries:
            self.set_secondary_deck()

    def can_draw_secondary(self) -> bool:
        return len(self.secondary_deck) > 0

    def draw_secondary_until_two(self, game) -> None:
        # Initialize deck if needed
        self.ensure_secondary_deck_initialized()
        # Draw until two active if deck allows
        while len(self.active_secondaries) < 2 and self.secondary_deck:
            card = self.secondary_deck.pop(0)
            try:
                if hasattr(card, 'can_be_drawn') and not card.can_be_drawn(game, self):
                    # Not eligible on draw. Some cards specify: redraw and shuffle this card back into deck.
                    if bool(getattr(card, "shuffle_back_on_ineligible_draw", False)):
                        try:
                            import random
                            # Shuffle back into the remaining deck at a random position.
                            idx = random.randint(0, len(self.secondary_deck))
                            self.secondary_deck.insert(idx, card)
                        except Exception:
                            # Fallback: append to the back of the deck
                            self.secondary_deck.append(card)
                        try:
                            print(f"🔄 {self.name} cannot draw Secondary: {card.name} (ineligible) → shuffled back into deck")
                        except Exception:
                            pass
                    else:
                        # Discard immediately and continue drawing
                        self.discarded_secondaries.append(card)
                        try:
                            print(f"🗑️ {self.name} cannot draw Secondary: {card.name} (ineligible) → discarded")
                        except Exception:
                            pass
                    continue
                # Allow cards to perform on-draw initialization
                if hasattr(card, 'on_draw'):
                    try:
                        card.on_draw(game, self)
                    except Exception:
                        pass
            except Exception:
                pass
            self.active_secondaries.append(card)
            try:
                print(f"🃏 {self.name} drew Secondary: {card.name}")
            except Exception:
                pass

    def discard_secondary(self, card: SecondaryMissionCard, gain_cp: bool = False) -> None:
        if card in self.active_secondaries:
            self.active_secondaries.remove(card)
            self.discarded_secondaries.append(card)
            if gain_cp:
                # Voluntary discard CP gain is subject to the core CP gain guardrail.
                self.gain_command_points(1, reason="Discard Secondary (gain 1CP)")

    def discard_achieved_secondaries(self, achieved_cards: list[SecondaryMissionCard]) -> None:
        for card in list(achieved_cards):
            if card in self.active_secondaries:
                self.active_secondaries.remove(card)
                self.discarded_secondaries.append(card)

    def __str__(self):
        return f"Name: {self.name}\nType: {self.type.name}\nCommand Points: {self.command_points}\nArmy: {self.army}"
