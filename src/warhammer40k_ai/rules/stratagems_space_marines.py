from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class SpaceMarinesStratagemMixin:
    @staticmethod
    def _sm_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _sm_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    def _sm_detachment_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "space_marines_detachments", None)

    def _is_saga_of_the_beastslayer_detachment(self) -> bool:
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "is_saga_of_the_beastslayer", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _sm_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _sm_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        checker = getattr(unit, "is_alive", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _sm_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return True
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(unit, "is_in_reserves", False))

    def _sm_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if self._sm_is_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None)):
            return False
        if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
            return False
        return True

    def _is_adeptus_astartes_unit(self, unit: Any) -> bool:
        root = self._sm_root(unit)
        if root is None:
            return False
        mgr = self._sm_detachment_mgr()
        checker = getattr(mgr, "attached_unit_is_adeptus_astartes", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any = getattr(root, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any("ADEPTUS ASTARTES"))
        return str(getattr(root, "faction_id", "") or "").strip().upper() == "SM"

    @staticmethod
    def _sm_is_thunderwolf_cavalry(unit: Any) -> bool:
        if unit is None:
            return False
        has_any = getattr(unit, "has_any_keyword", None)
        if callable(has_any) and bool(has_any("THUNDERWOLF CAVALRY")):
            return True
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("THUNDERWOLF CAVALRY")):
            return True
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return "thunderwolf cavalry" in name

    @staticmethod
    def _sm_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    @staticmethod
    def _sm_selected_to_charge_this_phase(unit: Any) -> bool:
        return bool(getattr(getattr(unit, "round_state", None), "attempted_charge_this_round", False))

    @staticmethod
    def _sm_spend_cp(player: Any, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return bool(
            player.spend_command_points(
                int(cp_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _sm_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u:
                used.add(name_u)

    def _space_marines_shock_cavalry_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_saga_of_the_beastslayer_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        phase_key = str(phase_name or "").strip().lower()
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._sm_owned_by_player(root, self.player):
                continue
            if not self._sm_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_adeptus_astartes_unit(root):
                continue
            if not self._sm_is_thunderwolf_cavalry(root):
                continue
            if phase_key == "movement phase" and self._sm_selected_to_move_this_phase(root):
                continue
            if phase_key == "charge phase" and self._sm_selected_to_charge_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._sm_sort_key)

    def _cleanup_space_marines_saga_of_the_beastslayer_phase_end_effects(self, *, phase: Any = None) -> None:
        if not self._is_saga_of_the_beastslayer_detachment():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name not in ("MOVEMENT_PHASE", "CHARGE_PHASE"):
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return

        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._sm_root(unit)
            if root is None:
                continue
            uid = self._sm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            exp = str(sr.get("space_marines_shock_cavalry_expires_phase", "") or "").strip().upper()
            if sr.get("space_marines_shock_cavalry_active") is not True:
                continue
            if exp and exp != phase_name:
                continue

            for key, added_key in (
                (
                    "bearer_unit_phase_move_models_only_types",
                    "space_marines_shock_cavalry_added_phase_move_models_only_types",
                ),
                (
                    "bearer_unit_phase_move_models_only_block_titanic_types",
                    "space_marines_shock_cavalry_added_phase_move_models_only_block_titanic_types",
                ),
                (
                    "move_over_low_terrain_height_types",
                    "space_marines_shock_cavalry_added_low_terrain_types",
                ),
                (
                    "bearer_unit_phase_move_engagement_types",
                    "space_marines_shock_cavalry_added_phase_move_engagement_types",
                ),
            ):
                added = set(sr.get(added_key) or [])
                if not added:
                    continue
                current = list(sr.get(key) or [])
                kept = [item for item in current if item not in added]
                if kept:
                    sr[key] = kept
                else:
                    sr.pop(key, None)

            if bool(sr.get("space_marines_shock_cavalry_prev_low_terrain_height_present", False)):
                sr["move_over_low_terrain_height_value"] = float(
                    sr.get("space_marines_shock_cavalry_prev_low_terrain_height_value", 4.0) or 4.0
                )
            else:
                sr.pop("move_over_low_terrain_height_value", None)

            for key in (
                "space_marines_shock_cavalry_active",
                "space_marines_shock_cavalry_expires_phase",
                "space_marines_shock_cavalry_turn_owner",
                "space_marines_shock_cavalry_turn",
                "space_marines_shock_cavalry_source",
                "space_marines_shock_cavalry_added_phase_move_models_only_types",
                "space_marines_shock_cavalry_added_phase_move_models_only_block_titanic_types",
                "space_marines_shock_cavalry_added_low_terrain_types",
                "space_marines_shock_cavalry_added_phase_move_engagement_types",
                "space_marines_shock_cavalry_prev_low_terrain_height_present",
                "space_marines_shock_cavalry_prev_low_terrain_height_value",
            ):
                sr.pop(key, None)
            root.special_rules = sr

    def _use_space_marines_saga_of_the_beastslayer_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "SHOCK CAVALRY":
            return self._use_space_marines_shock_cavalry(stratagem, **kwargs)
        return None

    def _use_space_marines_shock_cavalry(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_saga_of_the_beastslayer_detachment():
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in ("movement phase", "charge phase"):
            logger.error("ERROR: SHOCK CAVALRY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SHOCK CAVALRY: not your turn")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SHOCK CAVALRY: no target unit provided")
            return False

        root = self._sm_root(unit)
        if root is None:
            return False
        if not self._sm_owned_by_player(root, self.player):
            logger.error("ERROR: SHOCK CAVALRY: target unit is not yours")
            return False
        if not self._sm_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SHOCK CAVALRY: target must be on the battlefield and targetable")
            return False
        if not self._is_adeptus_astartes_unit(root):
            logger.error("ERROR: SHOCK CAVALRY: target must be an ADEPTUS ASTARTES unit")
            return False
        if not self._sm_is_thunderwolf_cavalry(root):
            logger.error("ERROR: SHOCK CAVALRY: target must be a THUNDERWOLF CAVALRY unit")
            return False

        if phase_name == "movement phase" and self._sm_selected_to_move_this_phase(root):
            logger.error("ERROR: SHOCK CAVALRY: target has already been selected to move this phase")
            return False
        if phase_name == "charge phase" and self._sm_selected_to_charge_this_phase(root):
            logger.error("ERROR: SHOCK CAVALRY: target has already declared a charge this phase")
            return False

        eligible = candidates or self._space_marines_shock_cavalry_candidates(phase_name=phase_name)
        if eligible:
            eid = self._sm_sort_key(root)
            if all(self._sm_sort_key(candidate) != eid for candidate in eligible):
                logger.error("ERROR: SHOCK CAVALRY: selected unit is not currently eligible")
                return False

        phase_label = "Movement phase" if phase_name == "movement phase" else "Charge phase"
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
            logger.error("ERROR: SHOCK CAVALRY: cannot be used in current state")
            return False
        if not self._sm_spend_cp(self.player, stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}

        move_types = {"move", "advance", "fall_back"} if phase_name == "movement phase" else {"charge"}
        engagement_move_types = {"move", "advance", "fall_back"} if phase_name == "movement phase" else set()

        def _merge_move_types(rule_key: str, added_key: str, values: set[str]) -> None:
            current = set(sr.get(rule_key) or [])
            added = sorted([move_type for move_type in values if move_type not in current])
            merged = sorted(current.union(values))
            if merged:
                sr[rule_key] = merged
            if added:
                sr[added_key] = added
            else:
                sr.pop(added_key, None)

        _merge_move_types(
            "bearer_unit_phase_move_models_only_types",
            "space_marines_shock_cavalry_added_phase_move_models_only_types",
            set(move_types),
        )
        _merge_move_types(
            "bearer_unit_phase_move_models_only_block_titanic_types",
            "space_marines_shock_cavalry_added_phase_move_models_only_block_titanic_types",
            set(move_types),
        )
        _merge_move_types(
            "move_over_low_terrain_height_types",
            "space_marines_shock_cavalry_added_low_terrain_types",
            set(move_types),
        )
        _merge_move_types(
            "bearer_unit_phase_move_engagement_types",
            "space_marines_shock_cavalry_added_phase_move_engagement_types",
            set(engagement_move_types),
        )

        low_height_present = "move_over_low_terrain_height_value" in sr
        sr["space_marines_shock_cavalry_prev_low_terrain_height_present"] = bool(low_height_present)
        if low_height_present:
            sr["space_marines_shock_cavalry_prev_low_terrain_height_value"] = float(
                sr.get("move_over_low_terrain_height_value", 4.0) or 4.0
            )
        current_height = float(sr.get("move_over_low_terrain_height_value", 0.0) or 0.0)
        sr["move_over_low_terrain_height_value"] = max(4.0, current_height)

        sr["space_marines_shock_cavalry_active"] = True
        sr["space_marines_shock_cavalry_expires_phase"] = (
            "MOVEMENT_PHASE" if phase_name == "movement phase" else "CHARGE_PHASE"
        )
        sr["space_marines_shock_cavalry_source"] = str(getattr(stratagem, "name", "") or "SHOCK CAVALRY")
        owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id:
            sr["space_marines_shock_cavalry_turn_owner"] = owner_id
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if turn:
            sr["space_marines_shock_cavalry_turn"] = turn

        root.special_rules = sr
        self._sm_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SHOCK CAVALRY: %s gains move-through models/low-terrain movement for this phase.",
            getattr(root, "name", "Unit"),
        )
        return True
