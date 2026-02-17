from __future__ import annotations

from typing import Any, Optional
import logging

from ..utility import dice as dice_module
from ..utility.entity_ids import maybe_entity_id

logger = logging.getLogger(__name__)


class ImperialKnightsStratagemMixin:
    @staticmethod
    def _ik_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _ik_sort_key(unit: Any) -> str:
        return str(maybe_entity_id(unit) or "")

    def _ik_detachment_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "imperial_knights_detachments", None)

    def _is_valourstrike_lance(self) -> bool:
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "is_valourstrike_lance", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _ik_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _ik_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _ik_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return True
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(unit, "is_in_reserves", False))

    def _ik_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._ik_is_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _is_imperial_knights_unit(self, unit: Any) -> bool:
        root = self._ik_root(unit)
        if root is None:
            return False
        mgr = self._ik_detachment_mgr()
        checker = getattr(mgr, "_unit_is_imperial_knights", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if callable(has_any_keyword):
            return bool(has_any_keyword("IMPERIAL KNIGHTS"))
        return str(getattr(root, "faction_id", "") or "").strip().upper() == "QI"

    def _imperial_knights_vow_of_retribution_candidates(self) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    @staticmethod
    def _ik_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    @staticmethod
    def _ik_selected_to_fight_this_phase(unit: Any) -> bool:
        return bool(getattr(getattr(unit, "round_state", None), "fought_this_phase", False))

    def _imperial_knights_full_tilt_candidates(self) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if self._ik_selected_to_move_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _imperial_knights_run_them_through_candidates(self) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            if self._ik_selected_to_fight_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    @staticmethod
    def _ik_normalize_weapon_name(value: str) -> str:
        name = str(value or "").replace("\u2019", "'").replace("\u0192?T", "'").strip().lower()
        return " ".join(name.split())

    @classmethod
    def _ik_is_feet_weapon_name(cls, value: str) -> bool:
        name = cls._ik_normalize_weapon_name(value)
        return ("armoured feet" in name) or ("titanic feet" in name)

    @staticmethod
    def _ik_model_is_alive(model: Any) -> bool:
        if model is None:
            return False
        checker = getattr(model, "is_alive", None)
        if callable(checker):
            return bool(checker())
        try:
            return int(getattr(model, "wounds", 1) or 0) > 0
        except (TypeError, ValueError):
            return True

    @classmethod
    def _ik_model_has_feet_melee_weapon(cls, model: Any) -> bool:
        for weapon in list(getattr(model, "wargear", []) or []):
            is_melee = getattr(weapon, "is_melee", None)
            if callable(is_melee):
                if not bool(is_melee()):
                    continue
            elif str(getattr(weapon, "type", "") or "").strip().lower() != "melee":
                continue
            if cls._ik_is_feet_weapon_name(getattr(weapon, "name", "")):
                return True
        return False

    def _ik_select_thunderstomp_model(self, unit: Any, *, requested_model: Any = None) -> Any:
        root = self._ik_root(unit)
        if root is None:
            return None
        models = list(getattr(root, "models", []) or [])
        if not models:
            return None
        if requested_model is not None:
            wanted_id = str(maybe_entity_id(requested_model) or "")
            for model in models:
                model_id = str(maybe_entity_id(model) or "")
                if model is not requested_model and (not wanted_id or not model_id or model_id != wanted_id):
                    continue
                if not self._ik_model_is_alive(model):
                    return None
                if not self._ik_model_has_feet_melee_weapon(model):
                    return None
                return model
            return None
        ordered_models = sorted(models, key=lambda m: str(maybe_entity_id(m) or ""))
        for model in ordered_models:
            if not self._ik_model_is_alive(model):
                continue
            if not self._ik_model_has_feet_melee_weapon(model):
                continue
            return model
        return None

    def _imperial_knights_thunderstomp_candidates(self) -> list[Any]:
        units = self._imperial_knights_run_them_through_candidates()
        out: list[Any] = []
        for root in list(units or []):
            if self._ik_select_thunderstomp_model(root) is None:
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    @staticmethod
    def _ik_unit_in_candidates(root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = str(maybe_entity_id(root) or "")
        for cand in list(candidates or []):
            cand_root = cand
            get_root = getattr(cand, "get_attached_unit_root", None)
            if callable(get_root):
                cand_root = get_root()
            if cand_root is root:
                return True
            cid = str(maybe_entity_id(cand_root) or "")
            if rid and cid and rid == cid:
                return True
        return False

    def _ik_distance_between_units(self, source_unit: Any, target_unit: Any) -> Optional[float]:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        get_dist = getattr(game_map, "get_distance_between_units", None) if game_map is not None else None
        if not callable(get_dist):
            return None
        source_root = self._ik_root(source_unit)
        target_root = self._ik_root(target_unit)
        if source_root is None or target_root is None:
            return None
        try:
            return float(get_dist(source_root, target_root))
        except (TypeError, ValueError):
            return None

    def _imperial_knights_tactical_foil_candidates(
        self,
        *,
        enemy_unit: Any,
        action: str = "",
    ) -> list[Any]:
        if not self._is_valourstrike_lance():
            return []
        if enemy_unit is None:
            return []
        action_key = str(action or "").strip().lower()
        if action_key and action_key not in {"move", "advance", "fall_back"}:
            return []
        enemy_root = self._ik_root(enemy_unit)
        if enemy_root is None:
            return []
        if self._ik_owned_by_player(enemy_root, self.player):
            return []
        if not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return []

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ik_root(unit)
            if root is None:
                continue
            uid = self._ik_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ik_owned_by_player(root, self.player):
                continue
            if not self._is_imperial_knights_unit(root):
                continue
            if not self._ik_on_battlefield(root, require_targetable=True):
                continue
            dist = self._ik_distance_between_units(root, enemy_root)
            if dist is None or float(dist) > 9.0 + 1e-6:
                continue
            out.append(root)
        return sorted(out, key=self._ik_sort_key)

    def _ik_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        enemy_unit: Any = None,
    ) -> bool:
        wanted_name = str(stratagem_name or "").strip().upper()
        wanted_phase = str(phase_name or "").strip().lower()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name):
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != wanted_name:
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != wanted_phase:
                continue
            if enemy_unit is not None and self._ik_root(reaction.get("enemy_unit")) is not self._ik_root(enemy_unit):
                continue
            return True
        return False

    def _queue_imperial_knights_valourstrike_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_valourstrike_lance():
            return
        if unit is None or self.game is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "fall_back"}:
            return
        enemy_root = self._ik_root(unit)
        if enemy_root is None:
            return
        if self._ik_owned_by_player(enemy_root, self.player):
            return
        if not self._ik_is_alive(enemy_root) or not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        stratagem = self.get_by_name("TACTICAL FOIL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if self._ik_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            enemy_unit=enemy_root,
        ):
            return

        candidates = self._imperial_knights_tactical_foil_candidates(enemy_unit=enemy_root, action=action_key)
        if not candidates:
            return

        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "action": action_key,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _ik_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return bool(
            self.player.spend_command_points(
                int(cp_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _ik_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u:
                used.add(name_u)

    def _use_imperial_knights_valourstrike_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "VOW OF RETRIBUTION":
            return self._use_valourstrike_vow_of_retribution(stratagem, **kwargs)
        if name_u == "FULL TILT":
            return self._use_valourstrike_full_tilt(stratagem, **kwargs)
        if name_u == "RUN THEM THROUGH!":
            return self._use_valourstrike_run_them_through(stratagem, **kwargs)
        if name_u == "THUNDERSTOMP":
            return self._use_valourstrike_thunderstomp(stratagem, **kwargs)
        if name_u == "TACTICAL FOIL":
            return self._use_valourstrike_tactical_foil(stratagem, **kwargs)
        return None

    def _use_valourstrike_vow_of_retribution(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: VOW OF RETRIBUTION: wrong phase")
            return False

        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: VOW OF RETRIBUTION: not your Shooting phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: VOW OF RETRIBUTION: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False

        candidates = self._imperial_knights_vow_of_retribution_candidates()
        if root not in candidates:
            logger.error(
                "ERROR: VOW OF RETRIBUTION: target must be an IMPERIAL KNIGHTS unit on the battlefield that has not shot"
            )
            return False

        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["vow_of_retribution_active"] = True
        sr["vow_of_retribution_expires_phase"] = "SHOOTING_PHASE"
        sr["vow_of_retribution_owner"] = str(getattr(self.player, "id", "") or "")
        sr["vow_of_retribution_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["vow_of_retribution_source"] = str(getattr(stratagem, "name", "") or "VOW OF RETRIBUTION")
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: VOW OF RETRIBUTION: {getattr(root, 'name', 'Unit')} gains Lethal Hits with ranged weapons this phase."
        )
        return True

    def _use_valourstrike_full_tilt(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: FULL TILT: wrong phase")
            return False

        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FULL TILT: not your Movement phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FULL TILT: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: FULL TILT: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: FULL TILT: target must be an IMPERIAL KNIGHTS unit")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: FULL TILT: target is not currently eligible")
            return False
        if self._ik_selected_to_move_this_phase(root):
            logger.error("ERROR: FULL TILT: target has already been selected to move this phase")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        from ..utility.modifiers import Modifier, ModifierOp

        root.remove_characteristic_modifiers_by_source("stratagem:imperial_knights_full_tilt")
        root.add_characteristic_modifier(
            "movement",
            Modifier(ModifierOp.ADD, 2, source="stratagem:imperial_knights_full_tilt"),
        )

        effect_tag = "stratagem:imperial_knights_full_tilt"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        adv_mods = list(sr.get("advance_roll_modifiers", []) or [])
        adv_mods = [
            entry
            for entry in adv_mods
            if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == effect_tag)
        ]
        adv_mods.append(
            {
                "value": 2,
                "source": str(getattr(stratagem, "name", "") or "FULL TILT"),
                "tag": effect_tag,
            }
        )
        sr["advance_roll_modifiers"] = adv_mods
        sr["full_tilt_active"] = True
        sr["full_tilt_expires_phase"] = "MOVEMENT_PHASE"
        sr["full_tilt_owner"] = str(getattr(self.player, "id", "") or "")
        sr["full_tilt_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["full_tilt_source"] = str(getattr(stratagem, "name", "") or "FULL TILT")
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: FULL TILT: %s gains +2\" Move and +2 to Advance rolls this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_valourstrike_run_them_through(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: RUN THEM THROUGH!: wrong phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RUN THEM THROUGH!: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: RUN THEM THROUGH!: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: RUN THEM THROUGH!: target must be an IMPERIAL KNIGHTS unit")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: RUN THEM THROUGH!: target is not currently eligible")
            return False
        if self._ik_selected_to_fight_this_phase(root):
            logger.error("ERROR: RUN THEM THROUGH!: target has already been selected to fight this phase")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_knights_run_them_through_active"] = True
        sr["imperial_knights_run_them_through_expires_phase"] = "FIGHT_PHASE"
        sr["imperial_knights_run_them_through_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["imperial_knights_run_them_through_source"] = str(getattr(stratagem, "name", "") or "RUN THEM THROUGH!")
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RUN THEM THROUGH!: %s gains [LANCE] on melee weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_valourstrike_thunderstomp(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: THUNDERSTOMP: wrong phase")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        model = kwargs.get("model") or kwargs.get("target_model")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and model is not None:
            unit = getattr(model, "parent_unit", None)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: THUNDERSTOMP: no target unit provided")
            return False

        root = self._ik_root(unit)
        if root is None:
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: THUNDERSTOMP: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: THUNDERSTOMP: target must be an IMPERIAL KNIGHTS model")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: THUNDERSTOMP: target is not currently eligible")
            return False
        if self._ik_selected_to_fight_this_phase(root):
            logger.error("ERROR: THUNDERSTOMP: target has already been selected to fight this phase")
            return False

        chosen_model = self._ik_select_thunderstomp_model(root, requested_model=model)
        if chosen_model is None:
            logger.error("ERROR: THUNDERSTOMP: selected model must be an IMPERIAL KNIGHTS model with armoured/titanic feet")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_knights_thunderstomp_active"] = True
        sr["imperial_knights_thunderstomp_expires_phase"] = "FIGHT_PHASE"
        sr["imperial_knights_thunderstomp_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game else 0
        sr["imperial_knights_thunderstomp_source"] = str(getattr(stratagem, "name", "") or "THUNDERSTOMP")
        sr["imperial_knights_thunderstomp_model_id"] = str(maybe_entity_id(chosen_model) or "")
        sr["imperial_knights_thunderstomp_armoured_feet_attacks"] = 8
        sr["imperial_knights_thunderstomp_titanic_feet_attacks"] = 12
        sr["imperial_knights_thunderstomp_ap_bonus"] = 1
        root.special_rules = sr

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: THUNDERSTOMP: %s gains enhanced Armoured/Titanic Feet profiles this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_valourstrike_tactical_foil(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_valourstrike_lance():
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("moving_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "TACTICAL FOIL":
                    continue
                from_pending = True
                unit = reaction.get("unit") or reaction.get("target_unit")
                enemy_unit = enemy_unit or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("action", reaction.get("action"))
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TACTICAL FOIL: no target unit provided")
            return False

        root = self._ik_root(unit)
        enemy_root = self._ik_root(enemy_unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: TACTICAL FOIL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: TACTICAL FOIL: not opponent's Movement phase")
            return False
        action_key = str(kwargs.get("action") or kwargs.get("trigger") or "").strip().lower()
        if action_key and action_key not in {"move", "advance", "fall_back"}:
            logger.error("ERROR: TACTICAL FOIL: invalid trigger action")
            return False
        if candidates and not self._ik_unit_in_candidates(root, candidates):
            logger.error("ERROR: TACTICAL FOIL: target is not currently eligible")
            return False
        if not self._ik_owned_by_player(root, self.player):
            logger.error("ERROR: TACTICAL FOIL: target unit is not yours")
            return False
        if not self._ik_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_imperial_knights_unit(root):
            logger.error("ERROR: TACTICAL FOIL: target must be an IMPERIAL KNIGHTS unit")
            return False
        if enemy_root is None:
            logger.error("ERROR: TACTICAL FOIL: missing enemy trigger unit")
            return False
        if self._ik_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: TACTICAL FOIL: trigger unit is not enemy")
            return False
        if not self._ik_on_battlefield(enemy_root, require_targetable=False):
            return False
        dist = self._ik_distance_between_units(root, enemy_root)
        if dist is None or float(dist) > 9.0 + 1e-6:
            logger.error("ERROR: TACTICAL FOIL: target must be within 9\" of the enemy unit")
            return False
        if not from_pending and not action_key:
            logger.error("ERROR: TACTICAL FOIL: missing movement trigger context")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: TACTICAL FOIL: reactive move queue is unavailable")
            return False
        if not self._ik_spend_cp(stratagem, target_unit=root):
            return False

        move_max = max(0, int(dice_module.get_roll("D6") or 0))
        req = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(move_max),
            kind="tactical_foil",
            movement_type="reactive",
            source=stratagem.name,
            moving_unit=enemy_root,
        )
        if req is None:
            logger.error("ERROR: TACTICAL FOIL: failed to queue reactive move")
            return False

        self._ik_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TACTICAL FOIL: %s can make a Normal move up to %d\".",
            getattr(root, "name", "Unit"),
            int(move_max),
        )
        return True
