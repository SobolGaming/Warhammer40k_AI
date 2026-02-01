# This is the player that gets put onto a Battlefield and has an Army

import logging
import uuid
from typing import Any
from enum import Enum, auto
from .army import Army
from ..units.unit import Unit
from ..battlefield.map import Objective
from ..engine.mission_cards import PrimaryMissionCard, SecondaryMissionCard, default_secondary_deck
from ..utility.rng import resolve_rng
from warhammer40k_ai.utility.calcs import get_dist

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class PlayerControl(Enum):
    LOCAL = auto()
    REMOTE = auto()


class Player:
    def __init__(self, name: str, control: PlayerControl = PlayerControl.LOCAL, army: Army = None):
        self._id = str(uuid.uuid4())
        self.name = name
        if control not in (PlayerControl.LOCAL, PlayerControl.REMOTE):
            raise ValueError(f"Invalid player control: {control}")
        self.control = control
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
        # Generic per-turn ability usage (keyed by ability string).
        self._ability_used_turn: dict[str, tuple[int, int]] = {}
        # One-shot overrides that dialogs can set to drive immediate decisions without requiring
        # a persistent controller. Entries are consumed on first read.
        self._next_optional_decisions: dict[str, bool] = {}
        # One-shot selection overrides for optional ability choices.
        self._next_optional_selections: dict[str, object] = {}
        # Optional controller hook for reactive move placement (non-local control).
        self.reactive_move_position_hook = None
        #print(f"Player {self.name} created with army: {self.army}")

    @property
    def id(self) -> str:
        return self._id

    def has_control(self) -> bool:
        return self.control == PlayerControl.LOCAL
    
    def set_army(self, army: Army) -> None:
        self.army = army
        army.set_player(self)
        stratagems = getattr(self, "stratagems", None)
        if stratagems is not None:
            stratagems.refresh_available()
        game = getattr(self, "game", None)
        refresh_fn = getattr(game, "refresh_rule_subscribers", None) if game is not None else None
        if callable(refresh_fn):
            refresh_fn()

    def set_game(self, game) -> None:
        """Set the game reference for this player."""
        self.game = game
        # Lazily attach stratagem manager when a game is set
        from ..rules.stratagems import StratagemManager
        self.stratagems = StratagemManager(self)
        try:
            event_system = getattr(game, "event_system", None)
        except Exception:
            event_system = None
        if event_system is not None:
            self.stratagems.enable_event_subscriptions(event_system=event_system, group="rule:stratagems")

    def _sync_cp_gain_guardrail_battle_round(self) -> None:
        """Reset per-battle-round CP gain guardrail counter when battle round advances."""
        game = getattr(self, "game", None)
        br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        if br <= 0:
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
        amount = int(amount or 0)
        if amount <= 0:
            return 0

        # Keep battle-round counter fresh
        self._sync_cp_gain_guardrail_battle_round()

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
        amount = int(amount or 0)
        if amount <= 0:
            return False
        self._last_stratagem_spend_failed_due_to_increase = False
        reason_text = str(reason or "")
        reason_lower = reason_text.lower()
        is_stratagem_spend = str(source or "").strip().lower() == "stratagem" or "stratagem:" in reason_lower
        pending = getattr(self, "_pending_stratagem_cp_increase", None)
        pending_increase = 0
        pending_name = ""
        if isinstance(pending, dict):
            pending_increase = int(pending.get("increase", 0) or 0)
            pending_name = str(pending.get("stratagem_name", "") or "").strip()
        reason_name = ""
        if "stratagem:" in reason_lower:
            reason_name = reason_text.split(":", 1)[1].strip()
        if pending_name and reason_name and pending_name.lower() != reason_name.lower():
            pending_increase = 0
        if self.command_points >= amount:
            self.command_points -= amount
            self._record_cp_change(-amount, reason=reason or "Command Points spent", source=source or "spend")
            if str(source or "").strip().lower() == "stratagem" or "stratagem:" in str(reason or "").lower():
                from ..utility.event_bus import append_action
                strat_name = ""
                if "stratagem:" in str(reason or "").lower():
                    strat_name = str(reason).split(":", 1)[1].strip()
                if strat_name:
                    append_action(self, f"Stratagem used: {strat_name} ({amount} CP)")
                else:
                    append_action(self, f"Stratagem used ({amount} CP)")
            if is_stratagem_spend:
                self._pending_stratagem_cp_increase = None
            return True
        if is_stratagem_spend and pending_increase > 0:
            key = (reason_name or pending_name).strip().upper()
            if key:
                mgr = getattr(self, "stratagems", None)
                if mgr is not None:
                    try:
                        mgr._used_stratagems_this_phase.add(key)
                    except Exception:
                        raise
            self._last_stratagem_spend_failed_due_to_increase = True
        if is_stratagem_spend:
            self._pending_stratagem_cp_increase = None
        return False

    def _record_cp_change(self, delta: int, *, reason: str | None = None, source: str | None = None) -> None:
        delta = int(delta or 0)
        if delta == 0:
            return
        if not hasattr(self, "cp_history") or self.cp_history is None:
            self.cp_history = []

        game = getattr(self, "game", None)
        round_val = int(getattr(game, "get_battle_round", lambda: 0)() or 0) if game is not None else 0
        phase_label = None
        if game is not None and hasattr(game, "_current_phase_label"):
            phase_label = game._current_phase_label()
        if not phase_label:
            phase = getattr(game, "phase", None) if game is not None else None
            if hasattr(phase, "name"):
                phase_label = str(phase.name).replace("_", " ").title()
            elif phase is not None:
                phase_label = str(phase)
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
        self.cp_history.append(entry)

    # ---------------- Stratagem CP modifiers (e.g. Direct the Slaughter) ----------------

    def _battle_round(self) -> int:
        game = getattr(self, "game", None)
        return int(getattr(game, "turn", 0) or 0) if game is not None else 0

    def _turn_key(self) -> tuple[int, int]:
        game = getattr(self, "game", None)
        if game is None:
            return (0, -1)
        return (int(getattr(game, "turn", 0) or 0), int(getattr(game, "current_player_index", 0) or 0))

    def _mark_ability_used_turn(self, key: str) -> None:
        k = str(key or "").strip().upper()
        if not k:
            return
        self._ability_used_turn[k] = self._turn_key()

    def _ability_used_this_turn(self, key: str) -> bool:
        k = str(key or "").strip().upper()
        if not k:
            return False
        return self._ability_used_turn.get(k) == self._turn_key()

    def _get_opponent_player(self):
        game = getattr(self, "game", None)
        if game is None:
            return None
        for p in list(getattr(game, "players", []) or []):
            if p is not self:
                return p
        return None

    def _model_has_ability_name(self, model, ability_name: str) -> bool:
        if model is None:
            return False
        key = str(ability_name or "").strip().lower()
        if not key:
            return False
        abilities = getattr(model, "abilities", {}) or {}
        for nm in list(abilities.keys()):
            if str(nm or "").strip().lower() == key:
                return True
        return False

    def _source_model_within_range_for_ability(self, source_unit, target_unit, rng: float, ability_name: str) -> bool:
        from warhammer40k_ai.utility.aura_utils import unit_within_range_of_unit

        models = list(source_unit.get_attached_unit_models() or [])
        has_named_model = False
        for m in models:
            if not getattr(m, "is_alive", True):
                continue
            if ability_name and self._model_has_ability_name(m, ability_name):
                has_named_model = True
                if source_unit._model_within_range_of_unit(m, target_unit, rng):
                    return True
        if has_named_model:
            return False
        return bool(unit_within_range_of_unit(source_unit, target_unit, rng, use_attached_aggregate=True))

    def _unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        fn = getattr(unit, "has_any_keyword", None)
        if callable(fn):
            return bool(fn(keyword))
        kw = str(keyword or "").strip().upper()
        if not kw:
            return False
        keywords = [
            str(k).strip().upper()
            for k in (getattr(unit, "keywords", []) or [])
            if str(k).strip()
        ]
        faction_keywords = [
            str(k).strip().upper()
            for k in (getattr(unit, "faction_keywords", []) or [])
            if str(k).strip()
        ]
        return kw in set(keywords + faction_keywords)

    def _attached_members(self, unit) -> list:
        if unit is None:
            return []
        fn = getattr(unit, "get_attached_unit_members", None)
        if callable(fn):
            members = list(fn() or [])
            return members if members else [unit]
        return [unit]

    def _should_preview_optional_ability(self, key: str, context: dict, *, assume: bool | None) -> bool:
        if assume is True:
            return True
        if assume is False:
            return False
        k = (key or "").strip().upper()
        if not k:
            return False
        overrides = getattr(self, "_next_optional_decisions", None)
        if isinstance(overrides, dict) and k in overrides:
            return bool(overrides.get(k))
        hook = getattr(self, "decision_hook", None)
        if callable(hook):
            return bool(hook(self, k, context))
        return False

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
        army = self.get_army()
        if army is None:
            return 0
        we_mgr = getattr(army, "world_eaters_detachments", None)
        if we_mgr is None or not we_mgr.is_berzerker_warband():
            return 0
        if not self._unit_has_keyword(target_unit, "WORLD EATERS"):
            return 0

        br = self._battle_round()
        if br <= 0:
            return 0
        if int(self._ability_used_battle_round.get("DIRECT_THE_SLAUGHTER", 0) or 0) == br:
            return 0

        game = getattr(self, "game", None)
        if game is None or getattr(game, "map", None) is None:
            return 0

        from warhammer40k_ai.utility.aura_utils import unit_within_range_of_unit

        for u in list(getattr(army, "units", []) or []):
            if not u.is_alive():
                continue
            has_ability = False
            for ab in (getattr(u, "possible_abilities", []) or []):
                nm = str(getattr(ab, "name", "") or "").strip().lower()
                if nm == "direct the slaughter":
                    has_ability = True
                    break
            if not has_ability:
                continue
            if unit_within_range_of_unit(u, target_unit, 12.0, use_attached_aggregate=True):
                return 1
        return 0

    def _target_unit_has_stratagem_target_cp_discount(self, target_unit) -> tuple[bool, list[str]]:
        if target_unit is None:
            return False, []
        try:
            parent = None
            getter = getattr(target_unit, "get_parent_army", None)
            if callable(getter):
                parent = getter()
            else:
                parent = getattr(target_unit, "parent_army", None)
                if parent is None:
                    parent = getattr(target_unit, "army", None)
            if parent is not None and parent is not self.get_army():
                return False, []
        except Exception:
            pass
        members = self._attached_members(target_unit)
        found = False
        names: list[str] = []
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if not sr.get("stratagem_target_cp_discount"):
                continue
            found = True
            for nm in list(sr.get("stratagem_target_cp_discount_sources", []) or []):
                if nm:
                    names.append(str(nm))
        if found and not names:
            names.append("Stratagem CP Discount")
        # Deduplicate while preserving order.
        seen = set()
        deduped: list[str] = []
        for n in names:
            key = str(n).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(str(n))
        return bool(found), deduped

    def _target_unit_has_stratagem_target_cp_discount_aura(self, target_unit) -> tuple[bool, list[str]]:
        if target_unit is None:
            return False, []
        try:
            parent = None
            getter = getattr(target_unit, "get_parent_army", None)
            if callable(getter):
                parent = getter()
            else:
                parent = getattr(target_unit, "parent_army", None)
                if parent is None:
                    parent = getattr(target_unit, "army", None)
            if parent is not None and parent is not self.get_army():
                return False, []
        except Exception:
            pass
        army = self.get_army()
        if army is None:
            return False, []

        names: list[str] = []
        for u in list(getattr(army, "units", []) or []):
            if not u.is_alive():
                continue
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            specs = list(sr.get("stratagem_target_cp_discount_aura", []) or [])
            if not specs:
                continue
            for spec in specs:
                if not isinstance(spec, dict):
                    continue
                rng = float(spec.get("range", 0) or 0)
                if rng <= 0:
                    continue
                kw = str(spec.get("keyword", "") or "").strip()
                if kw and not self._unit_has_keyword(target_unit, kw):
                    continue
                name = str(spec.get("name", "") or "Stratagem CP Discount").strip()
                if self._source_model_within_range_for_ability(u, target_unit, rng, name):
                    names.append(name or "Stratagem CP Discount")

        if not names:
            return False, []
        # Deduplicate while preserving order.
        seen = set()
        deduped: list[str] = []
        for n in names:
            key = str(n).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(str(n))
        return True, deduped

    def _preview_targeted_stratagem_cp_discount(self, *, target_unit=None) -> tuple[int, list[str]]:
        """
        Generic targeted stratagem CP discount:
        Once per battle round, one unit from your army with this ability can use it when its unit
        is targeted with a Stratagem. If it does, reduce the CP cost by 1CP.
        """
        if target_unit is None:
            return 0, []
        br = self._battle_round()
        if br <= 0:
            return 0, []
        if int(self._ability_used_battle_round.get("TARGETED_STRATAGEM_DISCOUNT", 0) or 0) == br:
            return 0, []
        found, names = self._target_unit_has_stratagem_target_cp_discount(target_unit)
        aura_found, aura_names = self._target_unit_has_stratagem_target_cp_discount_aura(target_unit)
        if not found and not aura_found:
            return 0, []
        combined = list(names or [])
        combined.extend(aura_names or [])
        # Deduplicate while preserving order.
        seen = set()
        deduped: list[str] = []
        for n in combined:
            key = str(n).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(str(n))
        return 1, deduped

    def _target_unit_has_stratagem_target_cp_increase_sources(self, target_unit, *, current_cost: int | None = None) -> tuple[list[dict], list[dict]]:
        if target_unit is None:
            return [], []
        try:
            parent = None
            getter = getattr(target_unit, "get_parent_army", None)
            if callable(getter):
                parent = getter()
            else:
                parent = getattr(target_unit, "parent_army", None)
                if parent is None:
                    parent = getattr(target_unit, "army", None)
            if parent is not None and parent is self.get_army():
                return [], []
        except Exception:
            pass
        army = self.get_army()
        if army is None:
            return [], []

        auto_specs: list[dict] = []
        optional_specs: list[dict] = []
        for u in list(getattr(army, "units", []) or []):
            if not u.is_alive():
                continue
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            specs = list(sr.get("stratagem_target_cp_increase_aura", []) or [])
            if not specs:
                continue
            for spec in specs:
                if not isinstance(spec, dict):
                    continue
                rng = float(spec.get("range", 0) or 0)
                if rng <= 0:
                    continue
                kw = str(spec.get("keyword", "") or "").strip()
                if kw and not self._unit_has_keyword(target_unit, kw):
                    continue
                name = str(spec.get("name", "") or "Stratagem CP Increase").strip()
                if not self._source_model_within_range_for_ability(u, target_unit, rng, name):
                    continue
                limit = str(spec.get("limit", "") or "").strip().lower()
                usage_key = str(spec.get("usage_key", "") or "").strip().upper()
                if limit == "battle_round":
                    br = self._battle_round()
                    if br > 0 and int(self._ability_used_battle_round.get(usage_key, 0) or 0) == br:
                        continue
                elif limit == "turn":
                    if usage_key and self._ability_used_this_turn(usage_key):
                        continue
                max_cp = spec.get("max_cp", None)
                if current_cost is not None and max_cp is not None:
                    try:
                        if int(current_cost) >= int(max_cp):
                            continue
                    except Exception:
                        pass
                if bool(spec.get("optional", False)):
                    optional_specs.append(spec)
                else:
                    auto_specs.append(spec)

        def _dedupe(specs: list[dict]) -> list[dict]:
            seen = set()
            out: list[dict] = []
            for spec in specs:
                key = str(spec.get("usage_key", "") or spec.get("name", "") or "").strip().lower()
                if not key:
                    key = f"{spec.get('range', 0)}:{spec.get('name', '')}".strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(spec)
            return out

        return _dedupe(auto_specs), _dedupe(optional_specs)

    def preview_targeted_stratagem_cp_increase(self, *, target_unit=None, current_cost: int | None = None) -> dict:
        auto_specs, optional_specs = self._target_unit_has_stratagem_target_cp_increase_sources(
            target_unit, current_cost=current_cost
        )
        auto_names = [str(s.get("name", "Stratagem CP Increase")) for s in auto_specs]
        optional_names = [str(s.get("name", "Stratagem CP Increase")) for s in optional_specs]
        return {
            "auto": bool(auto_specs),
            "optional": bool(optional_specs),
            "auto_names": auto_names,
            "optional_names": optional_names,
            "auto_specs": auto_specs,
            "optional_specs": optional_specs,
        }

    def apply_targeted_stratagem_cp_increase(self, *, target_unit=None, stratagem=None, current_cost: int | None = None) -> dict:
        auto_specs, optional_specs = self._target_unit_has_stratagem_target_cp_increase_sources(
            target_unit, current_cost=current_cost
        )
        increase = 0
        reasons: list[str] = []
        used_spec = None
        if auto_specs:
            used_spec = auto_specs[0]
            increase = 1
        elif optional_specs:
            used_spec = optional_specs[0]
            ctx = {
                "ability_name": str(used_spec.get("name", "") or "Stratagem CP Increase"),
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "current_cp_cost": int(current_cost or 0),
            }
            if self._should_use_optional_ability("OPPONENT_STRATAGEM_CP_INCREASE", ctx):
                increase = 1

        if increase and used_spec:
            label = str(used_spec.get("name", "") or "Stratagem CP Increase").strip() or "Stratagem CP Increase"
            reasons.append(f"{label}: +1CP")
            limit = str(used_spec.get("limit", "") or "").strip().lower()
            usage_key = str(used_spec.get("usage_key", "") or label).strip().upper()
            if limit == "battle_round":
                br = self._battle_round()
                if br > 0:
                    self._ability_used_battle_round[usage_key] = br
            elif limit == "turn":
                self._mark_ability_used_turn(usage_key)

        return {
            "increase": int(increase or 0),
            "reasons": reasons,
            "spec": used_spec,
        }

    def _target_unit_has_gift_of_foresight(self, target_unit) -> bool:
        if target_unit is None:
            return False
        members = self._attached_members(target_unit)
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                raise TypeError("special_rules must be a dict for Gift of Foresight.")
            if not sr.get("enhancement_free_command_reroll_once_per_battle_round", False):
                continue
            if not u.is_alive():
                continue
            return True
        return False

    def _target_unit_has_faultless_opportunist(self, target_unit) -> bool:
        if target_unit is None:
            return False
        members = self._attached_members(target_unit)
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not sr.get("enhancement_faultless_opportunist", False):
                continue
            try:
                if callable(getattr(u, "is_alive", None)) and not u.is_alive():
                    continue
            except Exception:
                continue
            return True
        return False

    def _preview_faultless_opportunist_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().lower()
        if name != "heroic intervention":
            return 0
        if not self._target_unit_has_faultless_opportunist(target_unit):
            return 0
        try:
            base = int(getattr(stratagem, "cp_cost", 0) or 0)
        except Exception:
            base = 0
        return max(0, base)

    def _preview_gift_of_foresight_discount(self, *, stratagem=None, target_unit=None) -> int:
        """
        Gift of Foresight (Warhost):
        Once per battle round, you can target the bearer's unit with Command Re-roll for 0CP.
        """
        if stratagem is None or target_unit is None:
            return 0
        army = self.get_army()
        mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
        if mgr is None or not mgr.is_warhost_detachment():
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().lower()
        if name not in ("command re-roll", "command reroll"):
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
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u not in ("SINUOUS BREACH", "PRIDEFUL SUPERIORITY"):
            return 0
        if not self._unit_has_keyword(target_unit, "FULGRIM"):
            return 0
        army = self.get_army()
        mgr = getattr(army, "emperors_children", None) if army is not None else None
        if mgr is None or not mgr.is_court_of_the_phoenician():
            return 0
        if not mgr.is_emperors_children_unit(target_unit):
            return 0
        br = self._battle_round()
        if br <= 0:
            return 0
        if int(getattr(mgr, "master_of_pageant_used_round", 0) or 0) == br:
            return 0
        return 1

    def _should_use_optional_ability(self, key: str, context: dict) -> bool:
        """
        Check for one-shot override decisions for optional abilities.
        Conservative default: False (do not auto-spend limited resources).
        """
        k = (key or "").strip().upper()
        if not k:
            return False
        overrides = getattr(self, "_next_optional_decisions", None)
        if isinstance(overrides, dict) and k in overrides:
            return bool(overrides.pop(k))
        hook = getattr(self, "decision_hook", None)
        if callable(hook):
            return bool(hook(self, k, context))
        return False

    def _choose_optional_value(self, key: str, options: list, context: dict):
        """
        Check for one-shot selection overrides from a list of options.
        Conservative default: None (no automatic selection).
        """
        k = (key or "").strip().upper()
        if not k:
            return None
        overrides = getattr(self, "_next_optional_selections", None)
        if isinstance(overrides, dict) and k in overrides:
            return overrides.pop(k)
        return None

    def choose_reactive_move_positions(self, context: dict):
        """
        Optional controller hook for reactive move placements.
        Expected to return a list of model position dicts or None to leave pending.
        """
        hook = getattr(self, "reactive_move_position_hook", None)
        if callable(hook):
            return hook(self, dict(context or {}))
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
        - If None, include optional discounts only if a decision hook exists (meaning a controller can decide).
        """
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        discount = 0
        reasons: list[str] = []

        faultless = self._preview_faultless_opportunist_discount(stratagem=stratagem, target_unit=target_unit)
        if faultless:
            discount = base
            reasons.append("Faultless Opportunist: Heroic Intervention for 0CP.")
            return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        dts = self._preview_direct_the_slaughter_discount(target_unit=target_unit)
        if dts:
            ctx = {
                "ability_name": "Direct the Slaughter",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability("DIRECT_THE_SLAUGHTER", ctx, assume=assume_optional_discounts):
                discount += int(dts)
                reasons.append("Direct the Slaughter: -1CP (once per battle round)")

        tsd, tsd_names = self._preview_targeted_stratagem_cp_discount(target_unit=target_unit)
        if tsd:
            label = tsd_names[0] if tsd_names else "Stratagem CP Discount"
            ctx = {
                "ability_name": label,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability("TARGETED_STRATAGEM_DISCOUNT", ctx, assume=assume_optional_discounts):
                discount += int(tsd)
                reasons.append(f"Targeted Stratagem Discount ({label}): -1CP (once per battle round)")

        gof = self._preview_gift_of_foresight_discount(stratagem=stratagem, target_unit=target_unit)
        if gof:
            discount += int(gof)
            print(f"Gift of Foresight: {self.name} uses Command Re-roll for 0CP.")

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
        faultless = self._preview_faultless_opportunist_discount(stratagem=stratagem, target_unit=target_unit)
        if faultless:
            cost = 0
            increase = 0
            increase_reasons: list[str] = []
            opponent = self._get_opponent_player()
            if opponent is not None:
                inc_info = opponent.apply_targeted_stratagem_cp_increase(
                    target_unit=target_unit,
                    stratagem=stratagem,
                    current_cost=cost,
                )
                increase = int(inc_info.get("increase", 0) or 0)
                increase_reasons = list(inc_info.get("reasons", []) or [])
                if increase:
                    cost = max(0, cost + increase)
            self._pending_stratagem_cp_increase = {
                "increase": int(increase or 0),
                "reasons": increase_reasons,
                "stratagem_name": getattr(stratagem, "name", None) or "",
            }
            return {
                "base": base,
                "discount": base,
                "cost": cost,
                "reasons": ["Faultless Opportunist: Heroic Intervention for 0CP."],
                "increase": increase,
                "increase_reasons": increase_reasons,
            }
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

        # Decide whether to apply targeted stratagem discount if available.
        tsd_available, tsd_names = self._preview_targeted_stratagem_cp_discount(target_unit=target_unit)
        if tsd_available:
            label = tsd_names[0] if tsd_names else "Stratagem CP Discount"
            ctx = {
                "ability_name": label,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("TARGETED_STRATAGEM_DISCOUNT", ctx):
                applied_discount += 1
                reasons.append(f"Targeted Stratagem Discount ({label}): -1CP (used)")
                br = self._battle_round()
                if br > 0:
                    self._ability_used_battle_round["TARGETED_STRATAGEM_DISCOUNT"] = br

        # Decide whether to apply Gift of Foresight if available.
        gof_available = bool(self._preview_gift_of_foresight_discount(stratagem=stratagem, target_unit=target_unit))
        if gof_available:
            ctx = {
                "ability_name": "Gift of Foresight",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            use_gof = self._should_use_optional_ability("GIFT_OF_FORESIGHT", ctx)
            if use_gof or getattr(self, "decision_hook", None) is None:
                applied_discount += 1
                br = self._battle_round()
                if br > 0:
                    self._ability_used_battle_round["GIFT_OF_FORESIGHT"] = br
                print(f"Gift of Foresight: {self.name} uses Command Re-roll for 0CP.")

        # Decide whether to apply Master of the Pageant if available.
        mop_available = bool(self._preview_master_of_the_pageant_discount(stratagem=stratagem, target_unit=target_unit))
        if mop_available:
            ctx = {
                "ability_name": "Master of the Pageant",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            use_mop = self._should_use_optional_ability("MASTER_OF_THE_PAGEANT", ctx)
            if use_mop:
                applied_discount += 1
                reasons.append("Master of the Pageant: -1CP (used)")
                br = self._battle_round()
                army = self.get_army()
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is not None and br > 0:
                    mgr.master_of_pageant_used_round = br

        cost = max(0, base - applied_discount)
        increase = 0
        increase_reasons: list[str] = []
        opponent = self._get_opponent_player()
        if opponent is not None:
            inc_info = opponent.apply_targeted_stratagem_cp_increase(
                target_unit=target_unit,
                stratagem=stratagem,
                current_cost=cost,
            )
            increase = int(inc_info.get("increase", 0) or 0)
            increase_reasons = list(inc_info.get("reasons", []) or [])
            if increase:
                cost = max(0, cost + increase)
        self._pending_stratagem_cp_increase = {
            "increase": int(increase or 0),
            "reasons": increase_reasons,
            "stratagem_name": getattr(stratagem, "name", None) or "",
        }
        return {
            "base": base,
            "discount": applied_discount,
            "available_discount": available_discount,
            "cost": cost,
            "increase": increase,
            "increase_reasons": increase_reasons,
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

    def set_secondary_deck(self, cards: list[SecondaryMissionCard] | None = None, *, game=None) -> None:
        # Use provided or default deck
        if cards is not None:
            self.secondary_deck = list(cards)
        else:
            rng = resolve_rng(game)
            self.secondary_deck = default_secondary_deck(rng=rng)
        self.active_secondaries = []
        self.discarded_secondaries = []

    def ensure_secondary_deck_initialized(self, game=None) -> None:
        if not self.secondary_deck and not self.active_secondaries and not self.discarded_secondaries:
            self.set_secondary_deck(game=game)

    def can_draw_secondary(self) -> bool:
        return len(self.secondary_deck) > 0

    def draw_secondary_until_two(self, game) -> None:
        # Initialize deck if needed
        self.ensure_secondary_deck_initialized(game)
        # Draw until two active if deck allows
        while len(self.active_secondaries) < 2 and self.secondary_deck:
            card = self.secondary_deck.pop(0)
            if hasattr(card, 'can_be_drawn') and not card.can_be_drawn(game, self):
                # Not eligible on draw. Some cards specify: redraw and shuffle this card back into deck.
                if bool(getattr(card, "shuffle_back_on_ineligible_draw", False)):
                    rng = resolve_rng(game)
                    # Shuffle back into the remaining deck at a random position.
                    idx = int(rng.randint(0, len(self.secondary_deck)))
                    self.secondary_deck.insert(idx, card)
                    print(
                        f"INFO: {self.name} cannot draw Secondary: {card.name} (ineligible); shuffled back into deck"
                    )
                else:
                    # Discard immediately and continue drawing
                    self.discarded_secondaries.append(card)
                    print(
                        f"INFO: {self.name} cannot draw Secondary: {card.name} (ineligible); discarded"
                    )
                continue
            # Allow cards to perform on-draw initialization
            if hasattr(card, 'on_draw'):
                card.on_draw(game, self)
            self.active_secondaries.append(card)
            print(f"INFO: {self.name} drew Secondary: {card.name}")

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
        return f"Name: {self.name}\nControl: {self.control.name}\nCommand Points: {self.command_points}\nArmy: {self.army}"
