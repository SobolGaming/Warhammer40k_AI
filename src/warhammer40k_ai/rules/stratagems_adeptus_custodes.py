from __future__ import annotations

import logging
from typing import Any

from ..utility import dice as dice_module
from ..utility import aura_utils
from ..utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class AdeptusCustodesStratagemMixin:
    @staticmethod
    def _ac_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _ac_phase_key(value: Any) -> str:
        return str(value or "").strip().upper().replace(" ", "_")

    @staticmethod
    def _ac_has_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        token = str(keyword or "").strip()
        if not token:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(token)):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        return bool(callable(has_kw) and has_kw(token))

    def _ac_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "adeptus_custodes_detachments", None)

    def _is_auric_champions_detachment(self) -> bool:
        mgr = self._ac_detachment_mgr()
        checker = getattr(mgr, "is_auric_champions", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_lions_of_the_emperor_detachment(self) -> bool:
        mgr = self._ac_detachment_mgr()
        checker = getattr(mgr, "is_lions_of_the_emperor", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_null_maiden_vigil_detachment(self) -> bool:
        mgr = self._ac_detachment_mgr()
        checker = getattr(mgr, "is_null_maiden_vigil", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_shield_host_detachment(self) -> bool:
        mgr = self._ac_detachment_mgr()
        checker = getattr(mgr, "is_shield_host", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_solar_spearhead_detachment(self) -> bool:
        mgr = self._ac_detachment_mgr()
        checker = getattr(mgr, "is_solar_spearhead", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_talons_of_the_emperor_detachment(self) -> bool:
        mgr = self._ac_detachment_mgr()
        checker = getattr(mgr, "is_talons_of_the_emperor", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _ac_phase_name_lower(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _ac_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "").strip()

    @staticmethod
    def _ac_unit_name_startswith(unit: Any, prefixes: tuple[str, ...]) -> bool:
        name = str(getattr(unit, "name", "") or "").strip().lower()
        return any(name.startswith(str(prefix or "").strip().lower()) for prefix in tuple(prefixes or ()))

    def _ac_submit_decision_request(self, request: Any) -> bool:
        if request is None or self.game is None:
            return False
        request_decision = getattr(self.game, "request_decision", None)
        if callable(request_decision):
            request_decision(request)
            return True
        queue = getattr(self.game, "decision_queue", None)
        if queue is not None and hasattr(queue, "add"):
            queue.add(request)
            return True
        return False

    def _ac_pending_choose_quarry_request(
        self,
        *,
        player_id: str = "",
        ctx_filters: dict[str, Any] | None = None,
    ) -> bool:
        if self.game is None:
            return False
        queue = getattr(self.game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        filters = dict(ctx_filters or {})
        for pending in list(queue.list() or []):
            if str(getattr(pending, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            if player_id and str(getattr(pending, "player_id", "") or "") != str(player_id):
                continue
            context = dict(getattr(pending, "context", {}) or {})
            matches = True
            for key, value in filters.items():
                if key in {"phase_name", "phase_key"}:
                    if self._ac_phase_key(context.get(key, "") or "") != self._ac_phase_key(value):
                        matches = False
                        break
                    continue
                if key == "turn":
                    if int(context.get("turn", 0) or 0) != int(value or 0):
                        matches = False
                        break
                    continue
                if str(context.get(key, "") or "").strip() != str(value or "").strip():
                    matches = False
                    break
            if matches:
                return True
        return False

    def _ac_owned_by_player(self, unit: Any, player: Any | None = None) -> bool:
        root = self._ac_root(unit)
        owner = self.player if player is None else player
        if root is None or owner is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        return getattr(army, "player", None) is owner

    def _ac_is_custodes_unit(self, unit: Any) -> bool:
        root = self._ac_root(unit)
        if root is None or not self._ac_owned_by_player(root):
            return False
        return self._ac_has_keyword(root, "ADEPTUS CUSTODES")

    def _ac_is_character_unit(self, unit: Any) -> bool:
        root = self._ac_root(unit)
        return root is not None and self._ac_is_custodes_unit(root) and self._ac_has_keyword(root, "CHARACTER")

    def _ac_is_anathema_psykana_unit(self, unit: Any) -> bool:
        root = self._ac_root(unit)
        if root is None or not self._ac_owned_by_player(root):
            return False
        mgr = self._ac_detachment_mgr()
        checker = getattr(mgr, "_unit_is_anathema_psykana", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._ac_has_keyword(root, "ANATHEMA PSYKANA")

    @staticmethod
    def _ac_is_battle_shocked(unit: Any) -> bool:
        checker = getattr(unit, "is_battle_shocked", None)
        return bool(callable(checker) and checker())

    def _ac_unit_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._ac_root(unit)
        if root is None:
            return False
        if require_targetable:
            is_active = getattr(root, "is_active_for_rules", None)
            if callable(is_active) and not bool(is_active()):
                return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if str(getattr(root, "reserve_status", "deployed") or "").strip().lower() != "deployed":
            return False
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        return True

    def _ac_is_enemy_battlefield_unit(self, unit: Any) -> bool:
        root = self._ac_root(unit)
        if root is None or not self._ac_unit_on_battlefield(root):
            return False
        return not self._ac_owned_by_player(root)

    def _ac_current_phase_name(self, explicit: Any = "") -> str:
        phase_name = str(explicit or "").strip()
        if phase_name:
            return phase_name
        current = str(getattr(self, "_current_phase_name", "") or "").strip()
        if current:
            return current
        phase = getattr(getattr(self, "game", None), "phase", None)
        return str(getattr(phase, "name", phase) or "").strip()

    def _ac_current_turn(self) -> int:
        return int(getattr(getattr(self, "game", None), "turn", 0) or 0)

    def _ac_turn_owner_id(self) -> str:
        game = getattr(self, "game", None)
        current = game.get_current_player() if game is not None and hasattr(game, "get_current_player") else None
        return str(getattr(current, "id", "") or "").strip()

    def _ac_effective_cp_cost(self, stratagem, *, target_unit: Any) -> int:
        cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit) or {}
            cost = int(preview.get("cost", cost))
        return int(cost)

    def _ac_spend_cp(self, stratagem, *, target_unit: Any) -> bool:
        cost = self._ac_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _ac_finalize_use(self, stratagem, *, dequeue: bool) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add(str(self._normalize_stratagem_name(stratagem.name or "")).strip())

    def _ac_model_has_keyword(self, model: Any, keyword: str) -> bool:
        return self._ac_has_keyword(model, keyword)

    def _ac_alive_models(self, unit: Any) -> list[Any]:
        root = self._ac_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        alive: list[Any] = []
        for model in models:
            if model is None:
                continue
            is_alive = getattr(model, "is_alive", None)
            if callable(is_alive):
                if not bool(is_alive()):
                    continue
            elif getattr(model, "is_alive", True) is False:
                continue
            alive.append(model)
        return alive

    def _ac_grant_melee_precision_to_unit(self, unit: Any, *, key_prefix: str, source: str) -> None:
        root = self._ac_root(unit)
        if root is None:
            return
        root_id = str(get_entity_id(root) or id(root))
        for model in self._ac_alive_models(root):
            set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
            if not callable(set_keywords):
                continue
            model_id = str(get_entity_id(model) or id(model))
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                is_melee = getattr(wargear, "is_melee", None)
                if not callable(is_melee) or not bool(is_melee()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                set_keywords(
                    key=f"{key_prefix}:{root_id}:{model_id}:{weapon_name}".lower(),
                    weapon_name=weapon_name,
                    keywords=["PRECISION"],
                    source=source,
                    expires_phase="FIGHT_PHASE",
                    attack_type="melee",
                )

    def _ac_unique_units(self, units: list[Any]) -> list[Any]:
        resolved: list[Any] = []
        seen: set[str] = set()
        for unit in list(units or []):
            root = self._ac_root(unit)
            unit_id = str(get_entity_id(root) or "").strip()
            if root is None or not unit_id or unit_id in seen:
                continue
            seen.add(unit_id)
            resolved.append(root)
        resolved.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return resolved

    def _ac_resolve_unit_selection(self, *values: Any) -> list[Any]:
        flattened: list[Any] = []
        for value in values:
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                flattened.extend(list(value))
            else:
                flattened.append(value)
        return self._ac_unique_units(flattened)

    def _ac_enemy_battlefield_units(self) -> list[Any]:
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return []
        return self._ac_unique_units(
            [unit for unit in list(getattr(game_map, "units", []) or []) if self._ac_is_enemy_battlefield_unit(unit)]
        )

    def _ac_friendly_battlefield_units(self) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        return self._ac_unique_units(
            [unit for unit in list(getattr(army, "units", []) or []) if self._ac_unit_on_battlefield(unit)]
        )

    def _ac_unit_has_weapon_type(self, unit: Any, attack_type: str) -> bool:
        root = self._ac_root(unit)
        if root is None:
            return False
        attack_type_l = str(attack_type or "").strip().lower()
        for model in self._ac_alive_models(root):
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                if attack_type_l == "ranged":
                    is_match = getattr(wargear, "is_ranged", None)
                else:
                    is_match = getattr(wargear, "is_melee", None)
                if callable(is_match) and bool(is_match()):
                    return True
        return False

    def _ac_unit_has_psychic_weapon(self, unit: Any, attack_type: str) -> bool:
        root = self._ac_root(unit)
        if root is None:
            return False
        attack_type_l = str(attack_type or "").strip().lower()
        for model in self._ac_alive_models(root):
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                if attack_type_l == "ranged":
                    type_check = getattr(wargear, "is_ranged", None)
                else:
                    type_check = getattr(wargear, "is_melee", None)
                if not callable(type_check) or not bool(type_check()):
                    continue
                profile_check = getattr(wargear, "is_psychic", None)
                if callable(profile_check) and bool(profile_check()):
                    return True
        return False

    def _ac_warlord_unit(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        warlord = getattr(army, "warlord", None) if army is not None else None
        return self._ac_root(warlord)

    def _ac_warlord_model_pair_key(self, model: Any, ability_key: str) -> str:
        model_id = str(get_entity_id(model) or "").strip()
        ability = str(ability_key or "").strip().lower()
        return f"{model_id}:{ability}"

    def _ac_superhuman_reserves_pairs(self) -> set[str]:
        pairs = getattr(self, "_auric_superhuman_reserves_granted_pairs", None)
        if not isinstance(pairs, set):
            pairs = set()
            self._auric_superhuman_reserves_granted_pairs = pairs
        return pairs

    def _ac_pending_reaction(self, stratagem_name: str) -> dict[str, Any] | None:
        wanted = str(stratagem_name or "").strip().upper()
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
                return reaction
        return None

    @staticmethod
    def _ac_objective_sort_key(objective: Any) -> str:
        if objective is None:
            return ""
        location = getattr(objective, "location", None)
        return str(
            getattr(objective, "id", "")
            or get_entity_id(objective)
            or getattr(location, "id", "")
            or get_entity_id(location)
            or ""
        ).strip()

    def _ac_resolve_objective(self, value: Any, *, candidates: list[Any] | None = None) -> Any:
        if value is None:
            return None
        if value in list(candidates or []):
            return value
        if not isinstance(value, str):
            objective_id = self._ac_objective_sort_key(value)
            if objective_id:
                for objective in list(candidates or []):
                    if objective_id == self._ac_objective_sort_key(objective):
                        return objective
                game_map = getattr(getattr(self, "game", None), "map", None)
                for objective in list(getattr(game_map, "objectives", []) or []):
                    if objective_id == self._ac_objective_sort_key(objective):
                        return objective
                return value
        token = str(value or "").strip()
        if not token:
            return value if not isinstance(value, str) else None
        for objective in list(candidates or []):
            if token == self._ac_objective_sort_key(objective):
                return objective
        game_map = getattr(getattr(self, "game", None), "map", None)
        for objective in list(getattr(game_map, "objectives", []) or []):
            if token == self._ac_objective_sort_key(objective):
                return objective
        return None

    def _ac_objectives_in_range(self, unit: Any) -> list[Any]:
        root = self._ac_root(unit)
        if root is None or not self._ac_unit_on_battlefield(root):
            return []
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return []
        objectives: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            location = getattr(objective, "location", None) or objective
            if location is None or bool(getattr(location, "removed", False)):
                continue
            objective_id = self._ac_objective_sort_key(objective)
            if not objective_id or objective_id in seen:
                continue
            try:
                if not bool(getattr(root, "is_within_objective_range")(location)):
                    continue
            except Exception:
                continue
            seen.add(objective_id)
            objectives.append(objective)
        objectives.sort(key=self._ac_objective_sort_key)
        return objectives

    def _ac_controlled_objectives_in_range(self, unit: Any) -> list[Any]:
        root = self._ac_root(unit)
        if root is None:
            return []
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        if player is None:
            return []
        controlled: list[Any] = []
        for objective in self._ac_objectives_in_range(root):
            location = getattr(objective, "location", None) or objective
            if getattr(location, "controlling_player", None) is player:
                controlled.append(objective)
        return controlled

    def _shield_host_battlefield_unit_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_infantry: bool = False,
        require_battleline: bool = False,
        require_below_starting_strength: bool = False,
        require_fell_back: bool = False,
        attack_type: str = "",
    ) -> list[Any]:
        if not self._is_shield_host_detachment():
            return []
        candidates: list[Any] = []
        for root in self._ac_friendly_battlefield_units():
            if not self._ac_is_custodes_unit(root) or self._ac_is_anathema_psykana_unit(root):
                continue
            if require_infantry and not self._ac_has_keyword(root, "INFANTRY"):
                continue
            if require_battleline and not self._ac_has_keyword(root, "BATTLELINE"):
                continue
            if require_below_starting_strength and not bool(getattr(root, "is_below_starting_strength", lambda: False)()):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_fell_back and not bool(getattr(round_state, "fell_back_this_round", False)):
                continue
            if attack_type and not self._ac_unit_has_weapon_type(root, attack_type):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._ac_sort_key)

    def _solar_spearhead_battlefield_unit_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_vehicle: bool = False,
        require_vehicle_or_mounted: bool = False,
        require_advanced: bool = False,
        attack_type: str = "",
    ) -> list[Any]:
        if not self._is_solar_spearhead_detachment():
            return []
        candidates: list[Any] = []
        for root in self._ac_friendly_battlefield_units():
            if not self._ac_is_custodes_unit(root):
                continue
            is_vehicle = bool(getattr(root, "is_vehicle", False)) or self._ac_has_keyword(root, "VEHICLE")
            is_mounted = bool(getattr(root, "is_mounted", False)) or self._ac_has_keyword(root, "MOUNTED")
            if require_vehicle and not is_vehicle:
                continue
            if require_vehicle_or_mounted and not (is_vehicle or is_mounted):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_advanced and not bool(getattr(round_state, "advanced_this_round", False)):
                continue
            if attack_type and not self._ac_unit_has_weapon_type(root, attack_type):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._ac_sort_key)

    def _solar_spearhead_targeted_unit_candidates(
        self,
        target_units: list[Any],
        *,
        require_vehicle: bool = False,
    ) -> list[Any]:
        candidates: list[Any] = []
        for root in self._ac_unique_units(list(target_units or [])):
            if not self._ac_owned_by_player(root):
                continue
            if not self._ac_unit_on_battlefield(root):
                continue
            if not self._ac_is_custodes_unit(root):
                continue
            if require_vehicle:
                is_vehicle = bool(getattr(root, "is_vehicle", False)) or self._ac_has_keyword(root, "VEHICLE")
                if not is_vehicle:
                    continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._ac_sort_key)

    def _talons_battlefield_unit_candidates(
        self,
        *,
        require_infantry: bool = False,
        require_not_shot: bool = False,
        require_melee: bool = False,
        require_ranged: bool = False,
    ) -> list[Any]:
        if not self._is_talons_of_the_emperor_detachment():
            return []
        candidates: list[Any] = []
        for root in self._ac_friendly_battlefield_units():
            if not self._ac_is_custodes_unit(root):
                continue
            if require_infantry and not self._ac_has_keyword(root, "INFANTRY"):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_melee and not self._ac_unit_has_weapon_type(root, "melee"):
                continue
            if require_ranged and not self._ac_unit_has_weapon_type(root, "ranged"):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._ac_sort_key)

    def _talons_targeted_custodes_candidates(
        self,
        target_units: list[Any],
        *,
        require_anathema: bool | None = None,
        require_infantry: bool = False,
    ) -> list[Any]:
        candidates: list[Any] = []
        for root in self._ac_unique_units(list(target_units or [])):
            if not self._ac_owned_by_player(root):
                continue
            if not self._ac_unit_on_battlefield(root):
                continue
            if not self._ac_is_custodes_unit(root):
                continue
            if require_infantry and not self._ac_has_keyword(root, "INFANTRY"):
                continue
            is_anathema = self._ac_is_anathema_psykana_unit(root)
            if require_anathema is True and not is_anathema:
                continue
            if require_anathema is False and is_anathema:
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._ac_sort_key)

    def _talons_support_candidates(
        self,
        source_unit: Any,
        *,
        range_in: float,
        require_anathema: bool | None = None,
        require_infantry: bool = False,
        exclude_same: bool = False,
    ) -> list[Any]:
        source_root = self._ac_root(source_unit)
        if source_root is None:
            return []
        candidates: list[Any] = []
        for root in self._ac_friendly_battlefield_units():
            if root is None or not self._ac_is_custodes_unit(root):
                continue
            if exclude_same and root is source_root:
                continue
            if require_infantry and not self._ac_has_keyword(root, "INFANTRY"):
                continue
            is_anathema = self._ac_is_anathema_psykana_unit(root)
            if require_anathema is True and not is_anathema:
                continue
            if require_anathema is False and is_anathema:
                continue
            if not aura_utils.unit_within_range_of_unit(
                source_root,
                root,
                float(range_in),
                use_attached_aggregate=True,
            ):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._ac_sort_key)

    def _talons_support_candidates_for_empyric(self, target_unit: Any) -> list[Any]:
        return self._talons_support_candidates(
            target_unit,
            range_in=6.0,
            require_anathema=True,
            require_infantry=False,
            exclude_same=False,
        )

    def _talons_support_candidates_for_shield(self, target_unit: Any) -> list[Any]:
        return self._talons_support_candidates(
            target_unit,
            range_in=6.0,
            require_anathema=False,
            require_infantry=True,
            exclude_same=True,
        )

    def _talons_unit_can_shoot_target(self, unit: Any, enemy_unit: Any) -> bool:
        root = self._ac_root(unit)
        enemy_root = self._ac_root(enemy_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if root is None or enemy_root is None or game_map is None:
            return False
        can_target_fn = getattr(root, "_can_model_shoot_weapon_at_target", None)
        if not callable(can_target_fn):
            return False
        for model in self._ac_alive_models(root):
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                profiles = getattr(wargear, "profiles", None)
                if isinstance(profiles, dict) and profiles:
                    profile_values = list(profiles.values())
                else:
                    profile_values = [wargear] if getattr(wargear, "parent_wargear", None) is not None else []
                for profile in list(profile_values or []):
                    if can_target_fn(model, profile, enemy_root, game_map):
                        return True
        return False

    def _talons_enemy_target_eligible_for_all_units(self, units: list[Any], enemy_unit: Any) -> bool:
        enemy_root = self._ac_root(enemy_unit)
        if enemy_root is None or not self._ac_is_enemy_battlefield_unit(enemy_root):
            return False
        selected_units = self._ac_resolve_unit_selection(units)
        if not selected_units:
            return False
        return all(self._talons_unit_can_shoot_target(unit, enemy_root) for unit in selected_units)

    def _queue_solar_spearhead_emperors_vengeance_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_solar_spearhead_detachment():
            return
        if self._ac_phase_key(self._ac_current_phase_name()) != "FIGHT_PHASE":
            return
        attacker_root = self._ac_root(attacking_unit)
        if attacker_root is None or self._ac_owned_by_player(attacker_root):
            return
        candidates = self._solar_spearhead_targeted_unit_candidates(list(target_units or []))
        if not candidates:
            return
        stratagem = self.get_by_name("EMPEROR'S VENGEANCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        attacker_id = self._ac_sort_key(attacker_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "EMPEROR'S VENGEANCE":
                continue
            if str(reaction.get("attacking_unit_id", "") or "").strip() == attacker_id:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "attacking_unit_id": attacker_id,
            "candidates": candidates,
            "target_units": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_solar_spearhead_flawless_construction_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
    ) -> None:
        if not self._is_solar_spearhead_detachment():
            return
        phase_key = self._ac_phase_key(phase_name)
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        attacker_root = self._ac_root(attacking_unit)
        if attacker_root is None or self._ac_owned_by_player(attacker_root):
            return
        candidates = self._solar_spearhead_targeted_unit_candidates(list(target_units or []), require_vehicle=True)
        if not candidates:
            return
        stratagem = self.get_by_name("FLAWLESS CONSTRUCTION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        attacker_id = self._ac_sort_key(attacker_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "FLAWLESS CONSTRUCTION":
                continue
            if str(reaction.get("attacking_unit_id", "") or "").strip() == attacker_id:
                return
        payload = {
            "event": "shooting_targets_selected" if phase_key == "SHOOTING_PHASE" else "fight_targets_selected",
            "phase_name": "Shooting phase" if phase_key == "SHOOTING_PHASE" else "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "attacking_unit_id": attacker_id,
            "candidates": candidates,
            "target_units": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_solar_spearhead_relentless_persecution_reaction(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower() != "advance":
            return
        root = self._ac_root(unit)
        if root is None or not self._is_solar_spearhead_detachment():
            return
        if not self._ac_is_custodes_unit(root) or not self._ac_unit_on_battlefield(root):
            return
        is_vehicle = bool(getattr(root, "is_vehicle", False)) or self._ac_has_keyword(root, "VEHICLE")
        if not is_vehicle or self._unit_cannot_be_target_of_stratagem(root):
            return
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "advanced_this_round", False)):
            return
        if self._ac_phase_key(self._ac_current_phase_name()) != "MOVEMENT_PHASE":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        stratagem = self.get_by_name("RELENTLESS PERSECUTION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip().lower() != "unit_move_ended":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "RELENTLESS PERSECUTION":
                continue
            if reaction.get("unit") is root:
                return
        self._queue_reaction(
            {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "action": "advance",
            },
            use_timer=False,
        )

    def _queue_talons_empyric_severance_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
    ) -> None:
        if not self._is_talons_of_the_emperor_detachment():
            return
        phase_key = self._ac_phase_key(phase_name)
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        attacker_root = self._ac_root(attacking_unit)
        if attacker_root is None or self._ac_owned_by_player(attacker_root):
            return
        candidates: list[Any] = []
        support_candidates_by_unit_id: dict[str, list[str]] = {}
        for root in self._talons_targeted_custodes_candidates(list(target_units or [])):
            supports = self._talons_support_candidates_for_empyric(root)
            if not supports:
                continue
            unit_id = self._ac_sort_key(root)
            if not unit_id:
                continue
            candidates.append(root)
            support_candidates_by_unit_id[unit_id] = [self._ac_sort_key(unit) for unit in supports if self._ac_sort_key(unit)]
        if not candidates:
            return
        stratagem = self.get_by_name("EMPYRIC SEVERANCE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        attacker_id = self._ac_sort_key(attacker_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "EMPYRIC SEVERANCE":
                continue
            if str(reaction.get("attacking_unit_id", "") or "").strip() == attacker_id:
                return
        payload = {
            "event": "shooting_targets_selected" if phase_key == "SHOOTING_PHASE" else "fight_targets_selected",
            "phase_name": "Shooting phase" if phase_key == "SHOOTING_PHASE" else "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "attacking_unit_id": attacker_id,
            "candidates": sorted(candidates, key=self._ac_sort_key),
            "support_candidates_by_unit_id": dict(support_candidates_by_unit_id),
        }
        if len(candidates) == 1:
            target_root = candidates[0]
            payload["unit"] = target_root
            payload["target_unit"] = target_root
            support_ids = list(support_candidates_by_unit_id.get(self._ac_sort_key(target_root), []) or [])
            if len(support_ids) == 1 and self.game is not None and hasattr(self.game, "_resolve_unit_by_id"):
                payload["support_unit"] = self.game._resolve_unit_by_id(support_ids[0])
        self._queue_reaction(payload, use_timer=False)

    def _queue_talons_shield_of_honour_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_talons_of_the_emperor_detachment():
            return
        if self._ac_phase_key(self._ac_current_phase_name()) != "SHOOTING_PHASE":
            return
        attacker_root = self._ac_root(attacking_unit)
        if attacker_root is None or self._ac_owned_by_player(attacker_root):
            return
        candidates: list[Any] = []
        support_candidates_by_unit_id: dict[str, list[str]] = {}
        for root in self._talons_targeted_custodes_candidates(
            list(target_units or []),
            require_anathema=True,
            require_infantry=True,
        ):
            supports = self._talons_support_candidates_for_shield(root)
            if not supports:
                continue
            unit_id = self._ac_sort_key(root)
            if not unit_id:
                continue
            candidates.append(root)
            support_candidates_by_unit_id[unit_id] = [self._ac_sort_key(unit) for unit in supports if self._ac_sort_key(unit)]
        if not candidates:
            return
        stratagem = self.get_by_name("SHIELD OF HONOUR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        attacker_id = self._ac_sort_key(attacker_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "SHIELD OF HONOUR":
                continue
            if str(reaction.get("attacking_unit_id", "") or "").strip() == attacker_id:
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "attacking_unit_id": attacker_id,
            "candidates": sorted(candidates, key=self._ac_sort_key),
            "support_candidates_by_unit_id": dict(support_candidates_by_unit_id),
        }
        if len(candidates) == 1:
            target_root = candidates[0]
            payload["unit"] = target_root
            payload["target_unit"] = target_root
            support_ids = list(support_candidates_by_unit_id.get(self._ac_sort_key(target_root), []) or [])
            if len(support_ids) == 1 and self.game is not None and hasattr(self.game, "_resolve_unit_by_id"):
                payload["support_unit"] = self.game._resolve_unit_by_id(support_ids[0])
        self._queue_reaction(payload, use_timer=False)

    def _queue_talons_taloned_pincer_reaction(self, *, unit: Any, action: str) -> None:
        action_key = str(action or "").strip().lower()
        if action_key not in {"move", "advance", "fall_back"}:
            return
        enemy_root = self._ac_root(unit)
        if enemy_root is None or not self._is_talons_of_the_emperor_detachment():
            return
        if self._ac_owned_by_player(enemy_root) or not self._ac_is_enemy_battlefield_unit(enemy_root):
            return
        if self._ac_phase_key(self._ac_current_phase_name()) != "MOVEMENT_PHASE":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        candidates: list[Any] = []
        for root in self._talons_battlefield_unit_candidates():
            if not aura_utils.unit_within_range_of_unit(
                root,
                enemy_root,
                9.0,
                use_attached_aggregate=True,
            ):
                continue
            candidates.append(root)
        if not candidates:
            return
        stratagem = self.get_by_name("TALONED PINCER")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        enemy_id = self._ac_sort_key(enemy_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "TALONED PINCER":
                continue
            if str(reaction.get("enemy_unit_id", "") or "").strip() == enemy_id:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "enemy_unit_id": enemy_id,
            "action": action_key,
            "candidates": sorted(candidates, key=self._ac_sort_key),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _ac_units_within_shoulder_range(self, leader_unit: Any, bodyguard_unit: Any) -> bool:
        source_models = self._ac_alive_models(leader_unit)
        target_models = self._ac_alive_models(bodyguard_unit)
        for source_model in source_models:
            source_base = getattr(source_model, "model_base", None)
            if source_base is None:
                continue
            for target_model in target_models:
                target_base = getattr(target_model, "model_base", None)
                if target_base is None:
                    continue
                horizontal = float(horizontal_distance_between_bases_2d(source_base, target_base))
                vertical = float(vertical_distance_between_bases(source_base, target_base))
                if horizontal <= 2.0 + 1e-6 and vertical <= 5.0 + 1e-6:
                    return True
        return False

    def _queue_auric_superhuman_reserves_reaction(
        self,
        *,
        player=None,
        model=None,
        ability_key: str = "",
        ability_name: str = "",
        phase_name: str = "",
        source: str = "",
    ) -> None:
        if player is not self.player or not self._is_auric_champions_detachment() or model is None:
            return
        if str(source or "").strip().lower() not in {"datasheet", "enhancement"}:
            return
        model_unit = getattr(model, "parent_unit", None)
        root = self._ac_root(model_unit)
        if root is None or root is not self._ac_warlord_unit() or not self._ac_unit_on_battlefield(root):
            return
        pair_key = self._ac_warlord_model_pair_key(model, ability_key)
        if not pair_key or pair_key in self._ac_superhuman_reserves_pairs():
            return
        stratagem = self.get_by_name("SUPERHUMAN RESERVES")
        if stratagem is None:
            return
        phase_label = self._ac_current_phase_name(phase_name)
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name=phase_label):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "SUPERHUMAN RESERVES":
                continue
            if str(reaction.get("pair_key", "") or "").strip() == pair_key:
                return
        self._queue_reaction(
            {
                "event": "once_per_battle_ability_used",
                "phase_name": phase_label,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "model": model,
                "unit": root,
                "target_unit": root,
                "ability_key": str(ability_key or "").strip().lower(),
                "ability_name": str(ability_name or "").strip(),
                "pair_key": pair_key,
            }
        )

    def _queue_auric_the_emperors_auspice_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        phase_name: str,
    ) -> None:
        if not self._is_auric_champions_detachment() or attacking_unit is None:
            return
        if self._ac_owned_by_player(attacking_unit):
            return
        stratagem = self.get_by_name("THE EMPEROR'S AUSPICE")
        if stratagem is None:
            return
        candidates = self._ac_unique_units(
            [
                unit
                for unit in list(target_units or [])
                if self._ac_is_character_unit(unit)
                and self._ac_unit_on_battlefield(unit)
                and not self._unit_cannot_be_target_of_stratagem(self._ac_root(unit))
            ]
        )
        if not candidates:
            return
        if not stratagem.can_use(self.player, self.game, unit=candidates[0], target_unit=candidates[0], phase_name=phase_name):
            return
        attacker_id = str(get_entity_id(self._ac_root(attacking_unit)) or "").strip()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "THE EMPEROR'S AUSPICE":
                continue
            if str(reaction.get("attacking_unit_id", "") or "").strip() == attacker_id:
                return
        payload = {
            "event": "shooting_targets_selected" if "shooting" in phase_name.lower() else "fight_targets_selected",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": self._ac_root(attacking_unit),
            "attacking_unit_id": attacker_id,
            "candidates": candidates,
            "target_units": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_auric_vigil_unending_reaction(self, *, unit: Any, model: Any) -> None:
        if not self._is_auric_champions_detachment():
            return
        phase_name = self._ac_current_phase_name()
        if self._ac_phase_key(phase_name) != "FIGHT_PHASE":
            return
        root = self._ac_root(unit)
        if root is None or model is None:
            return
        if not self._ac_is_character_unit(root) or not self._ac_owned_by_player(root):
            return
        if not self._ac_model_has_keyword(model, "CHARACTER"):
            return
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            return
        if self._unit_cannot_be_target_of_stratagem(root):
            return
        stratagem = self.get_by_name("VIGIL UNENDING")
        if stratagem is None or not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name=phase_name):
            return
        model_id = str(get_entity_id(model) or "").strip()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "VIGIL UNENDING":
                continue
            if str(reaction.get("destroyed_model_id", "") or "").strip() == model_id:
                return
        self._queue_reaction(
            {
                "event": "model_destroyed_before_removal",
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "model": model,
                "destroyed_model_id": model_id,
            },
            use_timer=False,
        )

    def _queue_auric_slayer_of_champions_reaction(self, *, destroyed_unit: Any, destroyed_by_unit: Any) -> None:
        if not self._is_auric_champions_detachment():
            return
        mgr = self._ac_detachment_mgr()
        if mgr is None or not bool(getattr(mgr, "is_assemblage_of_might_target", lambda _unit: False)(destroyed_unit)):
            return
        attacker = self._ac_root(destroyed_by_unit)
        if attacker is None or not self._ac_is_character_unit(attacker) or not self._ac_owned_by_player(attacker):
            return
        candidates = self._ac_enemy_battlefield_units()
        if not candidates:
            return
        stratagem = self.get_by_name("SLAYER OF CHAMPIONS")
        phase_name = self._ac_current_phase_name()
        if stratagem is None or not stratagem.can_use(self.player, self.game, unit=attacker, target_unit=attacker, phase_name=phase_name):
            return
        destroyed_id = str(get_entity_id(self._ac_root(destroyed_unit)) or "").strip()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "SLAYER OF CHAMPIONS":
                continue
            if str(reaction.get("destroyed_unit_id", "") or "").strip() == destroyed_id:
                return
        self._queue_reaction(
            {
                "event": "unit_destroyed",
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": attacker,
                "target_unit": attacker,
                "destroyed_unit": self._ac_root(destroyed_unit),
                "destroyed_unit_id": destroyed_id,
                "destroyed_unit_was_character": self._ac_has_keyword(self._ac_root(destroyed_unit), "CHARACTER"),
                "candidates": candidates,
            }
        )

    def _queue_lions_manoeuvre_and_fire_reaction(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower() != "fall_back":
            return
        root = self._ac_root(unit)
        if root is None or not self._is_lions_of_the_emperor_detachment():
            return
        if not self._ac_is_custodes_unit(root) or not self._ac_unit_on_battlefield(root):
            return
        if self._unit_cannot_be_target_of_stratagem(root):
            return
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "fell_back_this_round", False)):
            return
        phase_name = self._ac_current_phase_name()
        if self._ac_phase_key(phase_name) != "MOVEMENT_PHASE":
            return
        game = getattr(self, "game", None)
        active_player = game.get_current_player() if game is not None and hasattr(game, "get_current_player") else None
        if active_player is not self.player:
            return
        stratagem = self.get_by_name("MANOEUVRE AND FIRE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip().lower() != "unit_move_ended":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "MANOEUVRE AND FIRE":
                continue
            if reaction.get("unit") is root:
                return
        self._queue_reaction(
            {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "action": "fall_back",
            }
        )

    def _null_maiden_battlefield_unit_candidates(
        self,
        *,
        unit_prefixes: tuple[str, ...] = (),
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_infantry: bool = False,
        attack_type: str = "",
    ) -> list[Any]:
        if not self._is_null_maiden_vigil_detachment():
            return []
        candidates: list[Any] = []
        for root in self._ac_friendly_battlefield_units():
            if not self._ac_is_anathema_psykana_unit(root):
                continue
            if require_infantry and not self._ac_has_keyword(root, "INFANTRY"):
                continue
            if unit_prefixes and not self._ac_unit_name_startswith(root, unit_prefixes):
                continue
            if attack_type and not self._ac_unit_has_weapon_type(root, attack_type):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._ac_sort_key)

    def _null_maiden_anathema_blademastery_candidates(self) -> list[Any]:
        return self._null_maiden_battlefield_unit_candidates(
            unit_prefixes=("Vigilators",),
            require_not_fought=True,
            attack_type="melee",
        )

    def _null_maiden_purgation_sweep_candidates(self) -> list[Any]:
        return self._null_maiden_battlefield_unit_candidates(
            unit_prefixes=("Witchseekers",),
            require_not_shot=True,
            attack_type="ranged",
        )

    def _null_maiden_witch_hunters_candidates(self, *, phase_name: str) -> list[Any]:
        phase_lower = self._ac_phase_name_lower(phase_name)
        if phase_lower == "shooting phase":
            return self._null_maiden_battlefield_unit_candidates(
                require_not_shot=True,
                attack_type="ranged",
            )
        if phase_lower == "fight phase":
            return self._null_maiden_battlefield_unit_candidates(
                require_not_fought=True,
                attack_type="melee",
            )
        return []

    def _null_maiden_psychic_abominations_candidates(self, target_units: list[Any]) -> list[Any]:
        candidates: list[Any] = []
        for root in self._ac_unique_units(list(target_units or [])):
            if not self._ac_owned_by_player(root):
                continue
            if not self._ac_unit_on_battlefield(root):
                continue
            if not self._ac_is_anathema_psykana_unit(root):
                continue
            if not self._ac_has_keyword(root, "INFANTRY"):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._ac_sort_key)

    def _null_maiden_desperations_price_candidates(self, enemy_unit: Any) -> list[Any]:
        enemy_root = self._ac_root(enemy_unit)
        if enemy_root is None or not self._ac_is_enemy_battlefield_unit(enemy_root):
            return []
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return []
        candidates: list[Any] = []
        for root in self._null_maiden_battlefield_unit_candidates():
            try:
                distance = float(game_map.get_distance_between_units(root, enemy_root))
            except (TypeError, ValueError):
                continue
            if distance <= 18.0:
                candidates.append(root)
        return sorted(candidates, key=self._ac_sort_key)

    @staticmethod
    def _null_maiden_witch_hunters_choice_key(value: Any) -> str:
        text = str(value or "").strip().upper().replace(" ", "_")
        if text == "LETHAL_HITS":
            return "LETHAL_HITS"
        if text in {"SUSTAINED_HITS_1", "SUSTAINED_HITS1"}:
            return "SUSTAINED_HITS_1"
        return ""

    @staticmethod
    def _null_maiden_witch_hunters_choice_label(choice_key: str) -> str:
        return "Lethal Hits" if choice_key == "LETHAL_HITS" else "Sustained Hits 1"

    @staticmethod
    def _null_maiden_witch_hunters_choice_keywords(choice_key: str) -> list[str]:
        if choice_key == "LETHAL_HITS":
            return ["LETHAL HITS"]
        if choice_key == "SUSTAINED_HITS_1":
            return ["SUSTAINED HITS 1"]
        return []

    def _build_null_maiden_witch_hunters_choice_request(
        self,
        *,
        unit: Any,
        phase_name: str,
        stratagem_name: str,
    ) -> Any:
        if self.game is None or not bool(getattr(self.game, "is_authoritative", True)):
            return None
        root = self._ac_root(unit)
        if root is None:
            return None
        unit_id = self._ac_sort_key(root)
        if not unit_id:
            return None
        player_id = str(getattr(self.player, "id", "") or "")
        turn = self._ac_current_turn()
        turn_owner_id = self._ac_turn_owner_id()
        phase_label = str(phase_name or "").strip() or "Fight phase"
        if self._ac_pending_choose_quarry_request(
            player_id=player_id,
            ctx_filters={
                "ability": "adeptus_custodes_null_maiden_witch_hunters_choice",
                "unit_id": unit_id,
                "phase_name": phase_label,
                "turn": turn,
                "turn_owner_id": turn_owner_id,
            },
        ):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        attack_type = "ranged" if self._ac_phase_name_lower(phase_label) == "shooting phase" else "melee"
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{str(stratagem_name or '').strip() or 'WITCH HUNTERS'}: choose a weapon ability.",
            player_id=player_id,
            options=[
                DecisionOption.create(
                    "Lethal Hits",
                    payload={"choice_key": "LETHAL_HITS", "unit_id": unit_id},
                ),
                DecisionOption.create(
                    "Sustained Hits 1",
                    payload={"choice_key": "SUSTAINED_HITS_1", "unit_id": unit_id},
                ),
            ],
            context={
                "ability": "adeptus_custodes_null_maiden_witch_hunters_choice",
                "ability_name": str(stratagem_name or "").strip() or "WITCH HUNTERS",
                "army_id": str(get_entity_id(getattr(self.player, "army", None)) or ""),
                "unit_id": unit_id,
                "phase_name": phase_label,
                "attack_type": attack_type,
                "turn": turn,
                "turn_owner_id": turn_owner_id,
                "candidate_choice_keys": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
                "stratagem_name": str(stratagem_name or "").strip() or "WITCH HUNTERS",
                "optional": False,
            },
        )

    def validate_null_maiden_witch_hunters_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        attack_type: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
    ) -> tuple[bool, str]:
        root = self._ac_root(unit)
        if root is None:
            return False, "WITCH HUNTERS choice unit was not found."
        if player is not None and player is not self.player:
            return False, "WITCH HUNTERS choice must be resolved by the owning player."
        if not self._is_null_maiden_vigil_detachment():
            return False, "WITCH HUNTERS requires Null Maiden Vigil."
        if not self._ac_owned_by_player(root):
            return False, "WITCH HUNTERS target must belong to you."
        if not self._ac_unit_on_battlefield(root):
            return False, "WITCH HUNTERS target must be on the battlefield."
        if self._unit_cannot_be_target_of_stratagem(root):
            return False, "WITCH HUNTERS target can no longer be selected."
        if not self._ac_is_anathema_psykana_unit(root):
            return False, "WITCH HUNTERS target must be an Anathema Psykana unit."
        if game is not None:
            current_phase = self._ac_phase_key(getattr(getattr(game, "phase", None), "name", "") or "")
            expected_phase = self._ac_phase_key(phase_name)
            if current_phase and expected_phase and current_phase != expected_phase:
                return False, "WITCH HUNTERS choice is no longer in the same phase."
            if int(turn or 0) > 0 and int(getattr(game, "turn", 0) or 0) != int(turn or 0):
                return False, "WITCH HUNTERS choice is no longer in the same battle round."
            current_owner_id = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "")
            if turn_owner_id and current_owner_id and current_owner_id != str(turn_owner_id):
                return False, "WITCH HUNTERS choice is no longer in the same turn."
        phase_lower = self._ac_phase_name_lower(phase_name)
        round_state = getattr(root, "round_state", None)
        if phase_lower == "shooting phase":
            if bool(getattr(round_state, "shot_this_round", False)):
                return False, "WITCH HUNTERS target has already been selected to shoot."
            if not self._ac_unit_has_weapon_type(root, "ranged"):
                return False, "WITCH HUNTERS target has no ranged weapons."
        elif phase_lower == "fight phase":
            if bool(getattr(round_state, "fought_this_phase", False)):
                return False, "WITCH HUNTERS target has already fought."
            if not self._ac_unit_has_weapon_type(root, "melee"):
                return False, "WITCH HUNTERS target has no melee weapons."
        else:
            return False, "WITCH HUNTERS choice requires the Shooting or Fight phase."
        expected_attack_type = "ranged" if phase_lower == "shooting phase" else "melee"
        if attack_type and str(attack_type or "").strip().lower() != expected_attack_type:
            return False, "WITCH HUNTERS choice payload does not match the phase."
        choice_key = self._null_maiden_witch_hunters_choice_key(
            payload.get("choice_key", "") or payload.get("choice", "")
        )
        if choice_key not in {"LETHAL_HITS", "SUSTAINED_HITS_1"}:
            return False, "WITCH HUNTERS choice must be LETHAL HITS or SUSTAINED HITS 1."
        resolved_name = str(stratagem_name or payload.get("stratagem_name", "") or "").strip().upper()
        if resolved_name and resolved_name != "WITCH HUNTERS":
            return False, "WITCH HUNTERS choice payload does not match the stratagem."
        return True, ""

    def apply_null_maiden_witch_hunters_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        attack_type: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
    ) -> Any:
        valid, _reason = self.validate_null_maiden_witch_hunters_choice(
            unit,
            payload,
            game=game,
            player=player,
            phase_name=phase_name,
            attack_type=attack_type,
            turn=turn,
            turn_owner_id=turn_owner_id,
            stratagem_name=stratagem_name,
        )
        if not valid:
            return None
        root = self._ac_root(unit)
        if root is None:
            return None
        choice_key = self._null_maiden_witch_hunters_choice_key(
            payload.get("choice_key", "") or payload.get("choice", "")
        )
        return self._apply_null_maiden_witch_hunters_effect(
            root,
            choice_key=choice_key,
            phase_name=phase_name,
            stratagem_name=str(stratagem_name or payload.get("stratagem_name", "") or "WITCH HUNTERS"),
        )

    def _apply_null_maiden_witch_hunters_effect(
        self,
        unit: Any,
        *,
        choice_key: str,
        phase_name: str,
        stratagem_name: str,
    ) -> dict[str, Any] | None:
        root = self._ac_root(unit)
        if root is None:
            return None
        resolved_choice = self._null_maiden_witch_hunters_choice_key(choice_key)
        keyword_bonuses = self._null_maiden_witch_hunters_choice_keywords(resolved_choice)
        if not keyword_bonuses:
            return None
        attack_type = "ranged" if self._ac_phase_name_lower(phase_name) == "shooting phase" else "melee"
        root_id = self._ac_sort_key(root) or str(id(root))
        for model in self._ac_alive_models(root):
            set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
            if not callable(set_keywords):
                continue
            model_id = self._ac_sort_key(model) or str(id(model))
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                type_check = getattr(wargear, "is_ranged", None) if attack_type == "ranged" else getattr(wargear, "is_melee", None)
                if not callable(type_check) or not bool(type_check()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                set_keywords(
                    key=f"custodes_null_maiden_witch_hunters:{root_id}:{model_id}:{weapon_name}:{resolved_choice}".lower(),
                    weapon_name=weapon_name,
                    keywords=list(keyword_bonuses),
                    source=str(stratagem_name or "WITCH HUNTERS").strip() or "WITCH HUNTERS",
                    expires_phase=self._ac_phase_key(phase_name),
                    attack_type=attack_type,
                )
        special_rules = dict(getattr(root, "special_rules", {}) or {})
        special_rules["custodes_null_maiden_witch_hunters_active"] = True
        special_rules["custodes_null_maiden_witch_hunters_choice_key"] = resolved_choice
        special_rules["custodes_null_maiden_witch_hunters_attack_type"] = attack_type
        special_rules["custodes_null_maiden_witch_hunters_turn"] = self._ac_current_turn()
        special_rules["custodes_null_maiden_witch_hunters_turn_owner"] = self._ac_turn_owner_id()
        special_rules["custodes_null_maiden_witch_hunters_expires_phase"] = self._ac_phase_key(phase_name)
        special_rules["custodes_null_maiden_witch_hunters_source"] = str(stratagem_name or "WITCH HUNTERS").strip() or "WITCH HUNTERS"
        root.special_rules = special_rules
        return {
            "unit_id": self._ac_sort_key(root),
            "unit_name": str(getattr(root, "name", "Unit") or "Unit"),
            "choice_key": resolved_choice,
            "choice_label": self._null_maiden_witch_hunters_choice_label(resolved_choice),
            "attack_type": attack_type,
            "stratagem_name": str(stratagem_name or "WITCH HUNTERS").strip() or "WITCH HUNTERS",
        }

    def _queue_null_maiden_psychic_abominations_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_null_maiden_vigil_detachment():
            return
        if self._ac_phase_key(self._ac_current_phase_name()) != "SHOOTING_PHASE":
            return
        attacker_root = self._ac_root(attacking_unit)
        if attacker_root is None or self._ac_owned_by_player(attacker_root):
            return
        candidates = self._null_maiden_psychic_abominations_candidates(list(target_units or []))
        if not candidates:
            return
        stratagem = self.get_by_name("PSYCHIC ABOMINATIONS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "PSYCHIC ABOMINATIONS":
                continue
            if reaction.get("attacking_unit") is attacker_root:
                return
        self._queue_reaction(
            {
                "event": "shooting_targets_selected",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "attacking_unit": attacker_root,
                "candidates": candidates,
                "target_unit": candidates[0] if len(candidates) == 1 else None,
            },
            use_timer=False,
        )

    def _queue_null_maiden_psy_chaff_volley_reaction(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: dict[Any, Any] | None,
    ) -> None:
        if not self._is_null_maiden_vigil_detachment():
            return
        if self._ac_phase_key(self._ac_current_phase_name()) != "SHOOTING_PHASE":
            return
        attacker_root = self._ac_root(attacker_unit)
        if attacker_root is None or not self._ac_owned_by_player(attacker_root):
            return
        if not self._ac_unit_name_startswith(attacker_root, ("Prosecutors",)):
            return
        if self._unit_cannot_be_target_of_stratagem(attacker_root):
            return
        enemy_candidates: list[Any] = []
        for unit, hit_count in dict(hits_by_target or {}).items():
            try:
                parsed_hits = int(hit_count or 0)
            except (TypeError, ValueError):
                parsed_hits = 0
            if parsed_hits <= 0:
                continue
            root = self._ac_root(unit)
            if root is None or not self._ac_is_enemy_battlefield_unit(root):
                continue
            enemy_candidates.append(root)
        enemy_candidates = self._ac_unique_units(enemy_candidates)
        if not enemy_candidates:
            return
        stratagem = self.get_by_name("PSY-CHAFF VOLLEY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "PSY-CHAFF VOLLEY":
                continue
            if reaction.get("unit") is attacker_root:
                return
        self._queue_reaction(
            {
                "event": "unit_shooting_resolved",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": attacker_root,
                "target_unit": attacker_root,
                "enemy_candidates": enemy_candidates,
                "enemy_unit": enemy_candidates[0] if len(enemy_candidates) == 1 else None,
            },
            use_timer=False,
        )

    def _capture_null_maiden_desperations_price_shooting_targets_selected(
        self,
        *,
        attacking_unit: Any,
        weapon_declarations: list[dict[str, Any]] | None,
    ) -> None:
        if not self._is_null_maiden_vigil_detachment():
            return
        attacker_root = self._ac_root(attacking_unit)
        if attacker_root is None or self._ac_owned_by_player(attacker_root):
            return
        if not self._ac_has_keyword(attacker_root, "PSYKER"):
            return
        has_psychic_attack = False
        for declaration in list(weapon_declarations or []):
            target_unit = self._ac_root(declaration.get("target_unit"))
            if target_unit is None:
                continue
            profile = declaration.get("weapon_profile")
            is_psychic = getattr(profile, "is_psychic", None)
            if callable(is_psychic) and bool(is_psychic()):
                has_psychic_attack = True
                break
        if not has_psychic_attack:
            return
        tracked = dict(getattr(self, "_null_maiden_desperations_price_shooting_attackers", {}) or {})
        tracked[self._ac_sort_key(attacker_root)] = attacker_root
        self._null_maiden_desperations_price_shooting_attackers = tracked

    def _queue_null_maiden_desperations_price_reaction(
        self,
        *,
        enemy_unit: Any,
        source_event: str,
    ) -> None:
        if not self._is_null_maiden_vigil_detachment():
            return
        enemy_root = self._ac_root(enemy_unit)
        if enemy_root is None or not self._ac_is_enemy_battlefield_unit(enemy_root):
            return
        if not self._ac_has_keyword(enemy_root, "PSYKER"):
            return
        candidates = self._null_maiden_desperations_price_candidates(enemy_root)
        if not candidates:
            return
        stratagem = self.get_by_name("DESPERATION'S PRICE")
        phase_name = self._ac_current_phase_name() or "Any phase"
        if stratagem is None or not stratagem.can_use(
            self.player,
            self.game,
            unit=candidates[0],
            target_unit=candidates[0],
            phase_name=phase_name,
        ):
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        enemy_id = self._ac_sort_key(enemy_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "DESPERATION'S PRICE":
                continue
            if str(reaction.get("enemy_unit_id", "") or "").strip() == enemy_id:
                return
        self._queue_reaction(
            {
                "event": source_event,
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "enemy_unit": enemy_root,
                "enemy_unit_id": enemy_id,
                "candidates": candidates,
                "target_unit": candidates[0] if len(candidates) == 1 else None,
            },
            use_timer=False,
        )

    def _queue_null_maiden_desperations_price_from_shooting_resolved(self, *, attacker_unit: Any) -> None:
        attacker_root = self._ac_root(attacker_unit)
        attacker_id = self._ac_sort_key(attacker_root)
        tracked = dict(getattr(self, "_null_maiden_desperations_price_shooting_attackers", {}) or {})
        tracked.pop(attacker_id, None)
        self._null_maiden_desperations_price_shooting_attackers = tracked
        self._queue_null_maiden_desperations_price_reaction(
            enemy_unit=attacker_root,
            source_event="unit_shooting_resolved",
        )

    def _on_shooting_targets_selected_adeptus_custodes_null_maiden(
        self,
        attacking_unit=None,
        target_units=None,
        weapon_declarations=None,
        **_kwargs,
    ) -> None:
        if attacking_unit is None:
            return
        self._queue_null_maiden_psychic_abominations_reaction(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
        )
        self._capture_null_maiden_desperations_price_shooting_targets_selected(
            attacking_unit=attacking_unit,
            weapon_declarations=list(weapon_declarations or []),
        )

    def _on_unit_shooting_resolved_adeptus_custodes_null_maiden(
        self,
        attacker_unit=None,
        hits_by_target=None,
        hit_models_by_target_psychic=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None:
            return
        self._queue_null_maiden_psy_chaff_volley_reaction(
            attacker_unit=attacker_unit,
            hits_by_target=dict(hits_by_target or {}),
        )
        attacker_root = self._ac_root(attacker_unit)
        tracked = dict(getattr(self, "_null_maiden_desperations_price_shooting_attackers", {}) or {})
        if self._ac_sort_key(attacker_root) in tracked or bool(dict(hit_models_by_target_psychic or {})):
            self._queue_null_maiden_desperations_price_from_shooting_resolved(attacker_unit=attacker_root)

    def _on_fight_attacks_resolved_adeptus_custodes_null_maiden(
        self,
        unit=None,
        hit_models_by_target_psychic=None,
        **_kwargs,
    ) -> None:
        if unit is None:
            return
        if not bool(dict(hit_models_by_target_psychic or {})):
            return
        self._queue_null_maiden_desperations_price_reaction(
            enemy_unit=unit,
            source_event="fight_attacks_resolved",
        )

    def _on_cabal_ritual_resolved_adeptus_custodes_null_maiden(
        self,
        player=None,
        caster_unit=None,
        target_unit=None,
        **_kwargs,
    ) -> None:
        if player is self.player or caster_unit is None or target_unit is None:
            return
        self._queue_null_maiden_desperations_price_reaction(
            enemy_unit=caster_unit,
            source_event="cabal_ritual_resolved",
        )

    def _queue_shield_host_arcane_genetic_alchemy_reaction(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any,
        target_model: Any,
        phase_name: str,
    ) -> None:
        if not self._is_shield_host_detachment():
            return
        root = self._ac_root(target_unit or getattr(target_model, "parent_unit", None))
        if root is None or not self._ac_is_custodes_unit(root) or not self._ac_owned_by_player(root):
            return
        if not self._ac_unit_on_battlefield(root) or self._ac_is_anathema_psykana_unit(root):
            return
        if target_model is not None and self._ac_model_has_keyword(target_model, "ANATHEMA PSYKANA"):
            return
        if self._unit_cannot_be_target_of_stratagem(root):
            return
        stratagem = self.get_by_name("ARCANE GENETIC ALCHEMY")
        phase_label = self._ac_current_phase_name(phase_name) or "Any phase"
        if stratagem is None or not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            target_unit=root,
            phase_name=phase_label,
        ):
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        root_id = self._ac_sort_key(root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "ARCANE GENETIC ALCHEMY":
                continue
            if str(reaction.get("unit_id", "") or "").strip() == root_id:
                return
        self._queue_reaction(
            {
                "event": "mortal_wound_allocated",
                "phase_name": phase_label,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "unit_id": root_id,
                "target_unit": root,
                "attacker_unit": self._ac_root(attacker_unit),
                "target_model": target_model,
                "candidates": [root],
            },
            use_timer=False,
        )

    def _queue_shield_host_multipotentiality_reaction(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower() != "fall_back":
            return
        root = self._ac_root(unit)
        if root is None or not self._is_shield_host_detachment():
            return
        if not self._ac_is_custodes_unit(root) or self._ac_is_anathema_psykana_unit(root):
            return
        if not self._ac_unit_on_battlefield(root) or self._unit_cannot_be_target_of_stratagem(root):
            return
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "fell_back_this_round", False)):
            return
        phase_name = self._ac_current_phase_name()
        if self._ac_phase_key(phase_name) != "MOVEMENT_PHASE":
            return
        game = getattr(self, "game", None)
        active_player = game.get_current_player() if game is not None and hasattr(game, "get_current_player") else None
        if active_player is not self.player:
            return
        stratagem = self.get_by_name("MULTIPOTENTIALITY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip().lower() != "unit_move_ended":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "MULTIPOTENTIALITY":
                continue
            if reaction.get("unit") is root:
                return
        self._queue_reaction(
            {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "action": "fall_back",
            },
            use_timer=False,
        )

    def _shield_host_unwavering_sentinels_candidates(self, target_units: list[Any]) -> list[Any]:
        candidates: list[Any] = []
        for root in self._ac_unique_units(list(target_units or [])):
            if not self._ac_owned_by_player(root):
                continue
            if not self._ac_unit_on_battlefield(root):
                continue
            if not self._ac_is_custodes_unit(root) or self._ac_is_anathema_psykana_unit(root):
                continue
            if not self._ac_has_keyword(root, "INFANTRY"):
                continue
            if not self._ac_controlled_objectives_in_range(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._ac_sort_key)

    def _queue_shield_host_unwavering_sentinels_reaction(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_shield_host_detachment():
            return
        if self._ac_phase_key(self._ac_current_phase_name()) != "FIGHT_PHASE":
            return
        attacker_root = self._ac_root(attacking_unit)
        if attacker_root is None or self._ac_owned_by_player(attacker_root):
            return
        candidates = self._shield_host_unwavering_sentinels_candidates(list(target_units or []))
        if not candidates:
            return
        stratagem = self.get_by_name("UNWAVERING SENTINELS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(getattr(stratagem, "name", "") or "").strip().upper() in {
            str(v or "").strip().upper() for v in list(getattr(self, "_used_stratagems_this_phase", set()) or set())
        }:
            return
        attacker_id = self._ac_sort_key(attacker_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "UNWAVERING SENTINELS":
                continue
            if str(reaction.get("attacking_unit_id", "") or "").strip() == attacker_id:
                return
        self._queue_reaction(
            {
                "event": "fight_targets_selected",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "attacking_unit": attacker_root,
                "attacking_unit_id": attacker_id,
                "candidates": candidates,
                "target_unit": candidates[0] if len(candidates) == 1 else None,
            },
            use_timer=False,
        )

    @staticmethod
    def _shield_host_archeotech_munitions_choice_key(value: Any) -> str:
        text = str(value or "").strip().upper().replace(" ", "_")
        if text == "LETHAL_HITS":
            return "LETHAL_HITS"
        if text in {"SUSTAINED_HITS_1", "SUSTAINED_HITS1"}:
            return "SUSTAINED_HITS_1"
        return ""

    @staticmethod
    def _shield_host_archeotech_munitions_choice_label(choice_key: str) -> str:
        return "Lethal Hits" if choice_key == "LETHAL_HITS" else "Sustained Hits 1"

    @staticmethod
    def _shield_host_archeotech_munitions_choice_keywords(choice_key: str) -> list[str]:
        if choice_key == "LETHAL_HITS":
            return ["LETHAL HITS"]
        if choice_key == "SUSTAINED_HITS_1":
            return ["SUSTAINED HITS 1"]
        return []

    def _build_shield_host_archeotech_munitions_choice_request(
        self,
        *,
        unit: Any,
        phase_name: str,
        stratagem_name: str,
    ) -> Any:
        if self.game is None or not bool(getattr(self.game, "is_authoritative", True)):
            return None
        root = self._ac_root(unit)
        if root is None:
            return None
        unit_id = self._ac_sort_key(root)
        if not unit_id:
            return None
        player_id = str(getattr(self.player, "id", "") or "")
        turn = self._ac_current_turn()
        turn_owner_id = self._ac_turn_owner_id()
        phase_label = str(phase_name or "").strip() or "Shooting phase"
        if self._ac_pending_choose_quarry_request(
            player_id=player_id,
            ctx_filters={
                "ability": "adeptus_custodes_shield_host_archeotech_munitions_choice",
                "unit_id": unit_id,
                "phase_name": phase_label,
                "turn": turn,
                "turn_owner_id": turn_owner_id,
            },
        ):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{str(stratagem_name or '').strip() or 'ARCHEOTECH MUNITIONS'}: choose a ranged weapon ability.",
            player_id=player_id,
            options=[
                DecisionOption.create(
                    "Lethal Hits",
                    payload={"choice_key": "LETHAL_HITS", "unit_id": unit_id},
                ),
                DecisionOption.create(
                    "Sustained Hits 1",
                    payload={"choice_key": "SUSTAINED_HITS_1", "unit_id": unit_id},
                ),
            ],
            context={
                "ability": "adeptus_custodes_shield_host_archeotech_munitions_choice",
                "ability_name": str(stratagem_name or "").strip() or "ARCHEOTECH MUNITIONS",
                "army_id": str(get_entity_id(getattr(self.player, "army", None)) or ""),
                "unit_id": unit_id,
                "phase_name": phase_label,
                "attack_type": "ranged",
                "turn": turn,
                "turn_owner_id": turn_owner_id,
                "candidate_choice_keys": ["LETHAL_HITS", "SUSTAINED_HITS_1"],
                "stratagem_name": str(stratagem_name or "").strip() or "ARCHEOTECH MUNITIONS",
                "optional": False,
            },
        )

    def validate_shield_host_archeotech_munitions_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        attack_type: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
    ) -> tuple[bool, str]:
        root = self._ac_root(unit)
        if root is None:
            return False, "ARCHEOTECH MUNITIONS choice unit was not found."
        if player is not None and player is not self.player:
            return False, "ARCHEOTECH MUNITIONS choice must be resolved by the owning player."
        if not self._is_shield_host_detachment():
            return False, "ARCHEOTECH MUNITIONS requires Shield Host."
        if not self._ac_owned_by_player(root):
            return False, "ARCHEOTECH MUNITIONS target must belong to you."
        if not self._ac_unit_on_battlefield(root):
            return False, "ARCHEOTECH MUNITIONS target must be on the battlefield."
        if self._unit_cannot_be_target_of_stratagem(root):
            return False, "ARCHEOTECH MUNITIONS target can no longer be selected."
        if not self._ac_is_custodes_unit(root) or self._ac_is_anathema_psykana_unit(root):
            return False, "ARCHEOTECH MUNITIONS target must be a non-Anathema Adeptus Custodes unit."
        if game is not None:
            current_phase = self._ac_phase_key(getattr(getattr(game, "phase", None), "name", "") or "")
            expected_phase = self._ac_phase_key(phase_name)
            if current_phase and expected_phase and current_phase != expected_phase:
                return False, "ARCHEOTECH MUNITIONS choice is no longer in the same phase."
            if int(turn or 0) > 0 and int(getattr(game, "turn", 0) or 0) != int(turn or 0):
                return False, "ARCHEOTECH MUNITIONS choice is no longer in the same battle round."
            current_owner_id = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "")
            if turn_owner_id and current_owner_id and current_owner_id != str(turn_owner_id):
                return False, "ARCHEOTECH MUNITIONS choice is no longer in the same turn."
        if self._ac_phase_name_lower(phase_name) != "shooting phase":
            return False, "ARCHEOTECH MUNITIONS choice requires the Shooting phase."
        if attack_type and str(attack_type or "").strip().lower() != "ranged":
            return False, "ARCHEOTECH MUNITIONS choice payload does not match the phase."
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "shot_this_round", False)):
            return False, "ARCHEOTECH MUNITIONS target has already been selected to shoot."
        if not self._ac_unit_has_weapon_type(root, "ranged"):
            return False, "ARCHEOTECH MUNITIONS target has no ranged weapons."
        choice_key = self._shield_host_archeotech_munitions_choice_key(
            payload.get("choice_key", "") or payload.get("choice", "")
        )
        if choice_key not in {"LETHAL_HITS", "SUSTAINED_HITS_1"}:
            return False, "ARCHEOTECH MUNITIONS choice must be LETHAL HITS or SUSTAINED HITS 1."
        resolved_name = str(stratagem_name or payload.get("stratagem_name", "") or "").strip().upper()
        if resolved_name and resolved_name != "ARCHEOTECH MUNITIONS":
            return False, "ARCHEOTECH MUNITIONS choice payload does not match the stratagem."
        return True, ""

    def apply_shield_host_archeotech_munitions_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        attack_type: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
    ) -> Any:
        valid, _reason = self.validate_shield_host_archeotech_munitions_choice(
            unit,
            payload,
            game=game,
            player=player,
            phase_name=phase_name,
            attack_type=attack_type,
            turn=turn,
            turn_owner_id=turn_owner_id,
            stratagem_name=stratagem_name,
        )
        if not valid:
            return None
        root = self._ac_root(unit)
        if root is None:
            return None
        choice_key = self._shield_host_archeotech_munitions_choice_key(
            payload.get("choice_key", "") or payload.get("choice", "")
        )
        return self._apply_shield_host_archeotech_munitions_effect(
            root,
            choice_key=choice_key,
            phase_name=phase_name,
            stratagem_name=str(stratagem_name or payload.get("stratagem_name", "") or "ARCHEOTECH MUNITIONS"),
        )

    def _apply_shield_host_archeotech_munitions_effect(
        self,
        unit: Any,
        *,
        choice_key: str,
        phase_name: str,
        stratagem_name: str,
    ) -> dict[str, Any] | None:
        root = self._ac_root(unit)
        if root is None:
            return None
        resolved_choice = self._shield_host_archeotech_munitions_choice_key(choice_key)
        keyword_bonuses = self._shield_host_archeotech_munitions_choice_keywords(resolved_choice)
        if not keyword_bonuses:
            return None
        root_id = self._ac_sort_key(root) or str(id(root))
        phase_key = self._ac_phase_key(phase_name)
        for model in self._ac_alive_models(root):
            set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
            if not callable(set_keywords):
                continue
            model_id = self._ac_sort_key(model) or str(id(model))
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                set_keywords(
                    key=f"custodes_shield_host_archeotech_munitions:{root_id}:{model_id}:{weapon_name}:{resolved_choice}".lower(),
                    weapon_name=weapon_name,
                    keywords=list(keyword_bonuses),
                    source=str(stratagem_name or "ARCHEOTECH MUNITIONS").strip() or "ARCHEOTECH MUNITIONS",
                    expires_phase=phase_key,
                    attack_type="ranged",
                )
        special_rules = dict(getattr(root, "special_rules", {}) or {})
        special_rules["custodes_shield_host_archeotech_munitions_active"] = True
        special_rules["custodes_shield_host_archeotech_munitions_choice_key"] = resolved_choice
        special_rules["custodes_shield_host_archeotech_munitions_turn"] = self._ac_current_turn()
        special_rules["custodes_shield_host_archeotech_munitions_turn_owner"] = self._ac_turn_owner_id()
        special_rules["custodes_shield_host_archeotech_munitions_expires_phase"] = phase_key
        special_rules["custodes_shield_host_archeotech_munitions_source"] = (
            str(stratagem_name or "ARCHEOTECH MUNITIONS").strip() or "ARCHEOTECH MUNITIONS"
        )
        root.special_rules = special_rules
        return {
            "unit_id": self._ac_sort_key(root),
            "unit_name": str(getattr(root, "name", "Unit") or "Unit"),
            "choice_key": resolved_choice,
            "choice_label": self._shield_host_archeotech_munitions_choice_label(resolved_choice),
            "attack_type": "ranged",
            "stratagem_name": str(stratagem_name or "ARCHEOTECH MUNITIONS").strip() or "ARCHEOTECH MUNITIONS",
        }

    def _build_shield_host_vigilance_eternal_objective_request(
        self,
        *,
        unit: Any,
        objectives: list[Any],
        phase_name: str,
        stratagem_name: str,
    ) -> Any:
        if self.game is None or not bool(getattr(self.game, "is_authoritative", True)):
            return None
        root = self._ac_root(unit)
        if root is None:
            return None
        unit_id = self._ac_sort_key(root)
        candidate_objective_ids = [
            self._ac_objective_sort_key(objective)
            for objective in list(objectives or [])
            if self._ac_objective_sort_key(objective)
        ]
        if not unit_id or not candidate_objective_ids:
            return None
        player_id = str(getattr(self.player, "id", "") or "")
        turn = self._ac_current_turn()
        turn_owner_id = self._ac_turn_owner_id()
        phase_label = str(phase_name or "").strip() or "Movement phase"
        if self._ac_pending_choose_quarry_request(
            player_id=player_id,
            ctx_filters={
                "ability": "adeptus_custodes_shield_host_vigilance_eternal_objective",
                "unit_id": unit_id,
                "phase_name": phase_label,
                "turn": turn,
                "turn_owner_id": turn_owner_id,
            },
        ):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{str(stratagem_name or '').strip() or 'VIGILANCE ETERNAL'}: select one objective marker within range of {getattr(root, 'name', 'Unit')}.",
            player_id=player_id,
            options=[
                DecisionOption.create(
                    str(getattr(objective, "name", "Objective") or "Objective"),
                    payload={
                        "unit_id": unit_id,
                        "source_unit_id": unit_id,
                        "objective_id": self._ac_objective_sort_key(objective),
                    },
                )
                for objective in list(objectives or [])
                if self._ac_objective_sort_key(objective)
            ],
            context={
                "ability": "adeptus_custodes_shield_host_vigilance_eternal_objective",
                "ability_name": str(stratagem_name or "").strip() or "VIGILANCE ETERNAL",
                "army_id": str(get_entity_id(getattr(self.player, "army", None)) or ""),
                "phase_name": phase_label,
                "unit_id": unit_id,
                "source_unit_id": unit_id,
                "turn": turn,
                "turn_owner_id": turn_owner_id,
                "candidate_objective_ids": list(candidate_objective_ids),
                "stratagem_name": str(stratagem_name or "").strip() or "VIGILANCE ETERNAL",
                "optional": False,
            },
        )

    def validate_shield_host_vigilance_eternal_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
        candidate_objective_ids: list[str] | None = None,
    ) -> tuple[bool, str]:
        root = self._ac_root(unit)
        if root is None:
            return False, "VIGILANCE ETERNAL source unit was not found."
        if player is not None and player is not self.player:
            return False, "VIGILANCE ETERNAL choice must be resolved by the owning player."
        if not self._is_shield_host_detachment():
            return False, "VIGILANCE ETERNAL requires Shield Host."
        if not self._ac_owned_by_player(root):
            return False, "VIGILANCE ETERNAL source unit must belong to you."
        if not self._ac_unit_on_battlefield(root):
            return False, "VIGILANCE ETERNAL source unit must be on the battlefield."
        if self._unit_cannot_be_target_of_stratagem(root):
            return False, "VIGILANCE ETERNAL source unit can no longer be selected."
        if not self._ac_is_custodes_unit(root) or self._ac_is_anathema_psykana_unit(root):
            return False, "VIGILANCE ETERNAL source unit must be a non-Anathema Adeptus Custodes unit."
        if not self._ac_has_keyword(root, "BATTLELINE"):
            return False, "VIGILANCE ETERNAL requires a Battleline unit."
        if game is not None:
            current_phase = self._ac_phase_key(getattr(getattr(game, "phase", None), "name", "") or "")
            expected_phase = self._ac_phase_key(phase_name)
            if current_phase and expected_phase and current_phase != expected_phase:
                return False, "VIGILANCE ETERNAL choice is no longer in the same phase."
            if int(turn or 0) > 0 and int(getattr(game, "turn", 0) or 0) != int(turn or 0):
                return False, "VIGILANCE ETERNAL choice is no longer in the same battle round."
            current_owner_id = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "")
            if turn_owner_id and current_owner_id and current_owner_id != str(turn_owner_id):
                return False, "VIGILANCE ETERNAL choice is no longer in the same turn."
        if self._ac_phase_name_lower(phase_name) != "movement phase":
            return False, "VIGILANCE ETERNAL choice requires the Movement phase."
        objective_id = str(payload.get("objective_id", "") or "").strip()
        if not objective_id:
            return False, "VIGILANCE ETERNAL selection requires objective_id."
        objective = self._ac_resolve_objective(objective_id)
        if objective is None:
            return False, "VIGILANCE ETERNAL objective was not found."
        allowed_ids = {
            str(value or "").strip()
            for value in list(candidate_objective_ids or [])
            if str(value or "").strip()
        }
        if allowed_ids and self._ac_objective_sort_key(objective) not in allowed_ids:
            return False, "VIGILANCE ETERNAL objective is not in this request's candidate list."
        if objective not in list(self._ac_controlled_objectives_in_range(root) or []):
            return False, "VIGILANCE ETERNAL objective is no longer controlled and in range of the source unit."
        resolved_name = str(stratagem_name or payload.get("stratagem_name", "") or "").strip().upper()
        if resolved_name and resolved_name != "VIGILANCE ETERNAL":
            return False, "VIGILANCE ETERNAL choice payload does not match the stratagem."
        return True, ""

    def apply_shield_host_vigilance_eternal_choice(
        self,
        unit: Any,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        turn: int = 0,
        turn_owner_id: str = "",
        stratagem_name: str = "",
        candidate_objective_ids: list[str] | None = None,
    ) -> Any:
        valid, _reason = self.validate_shield_host_vigilance_eternal_choice(
            unit,
            payload,
            game=game,
            player=player,
            phase_name=phase_name,
            turn=turn,
            turn_owner_id=turn_owner_id,
            stratagem_name=stratagem_name,
            candidate_objective_ids=candidate_objective_ids,
        )
        if not valid:
            return None
        root = self._ac_root(unit)
        if root is None:
            return None
        objective = self._ac_resolve_objective(
            payload.get("objective_id", ""),
            candidates=list(self._ac_controlled_objectives_in_range(root) or []),
        )
        if objective is None:
            return None
        return self._apply_shield_host_vigilance_eternal_effect(
            root,
            objective=objective,
            stratagem_name=str(stratagem_name or payload.get("stratagem_name", "") or "VIGILANCE ETERNAL"),
        )

    def _apply_shield_host_vigilance_eternal_effect(
        self,
        unit: Any,
        *,
        objective: Any,
        stratagem_name: str,
    ) -> dict[str, Any] | None:
        root = self._ac_root(unit)
        resolved_objective = self._ac_resolve_objective(objective)
        if root is None or resolved_objective is None:
            return None
        location = getattr(resolved_objective, "location", None) or resolved_objective
        set_sticky = getattr(location, "set_sticky_control", None)
        if not callable(set_sticky):
            return None
        set_sticky(self.player, source="vigilance_eternal")
        return {
            "unit_id": self._ac_sort_key(root),
            "unit_name": str(getattr(root, "name", "Unit") or "Unit"),
            "objective_id": self._ac_objective_sort_key(resolved_objective),
            "objective_name": str(
                getattr(resolved_objective, "name", "")
                or f"objective {self._ac_objective_sort_key(resolved_objective)}"
            ).strip()
            or f"objective {self._ac_objective_sort_key(resolved_objective)}",
            "stratagem_name": str(stratagem_name or "VIGILANCE ETERNAL").strip() or "VIGILANCE ETERNAL",
        }

    def _cleanup_adeptus_custodes_phase_end_effects(self, *, phase: Any) -> None:
        phase_key = self._ac_phase_key(getattr(phase, "name", "") or "")
        if phase_key not in {"MOVEMENT_PHASE", "CHARGE_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ac_root(unit)
            unit_id = self._ac_sort_key(root)
            if root is None or (unit_id and unit_id in seen):
                continue
            if unit_id:
                seen.add(unit_id)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            if phase_key == "MOVEMENT_PHASE" or phase_key == "CHARGE_PHASE":
                exp = str(sr.get("custodes_solar_spearhead_unstoppable_expires_phase", "") or "").strip().upper()
                if sr.get("custodes_solar_spearhead_unstoppable_active") and (not exp or exp == phase_key):
                    added = set(sr.get("custodes_solar_spearhead_unstoppable_added_phase_move_terrain_only_types") or [])
                    if added:
                        current = list(sr.get("bearer_unit_phase_move_terrain_only_types") or [])
                        kept = [move_type for move_type in current if move_type not in added]
                        if kept:
                            sr["bearer_unit_phase_move_terrain_only_types"] = kept
                        else:
                            sr.pop("bearer_unit_phase_move_terrain_only_types", None)
                    for key in (
                        "custodes_solar_spearhead_unstoppable_active",
                        "custodes_solar_spearhead_unstoppable_expires_phase",
                        "custodes_solar_spearhead_unstoppable_turn_owner",
                        "custodes_solar_spearhead_unstoppable_turn",
                        "custodes_solar_spearhead_unstoppable_source",
                        "custodes_solar_spearhead_unstoppable_added_phase_move_terrain_only_types",
                    ):
                        sr.pop(key, None)
                    changed = True
            if phase_key == "SHOOTING_PHASE":
                exp = str(sr.get("custodes_solar_spearhead_punishment_inescapable_expires_phase", "") or "").strip().upper()
                if sr.get("custodes_solar_spearhead_punishment_inescapable_active") and (not exp or exp == phase_key):
                    for key in (
                        "custodes_solar_spearhead_punishment_inescapable_active",
                        "custodes_solar_spearhead_punishment_inescapable_expires_phase",
                        "custodes_solar_spearhead_punishment_inescapable_turn_owner",
                        "custodes_solar_spearhead_punishment_inescapable_turn",
                        "custodes_solar_spearhead_punishment_inescapable_source",
                        "custodes_solar_spearhead_punishment_inescapable_default_choice",
                    ):
                        sr.pop(key, None)
                    changed = True
                exp = str(sr.get("custodes_talons_talons_interlocked_expires_phase", "") or "").strip().upper()
                if sr.get("custodes_talons_talons_interlocked_active") and (not exp or exp == phase_key):
                    for key in (
                        "custodes_talons_talons_interlocked_active",
                        "custodes_talons_talons_interlocked_target_id",
                        "custodes_talons_talons_interlocked_expires_phase",
                        "custodes_talons_talons_interlocked_turn_owner",
                        "custodes_talons_talons_interlocked_turn",
                        "custodes_talons_talons_interlocked_source",
                    ):
                        sr.pop(key, None)
                    changed = True
                exp = str(sr.get("custodes_talons_shield_of_honour_expires_phase", "") or "").strip().upper()
                if sr.get("custodes_talons_shield_of_honour_active") and (not exp or exp == phase_key):
                    for key in (
                        "custodes_talons_shield_of_honour_active",
                        "custodes_talons_shield_of_honour_support_unit_id",
                        "custodes_talons_shield_of_honour_attacker_unit_id",
                        "custodes_talons_shield_of_honour_expires_phase",
                        "custodes_talons_shield_of_honour_turn_owner",
                        "custodes_talons_shield_of_honour_turn",
                        "custodes_talons_shield_of_honour_source",
                    ):
                        sr.pop(key, None)
                    changed = True
            if phase_key == "FIGHT_PHASE":
                exp = str(sr.get("custodes_solar_spearhead_emperors_vengeance_expires_phase", "") or "").strip().upper()
                if sr.get("custodes_solar_spearhead_emperors_vengeance_active") and (not exp or exp == phase_key):
                    for key in (
                        "custodes_solar_spearhead_emperors_vengeance_active",
                        "custodes_solar_spearhead_emperors_vengeance_expires_phase",
                        "custodes_solar_spearhead_emperors_vengeance_turn_owner",
                        "custodes_solar_spearhead_emperors_vengeance_turn",
                        "custodes_solar_spearhead_emperors_vengeance_threshold",
                        "custodes_solar_spearhead_emperors_vengeance_source",
                    ):
                        sr.pop(key, None)
                    changed = True
                exp = str(sr.get("custodes_solar_spearhead_relentless_persecution_expires_phase", "") or "").strip().upper()
                if sr.get("custodes_solar_spearhead_relentless_persecution_active") and (not exp or exp == phase_key):
                    for key in (
                        "custodes_solar_spearhead_relentless_persecution_active",
                        "custodes_solar_spearhead_relentless_persecution_expires_phase",
                        "custodes_solar_spearhead_relentless_persecution_turn_owner",
                        "custodes_solar_spearhead_relentless_persecution_turn",
                        "custodes_solar_spearhead_relentless_persecution_source",
                    ):
                        sr.pop(key, None)
                    changed = True
                exp = str(sr.get("custodes_talons_emperors_executioners_expires_phase", "") or "").strip().upper()
                if sr.get("custodes_talons_emperors_executioners_active") and (not exp or exp == phase_key):
                    for key in (
                        "custodes_talons_emperors_executioners_active",
                        "custodes_talons_emperors_executioners_wound_bonus",
                        "custodes_talons_emperors_executioners_expires_phase",
                        "custodes_talons_emperors_executioners_turn_owner",
                        "custodes_talons_emperors_executioners_turn",
                        "custodes_talons_emperors_executioners_source",
                    ):
                        sr.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = sr

    def _use_adeptus_custodes_stratagem(self, stratagem, **kwargs):
        name_u = str(self._normalize_stratagem_name(getattr(stratagem, "name", "") or "")).strip()
        handled = {
            "ANATHEMA BLADEMASTERY",
            "ARCANE GENETIC ALCHEMY",
            "ARCHEOTECH MUNITIONS",
            "AVENGE THE FALLEN",
            "DESPERATION'S PRICE",
            "EARNING OF A NAME",
            "EMPEROR'S EXECUTIONERS",
            "EMPEROR'S VENGEANCE",
            "EMPYRIC SEVERANCE",
            "FLAWLESS CONSTRUCTION",
            "HUNT AS ONE",
            "MANOEUVRE AND FIRE",
            "MULTIPOTENTIALITY",
            "PEERLESS WARRIOR",
            "PSY-CHAFF VOLLEY",
            "PSYCHIC ABOMINATIONS",
            "PUNISHMENT INESCAPABLE",
            "PURGATION SWEEP",
            "RELENTLESS PERSECUTION",
            "SHIELD OF HONOUR",
            "SHOULDER THE MANTLE",
            "SLAYER OF CHAMPIONS",
            "SUPERHUMAN RESERVES",
            "SWIFT AS THE EAGLE",
            "TALONED PINCER",
            "TALONS INTERLOCKED",
            "THE EMPEROR'S AUSPICE",
            "UNSTOPPABLE",
            "UNWAVERING SENTINELS",
            "VIGIL UNENDING",
            "VIGILANCE ETERNAL",
            "WRATHFUL ADVANCE",
            "WITCH HUNTERS",
        }
        if name_u not in handled:
            return None
        if name_u in {
            "EARNING OF A NAME",
            "SHOULDER THE MANTLE",
            "SLAYER OF CHAMPIONS",
            "SUPERHUMAN RESERVES",
            "THE EMPEROR'S AUSPICE",
            "VIGIL UNENDING",
        } and not self._is_auric_champions_detachment():
            return False
        if name_u in {
            "MANOEUVRE AND FIRE",
            "PEERLESS WARRIOR",
            "SWIFT AS THE EAGLE",
        } and not self._is_lions_of_the_emperor_detachment():
            return False
        if name_u in {
            "ARCANE GENETIC ALCHEMY",
            "ARCHEOTECH MUNITIONS",
            "AVENGE THE FALLEN",
            "MULTIPOTENTIALITY",
            "UNWAVERING SENTINELS",
            "VIGILANCE ETERNAL",
        } and not self._is_shield_host_detachment():
            return False
        if name_u in {
            "EMPEROR'S VENGEANCE",
            "FLAWLESS CONSTRUCTION",
            "PUNISHMENT INESCAPABLE",
            "RELENTLESS PERSECUTION",
            "UNSTOPPABLE",
            "WRATHFUL ADVANCE",
        } and not self._is_solar_spearhead_detachment():
            return False
        if name_u in {
            "EMPEROR'S EXECUTIONERS",
            "EMPYRIC SEVERANCE",
            "HUNT AS ONE",
            "SHIELD OF HONOUR",
            "TALONED PINCER",
            "TALONS INTERLOCKED",
        } and not self._is_talons_of_the_emperor_detachment():
            return False
        if name_u in {
            "ANATHEMA BLADEMASTERY",
            "DESPERATION'S PRICE",
            "PSY-CHAFF VOLLEY",
            "PSYCHIC ABOMINATIONS",
            "PURGATION SWEEP",
            "WITCH HUNTERS",
        } and not self._is_null_maiden_vigil_detachment():
            return False

        phase_name = self._ac_current_phase_name(kwargs.get("phase_name"))
        pending = self._ac_pending_reaction(name_u)
        dequeue = bool(kwargs.get("dequeue"))

        if name_u == "ARCANE GENETIC ALCHEMY":
            source_unit = self._ac_root(
                kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("unit") or (pending or {}).get("target_unit")
            )
            target_model = kwargs.get("target_model") or (pending or {}).get("target_model")
            if source_unit is None or not self._ac_is_custodes_unit(source_unit) or self._ac_is_anathema_psykana_unit(source_unit):
                logger.error("ERROR: ARCANE GENETIC ALCHEMY: target must be a non-Anathema Adeptus Custodes unit")
                return False
            if target_model is not None and self._ac_model_has_keyword(target_model, "ANATHEMA PSYKANA"):
                logger.error("ERROR: ARCANE GENETIC ALCHEMY: target model cannot be Anathema Psykana")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            phase_key = self._ac_phase_key(phase_name)
            for model in self._ac_alive_models(source_unit):
                set_fnp = getattr(model, "set_temporary_fnp", None)
                if not callable(set_fnp):
                    continue
                set_fnp(
                    key=f"custodes_shield_host_arcane_genetic_alchemy_{get_entity_id(model)}",
                    value=4,
                    source=stratagem.name,
                    condition="against mortal wounds",
                    expires_phase=phase_key,
                )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "ARCHEOTECH MUNITIONS":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._shield_host_battlefield_unit_candidates(
                require_not_shot=True,
                attack_type="ranged",
            )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "shooting phase":
                logger.error("ERROR: ARCHEOTECH MUNITIONS: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: ARCHEOTECH MUNITIONS: must be your Shooting phase")
                return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit) or self._ac_is_anathema_psykana_unit(source_unit):
                logger.error("ERROR: ARCHEOTECH MUNITIONS: target must be a non-Anathema Adeptus Custodes unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: ARCHEOTECH MUNITIONS: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if bool(getattr(getattr(source_unit, "round_state", None), "shot_this_round", False)):
                logger.error("ERROR: ARCHEOTECH MUNITIONS: target has already been selected to shoot")
                return False
            if not self._ac_unit_has_weapon_type(source_unit, "ranged"):
                logger.error("ERROR: ARCHEOTECH MUNITIONS: target has no ranged weapons")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            choice_key = self._shield_host_archeotech_munitions_choice_key(
                kwargs.get("choice_key", "") or kwargs.get("choice", "") or kwargs.get("selected_choice", "")
            )
            if choice_key:
                valid, reason = self.validate_shield_host_archeotech_munitions_choice(
                    source_unit,
                    {"choice_key": choice_key, "stratagem_name": stratagem.name},
                    game=self.game,
                    player=self.player,
                    phase_name=phase_name,
                    attack_type="ranged",
                    turn=self._ac_current_turn(),
                    turn_owner_id=self._ac_turn_owner_id(),
                    stratagem_name=stratagem.name,
                )
                if not valid:
                    logger.error("ERROR: ARCHEOTECH MUNITIONS: %s", reason)
                    return False
                if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                    return False
                if self._apply_shield_host_archeotech_munitions_effect(
                    source_unit,
                    choice_key=choice_key,
                    phase_name=phase_name,
                    stratagem_name=stratagem.name,
                ) is None:
                    return False
                self._ac_finalize_use(stratagem, dequeue=dequeue)
                return True
            choice_request = self._build_shield_host_archeotech_munitions_choice_request(
                unit=source_unit,
                phase_name=phase_name,
                stratagem_name=str(getattr(stratagem, "name", "") or "ARCHEOTECH MUNITIONS"),
            )
            if choice_request is None:
                logger.error("ERROR: ARCHEOTECH MUNITIONS: failed to build choice request")
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            if not self._ac_submit_decision_request(choice_request):
                logger.error("ERROR: ARCHEOTECH MUNITIONS: failed to queue choice request")
                return False
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "AVENGE THE FALLEN":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._shield_host_battlefield_unit_candidates(
                require_not_fought=True,
                require_below_starting_strength=True,
                attack_type="melee",
            )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "fight phase":
                logger.error("ERROR: AVENGE THE FALLEN: wrong phase")
                return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit) or self._ac_is_anathema_psykana_unit(source_unit):
                logger.error("ERROR: AVENGE THE FALLEN: target must be a non-Anathema Adeptus Custodes unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: AVENGE THE FALLEN: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if not bool(getattr(source_unit, "is_below_starting_strength", lambda: False)()):
                logger.error("ERROR: AVENGE THE FALLEN: target must be below Starting Strength")
                return False
            if not self._ac_unit_has_weapon_type(source_unit, "melee"):
                logger.error("ERROR: AVENGE THE FALLEN: target has no melee weapons")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            attacks_bonus = 2 if bool(getattr(source_unit, "is_below_half_strength", lambda: False)()) else 1
            phase_key = self._ac_phase_key(phase_name)
            root_id = self._ac_sort_key(source_unit) or str(id(source_unit))
            for model in self._ac_alive_models(source_unit):
                set_bonus = getattr(model, "set_temporary_weapon_bonus", None)
                if not callable(set_bonus):
                    continue
                model_id = self._ac_sort_key(model) or str(id(model))
                for wargear in list(getattr(model, "wargear", []) or []):
                    if wargear is None:
                        continue
                    is_melee = getattr(wargear, "is_melee", None)
                    if not callable(is_melee) or not bool(is_melee()):
                        continue
                    weapon_name = str(getattr(wargear, "name", "") or "").strip()
                    if not weapon_name:
                        continue
                    set_bonus(
                        key=f"custodes_shield_host_avenge_the_fallen:{root_id}:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        attacks_bonus=int(attacks_bonus),
                        source=stratagem.name,
                        expires_phase=phase_key,
                    )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "MULTIPOTENTIALITY":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._shield_host_battlefield_unit_candidates(
                require_fell_back=True,
            )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "movement phase":
                logger.error("ERROR: MULTIPOTENTIALITY: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: MULTIPOTENTIALITY: must be your Movement phase")
                return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit) or self._ac_is_anathema_psykana_unit(source_unit):
                logger.error("ERROR: MULTIPOTENTIALITY: target must be a non-Anathema Adeptus Custodes unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: MULTIPOTENTIALITY: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if not bool(getattr(getattr(source_unit, "round_state", None), "fell_back_this_round", False)):
                logger.error("ERROR: MULTIPOTENTIALITY: target must have Fallen Back this phase")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            special_rules = dict(getattr(source_unit, "special_rules", {}) or {})
            special_rules["manoeuvre_and_fire_active"] = True
            special_rules["manoeuvre_and_fire_turn"] = self._ac_current_turn()
            special_rules["manoeuvre_and_fire_turn_owner"] = self._ac_turn_owner_id()
            special_rules["custodes_shield_host_multipotentiality_active"] = True
            special_rules["custodes_shield_host_multipotentiality_turn"] = self._ac_current_turn()
            special_rules["custodes_shield_host_multipotentiality_turn_owner"] = self._ac_turn_owner_id()
            special_rules["custodes_shield_host_multipotentiality_source"] = stratagem.name
            source_unit.special_rules = special_rules
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "UNWAVERING SENTINELS":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            attacking_unit = self._ac_root(kwargs.get("attacking_unit") or (pending or {}).get("attacking_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            if not candidates:
                candidates = self._shield_host_unwavering_sentinels_candidates(list(kwargs.get("target_units") or []))
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "fight phase":
                logger.error("ERROR: UNWAVERING SENTINELS: wrong phase")
                return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit) or self._ac_is_anathema_psykana_unit(source_unit):
                logger.error("ERROR: UNWAVERING SENTINELS: target must be a non-Anathema Adeptus Custodes unit")
                return False
            if not self._ac_has_keyword(source_unit, "INFANTRY"):
                logger.error("ERROR: UNWAVERING SENTINELS: target must be an Infantry unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: UNWAVERING SENTINELS: target is not an eligible candidate")
                return False
            if attacking_unit is None or self._ac_owned_by_player(attacking_unit):
                logger.error("ERROR: UNWAVERING SENTINELS: missing enemy attacking unit")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if not self._ac_controlled_objectives_in_range(source_unit):
                logger.error("ERROR: UNWAVERING SENTINELS: target must be within range of a controlled objective marker")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            self._append_defensive_effect(
                source_unit,
                "defensive_hit_mods",
                {
                    "value": 1,
                    "attack_type": "melee",
                    "attacker_key": self._ac_sort_key(attacking_unit),
                    "expires_phase": "FIGHT_PHASE",
                    "source": str(getattr(stratagem, "name", "") or "UNWAVERING SENTINELS"),
                },
            )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "VIGILANCE ETERNAL":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._shield_host_battlefield_unit_candidates(
                require_battleline=True,
            )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "movement phase":
                logger.error("ERROR: VIGILANCE ETERNAL: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: VIGILANCE ETERNAL: must be your Movement phase")
                return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit) or self._ac_is_anathema_psykana_unit(source_unit):
                logger.error("ERROR: VIGILANCE ETERNAL: target must be a non-Anathema Adeptus Custodes unit")
                return False
            if not self._ac_has_keyword(source_unit, "BATTLELINE"):
                logger.error("ERROR: VIGILANCE ETERNAL: target must be a Battleline unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: VIGILANCE ETERNAL: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            objective_candidates = list(kwargs.get("objective_candidates") or []) or self._ac_controlled_objectives_in_range(source_unit)
            objective = self._ac_resolve_objective(
                kwargs.get("objective") or kwargs.get("objective_marker") or kwargs.get("objective_id"),
                candidates=objective_candidates,
            )
            if not objective_candidates:
                logger.error("ERROR: VIGILANCE ETERNAL: target must be within range of a controlled objective marker")
                return False
            if objective is None and len(objective_candidates) == 1:
                objective = objective_candidates[0]
            if objective is None:
                choice_request = self._build_shield_host_vigilance_eternal_objective_request(
                    unit=source_unit,
                    objectives=objective_candidates,
                    phase_name=phase_name,
                    stratagem_name=str(getattr(stratagem, "name", "") or "VIGILANCE ETERNAL"),
                )
                if choice_request is None:
                    logger.error("ERROR: VIGILANCE ETERNAL: failed to build objective request")
                    return False
                if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                    return False
                if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                    return False
                if not self._ac_submit_decision_request(choice_request):
                    logger.error("ERROR: VIGILANCE ETERNAL: failed to queue objective request")
                    return False
                self._ac_finalize_use(stratagem, dequeue=dequeue)
                return True
            if objective not in list(objective_candidates or []):
                logger.error("ERROR: VIGILANCE ETERNAL: selected objective is not an eligible candidate")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            if self._apply_shield_host_vigilance_eternal_effect(
                source_unit,
                objective=objective,
                stratagem_name=str(getattr(stratagem, "name", "") or "VIGILANCE ETERNAL"),
            ) is None:
                return False
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "EMPEROR'S VENGEANCE":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            attacking_unit = self._ac_root(kwargs.get("attacking_unit") or (pending or {}).get("attacking_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            if not candidates:
                candidates = self._solar_spearhead_targeted_unit_candidates(list(kwargs.get("target_units") or []))
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "fight phase":
                logger.error("ERROR: EMPEROR'S VENGEANCE: wrong phase")
                return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit):
                logger.error("ERROR: EMPEROR'S VENGEANCE: target must be an Adeptus Custodes unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: EMPEROR'S VENGEANCE: target is not an eligible candidate")
                return False
            if attacking_unit is None or self._ac_owned_by_player(attacking_unit):
                logger.error("ERROR: EMPEROR'S VENGEANCE: missing enemy attacking unit")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            threshold = 3 if self._ac_has_keyword(source_unit, "WALKER") else 4
            special_rules = dict(getattr(source_unit, "special_rules", {}) or {})
            special_rules["custodes_solar_spearhead_emperors_vengeance_active"] = True
            special_rules["custodes_solar_spearhead_emperors_vengeance_turn"] = self._ac_current_turn()
            special_rules["custodes_solar_spearhead_emperors_vengeance_turn_owner"] = self._ac_turn_owner_id()
            special_rules["custodes_solar_spearhead_emperors_vengeance_expires_phase"] = "FIGHT_PHASE"
            special_rules["custodes_solar_spearhead_emperors_vengeance_threshold"] = int(threshold)
            special_rules["custodes_solar_spearhead_emperors_vengeance_source"] = stratagem.name
            source_unit.special_rules = special_rules
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "FLAWLESS CONSTRUCTION":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            attacking_unit = self._ac_root(kwargs.get("attacking_unit") or (pending or {}).get("attacking_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            if not candidates:
                candidates = self._solar_spearhead_targeted_unit_candidates(
                    list(kwargs.get("target_units") or []),
                    require_vehicle=True,
                )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            phase_key = self._ac_phase_key(phase_name)
            if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                logger.error("ERROR: FLAWLESS CONSTRUCTION: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if phase_key == "SHOOTING_PHASE" and active_player is self.player:
                logger.error("ERROR: FLAWLESS CONSTRUCTION: must be your opponent's Shooting phase")
                return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit):
                logger.error("ERROR: FLAWLESS CONSTRUCTION: target must be an Adeptus Custodes unit")
                return False
            is_vehicle = bool(getattr(source_unit, "is_vehicle", False)) or self._ac_has_keyword(source_unit, "VEHICLE")
            if not is_vehicle:
                logger.error("ERROR: FLAWLESS CONSTRUCTION: target must be a Vehicle unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: FLAWLESS CONSTRUCTION: target is not an eligible candidate")
                return False
            if attacking_unit is None or self._ac_owned_by_player(attacking_unit):
                logger.error("ERROR: FLAWLESS CONSTRUCTION: missing enemy attacking unit")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            self._append_defensive_effect(
                source_unit,
                "defensive_wound_mods",
                {
                    "value": 1,
                    "attack_type": "any",
                    "expires_phase": phase_key,
                    "source": str(getattr(stratagem, "name", "") or "FLAWLESS CONSTRUCTION"),
                    "requires_strength_gt_toughness": True,
                },
            )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "PUNISHMENT INESCAPABLE":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._solar_spearhead_battlefield_unit_candidates(
                require_not_shot=True,
                attack_type="ranged",
            )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "shooting phase":
                logger.error("ERROR: PUNISHMENT INESCAPABLE: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: PUNISHMENT INESCAPABLE: must be your Shooting phase")
                return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit):
                logger.error("ERROR: PUNISHMENT INESCAPABLE: target must be an Adeptus Custodes unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: PUNISHMENT INESCAPABLE: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if bool(getattr(getattr(source_unit, "round_state", None), "shot_this_round", False)):
                logger.error("ERROR: PUNISHMENT INESCAPABLE: target has already been selected to shoot")
                return False
            if not self._ac_unit_has_weapon_type(source_unit, "ranged"):
                logger.error("ERROR: PUNISHMENT INESCAPABLE: target must have ranged weapons")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            root_id = self._ac_sort_key(source_unit) or str(id(source_unit))
            phase_key = self._ac_phase_key(phase_name)
            for model in self._ac_alive_models(source_unit):
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if not callable(set_keywords):
                    continue
                model_id = self._ac_sort_key(model) or str(id(model))
                for wargear in list(getattr(model, "wargear", []) or []):
                    if wargear is None:
                        continue
                    is_ranged = getattr(wargear, "is_ranged", None)
                    if not callable(is_ranged) or not bool(is_ranged()):
                        continue
                    weapon_name = str(getattr(wargear, "name", "") or "").strip()
                    if not weapon_name:
                        continue
                    set_keywords(
                        key=f"custodes_solar_spearhead_punishment_inescapable:{root_id}:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        keywords=["IGNORES COVER"],
                        source=str(getattr(stratagem, "name", "") or "PUNISHMENT INESCAPABLE"),
                        expires_phase=phase_key,
                        attack_type="ranged",
                    )
            special_rules = dict(getattr(source_unit, "special_rules", {}) or {})
            special_rules["custodes_solar_spearhead_punishment_inescapable_active"] = True
            special_rules["custodes_solar_spearhead_punishment_inescapable_turn"] = self._ac_current_turn()
            special_rules["custodes_solar_spearhead_punishment_inescapable_turn_owner"] = self._ac_turn_owner_id()
            special_rules["custodes_solar_spearhead_punishment_inescapable_expires_phase"] = "SHOOTING_PHASE"
            special_rules["custodes_solar_spearhead_punishment_inescapable_source"] = stratagem.name
            special_rules["custodes_solar_spearhead_punishment_inescapable_default_choice"] = "ignore_all"
            source_unit.special_rules = special_rules
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "RELENTLESS PERSECUTION":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._solar_spearhead_battlefield_unit_candidates(
                require_vehicle=True,
                require_advanced=True,
            )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "movement phase":
                logger.error("ERROR: RELENTLESS PERSECUTION: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: RELENTLESS PERSECUTION: must be your Movement phase")
                return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit):
                logger.error("ERROR: RELENTLESS PERSECUTION: target must be an Adeptus Custodes unit")
                return False
            is_vehicle = bool(getattr(source_unit, "is_vehicle", False)) or self._ac_has_keyword(source_unit, "VEHICLE")
            if not is_vehicle:
                logger.error("ERROR: RELENTLESS PERSECUTION: target must be a Vehicle unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: RELENTLESS PERSECUTION: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if not bool(getattr(getattr(source_unit, "round_state", None), "advanced_this_round", False)):
                logger.error("ERROR: RELENTLESS PERSECUTION: target must have Advanced this phase")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            special_rules = dict(getattr(source_unit, "special_rules", {}) or {})
            special_rules["custodes_solar_spearhead_relentless_persecution_active"] = True
            special_rules["custodes_solar_spearhead_relentless_persecution_turn"] = self._ac_current_turn()
            special_rules["custodes_solar_spearhead_relentless_persecution_turn_owner"] = self._ac_turn_owner_id()
            special_rules["custodes_solar_spearhead_relentless_persecution_expires_phase"] = "FIGHT_PHASE"
            special_rules["custodes_solar_spearhead_relentless_persecution_source"] = stratagem.name
            source_unit.special_rules = special_rules
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "UNSTOPPABLE":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._solar_spearhead_battlefield_unit_candidates(
                require_vehicle_or_mounted=True,
            )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            phase_key = self._ac_phase_key(phase_name)
            if phase_key not in {"MOVEMENT_PHASE", "CHARGE_PHASE"}:
                logger.error("ERROR: UNSTOPPABLE: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: UNSTOPPABLE: must be your Movement or Charge phase")
                return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit):
                logger.error("ERROR: UNSTOPPABLE: target must be an Adeptus Custodes unit")
                return False
            is_vehicle = bool(getattr(source_unit, "is_vehicle", False)) or self._ac_has_keyword(source_unit, "VEHICLE")
            is_mounted = bool(getattr(source_unit, "is_mounted", False)) or self._ac_has_keyword(source_unit, "MOUNTED")
            if not (is_vehicle or is_mounted):
                logger.error("ERROR: UNSTOPPABLE: target must be a Vehicle or Mounted unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: UNSTOPPABLE: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            move_types = {"charge"} if phase_key == "CHARGE_PHASE" else {"move", "advance", "fall_back"}
            special_rules = dict(getattr(source_unit, "special_rules", {}) or {})
            current = set(special_rules.get("bearer_unit_phase_move_terrain_only_types") or [])
            added = set()
            for move_type in move_types:
                if move_type not in current:
                    current.add(move_type)
                    added.add(move_type)
            if current:
                special_rules["bearer_unit_phase_move_terrain_only_types"] = sorted(current)
            if added:
                special_rules["custodes_solar_spearhead_unstoppable_added_phase_move_terrain_only_types"] = sorted(added)
            special_rules["custodes_solar_spearhead_unstoppable_active"] = True
            special_rules["custodes_solar_spearhead_unstoppable_turn"] = self._ac_current_turn()
            special_rules["custodes_solar_spearhead_unstoppable_turn_owner"] = self._ac_turn_owner_id()
            special_rules["custodes_solar_spearhead_unstoppable_expires_phase"] = phase_key
            special_rules["custodes_solar_spearhead_unstoppable_source"] = stratagem.name
            source_unit.special_rules = special_rules
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "WRATHFUL ADVANCE":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._solar_spearhead_battlefield_unit_candidates(
                require_not_fought=True,
            )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "fight phase":
                logger.error("ERROR: WRATHFUL ADVANCE: wrong phase")
                return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit):
                logger.error("ERROR: WRATHFUL ADVANCE: target must be an Adeptus Custodes unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: WRATHFUL ADVANCE: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if bool(getattr(getattr(source_unit, "round_state", None), "fought_this_phase", False)):
                logger.error("ERROR: WRATHFUL ADVANCE: target has already fought this phase")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            max_distance = float(max(1, int(dice_module.get_roll("D3") or 0)) + 3)
            special_rules = dict(getattr(source_unit, "special_rules", {}) or {})
            special_rules["stratagem_pile_in_distance_override"] = max(
                float(special_rules.get("stratagem_pile_in_distance_override", 0.0) or 0.0),
                max_distance,
            )
            special_rules["stratagem_pile_in_expires_phase"] = "FIGHT_PHASE"
            special_rules["stratagem_pile_in_source"] = stratagem.name
            source_unit.special_rules = special_rules
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "ANATHEMA BLADEMASTERY":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._null_maiden_anathema_blademastery_candidates()
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "fight phase":
                logger.error("ERROR: ANATHEMA BLADEMASTERY: wrong phase")
                return False
            if source_unit is None or not self._ac_unit_name_startswith(source_unit, ("Vigilators",)):
                logger.error("ERROR: ANATHEMA BLADEMASTERY: target must be a Vigilators unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: ANATHEMA BLADEMASTERY: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if bool(getattr(getattr(source_unit, "round_state", None), "fought_this_phase", False)):
                logger.error("ERROR: ANATHEMA BLADEMASTERY: target has already fought this phase")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            special_rules = dict(getattr(source_unit, "special_rules", {}) or {})
            special_rules["custodes_null_maiden_anathema_blademastery_active"] = True
            special_rules["custodes_null_maiden_anathema_blademastery_turn"] = self._ac_current_turn()
            special_rules["custodes_null_maiden_anathema_blademastery_turn_owner"] = self._ac_turn_owner_id()
            special_rules["custodes_null_maiden_anathema_blademastery_expires_phase"] = "FIGHT_PHASE"
            special_rules["custodes_null_maiden_anathema_blademastery_source"] = stratagem.name
            source_unit.special_rules = special_rules
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "PURGATION SWEEP":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._null_maiden_purgation_sweep_candidates()
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "shooting phase":
                logger.error("ERROR: PURGATION SWEEP: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: PURGATION SWEEP: must be your Shooting phase")
                return False
            if source_unit is None or not self._ac_unit_name_startswith(source_unit, ("Witchseekers",)):
                logger.error("ERROR: PURGATION SWEEP: target must be a Witchseekers unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: PURGATION SWEEP: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if bool(getattr(getattr(source_unit, "round_state", None), "shot_this_round", False)):
                logger.error("ERROR: PURGATION SWEEP: target has already been selected to shoot")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            special_rules = dict(getattr(source_unit, "special_rules", {}) or {})
            special_rules["custodes_null_maiden_purgation_sweep_active"] = True
            special_rules["custodes_null_maiden_purgation_sweep_turn"] = self._ac_current_turn()
            special_rules["custodes_null_maiden_purgation_sweep_turn_owner"] = self._ac_turn_owner_id()
            special_rules["custodes_null_maiden_purgation_sweep_expires_phase"] = "SHOOTING_PHASE"
            special_rules["custodes_null_maiden_purgation_sweep_source"] = stratagem.name
            source_unit.special_rules = special_rules
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "WITCH HUNTERS":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            phase_lower = self._ac_phase_name_lower(phase_name)
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._null_maiden_witch_hunters_candidates(
                phase_name=phase_name,
            )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if phase_lower not in {"shooting phase", "fight phase"}:
                logger.error("ERROR: WITCH HUNTERS: wrong phase")
                return False
            if source_unit is None or not self._ac_is_anathema_psykana_unit(source_unit):
                logger.error("ERROR: WITCH HUNTERS: target must be an Anathema Psykana unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: WITCH HUNTERS: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            choice_key = self._null_maiden_witch_hunters_choice_key(
                kwargs.get("choice_key", "") or kwargs.get("choice", "") or kwargs.get("selected_choice", "")
            )
            if choice_key:
                valid, reason = self.validate_null_maiden_witch_hunters_choice(
                    source_unit,
                    {"choice_key": choice_key, "stratagem_name": stratagem.name},
                    game=self.game,
                    player=self.player,
                    phase_name=phase_name,
                    attack_type="ranged" if phase_lower == "shooting phase" else "melee",
                    turn=self._ac_current_turn(),
                    turn_owner_id=self._ac_turn_owner_id(),
                    stratagem_name=stratagem.name,
                )
                if not valid:
                    logger.error("ERROR: WITCH HUNTERS: %s", reason)
                    return False
                if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                    return False
                if self._apply_null_maiden_witch_hunters_effect(
                    source_unit,
                    choice_key=choice_key,
                    phase_name=phase_name,
                    stratagem_name=stratagem.name,
                ) is None:
                    return False
                self._ac_finalize_use(stratagem, dequeue=dequeue)
                return True
            choice_request = self._build_null_maiden_witch_hunters_choice_request(
                unit=source_unit,
                phase_name=phase_name,
                stratagem_name=str(getattr(stratagem, "name", "") or "WITCH HUNTERS"),
            )
            if choice_request is None:
                logger.error("ERROR: WITCH HUNTERS: failed to build choice request")
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            if not self._ac_submit_decision_request(choice_request):
                logger.error("ERROR: WITCH HUNTERS: failed to queue choice request")
                return False
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "PSYCHIC ABOMINATIONS":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            attacking_unit = self._ac_root(kwargs.get("attacking_unit") or (pending or {}).get("attacking_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            if not candidates:
                candidates = self._null_maiden_psychic_abominations_candidates(list(kwargs.get("target_units") or []))
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if self._ac_phase_name_lower(phase_name) != "shooting phase":
                logger.error("ERROR: PSYCHIC ABOMINATIONS: wrong phase")
                return False
            if source_unit is None or not self._ac_is_anathema_psykana_unit(source_unit) or not self._ac_has_keyword(source_unit, "INFANTRY"):
                logger.error("ERROR: PSYCHIC ABOMINATIONS: target must be an Anathema Psykana Infantry unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: PSYCHIC ABOMINATIONS: target is not an eligible candidate")
                return False
            if attacking_unit is None or self._ac_owned_by_player(attacking_unit):
                logger.error("ERROR: PSYCHIC ABOMINATIONS: missing enemy attacking unit")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            special_rules = dict(getattr(source_unit, "special_rules", {}) or {})
            special_rules["opponent_shooting_phase_stealth_active"] = True
            special_rules["opponent_shooting_phase_stealth_owner"] = self._ac_turn_owner_id()
            special_rules["opponent_shooting_phase_stealth_turn"] = self._ac_current_turn()
            special_rules["opponent_shooting_phase_stealth_source"] = stratagem.name
            special_rules["opponent_shooting_phase_stealth_expires_phase"] = "SHOOTING_PHASE"
            special_rules["custodes_null_maiden_psychic_abominations_active"] = True
            special_rules["custodes_null_maiden_psychic_abominations_turn"] = self._ac_current_turn()
            special_rules["custodes_null_maiden_psychic_abominations_turn_owner"] = self._ac_turn_owner_id()
            special_rules["custodes_null_maiden_psychic_abominations_expires_phase"] = "SHOOTING_PHASE"
            special_rules["custodes_null_maiden_psychic_abominations_targeting_range"] = 12.0
            special_rules["custodes_null_maiden_psychic_abominations_source"] = stratagem.name
            source_unit.special_rules = special_rules
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "PSY-CHAFF VOLLEY":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("unit"))
            enemy_unit = self._ac_root(kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit") or (pending or {}).get("enemy_unit"))
            enemy_candidates = self._ac_unique_units(list(kwargs.get("enemy_candidates") or (pending or {}).get("enemy_candidates") or []))
            if enemy_unit is None and len(enemy_candidates) == 1:
                enemy_unit = enemy_candidates[0]
            if self._ac_phase_name_lower(phase_name) != "shooting phase":
                logger.error("ERROR: PSY-CHAFF VOLLEY: wrong phase")
                return False
            if source_unit is None or not self._ac_unit_name_startswith(source_unit, ("Prosecutors",)):
                logger.error("ERROR: PSY-CHAFF VOLLEY: source must be a Prosecutors unit")
                return False
            if not self._ac_owned_by_player(source_unit) or not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            if enemy_unit is None or not self._ac_is_enemy_battlefield_unit(enemy_unit):
                logger.error("ERROR: PSY-CHAFF VOLLEY: missing enemy unit hit by the attacks")
                return False
            if enemy_candidates and enemy_unit not in enemy_candidates:
                logger.error("ERROR: PSY-CHAFF VOLLEY: selected enemy is not an eligible candidate")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            special_rules = dict(getattr(enemy_unit, "special_rules", {}) or {})
            special_rules["custodes_null_maiden_psy_chaff_volley_active"] = True
            special_rules["custodes_null_maiden_psy_chaff_volley_source_unit_id"] = self._ac_sort_key(source_unit)
            special_rules["custodes_null_maiden_psy_chaff_volley_turn"] = self._ac_current_turn()
            special_rules["custodes_null_maiden_psy_chaff_volley_turn_owner"] = str(getattr(self.player, "id", "") or "")
            special_rules["custodes_null_maiden_psy_chaff_volley_source"] = stratagem.name
            enemy_unit.special_rules = special_rules
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "DESPERATION'S PRICE":
            from ..units.status_effects import BattleShockEffect

            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("target_unit"))
            enemy_unit = self._ac_root(kwargs.get("enemy_unit") or (pending or {}).get("enemy_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            if enemy_unit is not None and not candidates:
                candidates = self._null_maiden_desperations_price_candidates(enemy_unit)
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            if source_unit is None or not self._ac_is_anathema_psykana_unit(source_unit):
                logger.error("ERROR: DESPERATION'S PRICE: target must be an Anathema Psykana unit")
                return False
            if enemy_unit is None or not self._ac_is_enemy_battlefield_unit(enemy_unit) or not self._ac_has_keyword(enemy_unit, "PSYKER"):
                logger.error("ERROR: DESPERATION'S PRICE: missing enemy PSYKER unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: DESPERATION'S PRICE: target is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                return False
            game_map = getattr(getattr(self, "game", None), "map", None)
            if game_map is None:
                return False
            try:
                distance = float(game_map.get_distance_between_units(source_unit, enemy_unit))
            except (TypeError, ValueError):
                distance = 999.0
            if distance > 18.0:
                logger.error("ERROR: DESPERATION'S PRICE: target must be within 18\" of the enemy PSYKER")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            leadership_check = getattr(enemy_unit, "pass_leadership_check", None)
            if not callable(leadership_check):
                logger.error("ERROR: DESPERATION'S PRICE: enemy unit cannot take a Leadership test")
                return False
            passed = bool(leadership_check())
            if not passed:
                apply_mortal_wounds = getattr(source_unit, "_apply_mortal_wounds_to_unit", None)
                if callable(apply_mortal_wounds):
                    apply_mortal_wounds(enemy_unit, 3, game_map=game_map)
            if not self._ac_is_battle_shocked(enemy_unit):
                apply_status = getattr(enemy_unit, "apply_status_effect", None)
                if callable(apply_status):
                    apply_status(BattleShockEffect(self._ac_current_turn()))
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "EARNING OF A NAME":
            roots = self._ac_unique_units(
                list(kwargs.get("target_units") or []) + [kwargs.get("unit") or kwargs.get("target_unit")]
            )
            if not roots or len(roots) > 2:
                logger.error("ERROR: EARNING OF A NAME: expected one or two target units")
                return False
            for root in roots:
                if not self._ac_is_character_unit(root) or not self._ac_unit_on_battlefield(root):
                    logger.error("ERROR: EARNING OF A NAME: target must be an ADEPTUS CUSTODES CHARACTER unit on the battlefield")
                    return False
                if self._unit_cannot_be_target_of_stratagem(root):
                    logger.error("ERROR: EARNING OF A NAME: invalid target unit")
                    return False
                if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                    logger.error("ERROR: EARNING OF A NAME: target unit has already fought this phase")
                    return False
            primary = roots[0]
            if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=primary):
                return False
            for root in roots:
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["auric_earning_of_a_name_active"] = True
                sr["auric_earning_of_a_name_source"] = stratagem.name
                sr["auric_earning_of_a_name_turn"] = self._ac_current_turn()
                sr["auric_earning_of_a_name_owner"] = self._ac_turn_owner_id()
                sr["auric_earning_of_a_name_expires_phase"] = "FIGHT_PHASE"
                root.special_rules = sr
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "SHOULDER THE MANTLE":
            leader = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit"))
            bodyguard = self._ac_root(kwargs.get("bodyguard_unit") or kwargs.get("bodyguard"))
            if leader is None or bodyguard is None:
                logger.error("ERROR: SHOULDER THE MANTLE: missing leader or bodyguard unit")
                return False
            if not self._ac_is_character_unit(leader) or not self._ac_unit_on_battlefield(leader):
                logger.error("ERROR: SHOULDER THE MANTLE: leader must be an ADEPTUS CUSTODES CHARACTER unit on the battlefield")
                return False
            if not bool(getattr(leader, "is_leader", False)) or getattr(leader, "attached_to", None) is not None:
                logger.error("ERROR: SHOULDER THE MANTLE: target leader is already leading a unit")
                return False
            if not self._ac_unit_on_battlefield(bodyguard) or not self._ac_owned_by_player(bodyguard):
                logger.error("ERROR: SHOULDER THE MANTLE: bodyguard must be a friendly on-battlefield unit")
                return False
            if list(getattr(bodyguard, "attached_leaders", []) or []):
                logger.error("ERROR: SHOULDER THE MANTLE: bodyguard cannot already be an Attached unit")
                return False
            if bool(getattr(bodyguard, "is_battle_shocked", lambda: False)()):
                logger.error("ERROR: SHOULDER THE MANTLE: bodyguard cannot be Battle-shocked")
                return False
            if not leader.can_attach_to(bodyguard):
                logger.error("ERROR: SHOULDER THE MANTLE: selected leader cannot attach to that bodyguard")
                return False
            if not self._ac_units_within_shoulder_range(leader, bodyguard):
                logger.error("ERROR: SHOULDER THE MANTLE: bodyguard is not within 2\" horizontally and 5\" vertically")
                return False
            if not stratagem.can_use(self.player, self.game, unit=leader, target_unit=leader, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=leader):
                return False
            leader.attach_to_unit(bodyguard)
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "SLAYER OF CHAMPIONS":
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("unit"))
            enemy_unit = self._ac_root(kwargs.get("enemy_unit") or kwargs.get("selected_enemy_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            if source_unit is None or not self._ac_is_character_unit(source_unit):
                logger.error("ERROR: SLAYER OF CHAMPIONS: missing ADEPTUS CUSTODES CHARACTER source unit")
                return False
            if enemy_unit is None and len(candidates) == 1:
                enemy_unit = candidates[0]
            if enemy_unit is None or not self._ac_is_enemy_battlefield_unit(enemy_unit):
                logger.error("ERROR: SLAYER OF CHAMPIONS: missing enemy target unit")
                return False
            if candidates and enemy_unit not in candidates:
                logger.error("ERROR: SLAYER OF CHAMPIONS: selected enemy is not an eligible candidate")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            mgr = self._ac_detachment_mgr()
            if mgr is None or not bool(getattr(mgr, "set_slayer_of_champions_target", lambda _unit: False)(enemy_unit)):
                return False
            if bool(kwargs.get("destroyed_unit_was_character", (pending or {}).get("destroyed_unit_was_character", False))):
                gain_cp = getattr(self.player, "gain_command_points", None)
                if callable(gain_cp):
                    gain_cp(1, reason=stratagem.name, source="stratagem")
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "SUPERHUMAN RESERVES":
            model = kwargs.get("model") or (pending or {}).get("model")
            model_unit = getattr(model, "parent_unit", None) if model is not None else None
            source_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or model_unit or (pending or {}).get("unit"))
            ability_key = str(kwargs.get("ability_key") or (pending or {}).get("ability_key") or "").strip().lower()
            ability_name = str(kwargs.get("ability_name") or (pending or {}).get("ability_name") or "").strip()
            if model is None or source_unit is None or source_unit is not self._ac_warlord_unit():
                logger.error("ERROR: SUPERHUMAN RESERVES: target must be your WARLORD model")
                return False
            pair_key = self._ac_warlord_model_pair_key(model, ability_key)
            if not pair_key or pair_key in self._ac_superhuman_reserves_pairs():
                logger.error("ERROR: SUPERHUMAN RESERVES: that once-per-battle ability has already been extended")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            if not bool(model.grant_once_per_battle_extra_use(ability_key, uses=1)):
                return False
            self._ac_superhuman_reserves_pairs().add(pair_key)
            logger.info(
                "INFO: SUPERHUMAN RESERVES: %s gains one extra use of %s.",
                getattr(model, "name", "Model"),
                ability_name or ability_key or "ability",
            )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "THE EMPEROR'S AUSPICE":
            target_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("unit") or (pending or {}).get("target_unit"))
            if target_unit is None or not self._ac_is_character_unit(target_unit):
                logger.error("ERROR: THE EMPEROR'S AUSPICE: target must be an ADEPTUS CUSTODES CHARACTER unit")
                return False
            if not stratagem.can_use(self.player, self.game, unit=target_unit, target_unit=target_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=target_unit):
                return False
            phase_key = self._ac_phase_key(phase_name)
            for model in self._ac_alive_models(target_unit):
                if not self._ac_model_has_keyword(model, "CHARACTER"):
                    continue
                model.set_temporary_fnp(
                    key=f"auric_the_emperors_auspice_{get_entity_id(model)}",
                    value=4,
                    source=stratagem.name,
                    expires_phase=phase_key,
                )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "VIGIL UNENDING":
            target_unit = self._ac_root(kwargs.get("unit") or kwargs.get("target_unit") or (pending or {}).get("unit"))
            model = kwargs.get("model") or (pending or {}).get("model")
            model_id = str(get_entity_id(model) or "").strip() if model is not None else ""
            if target_unit is None or model is None or not model_id:
                logger.error("ERROR: VIGIL UNENDING: missing destroyed character model context")
                return False
            if not self._ac_is_character_unit(target_unit) or not self._ac_model_has_keyword(model, "CHARACTER"):
                logger.error("ERROR: VIGIL UNENDING: target must be a destroyed ADEPTUS CUSTODES CHARACTER model")
                return False
            if bool(getattr(getattr(target_unit, "round_state", None), "fought_this_phase", False)):
                logger.error("ERROR: VIGIL UNENDING: target unit has already fought this phase")
                return False
            if not stratagem.can_use(self.player, self.game, unit=target_unit, target_unit=target_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=target_unit):
                return False
            sr = getattr(target_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            model_ids = {str(v).strip() for v in list(sr.get("auric_vigil_unending_model_ids", []) or []) if str(v).strip()}
            model_ids.add(model_id)
            sr["auric_vigil_unending_active"] = True
            sr["auric_vigil_unending_model_ids"] = sorted(model_ids)
            sr["auric_vigil_unending_turn"] = self._ac_current_turn()
            sr["auric_vigil_unending_owner"] = self._ac_turn_owner_id()
            sr["auric_vigil_unending_expires_phase"] = "FIGHT_PHASE"
            sr["auric_vigil_unending_source"] = stratagem.name
            target_unit.special_rules = sr
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "MANOEUVRE AND FIRE":
            target_unit = self._ac_root(
                kwargs.get("unit")
                or kwargs.get("target_unit")
                or (pending or {}).get("unit")
                or (pending or {}).get("target_unit")
            )
            action = str(kwargs.get("action") or (pending or {}).get("action") or "").strip().lower()
            if target_unit is None or not self._ac_is_custodes_unit(target_unit):
                logger.error("ERROR: MANOEUVRE AND FIRE: target must be a friendly ADEPTUS CUSTODES unit")
                return False
            if self._ac_phase_key(phase_name) != "MOVEMENT_PHASE":
                logger.error("ERROR: MANOEUVRE AND FIRE: wrong phase")
                return False
            game = getattr(self, "game", None)
            active_player = game.get_current_player() if game is not None and hasattr(game, "get_current_player") else None
            if active_player is not self.player:
                logger.error("ERROR: MANOEUVRE AND FIRE: not your turn")
                return False
            if action and action != "fall_back":
                logger.error("ERROR: MANOEUVRE AND FIRE: invalid trigger")
                return False
            if self._unit_cannot_be_target_of_stratagem(target_unit):
                logger.error("ERROR: MANOEUVRE AND FIRE: target cannot be selected")
                return False
            if not bool(getattr(getattr(target_unit, "round_state", None), "fell_back_this_round", False)):
                logger.error("ERROR: MANOEUVRE AND FIRE: target has not fallen back this phase")
                return False
            if not stratagem.can_use(
                self.player,
                self.game,
                unit=target_unit,
                target_unit=target_unit,
                phase_name=phase_name,
                action="fall_back",
            ):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=target_unit):
                return False
            sr = getattr(target_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["manoeuvre_and_fire_active"] = True
            sr["manoeuvre_and_fire_turn_owner"] = str(getattr(self.player, "id", "") or "")
            sr["manoeuvre_and_fire_turn"] = self._ac_current_turn()
            sr["manoeuvre_and_fire_source"] = stratagem.name
            target_unit.special_rules = sr
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            logger.info(
                "INFO: MANOEUVRE AND FIRE: %s can shoot and declare a charge after falling back this turn.",
                getattr(target_unit, "name", "Unit"),
            )
            return True

        if name_u == "PEERLESS WARRIOR":
            target_unit = self._ac_root(
                kwargs.get("unit")
                or kwargs.get("target_unit")
                or (pending or {}).get("unit")
                or (pending or {}).get("target_unit")
            )
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            selecting_player = kwargs.get("selecting_player") or (pending or {}).get("selecting_player")
            if target_unit is None or not self._ac_is_custodes_unit(target_unit):
                logger.error("ERROR: PEERLESS WARRIOR: target must be a friendly ADEPTUS CUSTODES unit")
                return False
            if self._ac_phase_key(phase_name) != "FIGHT_PHASE":
                logger.error("ERROR: PEERLESS WARRIOR: wrong phase")
                return False
            if selecting_player is not None and selecting_player is not self.player:
                logger.error("ERROR: PEERLESS WARRIOR: selected unit is not being activated by this player")
                return False
            if candidates and target_unit not in candidates:
                logger.error("ERROR: PEERLESS WARRIOR: selected unit is not an eligible candidate")
                return False
            if self._unit_cannot_be_target_of_stratagem(target_unit):
                logger.error("ERROR: PEERLESS WARRIOR: target cannot be selected")
                return False
            if bool(getattr(getattr(target_unit, "round_state", None), "fought_this_phase", False)):
                logger.error("ERROR: PEERLESS WARRIOR: target unit has already fought this phase")
                return False
            if not stratagem.can_use(self.player, self.game, unit=target_unit, target_unit=target_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=target_unit):
                return False
            self._ac_grant_melee_precision_to_unit(
                target_unit,
                key_prefix="lions_peerless_warrior",
                source=stratagem.name,
            )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            logger.info(
                "INFO: PEERLESS WARRIOR: %s gains [PRECISION] on melee weapons this phase.",
                getattr(target_unit, "name", "Unit"),
            )
            return True

        if name_u == "SWIFT AS THE EAGLE":
            target_unit = self._ac_root(
                kwargs.get("unit")
                or kwargs.get("target_unit")
                or (pending or {}).get("unit")
                or (pending or {}).get("target_unit")
            )
            enemy_unit = self._ac_root(kwargs.get("enemy_unit") or kwargs.get("attacker_unit") or (pending or {}).get("enemy_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            if target_unit is None or not self._ac_is_custodes_unit(target_unit):
                logger.error("ERROR: SWIFT AS THE EAGLE: target must be a friendly ADEPTUS CUSTODES unit")
                return False
            if self._ac_has_keyword(target_unit, "VEHICLE"):
                logger.error("ERROR: SWIFT AS THE EAGLE: VEHICLE units cannot be targeted")
                return False
            if self._ac_phase_key(phase_name) != "SHOOTING_PHASE":
                logger.error("ERROR: SWIFT AS THE EAGLE: wrong phase")
                return False
            game = getattr(self, "game", None)
            active_player = game.get_current_player() if game is not None and hasattr(game, "get_current_player") else None
            if active_player is self.player:
                logger.error("ERROR: SWIFT AS THE EAGLE: not opponent's Shooting phase")
                return False
            if candidates and target_unit not in candidates:
                logger.error("ERROR: SWIFT AS THE EAGLE: selected unit is not an eligible candidate")
                return False
            if not self._ac_unit_on_battlefield(target_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(target_unit):
                logger.error("ERROR: SWIFT AS THE EAGLE: target cannot be selected")
                return False
            if enemy_unit is not None and self._ac_owned_by_player(enemy_unit):
                logger.error("ERROR: SWIFT AS THE EAGLE: attacker is not enemy")
                return False
            if getattr(game, "map", None) is None:
                logger.error("ERROR: SWIFT AS THE EAGLE: no map context")
                return False
            if not self._ac_spend_cp(stratagem, target_unit=target_unit):
                return False
            move_max = int(dice_module.get_roll("D6") or 0)
            request = (
                game._queue_reactive_move_movement_decision(
                    player=self.player,
                    unit=target_unit,
                    max_distance=int(move_max),
                    kind="swift_as_the_eagle",
                    movement_type="reactive",
                    source=stratagem.name,
                    attacker_unit=enemy_unit,
                )
                if game is not None
                else None
            )
            event_system = getattr(game, "event_system", None)
            if request is not None and event_system is not None:
                event_system.publish(
                    "swift_as_the_eagle_move",
                    player=self.player,
                    unit=target_unit,
                    max_distance=int(move_max),
                    decision_request=request,
                )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            logger.info(
                "INFO: SWIFT AS THE EAGLE: %s can make a Normal move of up to %s\".",
                getattr(target_unit, "name", "Unit"),
                int(move_max),
            )
            return True

        if name_u == "EMPEROR'S EXECUTIONERS":
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._talons_battlefield_unit_candidates(
                require_melee=True,
            )
            selected_units = self._ac_resolve_unit_selection(
                kwargs.get("units"),
                kwargs.get("target_units"),
                kwargs.get("selected_units"),
                kwargs.get("unit"),
                kwargs.get("target_unit"),
            )
            if not selected_units and len(candidates) == 1:
                selected_units = [candidates[0]]
            if self._ac_phase_name_lower(phase_name) != "fight phase":
                logger.error("ERROR: EMPEROR'S EXECUTIONERS: wrong phase")
                return False
            if not selected_units or len(selected_units) > 2:
                logger.error("ERROR: EMPEROR'S EXECUTIONERS: expected one or two target units")
                return False
            for root in selected_units:
                if root is None or not self._ac_is_custodes_unit(root):
                    logger.error("ERROR: EMPEROR'S EXECUTIONERS: targets must be friendly ADEPTUS CUSTODES units")
                    return False
                if candidates and root not in candidates:
                    logger.error("ERROR: EMPEROR'S EXECUTIONERS: selected unit is not an eligible candidate")
                    return False
                if not self._ac_unit_on_battlefield(root):
                    return False
                if self._unit_cannot_be_target_of_stratagem(root):
                    logger.error("ERROR: EMPEROR'S EXECUTIONERS: target cannot be selected")
                    return False
                if not self._ac_unit_has_weapon_type(root, "melee"):
                    logger.error("ERROR: EMPEROR'S EXECUTIONERS: target must have melee weapons")
                    return False
            primary = selected_units[0]
            if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=primary):
                return False
            for root in selected_units:
                sr = dict(getattr(root, "special_rules", {}) or {})
                sr["custodes_talons_emperors_executioners_active"] = True
                sr["custodes_talons_emperors_executioners_wound_bonus"] = 1
                sr["custodes_talons_emperors_executioners_expires_phase"] = "FIGHT_PHASE"
                sr["custodes_talons_emperors_executioners_turn_owner"] = self._ac_turn_owner_id()
                sr["custodes_talons_emperors_executioners_turn"] = self._ac_current_turn()
                sr["custodes_talons_emperors_executioners_source"] = stratagem.name
                root.special_rules = sr
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "EMPYRIC SEVERANCE":
            attacking_unit = self._ac_root(kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or (pending or {}).get("attacking_unit"))
            phase_key = self._ac_phase_key(phase_name)
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            if not candidates:
                candidates = self._talons_targeted_custodes_candidates(list(kwargs.get("target_units") or []))
            source_unit = self._ac_root(
                kwargs.get("unit")
                or kwargs.get("target_unit")
                or (pending or {}).get("unit")
                or (pending or {}).get("target_unit")
            )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            support_candidates_by_unit_id = dict(kwargs.get("support_candidates_by_unit_id") or (pending or {}).get("support_candidates_by_unit_id") or {})
            support_unit = self._ac_root(kwargs.get("support_unit") or (pending or {}).get("support_unit"))
            if source_unit is not None and support_unit is None:
                support_ids = list(support_candidates_by_unit_id.get(self._ac_sort_key(source_unit), []) or [])
                if len(support_ids) == 1 and self.game is not None and hasattr(self.game, "_resolve_unit_by_id"):
                    support_unit = self._ac_root(self.game._resolve_unit_by_id(support_ids[0]))
            if support_unit is None and source_unit is not None:
                support_candidates = self._talons_support_candidates_for_empyric(source_unit)
                if len(support_candidates) == 1:
                    support_unit = support_candidates[0]
            if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                logger.error("ERROR: EMPYRIC SEVERANCE: wrong phase")
                return False
            if phase_key == "SHOOTING_PHASE":
                active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
                if active_player is self.player:
                    logger.error("ERROR: EMPYRIC SEVERANCE: must be your opponent's Shooting phase")
                    return False
            if source_unit is None or not self._ac_is_custodes_unit(source_unit):
                logger.error("ERROR: EMPYRIC SEVERANCE: target must be a friendly ADEPTUS CUSTODES unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: EMPYRIC SEVERANCE: target is not an eligible candidate")
                return False
            if attacking_unit is None or self._ac_owned_by_player(attacking_unit):
                logger.error("ERROR: EMPYRIC SEVERANCE: missing enemy attacking unit")
                return False
            if support_unit is None or not self._ac_is_anathema_psykana_unit(support_unit):
                logger.error("ERROR: EMPYRIC SEVERANCE: support unit must be a friendly ANATHEMA PSYKANA unit")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if not self._ac_unit_on_battlefield(support_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                logger.error("ERROR: EMPYRIC SEVERANCE: target cannot be selected")
                return False
            if self._unit_cannot_be_target_of_stratagem(support_unit):
                logger.error("ERROR: EMPYRIC SEVERANCE: support unit cannot be selected")
                return False
            if not aura_utils.unit_within_range_of_unit(
                source_unit,
                support_unit,
                6.0,
                use_attached_aggregate=True,
            ):
                logger.error("ERROR: EMPYRIC SEVERANCE: support unit must be within 6\"")
                return False
            support_ids = list(support_candidates_by_unit_id.get(self._ac_sort_key(source_unit), []) or [])
            if support_ids and self._ac_sort_key(support_unit) not in support_ids:
                logger.error("ERROR: EMPYRIC SEVERANCE: support unit is not an eligible candidate")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            self._append_defensive_effect(
                source_unit,
                "defensive_fnp_overrides",
                {
                    "value": 4,
                    "attack_type": "any",
                    "expires_phase": phase_key,
                    "condition": "against psychic attacks and mortal wounds",
                    "source": str(getattr(stratagem, "name", "") or "EMPYRIC SEVERANCE"),
                },
            )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "HUNT AS ONE":
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._talons_battlefield_unit_candidates()
            selected_units = self._ac_resolve_unit_selection(
                kwargs.get("units"),
                kwargs.get("target_units"),
                kwargs.get("selected_units"),
                kwargs.get("unit"),
                kwargs.get("target_unit"),
            )
            if not selected_units and len(candidates) == 1:
                selected_units = [candidates[0]]
            if self._ac_phase_name_lower(phase_name) != "movement phase":
                logger.error("ERROR: HUNT AS ONE: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: HUNT AS ONE: must be your Movement phase")
                return False
            if not selected_units or len(selected_units) > 2:
                logger.error("ERROR: HUNT AS ONE: expected one or two target units")
                return False
            for root in selected_units:
                if root is None or not self._ac_is_custodes_unit(root):
                    logger.error("ERROR: HUNT AS ONE: targets must be friendly ADEPTUS CUSTODES units")
                    return False
                if candidates and root not in candidates:
                    logger.error("ERROR: HUNT AS ONE: selected unit is not an eligible candidate")
                    return False
                if not self._ac_unit_on_battlefield(root):
                    return False
                if self._unit_cannot_be_target_of_stratagem(root):
                    logger.error("ERROR: HUNT AS ONE: target cannot be selected")
                    return False
            primary = selected_units[0]
            if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=primary):
                return False
            for root in selected_units:
                sr = dict(getattr(root, "special_rules", {}) or {})
                sr["manoeuvre_and_fire_active"] = True
                sr["manoeuvre_and_fire_turn_owner"] = str(getattr(self.player, "id", "") or "")
                sr["manoeuvre_and_fire_turn"] = self._ac_current_turn()
                sr["manoeuvre_and_fire_source"] = stratagem.name
                root.special_rules = sr
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "SHIELD OF HONOUR":
            attacking_unit = self._ac_root(kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or (pending or {}).get("attacking_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            if not candidates:
                candidates = self._talons_targeted_custodes_candidates(
                    list(kwargs.get("target_units") or []),
                    require_anathema=True,
                    require_infantry=True,
                )
            source_unit = self._ac_root(
                kwargs.get("unit")
                or kwargs.get("target_unit")
                or (pending or {}).get("unit")
                or (pending or {}).get("target_unit")
            )
            if source_unit is None and len(candidates) == 1:
                source_unit = candidates[0]
            support_candidates_by_unit_id = dict(kwargs.get("support_candidates_by_unit_id") or (pending or {}).get("support_candidates_by_unit_id") or {})
            support_unit = self._ac_root(kwargs.get("support_unit") or (pending or {}).get("support_unit"))
            if source_unit is not None and support_unit is None:
                support_ids = list(support_candidates_by_unit_id.get(self._ac_sort_key(source_unit), []) or [])
                if len(support_ids) == 1 and self.game is not None and hasattr(self.game, "_resolve_unit_by_id"):
                    support_unit = self._ac_root(self.game._resolve_unit_by_id(support_ids[0]))
            if support_unit is None and source_unit is not None:
                support_candidates = self._talons_support_candidates_for_shield(source_unit)
                if len(support_candidates) == 1:
                    support_unit = support_candidates[0]
            if self._ac_phase_key(phase_name) != "SHOOTING_PHASE":
                logger.error("ERROR: SHIELD OF HONOUR: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is self.player:
                logger.error("ERROR: SHIELD OF HONOUR: must be your opponent's Shooting phase")
                return False
            if source_unit is None or not self._ac_is_anathema_psykana_unit(source_unit) or not self._ac_has_keyword(source_unit, "INFANTRY"):
                logger.error("ERROR: SHIELD OF HONOUR: target must be a friendly ANATHEMA PSYKANA INFANTRY unit")
                return False
            if candidates and source_unit not in candidates:
                logger.error("ERROR: SHIELD OF HONOUR: target is not an eligible candidate")
                return False
            if attacking_unit is None or self._ac_owned_by_player(attacking_unit):
                logger.error("ERROR: SHIELD OF HONOUR: missing enemy attacking unit")
                return False
            if support_unit is None or not self._ac_is_custodes_unit(support_unit):
                logger.error("ERROR: SHIELD OF HONOUR: support unit must be a friendly ADEPTUS CUSTODES unit")
                return False
            if self._ac_is_anathema_psykana_unit(support_unit) or not self._ac_has_keyword(support_unit, "INFANTRY"):
                logger.error("ERROR: SHIELD OF HONOUR: support unit must be a non-Anathema ADEPTUS CUSTODES INFANTRY unit")
                return False
            if support_unit is source_unit:
                logger.error("ERROR: SHIELD OF HONOUR: support unit must be different from the target unit")
                return False
            if not self._ac_unit_on_battlefield(source_unit):
                return False
            if not self._ac_unit_on_battlefield(support_unit):
                return False
            if self._unit_cannot_be_target_of_stratagem(source_unit):
                logger.error("ERROR: SHIELD OF HONOUR: target cannot be selected")
                return False
            if self._unit_cannot_be_target_of_stratagem(support_unit):
                logger.error("ERROR: SHIELD OF HONOUR: support unit cannot be selected")
                return False
            if not aura_utils.unit_within_range_of_unit(
                source_unit,
                support_unit,
                6.0,
                use_attached_aggregate=True,
            ):
                logger.error("ERROR: SHIELD OF HONOUR: support unit must be within 6\"")
                return False
            support_ids = list(support_candidates_by_unit_id.get(self._ac_sort_key(source_unit), []) or [])
            if support_ids and self._ac_sort_key(support_unit) not in support_ids:
                logger.error("ERROR: SHIELD OF HONOUR: support unit is not an eligible candidate")
                return False
            if not stratagem.can_use(self.player, self.game, unit=source_unit, target_unit=source_unit, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=source_unit):
                return False
            sr = dict(getattr(source_unit, "special_rules", {}) or {})
            sr["custodes_talons_shield_of_honour_active"] = True
            sr["custodes_talons_shield_of_honour_support_unit_id"] = self._ac_sort_key(support_unit)
            sr["custodes_talons_shield_of_honour_expires_phase"] = "SHOOTING_PHASE"
            sr["custodes_talons_shield_of_honour_turn_owner"] = self._ac_turn_owner_id()
            sr["custodes_talons_shield_of_honour_turn"] = self._ac_current_turn()
            sr["custodes_talons_shield_of_honour_source"] = stratagem.name
            source_unit.special_rules = sr
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "TALONED PINCER":
            enemy_unit = self._ac_root(kwargs.get("enemy_unit") or kwargs.get("attacker_unit") or (pending or {}).get("enemy_unit"))
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or (pending or {}).get("candidates") or []))
            if not candidates and enemy_unit is not None:
                candidates = [
                    root
                    for root in self._talons_battlefield_unit_candidates()
                    if aura_utils.unit_within_range_of_unit(root, enemy_unit, 9.0, use_attached_aggregate=True)
                ]
            selected_units = self._ac_resolve_unit_selection(
                kwargs.get("units"),
                kwargs.get("target_units"),
                kwargs.get("selected_units"),
                kwargs.get("unit"),
                kwargs.get("target_unit"),
            )
            if not selected_units and len(candidates) == 1:
                selected_units = [candidates[0]]
            if self._ac_phase_name_lower(phase_name) != "movement phase":
                logger.error("ERROR: TALONED PINCER: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is self.player:
                logger.error("ERROR: TALONED PINCER: must be your opponent's Movement phase")
                return False
            if enemy_unit is None or not self._ac_is_enemy_battlefield_unit(enemy_unit):
                logger.error("ERROR: TALONED PINCER: missing enemy unit")
                return False
            if not selected_units or len(selected_units) > 2:
                logger.error("ERROR: TALONED PINCER: expected one or two target units")
                return False
            for root in selected_units:
                if root is None or not self._ac_is_custodes_unit(root):
                    logger.error("ERROR: TALONED PINCER: targets must be friendly ADEPTUS CUSTODES units")
                    return False
                if candidates and root not in candidates:
                    logger.error("ERROR: TALONED PINCER: selected unit is not an eligible candidate")
                    return False
                if not self._ac_unit_on_battlefield(root):
                    return False
                if self._unit_cannot_be_target_of_stratagem(root):
                    logger.error("ERROR: TALONED PINCER: target cannot be selected")
                    return False
                if not aura_utils.unit_within_range_of_unit(
                    root,
                    enemy_unit,
                    9.0,
                    use_attached_aggregate=True,
                ):
                    logger.error("ERROR: TALONED PINCER: target must be within 9\" of the enemy unit")
                    return False
            primary = selected_units[0]
            if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=primary):
                return False
            queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
            if not callable(queue_move):
                logger.error("ERROR: TALONED PINCER: reactive movement queue is unavailable")
                return False
            for root in selected_units:
                queue_move(
                    player=self.player,
                    unit=root,
                    max_distance=6,
                    kind="taloned_pincer",
                    movement_type="reactive",
                    reactive_movement_type="move",
                    source=stratagem.name,
                    moving_unit=enemy_unit,
                    attacker_unit=enemy_unit,
                    range_value=9,
                    allow_skip=True,
                )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        if name_u == "TALONS INTERLOCKED":
            candidates = self._ac_unique_units(list(kwargs.get("candidates") or [])) or self._talons_battlefield_unit_candidates(
                require_infantry=True,
                require_not_shot=True,
                require_ranged=True,
            )
            selected_units = self._ac_resolve_unit_selection(
                kwargs.get("units"),
                kwargs.get("target_units"),
                kwargs.get("selected_units"),
                kwargs.get("unit"),
                kwargs.get("target_unit"),
            )
            if not selected_units and len(candidates) == 1:
                selected_units = [candidates[0]]
            enemy_candidates = self._ac_unique_units(list(kwargs.get("enemy_candidates") or []))
            enemy_unit = self._ac_root(kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit") or kwargs.get("enemy"))
            if enemy_unit is None and len(enemy_candidates) == 1:
                enemy_unit = enemy_candidates[0]
            if self._ac_phase_name_lower(phase_name) != "shooting phase":
                logger.error("ERROR: TALONS INTERLOCKED: wrong phase")
                return False
            active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
            if active_player is not self.player:
                logger.error("ERROR: TALONS INTERLOCKED: must be your Shooting phase")
                return False
            if not selected_units or len(selected_units) > 2:
                logger.error("ERROR: TALONS INTERLOCKED: expected one or two target units")
                return False
            for root in selected_units:
                if root is None or not self._ac_is_custodes_unit(root):
                    logger.error("ERROR: TALONS INTERLOCKED: targets must be friendly ADEPTUS CUSTODES units")
                    return False
                if candidates and root not in candidates:
                    logger.error("ERROR: TALONS INTERLOCKED: selected unit is not an eligible candidate")
                    return False
                if not self._ac_unit_on_battlefield(root):
                    return False
                if self._unit_cannot_be_target_of_stratagem(root):
                    logger.error("ERROR: TALONS INTERLOCKED: target cannot be selected")
                    return False
                if not self._ac_has_keyword(root, "INFANTRY"):
                    logger.error("ERROR: TALONS INTERLOCKED: target must be INFANTRY")
                    return False
                if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                    logger.error("ERROR: TALONS INTERLOCKED: target has already been selected to shoot")
                    return False
                if not self._ac_unit_has_weapon_type(root, "ranged"):
                    logger.error("ERROR: TALONS INTERLOCKED: target must have ranged weapons")
                    return False
            if enemy_unit is None or not self._ac_is_enemy_battlefield_unit(enemy_unit):
                logger.error("ERROR: TALONS INTERLOCKED: missing enemy target unit")
                return False
            if enemy_candidates and enemy_unit not in enemy_candidates:
                logger.error("ERROR: TALONS INTERLOCKED: selected enemy is not an eligible candidate")
                return False
            if not self._talons_enemy_target_eligible_for_all_units(selected_units, enemy_unit):
                logger.error("ERROR: TALONS INTERLOCKED: enemy target is not an eligible target for all selected units")
                return False
            primary = selected_units[0]
            if not stratagem.can_use(self.player, self.game, unit=primary, target_unit=primary, phase_name=phase_name):
                return False
            if not self._ac_spend_cp(stratagem, target_unit=primary):
                return False
            phase_key = self._ac_phase_key(phase_name)
            enemy_id = self._ac_sort_key(enemy_unit)
            for root in selected_units:
                sr = dict(getattr(root, "special_rules", {}) or {})
                sr["custodes_talons_talons_interlocked_active"] = True
                sr["custodes_talons_talons_interlocked_target_id"] = enemy_id
                sr["custodes_talons_talons_interlocked_expires_phase"] = "SHOOTING_PHASE"
                sr["custodes_talons_talons_interlocked_turn_owner"] = self._ac_turn_owner_id()
                sr["custodes_talons_talons_interlocked_turn"] = self._ac_current_turn()
                sr["custodes_talons_talons_interlocked_source"] = stratagem.name
                root.special_rules = sr
                root_id = self._ac_sort_key(root) or str(id(root))
                for model in self._ac_alive_models(root):
                    set_bonus = getattr(model, "set_temporary_weapon_bonus", None)
                    if not callable(set_bonus):
                        continue
                    model_id = self._ac_sort_key(model) or str(id(model))
                    for wargear in list(getattr(model, "wargear", []) or []):
                        if wargear is None:
                            continue
                        is_ranged = getattr(wargear, "is_ranged", None)
                        if not callable(is_ranged) or not bool(is_ranged()):
                            continue
                        weapon_name = str(getattr(wargear, "name", "") or "").strip()
                        if not weapon_name:
                            continue
                        set_bonus(
                            key=f"custodes_talons_talons_interlocked:{root_id}:{model_id}:{weapon_name}".lower(),
                            weapon_name=weapon_name,
                            strength_bonus=1,
                            ap_bonus=1,
                            source=stratagem.name,
                            expires_phase=phase_key,
                        )
            self._ac_finalize_use(stratagem, dequeue=dequeue)
            return True

        return None
