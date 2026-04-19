from __future__ import annotations

from typing import Any

from ..utility.entity_ids import get_entity_id


def initialize_player_resource_state(player) -> None:
    player.command_points = 0
    player.cp_history = []
    player.cp_gained_this_battle_round_excluding_normal_command_cp = 0
    player._cp_gain_guardrail_battle_round = None
    player._ability_used_battle_round = {}
    player._ability_used_turn = {}
    player._ability_used_phase = {}
    player._next_optional_decisions = {}
    player._next_optional_selections = {}
    player.optional_decision_hook = None
    player.reactive_move_position_hook = None
    player._pending_stratagem_target_unit_id = ""
    player._pending_stratagem_name = ""


class PlayerResourceMixin:
    def _sync_cp_gain_guardrail_battle_round(self) -> None:
        """Reset per-battle-round CP gain guardrail counter when battle round advances."""
        game = getattr(self, "game", None)
        br = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        if br <= 0:
            return
        if self._cp_gain_guardrail_battle_round != br:
            self._cp_gain_guardrail_battle_round = br
            self.cp_gained_this_battle_round_excluding_normal_command_cp = 0

    def gain_command_points(
        self,
        amount: int = 1,
        *,
        is_normal_command_phase_gain: bool = False,
        exempt_from_guardrail: bool = False,
        reason: str | None = None,
        source: str | None = None,
    ) -> int:
        """
        Gain command points, enforcing the core CP gain guardrail:
        - The normal +1CP at the start of your own Command phase is always allowed and does not count.
        - All other CP gains are limited to a maximum of +1 CP per battle round unless exempt.

        Returns the number of CP actually gained (may be less than requested).
        """
        amount = int(amount or 0)
        if amount <= 0:
            return 0

        self._sync_cp_gain_guardrail_battle_round()

        gain_reason = str(reason or "").strip() or "Command Points gained"
        gain_source = str(source or "").strip().lower()
        recorded_source = gain_source if gain_source else "gain"
        gained = 0

        if is_normal_command_phase_gain:
            gained = int(amount)
            self.command_points += gained
            self._record_cp_change(
                gained,
                reason=reason or "Normal Command phase CP",
                source=(recorded_source if gain_source else "normal_command_phase"),
            )
        elif exempt_from_guardrail:
            gained = int(amount)
            self.command_points += gained
            self._record_cp_change(gained, reason=gain_reason, source=recorded_source)
        else:
            if int(self.cp_gained_this_battle_round_excluding_normal_command_cp or 0) >= 1:
                return 0

            gained = min(int(amount), 1)
            self.command_points += gained
            self.cp_gained_this_battle_round_excluding_normal_command_cp += 1
            self._record_cp_change(gained, reason=gain_reason, source=recorded_source)

        if gained > 0:
            self._maybe_trigger_opponent_cp_gain_reactions(
                gained=gained,
                reason=gain_reason,
                source=gain_source,
                is_normal_command_phase_gain=bool(is_normal_command_phase_gain),
            )
        return int(gained)

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
        return self.gain_command_points(
            self.get_normal_command_phase_cp_gain(),
            is_normal_command_phase_gain=True,
            reason="Normal Command phase CP",
        )

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

    def _cp_gain_source_counts_as_ability(
        self,
        *,
        source: str,
        reason: str,
        is_normal_command_phase_gain: bool,
    ) -> bool:
        if bool(is_normal_command_phase_gain):
            return False
        source_key = str(source or "").strip().lower()
        if source_key == "gain":
            source_key = ""
        non_ability_sources = {
            "normal_command_phase",
            "mission",
            "mission_rule",
            "secondary",
            "secondary_discard",
            "objective",
        }
        if source_key in non_ability_sources:
            return False
        if source_key:
            return True
        reason_key = str(reason or "").strip().lower()
        if "normal command phase cp" in reason_key:
            return False
        if "discard secondary" in reason_key:
            return False
        return bool(reason_key)

    def _opponent_cp_gain_reaction_specs(self) -> list[dict[str, Any]]:
        army = self.get_army()
        if army is None:
            return []
        specs: list[dict[str, Any]] = []
        seen_roots: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            if root is None or not self._unit_is_alive_or_unknown(root):
                continue
            root_id = str(get_entity_id(root) or "")
            if root_id and root_id in seen_roots:
                continue
            if root_id:
                seen_roots.add(root_id)
            members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else []
            if not members:
                members = [root]
            members = sorted(members, key=lambda member: str(get_entity_id(member) or ""))
            for member in members:
                special_rules = getattr(member, "special_rules", None)
                if not isinstance(special_rules, dict):
                    continue
                for raw_spec in list(special_rules.get("opponent_ability_cp_gain_reaction_specs", []) or []):
                    if not isinstance(raw_spec, dict):
                        continue
                    source_model_id = str(raw_spec.get("source_model_id", "") or "").strip()
                    if source_model_id and not self._unit_has_alive_model_id(root, source_model_id):
                        continue
                    spec = dict(raw_spec)
                    spec["source_unit_id"] = root_id
                    specs.append(spec)
        seen_specs: set[tuple[str, str, str, int, int]] = set()
        deduped_specs: list[dict[str, Any]] = []
        for spec in specs:
            key = (
                str(spec.get("source_unit_id", "") or "").strip(),
                str(spec.get("source_model_id", "") or "").strip(),
                str(spec.get("name", "") or "").strip().lower(),
                int(spec.get("roll_min", 0) or 0),
                int(spec.get("cp_gain", 0) or 0),
            )
            if key in seen_specs:
                continue
            seen_specs.add(key)
            deduped_specs.append(spec)
        deduped_specs.sort(
            key=lambda item: (
                str(item.get("name", "") or "").strip().lower(),
                str(item.get("source_unit_id", "") or "").strip(),
                str(item.get("source_model_id", "") or "").strip(),
                int(item.get("roll_min", 0) or 0),
                int(item.get("cp_gain", 0) or 0),
            )
        )
        return deduped_specs
