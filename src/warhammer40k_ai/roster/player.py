# This is the player that gets put onto a Battlefield and has an Army

import logging
import uuid
from typing import Any, Sequence
from enum import Enum, auto
from .army import Army
from ..units.unit import Unit
from ..battlefield.map import Objective
from ..engine.mission_cards import PrimaryMissionCard, SecondaryMissionCard, default_secondary_deck
from ..utility.rng import resolve_rng
from warhammer40k_ai.utility.calcs import get_dist
from ..utility.entity_ids import get_entity_id

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


DEFAULT_PLAYER_UI_COLOR_PALETTE: tuple[tuple[int, int, int], ...] = (
    (57, 255, 20),   # Existing neon green default
    (255, 72, 72),   # Red
    (72, 170, 255),  # Blue
    (255, 200, 60),  # Gold
    (190, 120, 255), # Purple
    (70, 220, 210),  # Teal
)


def _normalize_rgb_triplet(rgb: Sequence[int]) -> list[int]:
    values = list(rgb or [])
    if len(values) != 3:
        raise ValueError("Player UI color must contain exactly 3 RGB components.")
    normalized: list[int] = []
    for idx, value in enumerate(values):
        ivalue = int(value)
        if ivalue < 0 or ivalue > 255:
            raise ValueError(f"RGB component index {idx} out of range: {ivalue}")
        normalized.append(ivalue)
    return normalized


