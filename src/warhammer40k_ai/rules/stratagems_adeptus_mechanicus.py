from __future__ import annotations

from typing import Any, Optional

import logging

from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class AdeptusMechanicusStratagemMixin:
    @staticmethod
    def _admech_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        return get_root() if callable(get_root) else unit

    @staticmethod
    def _admech_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    def _get_adeptus_mechanicus_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "adeptus_mechanicus_detachments", None) if army is not None else None

    def _is_rad_zone_corps(self) -> bool:
        mgr = self._get_adeptus_mechanicus_mgr()
        checker = getattr(mgr, "is_rad_zone_corps", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _admech_owned_by_player(self, unit: Any) -> bool:
        if unit is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is self.player

    def _admech_on_battlefield(self, unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        is_in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(is_in_reserves):
            if bool(is_in_reserves()):
                return False
        elif bool(getattr(unit, "is_in_reserves", False)):
            return False
        if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
            return False
        return True

    @staticmethod
    def _admech_has_any_keyword(unit: Any, keyword: str) -> bool:
        if unit is None or not keyword:
            return False
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            return bool(has_any_keyword(keyword))
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            return bool(has_keyword(keyword))
        return False

    def _is_adeptus_mechanicus_unit(self, unit: Any) -> bool:
        root = self._admech_root(unit)
        if root is None:
            return False
        if not self._admech_owned_by_player(root):
            return False
        if self._admech_has_any_keyword(root, "ADEPTUS MECHANICUS"):
            return True
        faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        return faction_id == "ADM"

    def _is_skitarii_unit(self, unit: Any) -> bool:
        root = self._admech_root(unit)
        if root is None:
            return False
        return self._admech_has_any_keyword(root, "SKITARII")

    def _is_battleline_unit(self, unit: Any) -> bool:
        root = self._admech_root(unit)
        if root is None:
            return False
        return self._admech_has_any_keyword(root, "BATTLELINE")

    def _admech_battlefield_units(
        self,
        *,
        require_not_shot: bool = False,
        require_skitarii: bool = False,
        exclude_battleline: bool = False,
    ) -> list[Any]:
        if not self._is_rad_zone_corps():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._admech_root(unit)
            if root is None:
                continue
            uid = self._admech_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._admech_on_battlefield(root):
                continue
            if not self._admech_owned_by_player(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adeptus_mechanicus_unit(root):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_skitarii and not self._is_skitarii_unit(root):
                continue
            if exclude_battleline and self._is_battleline_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._admech_sort_key)

    def _rad_zone_lethal_dosage_primary_candidates(self) -> list[Any]:
        return self._admech_battlefield_units(require_not_shot=True)

    def _rad_zone_pre_calibrated_purge_solution_primary_candidates(self) -> list[Any]:
        return self._admech_battlefield_units(require_not_shot=True)

    def _rad_zone_optional_skitarii_support_candidates(self, primary_unit: Any) -> list[Any]:
        primary_root = self._admech_root(primary_unit)
        if primary_root is None or not self._is_battleline_unit(primary_root):
            return []
        candidates = self._admech_battlefield_units(require_skitarii=True, exclude_battleline=True)
        if not candidates:
            return []
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return []
        distance_fn = getattr(game_map, "get_distance_between_units", None)
        if not callable(distance_fn):
            return []
        out: list[Any] = []
        for candidate in list(candidates or []):
            if candidate is primary_root:
                continue
            try:
                distance = float(distance_fn(primary_root, candidate))
            except (TypeError, ValueError):
                continue
            if distance <= 6.0 + 1e-6:
                out.append(candidate)
        return sorted(out, key=self._admech_sort_key)

    def _admech_resolve_unit_from_kwargs(self, kwargs: dict[str, Any], *, key: str, fallback_key: str = "") -> Any:
        value = kwargs.get(key)
        if value is None and fallback_key:
            value = kwargs.get(fallback_key)
        if value is not None:
            return self._admech_root(value)
        key_id = f"{key}_id"
        value_id = str(kwargs.get(key_id, "") or "")
        if not value_id and fallback_key:
            fallback_id = f"{fallback_key}_id"
            value_id = str(kwargs.get(fallback_id, "") or "")
        if not value_id:
            return None
        resolver = getattr(self.game, "_resolve_unit_by_id", None) if self.game is not None else None
        if not callable(resolver):
            return None
        return self._admech_root(resolver(value_id))

    def _admech_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        preview = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(preview):
            data = preview(stratagem, target_unit=target_unit) or {}
            cp_cost = int(data.get("cost", cp_cost))
        return cp_cost

    def _admech_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._admech_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _admech_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _rad_zone_opponent_player_id(self) -> str:
        if self.game is None:
            return ""
        for player in list(getattr(self.game, "players", []) or []):
            if player is not None and player is not self.player:
                return str(getattr(player, "id", "") or "")
        return ""

    def _mark_rad_zone_lethal_dosage(self, unit: Any, *, source_name: str) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["rad_zone_lethal_dosage_active"] = True
        sr["rad_zone_lethal_dosage_expires_phase"] = "SHOOTING_PHASE"
        sr["rad_zone_lethal_dosage_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["rad_zone_lethal_dosage_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["rad_zone_lethal_dosage_source"] = source_name
        unit.special_rules = sr

    def _mark_rad_zone_pre_calibrated(self, unit: Any, *, source_name: str, enemy_player_id: str) -> None:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["rad_zone_pre_calibrated_purge_solution_active"] = True
        sr["rad_zone_pre_calibrated_purge_solution_expires_phase"] = "SHOOTING_PHASE"
        sr["rad_zone_pre_calibrated_purge_solution_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["rad_zone_pre_calibrated_purge_solution_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["rad_zone_pre_calibrated_purge_solution_source"] = source_name
        sr["rad_zone_pre_calibrated_purge_solution_enemy_player_id"] = str(enemy_player_id or "")
        unit.special_rules = sr

    def _use_adeptus_mechanicus_rad_zone_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "LETHAL DOSAGE":
            return self._use_rad_zone_lethal_dosage(stratagem, **kwargs)
        if name_u == "PRE-CALIBRATED PURGE SOLUTION":
            return self._use_rad_zone_pre_calibrated_purge_solution(stratagem, **kwargs)
        return None

    def _use_rad_zone_lethal_dosage(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_rad_zone_corps():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: LETHAL DOSAGE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: LETHAL DOSAGE: not your Shooting phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: LETHAL DOSAGE: no primary unit selected")
            return False

        eligible_primary = self._rad_zone_lethal_dosage_primary_candidates()
        if primary not in eligible_primary:
            logger.error("ERROR: LETHAL DOSAGE: primary target must be an eligible ADEPTUS MECHANICUS unit that has not shot")
            return False

        secondary = self._admech_resolve_unit_from_kwargs(kwargs, key="secondary_unit", fallback_key="support_unit")
        eligible_secondary = self._rad_zone_optional_skitarii_support_candidates(primary)
        if secondary is not None and secondary not in eligible_secondary:
            logger.error("ERROR: LETHAL DOSAGE: optional support unit must be eligible SKITARII (excluding BATTLELINE) within 6\"")
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Shooting phase"):
            logger.error("ERROR: LETHAL DOSAGE: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        source_name = str(getattr(stratagem, "name", "") or "LETHAL DOSAGE")
        self._mark_rad_zone_lethal_dosage(primary, source_name=source_name)
        if secondary is not None:
            self._mark_rad_zone_lethal_dosage(secondary, source_name=source_name)

        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if secondary is None:
            logger.info("INFO: LETHAL DOSAGE: %s gains Lethal Hits on ranged weapons this phase.", getattr(primary, "name", "Unit"))
        else:
            logger.info(
                "INFO: LETHAL DOSAGE: %s and %s gain Lethal Hits on ranged weapons this phase.",
                getattr(primary, "name", "Unit"),
                getattr(secondary, "name", "Unit"),
            )
        return True

    def _use_rad_zone_pre_calibrated_purge_solution(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_rad_zone_corps():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PRE-CALIBRATED PURGE SOLUTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PRE-CALIBRATED PURGE SOLUTION: not your Shooting phase")
            return False

        primary = self._admech_resolve_unit_from_kwargs(kwargs, key="unit", fallback_key="target_unit")
        if primary is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                primary = self._admech_root(candidates[0])
        if primary is None:
            logger.error("ERROR: PRE-CALIBRATED PURGE SOLUTION: no primary unit selected")
            return False

        eligible_primary = self._rad_zone_pre_calibrated_purge_solution_primary_candidates()
        if primary not in eligible_primary:
            logger.error(
                "ERROR: PRE-CALIBRATED PURGE SOLUTION: primary target must be an eligible ADEPTUS MECHANICUS unit that has not shot"
            )
            return False

        secondary = self._admech_resolve_unit_from_kwargs(kwargs, key="secondary_unit", fallback_key="support_unit")
        eligible_secondary = self._rad_zone_optional_skitarii_support_candidates(primary)
        if secondary is not None and secondary not in eligible_secondary:
            logger.error(
                "ERROR: PRE-CALIBRATED PURGE SOLUTION: optional support unit must be eligible SKITARII (excluding BATTLELINE) within 6\""
            )
            return False

        if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name="Shooting phase"):
            logger.error("ERROR: PRE-CALIBRATED PURGE SOLUTION: cannot be used in current state")
            return False
        if not self._admech_spend_cp(stratagem, target_unit=primary):
            return False

        enemy_player_id = self._rad_zone_opponent_player_id()
        source_name = str(getattr(stratagem, "name", "") or "PRE-CALIBRATED PURGE SOLUTION")
        self._mark_rad_zone_pre_calibrated(primary, source_name=source_name, enemy_player_id=enemy_player_id)
        if secondary is not None:
            self._mark_rad_zone_pre_calibrated(secondary, source_name=source_name, enemy_player_id=enemy_player_id)

        self._admech_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        if secondary is None:
            logger.info(
                "INFO: PRE-CALIBRATED PURGE SOLUTION: %s re-rolls ranged Hit rolls vs targets in the opponent deployment zone this phase.",
                getattr(primary, "name", "Unit"),
            )
        else:
            logger.info(
                "INFO: PRE-CALIBRATED PURGE SOLUTION: %s and %s re-roll ranged Hit rolls vs targets in the opponent deployment zone this phase.",
                getattr(primary, "name", "Unit"),
                getattr(secondary, "name", "Unit"),
            )
        return True
