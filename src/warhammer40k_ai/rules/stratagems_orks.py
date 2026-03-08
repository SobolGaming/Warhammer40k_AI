from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class OrksStratagemMixin:
    @staticmethod
    def _orks_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _orks_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "")

    def _orks_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "orks_detachments", None)

    def _is_war_horde_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        if mgr is None:
            return False
        return bool(mgr.is_war_horde())

    def _is_green_tide_detachment(self) -> bool:
        mgr = self._orks_detachment_mgr()
        checker = getattr(mgr, "is_green_tide", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_orks_unit(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        if parent_army is not None and parent_army is not army:
            return False
        has_any_kw = getattr(root, "has_any_keyword", None)
        has_orks_kw = bool(has_any_kw("ORKS")) if callable(has_any_kw) else False
        root_faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if not has_orks_kw and root_faction_id != "ORK":
            return False
        return True

    @staticmethod
    def _orks_has_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and has_any(keyword):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and has_kw(keyword):
            return True
        return False

    def _orks_owned_by_player(self, unit: Any, player: Any) -> bool:
        root = self._orks_root(unit)
        if root is None or player is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    def _orks_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive):
            if not bool(is_alive()):
                return False
        elif not bool(getattr(root, "is_alive", True)):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        if getattr(root, "embarked_in", None) is not None:
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _orks_unit_is_boyz(self, unit: Any) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        if self._orks_has_keyword(root, "BOYZ"):
            return True
        return "BOYZ" in str(getattr(root, "name", "") or "").strip().upper()

    def _orks_model_is_character(self, model: Any) -> bool:
        if model is None:
            return False
        is_character = getattr(model, "is_character", None)
        if callable(is_character):
            if bool(is_character()):
                return True
        elif bool(is_character):
            return True
        if self._orks_has_keyword(model, "CHARACTER"):
            return True
        parent = getattr(model, "parent_unit", None)
        return bool(parent is not None and self._orks_has_keyword(parent, "CHARACTER"))

    def _orks_returnable_destroyed_non_character_models(self, unit: Any) -> list[Any]:
        root = self._orks_root(unit)
        if root is None:
            return []
        destroyed_pool = list(getattr(root, "models_lost", []) or [])
        can_return = getattr(root, "_horrors_can_return_model", None)
        candidates: list[Any] = []
        for model in destroyed_pool:
            if model is None:
                continue
            if self._orks_model_is_character(model):
                continue
            if callable(can_return) and not bool(can_return(model)):
                continue
            candidates.append(model)
        return sorted(candidates, key=self._orks_sort_key)

    def _orks_unit_in_candidates(self, unit: Any, candidates: list[Any]) -> bool:
        root = self._orks_root(unit)
        if root is None:
            return False
        root_id = self._orks_sort_key(root)
        for candidate in list(candidates or []):
            candidate_root = self._orks_root(candidate)
            if candidate_root is None:
                continue
            if candidate_root is root:
                return True
            if root_id and self._orks_sort_key(candidate_root) == root_id:
                return True
        return False

    def _orks_green_tide_come_on_ladz_candidates(self) -> list[Any]:
        if not self._is_green_tide_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._orks_root(unit)
            if root is None:
                continue
            uid = self._orks_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._orks_owned_by_player(root, self.player):
                continue
            if not self._orks_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_orks_unit(root):
                continue
            if not self._orks_unit_is_boyz(root):
                continue
            if not self._orks_returnable_destroyed_non_character_models(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._orks_sort_key)

    @staticmethod
    def _unit_is_grots(unit: Any) -> bool:
        if unit is None:
            return False
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            if has_any_keyword("Grots") or has_any_keyword("Grot") or has_any_keyword("Gretchin"):
                return True
        return False

    def _orks_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _orks_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._orks_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {str(getattr(stratagem, 'name', '') or '')}",
                source="stratagem",
            )
        )

    def _orks_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _use_orks_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "COME ON LADZ!":
            return self._use_orks_come_on_ladz(stratagem, **kwargs)
        return None

    def _use_orks_come_on_ladz(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "COME ON LADZ!":
                    continue
                target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if target_unit is None:
            logger.error("ERROR: COME ON LADZ!: no target unit provided")
            return False

        root = self._orks_root(target_unit)
        if root is None:
            return False
        if not self._is_green_tide_detachment():
            return False

        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower().replace("_", " ")
        if phase_name != "command phase":
            logger.error("ERROR: COME ON LADZ!: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if getattr(self, "game", None) is not None else None
        if active_player is not self.player:
            logger.error("ERROR: COME ON LADZ!: not your Command phase")
            return False
        if not self._orks_owned_by_player(root, self.player):
            logger.error("ERROR: COME ON LADZ!: target unit is not yours")
            return False
        if not self._orks_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: COME ON LADZ!: target must be on the battlefield and targetable")
            return False
        if not self._is_orks_unit(root):
            logger.error("ERROR: COME ON LADZ!: target must be an ORKS unit")
            return False
        if not self._orks_unit_is_boyz(root):
            logger.error("ERROR: COME ON LADZ!: target must be a BOYZ unit")
            return False

        eligible = candidates or self._orks_green_tide_come_on_ladz_candidates()
        if not eligible or not self._orks_unit_in_candidates(root, eligible):
            logger.error("ERROR: COME ON LADZ!: selected unit is not currently eligible")
            return False

        returnable_models = self._orks_returnable_destroyed_non_character_models(root)
        if not returnable_models:
            logger.error("ERROR: COME ON LADZ!: no destroyed non-CHARACTER models can be returned")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Command phase"):
            logger.error("ERROR: COME ON LADZ!: cannot be used in current state")
            return False
        if not self._orks_spend_cp(stratagem, target_unit=root):
            return False

        roll = max(0, int(dice_module.get_roll("D3") or 0)) + 2
        max_return = min(int(roll), len(returnable_models))

        explicit_selection = any(
            key in kwargs for key in ("return_models", "chosen_models", "models", "return_model_ids")
        )
        selected_models: list[Any]
        if explicit_selection:
            selected_models = []
            selected_ids: set[str] = set()
            requested_models = kwargs.get("return_models") or kwargs.get("chosen_models") or kwargs.get("models") or []
            requested_ids = kwargs.get("return_model_ids") or []
            request_tokens = [str(get_entity_id(model) or "") for model in list(requested_models or []) if model is not None]
            request_tokens.extend([str(item or "") for item in list(requested_ids or []) if str(item or "")])
            for token in request_tokens:
                if not token or token in selected_ids:
                    continue
                matched = None
                for model in returnable_models:
                    if str(get_entity_id(model) or "") == token:
                        matched = model
                        break
                if matched is None:
                    logger.error("ERROR: COME ON LADZ!: one or more selected models are not returnable")
                    return False
                selected_models.append(matched)
                selected_ids.add(token)
            if len(selected_models) > max_return:
                selected_models = selected_models[:max_return]
        else:
            selected_models = list(returnable_models[:max_return])

        returned = 0
        return_models = getattr(root, "return_destroyed_bodyguard_models", None)
        if callable(return_models):
            returned = int(
                return_models(
                    max_return,
                    game_map=getattr(getattr(self, "game", None), "map", None),
                    chosen_models=selected_models,
                    wounds=None,
                    placement_source=str(stratagem.name or "COME ON LADZ!"),
                )
                or 0
            )
        else:
            return_full = getattr(self, "_return_destroyed_models_full", None)
            if callable(return_full):
                returned = int(
                    return_full(
                        root,
                        amount=max_return,
                        game_map=getattr(getattr(self, "game", None), "map", None),
                        skip_character=True,
                    )
                    or 0
                )

        self._orks_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: COME ON LADZ!: returned %d destroyed model(s) to %s.",
            int(returned),
            getattr(root, "name", "Unit"),
        )
        return True