def _normalize_hue_degrees(hue_degrees: int | None) -> int | None:
    if hue_degrees is None:
        return None
    value = int(hue_degrees)
    if value < 0 or value >= 360:
        raise ValueError(f"Hue degrees must be within [0, 359], got {value}")
    return value


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
        # Generic per-phase ability usage (keyed by ability string).
        self._ability_used_phase: dict[str, tuple[int, str, int]] = {}
        # One-shot overrides that dialogs can set to drive immediate decisions without requiring
        # a persistent controller. Entries are consumed on first read.
        self._next_optional_decisions: dict[str, bool] = {}
        # One-shot selection overrides for optional ability choices.
        self._next_optional_selections: dict[str, object] = {}
        # Optional controller hook for reactive move placement (non-local control).
        self.reactive_move_position_hook = None
        # Stratagem-spend context (set by apply_stratagem_cp_cost, consumed by spend_command_points).
        self._pending_stratagem_target_unit_id: str = ""
        self._pending_stratagem_name: str = ""
        # Player UI color (serializable, deterministic default assigned by Game).
        self.ui_color_rgb: list[int] = [0, 0, 0]
        self.ui_color_hue_degrees: int | None = None
        self.ui_color_selected: bool = False
        self.ui_color_source: str = "default"
        #print(f"Player {self.name} created with army: {self.army}")

    @property
    def id(self) -> str:
        return self._id

    def has_control(self) -> bool:
        return self.control == PlayerControl.LOCAL

    def set_ui_color(
        self,
        rgb: Sequence[int],
        *,
        hue_degrees: int | None = None,
        selected: bool = True,
        source: str = "custom",
    ) -> None:
        self.ui_color_rgb = _normalize_rgb_triplet(rgb)
        self.ui_color_hue_degrees = _normalize_hue_degrees(hue_degrees)
        self.ui_color_selected = bool(selected)
        self.ui_color_source = str(source or "custom")

    def assign_default_ui_color(self, slot_index: int) -> None:
        idx = int(slot_index or 0)
        palette = DEFAULT_PLAYER_UI_COLOR_PALETTE
        color = palette[idx % len(palette)]
        self.set_ui_color(color, hue_degrees=None, selected=False, source="default")

    def get_ui_color_rgb(self) -> tuple[int, int, int]:
        rgb = _normalize_rgb_triplet(self.ui_color_rgb)
        self.ui_color_rgb = list(rgb)
        return (rgb[0], rgb[1], rgb[2])
    
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
        event_system = getattr(game, "event_system", None)
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
        if amount < 0:
            return False
        self._last_stratagem_spend_failed_due_to_increase = False
        reason_text = str(reason or "")
        reason_lower = reason_text.lower()
        is_stratagem_spend = str(source or "").strip().lower() == "stratagem" or "stratagem:" in reason_lower
        pending_target_unit_id = str(getattr(self, "_pending_stratagem_target_unit_id", "") or "")
        pending_stratagem_name = str(getattr(self, "_pending_stratagem_name", "") or "")
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
        if amount == 0:
            if is_stratagem_spend:
                self._maybe_apply_targeted_stratagem_cp_refund(
                    target_unit_id=pending_target_unit_id,
                    stratagem_name=(pending_stratagem_name or reason_name),
                )
            if is_stratagem_spend:
                self._pending_stratagem_cp_increase = None
                self._pending_stratagem_target_unit_id = ""
                self._pending_stratagem_name = ""
            return True
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
                self._maybe_apply_targeted_stratagem_cp_refund(
                    target_unit_id=pending_target_unit_id,
                    stratagem_name=(pending_stratagem_name or reason_name),
                )
            if is_stratagem_spend:
                self._pending_stratagem_cp_increase = None
                self._pending_stratagem_target_unit_id = ""
                self._pending_stratagem_name = ""
            return True
        if is_stratagem_spend and pending_increase > 0:
            key = (reason_name or pending_name).strip().upper()
            if key:
                mgr = getattr(self, "stratagems", None)
                if mgr is not None:
                    mgr._used_stratagems_this_phase.add(key)
            self._last_stratagem_spend_failed_due_to_increase = True
        if is_stratagem_spend:
            self._pending_stratagem_cp_increase = None
            self._pending_stratagem_target_unit_id = ""
            self._pending_stratagem_name = ""
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

    def _phase_key(self) -> tuple[int, str, int]:
        game = getattr(self, "game", None)
        if game is None:
            return (0, "", -1)
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn = 0
        phase_obj = getattr(game, "phase", None)
        phase_name = str(getattr(phase_obj, "name", "") or phase_obj or "").strip().upper()
        try:
            player_idx = int(getattr(game, "current_player_index", -1) or -1)
        except Exception:
            player_idx = -1
        return (turn, phase_name, player_idx)

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

    def _mark_ability_used_phase(self, key: str) -> None:
        k = str(key or "").strip().upper()
        if not k:
            return
        self._ability_used_phase[k] = self._phase_key()

    def _ability_used_this_phase(self, key: str) -> bool:
        k = str(key or "").strip().upper()
        if not k:
            return False
        return self._ability_used_phase.get(k) == self._phase_key()

    def _resolve_owned_unit_root_by_id(self, unit_id: str):
        key = str(unit_id or "").strip()
        if not key:
            return None
        army = self.get_army()
        if army is None:
            return None
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            rid = str(get_entity_id(root) or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            if rid == key:
                return root
        return None

    def _target_unit_stratagem_cp_refund_specs(self, target_unit) -> list[dict]:
        if target_unit is None:
            return []
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return []
        members = self._attached_members(target_unit)
        specs: list[dict] = []
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            for spec in list(sr.get("stratagem_target_cp_refund_specs", []) or []):
                if not isinstance(spec, dict):
                    continue
                source_model_id = str(spec.get("source_model_id", "") or "").strip()
                if source_model_id and not self._unit_has_alive_model_id(target_unit, source_model_id):
                    continue
                specs.append(spec)

        if not specs:
            has_rule = getattr(target_unit, "has_multiwave_comms_array", None)
            if callable(has_rule) and bool(has_rule()):
                specs.append(
                    {
                        "roll_min": 5,
                        "cp_gain": 1,
                        "name": "Multiwave Comms Array",
                        "description": "",
                    }
                )

        seen = set()
        deduped: list[dict] = []
        for spec in specs:
            try:
                bonus_roll = int(spec.get("roll_bonus", 0) or 0)
            except (TypeError, ValueError):
                bonus_roll = 0
            bonus_keyword = str(spec.get("roll_bonus_keyword", "") or "").strip().upper()
            try:
                bonus_range = int(spec.get("roll_bonus_range", 0) or 0)
            except (TypeError, ValueError):
                bonus_range = 0
            key = (
                int(spec.get("roll_min", 0) or 0),
                int(spec.get("cp_gain", 0) or 0),
                str(spec.get("name", "") or "").strip().lower(),
                int(bonus_roll),
                str(bonus_keyword),
                int(bonus_range),
                str(spec.get("roll_bonus_if_target_has_keyword", "") or "").strip().upper(),
                bool(spec.get("roll_bonus_if_source_model_within_vowed_objective", False)),
                str(spec.get("source_model_id", "") or "").strip(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(spec)
        deduped.sort(
            key=lambda item: (
                str(item.get("name", "") or "").strip().lower(),
                int(item.get("roll_min", 0) or 0),
                int(item.get("cp_gain", 0) or 0),
                int(item.get("roll_bonus", 0) or 0),
                str(item.get("roll_bonus_keyword", "") or "").strip().upper(),
                int(item.get("roll_bonus_range", 0) or 0),
                str(item.get("roll_bonus_if_target_has_keyword", "") or "").strip().upper(),
                int(bool(item.get("roll_bonus_if_source_model_within_vowed_objective", False))),
                str(item.get("source_model_id", "") or "").strip(),
            )
        )
        return deduped

    def _friendly_keyword_within_range_of_unit(self, *, target_unit, keyword: str, rng: float) -> bool:
        if target_unit is None:
            return False
        kw = str(keyword or "").strip().upper()
        if not kw:
            return False
        try:
            range_val = float(rng or 0.0)
        except (TypeError, ValueError):
            range_val = 0.0
        if range_val <= 0.0:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        army = self.get_army()
        if army is None:
            return False
        for source_unit in list(getattr(army, "units", []) or []):
            if not self._unit_is_alive_or_unknown(source_unit):
                continue
            if not self._unit_has_keyword(source_unit, kw):
                continue
            if self._source_model_within_range_for_ability(source_unit, target_unit, range_val, ""):
                return True
        return False

    def _maybe_apply_targeted_stratagem_cp_refund(self, *, target_unit_id: str, stratagem_name: str = "") -> None:
        root = self._resolve_owned_unit_root_by_id(target_unit_id)
        if root is None:
            return
        specs = self._target_unit_stratagem_cp_refund_specs(root)
        if not specs:
            return
        game = getattr(self, "game", None)
        event_system = getattr(game, "event_system", None) if game is not None else None

        for spec in specs:
            try:
                from ..utility.dice import get_roll

                roll = int(get_roll("D6") or 0)
            except Exception:
                roll = 0
            label = str(spec.get("name", "") or "Stratagem CP Refund").strip() or "Stratagem CP Refund"
            try:
                roll_min = int(spec.get("roll_min", 5) or 5)
            except Exception:
                roll_min = 5
            try:
                cp_gain = int(spec.get("cp_gain", 1) or 1)
            except Exception:
                cp_gain = 1
            try:
                roll_bonus_value = int(spec.get("roll_bonus", 0) or 0)
            except (TypeError, ValueError):
                roll_bonus_value = 0
            roll_bonus_keyword = str(spec.get("roll_bonus_keyword", "") or "").strip().upper()
            roll_bonus_target_keyword = str(spec.get("roll_bonus_if_target_has_keyword", "") or "").strip().upper()
            try:
                roll_bonus_range = float(spec.get("roll_bonus_range", 0) or 0)
            except (TypeError, ValueError):
                roll_bonus_range = 0.0
            roll_bonus_if_source_model_within_vowed_objective = bool(
                spec.get("roll_bonus_if_source_model_within_vowed_objective", False)
            )
            roll_bonus = 0
            if roll_bonus_value > 0 and roll_bonus_keyword and roll_bonus_range > 0:
                if self._friendly_keyword_within_range_of_unit(
                    target_unit=root,
                    keyword=roll_bonus_keyword,
                    rng=roll_bonus_range,
                ):
                    roll_bonus = max(int(roll_bonus), int(roll_bonus_value))
            if roll_bonus_value > 0 and roll_bonus_target_keyword:
                if self._unit_has_keyword(root, roll_bonus_target_keyword):
                    roll_bonus = max(int(roll_bonus), int(roll_bonus_value))
            if roll_bonus_value > 0 and roll_bonus_if_source_model_within_vowed_objective:
                source_model_id = str(spec.get("source_model_id", "") or "").strip()
                army = self.get_army()
                sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
                within_vowed_fn = (
                    getattr(sm_mgr, "inner_circle_source_model_within_vowed_objective", None)
                    if sm_mgr is not None
                    else None
                )
                if callable(within_vowed_fn):
                    if bool(within_vowed_fn(root, source_model_id=source_model_id, game=game)):
                        roll_bonus = max(int(roll_bonus), int(roll_bonus_value))
            effective_roll = int(roll + roll_bonus)
            gained = 0
            if effective_roll >= roll_min and cp_gain > 0:
                gained = int(self.gain_command_points(cp_gain, reason=label) or 0)
            try:
                from ..utility.event_bus import append_dice, append_action

                if roll_bonus > 0:
                    append_dice(self, f"{label} roll: {int(roll)} (+{int(roll_bonus)}) = {int(effective_roll)}")
                else:
                    append_dice(self, f"{label} roll: {int(roll)}")
                if gained > 0:
                    append_action(self, f"{label}: gained {int(gained)} CP.")
                else:
                    append_action(self, f"{label}: no CP gained.")
            except Exception:
                pass
            if event_system is not None:
                try:
                    event_system.publish(
                        "command_points_gained",
                        player=self,
                        amount=int(gained or 0),
                        reason=label,
                        target_unit=root,
                        roll=int(roll),
                        roll_bonus=int(roll_bonus),
                        effective_roll=int(effective_roll),
                        stratagem_name=str(stratagem_name or ""),
                    )
                except Exception:
                    pass
            if gained > 0:
                break

    def _maybe_apply_multiwave_comms_array_cp_refund(self, *, target_unit_id: str, stratagem_name: str = "") -> None:
        self._maybe_apply_targeted_stratagem_cp_refund(
            target_unit_id=target_unit_id,
            stratagem_name=stratagem_name,
        )

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

    def _source_model_within_range_for_ability(
        self,
        source_unit,
        target_unit,
        rng: float,
        ability_name: str,
        *,
        source_model_id: str = "",
    ) -> bool:
        from warhammer40k_ai.utility.aura_utils import unit_within_range_of_unit

        model_id = str(source_model_id or "").strip()
        if model_id:
            models = list(source_unit.get_attached_unit_models() or [])
            for m in models:
                try:
                    if not getattr(m, "is_alive", True):
                        continue
                except Exception:
                    continue
                mid = str(getattr(m, "id", getattr(m, "_id", "")) or "")
                if mid != model_id:
                    continue
                return bool(source_unit._model_within_range_of_unit(m, target_unit, rng))
            return False

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

    def _target_unit_parent_army(self, target_unit):
        if target_unit is None:
            return None
        getter = getattr(target_unit, "get_parent_army", None)
        if callable(getter):
            return getter()
        parent = getattr(target_unit, "parent_army", None)
        if parent is not None:
            return parent
        return getattr(target_unit, "army", None)

    def _unit_has_alive_model_id(self, unit, model_id: str) -> bool:
        key = str(model_id or "").strip()
        if unit is None or not key:
            return False
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = []
            for member in self._attached_members(unit):
                models.extend(list(getattr(member, "models", []) or []))
        for model in models:
            mid = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "")
            if mid != key:
                continue
            alive_attr = getattr(model, "is_alive", True)
            try:
                return bool(alive_attr() if callable(alive_attr) else alive_attr)
            except Exception:
                return False
        return False

    def _unit_is_alive_or_unknown(self, unit) -> bool:
        if unit is None:
            return False
        alive_attr = getattr(unit, "is_alive", None)
        if callable(alive_attr):
            return bool(alive_attr())
        if alive_attr is None:
            return True
        return bool(alive_attr)

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
            if not self._unit_is_alive_or_unknown(u):
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

    def _targeted_stratagem_cp_discount_usage_key(self, spec: dict, *, source_unit=None) -> str:
        base = str(spec.get("usage_key", "") or "").strip().upper()
        if not base:
            base = "TARGETED_STRATAGEM_DISCOUNT"
        scope = str(spec.get("usage_scope", "") or "army_ability").strip().lower()
        if scope == "source_unit" and source_unit is not None:
            try:
                get_root = getattr(source_unit, "get_attached_unit_root", None)
                root = get_root() if callable(get_root) else source_unit
            except Exception:
                root = source_unit
            try:
                unit_id = str(get_entity_id(root) or "").strip()
            except Exception:
                unit_id = ""
            if unit_id:
                return f"{base}:{unit_id}"
        if scope == "source_model":
            model_id = str(spec.get("source_model_id", "") or "").strip()
            if model_id:
                return f"{base}:{model_id}"
        return base

    def _targeted_stratagem_cp_discount_available(self, spec: dict) -> bool:
        usage_key = str(spec.get("_effective_usage_key", "") or "").strip().upper()
        if not usage_key:
            usage_key = "TARGETED_STRATAGEM_DISCOUNT"
        limit = str(spec.get("limit", "") or "battle_round").strip().lower().replace(" ", "_")
        if limit == "turn":
            return not self._ability_used_this_turn(usage_key)
        br = self._battle_round()
        if br <= 0:
            return False
        return int(self._ability_used_battle_round.get(usage_key, 0) or 0) != br

    def _mark_targeted_stratagem_cp_discount_used(self, spec: dict) -> None:
        usage_key = str(spec.get("_effective_usage_key", "") or "").strip().upper()
        if not usage_key:
            usage_key = "TARGETED_STRATAGEM_DISCOUNT"
        limit = str(spec.get("limit", "") or "battle_round").strip().lower().replace(" ", "_")
        if limit == "turn":
            self._mark_ability_used_turn(usage_key)
            return
        br = self._battle_round()
        if br > 0:
            self._ability_used_battle_round[usage_key] = br

    def _target_unit_has_stratagem_target_cp_discount(self, target_unit) -> tuple[list[dict], list[str]]:
        if target_unit is None:
            return [], []
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return [], []
        members = self._attached_members(target_unit)
        names: list[str] = []
        found_specs: list[dict] = []
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            raw_specs = list(sr.get("stratagem_target_cp_discount_specs", []) or [])
            if not raw_specs and sr.get("stratagem_target_cp_discount"):
                raw_names = list(sr.get("stratagem_target_cp_discount_sources", []) or [])
                if not raw_names:
                    raw_names = ["Stratagem CP Discount"]
                raw_specs = [
                    {
                        "name": str(nm or "Stratagem CP Discount"),
                        "limit": "battle_round",
                        "usage_scope": "army_ability",
                        "usage_key": "TARGETED_STRATAGEM_DISCOUNT",
                    }
                    for nm in raw_names
                ]
            for spec in raw_specs:
                if not isinstance(spec, dict):
                    continue
                resolved = dict(spec)
                name = str(resolved.get("name", "") or "Stratagem CP Discount").strip() or "Stratagem CP Discount"
                resolved["name"] = name
                limit = str(resolved.get("limit", "") or "battle_round").strip().lower().replace(" ", "_")
                if limit not in ("battle_round", "turn"):
                    limit = "battle_round"
                resolved["limit"] = limit
                resolved["_effective_usage_key"] = self._targeted_stratagem_cp_discount_usage_key(resolved, source_unit=u)
                source_model_id = str(resolved.get("source_model_id", "") or "").strip()
                if source_model_id:
                    model_alive = False
                    models = list(getattr(u, "get_attached_unit_models", lambda: [])() or [])
                    for model in models:
                        model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                        if model_id != source_model_id:
                            continue
                        alive_attr = getattr(model, "is_alive", True)
                        model_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                        break
                    if not model_alive:
                        continue
                if not self._targeted_stratagem_cp_discount_available(resolved):
                    continue
                names.append(name)
                found_specs.append(resolved)

        seen_specs: set[str] = set()
        deduped_specs: list[dict] = []
        for spec in found_specs:
            key = str(spec.get("_effective_usage_key", "") or "").strip().upper()
            if not key:
                key = f"TARGETED_STRATAGEM_DISCOUNT:{str(spec.get('name', '')).strip().upper()}"
            if key in seen_specs:
                continue
            seen_specs.add(key)
            deduped_specs.append(spec)

        seen = set()
        deduped_names: list[str] = []
        for n in names:
            key = str(n).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped_names.append(str(n))
        return deduped_specs, deduped_names

    def _target_unit_has_stratagem_target_cp_discount_aura(self, target_unit) -> tuple[list[dict], list[str]]:
        if target_unit is None:
            return [], []
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return [], []
        army = self.get_army()
        if army is None:
            return [], []

        names: list[str] = []
        found_specs: list[dict] = []
        for u in list(getattr(army, "units", []) or []):
            if not self._unit_is_alive_or_unknown(u):
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
                resolved = dict(spec)
                name = str(resolved.get("name", "") or "Stratagem CP Discount").strip() or "Stratagem CP Discount"
                resolved["name"] = name
                limit = str(resolved.get("limit", "") or "battle_round").strip().lower().replace(" ", "_")
                if limit not in ("battle_round", "turn"):
                    limit = "battle_round"
                resolved["limit"] = limit
                source_model_id = str(resolved.get("source_model_id", "") or "").strip()
                if not self._source_model_within_range_for_ability(
                    u,
                    target_unit,
                    rng,
                    name,
                    source_model_id=source_model_id,
                ):
                    continue
                resolved["_effective_usage_key"] = self._targeted_stratagem_cp_discount_usage_key(resolved, source_unit=u)
                if not self._targeted_stratagem_cp_discount_available(resolved):
                    continue
                names.append(name)
                found_specs.append(resolved)

        seen_specs: set[str] = set()
        deduped_specs: list[dict] = []
        for spec in found_specs:
            key = str(spec.get("_effective_usage_key", "") or "").strip().upper()
            if not key:
                key = f"TARGETED_STRATAGEM_DISCOUNT_AURA:{str(spec.get('name', '')).strip().upper()}"
            if key in seen_specs:
                continue
            seen_specs.add(key)
            deduped_specs.append(spec)

        seen = set()
        deduped_names: list[str] = []
        for n in names:
            key = str(n).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped_names.append(str(n))
        return deduped_specs, deduped_names

    def _preview_targeted_stratagem_cp_discount(self, *, target_unit=None) -> tuple[int, list[str], list[dict]]:
        """
        Generic targeted stratagem CP discount:
        Once per battle round, one unit from your army with this ability can use it when its unit
        is targeted with a Stratagem. If it does, reduce the CP cost by 1CP.
        """
        if target_unit is None:
            return 0, [], []
        br = self._battle_round()
        if br <= 0:
            return 0, [], []
        direct_specs, direct_names = self._target_unit_has_stratagem_target_cp_discount(target_unit)
        aura_specs, aura_names = self._target_unit_has_stratagem_target_cp_discount_aura(target_unit)
        combined_specs = list(direct_specs or [])
        combined_specs.extend(list(aura_specs or []))
        if not combined_specs:
            return 0, [], []
        combined_specs.sort(
            key=lambda spec: (
                str(spec.get("_effective_usage_key", "") or "").strip().upper(),
                str(spec.get("name", "") or "").strip().lower(),
                str(spec.get("limit", "") or "").strip().lower(),
            )
        )
        seen_specs: set[str] = set()
        deduped_specs: list[dict] = []
        for spec in combined_specs:
            key = str(spec.get("_effective_usage_key", "") or "").strip().upper()
            if not key:
                key = f"TARGETED_STRATAGEM_DISCOUNT:{str(spec.get('name', '')).strip().upper()}"
            if key in seen_specs:
                continue
            seen_specs.add(key)
            deduped_specs.append(spec)
        combined = list(direct_names or [])
        combined.extend(aura_names or [])
        seen = set()
        deduped: list[str] = []
        for n in combined:
            key = str(n).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(str(n))
        return 1, deduped, deduped_specs

    def _preview_seer_council_strands_of_fate_discount(self, *, stratagem=None) -> tuple[int, int]:
        if stratagem is None:
            return 0, 0
        army = self.get_army()
        mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
        if mgr is None:
            return 0, 0
        preview_fn = getattr(mgr, "preview_seer_council_fate_discount", None)
        if not callable(preview_fn):
            return 0, 0
        info = preview_fn(stratagem_name=getattr(stratagem, "name", None) or "")
        discount = int(info.get("discount", 0) or 0)
        die_value = int(info.get("die_value", 0) or 0)
        if discount <= 0 or die_value <= 0:
            return 0, 0
        return 1, die_value

    def _target_unit_has_stratagem_target_cp_increase_sources(self, target_unit, *, current_cost: int | None = None) -> tuple[list[dict], list[dict]]:
        if target_unit is None:
            return [], []
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is self.get_army():
            return [], []
        army = self.get_army()
        if army is None:
            return [], []

        auto_specs: list[dict] = []
        optional_specs: list[dict] = []
        for u in list(getattr(army, "units", []) or []):
            if not self._unit_is_alive_or_unknown(u):
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
                source_model_id = str(spec.get("source_model_id", "") or "").strip()
                if not self._source_model_within_range_for_ability(
                    u,
                    target_unit,
                    rng,
                    name,
                    source_model_id=source_model_id,
                ):
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
                    if int(current_cost) >= int(max_cp):
                        continue
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
            try:
                increase = max(1, int(used_spec.get("cp_increase", 1) or 1))
            except Exception:
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
                try:
                    increase = max(1, int(used_spec.get("cp_increase", 1) or 1))
                except Exception:
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
            if not self._unit_is_alive_or_unknown(u):
                continue
            return True
        return False

    def _target_unit_has_ancestral_crest(self, target_unit) -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        members = self._attached_members(target_unit)
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not sr.get("enhancement_ancestral_crest", False):
                continue
            if not self._unit_is_alive_or_unknown(u):
                continue
            get_bearer = getattr(u, "_get_enhancement_bearer_model", None)
            if callable(get_bearer) and get_bearer() is None:
                continue
            return True
        return False

    def _target_unit_has_mirror_of_fates(self, target_unit) -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        members = self._attached_members(target_unit)
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_mirror_of_fates_free_command_reroll_once_per_battle_round", False)):
                continue
            if not self._unit_is_alive_or_unknown(u):
                continue
            get_bearer = getattr(u, "_get_enhancement_bearer_model", None)
            if callable(get_bearer) and get_bearer() is None:
                continue
            return True
        return False

    def _target_unit_can_use_mirror_of_fates_command_reroll(self, target_unit) -> bool:
        if not self._target_unit_has_mirror_of_fates(target_unit):
            return False
        br = self._battle_round()
        if br <= 0:
            return False
        return int(self._ability_used_battle_round.get("MIRROR_OF_FATES", 0) or 0) != br

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
            if not self._unit_is_alive_or_unknown(u):
                continue
            return True
        return False

    def _target_unit_has_beacon_angelis(self, target_unit) -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        members = self._attached_members(target_unit)
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_beacon_angelis_rapid_ingress_discount")):
                continue
            if not self._unit_is_alive_or_unknown(u):
                continue
            get_bearer = getattr(u, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is None:
                continue
            alive_attr = getattr(bearer, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not is_alive:
                continue
            return True
        return False

    def _target_unit_can_use_grimnars_mark_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        stratagem_key = str(stratagem_name or "").strip().upper()
        if stratagem_key not in ("RAPID INGRESS", "HEROIC INTERVENTION"):
            return False
        battle_round = self._battle_round()
        if battle_round < 2:
            return False
        usage_key = "GRIMNARS_MARK_FREE_STRATAGEM"
        if int(self._ability_used_battle_round.get(usage_key, 0) or 0) == battle_round:
            return False
        army = self.get_army()
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        if sm_mgr is None or not bool(getattr(sm_mgr, "is_saga_of_the_great_wolf", lambda: False)()):
            return False
        members = self._attached_members(target_unit)
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_grimnars_mark", False)):
                continue
            if not self._unit_is_alive_or_unknown(u):
                continue
            configured_usage_key = str(sr.get("enhancement_grimnars_mark_usage_key", "") or "").strip().upper()
            if configured_usage_key:
                usage_key = configured_usage_key
                if int(self._ability_used_battle_round.get(usage_key, 0) or 0) == battle_round:
                    continue
            try:
                min_round = int(sr.get("enhancement_grimnars_mark_min_battle_round", 2) or 2)
            except Exception:
                min_round = 2
            if battle_round < int(max(1, min_round)):
                continue
            configured_names = [
                str(v or "").strip().upper()
                for v in list(sr.get("enhancement_grimnars_mark_stratagem_names", []) or [])
                if str(v or "").strip()
            ]
            if configured_names and stratagem_key not in set(configured_names):
                continue
            get_bearer = getattr(u, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is None:
                continue
            alive_attr = getattr(bearer, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not is_alive:
                continue
            return True
        return False

    def _target_unit_can_use_beast_handler_heroic_intervention(self, target_unit) -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_beast_handler_heroic_intervention", None)
        if callable(fn):
            return bool(fn(self.game))
        return False

    def _target_unit_can_use_guardians_of_the_machine_heroic_intervention(self, target_unit, *, enemy_unit=None) -> bool:
        if target_unit is None or enemy_unit is None:
            return False
        fn = getattr(target_unit, "can_use_guardians_of_the_machine_heroic_intervention", None)
        if callable(fn):
            return bool(fn(self.game, enemy_unit=enemy_unit))
        return False

    def _target_unit_can_use_prophetic_sentinels_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_prophetic_sentinels_stratagem_discount", None)
        if callable(fn):
            return bool(fn(self.game, stratagem_name=stratagem_name))
        return False

    def _target_unit_can_use_protector_of_paths_overwatch(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_protector_of_paths_overwatch", None)
        if callable(fn):
            return bool(fn(self.game, stratagem_name=stratagem_name))
        return False

    def _target_unit_can_use_shriekworm_familiar_overwatch(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_shriekworm_familiar_overwatch", None)
        if callable(fn):
            return bool(fn(self.game, stratagem_name=stratagem_name))
        return False

    def _target_unit_can_use_snarling_protector_heroic_intervention(self, target_unit) -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_snarling_protector_heroic_intervention", None)
        if callable(fn):
            return bool(fn(self.game))
        return False

    def _target_unit_can_use_intraneural_biotech_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_intraneural_biotech_stratagem_discount", None)
        if callable(fn):
            return bool(fn(self.game, stratagem_name=stratagem_name))
        return False

    def _target_unit_can_use_empyric_suffusion_heroic_intervention(self, target_unit) -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        if not self._unit_has_keyword(target_unit, "SLAANESH"):
            return False
        br = self._battle_round()
        if br <= 0:
            return False
        if int(self._ability_used_battle_round.get("EMPYRIC_SUFFUSION_HEROIC_INTERVENTION", 0) or 0) == br:
            return False
        army = self.get_army()
        if army is None:
            return False
        from warhammer40k_ai.utility.aura_utils import model_within_range_of_unit

        get_target_root = getattr(target_unit, "get_attached_unit_root", None)
        target_root = get_target_root() if callable(get_target_root) else target_unit
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_empyric_suffusion"):
                continue
            if not self._unit_is_alive_or_unknown(unit):
                continue
            try:
                if not bool(getattr(unit, "deployed", True)):
                    continue
            except Exception:
                pass
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            bearer = getattr(unit, "_get_enhancement_bearer_model", lambda: None)()
            if bearer is None or not bool(getattr(bearer, "is_alive", True)):
                continue
            if model_within_range_of_unit(bearer, target_root, 6.0, use_attached_aggregate=True):
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
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_beast_handler_heroic_intervention_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().lower()
        if name != "heroic intervention":
            return 0
        if not self._target_unit_can_use_beast_handler_heroic_intervention(target_unit):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_guardians_of_the_machine_heroic_intervention_discount(
        self,
        *,
        stratagem=None,
        target_unit=None,
        enemy_unit=None,
    ) -> int:
        if stratagem is None or target_unit is None or enemy_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().lower()
        if name != "heroic intervention":
            return 0
        if not self._target_unit_can_use_guardians_of_the_machine_heroic_intervention(
            target_unit,
            enemy_unit=enemy_unit,
        ):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_prophetic_sentinels_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name not in ("HEROIC INTERVENTION", "OVERWATCH", "FIRE OVERWATCH"):
            return 0
        if not self._target_unit_can_use_prophetic_sentinels_stratagem_discount(target_unit, stratagem_name=name):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_protector_of_paths_overwatch_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name not in ("OVERWATCH", "FIRE OVERWATCH"):
            return 0
        if not self._target_unit_can_use_protector_of_paths_overwatch(target_unit, stratagem_name=name):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_shriekworm_familiar_overwatch_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name not in ("OVERWATCH", "FIRE OVERWATCH"):
            return 0
        if not self._target_unit_can_use_shriekworm_familiar_overwatch(target_unit, stratagem_name=name):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_snarling_protector_heroic_intervention_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().lower()
        if name != "heroic intervention":
            return 0
        if not self._target_unit_can_use_snarling_protector_heroic_intervention(target_unit):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_intraneural_biotech_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u not in ("HEROIC INTERVENTION", "COUNTER-OFFENSIVE", "COUNTER OFFENSIVE"):
            return 0
        if not self._target_unit_can_use_intraneural_biotech_stratagem_discount(target_unit, stratagem_name=name_u):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_beacon_angelis_rapid_ingress_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u != "RAPID INGRESS":
            return 0
        if not self._target_unit_has_beacon_angelis(target_unit):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_grimnars_mark_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u not in ("RAPID INGRESS", "HEROIC INTERVENTION"):
            return 0
        if not self._target_unit_can_use_grimnars_mark_stratagem_discount(target_unit, stratagem_name=name_u):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_empyric_suffusion_heroic_intervention_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().lower()
        if name != "heroic intervention":
            return 0
        if not self._target_unit_can_use_empyric_suffusion_heroic_intervention(target_unit):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
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

    def _preview_mirror_of_fates_discount(self, *, stratagem=None, target_unit=None) -> int:
        """
        Mirror of Fates (Lords of Dread):
        Once per battle round, you can target the bearer's unit with Command Re-roll for 0CP.
        """
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().lower()
        if name not in ("command re-roll", "command reroll"):
            return 0
        if not self._target_unit_can_use_mirror_of_fates_command_reroll(target_unit):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_ancestral_crest_discount(self, *, stratagem=None, target_unit=None) -> int:
        """
        Ancestral Crest (Needgaârd Oathband):
        Once per turn, when targeting the bearer's unit with Command Re-roll, spend 1YP to reduce CP by 1.
        """
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().lower()
        if name not in ("command re-roll", "command reroll"):
            return 0
        if self._ability_used_this_turn("ANCESTRAL_CREST"):
            return 0
        if not self._target_unit_has_ancestral_crest(target_unit):
            return 0
        army = self.get_army()
        pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
        if pe is None:
            return 0
        try:
            if int(getattr(pe, "yield_points", 0) or 0) < 1:
                return 0
        except Exception:
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

    def _preview_unparalleled_tactician_discount(self, *, stratagem=None) -> int:
        """
        Unparalleled Tactician (Shadowmark Talon):
        Once per battle round, if Aethon Shaan is on the battlefield, you can use
        INTO DARKNESS for 0CP.
        """
        if stratagem is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u != "INTO DARKNESS":
            return 0
        army = self.get_army()
        sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
        can_fn = (
            getattr(sm_mgr, "can_use_unparalleled_tactician_into_darkness_discount", None)
            if sm_mgr is not None
            else None
        )
        if not callable(can_fn) or not bool(can_fn(game=self.game)):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_tyrannical_court_claimed_for_dark_gods_discount(self, *, stratagem=None) -> int:
        """
        Tyrannical Court (Lords of Dread):
        Once per battle round, if your Warlord is on the battlefield, you can use
        CLAIMED FOR THE DARK GODS for 0CP.
        """
        if stratagem is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u != "CLAIMED FOR THE DARK GODS":
            return 0
        army = self.get_army()
        ck_mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
        can_fn = (
            getattr(ck_mgr, "can_use_tyrannical_court_claimed_for_dark_gods_discount", None)
            if ck_mgr is not None
            else None
        )
        if not callable(can_fn) or not bool(can_fn(game=self.game)):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

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

    def preview_stratagem_cp_cost(
        self,
        stratagem,
        *,
        target_unit=None,
        enemy_unit=None,
        assume_optional_discounts: bool | None = None,
    ) -> dict:
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
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()

        unparalleled = self._preview_unparalleled_tactician_discount(stratagem=stratagem)
        if unparalleled:
            ctx = {
                "ability_name": "Unparalleled Tactician",
                "stratagem": getattr(stratagem, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability("UNPARALLELED_TACTICIAN", ctx, assume=assume_optional_discounts):
                discount = base
                reasons.append("Unparalleled Tactician: Into Darkness for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        tyrannical_court = self._preview_tyrannical_court_claimed_for_dark_gods_discount(stratagem=stratagem)
        if tyrannical_court:
            ctx = {
                "ability_name": "Tyrannical Court",
                "stratagem": getattr(stratagem, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "TYRANNICAL_COURT_CLAIMED_FOR_DARK_GODS",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append("Tyrannical Court: Claimed for the Dark Gods for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        faultless = self._preview_faultless_opportunist_discount(stratagem=stratagem, target_unit=target_unit)
        if faultless:
            discount = base
            reasons.append("Faultless Opportunist: Heroic Intervention for 0CP.")
            return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        beast_handler = self._preview_beast_handler_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if beast_handler:
            ctx = {
                "ability_name": "Beast Handler",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability("BEAST_HANDLER_HEROIC_INTERVENTION", ctx, assume=assume_optional_discounts):
                discount = base
                reasons.append("Beast Handler: Heroic Intervention for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        guardians = self._preview_guardians_of_the_machine_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
            enemy_unit=enemy_unit,
        )
        if guardians:
            ctx = {
                "ability_name": "Guardians of the Machine",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "enemy_unit": getattr(enemy_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "GUARDIANS_OF_THE_MACHINE_HEROIC_INTERVENTION",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append("Guardians of the Machine: Heroic Intervention for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        empyric = self._preview_empyric_suffusion_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if empyric:
            ctx = {
                "ability_name": "Empyric Suffusion",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "EMPYRIC_SUFFUSION_HEROIC_INTERVENTION",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append("Empyric Suffusion: Heroic Intervention for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        prophetic = self._preview_prophetic_sentinels_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if prophetic:
            if name_u in ("OVERWATCH", "FIRE OVERWATCH"):
                mgr = getattr(self, "stratagems", None)
                used_this_turn = getattr(mgr, "_used_this_turn", {}) if mgr is not None else {}
                overwatch_used = bool(used_this_turn.get("OVERWATCH", False)) if isinstance(used_this_turn, dict) else False
                can_traitor = bool(
                    getattr(target_unit, "can_use_traitor_enforcer_overwatch", lambda _g=None: False)(self.game)
                )
                if overwatch_used and not can_traitor:
                    prophetic = 0
            if not prophetic:
                pass
            else:
                ability_name = "Prophetic Sentinels"
                try:
                    get_rule = getattr(target_unit, "get_prophetic_sentinels_stratagem_discount_rule", None)
                    rule = get_rule() if callable(get_rule) else None
                    if isinstance(rule, dict):
                        ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
                except Exception:
                    pass
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                if self._should_preview_optional_ability(
                    "PROPHETIC_SENTINELS_STRATAGEM_DISCOUNT",
                    ctx,
                    assume=assume_optional_discounts,
                ):
                    discount = base
                    reasons.append(f"{ability_name}: Stratagem for 0CP.")
                    return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        protector = self._preview_protector_of_paths_overwatch_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if protector:
            ability_name = "Protector of the Paths"
            try:
                get_rule = getattr(target_unit, "get_protector_of_paths_overwatch_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "PROTECTOR_OF_PATHS_OVERWATCH",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Fire Overwatch for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        shriekworm = self._preview_shriekworm_familiar_overwatch_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if shriekworm:
            ability_name = "Shriekworm Familiar"
            try:
                get_rule = getattr(target_unit, "get_shriekworm_familiar_overwatch_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "SHRIEKWORM_FAMILIAR_OVERWATCH",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Fire Overwatch for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        snarling = self._preview_snarling_protector_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if snarling:
            ability_name = "Snarling Protector"
            try:
                get_rule = getattr(target_unit, "get_snarling_protector_heroic_intervention_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "SNARLING_PROTECTOR_HEROIC_INTERVENTION",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Heroic Intervention for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        intraneural = self._preview_intraneural_biotech_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if intraneural:
            ability_name = "Intraneural Biotech"
            try:
                get_rule = getattr(target_unit, "get_intraneural_biotech_stratagem_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            ability_key = "INTRANEURAL_BIOTECH_STRATAGEM_DISCOUNT"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                ability_key,
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                if name_u == "HEROIC INTERVENTION":
                    reasons.append(f"{ability_name}: Heroic Intervention for 0CP.")
                else:
                    reasons.append(f"{ability_name}: Counter-offensive for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        if name_u in ("OVERWATCH", "FIRE OVERWATCH") and target_unit is not None:
            get_rule = getattr(target_unit, "get_traitor_enforcer_overwatch_rule", None)
            rule = get_rule() if callable(get_rule) else None
            if rule and bool(getattr(target_unit, "can_use_traitor_enforcer_overwatch", lambda _g=None: False)(self.game)):
                ctx = {
                    "ability_name": str(rule.get("source", "") or "Brutal Example"),
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                if self._should_preview_optional_ability("BRUTAL_EXAMPLE_OVERWATCH", ctx, assume=assume_optional_discounts):
                    discount = base
                    reasons.append(f"{ctx['ability_name']}: Fire Overwatch for 0CP (destroy 1 Bodyguard model).")
                    return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        if name_u in ("COUNTER-OFFENSIVE", "COUNTER OFFENSIVE") and target_unit is not None:
            get_rule = getattr(target_unit, "get_daemonforge_counter_offensive_rule", None)
            rule = get_rule() if callable(get_rule) else None
            can_daemonforge = False
            mgr = getattr(self, "stratagems", None)
            daemonforge_available = getattr(mgr, "_counter_offensive_daemonforge_available", None)
            if callable(daemonforge_available):
                can_daemonforge = bool(
                    daemonforge_available(
                        target_unit=target_unit,
                        candidates=None,
                    )
                )
            elif rule:
                can_daemonforge = bool(
                    getattr(target_unit, "can_use_daemonforge_counter_offensive", lambda _g=None: False)(self.game)
                )
            if rule and can_daemonforge:
                ability_name = str(rule.get("source", "") or "Daemonforge").strip() or "Daemonforge"
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                if self._should_preview_optional_ability(
                    "DAEMONFORGE_COUNTER_OFFENSIVE",
                    ctx,
                    assume=assume_optional_discounts,
                ):
                    discount = base
                    reasons.append(f"{ability_name}: Counter-offensive for 0CP.")
                    return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        grimnars_mark = self._preview_grimnars_mark_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if grimnars_mark:
            discount = base
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u == "HEROIC INTERVENTION":
                reasons.append("Grimnar's Mark: Heroic Intervention for 0CP.")
            else:
                reasons.append("Grimnar's Mark: Rapid Ingress for 0CP.")
            return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        beacon = self._preview_beacon_angelis_rapid_ingress_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if beacon:
            discount = base
            reasons.append("Beacon Angelis: Rapid Ingress for 0CP.")
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

        tsd, tsd_names, tsd_specs = self._preview_targeted_stratagem_cp_discount(target_unit=target_unit)
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
                chosen = tsd_specs[0] if tsd_specs else {}
                limit = str(chosen.get("limit", "") or "battle_round").strip().lower()
                limit_label = "once per turn" if limit == "turn" else "once per battle round"
                reasons.append(f"Targeted Stratagem Discount ({label}): -1CP ({limit_label})")

        seer_discount, seer_die_value = self._preview_seer_council_strands_of_fate_discount(stratagem=stratagem)
        if seer_discount:
            ctx = {
                "ability_name": "Strands of Fate",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
                "fate_die_value": int(seer_die_value),
            }
            if self._should_preview_optional_ability(
                "SEER_COUNCIL_STRANDS_OF_FATE",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount += int(seer_discount)
                reasons.append(f"Strands of Fate: discard Fate die {int(seer_die_value)} for -1CP")

        gof = self._preview_gift_of_foresight_discount(stratagem=stratagem, target_unit=target_unit)
        if gof:
            discount += int(gof)
            logger.info("Gift of Foresight: %s uses Command Re-roll for 0CP.", self.name)

        mof = self._preview_mirror_of_fates_discount(stratagem=stratagem, target_unit=target_unit)
        if mof:
            discount += int(mof)
            logger.info("Mirror of Fates: %s uses Command Re-roll for 0CP.", self.name)

        ac = self._preview_ancestral_crest_discount(stratagem=stratagem, target_unit=target_unit)
        if ac:
            ctx = {
                "ability_name": "Ancestral Crest",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability("ANCESTRAL_CREST", ctx, assume=assume_optional_discounts):
                discount += int(ac)
                reasons.append("Ancestral Crest: -1CP (spend 1YP, once per turn)")

        mop = self._preview_master_of_the_pageant_discount(stratagem=stratagem, target_unit=target_unit)
        if mop:
            discount += int(mop)
            reasons.append("Master of the Pageant: -1CP (once per battle round)")

        cost = max(0, base - discount)
        return {"base": base, "discount": discount, "cost": cost, "reasons": reasons}

    def apply_stratagem_cp_cost(self, stratagem, *, target_unit=None, enemy_unit=None) -> dict:
        """
        Compute effective CP cost and CONSUME any once-per-battle-round discounts that are applied.
        """
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        target_root_id = ""
        if target_unit is not None:
            try:
                get_root = getattr(target_unit, "get_attached_unit_root", None)
                root = get_root() if callable(get_root) else target_unit
            except Exception:
                root = target_unit
            try:
                target_root_id = str(get_entity_id(root) or "")
            except Exception:
                target_root_id = ""
        self._pending_stratagem_target_unit_id = str(target_root_id or "")
        self._pending_stratagem_name = str(getattr(stratagem, "name", "") or "").strip()
        unparalleled = self._preview_unparalleled_tactician_discount(stratagem=stratagem)
        if unparalleled:
            ctx = {
                "ability_name": "Unparalleled Tactician",
                "stratagem": getattr(stratagem, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("UNPARALLELED_TACTICIAN", ctx):
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
                army = self.get_army()
                sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
                mark_used = getattr(sm_mgr, "mark_unparalleled_tactician_used", None) if sm_mgr is not None else None
                if callable(mark_used):
                    mark_used(game=self.game)
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": ["Unparalleled Tactician: Into Darkness for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                }
        tyrannical_court = self._preview_tyrannical_court_claimed_for_dark_gods_discount(stratagem=stratagem)
        if tyrannical_court:
            ctx = {
                "ability_name": "Tyrannical Court",
                "stratagem": getattr(stratagem, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("TYRANNICAL_COURT_CLAIMED_FOR_DARK_GODS", ctx):
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
                army = self.get_army()
                ck_mgr = getattr(army, "chaos_knights_detachments", None) if army is not None else None
                mark_used = (
                    getattr(ck_mgr, "mark_tyrannical_court_claimed_for_dark_gods_discount_used", None)
                    if ck_mgr is not None
                    else None
                )
                if callable(mark_used):
                    mark_used(game=self.game)
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": ["Tyrannical Court: Claimed for the Dark Gods for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                }
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
        beast_handler = self._preview_beast_handler_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if beast_handler:
            ctx = {
                "ability_name": "Beast Handler",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("BEAST_HANDLER_HEROIC_INTERVENTION", ctx):
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
                get_root = getattr(target_unit, "get_attached_unit_root", None)
                root = get_root() if callable(get_root) else target_unit
                if root is not None:
                    mark_used = getattr(root, "mark_unit_once_per_battle_used", None)
                    if callable(mark_used):
                        mark_used(
                            "beast_handler_heroic_intervention",
                            ability_name="Beast Handler",
                        )
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": ["Beast Handler: Heroic Intervention for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                }
        guardians = self._preview_guardians_of_the_machine_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
            enemy_unit=enemy_unit,
        )
        if guardians:
            ctx = {
                "ability_name": "Guardians of the Machine",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "enemy_unit": getattr(enemy_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("GUARDIANS_OF_THE_MACHINE_HEROIC_INTERVENTION", ctx):
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
                    "reasons": ["Guardians of the Machine: Heroic Intervention for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                }
        empyric = self._preview_empyric_suffusion_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if empyric:
            ctx = {
                "ability_name": "Empyric Suffusion",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("EMPYRIC_SUFFUSION_HEROIC_INTERVENTION", ctx):
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
                br = self._battle_round()
                if br > 0:
                    self._ability_used_battle_round["EMPYRIC_SUFFUSION_HEROIC_INTERVENTION"] = br
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": ["Empyric Suffusion: Heroic Intervention for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                }
        prophetic = self._preview_prophetic_sentinels_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if prophetic and target_unit is not None and name_u not in ("OVERWATCH", "FIRE OVERWATCH"):
            ability_name = "Prophetic Sentinels"
            try:
                get_rule = getattr(target_unit, "get_prophetic_sentinels_stratagem_discount_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("PROPHETIC_SENTINELS_STRATAGEM_DISCOUNT", ctx):
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
                try:
                    mark_used = getattr(target_unit, "mark_prophetic_sentinels_used", None)
                    if callable(mark_used):
                        mark_used(
                            self.game,
                            source=ability_name,
                            stratagem_name=str(getattr(stratagem, "name", "") or ""),
                        )
                except Exception:
                    pass
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": [f"{ability_name}: Stratagem for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "prophetic_sentinels_use": True,
                    "prophetic_sentinels_source": ability_name,
                }
        snarling = self._preview_snarling_protector_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if snarling and target_unit is not None:
            ability_name = "Snarling Protector"
            try:
                get_rule = getattr(target_unit, "get_snarling_protector_heroic_intervention_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("SNARLING_PROTECTOR_HEROIC_INTERVENTION", ctx):
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
                    "reasons": [f"{ability_name}: Heroic Intervention for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "snarling_protector_heroic_intervention_use": True,
                    "snarling_protector_heroic_intervention_source": ability_name,
                }
        intraneural = self._preview_intraneural_biotech_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if intraneural and target_unit is not None:
            ability_name = "Intraneural Biotech"
            try:
                get_rule = getattr(target_unit, "get_intraneural_biotech_stratagem_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("INTRANEURAL_BIOTECH_STRATAGEM_DISCOUNT", ctx):
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
                try:
                    mark_used = getattr(target_unit, "mark_intraneural_biotech_used", None)
                    if callable(mark_used):
                        mark_used(
                            self.game,
                            source=ability_name,
                            stratagem_name=str(getattr(stratagem, "name", "") or ""),
                        )
                except Exception:
                    pass
                reason = f"{ability_name}: Heroic Intervention for 0CP."
                if name_u in ("COUNTER-OFFENSIVE", "COUNTER OFFENSIVE"):
                    reason = f"{ability_name}: Counter-offensive for 0CP."
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": [reason],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "intraneural_biotech_use": True,
                    "intraneural_biotech_source": ability_name,
                }
        if name_u in ("OVERWATCH", "FIRE OVERWATCH") and target_unit is not None:
            get_rule = getattr(target_unit, "get_traitor_enforcer_overwatch_rule", None)
            rule = get_rule() if callable(get_rule) else None
            can_traitor = bool(rule) and bool(
                getattr(target_unit, "can_use_traitor_enforcer_overwatch", lambda _g=None: False)(self.game)
            )
            can_prophetic = bool(
                self._target_unit_can_use_prophetic_sentinels_stratagem_discount(
                    target_unit,
                    stratagem_name=name_u,
                )
            )
            can_protector = bool(
                self._target_unit_can_use_protector_of_paths_overwatch(
                    target_unit,
                    stratagem_name=name_u,
                )
            )
            can_shriekworm = bool(
                self._target_unit_can_use_shriekworm_familiar_overwatch(
                    target_unit,
                    stratagem_name=name_u,
                )
            )
            mgr = getattr(self, "stratagems", None)
            used_this_turn = getattr(mgr, "_used_this_turn", {}) if mgr is not None else {}
            overwatch_used = bool(used_this_turn.get("OVERWATCH", False)) if isinstance(used_this_turn, dict) else False
            if overwatch_used and not can_traitor:
                return {"denied": True, "reason": "Overwatch already used this turn"}
            if can_prophetic:
                ability_name = "Prophetic Sentinels"
                try:
                    get_p_rule = getattr(target_unit, "get_prophetic_sentinels_stratagem_discount_rule", None)
                    p_rule = get_p_rule() if callable(get_p_rule) else None
                    if isinstance(p_rule, dict):
                        ability_name = str(p_rule.get("source", "") or ability_name).strip() or ability_name
                except Exception:
                    pass
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                use_prophetic = self._should_use_optional_ability("PROPHETIC_SENTINELS_STRATAGEM_DISCOUNT", ctx)
                if use_prophetic:
                    applied_discount = base
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
                    try:
                        mark_used = getattr(target_unit, "mark_prophetic_sentinels_used", None)
                        if callable(mark_used):
                            mark_used(
                                self.game,
                                source=ability_name,
                                stratagem_name=str(getattr(stratagem, "name", "") or ""),
                            )
                    except Exception:
                        pass
                    return {
                        "base": base,
                        "discount": applied_discount,
                        "available_discount": applied_discount,
                        "cost": cost,
                        "increase": increase,
                        "increase_reasons": increase_reasons,
                        "reasons": [f"{ability_name}: Fire Overwatch for 0CP (used)"],
                        "prophetic_sentinels_use": True,
                        "prophetic_sentinels_source": ability_name,
                    }
            if can_protector:
                ability_name = "Protector of the Paths"
                try:
                    get_pro_rule = getattr(target_unit, "get_protector_of_paths_overwatch_rule", None)
                    pro_rule = get_pro_rule() if callable(get_pro_rule) else None
                    if isinstance(pro_rule, dict):
                        ability_name = str(pro_rule.get("source", "") or ability_name).strip() or ability_name
                except Exception:
                    pass
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                use_protector = self._should_use_optional_ability("PROTECTOR_OF_PATHS_OVERWATCH", ctx)
                if use_protector:
                    applied_discount = base
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
                        "available_discount": applied_discount,
                        "cost": cost,
                        "increase": increase,
                        "increase_reasons": increase_reasons,
                        "reasons": [f"{ability_name}: Fire Overwatch for 0CP (used)"],
                        "protector_of_paths_overwatch_use": True,
                        "protector_of_paths_overwatch_source": ability_name,
                    }
            if can_shriekworm:
                ability_name = "Shriekworm Familiar"
                try:
                    get_sr_rule = getattr(target_unit, "get_shriekworm_familiar_overwatch_rule", None)
                    sr_rule = get_sr_rule() if callable(get_sr_rule) else None
                    if isinstance(sr_rule, dict):
                        ability_name = str(sr_rule.get("source", "") or ability_name).strip() or ability_name
                except Exception:
                    pass
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                use_shriekworm = self._should_use_optional_ability("SHRIEKWORM_FAMILIAR_OVERWATCH", ctx)
                if use_shriekworm:
                    applied_discount = base
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
                        "available_discount": applied_discount,
                        "cost": cost,
                        "increase": increase,
                        "increase_reasons": increase_reasons,
                        "reasons": [f"{ability_name}: Fire Overwatch for 0CP (used)"],
                        "shriekworm_familiar_overwatch_use": True,
                        "shriekworm_familiar_overwatch_source": ability_name,
                    }
            if can_traitor:
                ability_name = str(rule.get("source", "") or "Brutal Example").strip() or "Brutal Example"
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                use_traitor = self._should_use_optional_ability("BRUTAL_EXAMPLE_OVERWATCH", ctx)
                if overwatch_used and not use_traitor:
                    return {"denied": True, "reason": "Overwatch already used this turn"}
                if use_traitor:
                    applied_discount = base
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
                        "available_discount": applied_discount,
                        "cost": cost,
                        "increase": increase,
                        "increase_reasons": increase_reasons,
                        "reasons": [f"{ability_name}: Fire Overwatch for 0CP (used)"],
                        "traitor_enforcer_overwatch_use": True,
                        "traitor_enforcer_overwatch_source": ability_name,
                    }
        if name_u in ("COUNTER-OFFENSIVE", "COUNTER OFFENSIVE") and target_unit is not None:
            get_rule = getattr(target_unit, "get_daemonforge_counter_offensive_rule", None)
            rule = get_rule() if callable(get_rule) else None
            mgr = getattr(self, "stratagems", None)
            used_this_phase = getattr(mgr, "_used_stratagems_this_phase", set()) if mgr is not None else set()
            counter_used = "COUNTER-OFFENSIVE" in used_this_phase if isinstance(used_this_phase, set) else False
            can_daemonforge = bool(
                getattr(target_unit, "can_use_daemonforge_counter_offensive", lambda _g=None: False)(self.game)
            )
            can_intraneural = self._target_unit_can_use_intraneural_biotech_stratagem_discount(
                target_unit,
                stratagem_name="COUNTER-OFFENSIVE",
            )
            if counter_used and not can_daemonforge and not can_intraneural:
                return {"denied": True, "reason": "Counter-offensive already used this phase"}
            if can_daemonforge and rule:
                ability_name = str(rule.get("source", "") or "Daemonforge").strip() or "Daemonforge"
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                use_daemonforge = self._should_use_optional_ability("DAEMONFORGE_COUNTER_OFFENSIVE", ctx)
                if counter_used and not use_daemonforge:
                    return {"denied": True, "reason": "Counter-offensive already used this phase"}
                if use_daemonforge:
                    applied_discount = base
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
                        "available_discount": applied_discount,
                        "cost": cost,
                        "increase": increase,
                        "increase_reasons": increase_reasons,
                        "reasons": [f"{ability_name}: Counter-offensive for 0CP (used)"],
                        "daemonforge_counter_offensive_use": True,
                        "daemonforge_counter_offensive_source": ability_name,
                    }
            if counter_used:
                return {"denied": True, "reason": "Counter-offensive already used this phase"}

        grimnars_mark = self._preview_grimnars_mark_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if grimnars_mark:
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
            usage_key = "GRIMNARS_MARK_FREE_STRATAGEM"
            members = self._attached_members(target_unit)
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not bool(sr.get("enhancement_grimnars_mark", False)):
                    continue
                configured_key = str(sr.get("enhancement_grimnars_mark_usage_key", "") or "").strip().upper()
                if configured_key:
                    usage_key = configured_key
                break
            br = self._battle_round()
            if br > 0:
                self._ability_used_battle_round[usage_key] = br
            stratagem_label = str(getattr(stratagem, "name", "") or "").strip().upper()
            if stratagem_label == "HEROIC INTERVENTION":
                reason = "Grimnar's Mark: Heroic Intervention for 0CP."
            else:
                reason = "Grimnar's Mark: Rapid Ingress for 0CP."
            return {
                "base": base,
                "discount": base,
                "cost": cost,
                "reasons": [reason],
                "increase": increase,
                "increase_reasons": increase_reasons,
            }

        beacon = self._preview_beacon_angelis_rapid_ingress_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if beacon:
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
                "reasons": ["Beacon Angelis: Rapid Ingress for 0CP."],
                "increase": increase,
                "increase_reasons": increase_reasons,
            }
        # For application, we still compute "available" discounts (even if declined), but affordability uses applied discount.
        preview = self.preview_stratagem_cp_cost(
            stratagem,
            target_unit=target_unit,
            enemy_unit=enemy_unit,
            assume_optional_discounts=True,
        )
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
        tsd_available, tsd_names, tsd_specs = self._preview_targeted_stratagem_cp_discount(target_unit=target_unit)
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
                chosen = tsd_specs[0] if tsd_specs else {}
                limit = str(chosen.get("limit", "") or "battle_round").strip().lower()
                limit_label = "once per turn" if limit == "turn" else "once per battle round"
                reasons.append(f"Targeted Stratagem Discount ({label}): -1CP ({limit_label}; used)")
                self._mark_targeted_stratagem_cp_discount_used(chosen)

        # Decide whether to apply Seer Council Strands of Fate discount if available.
        seer_available, seer_die_value = self._preview_seer_council_strands_of_fate_discount(stratagem=stratagem)
        if seer_available:
            ctx = {
                "ability_name": "Strands of Fate",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
                "fate_die_value": int(seer_die_value),
            }
            if self._should_use_optional_ability("SEER_COUNCIL_STRANDS_OF_FATE", ctx):
                army = self.get_army()
                mgr = getattr(army, "aeldari_detachments", None) if army is not None else None
                consume_fn = getattr(mgr, "consume_seer_council_fate_discount", None) if mgr is not None else None
                consumed = consume_fn(stratagem_name=getattr(stratagem, "name", None) or "") if callable(consume_fn) else {}
                if bool(consumed.get("consumed", False)):
                    applied_discount += int(consumed.get("discount", 1) or 1)
                    used_value = int(consumed.get("die_value", int(seer_die_value)) or int(seer_die_value))
                    reasons.append(f"Strands of Fate: discarded Fate die {used_value} for -1CP (used)")

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
                logger.info("Gift of Foresight: %s uses Command Re-roll for 0CP.", self.name)

        # Decide whether to apply Mirror of Fates if available.
        mof_discount = int(self._preview_mirror_of_fates_discount(stratagem=stratagem, target_unit=target_unit) or 0)
        if mof_discount:
            ctx = {
                "ability_name": "Mirror of Fates",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            use_mof = self._should_use_optional_ability("MIRROR_OF_FATES", ctx)
            if use_mof or getattr(self, "decision_hook", None) is None:
                applied_discount += int(mof_discount)
                br = self._battle_round()
                if br > 0:
                    self._ability_used_battle_round["MIRROR_OF_FATES"] = br
                reasons.append("Mirror of Fates: Command Re-roll for 0CP (used)")

        # Decide whether to apply Ancestral Crest if available.
        ac_available = bool(self._preview_ancestral_crest_discount(stratagem=stratagem, target_unit=target_unit))
        if ac_available:
            ctx = {
                "ability_name": "Ancestral Crest",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            use_ac = self._should_use_optional_ability("ANCESTRAL_CREST", ctx)
            if use_ac:
                army = self.get_army()
                pe = getattr(army, "prioritised_efficiency", None) if army is not None else None
                spent = bool(pe is not None and getattr(pe, "spend_yield_points", lambda _a, game=None: False)(1, game=self.game))
                if spent:
                    applied_discount += 1
                    reasons.append("Ancestral Crest: -1CP (spent 1YP, used)")
                    self._mark_ability_used_turn("ANCESTRAL_CREST")
                    event_system = getattr(self.game, "event_system", None) if self.game is not None else None
                    if event_system is not None:
                        event_system.publish(
                            "prioritised_efficiency_updated",
                            player=self,
                            game=self.game,
                            delta=-1,
                            mode=getattr(pe, "mode", None),
                            yield_points=int(getattr(pe, "yield_points", 0) or 0),
                            reason="Ancestral Crest",
                        )

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
            if self._unit_is_alive_or_unknown(unit) and unit.deployed:
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
                    logger.info(
                        "%s cannot draw Secondary: %s (ineligible); shuffled back into deck",
                        self.name,
                        card.name,
                    )
                else:
                    # Discard immediately and continue drawing
                    self.discarded_secondaries.append(card)
                    logger.info(
                        "%s cannot draw Secondary: %s (ineligible); discarded",
                        self.name,
                        card.name,
                    )
                continue
            # Allow cards to perform on-draw initialization
            if hasattr(card, 'on_draw'):
                card.on_draw(game, self)
            self.active_secondaries.append(card)
            logger.info("%s drew Secondary: %s", self.name, card.name)

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
