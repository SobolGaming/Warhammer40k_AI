# This is the player that gets put onto a Battlefield and has an Army

import logging
import uuid
from typing import Any
from .army import Army
from ..units.unit import Unit
from ..battlefield.map import Objective
from .player_control import PlayerControl, PlayerControlMixin
from .player_missions import PlayerMissionMixin, initialize_player_mission_state
from .player_resources import PlayerResourceMixin, initialize_player_resource_state
from .player_scoring import PlayerScoringMixin, initialize_player_scoring_state
from .player_ui import DEFAULT_PLAYER_UI_COLOR_PALETTE, PlayerUIMixin, initialize_player_ui_state
from warhammer40k_ai.utility.calcs import get_dist
from ..utility.entity_ids import get_entity_id

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

class Player(PlayerControlMixin, PlayerResourceMixin, PlayerScoringMixin, PlayerMissionMixin, PlayerUIMixin):
    def __init__(self, name: str, control: PlayerControl = PlayerControl.LOCAL, army: Army = None):
        self._id = str(uuid.uuid4())
        self.name = name
        if control not in (PlayerControl.LOCAL, PlayerControl.REMOTE):
            raise ValueError(f"Invalid player control: {control}")
        self.control = control
        self.round: int = 0
        self.army: Army = army
        initialize_player_resource_state(self)
        initialize_player_scoring_state(self)
        initialize_player_mission_state(self)
        # Set the player reference on the army
        if self.army:
            self.army.set_player(self)

        initialize_player_ui_state(self)

    @property
    def id(self) -> str:
        return self._id

    def _resolve_opponent_cp_gain_reactions(
        self,
        *,
        opponent_player,
        opponent_gain: int,
        opponent_reason: str,
    ) -> None:
        specs = self._opponent_cp_gain_reaction_specs()
        if not specs:
            return
        from ..utility.dice import get_roll
        from ..utility.event_bus import append_action, append_dice

        game = getattr(self, "game", None)
        event_system = getattr(game, "event_system", None) if game is not None else None
        trigger_player = getattr(opponent_player, "name", "Opponent")
        trigger_reason = str(opponent_reason or "").strip() or "ability"

        for spec in specs:
            try:
                roll_min = int(spec.get("roll_min", 2) or 2)
            except (TypeError, ValueError):
                roll_min = 2
            try:
                cp_gain = int(spec.get("cp_gain", 1) or 1)
            except (TypeError, ValueError):
                cp_gain = 1
            if roll_min <= 0 or cp_gain <= 0:
                continue
            source_name = str(spec.get("name", "") or "Opponent CP Gain Reaction").strip() or "Opponent CP Gain Reaction"
            roll = get_roll("D6")
            gained = 0
            if int(roll) >= int(roll_min):
                gained = int(self.gain_command_points(cp_gain, reason=source_name, source="ability") or 0)

            append_dice(
                self,
                f"{source_name} roll: {int(roll)} (vs {int(roll_min)}+) after {trigger_player} gained CP ({int(opponent_gain)}).",
            )
            if gained > 0:
                append_action(self, f"{source_name}: gained {int(gained)} CP (trigger: {trigger_reason}).")
            else:
                append_action(self, f"{source_name}: no CP gained (trigger: {trigger_reason}).")
            if event_system is not None:
                event_system.publish(
                    "command_points_gained",
                    player=self,
                    amount=int(gained or 0),
                    reason=source_name,
                    source="opponent_cp_gain_reaction",
                    triggering_player=opponent_player,
                    triggering_reason=trigger_reason,
                    triggering_cp_gain=int(opponent_gain or 0),
                    roll=int(roll),
                    roll_min=int(roll_min),
                )
            if gained > 0:
                break

    def _maybe_trigger_opponent_cp_gain_reactions(
        self,
        *,
        gained: int,
        reason: str,
        source: str,
        is_normal_command_phase_gain: bool,
    ) -> None:
        if int(gained or 0) <= 0:
            return
        if not self._cp_gain_source_counts_as_ability(
            source=source,
            reason=reason,
            is_normal_command_phase_gain=bool(is_normal_command_phase_gain),
        ):
            return
        opponent = self._get_opponent_player()
        if opponent is None or opponent is self:
            return
        resolve = getattr(opponent, "_resolve_opponent_cp_gain_reactions", None)
        if callable(resolve):
            resolve(opponent_player=self, opponent_gain=int(gained), opponent_reason=reason)

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
                resolved_spec = dict(spec)
                resolved_spec["_cp_refund_source_kind"] = "target"
                specs.append(resolved_spec)

        army = self.get_army()
        if army is not None:
            seen_source_roots: set[str] = set()
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    source_root = unit.get_attached_unit_root()
                except Exception:
                    source_root = unit
                source_root_id = str(get_entity_id(source_root) or "")
                if not source_root_id or source_root_id in seen_source_roots:
                    continue
                seen_source_roots.add(source_root_id)
                if not self._unit_is_alive_or_unknown(source_root):
                    continue
                sr = getattr(source_root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                for spec in list(sr.get("stratagem_target_cp_refund_aura", []) or []):
                    if not isinstance(spec, dict):
                        continue
                    source_model_id = str(spec.get("source_model_id", "") or "").strip()
                    if source_model_id and not self._unit_has_alive_model_id(source_root, source_model_id):
                        continue
                    kw = str(spec.get("keyword", "") or "").strip().upper()
                    if kw and not self._unit_has_keyword(target_unit, kw):
                        continue
                    try:
                        aura_range = float(spec.get("range", 0) or 0)
                    except (TypeError, ValueError):
                        aura_range = 0.0
                    if aura_range <= 0.0:
                        continue
                    if not self._source_model_within_range_for_ability(
                        source_root,
                        target_unit,
                        float(aura_range),
                        str(spec.get("name", "") or ""),
                        source_model_id=source_model_id,
                    ):
                        continue
                    resolved_spec = dict(spec)
                    resolved_spec["_cp_refund_source_kind"] = "aura"
                    specs.append(resolved_spec)

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
            source_model_id = ""
            key = (
                int(spec.get("roll_min", 0) or 0),
                int(spec.get("cp_gain", 0) or 0),
                str(spec.get("name", "") or "").strip().lower(),
                int(bonus_roll),
                str(bonus_keyword),
                int(bonus_range),
                str(spec.get("roll_bonus_if_target_has_keyword", "") or "").strip().upper(),
                bool(spec.get("roll_bonus_if_target_within_objective_range", False)),
                bool(spec.get("roll_bonus_if_source_model_within_vowed_objective", False)),
                source_model_id,
                str(spec.get("keyword", "") or "").strip().upper(),
                int(spec.get("range", 0) or 0),
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
                int(bool(item.get("roll_bonus_if_target_within_objective_range", False))),
                int(bool(item.get("roll_bonus_if_source_model_within_vowed_objective", False))),
                str(item.get("source_model_id", "") or "").strip(),
                str(item.get("keyword", "") or "").strip().upper(),
                int(item.get("range", 0) or 0),
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
        if not self._unit_is_alive_or_unknown(root):
            return
        specs = self._target_unit_stratagem_cp_refund_specs(root)
        if not specs:
            return
        game = getattr(self, "game", None)
        event_system = getattr(game, "event_system", None) if game is not None else None

        for spec in specs:
            try:
                from ..utility.dice import get_roll

                roll = get_roll("D6")
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
            roll_bonus_if_target_within_objective_range = bool(
                spec.get("roll_bonus_if_target_within_objective_range", False)
            )
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
            if roll_bonus_value > 0 and roll_bonus_if_target_within_objective_range:
                within_any_objective = getattr(root, "is_within_any_objective_range", None)
                if callable(within_any_objective):
                    if bool(within_any_objective(game_map=getattr(game, "map", None) if game is not None else None)):
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

    def _source_unit_ability_is_active(self, source_unit, ability_name: str) -> bool:
        name = str(ability_name or "").strip()
        if source_unit is None or not name:
            return True
        get_root = getattr(source_unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else source_unit
        if root is None:
            return False
        checker = getattr(root, "_ability_is_active", None)
        if not callable(checker):
            return True
        normalized_name = str(name).replace("\u2019", "'").strip().lower()
        matched_abilities = []
        for ability in list(getattr(root, "possible_abilities", []) or []):
            ability_name_value = str(getattr(ability, "name", "") or "")
            if ability_name_value.replace("\u2019", "'").strip().lower() == normalized_name:
                matched_abilities.append(ability)
        if not matched_abilities:
            return bool(checker(name))
        for ability in matched_abilities:
            if bool(checker(ability)):
                return True
        return False

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

    def _has_attached_decision_controller(self) -> bool:
        game = getattr(self, "game", None)
        hub = getattr(game, "decision_controller_hub", None) if game is not None else None
        controllers = getattr(hub, "_controllers", None)
        if not isinstance(controllers, list):
            return False
        for controller in list(controllers):
            handles_player = getattr(controller, "handles_player", None)
            if callable(handles_player) and bool(handles_player(getattr(self, "id", None))):
                return True
        return False

    @staticmethod
    def _default_optional_ability_name(key: str) -> str:
        words = [part for part in str(key or "").strip().split("_") if part]
        return " ".join(word.capitalize() for word in words)

    def _resolve_optional_ability_local_choice(self, key: str, context: dict) -> bool | None:
        """Consume one-shot overrides or synchronous hooks for an emitted request."""
        k = (key or "").strip().upper()
        if not k:
            return None
        overrides = getattr(self, "_next_optional_decisions", None)
        if isinstance(overrides, dict) and k in overrides:
            return bool(overrides.pop(k))
        optional_hook = getattr(self, "optional_decision_hook", None)
        if callable(optional_hook):
            return bool(optional_hook(self, k, dict(context or {})))
        hook = getattr(self, "decision_hook", None)
        if callable(hook):
            return bool(hook(self, k, dict(context or {})))
        return None

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
        if callable(getattr(self, "optional_decision_hook", None)):
            return True
        hook = getattr(self, "decision_hook", None)
        if callable(hook):
            return bool(hook(self, k, context))
        return self._has_attached_decision_controller()

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

    def _targeted_stratagem_cp_discount_blocked(self, *, target_unit, source_unit, stratagem=None) -> bool:
        if target_unit is None or source_unit is None or stratagem is None:
            return False
        stratagem_name = str(getattr(stratagem, "name", "") or "").strip().upper()
        if stratagem_name != "JOIN THE HUNT":
            return False
        try:
            if getattr(source_unit, "attached_to", None) is not target_unit:
                return False
        except Exception:
            return False
        try:
            return len(list(getattr(target_unit, "models", []) or [])) == 0
        except Exception:
            return False

    def _target_unit_has_stratagem_target_cp_discount(self, target_unit, *, stratagem=None) -> tuple[list[dict], list[str]]:
        if target_unit is None:
            return [], []
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return [], []
        members = self._attached_members(target_unit)
        names: list[str] = []
        found_specs: list[dict] = []
        for u in members:
            if self._targeted_stratagem_cp_discount_blocked(target_unit=target_unit, source_unit=u, stratagem=stratagem):
                continue
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
                if not self._source_unit_ability_is_active(u, name):
                    continue
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
                if not self._source_unit_ability_is_active(u, name):
                    continue
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

    def _preview_targeted_stratagem_cp_discount(self, *, target_unit=None, stratagem=None) -> tuple[int, list[str], list[dict]]:
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
        direct_specs, direct_names = self._target_unit_has_stratagem_target_cp_discount(
            target_unit,
            stratagem=stratagem,
        )
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

    def _webway_awl_rapid_ingress_discount_context(self, target_unit, *, stratagem_name: str = "") -> dict | None:
        if target_unit is None:
            return None
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return None
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if stratagem_key != "RAPID INGRESS":
            return None
        members = self._attached_members(target_unit)
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_webway_awl_rapid_ingress_discount", False)):
                continue
            if not self._unit_is_alive_or_unknown(u):
                continue
            configured_name = self._normalize_stratagem_name_key(
                str(sr.get("enhancement_webway_awl_stratagem_name", "") or "RAPID INGRESS")
            )
            if configured_name and configured_name != stratagem_key:
                continue
            get_bearer = getattr(u, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is None:
                continue
            alive_attr = getattr(bearer, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            return {
                "source_unit": u,
                "source": str(sr.get("enhancement_webway_awl_source", "") or "Webway Awl").strip() or "Webway Awl",
            }
        return None

    @staticmethod
    def _normalize_stratagem_name_key(stratagem_name: str) -> str:
        text = str(stratagem_name or "")
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-")
        text = text.replace("\u2013", "-").replace("\u2014", "-")
        text = " ".join(text.strip().upper().split())
        text = text.replace("-", " ")
        return " ".join(text.split())

    def _unit_is_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_is_alive_or_unknown(unit):
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
            return False
        if getattr(unit, "embarked_in", None) is not None:
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        return True

    def _unit_is_grey_knights_terminator_squad_for_gift_of_the_prescient(self, unit) -> bool:
        if unit is None:
            return False
        parent = self._target_unit_parent_army(unit)
        if parent is not None and parent is not self.get_army():
            return False
        get_root = getattr(unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else unit
        if root is None:
            return False
        name_key = self._normalize_stratagem_name_key(getattr(root, "name", "") or "")
        if "GREY KNIGHTS TERMINATOR SQUAD" in name_key:
            return True
        if "GREY KNIGHTS TERMINATOR" in name_key and "SQUAD" in name_key:
            return True
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if callable(has_any_keyword):
            for keyword in (
                "GREY KNIGHTS TERMINATOR SQUAD",
                "GREY KNIGHTS TERMINATORS",
                "GREY KNIGHTS TERMINATOR",
            ):
                if bool(has_any_keyword(keyword)):
                    return True
        keywords: list[str] = []
        keywords.extend([self._normalize_stratagem_name_key(v) for v in list(getattr(root, "keywords", []) or [])])
        keywords.extend(
            [self._normalize_stratagem_name_key(v) for v in list(getattr(root, "faction_keywords", []) or [])]
        )
        for keyword in keywords:
            if "GREY KNIGHTS TERMINATOR SQUAD" in keyword:
                return True
            if "GREY KNIGHTS TERMINATOR" in keyword and "SQUAD" in keyword:
                return True
        return False

    def _gift_of_the_prescient_discount_context(self, target_unit, *, stratagem_name: str = "") -> dict | None:
        if target_unit is None:
            return None
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return None
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if not stratagem_key:
            return None
        army = self.get_army()
        ia_mgr = getattr(army, "imperial_agents_detachments", None) if army is not None else None
        is_ordo_malleus_fn = getattr(ia_mgr, "is_ordo_malleus_daemon_hunters", None) if ia_mgr is not None else None
        if not bool(callable(is_ordo_malleus_fn) and is_ordo_malleus_fn()):
            return None
        get_target_root = getattr(target_unit, "get_attached_unit_root", None)
        target_root = get_target_root() if callable(get_target_root) else target_unit
        if target_root is None:
            return None
        target_name_key = self._normalize_stratagem_name_key(getattr(target_root, "name", "") or "")
        roots: list[object] = []
        seen_root_ids: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            get_root = getattr(unit, "get_attached_unit_root", None)
            root = get_root() if callable(get_root) else unit
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if root_id and root_id in seen_root_ids:
                continue
            if root_id:
                seen_root_ids.add(root_id)
            roots.append(root)
        roots.sort(key=lambda item: str(get_entity_id(item) or ""))

        for root in roots:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_ordo_malleus_gift_of_the_prescient", False)):
                continue
            if not self._unit_is_alive_or_unknown(root):
                continue
            requires_bearer_on_battlefield = bool(
                sr.get("enhancement_ordo_malleus_gift_of_the_prescient_requires_bearer_on_battlefield", True)
            )
            if requires_bearer_on_battlefield and not self._unit_is_on_battlefield(root):
                continue
            get_bearer = getattr(root, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is None:
                continue
            alive_attr = getattr(bearer, "is_alive", True)
            bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not bearer_alive:
                continue
            usage_key = str(
                sr.get("enhancement_ordo_malleus_gift_of_the_prescient_usage_key", "")
                or "gift_of_the_prescient_rapid_ingress"
            ).strip().lower()
            if not usage_key:
                usage_key = "gift_of_the_prescient_rapid_ingress"
            has_used = getattr(root, "has_used_unit_once_per_battle", None)
            if callable(has_used) and bool(has_used(usage_key)):
                continue
            configured_names: set[str] = set()
            for value in list(sr.get("enhancement_ordo_malleus_gift_of_the_prescient_stratagem_names", []) or []):
                name_key = self._normalize_stratagem_name_key(value)
                if name_key:
                    configured_names.add(name_key)
            if configured_names and stratagem_key not in configured_names:
                continue

            configured_patterns: list[str] = []
            for value in list(
                sr.get("enhancement_ordo_malleus_gift_of_the_prescient_required_target_unit_name_patterns", []) or []
            ):
                pattern_key = self._normalize_stratagem_name_key(value)
                if pattern_key:
                    configured_patterns.append(pattern_key)
            target_matches = False
            if configured_patterns:
                for pattern in configured_patterns:
                    if pattern in target_name_key or target_name_key in pattern:
                        target_matches = True
                        break
                if not target_matches:
                    target_matches = self._unit_is_grey_knights_terminator_squad_for_gift_of_the_prescient(target_root)
            else:
                target_matches = self._unit_is_grey_knights_terminator_squad_for_gift_of_the_prescient(target_root)
            if not target_matches:
                continue

            try:
                min_distance = float(
                    sr.get("enhancement_ordo_malleus_gift_of_the_prescient_deep_strike_min_distance", 3.0) or 3.0
                )
            except (TypeError, ValueError):
                min_distance = 3.0
            if min_distance <= 0.0:
                min_distance = 3.0
            source = str(
                sr.get("enhancement_ordo_malleus_gift_of_the_prescient_source", "") or "Gift of the Prescient"
            ).strip() or "Gift of the Prescient"
            expires_phase = str(
                sr.get("enhancement_ordo_malleus_gift_of_the_prescient_expires_phase", "") or "MOVEMENT_PHASE"
            ).strip().upper()
            if not expires_phase:
                expires_phase = "MOVEMENT_PHASE"
            return {
                "source_unit": root,
                "usage_key": usage_key,
                "source": source,
                "deep_strike_min_distance": float(min_distance),
                "expires_phase": expires_phase,
            }
        return None

    def _homing_beacon_rapid_ingress_discount_context(self, target_unit, *, stratagem_name: str = "") -> dict | None:
        if target_unit is None:
            return None
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return None
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if stratagem_key != "RAPID INGRESS":
            return None
        army = self.get_army()
        if army is None:
            return None
        roots: list[object] = []
        seen_root_ids: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            get_root = getattr(unit, "get_attached_unit_root", None)
            root = get_root() if callable(get_root) else unit
            if root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if root_id and root_id in seen_root_ids:
                continue
            if root_id:
                seen_root_ids.add(root_id)
            roots.append(root)
        roots.sort(key=lambda item: str(get_entity_id(item) or ""))

        for root in roots:
            can_use = getattr(root, "can_use_homing_beacon_rapid_ingress", None)
            if not callable(can_use):
                continue
            if not bool(can_use(self.game, stratagem_name=stratagem_key)):
                continue
            get_rule = getattr(root, "get_homing_beacon_rapid_ingress_rule", None)
            rule = get_rule() if callable(get_rule) else None
            if not isinstance(rule, dict):
                continue
            source = str(rule.get("source", "") or "Homing Beacon").strip() or "Homing Beacon"
            usage_key = str(rule.get("usage_key", "") or rule.get("ability_key", "") or "").strip().lower()
            if not usage_key:
                usage_key = "homing_beacon_rapid_ingress"
            try:
                anchor_distance = float(rule.get("anchor_distance", 3.0) or 3.0)
            except (TypeError, ValueError):
                anchor_distance = 3.0
            if anchor_distance <= 0.0:
                anchor_distance = 3.0
            try:
                min_enemy_distance = float(rule.get("deep_strike_min_distance", 9.0) or 9.0)
            except (TypeError, ValueError):
                min_enemy_distance = 9.0
            if min_enemy_distance <= 0.0:
                min_enemy_distance = 9.0
            return {
                "source_unit": root,
                "source_unit_id": str(get_entity_id(root) or ""),
                "source": source,
                "usage_key": usage_key,
                "anchor_mode": str(rule.get("anchor_mode", "") or "source_unit"),
                "anchor_distance": float(anchor_distance),
                "deep_strike_min_distance": float(min_enemy_distance),
            }
        return None

    def _teleport_homer_rapid_ingress_discount_context(self, target_unit, *, stratagem_name: str = "") -> dict | None:
        if target_unit is None:
            return None
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return None
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if stratagem_key != "RAPID INGRESS":
            return None
        get_root = getattr(target_unit, "get_attached_unit_root", None)
        root = get_root() if callable(get_root) else target_unit
        if root is None:
            return None
        can_use = getattr(root, "can_use_teleport_homer_rapid_ingress", None)
        if not callable(can_use) or not bool(can_use(self.game, stratagem_name=stratagem_key)):
            return None
        get_rule = getattr(root, "get_teleport_homer_rapid_ingress_rule", None)
        rule = get_rule() if callable(get_rule) else None
        if not isinstance(rule, dict):
            return None
        marker_point = None
        get_marker = getattr(root, "get_teleport_homer_marker_point", None)
        if callable(get_marker):
            marker_point = get_marker()
        if not isinstance(marker_point, (list, tuple)) or len(marker_point) < 2:
            return None
        try:
            marker_x = float(marker_point[0])
            marker_y = float(marker_point[1])
            marker_z = float(marker_point[2]) if len(marker_point) > 2 else 0.0
        except (TypeError, ValueError):
            return None

        source = str(rule.get("source", "") or "Teleport Homer").strip() or "Teleport Homer"
        usage_key = str(rule.get("usage_key", "") or rule.get("ability_key", "") or "").strip().lower()
        if not usage_key:
            usage_key = "teleport_homer_rapid_ingress"
        try:
            anchor_distance = float(rule.get("anchor_distance", 3.0) or 3.0)
        except (TypeError, ValueError):
            anchor_distance = 3.0
        if anchor_distance <= 0.0:
            anchor_distance = 3.0
        try:
            min_enemy_distance = float(rule.get("deep_strike_min_distance", 9.0) or 9.0)
        except (TypeError, ValueError):
            min_enemy_distance = 9.0
        if min_enemy_distance <= 0.0:
            min_enemy_distance = 9.0
        return {
            "source_unit": root,
            "source_unit_id": str(get_entity_id(root) or ""),
            "source": source,
            "usage_key": usage_key,
            "anchor_mode": str(rule.get("anchor_mode", "") or "marker_point"),
            "anchor_distance": float(anchor_distance),
            "anchor_point": [float(marker_x), float(marker_y), float(marker_z)],
            "deep_strike_min_distance": float(min_enemy_distance),
        }

    def _preview_gift_of_the_prescient_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        stratagem_key = self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or "")
        if stratagem_key != "RAPID INGRESS":
            return 0
        context = self._gift_of_the_prescient_discount_context(target_unit, stratagem_name=stratagem_key)
        if context is None:
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _target_unit_can_use_fleetmaster_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if not stratagem_key:
            return False
        battle_round = self._battle_round()
        if battle_round <= 0:
            return False
        usage_key = "FLEETMASTER_FREE_STRATAGEM"
        if int(self._ability_used_battle_round.get(usage_key, 0) or 0) == battle_round:
            return False
        army = self.get_army()
        ia_mgr = getattr(army, "imperial_agents_detachments", None) if army is not None else None
        if ia_mgr is None or not bool(getattr(ia_mgr, "is_imperialis_fleet", lambda: False)()):
            return False
        members = self._attached_members(target_unit)
        for u in members:
            sr = getattr(u, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("enhancement_imperialis_fleet_fleetmaster", False)):
                continue
            if not self._unit_is_alive_or_unknown(u):
                continue
            configured_usage_key = str(
                sr.get("enhancement_imperialis_fleet_fleetmaster_usage_key", "") or ""
            ).strip().upper()
            if configured_usage_key:
                usage_key = configured_usage_key
                if int(self._ability_used_battle_round.get(usage_key, 0) or 0) == battle_round:
                    continue
            configured_names: set[str] = set()
            for value in list(sr.get("enhancement_imperialis_fleet_fleetmaster_stratagem_names", []) or []):
                configured_name = self._normalize_stratagem_name_key(value)
                if configured_name:
                    configured_names.add(configured_name)
            if configured_names and stratagem_key not in configured_names:
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

    def _target_unit_can_use_hypersensory_array_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if stratagem_key not in ("RAPID INGRESS", "HEROIC INTERVENTION"):
            return False
        fn = getattr(target_unit, "can_use_hypersensory_array_stratagem_discount", None)
        if not callable(fn):
            return False
        if not bool(fn(self.game, stratagem_name=stratagem_key)):
            return False
        get_rule = getattr(target_unit, "get_hypersensory_array_stratagem_discount_rule", None)
        rule = get_rule() if callable(get_rule) else None
        usage_key = str((rule or {}).get("usage_key", "") or "HYPERSENSORY_ARRAY_FREE_STRATAGEM").strip().upper()
        battle_round = self._battle_round()
        if battle_round <= 0:
            return False
        if int(self._ability_used_battle_round.get(usage_key, 0) or 0) == battle_round:
            return False
        return True

    def _target_unit_can_use_synaptic_strategy_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if stratagem_key != "RAPID INGRESS":
            return False
        fn = getattr(target_unit, "can_use_synaptic_strategy_stratagem_discount", None)
        if not callable(fn):
            return False
        return bool(fn(self.game, stratagem_name=stratagem_key))

    def _target_unit_can_use_infernal_fulgurite_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if stratagem_key != "RAPID INGRESS":
            return False
        fn = getattr(target_unit, "can_use_infernal_fulgurite_stratagem_discount", None)
        if not callable(fn):
            return False
        return bool(fn(self.game, stratagem_name=stratagem_key))

    def _target_unit_can_use_blackwing_mantle_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if stratagem_key not in ("RAPID INGRESS", "HEROIC INTERVENTION"):
            return False
        fn = getattr(target_unit, "can_use_blackwing_mantle_stratagem_discount", None)
        if not callable(fn):
            return False
        return bool(fn(self.game, stratagem_name=stratagem_key))

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

    def _target_unit_can_use_visions_of_heresy_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_visions_of_heresy_stratagem_discount", None)
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

    def _target_unit_can_use_precursive_judgement_overwatch(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_precursive_judgement_overwatch", None)
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

    def _target_unit_can_use_datasheet_overwatch_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_datasheet_overwatch_stratagem_discount", None)
        if callable(fn):
            return bool(fn(self.game, stratagem_name=stratagem_name))
        return False

    def _target_unit_can_use_flare_launcher_smokescreen_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_flare_launcher_smokescreen_discount", None)
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

    def _target_unit_can_use_unit_contains_heroic_intervention(self, target_unit) -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_unit_contains_heroic_intervention", None)
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

    def _target_unit_can_use_master_of_prescience_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_master_of_prescience_stratagem_discount", None)
        if callable(fn):
            return bool(fn(self.game, stratagem_name=stratagem_name))
        return False

    def _target_unit_can_use_eye_of_the_augurium_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        fn = getattr(target_unit, "can_use_eye_of_the_augurium_stratagem_discount", None)
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

    def _target_unit_can_use_instinctive_defence_heroic_intervention(self, target_unit) -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        fn = getattr(target_unit, "can_use_instinctive_defence_heroic_intervention", None)
        if callable(fn):
            return bool(fn(self.game, stratagem_name="HEROIC INTERVENTION"))
        return False

    def _adaptive_reprisal_discount_context(self, target_unit, *, stratagem_name: str = "") -> dict | None:
        if target_unit is None:
            return None
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return None
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if stratagem_key != "HEROIC INTERVENTION":
            return None
        if not self._unit_has_keyword(target_unit, "GENESTEALER CULTS"):
            return None
        get_target_root = getattr(target_unit, "get_attached_unit_root", None)
        target_root = get_target_root() if callable(get_target_root) else target_unit
        if target_root is None:
            return None
        if not self._unit_is_alive_or_unknown(target_root):
            return None
        army = self.get_army()
        if army is None:
            return None

        from warhammer40k_ai.utility.aura_utils import model_within_range_of_unit

        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_adaptive_reprisal")):
                continue
            get_root = getattr(unit, "get_attached_unit_root", None)
            source_root = get_root() if callable(get_root) else unit
            if source_root is None:
                continue
            if not self._unit_is_alive_or_unknown(source_root):
                continue
            requires_bearer_on_battlefield = bool(
                sr.get("enhancement_adaptive_reprisal_requires_bearer_on_battlefield", True)
            )
            if requires_bearer_on_battlefield and not self._unit_is_on_battlefield(source_root):
                continue
            usage_key = str(
                sr.get("enhancement_adaptive_reprisal_usage_key", "") or "ADAPTIVE_REPRISAL_HEROIC_INTERVENTION"
            ).strip().upper()
            if not usage_key:
                usage_key = "ADAPTIVE_REPRISAL_HEROIC_INTERVENTION"
            if self._ability_used_this_turn(usage_key):
                continue
            configured_names = {
                self._normalize_stratagem_name_key(value)
                for value in list(sr.get("enhancement_adaptive_reprisal_stratagems", ()) or ())
                if self._normalize_stratagem_name_key(value)
            }
            if configured_names and stratagem_key not in configured_names:
                continue
            get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is None:
                get_bearer_root = getattr(source_root, "_get_enhancement_bearer_model", None)
                bearer = get_bearer_root() if callable(get_bearer_root) else None
            if bearer is None:
                continue
            alive_attr = getattr(bearer, "is_alive", True)
            bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not bearer_alive:
                continue
            try:
                aura_range = float(sr.get("enhancement_adaptive_reprisal_range", 9.0) or 9.0)
            except (TypeError, ValueError):
                aura_range = 9.0
            if aura_range <= 0.0:
                aura_range = 9.0
            if not model_within_range_of_unit(bearer, target_root, aura_range, use_attached_aggregate=True):
                continue
            source_name = str(sr.get("enhancement_adaptive_reprisal_source", "") or "Adaptive Reprisal").strip()
            if not source_name:
                source_name = "Adaptive Reprisal"
            return {
                "source_unit": source_root,
                "source": source_name,
                "usage_key": usage_key,
                "range": float(aura_range),
            }
        return None

    def _target_unit_can_use_adaptive_reprisal_heroic_intervention(self, target_unit, *, stratagem_name: str = "") -> bool:
        return self._adaptive_reprisal_discount_context(target_unit, stratagem_name=stratagem_name) is not None

    def _vengeful_tread_discount_context(self, target_unit, *, stratagem_name: str = "") -> dict | None:
        if target_unit is None:
            return None
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return None
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if stratagem_key != "TANK SHOCK":
            return None
        get_target_root = getattr(target_unit, "get_attached_unit_root", None)
        target_root = get_target_root() if callable(get_target_root) else target_unit
        if target_root is None:
            return None
        if not self._unit_is_alive_or_unknown(target_root):
            return None
        army = self.get_army()
        if army is None:
            return None
        target_root_id = str(get_entity_id(target_root) or "")
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_vengeful_tread")):
                continue
            get_root = getattr(unit, "get_attached_unit_root", None)
            source_root = get_root() if callable(get_root) else unit
            if source_root is None:
                continue
            if not self._unit_is_alive_or_unknown(source_root):
                continue
            requires_bearer_on_battlefield = bool(
                sr.get("enhancement_vengeful_tread_requires_bearer_on_battlefield", True)
            )
            if requires_bearer_on_battlefield and not self._unit_is_on_battlefield(source_root):
                continue
            source_root_id = str(get_entity_id(source_root) or "")
            if source_root is not target_root and (not source_root_id or source_root_id != target_root_id):
                continue
            usage_key = str(sr.get("enhancement_vengeful_tread_usage_key", "") or "VENGEFUL_TREAD_TANK_SHOCK").strip().upper()
            if not usage_key:
                usage_key = "VENGEFUL_TREAD_TANK_SHOCK"
            if self._ability_used_this_turn(usage_key):
                continue
            configured_names = {
                self._normalize_stratagem_name_key(value)
                for value in list(sr.get("enhancement_vengeful_tread_stratagems", ()) or ())
                if self._normalize_stratagem_name_key(value)
            }
            if configured_names and stratagem_key not in configured_names:
                continue
            get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is None:
                get_bearer_root = getattr(source_root, "_get_enhancement_bearer_model", None)
                bearer = get_bearer_root() if callable(get_bearer_root) else None
            if bearer is None:
                continue
            alive_attr = getattr(bearer, "is_alive", True)
            bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not bearer_alive:
                continue
            source_name = str(sr.get("enhancement_vengeful_tread_source", "") or "Vengeful Tread").strip()
            if not source_name:
                source_name = "Vengeful Tread"
            return {
                "source_unit": source_root,
                "source": source_name,
                "usage_key": usage_key,
            }
        return None

    def _martial_tuition_discount_context(self, target_unit, *, stratagem_name: str = "") -> dict | None:
        if target_unit is None:
            return None
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return None
        stratagem_key = self._normalize_stratagem_name_key(stratagem_name)
        if stratagem_key != "COUNTER OFFENSIVE":
            return None
        get_target_root = getattr(target_unit, "get_attached_unit_root", None)
        target_root = get_target_root() if callable(get_target_root) else target_unit
        if target_root is None:
            return None
        if not self._unit_is_alive_or_unknown(target_root):
            return None
        mgr = getattr(self, "stratagems", None)
        used_this_phase = getattr(mgr, "_used_stratagems_this_phase", set()) if mgr is not None else set()
        if isinstance(used_this_phase, set) and "COUNTER-OFFENSIVE" in used_this_phase:
            return None
        army = self.get_army()
        if army is None:
            return None
        target_root_id = str(get_entity_id(target_root) or "")
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_martial_tuition")):
                continue
            get_root = getattr(unit, "get_attached_unit_root", None)
            source_root = get_root() if callable(get_root) else unit
            if source_root is None:
                continue
            if not self._unit_is_alive_or_unknown(source_root):
                continue
            requires_bearer_on_battlefield = bool(
                sr.get("enhancement_martial_tuition_requires_bearer_on_battlefield", True)
            )
            if requires_bearer_on_battlefield and not self._unit_is_on_battlefield(source_root):
                continue
            usage_key = str(
                sr.get("enhancement_martial_tuition_usage_key", "") or "MARTIAL_TUITION_COUNTER_OFFENSIVE"
            ).strip().upper()
            if not usage_key:
                usage_key = "MARTIAL_TUITION_COUNTER_OFFENSIVE"
            if self._ability_used_this_turn(usage_key):
                continue
            configured_names = {
                self._normalize_stratagem_name_key(value)
                for value in list(sr.get("enhancement_martial_tuition_stratagems", ()) or ())
                if self._normalize_stratagem_name_key(value)
            }
            if configured_names and stratagem_key not in configured_names:
                continue
            required_keyword = str(
                sr.get("enhancement_martial_tuition_required_target_keyword", "") or "ARMIGER"
            ).strip().upper()
            if required_keyword and not self._unit_has_keyword(target_root, required_keyword):
                continue
            try:
                min_targets = int(sr.get("enhancement_martial_tuition_required_min_bondsman_targets", 2) or 2)
            except (TypeError, ValueError):
                min_targets = 2
            min_targets = max(1, min_targets)
            get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
            bearer = get_bearer() if callable(get_bearer) else None
            if bearer is None:
                get_bearer_root = getattr(source_root, "_get_enhancement_bearer_model", None)
                bearer = get_bearer_root() if callable(get_bearer_root) else None
            if bearer is None:
                continue
            alive_attr = getattr(bearer, "is_alive", True)
            bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not bearer_alive:
                continue
            source_root_id = str(get_entity_id(source_root) or "")
            if not source_root_id:
                continue
            bondsman_targets: list = []
            seen_target_keys: set[str] = set()
            for candidate in list(getattr(army, "units", []) or []):
                if candidate is None:
                    continue
                get_candidate_root = getattr(candidate, "get_attached_unit_root", None)
                candidate_root = get_candidate_root() if callable(get_candidate_root) else candidate
                if candidate_root is None:
                    continue
                candidate_id = str(get_entity_id(candidate_root) or "")
                dedupe_key = candidate_id or f"obj:{id(candidate_root)}"
                if dedupe_key in seen_target_keys:
                    continue
                seen_target_keys.add(dedupe_key)
                if not self._unit_is_alive_or_unknown(candidate_root):
                    continue
                candidate_sr = getattr(candidate_root, "special_rules", None)
                if not isinstance(candidate_sr, dict) or not bool(candidate_sr.get("bondsman_active")):
                    continue
                bondsman_source_unit_id = str(candidate_sr.get("bondsman_source_unit_id", "") or "").strip()
                if bondsman_source_unit_id != source_root_id:
                    continue
                if required_keyword and not self._unit_has_keyword(candidate_root, required_keyword):
                    continue
                bondsman_targets.append(candidate_root)
            if len(bondsman_targets) < min_targets:
                continue
            target_is_valid = False
            for candidate_root in bondsman_targets:
                candidate_id = str(get_entity_id(candidate_root) or "")
                if candidate_root is target_root:
                    target_is_valid = True
                    break
                if target_root_id and candidate_id and target_root_id == candidate_id:
                    target_is_valid = True
                    break
            if not target_is_valid:
                continue
            source_name = str(sr.get("enhancement_martial_tuition_source", "") or "Martial Tuition").strip()
            if not source_name:
                source_name = "Martial Tuition"
            return {
                "source_unit": source_root,
                "source": source_name,
                "usage_key": usage_key,
                "required_keyword": required_keyword,
                "min_targets": int(min_targets),
            }
        return None

    def _target_unit_can_use_vengeful_tread_tank_shock(self, target_unit, *, stratagem_name: str = "") -> bool:
        return self._vengeful_tread_discount_context(target_unit, stratagem_name=stratagem_name) is not None

    def _target_unit_can_use_martial_tuition_counter_offensive(self, target_unit, *, stratagem_name: str = "") -> bool:
        return self._martial_tuition_discount_context(target_unit, stratagem_name=stratagem_name) is not None

    def _target_unit_can_use_pheromone_trail_rapid_ingress(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        fn = getattr(target_unit, "can_use_pheromone_trail_rapid_ingress", None)
        if callable(fn):
            return bool(fn(self.game, stratagem_name=stratagem_name))
        return False

    def _target_unit_can_use_homing_beacon_rapid_ingress(self, target_unit, *, stratagem_name: str = "") -> bool:
        return self._homing_beacon_rapid_ingress_discount_context(
            target_unit,
            stratagem_name=stratagem_name,
        ) is not None

    def _target_unit_can_use_teleport_homer_rapid_ingress(self, target_unit, *, stratagem_name: str = "") -> bool:
        return self._teleport_homer_rapid_ingress_discount_context(
            target_unit,
            stratagem_name=stratagem_name,
        ) is not None

    def _target_unit_can_use_primed_and_ready_grenade(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        # Datasheet wording allows selecting one model/unit with this ability in your Shooting phase.
        # We treat this as one Primed and Ready usage per phase across the player's army.
        if self._ability_used_this_phase("PRIMED_AND_READY_GRENADE"):
            return False
        fn = getattr(target_unit, "can_use_primed_and_ready_grenade", None)
        if not callable(fn):
            return False
        if not bool(fn(self.game, stratagem_name=stratagem_name)):
            return False
        mgr = getattr(self, "stratagems", None)
        used_targets = getattr(mgr, "_grenade_units_this_phase", set()) if mgr is not None else set()
        if isinstance(used_targets, set):
            try:
                get_root = getattr(target_unit, "get_attached_unit_root", None)
                target_root = get_root() if callable(get_root) else target_unit
            except Exception:
                target_root = target_unit
            target_id = str(get_entity_id(target_root) or "")
            if target_id and target_id in used_targets:
                return False
        return True

    def _target_unit_can_use_grenadiers_grenade(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        fn = getattr(target_unit, "can_use_grenadiers_grenade", None)
        if not callable(fn):
            return False
        return bool(fn(self.game, stratagem_name=stratagem_name))

    def _target_unit_can_use_datasheet_command_reroll_stratagem_discount(self, target_unit, *, stratagem_name: str = "") -> bool:
        if target_unit is None:
            return False
        parent = self._target_unit_parent_army(target_unit)
        if parent is not None and parent is not self.get_army():
            return False
        fn = getattr(target_unit, "can_use_datasheet_command_reroll_stratagem_discount", None)
        if not callable(fn):
            return False
        return bool(fn(self.game, stratagem_name=stratagem_name))

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

    def _preview_visions_of_heresy_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name not in ("HEROIC INTERVENTION", "OVERWATCH", "FIRE OVERWATCH"):
            return 0
        if not self._target_unit_can_use_visions_of_heresy_stratagem_discount(target_unit, stratagem_name=name):
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

    def _preview_precursive_judgement_overwatch_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name not in ("OVERWATCH", "FIRE OVERWATCH"):
            return 0
        if not self._target_unit_can_use_precursive_judgement_overwatch(target_unit, stratagem_name=name):
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

    def _preview_datasheet_overwatch_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name not in ("OVERWATCH", "FIRE OVERWATCH"):
            return 0
        if not self._target_unit_can_use_datasheet_overwatch_stratagem_discount(target_unit, stratagem_name=name):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_flare_launcher_smokescreen_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name != "SMOKESCREEN":
            return 0
        if not self._target_unit_can_use_flare_launcher_smokescreen_discount(target_unit, stratagem_name=name):
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

    def _preview_unit_contains_heroic_intervention_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name = str(getattr(stratagem, "name", "") or "").strip().lower()
        if name != "heroic intervention":
            return 0
        if not self._target_unit_can_use_unit_contains_heroic_intervention(target_unit):
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

    def _preview_master_of_prescience_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u not in (
            "HEROIC INTERVENTION",
            "COUNTER-OFFENSIVE",
            "COUNTER OFFENSIVE",
            "OVERWATCH",
            "FIRE OVERWATCH",
            "GO TO GROUND",
        ):
            return 0
        if not self._target_unit_can_use_master_of_prescience_stratagem_discount(target_unit, stratagem_name=name_u):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_eye_of_the_augurium_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u not in ("OVERWATCH", "FIRE OVERWATCH", "HEROIC INTERVENTION"):
            return 0
        if not self._target_unit_can_use_eye_of_the_augurium_stratagem_discount(target_unit, stratagem_name=name_u):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_fleetmaster_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        stratagem_key = self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or "")
        if stratagem_key not in ("VIOLENT ACQUISITION", "MASTERS OF THE VOID", "CLOSE QUARTERS BARRAGE"):
            return 0
        if not self._target_unit_can_use_fleetmaster_stratagem_discount(target_unit, stratagem_name=stratagem_key):
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

    def _preview_webway_awl_rapid_ingress_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        stratagem_key = self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or "")
        if stratagem_key != "RAPID INGRESS":
            return 0
        if self._webway_awl_rapid_ingress_discount_context(
            target_unit,
            stratagem_name=stratagem_key,
        ) is None:
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

    def _preview_hypersensory_array_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u not in ("RAPID INGRESS", "HEROIC INTERVENTION"):
            return 0
        if not self._target_unit_can_use_hypersensory_array_stratagem_discount(target_unit, stratagem_name=name_u):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_synaptic_strategy_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u != "RAPID INGRESS":
            return 0
        if not self._target_unit_can_use_synaptic_strategy_stratagem_discount(target_unit, stratagem_name=name_u):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_infernal_fulgurite_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u != "RAPID INGRESS":
            return 0
        if not self._target_unit_can_use_infernal_fulgurite_stratagem_discount(target_unit, stratagem_name=name_u):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_blackwing_mantle_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u not in ("RAPID INGRESS", "HEROIC INTERVENTION"):
            return 0
        if not self._target_unit_can_use_blackwing_mantle_stratagem_discount(target_unit, stratagem_name=name_u):
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

    def _preview_instinctive_defence_heroic_intervention_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u != "HEROIC INTERVENTION":
            return 0
        if not self._target_unit_can_use_instinctive_defence_heroic_intervention(target_unit):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_adaptive_reprisal_heroic_intervention_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        stratagem_key = self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or "")
        if stratagem_key != "HEROIC INTERVENTION":
            return 0
        if self._adaptive_reprisal_discount_context(target_unit, stratagem_name=stratagem_key) is None:
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_vengeful_tread_tank_shock_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        stratagem_key = self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or "")
        if stratagem_key != "TANK SHOCK":
            return 0
        if self._vengeful_tread_discount_context(target_unit, stratagem_name=stratagem_key) is None:
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_martial_tuition_counter_offensive_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        stratagem_key = self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or "")
        if stratagem_key != "COUNTER OFFENSIVE":
            return 0
        if self._martial_tuition_discount_context(target_unit, stratagem_name=stratagem_key) is None:
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_pheromone_trail_rapid_ingress_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u != "RAPID INGRESS":
            return 0
        if not self._target_unit_can_use_pheromone_trail_rapid_ingress(target_unit, stratagem_name=name_u):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_homing_beacon_rapid_ingress_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u != "RAPID INGRESS":
            return 0
        if self._homing_beacon_rapid_ingress_discount_context(
            target_unit,
            stratagem_name=name_u,
        ) is None:
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_teleport_homer_rapid_ingress_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u != "RAPID INGRESS":
            return 0
        if self._teleport_homer_rapid_ingress_discount_context(
            target_unit,
            stratagem_name=name_u,
        ) is None:
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_primed_and_ready_grenade_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or "")
        if name_u != "GRENADE":
            return 0
        if not self._target_unit_can_use_primed_and_ready_grenade(target_unit, stratagem_name=name_u):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_grenadiers_grenade_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or "")
        if name_u != "GRENADE":
            return 0
        if not self._target_unit_can_use_grenadiers_grenade(target_unit, stratagem_name=name_u):
            return 0
        base = int(getattr(stratagem, "cp_cost", 0) or 0)
        return max(0, base)

    def _preview_datasheet_command_reroll_discount(self, *, stratagem=None, target_unit=None) -> int:
        if stratagem is None or target_unit is None:
            return 0
        name_u = self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or "")
        if name_u not in ("COMMAND RE ROLL", "COMMAND REROLL"):
            return 0
        if not self._target_unit_can_use_datasheet_command_reroll_stratagem_discount(
            target_unit,
            stratagem_name="COMMAND RE-ROLL",
        ):
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
        ctx = dict(context or {})

        game = getattr(self, "game", None)
        request_fn = getattr(game, "request_decision", None) if game is not None else None
        if not callable(request_fn):
            raise RuntimeError(
                f"Optional decision '{k}' requires game.request_decision before local choices can be consumed."
            )

        from ..engine.decision_kinds import DECISION_CONFIRM_YES_NO
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import decision_request_is_pending, resolve_or_reuse_confirmation_choice

        ability_name = str(ctx.get("ability_name", "") or "").strip() or self._default_optional_ability_name(k)
        ctx.setdefault("ability", str(k).lower())
        ctx["ability_name"] = ability_name
        ctx.setdefault("ability_key", k)
        ctx.setdefault("optional", True)
        prompt = str(ctx.get("prompt", "") or f"Use {ability_name}?")
        request = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            prompt,
            player_id=getattr(self, "id", None),
            options=[
                DecisionOption.create("Use", payload={"choice": True}),
                DecisionOption.create("Skip", payload={"choice": False}),
            ],
            context=ctx,
        )
        request_fn(request)

        local_choice = None
        if decision_request_is_pending(game, request):
            local_choice = self._resolve_optional_ability_local_choice(k, ctx)

        resolved_choice, apply_result = resolve_or_reuse_confirmation_choice(
            game,
            request,
            preselected_choice=local_choice,
            player_id=getattr(self, "id", None),
        )
        if decision_request_is_pending(game, request):
            raise RuntimeError(
                f"Optional decision '{k}' remained pending without a synchronous decision owner."
            )
        return bool(resolved_choice and apply_result is not None and getattr(apply_result, "ok", False))

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

        instinctive = self._preview_instinctive_defence_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if instinctive:
            ability_name = "Instinctive Defence"
            try:
                get_rule = getattr(target_unit, "get_instinctive_defence_heroic_intervention_rule", None)
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
                "INSTINCTIVE_DEFENCE_HEROIC_INTERVENTION",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Heroic Intervention for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        adaptive_reprisal = self._preview_adaptive_reprisal_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if adaptive_reprisal:
            context = self._adaptive_reprisal_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Adaptive Reprisal").strip() or "Adaptive Reprisal"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "ADAPTIVE_REPRISAL_HEROIC_INTERVENTION",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Heroic Intervention for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        vengeful_tread = self._preview_vengeful_tread_tank_shock_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if vengeful_tread:
            context = self._vengeful_tread_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Vengeful Tread").strip() or "Vengeful Tread"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "VENGEFUL_TREAD_TANK_SHOCK",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Tank Shock for 0CP.")
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

        visions = self._preview_visions_of_heresy_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if visions:
            if name_u in ("OVERWATCH", "FIRE OVERWATCH"):
                mgr = getattr(self, "stratagems", None)
                used_this_turn = getattr(mgr, "_used_this_turn", {}) if mgr is not None else {}
                overwatch_used = bool(used_this_turn.get("OVERWATCH", False)) if isinstance(used_this_turn, dict) else False
                if overwatch_used:
                    visions = 0
            if not visions:
                pass
            else:
                ability_name = "Visions of Heresy"
                try:
                    get_rule = getattr(target_unit, "get_visions_of_heresy_stratagem_discount_rule", None)
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
                    "VISIONS_OF_HERESY_STRATAGEM_DISCOUNT",
                    ctx,
                    assume=assume_optional_discounts,
                ):
                    discount = base
                    if name_u in ("OVERWATCH", "FIRE OVERWATCH"):
                        reasons.append(f"{ability_name}: Fire Overwatch for 0CP.")
                    else:
                        reasons.append(f"{ability_name}: Heroic Intervention for 0CP.")
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

        precursive = self._preview_precursive_judgement_overwatch_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if precursive:
            ability_name = "Precursive Judgement"
            try:
                get_rule = getattr(target_unit, "get_precursive_judgement_overwatch_rule", None)
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
                "PRECURSIVE_JUDGEMENT_OVERWATCH",
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

        datasheet_overwatch = self._preview_datasheet_overwatch_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if datasheet_overwatch:
            ability_name = "Datasheet Overwatch"
            try:
                get_rule = getattr(target_unit, "get_datasheet_overwatch_stratagem_discount_rule", None)
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
                "DATASHEET_OVERWATCH_DISCOUNT",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Fire Overwatch for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        flare_launcher = self._preview_flare_launcher_smokescreen_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if flare_launcher:
            ability_name = "Flare Launcher"
            try:
                get_rule = getattr(target_unit, "get_flare_launcher_smokescreen_rule", None)
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
                "FLARE_LAUNCHER_SMOKESCREEN_DISCOUNT",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Smokescreen for 0CP.")
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

        unit_contains_heroic = self._preview_unit_contains_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if unit_contains_heroic:
            ability_name = "Unit contains Heroic Intervention"
            try:
                get_rule = getattr(target_unit, "get_unit_contains_heroic_intervention_rule", None)
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
                "UNIT_CONTAINS_HEROIC_INTERVENTION",
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

        master_of_prescience = self._preview_master_of_prescience_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if master_of_prescience:
            if name_u in ("OVERWATCH", "FIRE OVERWATCH"):
                mgr = getattr(self, "stratagems", None)
                used_this_turn = getattr(mgr, "_used_this_turn", {}) if mgr is not None else {}
                overwatch_used = bool(used_this_turn.get("OVERWATCH", False)) if isinstance(used_this_turn, dict) else False
                if overwatch_used:
                    master_of_prescience = 0
            elif name_u in ("COUNTER-OFFENSIVE", "COUNTER OFFENSIVE"):
                mgr = getattr(self, "stratagems", None)
                used_this_phase = getattr(mgr, "_used_stratagems_this_phase", set()) if mgr is not None else set()
                counter_used = "COUNTER-OFFENSIVE" in used_this_phase if isinstance(used_this_phase, set) else False
                if counter_used:
                    master_of_prescience = 0
            if master_of_prescience:
                ability_name = "Master of Prescience (Psychic)"
                try:
                    get_rule = getattr(target_unit, "get_master_of_prescience_stratagem_discount_rule", None)
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
                    "MASTER_OF_PRESCIENCE_STRATAGEM_DISCOUNT",
                    ctx,
                    assume=assume_optional_discounts,
                ):
                    discount = base
                    if name_u in ("OVERWATCH", "FIRE OVERWATCH"):
                        reasons.append(f"{ability_name}: Fire Overwatch for 0CP.")
                    elif name_u in ("COUNTER-OFFENSIVE", "COUNTER OFFENSIVE"):
                        reasons.append(f"{ability_name}: Counter-offensive for 0CP.")
                    elif name_u == "GO TO GROUND":
                        reasons.append(f"{ability_name}: Go to Ground for 0CP.")
                    else:
                        reasons.append(f"{ability_name}: Heroic Intervention for 0CP.")
                    return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        eye = self._preview_eye_of_the_augurium_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if eye:
            ability_name = "Eye of the Augurium"
            try:
                get_rule = getattr(target_unit, "get_eye_of_the_augurium_stratagem_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            ability_key = "EYE_OF_THE_AUGURIUM_STRATAGEM_DISCOUNT"
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
                if name_u in ("OVERWATCH", "FIRE OVERWATCH"):
                    reasons.append(f"{ability_name}: Fire Overwatch for 0CP.")
                else:
                    reasons.append(f"{ability_name}: Heroic Intervention for 0CP.")
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

        martial_tuition = self._preview_martial_tuition_counter_offensive_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if martial_tuition:
            context = self._martial_tuition_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Martial Tuition").strip() or "Martial Tuition"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "MARTIAL_TUITION_COUNTER_OFFENSIVE",
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
        fleetmaster = self._preview_fleetmaster_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if fleetmaster:
            ability_name = "Fleetmaster"
            members = self._attached_members(target_unit)
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not bool(sr.get("enhancement_imperialis_fleet_fleetmaster", False)):
                    continue
                ability_name = str(
                    sr.get("enhancement_imperialis_fleet_fleetmaster_source", "") or ability_name
                ).strip() or ability_name
                break
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "FLEETMASTER_FREE_STRATAGEM",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                stratagem_label = str(getattr(stratagem, "name", "") or "").strip() or "Stratagem"
                reasons.append(f"{ability_name}: {stratagem_label} for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        gift_of_the_prescient = self._preview_gift_of_the_prescient_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if gift_of_the_prescient:
            context = self._gift_of_the_prescient_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Gift of the Prescient").strip() or "Gift of the Prescient"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "GIFT_OF_THE_PRESCIENT_RAPID_INGRESS",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Rapid Ingress for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        webway_awl = self._preview_webway_awl_rapid_ingress_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if webway_awl:
            context = self._webway_awl_rapid_ingress_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Webway Awl").strip() or "Webway Awl"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "WEBWAY_AWL_RAPID_INGRESS",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Rapid Ingress for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        teleport_homer = self._preview_teleport_homer_rapid_ingress_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if teleport_homer:
            context = self._teleport_homer_rapid_ingress_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Teleport Homer").strip() or "Teleport Homer"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "TELEPORT_HOMER_RAPID_INGRESS",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Rapid Ingress for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        homing_beacon = self._preview_homing_beacon_rapid_ingress_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if homing_beacon:
            context = self._homing_beacon_rapid_ingress_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Homing Beacon").strip() or "Homing Beacon"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "HOMING_BEACON_RAPID_INGRESS",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Rapid Ingress for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        pheromone_trail = self._preview_pheromone_trail_rapid_ingress_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if pheromone_trail:
            ability_name = "Pheromone Trail"
            try:
                get_rule = getattr(target_unit, "get_pheromone_trail_rapid_ingress_rule", None)
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
                "PHEROMONE_TRAIL_RAPID_INGRESS",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Rapid Ingress for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        grenadiers = self._preview_grenadiers_grenade_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if grenadiers:
            ability_name = "Grenadiers"
            try:
                get_rule = getattr(target_unit, "get_grenadiers_grenade_rule", None)
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
                "GRENADIERS_GRENADE",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Grenade for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        primed_and_ready = self._preview_primed_and_ready_grenade_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if primed_and_ready:
            ability_name = "Primed and Ready"
            try:
                get_rule = getattr(target_unit, "get_primed_and_ready_grenade_rule", None)
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
                "PRIMED_AND_READY_GRENADE",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
                reasons.append(f"{ability_name}: Grenade for 0CP.")
                return {"base": base, "discount": discount, "cost": 0, "reasons": reasons}

        blackwing = self._preview_blackwing_mantle_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if blackwing:
            ability_name = "Blackwing Mantle"
            try:
                get_rule = getattr(target_unit, "get_blackwing_mantle_stratagem_discount_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            stratagem_label = str(getattr(stratagem, "name", "") or "").strip() or "Stratagem"
            ctx = {
                "ability_name": ability_name,
                "stratagem": stratagem_label,
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "BLACKWING_MANTLE_STRATAGEM_DISCOUNT",
                ctx,
                assume=assume_optional_discounts,
            ):
                reasons.append(f"{ability_name}: {stratagem_label} for 0CP.")
                return {"base": base, "discount": base, "cost": 0, "reasons": reasons}

        hypersensory = self._preview_hypersensory_array_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if hypersensory:
            ability_name = "Hypersensory Array"
            try:
                get_rule = getattr(target_unit, "get_hypersensory_array_stratagem_discount_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            stratagem_label = str(getattr(stratagem, "name", "") or "").strip() or "Stratagem"
            ctx = {
                "ability_name": ability_name,
                "stratagem": stratagem_label,
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "HYPERSENSORY_ARRAY_STRATAGEM_DISCOUNT",
                ctx,
                assume=assume_optional_discounts,
            ):
                reasons.append(f"{ability_name}: {stratagem_label} for 0CP.")
                return {"base": base, "discount": base, "cost": 0, "reasons": reasons}

        synaptic_strategy = self._preview_synaptic_strategy_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if synaptic_strategy:
            ability_name = "Synaptic Strategy"
            try:
                get_rule = getattr(target_unit, "get_synaptic_strategy_stratagem_discount_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            stratagem_label = str(getattr(stratagem, "name", "") or "").strip() or "Stratagem"
            ctx = {
                "ability_name": ability_name,
                "stratagem": stratagem_label,
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "SYNAPTIC_STRATEGY_RAPID_INGRESS",
                ctx,
                assume=assume_optional_discounts,
            ):
                reasons.append(f"{ability_name}: {stratagem_label} for 0CP.")
                return {"base": base, "discount": base, "cost": 0, "reasons": reasons}

        infernal_fulgurite = self._preview_infernal_fulgurite_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if infernal_fulgurite:
            ability_name = "Infernal Fulgurite"
            try:
                get_rule = getattr(target_unit, "get_infernal_fulgurite_stratagem_discount_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            stratagem_label = str(getattr(stratagem, "name", "") or "").strip() or "Stratagem"
            ctx = {
                "ability_name": ability_name,
                "stratagem": stratagem_label,
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "INFERNAL_FULGURITE_RAPID_INGRESS",
                ctx,
                assume=assume_optional_discounts,
            ):
                reasons.append(f"{ability_name}: {stratagem_label} for 0CP.")
                return {"base": base, "discount": base, "cost": 0, "reasons": reasons}

        if grimnars_mark:
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            ctx = {
                "ability_name": "Grimnar's Mark",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "GRIMNARS_MARK_STRATAGEM_DISCOUNT",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount = base
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

        tsd, tsd_names, tsd_specs = self._preview_targeted_stratagem_cp_discount(
            target_unit=target_unit,
            stratagem=stratagem,
        )
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

        cherub_discount = self._preview_datasheet_command_reroll_discount(stratagem=stratagem, target_unit=target_unit)
        if cherub_discount:
            ability_name = "Cherub"
            try:
                get_rule = getattr(target_unit, "get_datasheet_command_reroll_stratagem_discount_rule", None)
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
                "DATASHEET_COMMAND_REROLL_DISCOUNT",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount += int(cherub_discount)
                reasons.append(f"{ability_name}: Command Re-roll for 0CP.")

        gof = self._preview_gift_of_foresight_discount(stratagem=stratagem, target_unit=target_unit)
        if gof:
            ctx = {
                "ability_name": "Gift of Foresight",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "GIFT_OF_FORESIGHT",
                ctx,
                assume=assume_optional_discounts,
            ):
                discount += int(gof)
                logger.info("Gift of Foresight: %s uses Command Re-roll for 0CP.", self.name)

        mof = self._preview_mirror_of_fates_discount(stratagem=stratagem, target_unit=target_unit)
        if mof:
            ctx = {
                "ability_name": "Mirror of Fates",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "MIRROR_OF_FATES",
                ctx,
                assume=assume_optional_discounts,
            ):
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
            ctx = {
                "ability_name": "Master of the Pageant",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_preview_optional_ability(
                "MASTER_OF_THE_PAGEANT",
                ctx,
                assume=assume_optional_discounts,
            ):
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
        mgr = getattr(self, "stratagems", None)
        used_this_phase = getattr(mgr, "_used_stratagems_this_phase", set()) if mgr is not None else set()
        heroic_intervention_used_this_phase = bool(
            name_u == "HEROIC INTERVENTION" and isinstance(used_this_phase, set) and "HEROIC INTERVENTION" in used_this_phase
        )
        if heroic_intervention_used_this_phase:
            repeat_allowed = getattr(mgr, "_heroic_intervention_repeat_allowed", None)
            if not callable(repeat_allowed) or not bool(
                repeat_allowed(target_unit=target_unit, enemy_unit=enemy_unit)
            ):
                return {"denied": True, "reason": "Heroic Intervention already used this phase"}
        rapid_ingress_used_this_phase = bool(
            name_u == "RAPID INGRESS" and isinstance(used_this_phase, set) and "RAPID INGRESS" in used_this_phase
        )
        if rapid_ingress_used_this_phase:
            repeat_allowed = getattr(mgr, "_rapid_ingress_repeat_allowed", None)
            if not callable(repeat_allowed) or not bool(repeat_allowed(target_unit=target_unit)):
                return {"denied": True, "reason": "Rapid Ingress already used this phase"}
        command_reroll_used_this_phase = bool(
            name_u == "COMMAND RE-ROLL" and isinstance(used_this_phase, set) and "COMMAND RE-ROLL" in used_this_phase
        )
        command_reroll_repeat_bypass_used = False
        if command_reroll_used_this_phase:
            repeat_allowed = getattr(mgr, "_command_reroll_repeat_allowed", None)
            if not callable(repeat_allowed) or not bool(repeat_allowed(target_unit=target_unit)):
                return {"denied": True, "reason": "Command Re-roll already used this phase"}
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
                "faultless_opportunist_use": True,
                "faultless_opportunist_source": "Faultless Opportunist",
            }
        flare_launcher = self._preview_flare_launcher_smokescreen_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if flare_launcher:
            ability_name = "Flare Launcher"
            try:
                get_rule = getattr(target_unit, "get_flare_launcher_smokescreen_rule", None)
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
            if self._should_use_optional_ability("FLARE_LAUNCHER_SMOKESCREEN_DISCOUNT", ctx):
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
                    "reasons": [f"{ability_name}: Smokescreen for 0CP."],
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
        instinctive = self._preview_instinctive_defence_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if instinctive and target_unit is not None:
            ability_name = "Instinctive Defence"
            try:
                get_rule = getattr(target_unit, "get_instinctive_defence_heroic_intervention_rule", None)
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
            if self._should_use_optional_ability("INSTINCTIVE_DEFENCE_HEROIC_INTERVENTION", ctx):
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
                    "instinctive_defence_heroic_intervention_use": True,
                    "instinctive_defence_heroic_intervention_source": ability_name,
                }
        adaptive_reprisal = self._preview_adaptive_reprisal_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if adaptive_reprisal and target_unit is not None:
            context = self._adaptive_reprisal_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Adaptive Reprisal").strip() or "Adaptive Reprisal"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("ADAPTIVE_REPRISAL_HEROIC_INTERVENTION", ctx):
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
                usage_key = str(
                    context.get("usage_key", "") or "ADAPTIVE_REPRISAL_HEROIC_INTERVENTION"
                ).strip().upper()
                if usage_key:
                    self._mark_ability_used_turn(usage_key)
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": [f"{ability_name}: Heroic Intervention for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "adaptive_reprisal_heroic_intervention_use": True,
                    "adaptive_reprisal_heroic_intervention_source": ability_name,
                }
        vengeful_tread = self._preview_vengeful_tread_tank_shock_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if vengeful_tread and target_unit is not None:
            context = self._vengeful_tread_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Vengeful Tread").strip() or "Vengeful Tread"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("VENGEFUL_TREAD_TANK_SHOCK", ctx):
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
                usage_key = str(context.get("usage_key", "") or "VENGEFUL_TREAD_TANK_SHOCK").strip().upper()
                if usage_key:
                    self._mark_ability_used_turn(usage_key)
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": [f"{ability_name}: Tank Shock for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "vengeful_tread_tank_shock_use": True,
                    "vengeful_tread_tank_shock_source": ability_name,
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
        visions = self._preview_visions_of_heresy_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if visions and target_unit is not None and name_u == "HEROIC INTERVENTION":
            ability_name = "Visions of Heresy"
            try:
                get_rule = getattr(target_unit, "get_visions_of_heresy_stratagem_discount_rule", None)
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
            if self._should_use_optional_ability("VISIONS_OF_HERESY_STRATAGEM_DISCOUNT", ctx):
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
                    mark_used = getattr(target_unit, "mark_visions_of_heresy_used", None)
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
                    "reasons": [f"{ability_name}: Heroic Intervention for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "visions_of_heresy_use": True,
                    "visions_of_heresy_source": ability_name,
                }
        snarling = self._preview_snarling_protector_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if snarling and target_unit is not None:
            ability_name = "Snarling Protector"
            usage_key = ""
            usage_scope = "turn"
            try:
                get_rule = getattr(target_unit, "get_snarling_protector_heroic_intervention_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
                    usage_key = str(rule.get("usage_key", "") or "").strip().upper()
                    usage_scope = str(rule.get("usage_scope", "") or "turn").strip().lower()
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
                if usage_key:
                    if usage_scope == "battle_round":
                        battle_round = int(self._battle_round() or 0)
                        if battle_round > 0:
                            self._ability_used_battle_round[usage_key] = battle_round
                    else:
                        self._mark_ability_used_turn(usage_key)
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
        unit_contains_heroic = self._preview_unit_contains_heroic_intervention_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if unit_contains_heroic and target_unit is not None:
            ability_name = "Unit contains Heroic Intervention"
            try:
                get_rule = getattr(target_unit, "get_unit_contains_heroic_intervention_rule", None)
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
            if self._should_use_optional_ability("UNIT_CONTAINS_HEROIC_INTERVENTION", ctx):
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
                    "unit_contains_heroic_intervention_use": True,
                    "unit_contains_heroic_intervention_source": ability_name,
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
        master_of_prescience = self._preview_master_of_prescience_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if (
            master_of_prescience
            and target_unit is not None
            and name_u not in ("OVERWATCH", "FIRE OVERWATCH", "COUNTER-OFFENSIVE", "COUNTER OFFENSIVE")
        ):
            ability_name = "Master of Prescience (Psychic)"
            try:
                get_rule = getattr(target_unit, "get_master_of_prescience_stratagem_discount_rule", None)
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
            if self._should_use_optional_ability("MASTER_OF_PRESCIENCE_STRATAGEM_DISCOUNT", ctx):
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
                    mark_used = getattr(target_unit, "mark_master_of_prescience_used", None)
                    if callable(mark_used):
                        mark_used(
                            self.game,
                            source=ability_name,
                            stratagem_name=str(getattr(stratagem, "name", "") or ""),
                        )
                except Exception:
                    pass
                if name_u == "GO TO GROUND":
                    reason = f"{ability_name}: Go to Ground for 0CP."
                else:
                    reason = f"{ability_name}: Heroic Intervention for 0CP."
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": [reason],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "master_of_prescience_use": True,
                    "master_of_prescience_source": ability_name,
                }
        eye = self._preview_eye_of_the_augurium_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if eye and target_unit is not None and name_u == "HEROIC INTERVENTION":
            ability_name = "Eye of the Augurium"
            try:
                get_rule = getattr(target_unit, "get_eye_of_the_augurium_stratagem_rule", None)
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
            if self._should_use_optional_ability("EYE_OF_THE_AUGURIUM_STRATAGEM_DISCOUNT", ctx):
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
                    mark_used = getattr(target_unit, "mark_eye_of_the_augurium_used", None)
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
                    "reasons": [f"{ability_name}: Heroic Intervention for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "eye_of_the_augurium_use": True,
                    "eye_of_the_augurium_source": ability_name,
                }
        if name_u in ("OVERWATCH", "FIRE OVERWATCH") and target_unit is not None:
            get_rule = getattr(target_unit, "get_traitor_enforcer_overwatch_rule", None)
            rule = get_rule() if callable(get_rule) else None
            can_traitor = bool(rule) and bool(
                getattr(target_unit, "can_use_traitor_enforcer_overwatch", lambda _g=None: False)(self.game)
            )
            can_eye = bool(
                self._target_unit_can_use_eye_of_the_augurium_stratagem_discount(
                    target_unit,
                    stratagem_name=name_u,
                )
            )
            can_prophetic = bool(
                self._target_unit_can_use_prophetic_sentinels_stratagem_discount(
                    target_unit,
                    stratagem_name=name_u,
                )
            )
            can_visions = bool(
                self._target_unit_can_use_visions_of_heresy_stratagem_discount(
                    target_unit,
                    stratagem_name=name_u,
                )
            )
            can_master_of_prescience = bool(
                self._target_unit_can_use_master_of_prescience_stratagem_discount(
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
            can_precursive = bool(
                self._target_unit_can_use_precursive_judgement_overwatch(
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
            can_datasheet_overwatch = bool(
                self._target_unit_can_use_datasheet_overwatch_stratagem_discount(
                    target_unit,
                    stratagem_name=name_u,
                )
            )
            get_datasheet_rule = getattr(target_unit, "get_datasheet_overwatch_stratagem_discount_rule", None)
            datasheet_rule = get_datasheet_rule() if callable(get_datasheet_rule) else None
            datasheet_repeat_bypass = bool(
                isinstance(datasheet_rule, dict)
                and bool(datasheet_rule.get("repeat_bypass", False))
            )
            mgr = getattr(self, "stratagems", None)
            used_this_turn = getattr(mgr, "_used_this_turn", {}) if mgr is not None else {}
            overwatch_used = bool(used_this_turn.get("OVERWATCH", False)) if isinstance(used_this_turn, dict) else False
            if overwatch_used and not can_traitor and not can_eye and not (can_datasheet_overwatch and datasheet_repeat_bypass):
                return {"denied": True, "reason": "Overwatch already used this turn"}
            if can_eye:
                ability_name = "Eye of the Augurium"
                try:
                    get_eye_rule = getattr(target_unit, "get_eye_of_the_augurium_stratagem_rule", None)
                    eye_rule = get_eye_rule() if callable(get_eye_rule) else None
                    if isinstance(eye_rule, dict):
                        ability_name = str(eye_rule.get("source", "") or ability_name).strip() or ability_name
                except Exception:
                    pass
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                use_eye = self._should_use_optional_ability("EYE_OF_THE_AUGURIUM_STRATAGEM_DISCOUNT", ctx)
                if use_eye:
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
                        mark_used = getattr(target_unit, "mark_eye_of_the_augurium_used", None)
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
                        "eye_of_the_augurium_use": True,
                        "eye_of_the_augurium_source": ability_name,
                    }
                if overwatch_used and not can_traitor:
                    return {"denied": True, "reason": "Overwatch already used this turn"}
            if can_precursive:
                ability_name = "Precursive Judgement"
                try:
                    get_rule = getattr(target_unit, "get_precursive_judgement_overwatch_rule", None)
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
                use_precursive = self._should_use_optional_ability("PRECURSIVE_JUDGEMENT_OVERWATCH", ctx)
                if use_precursive:
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
                    }
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
            if can_visions:
                ability_name = "Visions of Heresy"
                try:
                    get_v_rule = getattr(target_unit, "get_visions_of_heresy_stratagem_discount_rule", None)
                    v_rule = get_v_rule() if callable(get_v_rule) else None
                    if isinstance(v_rule, dict):
                        ability_name = str(v_rule.get("source", "") or ability_name).strip() or ability_name
                except Exception:
                    pass
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                use_visions = self._should_use_optional_ability("VISIONS_OF_HERESY_STRATAGEM_DISCOUNT", ctx)
                if use_visions:
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
                        mark_used = getattr(target_unit, "mark_visions_of_heresy_used", None)
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
                        "visions_of_heresy_use": True,
                        "visions_of_heresy_source": ability_name,
                    }
            if can_master_of_prescience:
                ability_name = "Master of Prescience (Psychic)"
                try:
                    get_master_rule = getattr(target_unit, "get_master_of_prescience_stratagem_discount_rule", None)
                    master_rule = get_master_rule() if callable(get_master_rule) else None
                    if isinstance(master_rule, dict):
                        ability_name = str(master_rule.get("source", "") or ability_name).strip() or ability_name
                except Exception:
                    pass
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                use_master = self._should_use_optional_ability("MASTER_OF_PRESCIENCE_STRATAGEM_DISCOUNT", ctx)
                if use_master:
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
                        mark_used = getattr(target_unit, "mark_master_of_prescience_used", None)
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
                        "master_of_prescience_use": True,
                        "master_of_prescience_source": ability_name,
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
            if can_datasheet_overwatch:
                ability_name = "Datasheet Overwatch"
                if isinstance(datasheet_rule, dict):
                    ability_name = str(datasheet_rule.get("source", "") or ability_name).strip() or ability_name
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                use_datasheet = self._should_use_optional_ability("DATASHEET_OVERWATCH_DISCOUNT", ctx)
                if overwatch_used and datasheet_repeat_bypass and not use_datasheet and not can_traitor and not can_eye:
                    return {"denied": True, "reason": "Overwatch already used this turn"}
                if use_datasheet:
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
                        "datasheet_overwatch_discount_use": True,
                        "datasheet_overwatch_discount_source": ability_name,
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
            mgr = getattr(self, "stratagems", None)
            used_this_phase = getattr(mgr, "_used_stratagems_this_phase", set()) if mgr is not None else set()
            counter_used = "COUNTER-OFFENSIVE" in used_this_phase if isinstance(used_this_phase, set) else False
            can_intraneural = self._target_unit_can_use_intraneural_biotech_stratagem_discount(
                target_unit,
                stratagem_name="COUNTER-OFFENSIVE",
            )
            can_master_of_prescience = self._target_unit_can_use_master_of_prescience_stratagem_discount(
                target_unit,
                stratagem_name="COUNTER-OFFENSIVE",
            )
            if counter_used and not can_intraneural:
                return {"denied": True, "reason": "Counter-offensive already used this phase"}
            if can_master_of_prescience and not counter_used:
                ability_name = "Master of Prescience (Psychic)"
                try:
                    get_master_rule = getattr(target_unit, "get_master_of_prescience_stratagem_discount_rule", None)
                    master_rule = get_master_rule() if callable(get_master_rule) else None
                    if isinstance(master_rule, dict):
                        ability_name = str(master_rule.get("source", "") or ability_name).strip() or ability_name
                except Exception:
                    pass
                ctx = {
                    "ability_name": ability_name,
                    "stratagem": getattr(stratagem, "name", None) or "",
                    "target_unit": getattr(target_unit, "name", None) or "",
                    "base_cp_cost": base,
                }
                if self._should_use_optional_ability("MASTER_OF_PRESCIENCE_STRATAGEM_DISCOUNT", ctx):
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
                        mark_used = getattr(target_unit, "mark_master_of_prescience_used", None)
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
                        "reasons": [f"{ability_name}: Counter-offensive for 0CP (used)"],
                        "master_of_prescience_use": True,
                        "master_of_prescience_source": ability_name,
                    }
            if counter_used:
                return {"denied": True, "reason": "Counter-offensive already used this phase"}

        grenade_used_this_phase = False
        if name_u == "GRENADE" and target_unit is not None:
            mgr = getattr(self, "stratagems", None)
            used_this_phase = getattr(mgr, "_used_stratagems_this_phase", set()) if mgr is not None else set()
            grenade_used_this_phase = "GRENADE" in used_this_phase if isinstance(used_this_phase, set) else False
            can_primed_and_ready = self._target_unit_can_use_primed_and_ready_grenade(
                target_unit,
                stratagem_name="GRENADE",
            )
            if grenade_used_this_phase and not can_primed_and_ready:
                return {"denied": True, "reason": "Grenade already used this phase"}

        martial_tuition = self._preview_martial_tuition_counter_offensive_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if martial_tuition and target_unit is not None:
            context = self._martial_tuition_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Martial Tuition").strip() or "Martial Tuition"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("MARTIAL_TUITION_COUNTER_OFFENSIVE", ctx):
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
                usage_key = str(
                    context.get("usage_key", "") or "MARTIAL_TUITION_COUNTER_OFFENSIVE"
                ).strip().upper()
                if usage_key:
                    self._mark_ability_used_turn(usage_key)
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": [f"{ability_name}: Counter-offensive for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "martial_tuition_counter_offensive_use": True,
                    "martial_tuition_counter_offensive_source": ability_name,
                }

        fleetmaster = self._preview_fleetmaster_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if fleetmaster:
            usage_key = "FLEETMASTER_FREE_STRATAGEM"
            ability_name = "Fleetmaster"
            members = self._attached_members(target_unit)
            for member in members:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not bool(sr.get("enhancement_imperialis_fleet_fleetmaster", False)):
                    continue
                configured_key = str(
                    sr.get("enhancement_imperialis_fleet_fleetmaster_usage_key", "") or ""
                ).strip().upper()
                if configured_key:
                    usage_key = configured_key
                ability_name = str(
                    sr.get("enhancement_imperialis_fleet_fleetmaster_source", "") or ability_name
                ).strip() or ability_name
                break
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("FLEETMASTER_FREE_STRATAGEM", ctx):
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
                    self._ability_used_battle_round[usage_key] = br
                stratagem_label = str(getattr(stratagem, "name", "") or "").strip() or "Stratagem"
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": [f"{ability_name}: {stratagem_label} for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "fleetmaster_use": True,
                    "fleetmaster_source": ability_name,
                }

        gift_of_the_prescient = self._preview_gift_of_the_prescient_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if gift_of_the_prescient:
            context = self._gift_of_the_prescient_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Gift of the Prescient").strip() or "Gift of the Prescient"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("GIFT_OF_THE_PRESCIENT_RAPID_INGRESS", ctx):
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
                usage_key = str(
                    context.get("usage_key", "") or "gift_of_the_prescient_rapid_ingress"
                ).strip().lower()
                if not usage_key:
                    usage_key = "gift_of_the_prescient_rapid_ingress"
                source_unit = context.get("source_unit")
                if source_unit is not None:
                    mark_used = getattr(source_unit, "mark_unit_once_per_battle_used", None)
                    if callable(mark_used):
                        mark_used(usage_key, ability_name=ability_name)
                try:
                    deep_strike_min_distance = float(context.get("deep_strike_min_distance", 3.0) or 3.0)
                except (TypeError, ValueError):
                    deep_strike_min_distance = 3.0
                if deep_strike_min_distance <= 0.0:
                    deep_strike_min_distance = 3.0
                expires_phase = str(context.get("expires_phase", "") or "MOVEMENT_PHASE").strip().upper()
                if not expires_phase:
                    expires_phase = "MOVEMENT_PHASE"
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": [f"{ability_name}: Rapid Ingress for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "gift_of_the_prescient_use": True,
                    "gift_of_the_prescient_source": ability_name,
                    "gift_of_the_prescient_usage_key": usage_key,
                    "gift_of_the_prescient_deep_strike_min_distance": float(deep_strike_min_distance),
                    "gift_of_the_prescient_expires_phase": expires_phase,
                }

        teleport_homer = self._preview_teleport_homer_rapid_ingress_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if teleport_homer and target_unit is not None:
            context = self._teleport_homer_rapid_ingress_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Teleport Homer").strip() or "Teleport Homer"
            source_unit_id = str(context.get("source_unit_id", "") or "")
            usage_key = str(context.get("usage_key", "") or "teleport_homer_rapid_ingress").strip().lower()
            try:
                anchor_distance = float(context.get("anchor_distance", 3.0) or 3.0)
            except (TypeError, ValueError):
                anchor_distance = 3.0
            if anchor_distance <= 0.0:
                anchor_distance = 3.0
            try:
                min_enemy_distance = float(context.get("deep_strike_min_distance", 9.0) or 9.0)
            except (TypeError, ValueError):
                min_enemy_distance = 9.0
            if min_enemy_distance <= 0.0:
                min_enemy_distance = 9.0
            anchor_point = [0.0, 0.0, 0.0]
            raw_anchor_point = context.get("anchor_point")
            if isinstance(raw_anchor_point, (list, tuple)) and len(raw_anchor_point) >= 2:
                try:
                    anchor_point = [
                        float(raw_anchor_point[0]),
                        float(raw_anchor_point[1]),
                        float(raw_anchor_point[2]) if len(raw_anchor_point) > 2 else 0.0,
                    ]
                except (TypeError, ValueError):
                    anchor_point = [0.0, 0.0, 0.0]
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("TELEPORT_HOMER_RAPID_INGRESS", ctx):
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
                    "reasons": [f"{ability_name}: Rapid Ingress for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "teleport_homer_rapid_ingress_use": True,
                    "teleport_homer_rapid_ingress_source": ability_name,
                    "teleport_homer_rapid_ingress_usage_key": usage_key,
                    "teleport_homer_rapid_ingress_source_unit_id": source_unit_id,
                    "teleport_homer_rapid_ingress_anchor_mode": str(context.get("anchor_mode", "") or "marker_point"),
                    "teleport_homer_rapid_ingress_anchor_distance": float(anchor_distance),
                    "teleport_homer_rapid_ingress_anchor_point": list(anchor_point),
                    "teleport_homer_rapid_ingress_deep_strike_min_distance": float(min_enemy_distance),
                }

        homing_beacon = self._preview_homing_beacon_rapid_ingress_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if homing_beacon and target_unit is not None:
            context = self._homing_beacon_rapid_ingress_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Homing Beacon").strip() or "Homing Beacon"
            source_unit = context.get("source_unit")
            source_unit_id = str(context.get("source_unit_id", "") or "")
            usage_key = str(context.get("usage_key", "") or "homing_beacon_rapid_ingress").strip().lower()
            try:
                anchor_distance = float(context.get("anchor_distance", 3.0) or 3.0)
            except (TypeError, ValueError):
                anchor_distance = 3.0
            if anchor_distance <= 0.0:
                anchor_distance = 3.0
            try:
                min_enemy_distance = float(context.get("deep_strike_min_distance", 9.0) or 9.0)
            except (TypeError, ValueError):
                min_enemy_distance = 9.0
            if min_enemy_distance <= 0.0:
                min_enemy_distance = 9.0
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("HOMING_BEACON_RAPID_INGRESS", ctx):
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
                if source_unit is not None:
                    mark_used = getattr(source_unit, "mark_homing_beacon_rapid_ingress_used", None)
                    if callable(mark_used):
                        mark_used(
                            source=ability_name,
                            stratagem_name=str(getattr(stratagem, "name", "") or ""),
                        )
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": [f"{ability_name}: Rapid Ingress for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "homing_beacon_rapid_ingress_use": True,
                    "homing_beacon_rapid_ingress_source": ability_name,
                    "homing_beacon_rapid_ingress_usage_key": usage_key,
                    "homing_beacon_rapid_ingress_source_unit_id": source_unit_id,
                    "homing_beacon_rapid_ingress_anchor_mode": str(context.get("anchor_mode", "") or "source_unit"),
                    "homing_beacon_rapid_ingress_anchor_distance": float(anchor_distance),
                    "homing_beacon_rapid_ingress_deep_strike_min_distance": float(min_enemy_distance),
                }

        pheromone_trail = self._preview_pheromone_trail_rapid_ingress_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if pheromone_trail and target_unit is not None:
            ability_name = "Pheromone Trail"
            try:
                get_rule = getattr(target_unit, "get_pheromone_trail_rapid_ingress_rule", None)
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
            if self._should_use_optional_ability("PHEROMONE_TRAIL_RAPID_INGRESS", ctx):
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
                    mark_used = getattr(target_unit, "mark_pheromone_trail_used", None)
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
                    "reasons": [f"{ability_name}: Rapid Ingress for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "pheromone_trail_rapid_ingress_use": True,
                    "pheromone_trail_rapid_ingress_source": ability_name,
                }

        grenadiers = self._preview_grenadiers_grenade_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if grenadiers and target_unit is not None:
            ability_name = "Grenadiers"
            try:
                get_rule = getattr(target_unit, "get_grenadiers_grenade_rule", None)
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
            use_grenadiers = self._should_use_optional_ability("GRENADIERS_GRENADE", ctx)
            if grenade_used_this_phase and use_grenadiers:
                return {"denied": True, "reason": "Grenade already used this phase"}
            if use_grenadiers:
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
                    mark_used = getattr(target_unit, "mark_grenadiers_grenade_used", None)
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
                    "reasons": [f"{ability_name}: Grenade for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "grenadiers_grenade_use": True,
                    "grenadiers_grenade_source": ability_name,
                }

        primed_and_ready = self._preview_primed_and_ready_grenade_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if primed_and_ready and target_unit is not None:
            ability_name = "Primed and Ready"
            try:
                get_rule = getattr(target_unit, "get_primed_and_ready_grenade_rule", None)
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
            use_primed_and_ready = self._should_use_optional_ability("PRIMED_AND_READY_GRENADE", ctx)
            if grenade_used_this_phase and not use_primed_and_ready:
                return {"denied": True, "reason": "Grenade already used this phase"}
            if use_primed_and_ready:
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
                self._mark_ability_used_phase("PRIMED_AND_READY_GRENADE")
                try:
                    mark_targeted = getattr(target_unit, "mark_primed_and_ready_grenade_targeted", None)
                    if callable(mark_targeted):
                        mark_targeted(
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
                    "reasons": [f"{ability_name}: Grenade for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "primed_and_ready_grenade_use": True,
                    "primed_and_ready_grenade_source": ability_name,
                }

        if name_u == "GRENADE" and grenade_used_this_phase:
            return {"denied": True, "reason": "Grenade already used this phase"}

        blackwing = self._preview_blackwing_mantle_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if blackwing:
            ability_name = "Blackwing Mantle"
            try:
                get_rule = getattr(target_unit, "get_blackwing_mantle_stratagem_discount_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            stratagem_label = str(getattr(stratagem, "name", "") or "").strip() or "Stratagem"
            ctx = {
                "ability_name": ability_name,
                "stratagem": stratagem_label,
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("BLACKWING_MANTLE_STRATAGEM_DISCOUNT", ctx):
                return {
                    "base": base,
                    "discount": base,
                    "cost": 0,
                    "reasons": [f"{ability_name}: {stratagem_label} for 0CP."],
                    "blackwing_mantle_use": True,
                    "blackwing_mantle_source": ability_name,
                }

        hypersensory = self._preview_hypersensory_array_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if hypersensory and target_unit is not None:
            ability_name = "Hypersensory Array"
            usage_key = "HYPERSENSORY_ARRAY_FREE_STRATAGEM"
            try:
                get_rule = getattr(target_unit, "get_hypersensory_array_stratagem_discount_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
                    usage_key = str(rule.get("usage_key", "") or usage_key).strip().upper() or usage_key
            except Exception:
                pass
            stratagem_label = str(getattr(stratagem, "name", "") or "").strip() or "Stratagem"
            ctx = {
                "ability_name": ability_name,
                "stratagem": stratagem_label,
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("HYPERSENSORY_ARRAY_STRATAGEM_DISCOUNT", ctx):
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
                if br > 0 and usage_key:
                    self._ability_used_battle_round[usage_key] = br
                try:
                    mark_used = getattr(target_unit, "mark_hypersensory_array_used", None)
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
                    "reasons": [f"{ability_name}: {stratagem_label} for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "hypersensory_array_use": True,
                    "hypersensory_array_source": ability_name,
                }

        synaptic_strategy = self._preview_synaptic_strategy_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if synaptic_strategy and target_unit is not None:
            ability_name = "Synaptic Strategy"
            try:
                get_rule = getattr(target_unit, "get_synaptic_strategy_stratagem_discount_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            stratagem_label = str(getattr(stratagem, "name", "") or "").strip() or "Stratagem"
            ctx = {
                "ability_name": ability_name,
                "stratagem": stratagem_label,
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("SYNAPTIC_STRATEGY_RAPID_INGRESS", ctx):
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
                    mark_used = getattr(target_unit, "mark_synaptic_strategy_used", None)
                    if callable(mark_used):
                        mark_used(
                            source=ability_name,
                            stratagem_name=str(getattr(stratagem, "name", "") or ""),
                        )
                except Exception:
                    pass
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": [f"{ability_name}: {stratagem_label} for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "synaptic_strategy_use": True,
                    "synaptic_strategy_source": ability_name,
                }

        infernal_fulgurite = self._preview_infernal_fulgurite_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if infernal_fulgurite and target_unit is not None:
            ability_name = "Infernal Fulgurite"
            try:
                get_rule = getattr(target_unit, "get_infernal_fulgurite_stratagem_discount_rule", None)
                rule = get_rule() if callable(get_rule) else None
                if isinstance(rule, dict):
                    ability_name = str(rule.get("source", "") or ability_name).strip() or ability_name
            except Exception:
                pass
            stratagem_label = str(getattr(stratagem, "name", "") or "").strip() or "Stratagem"
            ctx = {
                "ability_name": ability_name,
                "stratagem": stratagem_label,
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("INFERNAL_FULGURITE_RAPID_INGRESS", ctx):
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
                    mark_used = getattr(target_unit, "mark_infernal_fulgurite_used", None)
                    if callable(mark_used):
                        mark_used(
                            source=ability_name,
                            stratagem_name=str(getattr(stratagem, "name", "") or ""),
                        )
                except Exception:
                    pass
                return {
                    "base": base,
                    "discount": base,
                    "cost": cost,
                    "reasons": [f"{ability_name}: {stratagem_label} for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "infernal_fulgurite_use": True,
                    "infernal_fulgurite_source": ability_name,
                }

        grimnars_mark = self._preview_grimnars_mark_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if grimnars_mark:
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
            ctx = {
                "ability_name": "Grimnar's Mark",
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("GRIMNARS_MARK_STRATAGEM_DISCOUNT", ctx):
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
                    "grimnars_mark_use": True,
                }

        webway_awl = self._preview_webway_awl_rapid_ingress_discount(
            stratagem=stratagem,
            target_unit=target_unit,
        )
        if webway_awl:
            context = self._webway_awl_rapid_ingress_discount_context(
                target_unit,
                stratagem_name=self._normalize_stratagem_name_key(getattr(stratagem, "name", "") or ""),
            ) or {}
            ability_name = str(context.get("source", "") or "Webway Awl").strip() or "Webway Awl"
            ctx = {
                "ability_name": ability_name,
                "stratagem": getattr(stratagem, "name", None) or "",
                "target_unit": getattr(target_unit, "name", None) or "",
                "base_cp_cost": base,
            }
            if self._should_use_optional_ability("WEBWAY_AWL_RAPID_INGRESS", ctx):
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
                    "reasons": [f"{ability_name}: Rapid Ingress for 0CP."],
                    "increase": increase,
                    "increase_reasons": increase_reasons,
                    "webway_awl_rapid_ingress_use": True,
                    "webway_awl_rapid_ingress_source": ability_name,
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
                "beacon_angelis_use": True,
            }
        if heroic_intervention_used_this_phase:
            return {"denied": True, "reason": "Heroic Intervention already used this phase"}
        if rapid_ingress_used_this_phase:
            return {"denied": True, "reason": "Rapid Ingress already used this phase"}
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
        tsd_available, tsd_names, tsd_specs = self._preview_targeted_stratagem_cp_discount(
            target_unit=target_unit,
            stratagem=stratagem,
        )
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

        # Decide whether to apply datasheet Command Re-roll 0CP discount if available (e.g. Cherub).
        cherub_discount = int(
            self._preview_datasheet_command_reroll_discount(stratagem=stratagem, target_unit=target_unit) or 0
        )
        if cherub_discount and target_unit is not None:
            ability_name = "Cherub"
            try:
                get_rule = getattr(target_unit, "get_datasheet_command_reroll_stratagem_discount_rule", None)
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
            use_cherub = self._should_use_optional_ability("DATASHEET_COMMAND_REROLL_DISCOUNT", ctx)
            if use_cherub:
                command_reroll_repeat_bypass_used = True
                applied_discount += int(cherub_discount)
                reasons.append(f"{ability_name}: Command Re-roll for 0CP (used)")
                try:
                    mark_used = getattr(target_unit, "mark_datasheet_command_reroll_stratagem_discount_used", None)
                    if callable(mark_used):
                        mark_used(
                            self.game,
                            source=ability_name,
                            stratagem_name=str(getattr(stratagem, "name", "") or ""),
                        )
                except Exception:
                    pass

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
            if use_gof:
                command_reroll_repeat_bypass_used = True
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
            if use_mof:
                command_reroll_repeat_bypass_used = True
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

        if command_reroll_used_this_phase and not command_reroll_repeat_bypass_used:
            return {"denied": True, "reason": "Command Re-roll already used this phase"}

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

    def __str__(self):
        return f"Name: {self.name}\nControl: {self.control.name}\nCommand Points: {self.command_points}\nArmy: {self.army}"
