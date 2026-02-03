from __future__ import annotations

from typing import Iterable, Optional

from .detachment_manager import DetachmentManagerBase
from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id


class ChaosKnightsDetachmentManager(DetachmentManagerBase):
    faction_id = "QT"

    MALEFIC_SURGE_NAME = "Malefic Surge"
    DETACHMENT_INFERNAL_LANCE = "Infernal Lance"

    def __init__(self, army=None):
        super().__init__(army)
        self._malefic_surge_declined_turn: Optional[int] = None
        self._malefic_surge_declined_owner: str = ""

    def is_infernal_lance(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_INFERNAL_LANCE)

    def _unit_is_chaos_knights(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "has_any_keyword") and unit.has_any_keyword("CHAOS KNIGHTS"):
                return True
        except Exception:
            pass
        try:
            for kw in list(getattr(unit, "faction_keywords", []) or []):
                if str(kw or "").strip().upper() == "CHAOS KNIGHTS":
                    return True
        except Exception:
            pass
        try:
            return str(getattr(unit, "faction", "") or "").strip().upper() == "QT"
        except Exception:
            return False

    def _unit_on_battlefield(self, unit) -> bool:
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
            pass
        try:
            if hasattr(unit, "is_in_reserves") and callable(unit.is_in_reserves) and unit.is_in_reserves():
                return False
            if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
                return False
        except Exception:
            pass
        return True

    def _current_turn_key(self, game=None) -> int:
        try:
            return int(getattr(game, "turn", 0) or 0)
        except Exception:
            return 0

    def _current_owner_id(self, unit=None, game=None) -> str:
        if unit is not None:
            try:
                army = unit.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
                return str(getattr(player, "id", "") or "")
            except Exception:
                return ""
        if game is not None:
            try:
                player = game.get_current_player()
                return str(getattr(player, "id", "") or "")
            except Exception:
                return ""
        return ""

    def _unit_sr(self, unit) -> dict:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        return sr

    def is_unit_empowered(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        sr = self._unit_sr(unit)
        if not sr.get("malefic_surge_empowered"):
            return False
        owner = str(sr.get("malefic_surge_empowered_owner", "") or "")
        if owner:
            current = self._current_owner_id(unit=unit, game=game)
            if current and owner != current:
                return False
        return True

    def unit_used_malefic_surge_this_turn(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        sr = self._unit_sr(unit)
        owner = str(sr.get("malefic_surge_last_owner", "") or "")
        if owner:
            current = self._current_owner_id(unit=unit, game=game)
            if current and owner != current:
                return False
        try:
            return int(sr.get("malefic_surge_last_turn", -1) or -1) == int(self._current_turn_key(game))
        except Exception:
            return False

    def can_unit_malefic_surge(self, unit, *, game=None, ignore_used: bool = False) -> bool:
        if unit is None:
            return False
        if not self.is_infernal_lance():
            return False
        if not self._unit_is_chaos_knights(unit):
            return False
        if not self._unit_on_battlefield(unit):
            return False
        if not ignore_used and self.unit_used_malefic_surge_this_turn(unit, game=game):
            return False
        return True

    def _mark_empowered(self, unit, *, game=None, source: str = "") -> None:
        sr = self._unit_sr(unit)
        sr["malefic_surge_empowered"] = True
        sr["malefic_surge_empowered_turn"] = int(self._current_turn_key(game))
        sr["malefic_surge_empowered_owner"] = self._current_owner_id(unit=unit, game=game)
        if source:
            sr["malefic_surge_source"] = str(source or "").strip()
        unit.special_rules = sr

    def _mark_used(self, unit, *, game=None, choice: str | None = None) -> None:
        sr = self._unit_sr(unit)
        sr["malefic_surge_last_turn"] = int(self._current_turn_key(game))
        sr["malefic_surge_last_owner"] = self._current_owner_id(unit=unit, game=game)
        if choice:
            sr["malefic_surge_last_choice"] = str(choice or "").strip()
        for key in (
            "malefic_surge_empowered",
            "malefic_surge_empowered_turn",
            "malefic_surge_empowered_owner",
            "malefic_surge_source",
        ):
            sr.pop(key, None)
        unit.special_rules = sr

    def clear_empowered_at_command_phase_start(self, *, game=None, player=None) -> None:
        if not self.is_infernal_lance():
            return
        if self.army is None:
            return
        current_turn = int(self._current_turn_key(game))
        current_owner = str(getattr(player, "id", "") or "") if player is not None else ""
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("malefic_surge_empowered"):
                continue
            owner = str(sr.get("malefic_surge_empowered_owner", "") or "")
            if current_owner and owner and owner != current_owner:
                continue
            try:
                emp_turn = int(sr.get("malefic_surge_empowered_turn", -1) or -1)
            except Exception:
                emp_turn = -1
            if emp_turn >= 0 and emp_turn == current_turn:
                continue
            for key in (
                "malefic_surge_empowered",
                "malefic_surge_empowered_turn",
                "malefic_surge_empowered_owner",
                "malefic_surge_source",
            ):
                sr.pop(key, None)
            sr.pop("malefic_surge_choice_pending", None)
            unit.special_rules = sr
        if player is not None:
            self._malefic_surge_declined_turn = None
            self._malefic_surge_declined_owner = ""

    def _declined_this_turn(self, player=None, game=None) -> bool:
        if player is None:
            return False
        if self._malefic_surge_declined_turn is None:
            return False
        try:
            if int(self._malefic_surge_declined_turn) != int(self._current_turn_key(game)):
                return False
        except Exception:
            return False
        return str(self._malefic_surge_declined_owner or "") == str(getattr(player, "id", "") or "")

    def record_declined(self, *, player=None, game=None) -> None:
        if player is None:
            return
        self._malefic_surge_declined_turn = int(self._current_turn_key(game))
        self._malefic_surge_declined_owner = str(getattr(player, "id", "") or "")

    def get_malefic_surge_candidates(self, *, game=None) -> list:
        if self.army is None or not self.is_infernal_lance():
            return []
        units = []
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            if root in units:
                continue
            if not self.can_unit_malefic_surge(root, game=game):
                continue
            units.append(root)
        units.sort(key=lambda u: str(getattr(u, "name", "")))
        return units

    def prompt_malefic_surge_selection(self, *, game=None, player=None) -> None:
        if game is None or player is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not self.is_infernal_lance():
            return
        if self._declined_this_turn(player=player, game=game):
            return
        candidates = self.get_malefic_surge_candidates(game=game)
        if not candidates:
            return
        from ..engine.decision_kinds import DECISION_CHOOSE_MALEFIC_SURGE_UNIT
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_MALEFIC_SURGE_UNIT:
                    continue
                if str(getattr(req, "player_id", "") or "") == str(getattr(player, "id", "") or ""):
                    return

        options = []
        for unit in candidates:
            options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"unit_id": get_entity_id(unit)},
                )
            )
        options.append(
            DecisionOption.create(
                "None",
                payload={"skip": True, "action": "skip", "summary": "Do not select additional units."},
            )
        )
        ctx = {
            "ability": "malefic_surge",
            "ability_name": self.MALEFIC_SURGE_NAME,
            "battle_round": self._current_turn_key(game),
        }
        req = DecisionRequest.create(
            DECISION_CHOOSE_MALEFIC_SURGE_UNIT,
            "Select a unit to make a Malefic Surge (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        game.request_decision(req)

    def apply_malefic_surge(self, unit, *, game=None, ignore_used: bool = False) -> dict:
        if unit is None:
            return {"ok": False, "reason": "unit missing"}
        if not self.can_unit_malefic_surge(unit, game=game, ignore_used=ignore_used):
            return {"ok": False, "reason": "unit not eligible"}
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return {"ok": False, "reason": "unit missing"}
        extra_rerolls = []
        try:
            sr = self._unit_sr(root)
            if sr.get("enhancement_blasphemous_engine"):
                extra_rerolls.append("Blasphemous Engine")
        except Exception:
            extra_rerolls = []
        passed = bool(
            getattr(root, "pass_leadership_check", lambda **_k: True)(
                extra_reroll_sources=extra_rerolls,
                reroll_reason="Malefic Surge",
            )
        )
        if not passed:
            try:
                mortal = int(get_roll("D3") or 0)
            except Exception:
                mortal = 0
            if mortal <= 0:
                mortal = 1
            try:
                root._apply_mortal_wounds_to_unit(root, mortal, game_map=getattr(game, "map", None))
            except Exception:
                pass
        self._mark_empowered(root, game=game, source=self.MALEFIC_SURGE_NAME)
        try:
            if game is not None and hasattr(game, "event_system"):
                army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                player = getattr(army, "player", None) if army is not None else None
                game.event_system.publish(
                    "malefic_surge_applied",
                    unit=root,
                    player=player,
                    game=game,
                )
        except Exception:
            pass
        return {"ok": True, "passed": passed}

    def queue_malefic_surge_choice(self, unit, *, trigger: str, game=None) -> None:
        if unit is None or game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not self.is_infernal_lance():
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not self.is_unit_empowered(root, game=game):
            return
        sr = self._unit_sr(root)
        if sr.get("malefic_surge_choice_pending"):
            return
        from ..engine.decision_kinds import DECISION_CHOOSE_MALEFIC_SURGE_ABILITY
        from ..engine.decisions import DecisionOption, DecisionRequest

        trigger_key = str(trigger or "").strip().lower()
        if not trigger_key:
            return

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_MALEFIC_SURGE_ABILITY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("unit_id", "")) == str(get_entity_id(root)) and str(ctx.get("trigger", "")) == trigger_key:
                    return

        options = []
        header = "Select a Malefic Surge ability."
        if trigger_key == "movement":
            options.append(
                DecisionOption.create(
                    "Unholy Hunger",
                    payload={"choice": "UNHOLY_HUNGER", "summary": "Until end of phase, add 3\" to Move."},
                )
            )
            header = "Use Unholy Hunger for this move?"
        elif trigger_key in ("shooting", "fight"):
            options.append(
                DecisionOption.create(
                    "Lethal Hits",
                    payload={"choice": "LETHAL_HITS", "summary": "Weapons gain [LETHAL HITS] until end of phase."},
                )
            )
            options.append(
                DecisionOption.create(
                    "Sustained Hits 1",
                    payload={"choice": "SUSTAINED_HITS_1", "summary": "Weapons gain [SUSTAINED HITS 1] until end of phase."},
                )
            )
            header = "Select Diabolic Power ability."
        elif trigger_key in ("targeted_shooting", "targeted_fight"):
            options.append(
                DecisionOption.create(
                    "5+ Invulnerable Save",
                    payload={"choice": "INVULN_5", "summary": "Models gain a 5+ invulnerable save until end of phase."},
                )
            )
            options.append(
                DecisionOption.create(
                    "Feel No Pain 6+",
                    payload={"choice": "FNP_6", "summary": "Models gain Feel No Pain 6+ until end of phase."},
                )
            )
            header = "Select Unnatural Fortitude effect."
        else:
            return
        options.append(
            DecisionOption.create(
                "Skip",
                payload={"skip": True, "action": "skip", "summary": "Do not use Malefic Surge now."},
            )
        )
        player = None
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        ctx = {
            "ability": "malefic_surge",
            "ability_name": self.MALEFIC_SURGE_NAME,
            "unit_id": get_entity_id(root),
            "trigger": trigger_key,
        }
        req = DecisionRequest.create(
            DECISION_CHOOSE_MALEFIC_SURGE_ABILITY,
            header,
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        sr["malefic_surge_choice_pending"] = True
        root.special_rules = sr
        game.request_decision(req)

    def apply_malefic_surge_choice(self, unit, *, trigger: str, choice: str, game=None) -> bool:
        if unit is None or game is None:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return False
        if not self.is_unit_empowered(root, game=game):
            return False
        trigger_key = str(trigger or "").strip().lower()
        choice_key = str(choice or "").strip().upper()
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if not phase_name:
            phase_name = "SHOOTING_PHASE"
        if trigger_key == "movement" and choice_key == "UNHOLY_HUNGER":
            self._apply_unholy_hunger(root, phase_name=phase_name)
            try:
                if bool(getattr(game, "is_authoritative", True)):
                    from ..engine.decision_handlers.movement import _maybe_request_move_modifier_choice
                    _maybe_request_move_modifier_choice(game, root, action_type="move")
            except Exception:
                pass
        elif trigger_key in ("shooting", "fight") and choice_key in ("LETHAL_HITS", "SUSTAINED_HITS_1"):
            attack_type = "ranged" if trigger_key == "shooting" else "melee"
            self._apply_diabolic_power(root, choice_key, attack_type=attack_type, phase_name=phase_name)
        elif trigger_key in ("targeted_shooting", "targeted_fight") and choice_key in ("INVULN_5", "FNP_6"):
            self._apply_unnatural_fortitude(root, choice_key, phase_name=phase_name)
        else:
            return False
        self._mark_used(root, game=game, choice=choice_key)
        sr = self._unit_sr(root)
        sr.pop("malefic_surge_choice_pending", None)
        root.special_rules = sr
        return True

    def clear_pending_choice(self, unit) -> None:
        if unit is None:
            return
        sr = self._unit_sr(unit)
        sr.pop("malefic_surge_choice_pending", None)
        unit.special_rules = sr

    def _apply_unholy_hunger(self, unit, *, phase_name: str) -> None:
        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        for model in list(models or []):
            if model is None or not getattr(model, "is_alive", True):
                continue
            if not isinstance(getattr(model, "_temporary_effects", None), dict):
                model._temporary_effects = {}
            key = f"malefic_surge_unholy_hunger:{get_entity_id(model)}".strip().lower()
            model._temporary_effects[key] = {
                "expires_phase": str(phase_name or "").strip().upper(),
                "movement_bonus": 3,
                "movement_bonus_source": "Unholy Hunger",
            }
        sr = self._unit_sr(unit)
        sr["malefic_surge_unholy_hunger_active"] = True
        sr["malefic_surge_unholy_hunger_expires_phase"] = str(phase_name or "").strip().upper()
        sr["malefic_surge_unholy_hunger_source"] = self.MALEFIC_SURGE_NAME
        unit.special_rules = sr

    def _apply_diabolic_power(self, unit, choice: str, *, attack_type: str, phase_name: str) -> None:
        sr = self._unit_sr(unit)
        sr["malefic_surge_diabolic_active"] = True
        sr["malefic_surge_diabolic_choice"] = str(choice or "").strip().upper()
        sr["malefic_surge_diabolic_attack_type"] = str(attack_type or "").strip().lower()
        sr["malefic_surge_diabolic_expires_phase"] = str(phase_name or "").strip().upper()
        sr["malefic_surge_diabolic_source"] = self.MALEFIC_SURGE_NAME
        unit.special_rules = sr

    def _apply_unnatural_fortitude(self, unit, choice: str, *, phase_name: str) -> None:
        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        for model in list(models or []):
            if model is None or not getattr(model, "is_alive", True):
                continue
            if choice == "INVULN_5":
                setter = getattr(model, "set_temporary_invulnerable_save", None)
                if callable(setter):
                    setter(
                        key=f"malefic_surge_invuln:{get_entity_id(model)}",
                        value=5,
                        source="Unnatural Fortitude",
                        expires_phase=str(phase_name or "").strip().upper(),
                    )
            elif choice == "FNP_6":
                setter = getattr(model, "set_temporary_fnp", None)
                if callable(setter):
                    setter(
                        key=f"malefic_surge_fnp:{get_entity_id(model)}",
                        value=6,
                        source="Unnatural Fortitude",
                        expires_phase=str(phase_name or "").strip().upper(),
                    )
        sr = self._unit_sr(unit)
        sr["malefic_surge_unnatural_fortitude_active"] = True
        sr["malefic_surge_unnatural_fortitude_expires_phase"] = str(phase_name or "").strip().upper()
        sr["malefic_surge_unnatural_fortitude_source"] = self.MALEFIC_SURGE_NAME
        if sr.get("enhancement_fleshmetal_fusion"):
            sr["fleshmetal_fusion_fortitude_active"] = True
            sr["fleshmetal_fusion_fortitude_expires_phase"] = str(phase_name or "").strip().upper()
            sr["fleshmetal_fusion_fortitude_source"] = "Fleshmetal Fusion"
        unit.special_rules = sr
