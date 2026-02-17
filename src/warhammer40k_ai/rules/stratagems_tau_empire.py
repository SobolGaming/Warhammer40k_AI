from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class TauEmpireStratagemMixin:
    @staticmethod
    def _tau_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _tau_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "")

    def _tau_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "tau_empire_detachments", None)

    def _is_tau_experimental_prototype_cadre_detachment(self) -> bool:
        mgr = self._tau_detachment_mgr()
        checker = getattr(mgr, "is_experimental_prototype_cadre", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _tau_has_any_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and has_any(keyword):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and has_kw(keyword):
            return True
        return False

    def _is_tau_empire_unit(self, unit: Any) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        mgr = self._tau_detachment_mgr()
        checker = getattr(mgr, "_unit_is_tau_empire", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if faction_id == "TAU":
            return True
        if self._tau_has_any_keyword(root, "T'AU EMPIRE"):
            return True
        if self._tau_has_any_keyword(root, "T\u2019AU EMPIRE"):
            return True
        if self._tau_has_any_keyword(root, "TAU EMPIRE"):
            return True
        return False

    def _is_tau_battlesuit_unit(self, unit: Any) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        if not self._is_tau_empire_unit(root):
            return False
        return self._tau_has_any_keyword(root, "BATTLESUIT")

    @staticmethod
    def _tau_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    def _tau_owned_by_player(self, unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(army, "player", None) is player

    def _tau_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        if not self._tau_is_alive(root):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        if getattr(root, "embarked_in", None) is not None:
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _tau_unit_models(self, unit: Any) -> list[Any]:
        root = self._tau_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else []
        if not models:
            models = list(getattr(root, "models", []) or [])
        return sorted(models, key=self._tau_sort_key)

    @staticmethod
    def _tau_model_is_alive(model: Any) -> bool:
        if model is None:
            return False
        alive_attr = getattr(model, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    @staticmethod
    def _tau_model_missing_wounds(model: Any) -> int:
        if model is None:
            return 0
        base = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
        current = int(getattr(model, "wounds", 0) or 0)
        return max(0, int(base - current))

    def _tau_model_is_battlesuit(self, model: Any, *, parent_unit: Any = None) -> bool:
        if model is None:
            return False
        if self._tau_has_any_keyword(model, "BATTLESUIT"):
            return True
        root = self._tau_root(parent_unit) if parent_unit is not None else None
        if root is not None and self._tau_has_any_keyword(root, "BATTLESUIT"):
            return True
        parent = getattr(model, "parent_unit", None)
        return bool(parent is not None and self._tau_has_any_keyword(parent, "BATTLESUIT"))

    def _tau_wounded_battlesuit_models(self, unit: Any) -> list[Any]:
        root = self._tau_root(unit)
        if root is None:
            return []
        out: list[Any] = []
        for model in self._tau_unit_models(root):
            if not self._tau_model_is_alive(model):
                continue
            if not self._tau_model_is_battlesuit(model, parent_unit=root):
                continue
            if self._tau_model_missing_wounds(model) <= 0:
                continue
            out.append(model)
        return sorted(out, key=self._tau_sort_key)

    def _tau_unit_in_candidates(self, root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = self._tau_sort_key(root)
        for candidate in list(candidates or []):
            cand_root = self._tau_root(candidate)
            if cand_root is None:
                continue
            if cand_root is root:
                return True
            if rid and self._tau_sort_key(cand_root) == rid:
                return True
        return False

    def _tau_resolve_selected_model(self, selection: Any, models: list[Any]) -> Any:
        if selection is None:
            return None
        for model in list(models or []):
            if model is selection:
                return model
        selected_id = str(get_entity_id(selection) or selection or "")
        if not selected_id:
            return None
        for model in list(models or []):
            if str(get_entity_id(model) or "") == selected_id:
                return model
        return None

    def _tau_automated_repair_drones_candidates(self) -> list[Any]:
        if not self._is_tau_experimental_prototype_cadre_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_battlesuit_unit(root):
                continue
            if not self._tau_wounded_battlesuit_models(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    @staticmethod
    def _tau_has_shot_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "shot_this_round", False))

    def _tau_phase_effect_active(
        self,
        unit: Any,
        *,
        active_keys: tuple[str, ...],
        owner_keys: tuple[str, ...] = (),
        turn_keys: tuple[str, ...] = (),
        phase_keys: tuple[str, ...] = (),
        default_phase: str = "",
    ) -> bool:
        root = self._tau_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not any(bool(sr.get(key)) for key in tuple(active_keys or ())):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        if owner_id:
            effect_owner = ""
            for key in tuple(owner_keys or ()):
                value = str(sr.get(key, "") or "").strip()
                if value:
                    effect_owner = value
                    break
            if effect_owner and effect_owner != owner_id:
                return False

        game = getattr(self, "game", None)
        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        effect_turn = 0
        for key in tuple(turn_keys or ()):
            try:
                val = int(sr.get(key, 0) or 0)
            except (TypeError, ValueError):
                val = 0
            if val:
                effect_turn = val
                break
        if effect_turn and current_turn and effect_turn != current_turn:
            return False

        current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        effect_phase = ""
        for key in tuple(phase_keys or ()):
            value = str(sr.get(key, "") or "").strip().upper()
            if value:
                effect_phase = value
                break
        if not effect_phase:
            effect_phase = str(default_phase or "").strip().upper()
        if effect_phase and current_phase and effect_phase != current_phase:
            return False
        return True

    def _tau_threat_assessment_analyser_active(self, unit: Any) -> bool:
        return self._tau_phase_effect_active(
            unit,
            active_keys=(
                "tau_threat_assessment_analyser_active",
                "threat_assessment_analyser_active",
                "threat_assessment_analyzer_active",
            ),
            owner_keys=(
                "tau_threat_assessment_analyser_owner",
                "tau_threat_assessment_analyser_turn_owner",
                "threat_assessment_analyser_owner",
                "threat_assessment_analyser_turn_owner",
                "threat_assessment_analyzer_owner",
                "threat_assessment_analyzer_turn_owner",
            ),
            turn_keys=(
                "tau_threat_assessment_analyser_turn",
                "threat_assessment_analyser_turn",
                "threat_assessment_analyzer_turn",
            ),
            phase_keys=(
                "tau_threat_assessment_analyser_phase",
                "tau_threat_assessment_analyser_expires_phase",
                "threat_assessment_analyser_phase",
                "threat_assessment_analyser_expires_phase",
                "threat_assessment_analyzer_phase",
                "threat_assessment_analyzer_expires_phase",
            ),
            default_phase="SHOOTING_PHASE",
        )

    def _tau_experimental_ammunition_candidates(self) -> list[Any]:
        if not self._is_tau_experimental_prototype_cadre_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tau_root(unit)
            if root is None:
                continue
            uid = self._tau_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tau_owned_by_player(root, self.player):
                continue
            if not self._tau_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tau_empire_unit(root):
                continue
            if self._tau_has_shot_this_phase(root):
                continue
            if self._tau_threat_assessment_analyser_active(root):
                continue
            out.append(root)
        return sorted(out, key=self._tau_sort_key)

    @staticmethod
    def _tau_parse_experimental_ammunition_mode(raw_mode: Any) -> Optional[str]:
        mode = raw_mode
        if isinstance(mode, dict):
            mode = (
                mode.get("mode")
                or mode.get("choice")
                or mode.get("selection")
                or mode.get("effect")
                or mode.get("option")
            )
        mode_key = str(mode or "").strip().lower().replace("_", " ").replace("-", " ")
        mode_key = " ".join(mode_key.split())
        if not mode_key:
            return "strength"
        strength_modes = {
            "strength",
            "strength only",
            "s",
            "option 1",
            "1",
            "basic",
        }
        hazardous_modes = {
            "strength ap hazardous",
            "strength and ap hazardous",
            "strength ap",
            "ap hazardous",
            "hazardous",
            "high output",
            "option 2",
            "2",
        }
        if mode_key in strength_modes:
            return "strength"
        if mode_key in hazardous_modes:
            return "hazardous"
        return None

    def _tau_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        effective_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        preview_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(preview_fn):
            preview = preview_fn(stratagem, target_unit=target_unit) or {}
            effective_cost = int(preview.get("cost", effective_cost))
        return bool(
            self.player.spend_command_points(
                int(effective_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _tau_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            raw_name = str(getattr(stratagem, "name", "") or "").strip().upper()
            if raw_name:
                used.add(raw_name)

    def _use_tau_experimental_prototype_cadre_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_tau_experimental_prototype_cadre_detachment():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "AUTOMATED REPAIR DRONES":
            return self._use_tau_automated_repair_drones(stratagem, **kwargs)
        if name_u == "EXPERIMENTAL AMMUNITION":
            return self._use_tau_experimental_ammunition(stratagem, **kwargs)
        return None

    def _use_tau_experimental_ammunition(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_empire_unit(root):
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: target must be a T'AU EMPIRE unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: not your Shooting phase")
            return False

        eligible = candidates or self._tau_experimental_ammunition_candidates()
        if eligible and not self._tau_unit_in_candidates(root, eligible):
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: target is not currently eligible")
            return False
        if self._tau_has_shot_this_phase(root):
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: target has already been selected to shoot")
            return False
        if self._tau_threat_assessment_analyser_active(root):
            logger.error(
                "ERROR: EXPERIMENTAL AMMUNITION: target unit cannot also be targeted by THREAT ASSESSMENT ANALYSER in this phase"
            )
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: cannot be used in current state")
            return False

        mode = self._tau_parse_experimental_ammunition_mode(
            kwargs.get("mode")
            or kwargs.get("experimental_ammunition_mode")
            or kwargs.get("choice")
            or kwargs.get("selection")
            or kwargs.get("effect")
        )
        if mode is None:
            logger.error("ERROR: EXPERIMENTAL AMMUNITION: invalid mode selection")
            return False

        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        hazardous = mode == "hazardous"
        ap_bonus = 1 if hazardous else 0
        source_name = str(getattr(stratagem, "name", "") or "EXPERIMENTAL AMMUNITION")
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tau_experimental_ammunition_active"] = True
        sr["tau_experimental_ammunition_strength_bonus"] = 1
        sr["tau_experimental_ammunition_ap_bonus"] = int(ap_bonus)
        sr["tau_experimental_ammunition_ranged_hazardous"] = bool(hazardous)
        sr["tau_experimental_ammunition_expires_phase"] = "SHOOTING_PHASE"
        sr["tau_experimental_ammunition_turn_owner"] = owner_id
        sr["tau_experimental_ammunition_turn"] = int(current_turn)
        sr["tau_experimental_ammunition_source"] = source_name
        # Marker used for same-phase incompatibility checks versus THREAT ASSESSMENT ANALYSER.
        sr["tau_experimental_ammunition_phase_active"] = True
        sr["tau_experimental_ammunition_phase_owner"] = owner_id
        sr["tau_experimental_ammunition_phase_turn"] = int(current_turn)
        sr["tau_experimental_ammunition_phase"] = "SHOOTING_PHASE"
        root.special_rules = sr

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if hazardous:
            logger.info(
                "INFO: EXPERIMENTAL AMMUNITION: %s gains +1 Strength, +1 AP, and [HAZARDOUS] on ranged weapons this phase.",
                getattr(root, "name", "Unit"),
            )
        else:
            logger.info(
                "INFO: EXPERIMENTAL AMMUNITION: %s gains +1 Strength on ranged weapons this phase.",
                getattr(root, "name", "Unit"),
            )
        return True

    def _use_tau_automated_repair_drones(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: AUTOMATED REPAIR DRONES: no target unit provided")
            return False

        root = self._tau_root(target_unit)
        if root is None:
            return False
        if candidates and not self._tau_unit_in_candidates(root, candidates):
            logger.error("ERROR: AUTOMATED REPAIR DRONES: target is not currently eligible")
            return False
        if not self._tau_owned_by_player(root, self.player):
            logger.error("ERROR: AUTOMATED REPAIR DRONES: target unit is not yours")
            return False
        if not self._tau_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tau_battlesuit_unit(root):
            logger.error("ERROR: AUTOMATED REPAIR DRONES: target must be a T'AU EMPIRE BATTLESUIT unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "command phase":
            logger.error("ERROR: AUTOMATED REPAIR DRONES: wrong phase")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Command phase"):
            logger.error("ERROR: AUTOMATED REPAIR DRONES: cannot be used in current state")
            return False

        wounded_models = self._tau_wounded_battlesuit_models(root)
        if not wounded_models:
            logger.error("ERROR: AUTOMATED REPAIR DRONES: no wounded BATTLESUIT model in target unit")
            return False

        model_selection = kwargs.get("model") or kwargs.get("target_model")
        heal_model = self._tau_resolve_selected_model(model_selection, self._tau_unit_models(root))
        if heal_model is None:
            heal_model = wounded_models[0]
        if not self._tau_model_is_battlesuit(heal_model, parent_unit=root):
            logger.error("ERROR: AUTOMATED REPAIR DRONES: selected model must have BATTLESUIT keyword")
            return False
        missing = self._tau_model_missing_wounds(heal_model)
        if missing <= 0:
            logger.error("ERROR: AUTOMATED REPAIR DRONES: selected model has no lost wounds")
            return False

        if not self._tau_spend_cp(stratagem, target_unit=root):
            return False

        heal_roll = max(0, int(dice_module.get_roll("D3") or 0))
        heal_amount = int(heal_roll + 1)
        healed = min(int(heal_amount), int(missing))

        heal_fn = getattr(heal_model, "heal", None)
        if callable(heal_fn):
            heal_fn(int(heal_amount))
        else:
            base_wounds = int(getattr(heal_model, "_base_wounds", getattr(heal_model, "base_wounds", 0)) or 0)
            current_wounds = int(getattr(heal_model, "wounds", 0) or 0)
            heal_model.wounds = min(base_wounds, current_wounds + int(heal_amount))

        self._tau_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: AUTOMATED REPAIR DRONES: %s healed %d wound(s).",
            getattr(root, "name", "Unit"),
            int(healed),
        )
        return True
