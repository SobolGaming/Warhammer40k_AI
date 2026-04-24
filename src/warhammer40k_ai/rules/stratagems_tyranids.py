from __future__ import annotations

from itertools import combinations
import logging
from typing import Any, Optional

from ..utility.aura_utils import unit_within_range_of_unit
from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class TyranidsStratagemMixin:
    @staticmethod
    def _tyr_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _tyr_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "")

    @staticmethod
    def _tyr_has_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and has_any(keyword):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and has_kw(keyword):
            return True
        return False

    @staticmethod
    def _tyr_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    def _tyr_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "tyranids_detachments", None)

    def _is_tyranids_invasion_fleet_detachment(self) -> bool:
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "is_invasion_fleet", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tyranids_assimilation_swarm_detachment(self) -> bool:
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "is_assimilation_swarm", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tyranids_unending_swarm_detachment(self) -> bool:
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "is_unending_swarm", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tyranids_vanguard_onslaught_detachment(self) -> bool:
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "is_vanguard_onslaught", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tyranids_synaptic_nexus_detachment(self) -> bool:
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "is_synaptic_nexus", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tyranids_crusher_stampede_detachment(self) -> bool:
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "is_crusher_stampede", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tyranids_subterranean_assault_detachment(self) -> bool:
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "is_subterranean_assault", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tyranids_warrior_bioform_onslaught_detachment(self) -> bool:
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "is_warrior_bioform_onslaught", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_tyranids_unit(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "_unit_is_tyranids", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if faction_id == "TYR":
            return True
        return self._tyr_has_keyword(root, "TYRANIDS")

    def _tyr_owned_by_player(self, unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(army, "player", None) is player

    @staticmethod
    def _tyr_remove_keyword_exact(entity: Any, keyword: str) -> None:
        if entity is None:
            return
        key = str(keyword or "").strip()
        if not key:
            return
        keywords = list(getattr(entity, "keywords", []) or [])
        filtered = [value for value in keywords if str(value or "").strip().lower() != key.lower()]
        entity.keywords = filtered

    @staticmethod
    def _tyr_model_is_alive(model: Any) -> bool:
        if model is None:
            return False
        is_alive = getattr(model, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(model, "is_alive", True))

    def _tyr_iter_unit_models(self, unit: Any) -> list[Any]:
        root = self._tyr_root(unit)
        if root is None:
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        return [model for model in list(models or []) if model is not None]

    def _tyr_damaged_models(self, unit: Any) -> list[Any]:
        out: list[Any] = []
        for model in self._tyr_iter_unit_models(unit):
            if not self._tyr_model_is_alive(model):
                continue
            base_wounds = self._tyr_model_wounds_characteristic(model)
            try:
                current_wounds = int(getattr(model, "wounds", 0) or 0)
            except (TypeError, ValueError):
                current_wounds = 0
            if base_wounds > 0 and current_wounds < base_wounds:
                out.append(model)
        return out

    def _tyr_unit_is_battle_shocked(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        is_battle_shocked = getattr(root, "is_battle_shocked", None)
        if callable(is_battle_shocked):
            return bool(is_battle_shocked())
        return bool(getattr(root, "battle_shocked", False))

    @staticmethod
    def _tyr_normalize_weapon_name(value: str) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _tyr_model_weapon_names(self, model: Any, *, attack_type: str) -> list[str]:
        if model is None:
            return []
        mode = str(attack_type or "").strip().lower()
        if mode not in {"melee", "ranged"}:
            return []
        names: list[str] = []
        seen: set[str] = set()
        for wargear in list(getattr(model, "wargear", []) or []):
            if wargear is None:
                continue
            is_match = getattr(wargear, f"is_{mode}", None)
            if not callable(is_match) or not bool(is_match()):
                continue
            weapon_name = str(getattr(wargear, "name", "") or "").strip()
            if not weapon_name:
                continue
            key = self._tyr_normalize_weapon_name(weapon_name)
            if not key or key in seen:
                continue
            seen.add(key)
            names.append(weapon_name)
        names.sort(key=self._tyr_normalize_weapon_name)
        return names

    def _tyr_is_monster_unit(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        return bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")

    def _tyr_is_burrower_unit(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "_unit_is_burrower", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._tyr_has_keyword(root, "BURROWER")

    @staticmethod
    def _tyr_model_wounds_characteristic(model: Any) -> int:
        if model is None:
            return 0
        try:
            return int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
        except (TypeError, ValueError):
            return 0

    def _tyr_unit_arrived_from_reserves_this_turn(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        return bool(getattr(root, "arrived_from_reserves_this_turn", False))

    def _tyr_current_tunnel_marker_ids(self, unit: Any) -> list[str]:
        root = self._tyr_root(unit)
        if root is None:
            return []
        mgr = self._tyr_detachment_mgr()
        getter = getattr(mgr, "subterranean_assault_tunnel_marker_ids_for_unit", None) if mgr is not None else None
        if not callable(getter):
            return []
        return [str(value or "").strip() for value in list(getter(root) or []) if str(value or "").strip()]

    def _tyr_is_infantry_unit(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        return self._tyr_has_keyword(root, "INFANTRY")

    def _tyr_is_vanguard_invader_unit(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        return self._tyr_has_keyword(root, "VANGUARD INVADER")

    def _tyr_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        if not self._tyr_is_alive(root):
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

    def _tyr_objective_candidates_you_control(self, unit: Any) -> list[Any]:
        root = self._tyr_root(unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if root is None or game_map is None:
            return []
        is_within = getattr(root, "is_within_objective_range", None)
        if not callable(is_within):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(objective, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            if not bool(is_within(loc)):
                continue
            controller = getattr(loc, "controlling_player", None)
            sticky_controller = getattr(loc, "sticky_controller", None)
            if controller is not self.player and sticky_controller is not self.player:
                continue
            objective_id = str(getattr(objective, "id", "") or get_entity_id(objective) or "")
            if objective_id and objective_id in seen:
                continue
            if objective_id:
                seen.add(objective_id)
            out.append(objective)
        out.sort(key=lambda objective: str(getattr(objective, "id", "") or get_entity_id(objective) or ""))
        return out

    def _tyr_unit_in_synapse_range(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        synapse_mgr = getattr(army, "synapse", None) if army is not None else None
        if synapse_mgr is None:
            return False
        return bool(synapse_mgr.unit_in_synapse_range(root, game=getattr(self, "game", None)))

    def _tyr_unit_in_engagement_range(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if root is None or game_map is None:
            return False
        for other in list(getattr(game_map, "units", []) or []):
            enemy_root = self._tyr_root(other)
            if enemy_root is None:
                continue
            if enemy_root is root:
                continue
            if not self._tyr_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if self._tyr_owned_by_player(enemy_root, self.player):
                continue
            if bool(game_map.is_within_engagement_range(root, enemy_root)):
                return True
        return False

    def _tyr_unit_in_candidates(self, root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = self._tyr_sort_key(root)
        for candidate in list(candidates or []):
            candidate_root = self._tyr_root(candidate)
            if candidate_root is None:
                continue
            if candidate_root is root:
                return True
            if rid and self._tyr_sort_key(candidate_root) == rid:
                return True
        return False

    @staticmethod
    def _tyr_phase_name(value: Any) -> str:
        return str(value or "").strip().lower().replace("_", " ")

    @staticmethod
    def _tyr_normalize_token(value: Any) -> str:
        text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
        return " ".join(text.split())

    def _tyr_is_own_command_phase(self, *, phase_name: str) -> bool:
        if phase_name != "command phase":
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if getattr(self, "game", None) is not None else None
        return active_player is self.player

    def _tyr_is_endless_multitude_unit(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        return self._tyr_has_keyword(root, "ENDLESS MULTITUDE")

    def _tyr_unit_has_destroyed_models(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        can_return = getattr(root, "_horrors_can_return_model", None)

        def _pool_has_returnable(pool: list[Any]) -> bool:
            for model in list(pool or []):
                if callable(can_return) and not bool(can_return(model)):
                    continue
                return True
            return False

        if _pool_has_returnable(list(getattr(root, "models_lost", []) or [])):
            return True
        members_fn = getattr(root, "get_attached_unit_members", None)
        if callable(members_fn):
            for member in list(members_fn() or []):
                if member is None or member is root:
                    continue
                if _pool_has_returnable(list(getattr(member, "models_lost", []) or [])):
                    return True
        return False

    @staticmethod
    def _tyr_selected_to_move_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )

    def _tyr_return_destroyed_models(self, unit: Any, *, amount: int) -> int:
        root = self._tyr_root(unit)
        if root is None:
            return 0
        qty = max(0, int(amount or 0))
        if qty <= 0:
            return 0
        return_full = getattr(self, "_return_destroyed_models_full", None)
        if callable(return_full):
            returned = return_full(
                root,
                amount=qty,
                game_map=getattr(getattr(self, "game", None), "map", None),
                skip_character=True,
            )
            return max(0, int(returned or 0))
        return 0

    def _tyr_return_destroyed_models_with_wounds_characteristic(
        self,
        unit: Any,
        *,
        amount: int,
        wounds_characteristic: int,
    ) -> int:
        root = self._tyr_root(unit)
        qty = max(0, int(amount or 0))
        target_wounds = max(0, int(wounds_characteristic or 0))
        if root is None or qty <= 0 or target_wounds <= 0:
            return 0
        members: list[Any] = [root]
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            for member in list(get_members() or []):
                if member is None or member is root:
                    continue
                members.append(member)
        returned = 0
        for member in list(members):
            destroyed = list(getattr(member, "models_lost", []) or [])
            eligible = [
                model
                for model in list(destroyed or [])
                if self._tyr_model_wounds_characteristic(model) == target_wounds
            ]
            for model in eligible[: max(0, qty - returned)]:
                if hasattr(member, "models_lost") and model in list(getattr(member, "models_lost", []) or []):
                    member.models_lost.remove(model)
                set_parent = getattr(model, "set_parent_unit", None)
                if callable(set_parent):
                    set_parent(member)
                else:
                    model.parent_unit = member
                model.wounds = int(target_wounds)
                check_profile = getattr(model, "_check_damaged_profile", None)
                if callable(check_profile):
                    check_profile()
                setattr(model, "_on_death_reactions_resolved", False)
                setattr(model, "_fight_on_death_used", False)
                setattr(model, "_shoot_on_death_used", False)
                existing = list(getattr(member, "models", []) or [])
                if not any(str(get_entity_id(existing_model) or "") == str(get_entity_id(model) or "") for existing_model in existing):
                    existing.append(model)
                    member.models = existing
                returned += 1
                if returned >= qty:
                    break
            update_coherency = getattr(member, "update_coherency", None)
            if callable(update_coherency):
                update_coherency()
            if returned >= qty:
                break
        return int(returned)

    def _tyr_hyper_adaptation_by_key(self) -> dict[str, Any]:
        mgr = self._tyr_detachment_mgr()
        get_available = getattr(mgr, "get_available_hyper_adaptations", None) if mgr is not None else None
        if not callable(get_available):
            return {}
        out: dict[str, Any] = {}
        for adaptation in list(get_available() or []):
            key = str(getattr(adaptation, "key", "") or "").strip().upper()
            if key:
                out[key] = adaptation
        return out

    def _tyr_resolve_predatory_imperative_adaptation(self, raw_choice: Any) -> str:
        options = self._tyr_hyper_adaptation_by_key()
        if not options:
            return ""
        mgr = self._tyr_detachment_mgr()
        restricted_key = str(getattr(mgr, "active_hyper_adaptation_key", "") or "").strip().upper() if mgr is not None else ""
        allowed_keys = sorted([key for key in options if key != restricted_key])
        if not allowed_keys:
            return ""

        choice = raw_choice
        if isinstance(choice, dict):
            choice = (
                choice.get("choice")
                or choice.get("mode")
                or choice.get("selection")
                or choice.get("adaptation")
                or choice.get("hyper_adaptation")
                or choice.get("key")
            )
        token = self._tyr_normalize_token(choice)
        if token:
            aliases = {
                "swarming instincts": "SWARMING_INSTINCTS",
                "swarming": "SWARMING_INSTINCTS",
                "hyper aggression": "HYPER_AGGRESSION",
                "hyperaggression": "HYPER_AGGRESSION",
                "hive predators": "HIVE_PREDATORS",
                "predators": "HIVE_PREDATORS",
            }
            alias_key = aliases.get(token, "")
            if alias_key and alias_key in allowed_keys:
                return alias_key
            for key in list(allowed_keys):
                adaptation = options.get(key)
                names = {
                    self._tyr_normalize_token(key),
                    self._tyr_normalize_token(getattr(adaptation, "key", "")),
                    self._tyr_normalize_token(getattr(adaptation, "name", "")),
                }
                if token in names:
                    return key
            return ""
        return allowed_keys[0]

    def _tyr_resolve_units(self, value: Any) -> list[Any]:
        raw = value
        if raw is None:
            return []
        if not isinstance(raw, (list, tuple, set)):
            raw = [raw]
        out: list[Any] = []
        seen: set[str] = set()
        for entry in list(raw or []):
            if isinstance(entry, str):
                resolver = getattr(self, "_resolve_unit_by_id", None)
                if callable(resolver):
                    entry = resolver(entry)
            root = self._tyr_root(entry)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_fight_eligible_candidates(self) -> list[Any]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return []
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            is_eligible = getattr(root, "is_eligible_to_fight", None)
            if not callable(is_eligible) or not bool(is_eligible(game_map)):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_command_phase_candidates(self, *, endless_multitude_only: bool = False) -> list[Any]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if endless_multitude_only and not self._tyr_is_endless_multitude_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_adrenal_surge_candidates(self) -> list[Any]:
        return self._tyr_fight_eligible_candidates()

    def _tyr_predatory_imperative_candidates(self) -> list[Any]:
        return self._tyr_command_phase_candidates(endless_multitude_only=False)

    def _tyr_endless_swarm_candidates(self) -> list[Any]:
        out: list[Any] = []
        for root in self._tyr_command_phase_candidates(endless_multitude_only=True):
            if not self._tyr_unit_has_destroyed_models(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_invasion_fleet_tool_action_context(
        self,
        stratagem_name: str,
        *,
        phase_name: str = "",
    ) -> dict[str, Any]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return {}
        phase_key = self._tyr_phase_name(phase_name)
        name_u = str(stratagem_name or "").strip().upper()
        if name_u == "ADRENAL SURGE":
            if phase_key != "fight phase":
                return {}
            return {
                "candidates": self._tyr_adrenal_surge_candidates(),
                "max_units": 2,
            }
        if phase_key != "command phase":
            return {}
        if name_u == "PREDATORY IMPERATIVE":
            return {
                "candidates": self._tyr_predatory_imperative_candidates(),
                "max_units": 2,
            }
        if name_u == "ENDLESS SWARM":
            return {
                "candidates": self._tyr_endless_swarm_candidates(),
                "max_units": 2,
            }
        return {}

    def _tyr_can_use_invasion_fleet_tool_action(self, stratagem_name: str, kwargs: dict[str, Any]) -> Optional[bool]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return None
        name_u = str(stratagem_name or "").strip().upper()
        if name_u not in {"ADRENAL SURGE", "PREDATORY IMPERATIVE", "ENDLESS SWARM"}:
            return None
        phase_name = self._tyr_phase_name((kwargs or {}).get("phase_name") or getattr(self, "_current_phase_name", ""))
        if name_u == "ADRENAL SURGE":
            if phase_name != "fight phase":
                return False
            eligible = self._tyr_adrenal_surge_candidates()
        else:
            if phase_name != "command phase" or not self._tyr_is_own_command_phase(phase_name=phase_name):
                return False
            eligible = (
                self._tyr_predatory_imperative_candidates()
                if name_u == "PREDATORY IMPERATIVE"
                else self._tyr_endless_swarm_candidates()
            )
        if not eligible:
            return False
        selected = (kwargs or {}).get("units") or (kwargs or {}).get("selected_units")
        if selected is None:
            selected = (kwargs or {}).get("target_units")
        if selected is None:
            selected = (kwargs or {}).get("unit") or (kwargs or {}).get("target_unit")
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots or len(selected_roots) > 2:
            return False
        if any(not self._tyr_unit_in_candidates(root, eligible) for root in selected_roots):
            return False
        if len(selected_roots) == 2 and not all(self._tyr_unit_in_synapse_range(root) for root in selected_roots):
            return False
        return True

    def _tyr_unending_swarm_bounding_advance_candidates(self) -> list[Any]:
        if not self._is_tyranids_unending_swarm_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_is_endless_multitude_unit(root):
                continue
            if self._tyr_selected_to_move_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_unending_swarm_targeted_endless_multitude_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_tyranids_unending_swarm_detachment():
            return []
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is not None and self._tyr_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_is_endless_multitude_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_unending_swarm_swarming_masses_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_tyranids_unending_swarm_detachment():
            return []
        phase_key = self._tyr_phase_name(phase_name)
        if phase_key not in {"shooting phase", "fight phase"}:
            return []
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_is_endless_multitude_unit(root):
                continue
            if self._tyr_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name=phase_key):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_unending_swarm_synaptic_goading_candidates(self) -> list[Any]:
        if not self._is_tyranids_unending_swarm_detachment():
            return []
        game = getattr(self, "game", None)
        queue = getattr(game, "decision_queue", None) if game is not None else None
        if queue is None or not callable(getattr(queue, "list", None)):
            return []
        registry = getattr(game, "entity_registry", None) if game is not None else None
        out: list[Any] = []
        seen: set[str] = set()
        for request in list(queue.list() or []):
            ctx = dict(getattr(request, "context", {}) or {})
            if str(ctx.get("reactive_move_kind", "") or "").strip() != "horde_move":
                continue
            unit_id = str(ctx.get("reactive_move_unit_id", "") or "").strip()
            if not unit_id or unit_id in seen or registry is None:
                continue
            root = registry.get(unit_id, kind="unit")
            if root is None:
                continue
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_is_endless_multitude_unit(root):
                continue
            has_insurmountable_odds = getattr(root, "has_insurmountable_odds", None)
            if callable(has_insurmountable_odds) and not bool(has_insurmountable_odds()):
                continue
            if not self._tyr_unit_in_synapse_range(root):
                continue
            seen.add(unit_id)
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_unending_waves_candidates(self, *, destroyed_unit: Any = None) -> list[Any]:
        if not self._is_tyranids_unending_swarm_detachment():
            return []
        destroyed_root = self._tyr_root(destroyed_unit)
        if destroyed_root is None:
            return []
        if not self._tyr_owned_by_player(destroyed_root, self.player):
            return []
        if not self._is_tyranids_unit(destroyed_root):
            return []
        if not self._tyr_is_endless_multitude_unit(destroyed_root):
            return []
        if self._tyr_is_alive(destroyed_root):
            return []
        return [destroyed_root]

    def _tyr_ablative_carapace_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_tyranids_assimilation_swarm_detachment():
            return []
        if attacking_unit is not None:
            attacker_root = self._tyr_root(attacking_unit)
            if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
                return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_has_keyword(root, "HARVESTER"):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_rapacious_hunger_candidates(
        self,
        *,
        destroyed_unit: Any = None,
        destroyed_by_unit: Any = None,
    ) -> list[Any]:
        if not self._is_tyranids_assimilation_swarm_detachment():
            return []
        if destroyed_unit is None or destroyed_by_unit is None:
            return []
        attacker_root = self._tyr_root(destroyed_by_unit)
        destroyed_root = self._tyr_root(destroyed_unit)
        if attacker_root is None or destroyed_root is None:
            return []
        if not self._tyr_owned_by_player(attacker_root, self.player):
            return []
        if self._tyr_owned_by_player(destroyed_root, self.player):
            return []
        if not self._tyr_on_battlefield(attacker_root, require_targetable=True):
            return []
        if not self._is_tyranids_unit(attacker_root):
            return []
        mgr = self._tyr_detachment_mgr()
        options_fn = getattr(mgr, "assimilation_regeneration_options_for_unit", None) if mgr is not None else None
        if not callable(options_fn):
            return []
        options = list(options_fn(attacker_root, game=getattr(self, "game", None), player=self.player) or [])
        if not options:
            return []
        return [attacker_root]

    def _tyr_broodguard_impulse_candidates(
        self,
        *,
        destroyed_unit: Any = None,
        destroyed_by_unit: Any = None,
    ) -> list[Any]:
        if not self._is_tyranids_assimilation_swarm_detachment():
            return []
        destroyed_root = self._tyr_root(destroyed_unit)
        attacker_root = self._tyr_root(destroyed_by_unit)
        if destroyed_root is None or attacker_root is None:
            return []
        if not self._tyr_owned_by_player(destroyed_root, self.player):
            return []
        if not self._is_tyranids_unit(destroyed_root):
            return []
        if not self._tyr_has_keyword(destroyed_root, "HARVESTER"):
            return []
        if self._tyr_owned_by_player(attacker_root, self.player):
            return []
        return [destroyed_root]

    def _tyr_reclaim_biomass_candidates(self, *, destroyed_unit: Any = None) -> list[Any]:
        if not self._is_tyranids_assimilation_swarm_detachment():
            return []
        destroyed_root = self._tyr_root(destroyed_unit)
        if destroyed_root is None:
            return []
        if not self._tyr_owned_by_player(destroyed_root, self.player):
            return []
        if not self._is_tyranids_unit(destroyed_root):
            return []
        mgr = self._tyr_detachment_mgr()
        options_fn = getattr(mgr, "assimilation_regeneration_options_for_harvester", None) if mgr is not None else None
        if not callable(options_fn):
            return []
        destroyed_id = self._tyr_sort_key(destroyed_root)
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if root is destroyed_root:
                continue
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_has_keyword(root, "HARVESTER"):
                continue
            options = list(
                options_fn(
                    root,
                    game=getattr(self, "game", None),
                    player=self.player,
                    exclude_target_ids=(destroyed_id,),
                )
                or []
            )
            if not options:
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_secure_biomass_candidates(self) -> list[Any]:
        if not self._is_tyranids_assimilation_swarm_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_tyrannoformed_candidates(self) -> tuple[list[Any], dict[str, list[Any]]]:
        if not self._is_tyranids_assimilation_swarm_detachment():
            return [], {}
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return [], {}
        candidates: list[Any] = []
        objective_map: dict[str, list[Any]] = {}
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_has_keyword(root, "HARVESTER"):
                continue
            objectives = self._tyr_objective_candidates_you_control(root)
            if not objectives:
                continue
            candidates.append(root)
            objective_map[uid] = objectives
        return sorted(candidates, key=self._tyr_sort_key), objective_map

    def _tyr_unit_has_destroyed_non_character_models(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        can_return = getattr(root, "_horrors_can_return_model", None)

        def _pool_has_returnable(pool: list[Any]) -> bool:
            for model in list(pool or []):
                if bool(getattr(model, "is_character", False)):
                    continue
                if callable(can_return) and not bool(can_return(model)):
                    continue
                return True
            return False

        if _pool_has_returnable(list(getattr(root, "models_lost", []) or [])):
            return True
        members_fn = getattr(root, "get_attached_unit_members", None)
        if callable(members_fn):
            for member in list(members_fn() or []):
                if member is None or member is root:
                    continue
                if _pool_has_returnable(list(getattr(member, "models_lost", []) or [])):
                    return True
        return False

    def _tyr_warrior_bioform_warrior_candidates(self) -> list[Any]:
        if not self._is_tyranids_warrior_bioform_onslaught_detachment():
            return []
        mgr = self._tyr_detachment_mgr()
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            is_warrior = bool(
                getattr(mgr, "_leader_beasts_unit_is_tyranid_warrior_datasheet", lambda *_a, **_k: False)(root)
            )
            if not is_warrior:
                is_warrior = bool(getattr(mgr, "_attached_unit_has_keyword", lambda *_a, **_k: False)(root, "TYRANID WARRIORS"))
            if not is_warrior:
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_warrior_bioform_secondary_endless_candidates(self, source_unit: Any) -> list[Any]:
        if not self._is_tyranids_warrior_bioform_onslaught_detachment():
            return []
        source_root = self._tyr_root(source_unit)
        if source_root is None:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if root is source_root:
                continue
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_is_endless_multitude_unit(root):
                continue
            if self._tyr_unit_is_battle_shocked(root):
                continue
            if not bool(unit_within_range_of_unit(source_root, root, 6.0, use_attached_aggregate=True)):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_warrior_bioform_synaptic_micronodes_candidates(self) -> tuple[list[Any], dict[str, list[Any]]]:
        if not self._is_tyranids_warrior_bioform_onslaught_detachment():
            return [], {}
        phase_name = self._tyr_phase_name(getattr(self, "_current_phase_name", ""))
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name != "movement phase" or active_player is not self.player:
            return [], {}
        candidates: list[Any] = []
        objective_map: dict[str, list[Any]] = {}
        for root in list(self._tyr_warrior_bioform_warrior_candidates() or []):
            objectives = self._tyr_objective_candidates_you_control(root)
            if not objectives:
                continue
            candidates.append(root)
            objective_map[self._tyr_sort_key(root)] = objectives
        return sorted(candidates, key=self._tyr_sort_key), objective_map

    def _tyr_warrior_bioform_synaptic_amplification_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_tyranids_warrior_bioform_onslaught_detachment():
            return []
        phase_key = self._tyr_phase_name(phase_name)
        if phase_key not in {"shooting phase", "fight phase"}:
            return []
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if self._tyr_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name=phase_key):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_warrior_bioform_restorative_impulse_candidates(self) -> list[Any]:
        if not self._is_tyranids_warrior_bioform_onslaught_detachment():
            return []
        if not self._tyr_is_own_command_phase(phase_name=self._tyr_phase_name(getattr(self, "_current_phase_name", ""))):
            return []
        out: list[Any] = []
        for root in list(self._tyr_warrior_bioform_warrior_candidates() or []):
            if not self._tyr_unit_has_destroyed_non_character_models(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_warrior_bioform_parasitic_payload_candidates(self) -> list[Any]:
        if not self._is_tyranids_warrior_bioform_onslaught_detachment():
            return []
        phase_key = self._tyr_phase_name(getattr(self, "_current_phase_name", ""))
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_key != "shooting phase" or active_player is not self.player:
            return []
        mgr = self._tyr_detachment_mgr()
        out: list[Any] = []
        for root in list(self._tyr_warrior_bioform_warrior_candidates() or []):
            if not bool(getattr(mgr, "_warrior_bioform_unit_is_ranged_tyranid_warrior_datasheet", lambda *_a, **_k: False)(root)):
                continue
            if self._tyr_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name="shooting phase"):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_warrior_bioform_spontaneous_hypercorrosion_candidates(self, *, phase_name: str) -> list[Any]:
        return self._tyr_warrior_bioform_synaptic_amplification_candidates(phase_name=phase_name)

    def _tyr_warrior_bioform_synaptic_shield_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_tyranids_warrior_bioform_onslaught_detachment():
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return []
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return []
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return []
        warrior_ids = {self._tyr_sort_key(root) for root in list(self._tyr_warrior_bioform_warrior_candidates() or [])}
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if not uid or uid in seen:
                continue
            seen.add(uid)
            if uid not in warrior_ids:
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_death_frenzy_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return []
        if attacking_unit is not None:
            attacker_root = self._tyr_root(attacking_unit)
            if attacker_root is None:
                return []
            if self._tyr_owned_by_player(attacker_root, self.player):
                return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_rapid_regeneration_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return []
        if attacking_unit is not None:
            attacker_root = self._tyr_root(attacking_unit)
            if attacker_root is None:
                return []
            if self._tyr_owned_by_player(attacker_root, self.player):
                return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_overrun_candidates(self, *, unit: Any = None) -> list[Any]:
        if not self._is_tyranids_invasion_fleet_detachment():
            return []
        if unit is not None:
            root = self._tyr_root(unit)
            if root is None:
                return []
            if not self._tyr_owned_by_player(root, self.player):
                return []
            if not self._tyr_on_battlefield(root, require_targetable=True):
                return []
            if not self._is_tyranids_unit(root):
                return []
            return [root]

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit_entry in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit_entry)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_invisible_hunter_candidates(self) -> list[Any]:
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            is_vanguard = self._tyr_is_vanguard_invader_unit(root)
            is_tyr_infantry = self._tyr_is_infantry_unit(root)
            if not (is_vanguard or is_tyr_infantry):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_validate_vanguard_pair_selection(
        self,
        selected_roots: list[Any],
        *,
        eligible: list[Any],
        vanguard_candidates: list[Any],
        infantry_candidates: list[Any],
    ) -> tuple[bool, str]:
        if not selected_roots:
            return False, "no_units"
        if len(selected_roots) > 2:
            return False, "too_many_units"
        valid_vanguard = self._tyr_resolve_units(vanguard_candidates) or [
            unit for unit in list(eligible or []) if self._tyr_is_vanguard_invader_unit(unit)
        ]
        valid_infantry = self._tyr_resolve_units(infantry_candidates) or [
            unit for unit in list(eligible or []) if self._tyr_is_infantry_unit(unit)
        ]
        selected_vanguard = 0
        selected_infantry_only = 0
        for root in list(selected_roots):
            if not self._tyr_unit_in_candidates(root, eligible):
                return False, "unit_not_candidate"
            is_vanguard = self._tyr_unit_in_candidates(root, valid_vanguard)
            is_infantry = self._tyr_unit_in_candidates(root, valid_infantry)
            if not (is_vanguard or is_infantry):
                return False, "unit_not_eligible"
            if is_vanguard:
                selected_vanguard += 1
            else:
                selected_infantry_only += 1
        if selected_infantry_only > 1:
            return False, "too_many_infantry"
        if selected_infantry_only > 0 and len(selected_roots) > 1:
            return False, "mixed_selection"
        if len(selected_roots) == 2 and selected_vanguard != 2:
            return False, "two_units_require_vanguard"
        return True, ""

    def _tyr_pending_choose_quarry_request(self, *, ability: str, **match_context: Any) -> bool:
        game = getattr(self, "game", None)
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != str(DECISION_CHOOSE_QUARRY):
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != str(ability or ""):
                continue
            matches = True
            for key, value in dict(match_context or {}).items():
                if isinstance(value, (list, tuple, set)):
                    expected = [str(item or "").strip() for item in list(value or []) if str(item or "").strip()]
                    current = [
                        str(item or "").strip()
                        for item in list(ctx.get(key, []) or [])
                        if str(item or "").strip()
                    ]
                    if current != expected:
                        matches = False
                        break
                    continue
                if str(ctx.get(key, "") or "").strip() != str(value or "").strip():
                    matches = False
                    break
            if matches:
                return True
        return False

    def _tyr_vanguard_selection_payloads(
        self,
        *,
        eligible: list[Any],
        vanguard_candidates: list[Any],
        single_unit_candidates: list[Any],
    ) -> list[dict[str, Any]]:
        eligible_roots = self._tyr_resolve_units(eligible)
        if not eligible_roots:
            return []
        valid_vanguard = self._tyr_resolve_units(vanguard_candidates) or [
            unit for unit in list(eligible_roots or []) if self._tyr_is_vanguard_invader_unit(unit)
        ]
        valid_single = self._tyr_resolve_units(single_unit_candidates) or list(eligible_roots)
        payloads: list[dict[str, Any]] = []
        seen_keys: set[str] = set()

        def _add_selection(selected_roots: list[Any]) -> None:
            is_valid, _reason = self._tyr_validate_vanguard_pair_selection(
                selected_roots,
                eligible=eligible_roots,
                vanguard_candidates=valid_vanguard,
                infantry_candidates=valid_single,
            )
            if not is_valid:
                return
            resolved_roots = self._tyr_resolve_units(selected_roots)
            selected_ids = [self._tyr_sort_key(root) for root in list(resolved_roots) if self._tyr_sort_key(root)]
            if not selected_ids:
                return
            key = "|".join(selected_ids)
            if key in seen_keys:
                return
            seen_keys.add(key)
            payloads.append(
                {
                    "label": ", ".join(str(getattr(root, "name", "Unit") or "Unit") for root in list(resolved_roots)),
                    "payload": {"selected_unit_ids": list(selected_ids)},
                }
            )

        for root in list(valid_single):
            _add_selection([root])
        for left, right in combinations(list(valid_vanguard), 2):
            _add_selection([left, right])
        payloads.sort(
            key=lambda item: tuple(
                str(value or "").strip()
                for value in list(dict(item.get("payload", {}) or {}).get("selected_unit_ids", []) or [])
            )
        )
        return payloads

    def _tyr_vanguard_surprise_assault_enemy_candidates(self, *, attacking_unit: Any, target_units: Any) -> list[Any]:
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return []
        game = getattr(self, "game", None)
        if game is None:
            return []
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return []
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return []
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or not self._tyr_owned_by_player(attacker_root, self.player):
            return []
        if not self._tyr_on_battlefield(attacker_root, require_targetable=True):
            return []
        if not self._is_tyranids_unit(attacker_root):
            return []
        if not self._tyr_is_vanguard_invader_unit(attacker_root):
            return []
        if self._tyr_unit_already_selected_to_shoot_or_fight_this_phase(
            attacker_root,
            phase_name="Shooting phase" if phase_key == "SHOOTING_PHASE" else "Fight phase",
        ):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=False):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_vanguard_assassin_beasts_candidates(self) -> list[Any]:
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return []
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_is_vanguard_invader_unit(root):
                continue
            if not self._tyr_is_infantry_unit(root):
                continue
            is_eligible = getattr(root, "is_eligible_to_fight", None)
            if not callable(is_eligible) or not bool(is_eligible(game_map)):
                continue
            if self._tyr_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name="Fight phase"):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_vanguard_seeded_broods_candidates(self) -> list[Any]:
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._is_tyranids_unit(root):
                continue
            is_in_reserves = getattr(root, "is_in_reserves", None)
            if not callable(is_in_reserves) or not bool(is_in_reserves()):
                continue
            if bool(getattr(root, "embarked_in", None)):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_vanguard_targeted_vanguard_invader_candidates(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> list[Any]:
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return []
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_is_vanguard_invader_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_vanguard_hypersensory_scillia_candidates(self, *, enemy_unit: Any) -> list[Any]:
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return []
        enemy_root = self._tyr_root(enemy_unit)
        if enemy_root is None or self._tyr_owned_by_player(enemy_root, self.player):
            return []
        if not self._tyr_on_battlefield(enemy_root, require_targetable=True):
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if self._tyr_unit_in_engagement_range(root):
                continue
            is_vanguard = self._tyr_is_vanguard_invader_unit(root)
            is_infantry = self._tyr_is_infantry_unit(root)
            if not (is_vanguard or is_infantry):
                continue
            if not unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_untrammelled_ferocity_candidates(self) -> list[Any]:
        if not self._is_tyranids_crusher_stampede_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
            if not is_monster:
                continue
            if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_crusher_monster_candidates(
        self,
        *,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
    ) -> list[Any]:
        if not self._is_tyranids_crusher_stampede_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
            if not is_monster:
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(
                getattr(round_state, "shot_this_phase", False) or getattr(round_state, "shot_this_round", False)
            ):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_rampaging_monstrosities_candidates(self) -> list[Any]:
        return self._tyr_crusher_monster_candidates(require_not_fought=True)

    def _tyr_swarm_guided_salvoes_candidates(self) -> list[Any]:
        return self._tyr_crusher_monster_candidates(require_not_shot=True)

    def _tyr_savage_roar_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_tyranids_crusher_stampede_detachment():
            return []
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
            if not is_monster:
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_massive_impact_source_models(self, source_unit: Any) -> list[Any]:
        if not self._is_tyranids_crusher_stampede_detachment():
            return []
        root = self._tyr_root(source_unit)
        if root is None:
            return []
        if not self._tyr_owned_by_player(root, self.player):
            return []
        if not self._tyr_on_battlefield(root, require_targetable=True):
            return []
        if not self._is_tyranids_unit(root):
            return []
        is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
        if not is_monster:
            return []
        if not bool(getattr(getattr(root, "round_state", None), "charged_this_round", False)):
            return []
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        out: list[Any] = []
        seen: set[str] = set()
        for model in list(models or []):
            if model is None:
                continue
            is_alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
            if not is_alive:
                continue
            model_id = str(get_entity_id(model) or "")
            if model_id and model_id in seen:
                continue
            if model_id:
                seen.add(model_id)
            if not self._tyr_massive_impact_enemy_candidates(model):
                continue
            out.append(model)
        out.sort(key=lambda model: str(get_entity_id(model) or ""))
        return out

    def _tyr_massive_impact_enemy_candidates(self, source_model: Any) -> list[Any]:
        if not self._is_tyranids_crusher_stampede_detachment():
            return []
        if source_model is None:
            return []
        source_unit = getattr(source_model, "parent_unit", None)
        source_root = self._tyr_root(source_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if source_root is None or game_map is None:
            return []
        if not self._tyr_on_battlefield(source_root, require_targetable=True):
            return []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        from ..utility.aura_utils import model_within_engagement_range_of_unit

        out: list[Any] = []
        seen: set[str] = set()
        for enemy_unit in list(get_enemy_units(source_root) or []):
            enemy_root = self._tyr_root(enemy_unit)
            if enemy_root is None:
                continue
            if self._tyr_owned_by_player(enemy_root, self.player):
                continue
            if not self._tyr_on_battlefield(enemy_root, require_targetable=False):
                continue
            try:
                if not bool(model_within_engagement_range_of_unit(source_model, enemy_root)):
                    continue
            except Exception:
                continue
            enemy_id = self._tyr_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            out.append(enemy_root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_override_instincts_candidates(self) -> list[Any]:
        if not self._is_tyranids_synaptic_nexus_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                continue
            if not self._tyr_unit_in_synapse_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_is_synapse_unit(self, unit: Any) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        return self._tyr_has_keyword(root, "SYNAPSE")

    def _tyr_unit_visible_to_unit(self, source_unit: Any, target_unit: Any) -> bool:
        source_root = self._tyr_root(source_unit)
        target_root = self._tyr_root(target_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if source_root is None or target_root is None or game_map is None:
            return False
        has_los = getattr(source_root, "_has_line_of_sight_to_target", None)
        if not callable(has_los):
            return False
        for model in self._tyr_iter_unit_models(source_root):
            if not self._tyr_model_is_alive(model):
                continue
            if bool(has_los(model, target_root, game_map)):
                return True
        return False

    def _tyr_unit_already_selected_to_shoot_or_fight_this_phase(self, unit: Any, *, phase_name: str) -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return True
        phase_key = self._tyr_phase_name(phase_name)
        if phase_key == "shooting phase":
            return bool(getattr(getattr(root, "round_state", None), "shot_this_round", False))
        if phase_key != "fight phase":
            return True
        fight_mgr = getattr(self.game, "fight_phase_manager", None) if self.game is not None else None
        fought_units = getattr(fight_mgr, "fought_units", set()) if fight_mgr is not None else set()
        return bool(root in fought_units or getattr(getattr(root, "round_state", None), "fought_this_round", False))

    def _tyr_synaptic_nexus_synapse_candidates(self) -> list[Any]:
        if not self._is_tyranids_synaptic_nexus_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_is_synapse_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_reinforced_hive_node_candidates(self, *, attacking_unit: Any, target_units: Any) -> list[Any]:
        if not self._is_tyranids_synaptic_nexus_detachment():
            return []
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_is_synapse_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_irresistible_will_source_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_tyranids_synaptic_nexus_detachment():
            return []
        out: list[Any] = []
        for root in list(self._tyr_synaptic_nexus_synapse_candidates() or []):
            if self._tyr_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name=phase_name):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_irresistible_will_enemy_candidates(self, source_unit: Any) -> list[Any]:
        if not self._is_tyranids_synaptic_nexus_detachment():
            return []
        source_root = self._tyr_root(source_unit)
        game_map = getattr(getattr(self, "game", None), "map", None)
        if source_root is None or game_map is None:
            return []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for enemy_unit in list(get_enemy_units(source_root) or []):
            enemy_root = self._tyr_root(enemy_unit)
            if enemy_root is None:
                continue
            enemy_id = self._tyr_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if self._tyr_owned_by_player(enemy_root, self.player):
                continue
            if not self._tyr_on_battlefield(enemy_root, require_targetable=True):
                continue
            if not unit_within_range_of_unit(source_root, enemy_root, 24.0, use_attached_aggregate=True):
                continue
            if not self._tyr_unit_visible_to_unit(source_root, enemy_root):
                continue
            out.append(enemy_root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_synaptic_channelling_candidates(self) -> list[Any]:
        return list(self._tyr_synaptic_nexus_synapse_candidates() or [])

    def _tyr_imperative_dominance_candidates(self) -> list[Any]:
        if not self._is_tyranids_synaptic_nexus_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_unit_in_synapse_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_smothering_shadow_candidates(self, *, enemy_unit: Any) -> list[Any]:
        if not self._is_tyranids_synaptic_nexus_detachment():
            return []
        enemy_root = self._tyr_root(enemy_unit)
        if enemy_root is None or self._tyr_owned_by_player(enemy_root, self.player):
            return []
        out: list[Any] = []
        for root in list(self._tyr_synaptic_nexus_synapse_candidates() or []):
            if not unit_within_range_of_unit(root, enemy_root, 12.0, use_attached_aggregate=True):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_adaptive_optimisation_candidates(self) -> list[Any]:
        if not self._is_tyranids_subterranean_assault_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._tyr_detachment_mgr()
        checker = getattr(mgr, "_unit_is_mawloc_or_trygon_datasheet", None) if mgr is not None else None
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
                continue
            if callable(checker):
                if not bool(checker(root)):
                    continue
            elif not (self._tyr_has_keyword(root, "MAWLOC") or self._tyr_has_keyword(root, "TRYGON")):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_replenishing_swarms_candidates(self) -> list[Any]:
        if not self._is_tyranids_subterranean_assault_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_current_tunnel_marker_ids(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_enfilading_emergence_candidates(self) -> list[Any]:
        if not self._is_tyranids_subterranean_assault_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_unit_arrived_from_reserves_this_turn(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_tunnel_network_candidates(self) -> list[Any]:
        if not self._is_tyranids_subterranean_assault_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._tyr_detachment_mgr()
        get_markers = getattr(mgr, "get_active_tunnel_markers", None) if mgr is not None else None
        active_marker_ids = {
            str(getattr(marker, "marker_id", "") or "").strip()
            for marker in list(get_markers() or [])
            if str(getattr(marker, "marker_id", "") or "").strip()
        } if callable(get_markers) else set()
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if self._tyr_unit_in_engagement_range(root):
                continue
            current_marker_ids = self._tyr_current_tunnel_marker_ids(root)
            if not current_marker_ids:
                continue
            destination_ids = [
                marker_id
                for marker_id in sorted(active_marker_ids)
                if any(source_id != marker_id for source_id in list(current_marker_ids))
            ]
            if not destination_ids:
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_swarming_assault_candidates(self) -> list[Any]:
        if not self._is_tyranids_subterranean_assault_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if not self._tyr_is_monster_unit(root):
                continue
            if not self._tyr_unit_arrived_from_reserves_this_turn(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_retreat_below_candidates(self) -> list[Any]:
        if not self._is_tyranids_subterranean_assault_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._tyr_owned_by_player(root, self.player):
                continue
            if not self._tyr_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_tyranids_unit(root):
                continue
            if self._tyr_unit_in_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._tyr_sort_key)

    def _tyr_spend_cp(self, stratagem: Any, *, target_unit: Any = None, enemy_unit: Any = None) -> bool:
        effective_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit, enemy_unit=enemy_unit) or {}
            effective_cost = int(preview.get("cost", effective_cost))
        return bool(
            self.player.spend_command_points(
                int(effective_cost),
                reason=f"Stratagem: {getattr(stratagem, 'name', 'Unknown')}",
                source="stratagem",
            )
        )

    def _tyr_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._tyr_root(unit)
        if root is None:
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        place_fn = getattr(root, "enter_strategic_reserves_midgame", None)
        if callable(place_fn):
            return bool(place_fn(game=game, game_map=game_map, reason=reason))

        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            if member is None:
                continue
            set_status = getattr(member, "set_reserve_status", None)
            if callable(set_status):
                set_status("strategic_reserves")
            else:
                member.reserve_status = "strategic_reserves"
            mark_midgame = getattr(member, "mark_entered_reserves_midgame", None)
            if callable(mark_midgame):
                mark_midgame(game=game)
            if bool(getattr(member, "is_aircraft", False)) and not bool(getattr(member, "hover_mode", False)):
                member._aircraft_return_turn = int(getattr(game, "turn", 0) or 0) + 1 if game is not None else 0
            member.deployed = True
            member.reserve_turn_deployed = None
            member.arrived_from_reserves_this_turn = False
            if game_map is not None and isinstance(getattr(game_map, "units", None), list) and member in game_map.units:
                game_map.units.remove(member)
        return True

    def _tyr_clone_unending_waves_unit(self, unit: Any) -> Any:
        if unit is None:
            return None
        clone_hook = getattr(unit, "clone_for_cult_ambush", None)
        if callable(clone_hook):
            return clone_hook()
        try:
            from ..units.unit import Unit as UnitClass
        except ImportError:
            return None
        datasheet = getattr(unit, "_datasheet", None)
        if datasheet is None:
            return None
        count = int(getattr(unit, "starting_model_count", 0) or 0)
        if count <= 0:
            count = len(list(getattr(unit, "models", []) or []))
        if count <= 0:
            count = len(list(getattr(unit, "models_lost", []) or []))
        if count <= 0:
            return None
        try:
            new_unit = UnitClass(datasheet, quantity=count, enhancement=getattr(unit, "enhancement", None))
        except TypeError:
            new_unit = UnitClass(datasheet, quantity=count)
        self._tyr_copy_model_wargear(unit, new_unit)
        new_unit.is_warlord = bool(getattr(unit, "is_warlord", False))
        return new_unit

    def _tyr_copy_model_wargear(self, source_unit: Any, target_unit: Any) -> None:
        if source_unit is None or target_unit is None:
            return

        def _norm(text: str) -> str:
            raw = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in str(text or "").lower())
            return " ".join(raw.split())

        source_models = list(getattr(source_unit, "models", []) or [])
        source_models.extend(list(getattr(source_unit, "models_lost", []) or []))

        buckets: dict[str, list[Any]] = {}
        for source_model in source_models:
            key = _norm(getattr(source_model, "name", "") or "")
            buckets.setdefault(key, []).append(source_model)

        possible = list(getattr(target_unit, "possible_wargear", []) or [])
        possible_by_name = {_norm(getattr(wg, "name", "") or ""): wg for wg in possible}
        leftovers = [model for model in source_models if model is not None]

        for target_model in list(getattr(target_unit, "models", []) or []):
            key = _norm(getattr(target_model, "name", "") or "")
            source_model = None
            if key in buckets and buckets[key]:
                source_model = buckets[key].pop(0)
            elif leftovers:
                source_model = leftovers.pop(0)
            if source_model is None:
                continue

            target_model.wargear = []
            for wargear in list(getattr(source_model, "wargear", []) or []):
                name_key = _norm(getattr(wargear, "name", "") or "")
                target_model.wargear.append(possible_by_name.get(name_key, wargear))
            target_model.optional_wargear = list(getattr(source_model, "optional_wargear", []) or [])

    def _tyr_prepare_unending_waves_unit(self, unit: Any) -> bool:
        if unit is None:
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        set_parent = getattr(unit, "set_parent_army", None)
        if callable(set_parent):
            set_parent(army)
        else:
            unit.parent_army = army
        if hasattr(army, "add_unit"):
            army.add_unit(unit)
        else:
            army.units.append(unit)
        if not self._tyr_place_unit_into_strategic_reserves(unit, reason="UNENDING WAVES"):
            return False
        rebuild = getattr(self.game, "rebuild_entity_registry", None) if self.game is not None else None
        if callable(rebuild):
            rebuild()
        return True

    def _tyr_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            raw_name = str(getattr(stratagem, "name", "") or "").strip().upper()
            if raw_name:
                used.add(raw_name)

    def _tyr_clear_melee_fight_on_death_cache(self, unit: Any) -> None:
        root = self._tyr_root(unit)
        if root is None:
            return
        cache = getattr(root, "_ability_cache", None)
        if not isinstance(cache, dict):
            return
        for key in list(cache.keys()):
            if str(key).startswith("melee_fight_on_death_after_attacks:"):
                cache.pop(key, None)

    def _queue_tyranids_unending_swarm_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None:
            return
        if not self._is_tyranids_unending_swarm_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return
        candidates = self._tyr_unending_swarm_targeted_endless_multitude_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        queue_reaction = getattr(self, "_queue_reaction", None)
        if not callable(queue_reaction):
            return
        for stratagem_name in ("TEEMING MASSES", "PRESERVATION IMPERATIVE"):
            stratagem = getattr(self, "get_by_name", lambda _name: None)(stratagem_name)
            if stratagem is None:
                continue
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                continue
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                continue
            duplicate = False
            for reaction in list(getattr(self, "_pending_reactions", []) or []):
                if reaction.get("event") != "shooting_targets_selected":
                    continue
                if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                    continue
                if reaction.get("attacking_unit") is attacking_unit:
                    duplicate = True
                    break
            if duplicate:
                continue
            payload = {
                "event": "shooting_targets_selected",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "attacking_unit": attacking_unit,
                "target_units": list(target_units or []),
                "candidates": list(candidates),
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            queue_reaction(payload)

    def _queue_tyranids_unending_swarm_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None:
            return
        if not self._is_tyranids_unending_swarm_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("TEEMING MASSES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_unending_swarm_targeted_endless_multitude_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if reaction.get("event") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("attacking_unit") is attacking_unit:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tyranids_unending_swarm_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> None:
        if not self._is_tyranids_unending_swarm_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("SYNAPTIC GOADING")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_unending_swarm_synaptic_goading_candidates()
        if not candidates:
            return
        queue_reaction = getattr(self, "_queue_reaction", None)
        if not callable(queue_reaction):
            return
        attacker_root = self._tyr_root(attacker_unit)
        attacker_id = self._tyr_sort_key(attacker_root)
        for root in list(candidates or []):
            unit_id = self._tyr_sort_key(root)
            duplicate = False
            for reaction in list(getattr(self, "_pending_reactions", []) or []):
                if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                    continue
                if str(reaction.get("unit_id", "") or "") != unit_id:
                    continue
                duplicate = True
                break
            if duplicate:
                continue
            payload = {
                "event": "unit_shooting_resolved",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "attacking_unit": attacker_root,
                "attacking_unit_id": attacker_id,
                "hits_by_target": hits_by_target,
                "unit": root,
                "target_unit": root,
                "unit_id": unit_id,
                "candidates": [root],
            }
            queue_reaction(payload, use_timer=False)

    def _queue_tyranids_unending_waves_unit_destroyed_reactions(
        self,
        *,
        destroyed_unit: Any,
        destroyed_by_unit: Any = None,
    ) -> None:
        if destroyed_unit is None:
            return
        if not self._is_tyranids_unending_swarm_detachment():
            return
        if bool(getattr(self, "_tyr_unending_waves_used", False)):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("UNENDING WAVES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_unending_waves_candidates(destroyed_unit=destroyed_unit)
        if not candidates:
            return
        destroyed_root = candidates[0]
        destroyed_id = self._tyr_sort_key(destroyed_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("destroyed_unit_id", "") or "") == destroyed_id:
                return
        payload = {
            "event": "unit_destroyed",
            "phase_name": str(getattr(self, "_current_phase_name", "") or "").strip() or "Any phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "destroyed_unit": destroyed_root,
            "destroyed_unit_id": destroyed_id,
            "destroyed_by_unit": self._tyr_root(destroyed_by_unit),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_tyranids_assimilation_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None:
            return
        if not self._is_tyranids_assimilation_swarm_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("ABLATIVE CARAPACE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_ablative_carapace_candidates(attacking_unit=attacker_root, target_units=target_units)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "shooting_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tyranids_assimilation_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None:
            return
        if not self._is_tyranids_assimilation_swarm_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return
        queue_reaction = getattr(self, "_queue_reaction", None)
        if not callable(queue_reaction):
            return

        ablative = getattr(self, "get_by_name", lambda _name: None)("ABLATIVE CARAPACE")
        if ablative is not None and int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(ablative, "cp_cost", 0) or 0):
            name_u = str(getattr(ablative, "name", "") or "").strip().upper()
            if name_u not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                candidates = self._tyr_ablative_carapace_candidates(attacking_unit=attacker_root, target_units=target_units)
                if candidates:
                    already = False
                    for reaction in list(getattr(self, "_pending_reactions", []) or []):
                        if (
                            reaction.get("event") == "fight_targets_selected"
                            and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                            and reaction.get("attacking_unit") is attacking_unit
                        ):
                            already = True
                            break
                    if not already:
                        payload = {
                            "event": "fight_targets_selected",
                            "phase_name": "Fight phase",
                            "stratagem": ablative.name,
                            "cp_cost": ablative.cp_cost,
                            "attacking_unit": attacking_unit,
                            "target_units": list(target_units or []),
                            "candidates": candidates,
                        }
                        if len(candidates) == 1:
                            payload["unit"] = candidates[0]
                            payload["target_unit"] = candidates[0]
                        queue_reaction(payload)

    def _queue_tyranids_assimilation_model_destroyed_reactions(self, *, unit: Any, model: Any) -> None:
        if unit is None or model is None:
            return
        if not self._is_tyranids_assimilation_swarm_detachment():
            return
        root = self._tyr_root(unit)
        if root is None:
            return
        models = list(root.get_attached_unit_models() or []) if hasattr(root, "get_attached_unit_models") else list(getattr(root, "models", []) or [])
        for other in models:
            if other is model:
                continue
            if self._tyr_is_alive(other):
                return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("RECLAIM BIOMASS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_reclaim_biomass_candidates(destroyed_unit=root)
        if not candidates:
            return
        destroyed_id = self._tyr_sort_key(root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("destroyed_unit_id", "") or "") == destroyed_id:
                return
        payload = {
            "event": "model_destroyed_before_removal",
            "phase_name": str(getattr(self, "_current_phase_name", "") or "").strip() or "Any phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "destroyed_unit": root,
            "destroyed_unit_id": destroyed_id,
            "destroyed_model": model,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_tyranids_assimilation_unit_destroyed_reactions(
        self,
        *,
        destroyed_unit: Any,
        destroyed_by_unit: Any,
    ) -> None:
        if destroyed_unit is None or destroyed_by_unit is None:
            return
        if not self._is_tyranids_assimilation_swarm_detachment():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip() or "Any phase"
        queue_reaction = getattr(self, "_queue_reaction", None)
        if not callable(queue_reaction):
            return

        broodguard = getattr(self, "get_by_name", lambda _name: None)("BROODGUARD IMPULSE")
        if broodguard is not None and int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(broodguard, "cp_cost", 0) or 0):
            name_u = str(getattr(broodguard, "name", "") or "").strip().upper()
            if name_u not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                candidates = self._tyr_broodguard_impulse_candidates(
                    destroyed_unit=destroyed_unit,
                    destroyed_by_unit=destroyed_by_unit,
                )
                if candidates:
                    destroyed_id = self._tyr_sort_key(destroyed_unit)
                    already = False
                    for reaction in list(getattr(self, "_pending_reactions", []) or []):
                        if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                            continue
                        if str(reaction.get("destroyed_unit_id", "") or "") == destroyed_id:
                            already = True
                            break
                    if not already:
                        payload = {
                            "event": "unit_destroyed",
                            "phase_name": phase_name,
                            "stratagem": broodguard.name,
                            "cp_cost": broodguard.cp_cost,
                            "destroyed_unit": self._tyr_root(destroyed_unit),
                            "destroyed_unit_id": destroyed_id,
                            "destroyed_by_unit": self._tyr_root(destroyed_by_unit),
                            "candidates": candidates,
                        }
                        if len(candidates) == 1:
                            payload["unit"] = candidates[0]
                            payload["target_unit"] = candidates[0]
                        queue_reaction(payload, use_timer=False)

        rapacious = getattr(self, "get_by_name", lambda _name: None)("RAPACIOUS HUNGER")
        if rapacious is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(rapacious, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(rapacious, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_rapacious_hunger_candidates(
            destroyed_unit=destroyed_unit,
            destroyed_by_unit=destroyed_by_unit,
        )
        if not candidates:
            return
        attacker_id = self._tyr_sort_key(destroyed_by_unit)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("destroyed_by_unit_id", "") or "") == attacker_id:
                return
        payload = {
            "event": "unit_destroyed",
            "phase_name": phase_name,
            "stratagem": rapacious.name,
            "cp_cost": rapacious.cp_cost,
            "destroyed_unit": self._tyr_root(destroyed_unit),
            "destroyed_by_unit": self._tyr_root(destroyed_by_unit),
            "destroyed_by_unit_id": attacker_id,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction(payload, use_timer=False)

    def _queue_tyranids_invasion_fleet_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None:
            return
        if not self._is_tyranids_invasion_fleet_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None:
            return
        if self._tyr_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("DEATH FRENZY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_death_frenzy_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "fight_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

        # RAPID REGENERATION
        rapid = getattr(self, "get_by_name", lambda _name: None)("RAPID REGENERATION")
        if rapid is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(rapid, "cp_cost", 0) or 0):
            return
        rapid_name = str(getattr(rapid, "name", "") or "").strip().upper()
        if rapid_name in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        rapid_candidates = self._tyr_rapid_regeneration_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not rapid_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "fight_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == rapid_name
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        rapid_payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": rapid.name,
            "cp_cost": rapid.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": rapid_candidates,
        }
        if len(rapid_candidates) == 1:
            rapid_payload["unit"] = rapid_candidates[0]
            rapid_payload["target_unit"] = rapid_candidates[0]
        if callable(queue_reaction):
            queue_reaction(rapid_payload)

    def _queue_tyranids_invasion_fleet_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None:
            return
        if not self._is_tyranids_invasion_fleet_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None:
            return
        if self._tyr_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("RAPID REGENERATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_rapid_regeneration_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "shooting_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tyranids_invasion_fleet_before_consolidate_reactions(
        self,
        *,
        unit: Any,
        target_unit: Any = None,
    ) -> None:
        if unit is None:
            return
        if not self._is_tyranids_invasion_fleet_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        root = self._tyr_root(unit)
        if root is None:
            return
        if not self._tyr_owned_by_player(root, self.player):
            return
        candidates = self._tyr_overrun_candidates(unit=root)
        if not candidates:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("OVERRUN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "before_consolidate"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("unit") is root
            ):
                return
        payload = {
            "event": "before_consolidate",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "last_target_unit": target_unit,
            "candidates": candidates,
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tyranids_crusher_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None:
            return
        if not self._is_tyranids_crusher_stampede_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"charge", "charge move"}:
            return
        root = self._tyr_root(unit)
        if root is None or not self._tyr_owned_by_player(root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("MASSIVE IMPACT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        source_model_candidates = self._tyr_massive_impact_source_models(root)
        if not source_model_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("event") != "unit_move_ended":
                continue
            if self._tyr_root(reaction.get("unit")) is root:
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "source_unit": root,
            "action": str(action or ""),
            "source_model_candidates": source_model_candidates,
        }
        if len(source_model_candidates) == 1:
            source_model = source_model_candidates[0]
            enemy_candidates = self._tyr_massive_impact_enemy_candidates(source_model)
            payload["model"] = source_model
            payload["target_model"] = source_model
            payload["source_model"] = source_model
            payload["enemy_candidates"] = enemy_candidates
            if len(enemy_candidates) == 1:
                payload["enemy_unit"] = enemy_candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_tyranids_crusher_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None:
            return
        if not self._is_tyranids_crusher_stampede_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("SAVAGE ROAR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_savage_roar_candidates(attacking_unit=attacker_root, target_units=target_units)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "fight_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tyranids_crusher_model_destroyed_reactions(self, *, unit: Any, model: Any) -> None:
        if unit is None or model is None:
            return
        if not self._is_tyranids_crusher_stampede_detachment():
            return
        root = self._tyr_root(unit)
        if root is None or not self._tyr_owned_by_player(root, self.player):
            return
        if not self._is_tyranids_unit(root):
            return
        is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
        if not is_monster:
            return
        if self._tyr_has_keyword(root, "FLY") or self._tyr_has_keyword(model, "FLY"):
            return
        try:
            has_deadly, _dd = root.has_deadly_demise()
        except Exception:
            has_deadly = False
        if not has_deadly:
            return
        phase_key = str(getattr(self, "_current_phase_name", "") or "").strip().upper()
        if phase_key not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        game = getattr(self, "game", None)
        if phase_key == "SHOOTING_PHASE":
            active_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
            if active_player is self.player:
                return
        model_alive_attr = getattr(model, "is_alive", None)
        model_alive = bool(model_alive_attr() if callable(model_alive_attr) else model_alive_attr)
        if model_alive:
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("CORROSIVE VISCERA")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        destroyed_model_id = str(get_entity_id(model) or "")
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("destroyed_model_id", "") or "") == destroyed_model_id:
                return
        phase_label = "Shooting phase" if phase_key == "SHOOTING_PHASE" else "Fight phase"
        payload = {
            "event": "model_destroyed_before_removal",
            "phase_name": phase_label,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "destroyed_unit": root,
            "destroyed_model": model,
            "destroyed_model_id": destroyed_model_id,
            "unit": root,
            "target_unit": root,
            "model": model,
            "target_model": model,
        }
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_tyranids_vanguard_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None or not self._is_tyranids_vanguard_onslaught_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        queue_reaction = getattr(self, "_queue_reaction", None)
        if not callable(queue_reaction):
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None:
            return
        if active_player is self.player and self._tyr_owned_by_player(attacker_root, self.player):
            surprise = getattr(self, "get_by_name", lambda _name: None)("SURPRISE ASSAULT")
            if surprise is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(surprise, "cp_cost", 0) or 0):
                return
            name_u = str(getattr(surprise, "name", "") or "").strip().upper()
            if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            enemy_candidates = self._tyr_vanguard_surprise_assault_enemy_candidates(
                attacking_unit=attacker_root,
                target_units=target_units,
            )
            if not enemy_candidates:
                return
            for reaction in list(getattr(self, "_pending_reactions", []) or []):
                if (
                    reaction.get("event") == "shooting_targets_selected"
                    and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                    and reaction.get("attacking_unit") is attacking_unit
                ):
                    return
            payload = {
                "event": "shooting_targets_selected",
                "phase_name": "Shooting phase",
                "stratagem": surprise.name,
                "cp_cost": surprise.cp_cost,
                "attacking_unit": attacking_unit,
                "unit": attacker_root,
                "target_unit": attacker_root,
                "enemy_candidates": enemy_candidates,
            }
            if len(enemy_candidates) == 1:
                payload["enemy_unit"] = enemy_candidates[0]
            queue_reaction(payload)
            return
        if self._tyr_owned_by_player(attacker_root, self.player):
            return
        unseen = getattr(self, "get_by_name", lambda _name: None)("UNSEEN LURKERS")
        if unseen is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(unseen, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(unseen, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_vanguard_targeted_vanguard_invader_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "shooting_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": unseen.name,
            "cp_cost": unseen.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction(payload)

    def _queue_tyranids_vanguard_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None or not self._is_tyranids_vanguard_onslaught_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        queue_reaction = getattr(self, "_queue_reaction", None)
        if not callable(queue_reaction):
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or active_player is not self.player or not self._tyr_owned_by_player(attacker_root, self.player):
            return
        surprise = getattr(self, "get_by_name", lambda _name: None)("SURPRISE ASSAULT")
        if surprise is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(surprise, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(surprise, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        enemy_candidates = self._tyr_vanguard_surprise_assault_enemy_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not enemy_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "fight_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": surprise.name,
            "cp_cost": surprise.cp_cost,
            "attacking_unit": attacking_unit,
            "unit": attacker_root,
            "target_unit": attacker_root,
            "enemy_candidates": enemy_candidates,
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
        queue_reaction(payload)

    def _queue_tyranids_vanguard_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None or not self._is_tyranids_vanguard_onslaught_detachment():
            return
        action_key = self._tyr_normalize_token(action)
        if action_key not in {"move", "advance", "fall back"}:
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        enemy_root = self._tyr_root(unit)
        if enemy_root is None or self._tyr_owned_by_player(enemy_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("HYPERSENSORY SCILLIA")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_vanguard_hypersensory_scillia_candidates(enemy_unit=enemy_root)
        if not candidates:
            return
        enemy_id = self._tyr_sort_key(enemy_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("enemy_unit_id", "") or "") == enemy_id:
                return
        vanguard_candidates = [candidate for candidate in candidates if self._tyr_is_vanguard_invader_unit(candidate)]
        infantry_candidates = [candidate for candidate in candidates if self._tyr_is_infantry_unit(candidate)]
        max_units = 2 if len(vanguard_candidates) >= 2 else 1
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "enemy_unit_id": enemy_id,
            "move_action": str(action),
            "candidates": candidates,
            "vanguard_candidates": vanguard_candidates,
            "infantry_candidates": infantry_candidates,
            "max_units": int(max_units),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _queue_tyranids_vanguard_onslaught_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        if player is self.player:
            return
        queue_reaction = getattr(self, "_queue_reaction", None)
        if not callable(queue_reaction):
            return

        if self._is_tyranids_vanguard_onslaught_detachment():
            stratagem = getattr(self, "get_by_name", lambda _name: None)("INVISIBLE HUNTER")
            if stratagem is not None:
                if int(getattr(self.player, "command_points", 0) or 0) >= int(getattr(stratagem, "cp_cost", 0) or 0):
                    name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
                    if name_u not in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                        if stratagem.can_use(self.player, self.game, phase_name="Fight phase"):
                            candidates = self._tyr_invisible_hunter_candidates()
                            if candidates:
                                already_queued = False
                                for reaction in list(getattr(self, "_pending_reactions", []) or []):
                                    if str(reaction.get("event", "") or "").strip() != "phase_end":
                                        continue
                                    if str(reaction.get("phase_name", "") or "").strip().lower() != "fight phase":
                                        continue
                                    if str(reaction.get("stratagem", "") or "").strip().upper() == name_u:
                                        already_queued = True
                                        break
                                if not already_queued:
                                    vanguard_candidates = [
                                        unit for unit in candidates if self._tyr_is_vanguard_invader_unit(unit)
                                    ]
                                    infantry_candidates = [unit for unit in candidates if self._tyr_is_infantry_unit(unit)]
                                    max_units = 2 if len(vanguard_candidates) >= 2 else 1
                                    payload: dict[str, Any] = {
                                        "event": "phase_end",
                                        "phase": "Fight phase",
                                        "phase_name": "Fight phase",
                                        "stratagem": stratagem.name,
                                        "cp_cost": stratagem.cp_cost,
                                        "candidates": candidates,
                                        "vanguard_candidates": vanguard_candidates,
                                        "infantry_candidates": infantry_candidates,
                                        "max_units": int(max_units),
                                    }
                                    if len(candidates) == 1:
                                        payload["unit"] = candidates[0]
                                        payload["target_unit"] = candidates[0]
                                    queue_reaction(payload, use_timer=False)

        if self._is_tyranids_subterranean_assault_detachment():
            stratagem = getattr(self, "get_by_name", lambda _name: None)("RETREAT BELOW")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            if not stratagem.can_use(self.player, self.game, phase_name="Fight phase"):
                return
            candidates = self._tyr_retreat_below_candidates()
            if not candidates:
                return
            for reaction in list(getattr(self, "_pending_reactions", []) or []):
                if str(reaction.get("event", "") or "").strip() != "phase_end":
                    continue
                if str(reaction.get("phase_name", "") or "").strip().lower() != "fight phase":
                    continue
                if str(reaction.get("stratagem", "") or "").strip().upper() == name_u:
                    return
            burrower_candidates = [unit for unit in candidates if self._tyr_is_burrower_unit(unit)]
            max_units = 2 if len(burrower_candidates) >= 2 else 1
            payload = {
                "event": "phase_end",
                "phase": "Fight phase",
                "phase_name": "Fight phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
                "burrower_candidates": burrower_candidates,
                "max_units": int(max_units),
            }
            if len(candidates) == 1:
                payload["unit"] = candidates[0]
                payload["target_unit"] = candidates[0]
            queue_reaction(payload, use_timer=False)

    def _queue_tyranids_warrior_bioform_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None or not self._is_tyranids_warrior_bioform_onslaught_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("SYNAPTIC SHIELD")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_warrior_bioform_synaptic_shield_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "shooting_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tyranids_synaptic_nexus_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None or not self._is_tyranids_synaptic_nexus_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("REINFORCED HIVE NODE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_reinforced_hive_node_candidates(attacking_unit=attacker_root, target_units=target_units)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "shooting_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tyranids_synaptic_nexus_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: Any,
    ) -> None:
        if attacking_unit is None or not self._is_tyranids_synaptic_nexus_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "FIGHT_PHASE":
            return
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None or self._tyr_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("REINFORCED HIVE NODE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_reinforced_hive_node_candidates(attacking_unit=attacker_root, target_units=target_units)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                reaction.get("event") == "fight_targets_selected"
                and str(reaction.get("stratagem", "") or "").strip().upper() == name_u
                and reaction.get("attacking_unit") is attacking_unit
            ):
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_tyranids_synaptic_nexus_failed_battleshock_reactions(
        self,
        *,
        enemy_unit: Any,
        passed: bool,
    ) -> None:
        if passed or enemy_unit is None or not self._is_tyranids_synaptic_nexus_detachment():
            return
        enemy_root = self._tyr_root(enemy_unit)
        if enemy_root is None or self._tyr_owned_by_player(enemy_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("THE SMOTHERING SHADOW")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._tyr_smothering_shadow_candidates(enemy_unit=enemy_root)
        if not candidates:
            return
        enemy_id = self._tyr_sort_key(enemy_root)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if str(reaction.get("enemy_unit_id", "") or "") == enemy_id:
                return
        payload = {
            "event": "battle_shock_test_resolved",
            "phase_name": str(getattr(self, "_current_phase_name", "") or "").strip() or "Any phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "enemy_unit_id": enemy_id,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _cleanup_tyranids_invasion_fleet_phase_start_effects(self, *, player: Any = None, phase: Any = None) -> None:
        if str(getattr(phase, "name", "") or "").strip().upper() != "COMMAND_PHASE":
            return
        if player is not self.player:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if self._is_tyranids_invasion_fleet_detachment():
                if sr.get("tyranids_predatory_imperative_active") is True:
                    for key in (
                        "tyranids_predatory_imperative_active",
                        "tyranids_predatory_imperative_adaptation_key",
                        "tyranids_predatory_imperative_source",
                        "tyranids_predatory_imperative_owner",
                        "tyranids_predatory_imperative_turn",
                    ):
                        sr.pop(key, None)
            if self._is_tyranids_subterranean_assault_detachment():
                exp = str(sr.get("tyranids_subterranean_adaptive_optimisation_expires_phase", "") or "").strip().upper()
                if sr.get("tyranids_subterranean_adaptive_optimisation_active") is True and (not exp or exp == "COMMAND_PHASE"):
                    if bool(sr.get("tyranids_subterranean_adaptive_optimisation_added_unit_keyword", False)):
                        self._tyr_remove_keyword_exact(root, "SYNAPSE")
                    added_model_ids = {
                        str(value or "").strip()
                        for value in list(sr.get("tyranids_subterranean_adaptive_optimisation_added_model_ids", []) or [])
                        if str(value or "").strip()
                    }
                    if added_model_ids:
                        for model in self._tyr_iter_unit_models(root):
                            if str(get_entity_id(model) or "") in added_model_ids:
                                self._tyr_remove_keyword_exact(model, "SYNAPSE")
                    for key in (
                        "tyranids_subterranean_adaptive_optimisation_active",
                        "tyranids_subterranean_adaptive_optimisation_expires_phase",
                        "tyranids_subterranean_adaptive_optimisation_source",
                        "tyranids_subterranean_adaptive_optimisation_turn_owner",
                        "tyranids_subterranean_adaptive_optimisation_turn",
                        "tyranids_subterranean_adaptive_optimisation_added_unit_keyword",
                        "tyranids_subterranean_adaptive_optimisation_added_model_ids",
                    ):
                        sr.pop(key, None)
            root.special_rules = sr

    def _cleanup_tyranids_crusher_stampede_phase_end_effects(self, *, phase: Any = None) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"MOVEMENT_PHASE", "CHARGE_PHASE", "FIGHT_PHASE", "SHOOTING_PHASE"}:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._tyr_root(unit)
            if root is None:
                continue
            uid = self._tyr_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if self._is_tyranids_subterranean_assault_detachment():
                if phase_key == "CHARGE_PHASE":
                    exp = str(sr.get("tyranids_subterranean_swarming_assault_expires_phase", "") or "").strip().upper()
                    if sr.get("tyranids_subterranean_swarming_assault_active") is True and (not exp or exp == "CHARGE_PHASE"):
                        for key in (
                            "tyranids_subterranean_swarming_assault_active",
                            "tyranids_subterranean_swarming_assault_expires_phase",
                            "tyranids_subterranean_swarming_assault_turn_owner",
                            "tyranids_subterranean_swarming_assault_turn",
                            "tyranids_subterranean_swarming_assault_source",
                        ):
                            sr.pop(key, None)
                if phase_key == "FIGHT_PHASE":
                    exp = str(sr.get("tyranids_enfilading_emergence_expires_phase", "") or "").strip().upper()
                    if sr.get("tyranids_enfilading_emergence_active") is True and (not exp or exp == "FIGHT_PHASE"):
                        for model in self._tyr_iter_unit_models(root):
                            effects = getattr(model, "_temporary_effects", None)
                            if not isinstance(effects, dict):
                                continue
                            for key in list(effects.keys()):
                                if str(key or "").startswith("tyranids_enfilading_emergence:"):
                                    effects.pop(key, None)
                        for key in (
                            "tyranids_enfilading_emergence_active",
                            "tyranids_enfilading_emergence_expires_phase",
                            "tyranids_enfilading_emergence_turn_owner",
                            "tyranids_enfilading_emergence_turn",
                            "tyranids_enfilading_emergence_source",
                        ):
                            sr.pop(key, None)
            if self._is_tyranids_unending_swarm_detachment():
                if phase_key == "SHOOTING_PHASE":
                    exp = str(sr.get("tyranids_preservation_imperative_expires_phase", "") or "").strip().upper()
                    if sr.get("tyranids_preservation_imperative_active") is True and (not exp or exp == "SHOOTING_PHASE"):
                        for key in (
                            "tyranids_preservation_imperative_active",
                            "tyranids_preservation_imperative_expires_phase",
                            "tyranids_preservation_imperative_turn_owner",
                            "tyranids_preservation_imperative_turn",
                            "tyranids_preservation_imperative_source",
                        ):
                            sr.pop(key, None)

                    exp = str(sr.get("tyranids_synaptic_goading_expires_phase", "") or "").strip().upper()
                    if sr.get("tyranids_synaptic_goading_active") is True and (not exp or exp == "SHOOTING_PHASE"):
                        for key in (
                            "tyranids_synaptic_goading_active",
                            "tyranids_synaptic_goading_phase_key",
                            "tyranids_synaptic_goading_expires_phase",
                            "tyranids_synaptic_goading_source",
                        ):
                            sr.pop(key, None)

                if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
                    exp = str(sr.get("tyranids_swarming_masses_expires_phase", "") or "").strip().upper()
                    if sr.get("tyranids_swarming_masses_active") is True and (not exp or exp == phase_key):
                        attack_type = str(sr.get("tyranids_swarming_masses_attack_type", "") or "").strip().lower()
                        if attack_type == "ranged" and bool(sr.get("tyranids_swarming_masses_added_sustained_ranged", False)):
                            prev = int(sr.get("tyranids_swarming_masses_prev_sustained_ranged", 0) or 0)
                            if prev > 0:
                                sr["bearer_unit_sustained_hits_value_ranged"] = prev
                            else:
                                sr.pop("bearer_unit_sustained_hits_value_ranged", None)
                        if attack_type == "melee" and bool(sr.get("tyranids_swarming_masses_added_sustained_melee", False)):
                            prev = int(sr.get("tyranids_swarming_masses_prev_sustained_melee", 0) or 0)
                            if prev > 0:
                                sr["bearer_unit_sustained_hits_value_melee"] = prev
                            else:
                                sr.pop("bearer_unit_sustained_hits_value_melee", None)
                        for key in (
                            "tyranids_swarming_masses_active",
                            "tyranids_swarming_masses_attack_type",
                            "tyranids_swarming_masses_expires_phase",
                            "tyranids_swarming_masses_turn_owner",
                            "tyranids_swarming_masses_turn",
                            "tyranids_swarming_masses_source",
                            "tyranids_swarming_masses_added_sustained_ranged",
                            "tyranids_swarming_masses_prev_sustained_ranged",
                            "tyranids_swarming_masses_added_sustained_melee",
                            "tyranids_swarming_masses_prev_sustained_melee",
                            "tyranids_swarming_masses_crit_threshold",
                            "tyranids_swarming_masses_crit_model_threshold",
                        ):
                            sr.pop(key, None)
            if not self._is_tyranids_crusher_stampede_detachment():
                root.special_rules = sr
                continue
            if phase_key == "MOVEMENT_PHASE":
                exp = str(sr.get("tyranids_untrammelled_ferocity_expires_phase", "") or "").strip().upper()
                if sr.get("tyranids_untrammelled_ferocity_active") is True and (not exp or exp == "MOVEMENT_PHASE"):
                    for key, added_key in (
                        ("bearer_unit_phase_move_types", "tyranids_untrammelled_ferocity_added_phase_move_types"),
                        (
                            "bearer_unit_phase_move_block_titanic_types",
                            "tyranids_untrammelled_ferocity_added_phase_move_block_titanic_types",
                        ),
                        (
                            "bearer_unit_phase_move_engagement_types",
                            "tyranids_untrammelled_ferocity_added_phase_move_engagement_types",
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

                    if bool(sr.get("tyranids_untrammelled_ferocity_prev_stride_height_present", False)):
                        sr["titanic_stride_tall_terrain_height"] = float(
                            sr.get("tyranids_untrammelled_ferocity_prev_stride_height_value", 4.0) or 4.0
                        )
                    else:
                        sr.pop("titanic_stride_tall_terrain_height", None)

                    if bool(sr.get("tyranids_untrammelled_ferocity_prev_stride_source_present", False)):
                        sr["titanic_stride_source"] = str(
                            sr.get("tyranids_untrammelled_ferocity_prev_stride_source_value", "") or ""
                        )
                    else:
                        sr.pop("titanic_stride_source", None)

                    for key in (
                        "tyranids_untrammelled_ferocity_active",
                        "tyranids_untrammelled_ferocity_expires_phase",
                        "tyranids_untrammelled_ferocity_turn_owner",
                        "tyranids_untrammelled_ferocity_turn",
                        "tyranids_untrammelled_ferocity_source",
                        "tyranids_untrammelled_ferocity_added_phase_move_types",
                        "tyranids_untrammelled_ferocity_added_phase_move_block_titanic_types",
                        "tyranids_untrammelled_ferocity_added_phase_move_engagement_types",
                        "tyranids_untrammelled_ferocity_prev_stride_height_present",
                        "tyranids_untrammelled_ferocity_prev_stride_height_value",
                        "tyranids_untrammelled_ferocity_prev_stride_source_present",
                        "tyranids_untrammelled_ferocity_prev_stride_source_value",
                    ):
                        sr.pop(key, None)

            if phase_key == "FIGHT_PHASE":
                exp = str(sr.get("tyranids_rampaging_monstrosities_expires_phase", "") or "").strip().upper()
                if sr.get("tyranids_rampaging_monstrosities_active") is True and (not exp or exp == "FIGHT_PHASE"):
                    for key in (
                        "tyranids_rampaging_monstrosities_active",
                        "tyranids_rampaging_monstrosities_expires_phase",
                        "tyranids_rampaging_monstrosities_turn_owner",
                        "tyranids_rampaging_monstrosities_turn",
                        "tyranids_rampaging_monstrosities_source",
                    ):
                        sr.pop(key, None)

            if phase_key == "SHOOTING_PHASE":
                exp = str(sr.get("tyranids_swarm_guided_salvoes_expires_phase", "") or "").strip().upper()
                if sr.get("tyranids_swarm_guided_salvoes_active") is True and (not exp or exp == "SHOOTING_PHASE"):
                    for key in (
                        "tyranids_swarm_guided_salvoes_active",
                        "tyranids_swarm_guided_salvoes_expires_phase",
                        "tyranids_swarm_guided_salvoes_turn_owner",
                        "tyranids_swarm_guided_salvoes_turn",
                        "tyranids_swarm_guided_salvoes_source",
                    ):
                        sr.pop(key, None)
            root.special_rules = sr

    def _use_tyranids_invasion_fleet_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if self._is_tyranids_assimilation_swarm_detachment():
            if name_u == "ABLATIVE CARAPACE":
                return self._use_tyranids_ablative_carapace(stratagem, **kwargs)
            if name_u == "BROODGUARD IMPULSE":
                return self._use_tyranids_broodguard_impulse(stratagem, **kwargs)
            if name_u == "RAPACIOUS HUNGER":
                return self._use_tyranids_rapacious_hunger(stratagem, **kwargs)
            if name_u == "RECLAIM BIOMASS":
                return self._use_tyranids_reclaim_biomass(stratagem, **kwargs)
            if name_u == "SECURE BIOMASS":
                return self._use_tyranids_secure_biomass(stratagem, **kwargs)
            if name_u == "TYRANNOFORMED":
                return self._use_tyranids_tyrannoformed(stratagem, **kwargs)
        if self._is_tyranids_unending_swarm_detachment():
            if name_u == "BOUNDING ADVANCE":
                return self._use_tyranids_bounding_advance(stratagem, **kwargs)
            if name_u == "SYNAPTIC GOADING":
                return self._use_tyranids_synaptic_goading(stratagem, **kwargs)
            if name_u == "UNENDING WAVES":
                return self._use_tyranids_unending_waves(stratagem, **kwargs)
            if name_u == "TEEMING MASSES":
                return self._use_tyranids_teeming_masses(stratagem, **kwargs)
            if name_u == "SWARMING MASSES":
                return self._use_tyranids_swarming_masses(stratagem, **kwargs)
            if name_u == "PRESERVATION IMPERATIVE":
                return self._use_tyranids_preservation_imperative(stratagem, **kwargs)
        if self._is_tyranids_subterranean_assault_detachment():
            if name_u == "ADAPTIVE OPTIMISATION":
                return self._use_tyranids_adaptive_optimisation(stratagem, **kwargs)
            if name_u == "REPLENISHING SWARMS":
                return self._use_tyranids_replenishing_swarms(stratagem, **kwargs)
            if name_u == "ENFILADING EMERGENCE":
                return self._use_tyranids_enfilading_emergence(stratagem, **kwargs)
            if name_u == "TUNNEL NETWORK":
                return self._use_tyranids_tunnel_network(stratagem, **kwargs)
            if name_u == "SWARMING ASSAULT":
                return self._use_tyranids_swarming_assault(stratagem, **kwargs)
            if name_u == "RETREAT BELOW":
                return self._use_tyranids_retreat_below(stratagem, **kwargs)
        if self._is_tyranids_invasion_fleet_detachment():
            if name_u == "RAPID REGENERATION":
                return self._use_tyranids_rapid_regeneration(stratagem, **kwargs)
            if name_u == "PREDATORY IMPERATIVE":
                return self._use_tyranids_predatory_imperative(stratagem, **kwargs)
            if name_u == "ENDLESS SWARM":
                return self._use_tyranids_endless_swarm(stratagem, **kwargs)
            if name_u == "ADRENAL SURGE":
                return self._use_tyranids_adrenal_surge(stratagem, **kwargs)
            if name_u == "DEATH FRENZY":
                return self._use_tyranids_death_frenzy(stratagem, **kwargs)
            if name_u == "OVERRUN":
                return self._use_tyranids_overrun(stratagem, **kwargs)
        if self._is_tyranids_vanguard_onslaught_detachment():
            if name_u == "SURPRISE ASSAULT":
                return self._use_tyranids_surprise_assault(stratagem, **kwargs)
            if name_u == "ASSASSIN BEASTS":
                return self._use_tyranids_assassin_beasts(stratagem, **kwargs)
            if name_u == "SEEDED BROODS":
                return self._use_tyranids_seeded_broods(stratagem, **kwargs)
            if name_u == "HYPERSENSORY SCILLIA":
                return self._use_tyranids_hypersensory_scillia(stratagem, **kwargs)
            if name_u == "UNSEEN LURKERS":
                return self._use_tyranids_unseen_lurkers(stratagem, **kwargs)
            if name_u == "INVISIBLE HUNTER":
                return self._use_tyranids_invisible_hunter(stratagem, **kwargs)
        if self._is_tyranids_warrior_bioform_onslaught_detachment():
            if name_u == "SYNAPTIC MICRONODES":
                return self._use_tyranids_synaptic_micronodes(stratagem, **kwargs)
            if name_u == "SYNAPTIC AMPLIFICATION":
                return self._use_tyranids_synaptic_amplification(stratagem, **kwargs)
            if name_u == "RESTORATIVE IMPULSE":
                return self._use_tyranids_restorative_impulse(stratagem, **kwargs)
            if name_u == "SYNAPTIC SHIELD":
                return self._use_tyranids_synaptic_shield(stratagem, **kwargs)
            if name_u == "PARASITIC PAYLOAD":
                return self._use_tyranids_parasitic_payload(stratagem, **kwargs)
            if name_u == "SPONTANEOUS HYPERCORROSION":
                return self._use_tyranids_spontaneous_hypercorrosion(stratagem, **kwargs)
        if self._is_tyranids_synaptic_nexus_detachment():
            if name_u == "REINFORCED HIVE NODE":
                return self._use_tyranids_reinforced_hive_node(stratagem, **kwargs)
            if name_u == "IRRESISTIBLE WILL":
                return self._use_tyranids_irresistible_will(stratagem, **kwargs)
            if name_u == "SYNAPTIC CHANNELLING":
                return self._use_tyranids_synaptic_channelling(stratagem, **kwargs)
            if name_u == "IMPERATIVE DOMINANCE":
                return self._use_tyranids_imperative_dominance(stratagem, **kwargs)
            if name_u == "THE SMOTHERING SHADOW":
                return self._use_tyranids_the_smothering_shadow(stratagem, **kwargs)
            if name_u == "OVERRIDE INSTINCTS":
                return self._use_tyranids_override_instincts(stratagem, **kwargs)
        if self._is_tyranids_crusher_stampede_detachment():
            if name_u == "CORROSIVE VISCERA":
                return self._use_tyranids_corrosive_viscera(stratagem, **kwargs)
            if name_u == "MASSIVE IMPACT":
                return self._use_tyranids_massive_impact(stratagem, **kwargs)
            if name_u == "RAMPAGING MONSTROSITIES":
                return self._use_tyranids_rampaging_monstrosities(stratagem, **kwargs)
            if name_u == "SAVAGE ROAR":
                return self._use_tyranids_savage_roar(stratagem, **kwargs)
            if name_u == "SWARM-GUIDED SALVOES":
                return self._use_tyranids_swarm_guided_salvoes(stratagem, **kwargs)
            if name_u == "UNTRAMMELLED FEROCITY":
                return self._use_tyranids_untrammelled_ferocity(stratagem, **kwargs)
        return None

    def _use_tyranids_ablative_carapace(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])

        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "ABLATIVE CARAPACE":
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        target_roots = self._tyr_resolve_units(target_unit)
        root = target_roots[0] if target_roots else None
        attacker_root = self._tyr_root(attacking_unit)
        if root is None:
            logger.error("ERROR: ABLATIVE CARAPACE: no target unit provided")
            return False
        if attacker_root is None:
            logger.error("ERROR: ABLATIVE CARAPACE: missing attacking unit context")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: ABLATIVE CARAPACE: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tyranids_unit(root) or not self._tyr_has_keyword(root, "HARVESTER"):
            logger.error("ERROR: ABLATIVE CARAPACE: target must be a friendly HARVESTER unit")
            return False
        if self._tyr_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: ABLATIVE CARAPACE: attacker must be an enemy unit")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: ABLATIVE CARAPACE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: ABLATIVE CARAPACE: not opponent's Shooting phase")
            return False

        eligible = candidates or self._tyr_ablative_carapace_candidates(attacking_unit=attacker_root, target_units=target_units)
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: ABLATIVE CARAPACE: target must be one of the selected HARVESTER targets")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            attacking_unit=attacker_root,
            phase_name=phase_label,
        ):
            logger.error("ERROR: ABLATIVE CARAPACE: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        within_controlled = bool(getattr(root, "_within_controlled_objective_range", lambda game_map=None: False)(game_map=getattr(self.game, "map", None)))
        fnp_value = 4 if within_controlled else 5
        phase_key_fn = getattr(self, "_phase_key_from_name", None)
        phase_key = phase_key_fn(phase_name) if callable(phase_key_fn) else ""
        if not phase_key:
            phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        entry = {
            "value": int(fnp_value),
            "attack_type": "any",
            "expires_phase": str(phase_key),
            "source": str(getattr(stratagem, "name", "") or "ABLATIVE CARAPACE"),
        }
        append_defensive_effect = getattr(self, "_append_defensive_effect", None)
        if callable(append_defensive_effect):
            append_defensive_effect(root, "defensive_fnp_overrides", entry)
        else:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            items = list(sr.get("defensive_fnp_overrides", []) or [])
            items.append(entry)
            sr["defensive_fnp_overrides"] = items
            root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        return True

    def _use_tyranids_broodguard_impulse(self, stratagem: Any, **kwargs) -> bool:
        destroyed_unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("destroyed_unit")
        destroyed_by_unit = kwargs.get("destroyed_by_unit") or kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])

        if destroyed_unit is None or destroyed_by_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BROODGUARD IMPULSE":
                    continue
                if destroyed_unit is None:
                    destroyed_unit = reaction.get("destroyed_unit") or reaction.get("target_unit") or reaction.get("unit")
                if destroyed_by_unit is None:
                    destroyed_by_unit = reaction.get("destroyed_by_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        destroyed_root = self._tyr_root(destroyed_unit)
        attacker_root = self._tyr_root(destroyed_by_unit)
        if destroyed_root is None:
            logger.error("ERROR: BROODGUARD IMPULSE: no destroyed HARVESTER provided")
            return False
        if attacker_root is None:
            logger.error("ERROR: BROODGUARD IMPULSE: missing destroying enemy unit")
            return False
        eligible = candidates or self._tyr_broodguard_impulse_candidates(
            destroyed_unit=destroyed_root,
            destroyed_by_unit=attacker_root,
        )
        if not eligible or not self._tyr_unit_in_candidates(destroyed_root, eligible):
            logger.error("ERROR: BROODGUARD IMPULSE: target must be the just-destroyed friendly HARVESTER")
            return False
        phase_label = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "Any phase").strip() or "Any phase"
        if not stratagem.can_use(self.player, self.game, phase_name=phase_label):
            logger.error("ERROR: BROODGUARD IMPULSE: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, enemy_unit=attacker_root):
            return False

        sr = getattr(attacker_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tyranids_broodguard_impulse_active"] = True
        sr["tyranids_broodguard_impulse_owner_id"] = str(getattr(self.player, "id", "") or "")
        sr["tyranids_broodguard_impulse_wound_bonus"] = 1
        sr["tyranids_broodguard_impulse_source"] = str(getattr(stratagem, "name", "") or "BROODGUARD IMPULSE")
        sr["tyranids_broodguard_impulse_destroyed_harvester_id"] = self._tyr_sort_key(destroyed_root)
        attacker_root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        return True

    def _use_tyranids_rapacious_hunger(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("destroyed_by_unit")
        destroyed_unit = kwargs.get("destroyed_unit")
        candidates = list(kwargs.get("candidates") or [])

        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "RAPACIOUS HUNGER":
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit") or reaction.get("destroyed_by_unit")
                if destroyed_unit is None:
                    destroyed_unit = reaction.get("destroyed_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        target_roots = self._tyr_resolve_units(target_unit)
        root = target_roots[0] if target_roots else None
        if root is None:
            logger.error("ERROR: RAPACIOUS HUNGER: no target unit provided")
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "fight phase":
            logger.error("ERROR: RAPACIOUS HUNGER: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: RAPACIOUS HUNGER: not your turn")
            return False
        eligible = candidates or self._tyr_rapacious_hunger_candidates(destroyed_unit=destroyed_unit, destroyed_by_unit=root)
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: RAPACIOUS HUNGER: target must be the TYRANIDS unit that just destroyed an enemy unit")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: RAPACIOUS HUNGER: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._tyr_detachment_mgr()
        options_fn = getattr(mgr, "assimilation_regeneration_options_for_unit", None) if mgr is not None else None
        apply_fn = getattr(mgr, "_apply_regeneration_option", None) if mgr is not None else None
        if not callable(options_fn) or not callable(apply_fn):
            return False
        options = list(options_fn(root, game=getattr(self, "game", None), player=self.player) or [])
        option_key = str(kwargs.get("option_key", "") or "").strip()
        if not option_key and len(options) == 1:
            option_key = str(options[0].get("option_key", "") or "").strip()
        if not option_key:
            logger.error("ERROR: RAPACIOUS HUNGER: regeneration option is required")
            return False
        selected_option = None
        for option in options:
            if str(option.get("option_key", "") or "") == option_key:
                selected_option = option
                break
        if selected_option is None:
            logger.error("ERROR: RAPACIOUS HUNGER: selected regeneration option is not eligible")
            return False
        heal_override = 3 if self._tyr_has_keyword(root, "HARVESTER") and str(selected_option.get("action", "") or "").strip().lower() == "heal" else None
        result = apply_fn(
            selected_option,
            game=getattr(self, "game", None),
            player=self.player,
            mark_source_used=False,
            heal_amount_override=heal_override,
            placement_source="rapacious_hunger",
        )
        if result is None:
            return False
        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        return True

    def _use_tyranids_reclaim_biomass(self, stratagem: Any, **kwargs) -> bool:
        source_unit = kwargs.get("unit") or kwargs.get("target_unit")
        destroyed_unit = kwargs.get("destroyed_unit")
        candidates = list(kwargs.get("candidates") or [])

        if source_unit is None or destroyed_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "RECLAIM BIOMASS":
                    continue
                if source_unit is None:
                    source_unit = reaction.get("target_unit") or reaction.get("unit")
                if destroyed_unit is None:
                    destroyed_unit = reaction.get("destroyed_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        source_roots = self._tyr_resolve_units(source_unit)
        root = source_roots[0] if source_roots else None
        destroyed_root = self._tyr_root(destroyed_unit)
        if root is None:
            logger.error("ERROR: RECLAIM BIOMASS: no HARVESTER source provided")
            return False
        if destroyed_root is None:
            logger.error("ERROR: RECLAIM BIOMASS: missing destroyed unit context")
            return False
        eligible = candidates or self._tyr_reclaim_biomass_candidates(destroyed_unit=destroyed_root)
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: RECLAIM BIOMASS: selected HARVESTER is not eligible")
            return False
        phase_label = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "Any phase").strip() or "Any phase"
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
            logger.error("ERROR: RECLAIM BIOMASS: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._tyr_detachment_mgr()
        options_fn = getattr(mgr, "assimilation_regeneration_options_for_harvester", None) if mgr is not None else None
        apply_fn = getattr(mgr, "_apply_regeneration_option", None) if mgr is not None else None
        if not callable(options_fn) or not callable(apply_fn):
            return False
        destroyed_id = self._tyr_sort_key(destroyed_root)
        options = list(
            options_fn(
                root,
                game=getattr(self, "game", None),
                player=self.player,
                exclude_target_ids=(destroyed_id,),
            )
            or []
        )
        option_key = str(kwargs.get("option_key", "") or "").strip()
        if not option_key and len(options) == 1:
            option_key = str(options[0].get("option_key", "") or "").strip()
        if not option_key:
            logger.error("ERROR: RECLAIM BIOMASS: regeneration option is required")
            return False
        selected_option = None
        for option in options:
            if str(option.get("option_key", "") or "") == option_key:
                selected_option = option
                break
        if selected_option is None:
            logger.error("ERROR: RECLAIM BIOMASS: selected regeneration option is not eligible")
            return False
        result = apply_fn(
            selected_option,
            game=getattr(self, "game", None),
            player=self.player,
            mark_source_used=False,
            placement_source="reclaim_biomass",
        )
        if result is None:
            return False
        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        return True

    def _use_tyranids_secure_biomass(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SECURE BIOMASS":
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        target_roots = self._tyr_resolve_units(target_unit)
        root = target_roots[0] if target_roots else None
        if root is None:
            logger.error("ERROR: SECURE BIOMASS: no target unit provided")
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "fight phase":
            logger.error("ERROR: SECURE BIOMASS: wrong phase")
            return False
        eligible = candidates or self._tyr_secure_biomass_candidates()
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: SECURE BIOMASS: selected unit is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: SECURE BIOMASS: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tyranids_secure_biomass_active"] = True
        sr["tyranids_secure_biomass_expires_phase"] = "FIGHT_PHASE"
        sr["tyranids_secure_biomass_turn"] = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        sr["tyranids_secure_biomass_owner"] = str(getattr(self.player, "id", "") or "")
        sr["tyranids_secure_biomass_source"] = str(getattr(stratagem, "name", "") or "SECURE BIOMASS")
        sr["tyranids_secure_biomass_crit_threshold"] = 5
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        return True

    def _use_tyranids_synaptic_micronodes(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        objective_candidates_by_unit = dict(kwargs.get("objective_candidates_by_unit") or {})
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: SYNAPTIC MICRONODES: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        if root is None:
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "movement phase":
            logger.error("ERROR: SYNAPTIC MICRONODES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SYNAPTIC MICRONODES: not your Movement phase")
            return False

        eligible, objective_map = self._tyr_warrior_bioform_synaptic_micronodes_candidates()
        if not eligible or not self._tyr_unit_in_candidates(root, candidates or eligible):
            logger.error("ERROR: SYNAPTIC MICRONODES: selected unit is not currently eligible")
            return False
        if not objective_candidates and objective_candidates_by_unit:
            objective_candidates = list(objective_candidates_by_unit.get(self._tyr_sort_key(root)) or [])
        if not objective_candidates:
            objective_candidates = list(objective_map.get(self._tyr_sort_key(root)) or self._tyr_objective_candidates_you_control(root))
        if not objective_candidates:
            logger.error("ERROR: SYNAPTIC MICRONODES: no eligible objective markers")
            return False
        if objective is None and len(objective_candidates) == 1:
            objective = objective_candidates[0]
        if isinstance(objective, str):
            for candidate in list(objective_candidates or []):
                objective_id = str(getattr(candidate, "id", "") or get_entity_id(candidate) or "")
                location = getattr(candidate, "location", None)
                location_id = str(getattr(location, "id", "") or get_entity_id(location) or "")
                if objective == objective_id or objective == location_id:
                    objective = candidate
                    break

        phase_label = "Movement phase"
        source_name = str(getattr(stratagem, "name", "") or "SYNAPTIC MICRONODES").strip() or "SYNAPTIC MICRONODES"
        if objective is None:
            request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
            if not callable(request_decision):
                logger.error("ERROR: SYNAPTIC MICRONODES: decision queue unavailable")
                return False
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest

            unit_id = self._tyr_sort_key(root)
            candidate_objective_ids = [
                str(getattr(candidate, "id", "") or get_entity_id(candidate) or "")
                for candidate in list(objective_candidates)
                if str(getattr(candidate, "id", "") or get_entity_id(candidate) or "")
            ]
            if not unit_id or not candidate_objective_ids:
                logger.error("ERROR: SYNAPTIC MICRONODES: source unit or objective candidates missing stable ids")
                return False
            if self._tyr_pending_choose_quarry_request(
                ability="tyranids_synaptic_micronodes_objective",
                source_unit_id=unit_id,
            ):
                logger.error("ERROR: SYNAPTIC MICRONODES: objective selection already queued")
                return False
            if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
                logger.error("ERROR: SYNAPTIC MICRONODES: cannot be used in current state")
                return False
            if not self._tyr_spend_cp(stratagem, target_unit=root):
                return False
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{source_name}: select one objective marker within range of {getattr(root, 'name', 'Unit')}.",
                player_id=getattr(self.player, "id", None),
                options=[
                    DecisionOption.create(
                        str(getattr(candidate, "name", "Objective") or "Objective"),
                        payload={
                            "unit_id": unit_id,
                            "source_unit_id": unit_id,
                            "objective_id": str(getattr(candidate, "id", "") or get_entity_id(candidate) or ""),
                        },
                    )
                    for candidate in list(objective_candidates)
                    if str(getattr(candidate, "id", "") or get_entity_id(candidate) or "")
                ],
                context={
                    "ability": "tyranids_synaptic_micronodes_objective",
                    "ability_name": source_name,
                    "phase": phase_label,
                    "phase_name": phase_label,
                    "unit_id": unit_id,
                    "source_unit_id": unit_id,
                    "candidate_objective_ids": list(candidate_objective_ids),
                    "optional": False,
                },
            )
            request_decision(request)
            self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info("INFO: SYNAPTIC MICRONODES: queued objective selection for %s.", getattr(root, "name", "Unit"))
            return True

        if objective not in list(objective_candidates or []):
            logger.error("ERROR: SYNAPTIC MICRONODES: objective selection is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
            logger.error("ERROR: SYNAPTIC MICRONODES: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        location = getattr(objective, "location", None) or objective
        set_sticky = getattr(location, "set_sticky_control", None)
        if not callable(set_sticky):
            logger.error("ERROR: SYNAPTIC MICRONODES: selected objective cannot become sticky")
            return False
        set_sticky(self.player, source="synaptic_micronodes")
        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SYNAPTIC MICRONODES: %s makes %s sticky.",
            getattr(root, "name", "Unit"),
            getattr(objective, "name", "Objective"),
        )
        return True

    def _use_tyranids_synaptic_amplification(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = candidates[0]
        if selected is None:
            logger.error("ERROR: SYNAPTIC AMPLIFICATION: no target unit provided")
            return False

        root = self._tyr_root(selected)
        if root is None:
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: SYNAPTIC AMPLIFICATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SYNAPTIC AMPLIFICATION: not your turn")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: SYNAPTIC AMPLIFICATION: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SYNAPTIC AMPLIFICATION: target must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: SYNAPTIC AMPLIFICATION: target must be a TYRANIDS unit")
            return False
        if self._tyr_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name=phase_name):
            logger.error("ERROR: SYNAPTIC AMPLIFICATION: target has already been selected this phase")
            return False

        eligible = candidates or self._tyr_warrior_bioform_synaptic_amplification_candidates(phase_name=phase_name)
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: SYNAPTIC AMPLIFICATION: selected unit is not currently eligible")
            return False

        mgr = self._tyr_detachment_mgr()
        is_warrior = bool(getattr(mgr, "_leader_beasts_unit_is_tyranid_warrior_datasheet", lambda *_a, **_k: False)(root))
        secondary_candidates = self._tyr_warrior_bioform_secondary_endless_candidates(root) if is_warrior else []
        secondary_roots = self._tyr_resolve_units(kwargs.get("secondary_unit"))
        secondary_root = secondary_roots[0] if secondary_roots else None
        if secondary_root is not None and not self._tyr_unit_in_candidates(secondary_root, secondary_candidates):
            logger.error("ERROR: SYNAPTIC AMPLIFICATION: selected secondary unit is not eligible")
            return False

        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        source_name = str(getattr(stratagem, "name", "") or "SYNAPTIC AMPLIFICATION").strip() or "SYNAPTIC AMPLIFICATION"
        request_decision = None
        unit_id = self._tyr_sort_key(root)
        candidate_unit_ids: list[str] = []
        if secondary_root is None and secondary_candidates:
            request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
            if not callable(request_decision):
                logger.error("ERROR: SYNAPTIC AMPLIFICATION: decision queue unavailable")
                return False
            candidate_unit_ids = [self._tyr_sort_key(candidate) for candidate in list(secondary_candidates) if self._tyr_sort_key(candidate)]
            if self._tyr_pending_choose_quarry_request(
                ability="tyranids_synaptic_amplification_secondary",
                source_unit_id=unit_id,
            ):
                logger.error("ERROR: SYNAPTIC AMPLIFICATION: secondary selection already queued")
                return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
            logger.error("ERROR: SYNAPTIC AMPLIFICATION: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False
        outcome = getattr(mgr, "activate_warrior_bioform_synaptic_amplification", lambda *_a, **_k: {"ok": False})(
            root,
            phase_name=phase_label,
            game=self.game,
            player=self.player,
            source=source_name,
            reroll_hit_ones=is_warrior,
            reroll_wound_ones=True,
        )
        if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
            logger.error("ERROR: SYNAPTIC AMPLIFICATION: failed to apply primary effect")
            return False

        if secondary_root is None and secondary_candidates:
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest

            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{source_name}: optionally select one ENDLESS MULTITUDE unit within 6\" of {getattr(root, 'name', 'Unit')}.",
                player_id=getattr(self.player, "id", None),
                options=[
                    DecisionOption.create("None", payload={"action": "skip", "source_unit_id": unit_id}),
                    *[
                        DecisionOption.create(
                            str(getattr(candidate, "name", "Unit") or "Unit"),
                            payload={
                                "source_unit_id": unit_id,
                                "unit_id": unit_id,
                                "target_unit_id": self._tyr_sort_key(candidate),
                            },
                        )
                        for candidate in list(secondary_candidates)
                        if self._tyr_sort_key(candidate)
                    ],
                ],
                context={
                    "ability": "tyranids_synaptic_amplification_secondary",
                    "ability_name": source_name,
                    "phase": phase_label,
                    "phase_name": phase_label,
                    "source_unit_id": unit_id,
                    "unit_id": unit_id,
                    "candidate_unit_ids": list(candidate_unit_ids),
                    "optional": True,
                },
            )
            request_decision(request)
            self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: SYNAPTIC AMPLIFICATION: %s gains re-roll Wound rolls of 1 and queued optional secondary selection.",
                getattr(root, "name", "Unit"),
            )
            return True

        if secondary_root is not None:
            secondary_outcome = getattr(mgr, "activate_warrior_bioform_synaptic_amplification", lambda *_a, **_k: {"ok": False})(
                secondary_root,
                phase_name=phase_label,
                game=self.game,
                player=self.player,
                source=source_name,
                reroll_hit_ones=False,
                reroll_wound_ones=True,
            )
            if not isinstance(secondary_outcome, dict) or not bool(secondary_outcome.get("ok", False)):
                logger.error("ERROR: SYNAPTIC AMPLIFICATION: failed to apply secondary effect")
                return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SYNAPTIC AMPLIFICATION: %s gains re-roll Wound rolls of 1%s.",
            getattr(root, "name", "Unit"),
            " and re-roll Hit rolls of 1" if is_warrior else "",
        )
        return True

    def _use_tyranids_restorative_impulse(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = candidates[0]
        if selected is None:
            logger.error("ERROR: RESTORATIVE IMPULSE: no target unit provided")
            return False

        root = self._tyr_root(selected)
        if root is None:
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "command phase":
            logger.error("ERROR: RESTORATIVE IMPULSE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: RESTORATIVE IMPULSE: not your Command phase")
            return False
        eligible = candidates or self._tyr_warrior_bioform_restorative_impulse_candidates()
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: RESTORATIVE IMPULSE: selected unit is not currently eligible")
            return False
        if not self._tyr_unit_has_destroyed_non_character_models(root):
            logger.error("ERROR: RESTORATIVE IMPULSE: selected unit has no destroyed non-CHARACTER models")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Command phase"):
            logger.error("ERROR: RESTORATIVE IMPULSE: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False
        returned = self._tyr_return_destroyed_models(root, amount=1)
        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RESTORATIVE IMPULSE: returned %d model(s) to %s.",
            int(returned),
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_synaptic_shield(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        if target_unit is None or not candidates or attacking_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SYNAPTIC SHIELD":
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: SYNAPTIC SHIELD: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        attacker_root = self._tyr_root(attacking_unit)
        if root is None or attacker_root is None:
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "shooting phase":
            logger.error("ERROR: SYNAPTIC SHIELD: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SYNAPTIC SHIELD: not the opponent's Shooting phase")
            return False
        if self._tyr_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: SYNAPTIC SHIELD: attacking unit must be an enemy unit")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: SYNAPTIC SHIELD: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SYNAPTIC SHIELD: target must be on the battlefield")
            return False

        eligible = candidates or self._tyr_warrior_bioform_synaptic_shield_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: SYNAPTIC SHIELD: selected unit is not currently eligible")
            return False

        secondary_roots = self._tyr_resolve_units(kwargs.get("secondary_unit"))
        secondary_root = secondary_roots[0] if secondary_roots else None
        secondary_candidates = self._tyr_warrior_bioform_secondary_endless_candidates(root)
        if secondary_root is not None and not self._tyr_unit_in_candidates(secondary_root, secondary_candidates):
            logger.error("ERROR: SYNAPTIC SHIELD: selected secondary unit is not eligible")
            return False

        source_name = str(getattr(stratagem, "name", "") or "SYNAPTIC SHIELD").strip() or "SYNAPTIC SHIELD"
        request_decision = None
        unit_id = self._tyr_sort_key(root)
        candidate_unit_ids: list[str] = []
        if secondary_root is None and secondary_candidates:
            request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
            candidate_unit_ids = [self._tyr_sort_key(candidate) for candidate in list(secondary_candidates) if self._tyr_sort_key(candidate)]
            if not callable(request_decision):
                logger.error("ERROR: SYNAPTIC SHIELD: decision queue unavailable")
                return False
            if self._tyr_pending_choose_quarry_request(
                ability="tyranids_synaptic_shield_secondary",
                source_unit_id=unit_id,
            ):
                logger.error("ERROR: SYNAPTIC SHIELD: secondary selection already queued")
                return False
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            enemy_unit=attacker_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: SYNAPTIC SHIELD: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        entry = {
            "value": 1,
            "attack_type": "ranged",
            "expires_phase": "SHOOTING_PHASE",
            "source": source_name,
            "requires_strength_gt_toughness": True,
        }
        append_defensive_effect = getattr(self, "_append_defensive_effect", None)
        if callable(append_defensive_effect):
            append_defensive_effect(root, "defensive_wound_mods", dict(entry))
        else:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            items = list(sr.get("defensive_wound_mods", []) or [])
            items.append(dict(entry))
            sr["defensive_wound_mods"] = items
            root.special_rules = sr

        if secondary_root is None and secondary_candidates:
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{source_name}: optionally select one ENDLESS MULTITUDE unit within 6\" of {getattr(root, 'name', 'Unit')}.",
                player_id=getattr(self.player, "id", None),
                options=[
                    DecisionOption.create("None", payload={"action": "skip", "source_unit_id": unit_id}),
                    *[
                        DecisionOption.create(
                            str(getattr(candidate, "name", "Unit") or "Unit"),
                            payload={
                                "source_unit_id": unit_id,
                                "unit_id": unit_id,
                                "target_unit_id": self._tyr_sort_key(candidate),
                            },
                        )
                        for candidate in list(secondary_candidates)
                        if self._tyr_sort_key(candidate)
                    ],
                ],
                context={
                    "ability": "tyranids_synaptic_shield_secondary",
                    "ability_name": source_name,
                    "phase": "Opponent Shooting phase",
                    "phase_name": "Shooting phase",
                    "source_unit_id": unit_id,
                    "unit_id": unit_id,
                    "candidate_unit_ids": list(candidate_unit_ids),
                    "optional": True,
                },
            )
            request_decision(request)
            self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: SYNAPTIC SHIELD: %s gains defensive protection and queued optional secondary selection.",
                getattr(root, "name", "Unit"),
            )
            return True

        if secondary_root is not None:
            if callable(append_defensive_effect):
                append_defensive_effect(secondary_root, "defensive_wound_mods", dict(entry))
            else:
                sr = getattr(secondary_root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                items = list(sr.get("defensive_wound_mods", []) or [])
                items.append(dict(entry))
                sr["defensive_wound_mods"] = items
                secondary_root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SYNAPTIC SHIELD: %s gains -1 to wound from stronger ranged attacks this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_parasitic_payload(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = candidates[0]
        if selected is None:
            logger.error("ERROR: PARASITIC PAYLOAD: no target unit provided")
            return False

        root = self._tyr_root(selected)
        if root is None:
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "shooting phase":
            logger.error("ERROR: PARASITIC PAYLOAD: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PARASITIC PAYLOAD: not your Shooting phase")
            return False
        eligible = candidates or self._tyr_warrior_bioform_parasitic_payload_candidates()
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: PARASITIC PAYLOAD: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: PARASITIC PAYLOAD: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "PARASITIC PAYLOAD").strip() or "PARASITIC PAYLOAD"
        for model in list(self._tyr_iter_unit_models(root) or []):
            model_id = str(get_entity_id(model) or "")
            for weapon_index, weapon_name in enumerate(self._tyr_model_weapon_names(model, attack_type="ranged")):
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if not callable(set_keywords):
                    continue
                set_keywords(
                    key=f"tyranids_parasitic_payload:{model_id}:{weapon_index}:{weapon_name}".lower(),
                    weapon_name=weapon_name,
                    keywords=["IGNORES COVER"],
                    source=source_name,
                    expires_phase="SHOOTING_PHASE",
                    attack_type="ranged",
                )

        mgr = self._tyr_detachment_mgr()
        outcome = getattr(mgr, "activate_warrior_bioform_parasitic_payload", lambda *_a, **_k: {"ok": False})(
            root,
            phase_name="Shooting phase",
            game=self.game,
            player=self.player,
            source=source_name,
        )
        if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
            logger.error("ERROR: PARASITIC PAYLOAD: failed to activate post-shoot effect")
            return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PARASITIC PAYLOAD: %s gains [IGNORES COVER] on ranged weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_spontaneous_hypercorrosion(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = candidates[0]
        if selected is None:
            logger.error("ERROR: SPONTANEOUS HYPERCORROSION: no target unit provided")
            return False

        root = self._tyr_root(selected)
        if root is None:
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: SPONTANEOUS HYPERCORROSION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SPONTANEOUS HYPERCORROSION: not your turn")
            return False
        eligible = candidates or self._tyr_warrior_bioform_spontaneous_hypercorrosion_candidates(phase_name=phase_name)
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: SPONTANEOUS HYPERCORROSION: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            phase_name="Shooting phase" if phase_name == "shooting phase" else "Fight phase",
        ):
            logger.error("ERROR: SPONTANEOUS HYPERCORROSION: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        expires_phase = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        source_name = str(getattr(stratagem, "name", "") or "SPONTANEOUS HYPERCORROSION").strip() or "SPONTANEOUS HYPERCORROSION"
        mgr = self._tyr_detachment_mgr()
        for model in list(self._tyr_iter_unit_models(root) or []):
            model_id = str(get_entity_id(model) or "")
            for weapon_index, weapon_name in enumerate(self._tyr_model_weapon_names(model, attack_type="ranged")):
                set_bonus = getattr(model, "set_temporary_weapon_bonus", None)
                if not callable(set_bonus):
                    continue
                set_bonus(
                    key=f"tyranids_spontaneous_hypercorrosion:ranged:{model_id}:{weapon_index}:{weapon_name}".lower(),
                    weapon_name=weapon_name,
                    strength_bonus=2,
                    source=source_name,
                    expires_phase=expires_phase,
                )
            member_unit = getattr(model, "parent_unit", None)
            grants_melee = bool(getattr(mgr, "_leader_beasts_unit_is_tyranid_warrior_datasheet", lambda *_a, **_k: False)(member_unit))
            if not grants_melee:
                grants_melee = bool(getattr(mgr, "_leader_beasts_unit_is_winged_tyranid_prime_datasheet", lambda *_a, **_k: False)(member_unit))
            if not grants_melee:
                continue
            for weapon_index, weapon_name in enumerate(self._tyr_model_weapon_names(model, attack_type="melee")):
                set_bonus = getattr(model, "set_temporary_weapon_bonus", None)
                if not callable(set_bonus):
                    continue
                set_bonus(
                    key=f"tyranids_spontaneous_hypercorrosion:melee:{model_id}:{weapon_index}:{weapon_name}".lower(),
                    weapon_name=weapon_name,
                    strength_bonus=1,
                    source=source_name,
                    expires_phase=expires_phase,
                )

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SPONTANEOUS HYPERCORROSION: %s gains +2 Strength on ranged weapons and eligible models gain +1 Strength on melee weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_tyrannoformed(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        objective_candidates_by_unit = dict(kwargs.get("objective_candidates_by_unit") or {})
        candidates = list(kwargs.get("candidates") or [])

        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "TYRANNOFORMED":
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if objective is None:
                    objective = reaction.get("objective") or reaction.get("objective_marker")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not objective_candidates:
                    objective_candidates = list(reaction.get("objective_candidates") or [])
                if not objective_candidates_by_unit:
                    objective_candidates_by_unit = dict(reaction.get("objective_candidates_by_unit") or {})
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        target_roots = self._tyr_resolve_units(target_unit)
        root = target_roots[0] if target_roots else None
        if root is None:
            logger.error("ERROR: TYRANNOFORMED: no HARVESTER target provided")
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "command phase":
            logger.error("ERROR: TYRANNOFORMED: wrong phase")
            return False
        available_candidates, objective_map = self._tyr_tyrannoformed_candidates()
        eligible = candidates or available_candidates
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: TYRANNOFORMED: selected HARVESTER is not eligible")
            return False
        if not objective_candidates and objective_candidates_by_unit:
            objective_candidates = list(objective_candidates_by_unit.get(self._tyr_sort_key(root)) or [])
        if not objective_candidates:
            objective_candidates = list(objective_map.get(self._tyr_sort_key(root)) or self._tyr_objective_candidates_you_control(root))
        if objective is None and len(objective_candidates) == 1:
            objective = objective_candidates[0]
        if isinstance(objective, str):
            for candidate in list(objective_candidates or []):
                objective_id = str(getattr(candidate, "id", "") or get_entity_id(candidate) or "")
                loc = getattr(candidate, "location", None)
                location_id = str(getattr(loc, "id", "") or get_entity_id(loc) or "")
                if objective == objective_id or objective == location_id:
                    objective = candidate
                    break
        if objective not in list(objective_candidates or []):
            logger.error("ERROR: TYRANNOFORMED: objective marker selection is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Command phase"):
            logger.error("ERROR: TYRANNOFORMED: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        loc = getattr(objective, "location", None) or objective
        set_sticky = getattr(loc, "set_sticky_control", None)
        if not callable(set_sticky):
            return False
        set_sticky(self.player, source="tyrannoformed")
        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        return True

    def _use_tyranids_bounding_advance(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: BOUNDING ADVANCE: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        if root is None:
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: BOUNDING ADVANCE: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: BOUNDING ADVANCE: target must be on the battlefield and targetable")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: BOUNDING ADVANCE: target must be a TYRANIDS unit")
            return False
        if not self._tyr_is_endless_multitude_unit(root):
            logger.error("ERROR: BOUNDING ADVANCE: target must be an ENDLESS MULTITUDE unit")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "movement phase":
            logger.error("ERROR: BOUNDING ADVANCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: BOUNDING ADVANCE: not your Movement phase")
            return False

        eligible = candidates or self._tyr_unending_swarm_bounding_advance_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: BOUNDING ADVANCE: target is not currently eligible")
            return False
        if self._tyr_selected_to_move_this_phase(root):
            logger.error("ERROR: BOUNDING ADVANCE: target has already been selected to move this phase")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: BOUNDING ADVANCE: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "BOUNDING ADVANCE").strip() or "BOUNDING ADVANCE"
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        effect_tag = "stratagem:tyranids_bounding_advance"
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        effects = [
            entry
            for entry in list(sr.get("advance_no_roll_effects", []) or [])
            if not (isinstance(entry, dict) and str(entry.get("tag", "") or "") == effect_tag)
        ]
        effects.append(
            {
                "distance": 6,
                "source": source_name,
                "tag": effect_tag,
                "expires_phase": "MOVEMENT_PHASE",
            }
        )
        sr["advance_no_roll_effects"] = effects
        sr["tyranids_bounding_advance_active"] = True
        sr["tyranids_bounding_advance_distance"] = 6
        sr["tyranids_bounding_advance_expires_phase"] = "MOVEMENT_PHASE"
        sr["tyranids_bounding_advance_turn_owner"] = owner_id
        sr["tyranids_bounding_advance_turn"] = int(current_turn)
        sr["tyranids_bounding_advance_source"] = source_name
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BOUNDING ADVANCE: %s adds 6\" to Move when it Advances this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_synaptic_goading(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SYNAPTIC GOADING":
                    continue
                target_unit = target_unit or reaction.get("target_unit") or reaction.get("unit")
                attacking_unit = attacking_unit or reaction.get("attacking_unit") or reaction.get("attacker_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: SYNAPTIC GOADING: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        if root is None:
            return False
        if not self._is_tyranids_unending_swarm_detachment():
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: SYNAPTIC GOADING: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SYNAPTIC GOADING: target unit must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: SYNAPTIC GOADING: target must be a TYRANIDS unit")
            return False
        if not self._tyr_is_endless_multitude_unit(root):
            logger.error("ERROR: SYNAPTIC GOADING: target must be an ENDLESS MULTITUDE unit")
            return False
        if not self._tyr_unit_in_synapse_range(root):
            logger.error("ERROR: SYNAPTIC GOADING: target must be within Synapse Range")
            return False
        has_insurmountable_odds = getattr(root, "has_insurmountable_odds", None)
        if callable(has_insurmountable_odds) and not bool(has_insurmountable_odds()):
            logger.error("ERROR: SYNAPTIC GOADING: target must be about to make a Surge move")
            return False
        can_horde_move = getattr(root, "can_horde_move", None)
        if callable(can_horde_move) and not bool(can_horde_move(game=self.game, game_map=getattr(self.game, "map", None))):
            logger.error("ERROR: SYNAPTIC GOADING: target is not currently eligible to make a Surge move")
            return False
        eligible = candidates or self._tyr_unending_swarm_synaptic_goading_candidates()
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: SYNAPTIC GOADING: target must be one of your units that is about to make a Surge move")
            return False
        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip() or "Shooting phase"
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_name):
            logger.error("ERROR: SYNAPTIC GOADING: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=self._tyr_root(attacking_unit)):
            return False

        activate = getattr(root, "activate_tyranids_synaptic_goading_horde_move", None)
        if callable(activate):
            activate(game=self.game, source=str(getattr(stratagem, "name", "") or "SYNAPTIC GOADING"))
        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SYNAPTIC GOADING: %s can re-roll its Surge move distance and move toward the closest objective marker.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_unending_waves(self, stratagem: Any, **kwargs) -> bool:
        destroyed_unit = kwargs.get("destroyed_unit") or kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if destroyed_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "UNENDING WAVES":
                    continue
                destroyed_unit = destroyed_unit or reaction.get("destroyed_unit") or reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if destroyed_unit is None and len(candidates) == 1:
            destroyed_unit = candidates[0]
        root = self._tyr_root(destroyed_unit)
        if root is None:
            logger.error("ERROR: UNENDING WAVES: no destroyed unit provided")
            return False
        if not self._is_tyranids_unending_swarm_detachment():
            return False
        if bool(getattr(self, "_tyr_unending_waves_used", False)):
            logger.error("ERROR: UNENDING WAVES: already used this battle")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: UNENDING WAVES: target must be a friendly unit")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: UNENDING WAVES: target must be a TYRANIDS unit")
            return False
        if not self._tyr_is_endless_multitude_unit(root):
            logger.error("ERROR: UNENDING WAVES: target must be an ENDLESS MULTITUDE unit")
            return False
        if self._tyr_is_alive(root):
            logger.error("ERROR: UNENDING WAVES: target unit must have been just destroyed")
            return False
        eligible = candidates or self._tyr_unending_waves_candidates(destroyed_unit=root)
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: UNENDING WAVES: target unit is not currently eligible")
            return False
        replacement = self._tyr_clone_unending_waves_unit(root)
        if replacement is None:
            logger.error("ERROR: UNENDING WAVES: failed to create replacement unit")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False
        if not self._tyr_prepare_unending_waves_unit(replacement):
            logger.error("ERROR: UNENDING WAVES: failed to place replacement unit into Strategic Reserves")
            return False
        self._tyr_unending_waves_used = True
        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNENDING WAVES: added a new %s unit to Strategic Reserves at Starting Strength.",
            getattr(replacement, "name", "Unit"),
        )
        return True

    def _use_tyranids_teeming_masses(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])
        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "TEEMING MASSES":
                    continue
                target_unit = target_unit or reaction.get("target_unit") or reaction.get("unit")
                attacking_unit = attacking_unit or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        root = self._tyr_root(target_unit)
        attacker_root = self._tyr_root(attacking_unit)
        if root is None:
            logger.error("ERROR: TEEMING MASSES: no target unit provided")
            return False
        if attacker_root is None:
            logger.error("ERROR: TEEMING MASSES: missing attacking unit context")
            return False
        if not self._is_tyranids_unending_swarm_detachment():
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: TEEMING MASSES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: TEEMING MASSES: not your opponent's phase")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: TEEMING MASSES: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: TEEMING MASSES: target unit must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: TEEMING MASSES: target must be a TYRANIDS unit")
            return False
        if not self._tyr_is_endless_multitude_unit(root):
            logger.error("ERROR: TEEMING MASSES: target must be an ENDLESS MULTITUDE unit")
            return False
        if self._tyr_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: TEEMING MASSES: attacking unit must be enemy")
            return False
        eligible = candidates or self._tyr_unending_swarm_targeted_endless_multitude_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: TEEMING MASSES: target must be one of the attacking unit's selected targets")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            attacking_unit=attacker_root,
            phase_name=phase_label,
        ):
            logger.error("ERROR: TEEMING MASSES: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        attack_type = "ranged" if phase_name == "shooting phase" else "melee"
        expires_phase = "SHOOTING_PHASE" if attack_type == "ranged" else "FIGHT_PHASE"
        source_name = str(getattr(stratagem, "name", "") or "TEEMING MASSES").strip() or "TEEMING MASSES"
        attacker_key_fn = getattr(self, "_attacker_unit_key", None)
        attacker_key = attacker_key_fn(attacker_root) if callable(attacker_key_fn) else self._tyr_sort_key(attacker_root)
        entry = {
            "value": 1,
            "attack_type": attack_type,
            "attacker_key": attacker_key,
            "expires_phase": expires_phase,
            "source": source_name,
        }
        append_defensive_effect = getattr(self, "_append_defensive_effect", None)
        if callable(append_defensive_effect):
            append_defensive_effect(root, "defensive_hit_mods", dict(entry))
        else:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            hit_mods = list(sr.get("defensive_hit_mods", []) or [])
            hit_mods.append(dict(entry))
            sr["defensive_hit_mods"] = hit_mods
            root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TEEMING MASSES: %s suffers -1 to hit against %s this phase.",
            getattr(attacker_root, "name", "Enemy"),
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_swarming_masses(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: SWARMING MASSES: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        if root is None:
            return False
        if not self._is_tyranids_unending_swarm_detachment():
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: SWARMING MASSES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SWARMING MASSES: not your Shooting/Fight phase")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: SWARMING MASSES: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SWARMING MASSES: target unit must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: SWARMING MASSES: target must be a TYRANIDS unit")
            return False
        if not self._tyr_is_endless_multitude_unit(root):
            logger.error("ERROR: SWARMING MASSES: target must be an ENDLESS MULTITUDE unit")
            return False
        eligible = candidates or self._tyr_unending_swarm_swarming_masses_candidates(phase_name=phase_name)
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: SWARMING MASSES: target must be eligible and not yet selected this phase")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
            logger.error("ERROR: SWARMING MASSES: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        source_name = str(getattr(stratagem, "name", "") or "SWARMING MASSES").strip() or "SWARMING MASSES"
        attack_type = "ranged" if phase_name == "shooting phase" else "melee"
        if attack_type == "ranged":
            current_val = int(sr.get("bearer_unit_sustained_hits_value_ranged", 0) or 0)
            added = current_val < 1
            if added:
                sr["bearer_unit_sustained_hits_value_ranged"] = 1
            sr["tyranids_swarming_masses_added_sustained_ranged"] = bool(added)
            sr["tyranids_swarming_masses_prev_sustained_ranged"] = current_val
        else:
            current_val = int(sr.get("bearer_unit_sustained_hits_value_melee", 0) or 0)
            added = current_val < 1
            if added:
                sr["bearer_unit_sustained_hits_value_melee"] = 1
            sr["tyranids_swarming_masses_added_sustained_melee"] = bool(added)
            sr["tyranids_swarming_masses_prev_sustained_melee"] = current_val
        sr["tyranids_swarming_masses_active"] = True
        sr["tyranids_swarming_masses_attack_type"] = attack_type
        sr["tyranids_swarming_masses_expires_phase"] = "SHOOTING_PHASE" if attack_type == "ranged" else "FIGHT_PHASE"
        sr["tyranids_swarming_masses_turn_owner"] = owner_id
        sr["tyranids_swarming_masses_turn"] = current_turn
        sr["tyranids_swarming_masses_source"] = source_name
        sr["tyranids_swarming_masses_crit_threshold"] = 5
        sr["tyranids_swarming_masses_crit_model_threshold"] = 15
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SWARMING MASSES: %s gains Sustained Hits 1 and critical hits on 5+ while it has 15+ models this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_preservation_imperative(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])
        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "PRESERVATION IMPERATIVE":
                    continue
                target_unit = target_unit or reaction.get("target_unit") or reaction.get("unit")
                attacking_unit = attacking_unit or reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        root = self._tyr_root(target_unit)
        attacker_root = self._tyr_root(attacking_unit)
        if root is None:
            logger.error("ERROR: PRESERVATION IMPERATIVE: no target unit provided")
            return False
        if attacker_root is None:
            logger.error("ERROR: PRESERVATION IMPERATIVE: missing attacking unit context")
            return False
        if not self._is_tyranids_unending_swarm_detachment():
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "shooting phase":
            logger.error("ERROR: PRESERVATION IMPERATIVE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: PRESERVATION IMPERATIVE: not your opponent's Shooting phase")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: PRESERVATION IMPERATIVE: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: PRESERVATION IMPERATIVE: target unit must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: PRESERVATION IMPERATIVE: target must be a TYRANIDS unit")
            return False
        if not self._tyr_is_endless_multitude_unit(root):
            logger.error("ERROR: PRESERVATION IMPERATIVE: target must be an ENDLESS MULTITUDE unit")
            return False
        if self._tyr_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: PRESERVATION IMPERATIVE: attacking unit must be enemy")
            return False
        eligible = candidates or self._tyr_unending_swarm_targeted_endless_multitude_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: PRESERVATION IMPERATIVE: target must be one of the attacking unit's selected targets")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            attacking_unit=attacker_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: PRESERVATION IMPERATIVE: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tyranids_preservation_imperative_active"] = True
        sr["tyranids_preservation_imperative_expires_phase"] = "SHOOTING_PHASE"
        sr["tyranids_preservation_imperative_turn_owner"] = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        sr["tyranids_preservation_imperative_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["tyranids_preservation_imperative_source"] = str(
            getattr(stratagem, "name", "") or "PRESERVATION IMPERATIVE"
        ).strip() or "PRESERVATION IMPERATIVE"
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PRESERVATION IMPERATIVE: %s is treated as containing fewer than five models for Blast this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_adaptive_optimisation(self, stratagem: Any, **kwargs) -> bool:
        target = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target is None and len(candidates) == 1:
            target = candidates[0]
        if target is None:
            logger.error("ERROR: ADAPTIVE OPTIMISATION: no target unit provided")
            return False

        root = self._tyr_root(target)
        if root is None:
            return False
        if not self._is_tyranids_subterranean_assault_detachment():
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: ADAPTIVE OPTIMISATION: target unit is not yours")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: ADAPTIVE OPTIMISATION: target must be a TYRANIDS unit")
            return False

        eligible = candidates or self._tyr_adaptive_optimisation_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: ADAPTIVE OPTIMISATION: target must be a Mawloc or Trygon unit from your army")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "command phase":
            logger.error("ERROR: ADAPTIVE OPTIMISATION: wrong phase")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Command phase"):
            logger.error("ERROR: ADAPTIVE OPTIMISATION: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._tyr_detachment_mgr()
        unit_keyword_added = False
        if not self._tyr_has_keyword(root, "SYNAPSE"):
            if mgr is not None and callable(getattr(mgr, "_add_keyword_once", None)):
                mgr._add_keyword_once(root, "Synapse")
            else:
                keywords = list(getattr(root, "keywords", []) or [])
                keywords.append("Synapse")
                root.keywords = keywords
            unit_keyword_added = True

        added_model_ids: list[str] = []
        for model in self._tyr_iter_unit_models(root):
            if not self._tyr_model_is_alive(model):
                continue
            if self._tyr_has_keyword(model, "SYNAPSE"):
                continue
            if mgr is not None and callable(getattr(mgr, "_add_keyword_once", None)):
                mgr._add_keyword_once(model, "Synapse")
            else:
                keywords = list(getattr(model, "keywords", []) or [])
                keywords.append("Synapse")
                model.keywords = keywords
            model_id = str(get_entity_id(model) or "")
            if model_id:
                added_model_ids.append(model_id)

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tyranids_subterranean_adaptive_optimisation_active"] = True
        sr["tyranids_subterranean_adaptive_optimisation_expires_phase"] = "COMMAND_PHASE"
        sr["tyranids_subterranean_adaptive_optimisation_source"] = (
            str(getattr(stratagem, "name", "") or "ADAPTIVE OPTIMISATION").strip() or "ADAPTIVE OPTIMISATION"
        )
        if unit_keyword_added:
            sr["tyranids_subterranean_adaptive_optimisation_added_unit_keyword"] = True
        if added_model_ids:
            sr["tyranids_subterranean_adaptive_optimisation_added_model_ids"] = added_model_ids
        owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id:
            sr["tyranids_subterranean_adaptive_optimisation_turn_owner"] = owner_id
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if turn:
            sr["tyranids_subterranean_adaptive_optimisation_turn"] = turn
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ADAPTIVE OPTIMISATION: %s gains the SYNAPSE keyword until the start of your next Command phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_replenishing_swarms(self, stratagem: Any, **kwargs) -> bool:
        target = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target is None and len(candidates) == 1:
            target = candidates[0]
        if target is None:
            logger.error("ERROR: REPLENISHING SWARMS: no target unit provided")
            return False

        root = self._tyr_root(target)
        if root is None:
            return False
        if not self._is_tyranids_subterranean_assault_detachment():
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "movement phase":
            logger.error("ERROR: REPLENISHING SWARMS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: REPLENISHING SWARMS: not your turn")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: REPLENISHING SWARMS: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: REPLENISHING SWARMS: target must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: REPLENISHING SWARMS: target must be a TYRANIDS unit")
            return False

        eligible = candidates or self._tyr_replenishing_swarms_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: REPLENISHING SWARMS: target must be wholly within 9\" of a Tunnel Marker")
            return False

        action_key = str(kwargs.get("action") or kwargs.get("mode") or "").strip().lower()
        damaged_models = self._tyr_damaged_models(root)
        returnable_count = 0
        members: list[Any] = [root]
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            for member in list(get_members() or []):
                if member is None or member is root:
                    continue
                members.append(member)
        for member in list(members):
            destroyed = list(getattr(member, "models_lost", []) or [])
            returnable_count += sum(
                1
                for model in list(destroyed or [])
                if self._tyr_model_wounds_characteristic(model) == 1
            )

        if not action_key:
            if damaged_models and returnable_count:
                logger.error("ERROR: REPLENISHING SWARMS: action must be selected when both heal and return are available")
                return False
            if damaged_models:
                action_key = "heal"
            elif returnable_count:
                action_key = "return"
        if action_key not in {"heal", "return"}:
            logger.error("ERROR: REPLENISHING SWARMS: action must be 'heal' or 'return'")
            return False
        if action_key == "heal" and not damaged_models:
            logger.error("ERROR: REPLENISHING SWARMS: target unit has no damaged model to heal")
            return False
        if action_key == "return" and returnable_count <= 0:
            logger.error("ERROR: REPLENISHING SWARMS: target unit has no destroyed Wounds 1 models to return")
            return False

        target_model = kwargs.get("target_model") or kwargs.get("model")
        if isinstance(target_model, str):
            target_model = next(
                (model for model in damaged_models if str(get_entity_id(model) or "") == str(target_model or "")),
                None,
            )
        if action_key == "heal":
            if target_model is None and len(damaged_models) == 1:
                target_model = damaged_models[0]
            if target_model is None:
                logger.error("ERROR: REPLENISHING SWARMS: a damaged model must be selected for heal mode")
                return False
            if all(model is not target_model for model in damaged_models):
                logger.error("ERROR: REPLENISHING SWARMS: selected model is not an eligible damaged model")
                return False

        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Movement phase"):
            logger.error("ERROR: REPLENISHING SWARMS: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        roll = max(0, dice_module.get_roll("D3")) + 1
        if action_key == "heal":
            base_wounds = self._tyr_model_wounds_characteristic(target_model)
            before = int(getattr(target_model, "wounds", 0) or 0)
            heal_fn = getattr(target_model, "heal", None)
            if callable(heal_fn):
                heal_fn(int(roll))
            else:
                target_model.wounds = int(min(base_wounds, before + int(roll)))
                check_profile = getattr(target_model, "_check_damaged_profile", None)
                if callable(check_profile):
                    check_profile()
            healed = max(0, int(getattr(target_model, "wounds", 0) or 0) - before)
            self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: REPLENISHING SWARMS: %s regains %d wound(s) on %s.",
                getattr(root, "name", "Unit"),
                int(healed),
                getattr(target_model, "name", "Model"),
            )
            return True

        returned = self._tyr_return_destroyed_models_with_wounds_characteristic(
            root,
            amount=int(roll),
            wounds_characteristic=1,
        )
        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REPLENISHING SWARMS: %s returns %d destroyed model(s).",
            getattr(root, "name", "Unit"),
            int(returned),
        )
        return True

    def _use_tyranids_enfilading_emergence(self, stratagem: Any, **kwargs) -> bool:
        target = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target is None and len(candidates) == 1:
            target = candidates[0]
        if target is None:
            logger.error("ERROR: ENFILADING EMERGENCE: no target unit provided")
            return False

        root = self._tyr_root(target)
        if root is None:
            return False
        if not self._is_tyranids_subterranean_assault_detachment():
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "movement phase":
            logger.error("ERROR: ENFILADING EMERGENCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: ENFILADING EMERGENCE: not your turn")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: ENFILADING EMERGENCE: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: ENFILADING EMERGENCE: target must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: ENFILADING EMERGENCE: target must be a TYRANIDS unit")
            return False
        if not self._tyr_unit_arrived_from_reserves_this_turn(root):
            logger.error("ERROR: ENFILADING EMERGENCE: target must have been set up as Reinforcements this turn")
            return False

        eligible = candidates or self._tyr_enfilading_emergence_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: ENFILADING EMERGENCE: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Movement phase"):
            logger.error("ERROR: ENFILADING EMERGENCE: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "ENFILADING EMERGENCE").strip() or "ENFILADING EMERGENCE"
        for model_index, model in enumerate(self._tyr_iter_unit_models(root)):
            if not self._tyr_model_is_alive(model):
                continue
            model_id = str(get_entity_id(model) or model_index)
            for wargear_index, wargear in enumerate(list(getattr(model, "wargear", []) or [])):
                if wargear is None:
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if callable(set_keywords):
                    set_keywords(
                        key=f"tyranids_enfilading_emergence:{model_id}:{wargear_index}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        keywords=["SUSTAINED HITS 1", "IGNORES COVER"],
                        source=source_name,
                        expires_phase="FIGHT_PHASE",
                        attack_type="any",
                    )

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tyranids_enfilading_emergence_active"] = True
        sr["tyranids_enfilading_emergence_expires_phase"] = "FIGHT_PHASE"
        sr["tyranids_enfilading_emergence_source"] = source_name
        owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id:
            sr["tyranids_enfilading_emergence_turn_owner"] = owner_id
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if turn:
            sr["tyranids_enfilading_emergence_turn"] = turn
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ENFILADING EMERGENCE: %s gains [SUSTAINED HITS 1] and [IGNORES COVER] on its weapons until end of Fight phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_tunnel_network(self, stratagem: Any, **kwargs) -> bool:
        target = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target is None and len(candidates) == 1:
            target = candidates[0]
        if target is None:
            logger.error("ERROR: TUNNEL NETWORK: no target unit provided")
            return False

        root = self._tyr_root(target)
        if root is None:
            return False
        if not self._is_tyranids_subterranean_assault_detachment():
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "movement phase":
            logger.error("ERROR: TUNNEL NETWORK: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: TUNNEL NETWORK: not your turn")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: TUNNEL NETWORK: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: TUNNEL NETWORK: target must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: TUNNEL NETWORK: target must be a TYRANIDS unit")
            return False
        if self._tyr_unit_in_engagement_range(root):
            logger.error("ERROR: TUNNEL NETWORK: target must not be within Engagement Range")
            return False

        eligible = candidates or self._tyr_tunnel_network_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: TUNNEL NETWORK: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Movement phase"):
            logger.error("ERROR: TUNNEL NETWORK: cannot be used in current state")
            return False

        mgr = self._tyr_detachment_mgr()
        get_markers = getattr(mgr, "get_active_tunnel_markers", None) if mgr is not None else None
        active_marker_ids = [
            str(getattr(marker, "marker_id", "") or "").strip()
            for marker in list(get_markers() or [])
            if str(getattr(marker, "marker_id", "") or "").strip()
        ] if callable(get_markers) else []
        current_marker_ids = self._tyr_current_tunnel_marker_ids(root)
        destination_marker_ids = [
            marker_id
            for marker_id in list(active_marker_ids)
            if any(source_id != marker_id for source_id in list(current_marker_ids))
        ]
        if not current_marker_ids or not destination_marker_ids:
            logger.error("ERROR: TUNNEL NETWORK: target must be wholly within range of a Tunnel Marker and have another marker to move to")
            return False

        game = getattr(self, "game", None)
        request_decision = getattr(game, "request_decision", None)
        if not callable(request_decision):
            logger.error("ERROR: TUNNEL NETWORK: move decision queue unavailable")
            return False

        from ..engine.decision_kinds import DECISION_MOVE_UNIT
        from ..engine.decisions import DecisionOption, DecisionRequest

        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            logger.error("ERROR: TUNNEL NETWORK: target unit must have a stable id")
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != str(DECISION_MOVE_UNIT):
                    continue
                req_ctx = dict(getattr(req, "context", {}) or {})
                if str(req_ctx.get("placement_kind", "") or "") != "subterranean_tunnel_network":
                    continue
                if str(req_ctx.get("unit_id", "") or "") != unit_id:
                    continue
                logger.error("ERROR: TUNNEL NETWORK: placement decision already queued for target unit")
                return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        allowed_model_ids = [
            str(get_entity_id(model) or "")
            for model in self._tyr_iter_unit_models(root)
            if str(get_entity_id(model) or "")
        ]
        if not allowed_model_ids:
            logger.error("ERROR: TUNNEL NETWORK: target unit has no models to place")
            return False
        game_map = getattr(game, "map", None)
        if game_map is not None and isinstance(getattr(game_map, "units", None), list) and root in list(game_map.units or []):
            game_map.units.remove(root)
        root.deployed = False
        root.embarked_in = None
        for model in self._tyr_iter_unit_models(root):
            model._pending_placement = True
            model._pending_placement_source = str(getattr(stratagem, "name", "") or "TUNNEL NETWORK")
        request = DecisionRequest.create(
            DECISION_MOVE_UNIT,
            f"{getattr(stratagem, 'name', 'TUNNEL NETWORK')}: set up {getattr(root, 'name', 'Unit')} wholly within 9\" of another Tunnel Marker",
            player_id=getattr(self.player, "id", None),
            options=[
                DecisionOption.create(
                    "Confirm",
                    payload={"unit_id": unit_id, "movement_type": "deploy", "action": "confirm"},
                )
            ],
            context={
                "unit_id": unit_id,
                "movement_type": "deploy",
                "placement_kind": "subterranean_tunnel_network",
                "allowed_model_ids": allowed_model_ids,
                "allow_skip": False,
                "ability_name": str(getattr(stratagem, "name", "TUNNEL NETWORK") or "TUNNEL NETWORK"),
                "tunnel_marker_allowed_ids": destination_marker_ids,
                "reserves_arrival_require_not_engagement": True,
            },
        )
        request_decision(request)

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TUNNEL NETWORK: %s must be set up again wholly within 9\" of another Tunnel Marker.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_swarming_assault(self, stratagem: Any, **kwargs) -> bool:
        target = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target is None and len(candidates) == 1:
            target = candidates[0]
        if target is None:
            logger.error("ERROR: SWARMING ASSAULT: no target unit provided")
            return False

        root = self._tyr_root(target)
        if root is None:
            return False
        if not self._is_tyranids_subterranean_assault_detachment():
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "charge phase":
            logger.error("ERROR: SWARMING ASSAULT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SWARMING ASSAULT: not your turn")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: SWARMING ASSAULT: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SWARMING ASSAULT: target must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: SWARMING ASSAULT: target must be a TYRANIDS unit")
            return False
        if not self._tyr_is_monster_unit(root):
            logger.error("ERROR: SWARMING ASSAULT: target must be a TYRANIDS MONSTER unit")
            return False
        if not self._tyr_unit_arrived_from_reserves_this_turn(root):
            logger.error("ERROR: SWARMING ASSAULT: target must have been set up as Reinforcements this turn")
            return False

        eligible = candidates or self._tyr_swarming_assault_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: SWARMING ASSAULT: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Charge phase"):
            logger.error("ERROR: SWARMING ASSAULT: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tyranids_subterranean_swarming_assault_active"] = True
        sr["tyranids_subterranean_swarming_assault_expires_phase"] = "CHARGE_PHASE"
        sr["tyranids_subterranean_swarming_assault_source"] = (
            str(getattr(stratagem, "name", "") or "SWARMING ASSAULT").strip() or "SWARMING ASSAULT"
        )
        owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id:
            sr["tyranids_subterranean_swarming_assault_turn_owner"] = owner_id
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if turn:
            sr["tyranids_subterranean_swarming_assault_turn"] = turn
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SWARMING ASSAULT: friendly TYRANIDS units within 6\" of %s can re-roll Charge rolls this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_retreat_below(self, stratagem: Any, **kwargs) -> bool:
        selected = (
            kwargs.get("units")
            or kwargs.get("target_units")
            or kwargs.get("selected_units")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        candidates = list(kwargs.get("candidates") or [])
        burrower_candidates = list(kwargs.get("burrower_candidates") or [])
        max_units = int(kwargs.get("max_units", 2) or 2)
        if selected is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if selected is None:
                    selected = (
                        reaction.get("units")
                        or reaction.get("target_units")
                        or reaction.get("selected_units")
                        or reaction.get("unit")
                        or reaction.get("target_unit")
                    )
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not burrower_candidates:
                    burrower_candidates = list(reaction.get("burrower_candidates") or [])
                if "max_units" not in kwargs:
                    max_units = int(reaction.get("max_units", max_units) or max_units)
                break

        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots:
            logger.error("ERROR: RETREAT BELOW: no target units provided")
            return False
        if len(selected_roots) > max(1, int(max_units)):
            logger.error("ERROR: RETREAT BELOW: selected too many units")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: RETREAT BELOW: cannot select more than two units")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "fight phase":
            logger.error("ERROR: RETREAT BELOW: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: RETREAT BELOW: not opponent's Fight phase")
            return False

        eligible = candidates or self._tyr_retreat_below_candidates()
        valid_burrowers = self._tyr_resolve_units(burrower_candidates) or [
            unit for unit in eligible if self._tyr_is_burrower_unit(unit)
        ]
        for root in list(selected_roots):
            if not self._tyr_unit_in_candidates(root, eligible):
                logger.error("ERROR: RETREAT BELOW: selected unit is not currently eligible")
                return False
            if not self._tyr_owned_by_player(root, self.player):
                logger.error("ERROR: RETREAT BELOW: selected unit is not yours")
                return False
            if not self._tyr_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: RETREAT BELOW: selected unit must be on the battlefield and targetable")
                return False
            if not self._is_tyranids_unit(root):
                logger.error("ERROR: RETREAT BELOW: selected unit must be a TYRANIDS unit")
                return False
            if self._tyr_unit_in_engagement_range(root):
                logger.error("ERROR: RETREAT BELOW: selected unit must not be within Engagement Range")
                return False
        if len(selected_roots) == 2 and not all(self._tyr_unit_in_candidates(root, valid_burrowers) for root in list(selected_roots)):
            logger.error("ERROR: RETREAT BELOW: selecting two units requires both units to be BURROWER units")
            return False

        can_use = False
        try:
            can_use = bool(
                stratagem.can_use(
                    self.player,
                    self.game,
                    phase_name="Fight phase",
                    unit=selected_roots[0],
                    units=list(selected_roots),
                )
            )
        except TypeError:
            can_use = bool(stratagem.can_use(self.player, self.game, phase_name="Fight phase", unit=selected_roots[0]))
        if not can_use:
            logger.error("ERROR: RETREAT BELOW: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=selected_roots[0]):
            return False

        for root in list(selected_roots):
            if not self._tyr_place_unit_into_strategic_reserves(
                root,
                reason=str(getattr(stratagem, "name", "") or "RETREAT BELOW"),
            ):
                logger.error(
                    "ERROR: RETREAT BELOW: failed to place %s into Strategic Reserves",
                    getattr(root, "name", "Unit"),
                )
                return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        moved_units = ", ".join(str(getattr(root, "name", "Unit") or "Unit") for root in list(selected_roots))
        logger.info("INFO: RETREAT BELOW: %s entered Strategic Reserves.", moved_units)
        return True

    def _use_tyranids_rapid_regeneration(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])

        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: RAPID REGENERATION: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        if root is None:
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: RAPID REGENERATION: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: RAPID REGENERATION: target must be a TYRANIDS unit")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: RAPID REGENERATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: RAPID REGENERATION: not opponent's Shooting phase")
            return False

        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: RAPID REGENERATION: missing attacking unit context")
            return False
        if self._tyr_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: RAPID REGENERATION: attacker is not an enemy unit")
            return False

        eligible = candidates or self._tyr_rapid_regeneration_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: RAPID REGENERATION: target must be one of the attacking unit's selected targets")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            attacking_unit=attacker_root,
            phase_name=phase_label,
        ):
            logger.error("ERROR: RAPID REGENERATION: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        fnp_value = 5 if self._tyr_unit_in_synapse_range(root) else 6
        phase_key_fn = getattr(self, "_phase_key_from_name", None)
        phase_key = phase_key_fn(phase_name) if callable(phase_key_fn) else ""
        if not phase_key:
            phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        entry = {
            "value": int(fnp_value),
            "attack_type": "any",
            "expires_phase": str(phase_key),
            "source": str(getattr(stratagem, "name", "") or "RAPID REGENERATION"),
        }
        append_defensive_effect = getattr(self, "_append_defensive_effect", None)
        if callable(append_defensive_effect):
            append_defensive_effect(root, "defensive_fnp_overrides", entry)
        else:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            items = list(sr.get("defensive_fnp_overrides", []) or [])
            items.append(entry)
            sr["defensive_fnp_overrides"] = items
            root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RAPID REGENERATION: %s gains Feel No Pain %d+ this phase.",
            getattr(root, "name", "Unit"),
            int(fnp_value),
        )
        return True

    def _use_tyranids_predatory_imperative(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("units") or kwargs.get("selected_units")
        if selected is None:
            selected = kwargs.get("target_units")
        if selected is None:
            selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots:
            logger.error("ERROR: PREDATORY IMPERATIVE: no target unit provided")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: PREDATORY IMPERATIVE: cannot target more than two units")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "command phase":
            logger.error("ERROR: PREDATORY IMPERATIVE: wrong phase")
            return False
        if not self._tyr_is_own_command_phase(phase_name=phase_name):
            logger.error("ERROR: PREDATORY IMPERATIVE: not your Command phase")
            return False

        eligible = candidates or self._tyr_predatory_imperative_candidates()
        for root in list(selected_roots):
            if not self._tyr_unit_in_candidates(root, eligible):
                logger.error("ERROR: PREDATORY IMPERATIVE: one or more selected units are not currently eligible")
                return False
        if len(selected_roots) == 2 and not all(self._tyr_unit_in_synapse_range(root) for root in list(selected_roots)):
            logger.error("ERROR: PREDATORY IMPERATIVE: selecting two units requires both units to be within Synapse Range")
            return False

        adaptation_choice = (
            kwargs.get("adaptation")
            or kwargs.get("hyper_adaptation")
            or kwargs.get("choice")
            or kwargs.get("mode")
            or kwargs.get("selection")
        )
        selected_key = self._tyr_resolve_predatory_imperative_adaptation(adaptation_choice)
        if not selected_key:
            logger.error("ERROR: PREDATORY IMPERATIVE: no valid Hyper-adaptation choice available")
            return False
        mgr = self._tyr_detachment_mgr()
        restricted_key = str(getattr(mgr, "active_hyper_adaptation_key", "") or "").strip().upper() if mgr is not None else ""
        if selected_key == restricted_key:
            logger.error(
                "ERROR: PREDATORY IMPERATIVE: cannot select the Hyper-adaptation chosen at the start of battle round one"
            )
            return False

        first = selected_roots[0]
        if not stratagem.can_use(self.player, self.game, target_unit=first, unit=first, phase_name="Command phase"):
            logger.error("ERROR: PREDATORY IMPERATIVE: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=first):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        source_name = str(getattr(stratagem, "name", "") or "PREDATORY IMPERATIVE")
        for root in list(selected_roots):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["tyranids_predatory_imperative_active"] = True
            sr["tyranids_predatory_imperative_adaptation_key"] = str(selected_key)
            sr["tyranids_predatory_imperative_source"] = source_name
            if owner_id:
                sr["tyranids_predatory_imperative_owner"] = owner_id
            if turn:
                sr["tyranids_predatory_imperative_turn"] = int(turn)
            root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PREDATORY IMPERATIVE: %d unit(s) gain Hyper-adaptation %s until your next Command phase.",
            len(selected_roots),
            str(selected_key),
        )
        return True

    def _use_tyranids_endless_swarm(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("units") or kwargs.get("selected_units")
        if selected is None:
            selected = kwargs.get("target_units")
        if selected is None:
            selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots:
            logger.error("ERROR: ENDLESS SWARM: no target unit provided")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: ENDLESS SWARM: cannot target more than two units")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "command phase":
            logger.error("ERROR: ENDLESS SWARM: wrong phase")
            return False
        if not self._tyr_is_own_command_phase(phase_name=phase_name):
            logger.error("ERROR: ENDLESS SWARM: not your Command phase")
            return False

        eligible = candidates or self._tyr_endless_swarm_candidates()
        for root in list(selected_roots):
            if not self._tyr_unit_in_candidates(root, eligible):
                logger.error(
                    "ERROR: ENDLESS SWARM: one or more selected units are not eligible ENDLESS MULTITUDE units with destroyed models"
                )
                return False
        if len(selected_roots) == 2 and not all(self._tyr_unit_in_synapse_range(root) for root in list(selected_roots)):
            logger.error("ERROR: ENDLESS SWARM: selecting two units requires both units to be within Synapse Range")
            return False

        first = selected_roots[0]
        if not stratagem.can_use(self.player, self.game, target_unit=first, unit=first, phase_name="Command phase"):
            logger.error("ERROR: ENDLESS SWARM: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=first):
            return False

        total_returned = 0
        for root in list(selected_roots):
            roll = max(0, dice_module.get_roll("D3")) + 3
            returned = self._tyr_return_destroyed_models(root, amount=int(roll))
            total_returned += int(returned)

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ENDLESS SWARM: returned %d destroyed model(s) across %d unit(s).",
            int(total_returned),
            len(selected_roots),
        )
        return True

    def _use_tyranids_adrenal_surge(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("units") or kwargs.get("selected_units")
        if selected is None:
            selected = kwargs.get("target_units")
        if selected is None:
            selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots:
            logger.error("ERROR: ADRENAL SURGE: no target unit provided")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: ADRENAL SURGE: cannot target more than two units")
            return False

        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: ADRENAL SURGE: wrong phase")
            return False

        eligible = candidates or self._tyr_adrenal_surge_candidates()
        for root in list(selected_roots):
            if not self._tyr_unit_in_candidates(root, eligible):
                logger.error("ERROR: ADRENAL SURGE: one or more selected units are not currently eligible to fight")
                return False
        if len(selected_roots) == 2 and not all(self._tyr_unit_in_synapse_range(root) for root in list(selected_roots)):
            logger.error("ERROR: ADRENAL SURGE: selecting two units requires both units to be within Synapse Range")
            return False

        first = selected_roots[0]
        if not stratagem.can_use(self.player, self.game, target_unit=first, unit=first, phase_name="Fight phase"):
            logger.error("ERROR: ADRENAL SURGE: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=first):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        source_name = str(getattr(stratagem, "name", "") or "ADRENAL SURGE")
        for root in list(selected_roots):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["tyranids_adrenal_surge_active"] = True
            sr["tyranids_adrenal_surge_crit_threshold"] = 5
            sr["tyranids_adrenal_surge_expires_phase"] = "FIGHT_PHASE"
            sr["tyranids_adrenal_surge_source"] = source_name
            if owner_id:
                sr["tyranids_adrenal_surge_turn_owner"] = owner_id
            if turn:
                sr["tyranids_adrenal_surge_turn"] = int(turn)
            root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ADRENAL SURGE: %d unit(s) gain melee critical hits on 5+ this phase.",
            len(selected_roots),
        )
        return True

    def _use_tyranids_death_frenzy(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])

        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: DEATH FRENZY: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        if root is None:
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: DEATH FRENZY: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: DEATH FRENZY: target must be a TYRANIDS unit")
            return False

        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: DEATH FRENZY: wrong phase")
            return False
        attacker_root = self._tyr_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: DEATH FRENZY: missing attacking unit context")
            return False
        if self._tyr_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: DEATH FRENZY: attacker is not an enemy unit")
            return False

        eligible = candidates or self._tyr_death_frenzy_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: DEATH FRENZY: target must be one of the attacking unit's selected targets")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            attacking_unit=attacker_root,
            phase_name="Fight phase",
        ):
            logger.error("ERROR: DEATH FRENZY: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tyranids_death_frenzy_active"] = True
        sr["tyranids_death_frenzy_threshold"] = 4
        sr["tyranids_death_frenzy_expires_phase"] = "FIGHT_PHASE"
        sr["tyranids_death_frenzy_source"] = str(getattr(stratagem, "name", "") or "DEATH FRENZY")
        if owner_id:
            sr["tyranids_death_frenzy_owner"] = owner_id
        if turn:
            sr["tyranids_death_frenzy_turn"] = int(turn)
        root.special_rules = sr
        self._tyr_clear_melee_fight_on_death_cache(root)

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DEATH FRENZY: %s gains melee fight-on-death on 4+ this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_overrun(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: OVERRUN: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        if root is None:
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: OVERRUN: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: OVERRUN: target must be a TYRANIDS unit")
            return False

        phase_name = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: OVERRUN: wrong phase")
            return False

        eligible = candidates or self._tyr_overrun_candidates(unit=root)
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: OVERRUN: target is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: OVERRUN: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current_cons = float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0)
        sr["stratagem_consolidate_distance_override"] = max(current_cons, 6.0)
        sr["stratagem_consolidate_requires_engagement"] = True
        sr["stratagem_consolidate_expires_phase"] = "FIGHT_PHASE"
        sr["stratagem_consolidate_source"] = str(getattr(stratagem, "name", "") or "OVERRUN")

        normal_move_active = self._tyr_unit_in_synapse_range(root) and not self._tyr_unit_in_engagement_range(root)
        if normal_move_active:
            sr["tyranids_overrun_normal_move_active"] = True
            sr["tyranids_overrun_normal_move_distance"] = 6
            sr["tyranids_overrun_expires_phase"] = "FIGHT_PHASE"
            sr["tyranids_overrun_source"] = str(getattr(stratagem, "name", "") or "OVERRUN")
            if owner_id:
                sr["tyranids_overrun_turn_owner"] = owner_id
            if turn:
                sr["tyranids_overrun_turn"] = int(turn)
        else:
            for key in (
                "tyranids_overrun_normal_move_active",
                "tyranids_overrun_normal_move_distance",
                "tyranids_overrun_expires_phase",
                "tyranids_overrun_source",
                "tyranids_overrun_turn_owner",
                "tyranids_overrun_turn",
            ):
                sr.pop(key, None)
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: OVERRUN: %s gets +3\" consolidate this phase%s.",
            getattr(root, "name", "Unit"),
            " and may make a 6\" Normal move instead" if normal_move_active else "",
        )
        return True

    def _use_tyranids_surprise_assault(self, stratagem: Any, **kwargs) -> bool:
        source_unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit")
        attacking_unit = kwargs.get("attacking_unit")
        enemy_candidates = list(kwargs.get("enemy_candidates") or kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])

        if source_unit is None or (enemy_unit is None and not enemy_candidates):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SURPRISE ASSAULT":
                    continue
                if source_unit is None:
                    source_unit = reaction.get("target_unit") or reaction.get("unit")
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit")
                if not enemy_candidates:
                    enemy_candidates = list(reaction.get("enemy_candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        root = self._tyr_root(source_unit)
        enemy_root = self._tyr_root(enemy_unit)
        attacker_root = self._tyr_root(attacking_unit) if attacking_unit is not None else root
        if root is None:
            logger.error("ERROR: SURPRISE ASSAULT: no source unit provided")
            return False
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: SURPRISE ASSAULT: wrong phase")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SURPRISE ASSAULT: not your turn")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: SURPRISE ASSAULT: source unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SURPRISE ASSAULT: source unit must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: SURPRISE ASSAULT: source must be a TYRANIDS unit")
            return False
        if not self._tyr_is_vanguard_invader_unit(root):
            logger.error("ERROR: SURPRISE ASSAULT: source must be a VANGUARD INVADER unit")
            return False

        eligible = list(enemy_candidates or [])
        if not eligible and enemy_root is not None:
            eligible = [enemy_root]
        if not eligible:
            eligible = self._tyr_vanguard_surprise_assault_enemy_candidates(
                attacking_unit=attacker_root,
                target_units=target_units or ([enemy_root] if enemy_root is not None else []),
            )
        if not eligible:
            logger.error("ERROR: SURPRISE ASSAULT: no eligible enemy targets")
            return False

        if enemy_root is None:
            if len(eligible) == 1:
                enemy_root = eligible[0]
            else:
                request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
                if not callable(request_decision):
                    logger.error("ERROR: SURPRISE ASSAULT: decision queue unavailable")
                    return False
                from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
                from ..engine.decisions import DecisionOption, DecisionRequest

                unit_id = str(get_entity_id(root) or "")
                candidate_ids = [self._tyr_sort_key(candidate) for candidate in list(eligible) if self._tyr_sort_key(candidate)]
                if not unit_id or not candidate_ids:
                    logger.error("ERROR: SURPRISE ASSAULT: source unit or candidate target is missing a stable id")
                    return False
                if self._tyr_pending_choose_quarry_request(
                    ability="tyranids_vanguard_surprise_assault",
                    source_unit_id=unit_id,
                    phase_name=phase_label,
                ):
                    logger.error("ERROR: SURPRISE ASSAULT: target selection already queued for this unit")
                    return False
                if not stratagem.can_use(
                    self.player,
                    self.game,
                    unit=root,
                    target_unit=root,
                    enemy_unit=eligible[0],
                    phase_name=phase_label,
                ):
                    logger.error("ERROR: SURPRISE ASSAULT: cannot be used in current state")
                    return False
                if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=eligible[0]):
                    return False
                request = DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    f"{getattr(stratagem, 'name', 'SURPRISE ASSAULT')}: select one enemy unit targeted by {getattr(root, 'name', 'Unit')}.",
                    player_id=getattr(self.player, "id", None),
                    options=[
                        DecisionOption.create(
                            str(getattr(candidate, "name", "Enemy Unit") or "Enemy Unit"),
                            payload={
                                "unit_id": unit_id,
                                "source_unit_id": unit_id,
                                "target_unit_id": self._tyr_sort_key(candidate),
                            },
                        )
                        for candidate in list(eligible)
                        if self._tyr_sort_key(candidate)
                    ],
                    context={
                        "ability": "tyranids_vanguard_surprise_assault",
                        "ability_name": str(getattr(stratagem, "name", "") or "SURPRISE ASSAULT"),
                        "phase": phase_label,
                        "phase_name": phase_label,
                        "unit_id": unit_id,
                        "source_unit_id": unit_id,
                        "candidate_unit_ids": list(candidate_ids),
                        "optional": False,
                    },
                )
                request_decision(request)
                queue = getattr(self.game, "decision_queue", None) if self.game is not None else None
                if queue is not None and hasattr(queue, "get") and hasattr(queue, "add"):
                    decision_id = str(getattr(request, "decision_id", "") or "")
                    if decision_id and queue.get(decision_id) is None:
                        queue.add(request)
                self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
                logger.info(
                    "INFO: SURPRISE ASSAULT: queued target selection for %s.",
                    getattr(root, "name", "Unit"),
                )
                return True

        if enemy_root is None:
            logger.error("ERROR: SURPRISE ASSAULT: no enemy unit selected")
            return False
        if self._tyr_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: SURPRISE ASSAULT: enemy target must be an enemy unit")
            return False
        if not self._tyr_on_battlefield(enemy_root, require_targetable=False):
            logger.error("ERROR: SURPRISE ASSAULT: enemy target must be on the battlefield")
            return False
        if not self._tyr_unit_in_candidates(enemy_root, eligible):
            logger.error("ERROR: SURPRISE ASSAULT: selected enemy is not currently eligible")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            target_unit=root,
            enemy_unit=enemy_root,
            phase_name=phase_label,
        ):
            logger.error("ERROR: SURPRISE ASSAULT: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False

        mgr = self._tyr_detachment_mgr()
        activate = getattr(mgr, "activate_vanguard_surprise_assault", None) if mgr is not None else None
        outcome = (
            activate(
                root,
                enemy_root,
                phase_name=phase_label,
                game=self.game,
                player=self.player,
                source=str(getattr(stratagem, "name", "") or "SURPRISE ASSAULT"),
            )
            if callable(activate)
            else {"ok": False}
        )
        if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
            logger.error("ERROR: SURPRISE ASSAULT: failed to apply selected target")
            return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SURPRISE ASSAULT: %s gains +1 to hit%s against %s this phase.",
            getattr(root, "name", "Unit"),
            " and +1 to wound" if bool(outcome.get("failed_battle_shock", False)) else "",
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_tyranids_assassin_beasts(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "ASSASSIN BEASTS":
                    continue
                target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: ASSASSIN BEASTS: no target unit provided")
            return False

        root = self._tyr_root(target_unit)
        if root is None:
            return False
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "fight phase":
            logger.error("ERROR: ASSASSIN BEASTS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: ASSASSIN BEASTS: not your turn")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: ASSASSIN BEASTS: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: ASSASSIN BEASTS: target unit must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: ASSASSIN BEASTS: target must be a TYRANIDS unit")
            return False
        if not self._tyr_is_vanguard_invader_unit(root) or not self._tyr_is_infantry_unit(root):
            logger.error("ERROR: ASSASSIN BEASTS: target must be a VANGUARD INVADER INFANTRY unit")
            return False

        eligible = candidates or self._tyr_vanguard_assassin_beasts_candidates()
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: ASSASSIN BEASTS: target is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, target_unit=root, phase_name="Fight phase"):
            logger.error("ERROR: ASSASSIN BEASTS: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._tyr_detachment_mgr()
        activate = getattr(mgr, "activate_vanguard_assassin_beasts", None) if mgr is not None else None
        outcome = (
            activate(
                root,
                phase_name="Fight phase",
                game=self.game,
                player=self.player,
                source=str(getattr(stratagem, "name", "") or "ASSASSIN BEASTS"),
            )
            if callable(activate)
            else {"ok": False}
        )
        if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
            logger.error("ERROR: ASSASSIN BEASTS: failed to apply precision bonus")
            return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ASSASSIN BEASTS: %s gains [PRECISION] on melee weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_seeded_broods(self, stratagem: Any, **kwargs) -> bool:
        selected = (
            kwargs.get("units")
            or kwargs.get("target_units")
            or kwargs.get("selected_units")
            or kwargs.get("selected_unit_ids")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        candidates = list(kwargs.get("candidates") or [])
        if not candidates:
            candidates = self._tyr_vanguard_seeded_broods_candidates()

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "movement phase":
            logger.error("ERROR: SEEDED BROODS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SEEDED BROODS: not your turn")
            return False
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return False
        if not candidates:
            logger.error("ERROR: SEEDED BROODS: no eligible units are in Reserves")
            return False

        vanguard_candidates = [candidate for candidate in list(candidates) if self._tyr_is_vanguard_invader_unit(candidate)]
        option_payloads = self._tyr_vanguard_selection_payloads(
            eligible=candidates,
            vanguard_candidates=vanguard_candidates,
            single_unit_candidates=candidates,
        )
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots and len(option_payloads) == 1:
            selected_roots = self._tyr_resolve_units(
                dict(option_payloads[0].get("payload", {}) or {}).get("selected_unit_ids")
            )
        if not selected_roots:
            request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
            if not callable(request_decision):
                logger.error("ERROR: SEEDED BROODS: decision queue unavailable")
                return False
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest

            candidate_ids = [self._tyr_sort_key(candidate) for candidate in list(candidates) if self._tyr_sort_key(candidate)]
            vanguard_candidate_ids = [
                self._tyr_sort_key(candidate)
                for candidate in list(vanguard_candidates)
                if self._tyr_sort_key(candidate)
            ]
            if not candidate_ids or not option_payloads:
                logger.error("ERROR: SEEDED BROODS: no legal selections are available")
                return False
            if self._tyr_pending_choose_quarry_request(
                ability="tyranids_vanguard_seeded_broods",
                phase_name="Movement phase",
                candidate_unit_ids=candidate_ids,
            ):
                logger.error("ERROR: SEEDED BROODS: unit selection already queued")
                return False
            if not stratagem.can_use(
                self.player,
                self.game,
                unit=candidates[0],
                target_unit=candidates[0],
                phase_name="Movement phase",
            ):
                logger.error("ERROR: SEEDED BROODS: cannot be used in current state")
                return False
            if not self._tyr_spend_cp(stratagem, target_unit=candidates[0]):
                return False
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{getattr(stratagem, 'name', 'SEEDED BROODS')}: select eligible unit(s) in Reserves.",
                player_id=getattr(self.player, "id", None),
                options=[
                    DecisionOption.create(
                        str(item.get("label", "") or "Selected units"),
                        payload=dict(item.get("payload", {}) or {}),
                    )
                    for item in list(option_payloads)
                ],
                context={
                    "ability": "tyranids_vanguard_seeded_broods",
                    "ability_name": str(getattr(stratagem, "name", "") or "SEEDED BROODS"),
                    "phase": "Movement phase",
                    "phase_name": "Movement phase",
                    "candidate_unit_ids": list(candidate_ids),
                    "vanguard_candidate_unit_ids": list(vanguard_candidate_ids),
                    "max_selections": 2,
                    "optional": False,
                },
            )
            request_decision(request)
            self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info("INFO: SEEDED BROODS: queued reserves unit selection.")
            return True

        is_valid, reason = self._tyr_validate_vanguard_pair_selection(
            selected_roots,
            eligible=candidates,
            vanguard_candidates=vanguard_candidates,
            infantry_candidates=candidates,
        )
        if not is_valid:
            logger.error("ERROR: SEEDED BROODS: invalid unit selection (%s)", reason or "invalid_selection")
            return False
        for root in list(selected_roots):
            if not self._tyr_owned_by_player(root, self.player):
                logger.error("ERROR: SEEDED BROODS: selected unit is not yours")
                return False
            if not self._is_tyranids_unit(root):
                logger.error("ERROR: SEEDED BROODS: selected unit must be a TYRANIDS unit")
                return False
            is_in_reserves = getattr(root, "is_in_reserves", None)
            if not callable(is_in_reserves) or not bool(is_in_reserves()):
                logger.error("ERROR: SEEDED BROODS: selected unit must currently be in Reserves")
                return False
            if bool(getattr(root, "embarked_in", None)):
                logger.error("ERROR: SEEDED BROODS: embarked units cannot be selected")
                return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=selected_roots[0],
            units=list(selected_roots),
            target_unit=selected_roots[0],
            phase_name="Movement phase",
        ):
            logger.error("ERROR: SEEDED BROODS: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=selected_roots[0]):
            return False

        mgr = self._tyr_detachment_mgr()
        activate = getattr(mgr, "activate_vanguard_seeded_broods", None) if mgr is not None else None
        if not callable(activate):
            logger.error("ERROR: SEEDED BROODS: detachment effect manager is unavailable")
            return False
        for root in list(selected_roots):
            outcome = activate(
                root,
                phase_name="Movement phase",
                game=self.game,
                player=self.player,
                source=str(getattr(stratagem, "name", "") or "SEEDED BROODS"),
            )
            if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
                logger.error("ERROR: SEEDED BROODS: failed to apply setup-round bonus to %s", getattr(root, "name", "Unit"))
                return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SEEDED BROODS: %s treat the current battle round as one higher when setting up this phase.",
            ", ".join(str(getattr(root, "name", "Unit") or "Unit") for root in list(selected_roots)),
        )
        return True

    def _use_tyranids_hypersensory_scillia(self, stratagem: Any, **kwargs) -> bool:
        selected = (
            kwargs.get("units")
            or kwargs.get("target_units")
            or kwargs.get("selected_units")
            or kwargs.get("selected_unit_ids")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        enemy_unit = kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        vanguard_candidates = list(kwargs.get("vanguard_candidates") or [])
        infantry_candidates = list(kwargs.get("infantry_candidates") or [])

        if enemy_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "HYPERSENSORY SCILLIA":
                    continue
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not vanguard_candidates:
                    vanguard_candidates = list(reaction.get("vanguard_candidates") or [])
                if not infantry_candidates:
                    infantry_candidates = list(reaction.get("infantry_candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        enemy_root = self._tyr_root(enemy_unit)
        if enemy_root is None:
            logger.error("ERROR: HYPERSENSORY SCILLIA: missing enemy move trigger context")
            return False
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "movement phase":
            logger.error("ERROR: HYPERSENSORY SCILLIA: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: HYPERSENSORY SCILLIA: only available in your opponent's Movement phase")
            return False
        if self._tyr_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: HYPERSENSORY SCILLIA: trigger unit must be an enemy unit")
            return False
        if not self._tyr_on_battlefield(enemy_root, require_targetable=True):
            logger.error("ERROR: HYPERSENSORY SCILLIA: trigger unit must be on the battlefield")
            return False

        eligible = candidates or self._tyr_vanguard_hypersensory_scillia_candidates(enemy_unit=enemy_root)
        if not eligible:
            logger.error("ERROR: HYPERSENSORY SCILLIA: no eligible units are within range")
            return False
        if not vanguard_candidates:
            vanguard_candidates = [candidate for candidate in list(eligible) if self._tyr_is_vanguard_invader_unit(candidate)]
        if not infantry_candidates:
            infantry_candidates = [candidate for candidate in list(eligible) if self._tyr_is_infantry_unit(candidate)]

        option_payloads = self._tyr_vanguard_selection_payloads(
            eligible=eligible,
            vanguard_candidates=vanguard_candidates,
            single_unit_candidates=eligible,
        )
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots and len(option_payloads) == 1:
            selected_roots = self._tyr_resolve_units(
                dict(option_payloads[0].get("payload", {}) or {}).get("selected_unit_ids")
            )
        if not selected_roots:
            request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
            if not callable(request_decision):
                logger.error("ERROR: HYPERSENSORY SCILLIA: decision queue unavailable")
                return False
            from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
            from ..engine.decisions import DecisionOption, DecisionRequest

            candidate_ids = [self._tyr_sort_key(candidate) for candidate in list(eligible) if self._tyr_sort_key(candidate)]
            vanguard_candidate_ids = [
                self._tyr_sort_key(candidate)
                for candidate in list(vanguard_candidates)
                if self._tyr_sort_key(candidate)
            ]
            infantry_candidate_ids = [
                self._tyr_sort_key(candidate)
                for candidate in list(infantry_candidates)
                if self._tyr_sort_key(candidate)
            ]
            enemy_unit_id = self._tyr_sort_key(enemy_root)
            if not candidate_ids or not option_payloads or not enemy_unit_id:
                logger.error("ERROR: HYPERSENSORY SCILLIA: no legal reactive move selections are available")
                return False
            if self._tyr_pending_choose_quarry_request(
                ability="tyranids_vanguard_hypersensory_scillia",
                enemy_unit_id=enemy_unit_id,
            ):
                logger.error("ERROR: HYPERSENSORY SCILLIA: unit selection already queued for this enemy move")
                return False
            if not stratagem.can_use(
                self.player,
                self.game,
                unit=eligible[0],
                target_unit=eligible[0],
                enemy_unit=enemy_root,
                phase_name="Movement phase",
            ):
                logger.error("ERROR: HYPERSENSORY SCILLIA: cannot be used in current state")
                return False
            if not self._tyr_spend_cp(stratagem, target_unit=eligible[0], enemy_unit=enemy_root):
                return False
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{getattr(stratagem, 'name', 'HYPERSENSORY SCILLIA')}: select eligible units to react to {getattr(enemy_root, 'name', 'Enemy')}.",
                player_id=getattr(self.player, "id", None),
                options=[
                    DecisionOption.create(
                        str(item.get("label", "") or "Selected units"),
                        payload=dict(item.get("payload", {}) or {}),
                    )
                    for item in list(option_payloads)
                ],
                context={
                    "ability": "tyranids_vanguard_hypersensory_scillia",
                    "ability_name": str(getattr(stratagem, "name", "") or "HYPERSENSORY SCILLIA"),
                    "phase": "Opponent Movement phase",
                    "phase_name": "Movement phase",
                    "enemy_unit_id": enemy_unit_id,
                    "candidate_unit_ids": list(candidate_ids),
                    "vanguard_candidate_unit_ids": list(vanguard_candidate_ids),
                    "infantry_candidate_unit_ids": list(infantry_candidate_ids),
                    "max_selections": 2,
                    "optional": False,
                },
            )
            request_decision(request)
            self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: HYPERSENSORY SCILLIA: queued reactive move selection against %s.",
                getattr(enemy_root, "name", "Enemy"),
            )
            return True

        is_valid, reason = self._tyr_validate_vanguard_pair_selection(
            selected_roots,
            eligible=eligible,
            vanguard_candidates=vanguard_candidates,
            infantry_candidates=infantry_candidates,
        )
        if not is_valid:
            logger.error("ERROR: HYPERSENSORY SCILLIA: invalid unit selection (%s)", reason or "invalid_selection")
            return False
        for root in list(selected_roots):
            if not self._tyr_owned_by_player(root, self.player):
                logger.error("ERROR: HYPERSENSORY SCILLIA: selected unit is not yours")
                return False
            if not self._tyr_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: HYPERSENSORY SCILLIA: selected unit must be on the battlefield")
                return False
            if not self._is_tyranids_unit(root):
                logger.error("ERROR: HYPERSENSORY SCILLIA: selected unit must be a TYRANIDS unit")
                return False
            if self._tyr_unit_in_engagement_range(root):
                logger.error("ERROR: HYPERSENSORY SCILLIA: selected unit cannot be in Engagement Range")
                return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=selected_roots[0],
            units=list(selected_roots),
            target_unit=selected_roots[0],
            enemy_unit=enemy_root,
            phase_name="Movement phase",
        ):
            logger.error("ERROR: HYPERSENSORY SCILLIA: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=selected_roots[0], enemy_unit=enemy_root):
            return False

        queue_reactive_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_reactive_move):
            logger.error("ERROR: HYPERSENSORY SCILLIA: reactive move queue is unavailable")
            return False
        for root in list(selected_roots):
            queue_reactive_move(
                player=self.player,
                unit=root,
                max_distance=6,
                kind="tyranids_hypersensory_scillia",
                movement_type="reactive",
                source=str(getattr(stratagem, "name", "") or "HYPERSENSORY SCILLIA"),
                moving_unit=enemy_root,
                range_value=6,
                allow_skip=True,
            )

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: HYPERSENSORY SCILLIA: queued reactive moves for %s.",
            ", ".join(str(getattr(root, "name", "Unit") or "Unit") for root in list(selected_roots)),
        )
        return True

    def _use_tyranids_unseen_lurkers(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])

        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "UNSEEN LURKERS":
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        root = self._tyr_root(target_unit)
        attacker_root = self._tyr_root(attacking_unit)
        if root is None:
            logger.error("ERROR: UNSEEN LURKERS: no target unit provided")
            return False
        if attacker_root is None:
            logger.error("ERROR: UNSEEN LURKERS: missing attacking unit context")
            return False
        if not self._is_tyranids_vanguard_onslaught_detachment():
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "shooting phase":
            logger.error("ERROR: UNSEEN LURKERS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: UNSEEN LURKERS: only available in your opponent's Shooting phase")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: UNSEEN LURKERS: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: UNSEEN LURKERS: target unit must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: UNSEEN LURKERS: target must be a TYRANIDS unit")
            return False
        if not self._tyr_is_vanguard_invader_unit(root):
            logger.error("ERROR: UNSEEN LURKERS: target must be a VANGUARD INVADER unit")
            return False
        if self._tyr_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: UNSEEN LURKERS: attacker must be an enemy unit")
            return False

        eligible = candidates or self._tyr_vanguard_targeted_vanguard_invader_candidates(
            attacking_unit=attacker_root,
            target_units=target_units or ([root] if root is not None else []),
        )
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: UNSEEN LURKERS: target must be one of the attacking unit's selected VANGUARD INVADER targets")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            attacking_unit=attacker_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: UNSEEN LURKERS: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        mgr = self._tyr_detachment_mgr()
        activate = getattr(mgr, "activate_vanguard_unseen_lurkers", None) if mgr is not None else None
        outcome = (
            activate(
                root,
                phase_name="Shooting phase",
                game=self.game,
                player=active_player,
                source=str(getattr(stratagem, "name", "") or "UNSEEN LURKERS"),
            )
            if callable(activate)
            else {"ok": False}
        )
        if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
            logger.error("ERROR: UNSEEN LURKERS: failed to apply ranged targeting cap")
            return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNSEEN LURKERS: %s can only be targeted by ranged attacks from within 18\" this phase (or 6\" while it has Lone Operative).",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_invisible_hunter(self, stratagem: Any, **kwargs) -> bool:
        selected = (
            kwargs.get("units")
            or kwargs.get("target_units")
            or kwargs.get("selected_units")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        candidates = list(kwargs.get("candidates") or [])
        vanguard_candidates = list(kwargs.get("vanguard_candidates") or [])
        infantry_candidates = list(kwargs.get("infantry_candidates") or [])
        max_units = int(kwargs.get("max_units", 2) or 2)
        if selected is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if selected is None:
                    selected = (
                        reaction.get("units")
                        or reaction.get("target_units")
                        or reaction.get("selected_units")
                        or reaction.get("unit")
                        or reaction.get("target_unit")
                    )
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not vanguard_candidates:
                    vanguard_candidates = list(reaction.get("vanguard_candidates") or [])
                if not infantry_candidates:
                    infantry_candidates = list(reaction.get("infantry_candidates") or [])
                if "max_units" not in kwargs:
                    max_units = int(reaction.get("max_units", max_units) or max_units)
                break

        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        selected_roots = self._tyr_resolve_units(selected)
        if not selected_roots:
            logger.error("ERROR: INVISIBLE HUNTER: no target units provided")
            return False
        if len(selected_roots) > max(1, int(max_units)):
            logger.error("ERROR: INVISIBLE HUNTER: selected too many units")
            return False
        if len(selected_roots) > 2:
            logger.error("ERROR: INVISIBLE HUNTER: cannot select more than two units")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "fight phase":
            logger.error("ERROR: INVISIBLE HUNTER: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: INVISIBLE HUNTER: not opponent's Fight phase")
            return False

        eligible = candidates or self._tyr_invisible_hunter_candidates()
        if not eligible:
            logger.error("ERROR: INVISIBLE HUNTER: no eligible units")
            return False
        valid_vanguard = self._tyr_resolve_units(vanguard_candidates) or [
            unit for unit in eligible if self._tyr_is_vanguard_invader_unit(unit)
        ]
        valid_infantry = self._tyr_resolve_units(infantry_candidates) or [
            unit for unit in eligible if self._tyr_is_infantry_unit(unit)
        ]
        selected_vanguard = 0
        selected_infantry_only = 0

        for root in list(selected_roots):
            if not self._tyr_unit_in_candidates(root, eligible):
                logger.error("ERROR: INVISIBLE HUNTER: selected unit is not currently eligible")
                return False
            if not self._tyr_owned_by_player(root, self.player):
                logger.error("ERROR: INVISIBLE HUNTER: selected unit is not yours")
                return False
            if not self._tyr_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: INVISIBLE HUNTER: selected unit must be on the battlefield and targetable")
                return False
            if not self._is_tyranids_unit(root):
                logger.error("ERROR: INVISIBLE HUNTER: selected unit must be a TYRANIDS unit")
                return False
            is_vanguard = self._tyr_unit_in_candidates(root, valid_vanguard)
            is_infantry = self._tyr_unit_in_candidates(root, valid_infantry)
            if not (is_vanguard or is_infantry):
                logger.error("ERROR: INVISIBLE HUNTER: selected unit must be VANGUARD INVADER or TYRANIDS INFANTRY")
                return False
            if is_vanguard:
                selected_vanguard += 1
            elif is_infantry:
                selected_infantry_only += 1

        if selected_infantry_only > 1:
            logger.error("ERROR: INVISIBLE HUNTER: cannot select more than one non-VANGUARD TYRANIDS INFANTRY unit")
            return False
        if selected_infantry_only > 0 and len(selected_roots) > 1:
            logger.error("ERROR: INVISIBLE HUNTER: selecting TYRANIDS INFANTRY that is not VANGUARD INVADER limits selection to one unit")
            return False
        if len(selected_roots) == 2 and selected_vanguard != 2:
            logger.error("ERROR: INVISIBLE HUNTER: selecting two units requires both to be VANGUARD INVADER units")
            return False

        can_use = False
        try:
            can_use = bool(
                stratagem.can_use(
                    self.player,
                    self.game,
                    phase_name="Fight phase",
                    unit=selected_roots[0],
                    units=list(selected_roots),
                )
            )
        except TypeError:
            can_use = bool(stratagem.can_use(self.player, self.game, phase_name="Fight phase", unit=selected_roots[0]))
        if not can_use:
            logger.error("ERROR: INVISIBLE HUNTER: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=selected_roots[0]):
            return False

        for root in list(selected_roots):
            if not self._tyr_place_unit_into_strategic_reserves(
                root,
                reason=str(getattr(stratagem, "name", "") or "INVISIBLE HUNTER"),
            ):
                logger.error(
                    "ERROR: INVISIBLE HUNTER: failed to place %s into Strategic Reserves",
                    getattr(root, "name", "Unit"),
                )
                return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        moved_units = ", ".join(str(getattr(root, "name", "Unit") or "Unit") for root in list(selected_roots))
        logger.info("INFO: INVISIBLE HUNTER: %s entered Strategic Reserves.", moved_units)
        return True

    def _use_tyranids_reinforced_hive_node(self, stratagem: Any, **kwargs) -> bool:
        target = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])

        if target is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "REINFORCED HIVE NODE":
                    continue
                if target is None:
                    target = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        root = self._tyr_root(target)
        attacker_root = self._tyr_root(attacking_unit)
        if root is None:
            logger.error("ERROR: REINFORCED HIVE NODE: no target unit provided")
            return False
        if attacker_root is None:
            logger.error("ERROR: REINFORCED HIVE NODE: missing attacking unit context")
            return False
        if not self._is_tyranids_synaptic_nexus_detachment():
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: REINFORCED HIVE NODE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: REINFORCED HIVE NODE: not opponent's Shooting phase")
            return False
        if self._tyr_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: REINFORCED HIVE NODE: attacking unit must be enemy")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: REINFORCED HIVE NODE: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: REINFORCED HIVE NODE: target must be on the battlefield and targetable")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: REINFORCED HIVE NODE: target must be a TYRANIDS unit")
            return False
        if not self._tyr_is_synapse_unit(root):
            logger.error("ERROR: REINFORCED HIVE NODE: target must be a SYNAPSE unit")
            return False
        if candidates and not self._tyr_unit_in_candidates(root, candidates):
            logger.error("ERROR: REINFORCED HIVE NODE: selected unit is not currently eligible")
            return False
        if target_units:
            resolved_targets = self._tyr_resolve_units(target_units)
            if resolved_targets and not self._tyr_unit_in_candidates(root, resolved_targets):
                logger.error("ERROR: REINFORCED HIVE NODE: target was not selected by the attacking unit")
                return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
            logger.error("ERROR: REINFORCED HIVE NODE: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False
        if not self._apply_generic_defensive_effect(
            root,
            {"effect_type": "ap_worsen", "duration": "attacker", "value": 1, "attack_type": "any"},
            attacker_unit=attacker_root,
            phase_name=phase_label,
            source_name=str(getattr(stratagem, "name", "") or "REINFORCED HIVE NODE"),
        ):
            logger.error("ERROR: REINFORCED HIVE NODE: failed to apply AP modifier")
            return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REINFORCED HIVE NODE: %s worsens incoming AP from %s by 1 until the attacker finishes its attacks.",
            getattr(root, "name", "Unit"),
            getattr(attacker_root, "name", "Attacker"),
        )
        return True

    def _use_tyranids_irresistible_will(self, stratagem: Any, **kwargs) -> bool:
        source_unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("source_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if source_unit is None and len(candidates) == 1:
            source_unit = candidates[0]
        if source_unit is None:
            logger.error("ERROR: IRRESISTIBLE WILL: no source unit provided")
            return False
        if enemy_unit is None:
            logger.error("ERROR: IRRESISTIBLE WILL: no enemy unit provided")
            return False

        root = self._tyr_root(source_unit)
        enemy_root = self._tyr_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        if not self._is_tyranids_synaptic_nexus_detachment():
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: IRRESISTIBLE WILL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: IRRESISTIBLE WILL: not your Shooting phase")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: IRRESISTIBLE WILL: source unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: IRRESISTIBLE WILL: source unit must be on the battlefield and targetable")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: IRRESISTIBLE WILL: source unit must be a TYRANIDS unit")
            return False
        if not self._tyr_is_synapse_unit(root):
            logger.error("ERROR: IRRESISTIBLE WILL: source unit must be a SYNAPSE unit")
            return False
        if self._tyr_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name=phase_name):
            logger.error("ERROR: IRRESISTIBLE WILL: source unit has already been selected this phase")
            return False
        eligible = candidates or self._tyr_irresistible_will_source_candidates(phase_name=phase_name)
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: IRRESISTIBLE WILL: selected source unit is not currently eligible")
            return False
        if self._tyr_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: IRRESISTIBLE WILL: selected enemy must be enemy")
            return False
        if not self._tyr_on_battlefield(enemy_root, require_targetable=True):
            logger.error("ERROR: IRRESISTIBLE WILL: enemy unit must be on the battlefield and targetable")
            return False
        if not unit_within_range_of_unit(root, enemy_root, 24.0, use_attached_aggregate=True):
            logger.error("ERROR: IRRESISTIBLE WILL: enemy unit must be within 24\"")
            return False
        if not self._tyr_unit_visible_to_unit(root, enemy_root):
            logger.error("ERROR: IRRESISTIBLE WILL: enemy unit must be visible to the source unit")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
            logger.error("ERROR: IRRESISTIBLE WILL: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False

        mgr = self._tyr_detachment_mgr()
        activate = getattr(mgr, "activate_synaptic_nexus_irresistible_will", None) if mgr is not None else None
        outcome = (
            activate(
                root,
                enemy_root,
                phase_name=phase_label,
                game=self.game,
                player=self.player,
                source=str(getattr(stratagem, "name", "") or "IRRESISTIBLE WILL"),
            )
            if callable(activate)
            else {"ok": False}
        )
        if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
            logger.error("ERROR: IRRESISTIBLE WILL: failed to apply attack reroll effect")
            return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: IRRESISTIBLE WILL: attacks by friendly TYRANIDS units within 6\" of %s re-roll Hit and Wound rolls of 1 against %s this phase.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_tyranids_synaptic_channelling(self, stratagem: Any, **kwargs) -> bool:
        target = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target is None and len(candidates) == 1:
            target = candidates[0]
        if target is None:
            logger.error("ERROR: SYNAPTIC CHANNELLING: no target unit provided")
            return False

        root = self._tyr_root(target)
        if root is None:
            return False
        if not self._is_tyranids_synaptic_nexus_detachment():
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "command phase":
            logger.error("ERROR: SYNAPTIC CHANNELLING: wrong phase")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: SYNAPTIC CHANNELLING: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SYNAPTIC CHANNELLING: target must be on the battlefield and targetable")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: SYNAPTIC CHANNELLING: target must be a TYRANIDS unit")
            return False
        if not self._tyr_is_synapse_unit(root):
            logger.error("ERROR: SYNAPTIC CHANNELLING: target must be a SYNAPSE unit")
            return False
        eligible = candidates or self._tyr_synaptic_channelling_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: SYNAPTIC CHANNELLING: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Command phase"):
            logger.error("ERROR: SYNAPTIC CHANNELLING: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        mgr = self._tyr_detachment_mgr()
        activate = getattr(mgr, "activate_synaptic_nexus_synaptic_channelling", None) if mgr is not None else None
        outcome = (
            activate(
                root,
                game=self.game,
                player=self.player,
                source=str(getattr(stratagem, "name", "") or "SYNAPTIC CHANNELLING"),
            )
            if callable(activate)
            else {"ok": False}
        )
        if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
            logger.error("ERROR: SYNAPTIC CHANNELLING: failed to apply Synapse projection")
            return False

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SYNAPTIC CHANNELLING: friendly TYRANIDS units within 9\" of %s are in Synapse Range until end of turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_imperative_dominance(self, stratagem: Any, **kwargs) -> bool:
        target = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target is None and len(candidates) == 1:
            target = candidates[0]
        if target is None:
            logger.error("ERROR: IMPERATIVE DOMINANCE: no target unit provided")
            return False

        root = self._tyr_root(target)
        if root is None:
            return False
        if not self._is_tyranids_synaptic_nexus_detachment():
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "command phase":
            logger.error("ERROR: IMPERATIVE DOMINANCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: IMPERATIVE DOMINANCE: not your turn")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: IMPERATIVE DOMINANCE: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: IMPERATIVE DOMINANCE: target must be on the battlefield and targetable")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: IMPERATIVE DOMINANCE: target must be a TYRANIDS unit")
            return False
        if not self._tyr_unit_in_synapse_range(root):
            logger.error("ERROR: IMPERATIVE DOMINANCE: target must be within Synapse Range")
            return False
        eligible = candidates or self._tyr_imperative_dominance_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: IMPERATIVE DOMINANCE: selected unit is not currently eligible")
            return False

        imperative_key = str(kwargs.get("imperative_key") or kwargs.get("choice_key") or kwargs.get("key") or "").strip().upper()
        if imperative_key:
            if imperative_key not in {"SYNAPTIC_AUGMENTATION", "SURGING_VITALITY", "GOADED_TO_SLAUGHTER"}:
                logger.error("ERROR: IMPERATIVE DOMINANCE: selected imperative is invalid")
                return False
            if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Command phase"):
                logger.error("ERROR: IMPERATIVE DOMINANCE: cannot be used in current state")
                return False
            if not self._tyr_spend_cp(stratagem, target_unit=root):
                return False
            mgr = self._tyr_detachment_mgr()
            activate = getattr(mgr, "activate_synaptic_nexus_imperative_dominance", None) if mgr is not None else None
            outcome = (
                activate(
                    root,
                    imperative_key,
                    game=self.game,
                    player=self.player,
                    source=str(getattr(stratagem, "name", "") or "IMPERATIVE DOMINANCE"),
                )
                if callable(activate)
                else {"ok": False}
            )
            if not isinstance(outcome, dict) or not bool(outcome.get("ok", False)):
                logger.error("ERROR: IMPERATIVE DOMINANCE: failed to apply selected imperative")
                return False
            self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: IMPERATIVE DOMINANCE: %s now uses %s until the start of your next Command phase.",
                getattr(root, "name", "Unit"),
                str(outcome.get("choice_name", imperative_key) or imperative_key),
            )
            return True

        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Command phase"):
            logger.error("ERROR: IMPERATIVE DOMINANCE: cannot be used in current state")
            return False
        request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
        if not callable(request_decision):
            logger.error("ERROR: IMPERATIVE DOMINANCE: decision queue unavailable")
            return False

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        unit_id = str(get_entity_id(root) or "")
        if not unit_id:
            logger.error("ERROR: IMPERATIVE DOMINANCE: target unit must have a stable id")
            return False
        queue = getattr(self.game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != str(DECISION_CHOOSE_QUARRY):
                    continue
                req_ctx = dict(getattr(req, "context", {}) or {})
                if str(req_ctx.get("ability", "") or "") != "tyranids_imperative_dominance":
                    continue
                if str(req_ctx.get("unit_id", "") or "") != unit_id:
                    continue
                logger.error("ERROR: IMPERATIVE DOMINANCE: imperative selection already queued for target unit")
                return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        choices = (
            ("SYNAPTIC_AUGMENTATION", "Synaptic Augmentation", "Models in this unit have a 5+ invulnerable save."),
            ("SURGING_VITALITY", "Surging Vitality", "Add 1 to Advance and Charge rolls made for this unit."),
            ("GOADED_TO_SLAUGHTER", "Goaded to Slaughter", "Each time a model in this unit makes a melee attack, add 1 to the Hit roll."),
        )
        options = [
            DecisionOption.create(
                label,
                payload={
                    "unit_id": unit_id,
                    "choice_key": key,
                    "summary": summary,
                },
            )
            for key, label, summary in choices
        ]
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{getattr(stratagem, 'name', 'IMPERATIVE DOMINANCE')}: select one Synaptic Imperative for {getattr(root, 'name', 'Unit')}.",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "tyranids_imperative_dominance",
                "ability_name": str(getattr(stratagem, "name", "") or "IMPERATIVE DOMINANCE"),
                "unit_id": unit_id,
                "allowed_choice_keys": [key for key, _label, _summary in choices],
                "battle_round": int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0,
            },
        )
        request_decision(request)

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: IMPERATIVE DOMINANCE: queued imperative selection for %s.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_the_smothering_shadow(self, stratagem: Any, **kwargs) -> bool:
        source_unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
        candidates = list(kwargs.get("candidates") or [])

        if source_unit is None or enemy_unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "THE SMOTHERING SHADOW":
                    continue
                if source_unit is None:
                    source_unit = reaction.get("target_unit") or reaction.get("unit")
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        root = self._tyr_root(source_unit)
        enemy_root = self._tyr_root(enemy_unit)
        if root is None:
            logger.error("ERROR: THE SMOTHERING SHADOW: no source unit provided")
            return False
        if enemy_root is None:
            logger.error("ERROR: THE SMOTHERING SHADOW: missing enemy unit context")
            return False
        if not self._is_tyranids_synaptic_nexus_detachment():
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: THE SMOTHERING SHADOW: source unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: THE SMOTHERING SHADOW: source unit must be on the battlefield and targetable")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: THE SMOTHERING SHADOW: source unit must be a TYRANIDS unit")
            return False
        if not self._tyr_is_synapse_unit(root):
            logger.error("ERROR: THE SMOTHERING SHADOW: source unit must be a SYNAPSE unit")
            return False
        if self._tyr_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: THE SMOTHERING SHADOW: selected enemy must be enemy")
            return False
        if not self._tyr_on_battlefield(enemy_root, require_targetable=False):
            logger.error("ERROR: THE SMOTHERING SHADOW: enemy unit must be on the battlefield")
            return False
        if not unit_within_range_of_unit(root, enemy_root, 12.0, use_attached_aggregate=True):
            logger.error("ERROR: THE SMOTHERING SHADOW: enemy unit must be within 12\" of the source unit")
            return False
        eligible = candidates or self._tyr_smothering_shadow_candidates(enemy_unit=enemy_root)
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: THE SMOTHERING SHADOW: selected source unit is not currently eligible")
            return False
        phase_label = str(kwargs.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip() or "Any phase"
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name=phase_label):
            logger.error("ERROR: THE SMOTHERING SHADOW: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False

        rolls = [dice_module.get_roll("D6") for _ in range(6)]
        mortal_wounds = sum(1 for roll in rolls if int(roll or 0) >= 3)
        if mortal_wounds > 0:
            apply_mortals = getattr(enemy_root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortals):
                try:
                    apply_mortals(enemy_root, int(mortal_wounds), game_map=getattr(self.game, "map", None))
                except TypeError:
                    apply_mortals(
                        target_unit=enemy_root,
                        amount=int(mortal_wounds),
                        game_map=getattr(self.game, "map", None),
                    )

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: THE SMOTHERING SHADOW: %s rolls %s against %s for %d mortal wounds.",
            getattr(root, "name", "Unit"),
            rolls,
            getattr(enemy_root, "name", "Enemy"),
            int(mortal_wounds),
        )
        return True

    def _use_tyranids_override_instincts(self, stratagem: Any, **kwargs) -> bool:
        target = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target is None and len(candidates) == 1:
            target = candidates[0]
        if target is None:
            logger.error("ERROR: OVERRIDE INSTINCTS: no target unit provided")
            return False

        root = self._tyr_root(target)
        if root is None:
            return False
        if not self._is_tyranids_synaptic_nexus_detachment():
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "movement phase":
            logger.error("ERROR: OVERRIDE INSTINCTS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: OVERRIDE INSTINCTS: not your turn")
            return False

        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: OVERRIDE INSTINCTS: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: OVERRIDE INSTINCTS: target must be on the battlefield and targetable")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: OVERRIDE INSTINCTS: target must be a TYRANIDS unit")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: OVERRIDE INSTINCTS: target must have Fallen Back this phase")
            return False
        if not self._tyr_unit_in_synapse_range(root):
            logger.error("ERROR: OVERRIDE INSTINCTS: target must be within Synapse Range")
            return False

        eligible = candidates or self._tyr_override_instincts_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: OVERRIDE INSTINCTS: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: OVERRIDE INSTINCTS: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tyranids_override_instincts_active"] = True
        sr["tyranids_override_instincts_expires_phase"] = "CHARGE_PHASE"
        sr["tyranids_override_instincts_source"] = str(getattr(stratagem, "name", "") or "OVERRIDE INSTINCTS")
        owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id:
            sr["tyranids_override_instincts_turn_owner"] = owner_id
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if turn:
            sr["tyranids_override_instincts_turn"] = int(turn)
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: OVERRIDE INSTINCTS: %s can shoot and charge this turn after Falling Back.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_corrosive_viscera(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("destroyed_unit") or kwargs.get("unit") or kwargs.get("target_unit")
        model = kwargs.get("destroyed_model") or kwargs.get("model") or kwargs.get("target_model")
        if unit is None or model is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "CORROSIVE VISCERA":
                    continue
                unit = unit or reaction.get("destroyed_unit") or reaction.get("unit") or reaction.get("target_unit")
                model = model or reaction.get("destroyed_model") or reaction.get("model") or reaction.get("target_model")
                if not kwargs.get("phase_name") and reaction.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None or model is None:
            logger.error("ERROR: CORROSIVE VISCERA: missing destroyed model context")
            return False

        root = self._tyr_root(unit)
        if root is None:
            return False
        if not self._is_tyranids_crusher_stampede_detachment():
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: CORROSIVE VISCERA: target unit is not yours")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: CORROSIVE VISCERA: target must be a TYRANIDS unit")
            return False
        is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
        if not is_monster:
            logger.error("ERROR: CORROSIVE VISCERA: target must be a MONSTER unit")
            return False
        if self._tyr_has_keyword(root, "FLY") or self._tyr_has_keyword(model, "FLY"):
            logger.error("ERROR: CORROSIVE VISCERA: target model cannot have FLY")
            return False
        try:
            has_deadly, _dd = root.has_deadly_demise()
        except Exception:
            has_deadly = False
        if not has_deadly:
            logger.error("ERROR: CORROSIVE VISCERA: target does not have Deadly Demise")
            return False
        model_alive_attr = getattr(model, "is_alive", None)
        model_alive = bool(model_alive_attr() if callable(model_alive_attr) else model_alive_attr)
        if model_alive:
            logger.error("ERROR: CORROSIVE VISCERA: target model is not destroyed")
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: CORROSIVE VISCERA: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: CORROSIVE VISCERA: not opponent's Shooting phase")
            return False

        game_map = getattr(self.game, "map", None)
        if game_map is None:
            logger.error("ERROR: CORROSIVE VISCERA: map context unavailable")
            return False
        phase_label = "Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            target_model=model,
            model=model,
            phase_name=phase_label,
        ):
            logger.error("ERROR: CORROSIVE VISCERA: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        setattr(model, "_corrosive_viscera_auto_trigger_once", True)
        setattr(model, "_skip_deadly_demise_once", True)
        trigger_fn = getattr(root, "trigger_deadly_demise_manually", None)
        if callable(trigger_fn):
            trigger_fn(model, game_map)

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CORROSIVE VISCERA: %s automatically triggers Deadly Demise.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_massive_impact(self, stratagem: Any, **kwargs) -> bool:
        source_unit = kwargs.get("source_unit") or kwargs.get("unit") or kwargs.get("target_unit")
        source_model = kwargs.get("source_model") or kwargs.get("model") or kwargs.get("target_model")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
        source_model_candidates = list(kwargs.get("source_model_candidates") or [])
        enemy_candidates = list(kwargs.get("enemy_candidates") or [])
        action = str(kwargs.get("action") or "")

        if source_unit is None or source_model is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "MASSIVE IMPACT":
                    continue
                source_unit = source_unit or reaction.get("source_unit") or reaction.get("unit") or reaction.get("target_unit")
                source_model = source_model or reaction.get("source_model") or reaction.get("model") or reaction.get("target_model")
                enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("target_enemy_unit")
                if not source_model_candidates:
                    source_model_candidates = list(reaction.get("source_model_candidates") or [])
                if not enemy_candidates:
                    enemy_candidates = list(reaction.get("enemy_candidates") or [])
                if not action:
                    action = str(reaction.get("action") or "")
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        root = self._tyr_root(source_unit)
        if root is None:
            logger.error("ERROR: MASSIVE IMPACT: missing source unit")
            return False
        if not self._is_tyranids_crusher_stampede_detachment():
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "charge phase":
            logger.error("ERROR: MASSIVE IMPACT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MASSIVE IMPACT: not your turn")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: MASSIVE IMPACT: source unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: MASSIVE IMPACT: source unit must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: MASSIVE IMPACT: source unit must be a TYRANIDS unit")
            return False
        is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
        if not is_monster:
            logger.error("ERROR: MASSIVE IMPACT: source unit must be a MONSTER unit")
            return False
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"", "charge", "charge move"} and not bool(
            getattr(getattr(root, "round_state", None), "charged_this_round", False)
        ):
            logger.error("ERROR: MASSIVE IMPACT: source model must have ended a Charge move")
            return False

        if not source_model_candidates:
            source_model_candidates = self._tyr_massive_impact_source_models(root)
        if source_model is None and len(source_model_candidates) == 1:
            source_model = source_model_candidates[0]
        if source_model is None:
            logger.error("ERROR: MASSIVE IMPACT: missing source model")
            return False
        if source_model_candidates and source_model not in source_model_candidates:
            logger.error("ERROR: MASSIVE IMPACT: selected source model is not eligible")
            return False
        model_alive_attr = getattr(source_model, "is_alive", None)
        model_alive = bool(model_alive_attr() if callable(model_alive_attr) else model_alive_attr)
        if not model_alive:
            logger.error("ERROR: MASSIVE IMPACT: source model must be alive")
            return False

        if not enemy_candidates:
            enemy_candidates = self._tyr_massive_impact_enemy_candidates(source_model)
        enemy_root = self._tyr_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None and len(enemy_candidates) == 1:
            enemy_root = self._tyr_root(enemy_candidates[0])
        if enemy_root is None:
            logger.error("ERROR: MASSIVE IMPACT: missing enemy unit within Engagement Range")
            return False
        if enemy_candidates and not self._tyr_unit_in_candidates(enemy_root, enemy_candidates):
            logger.error("ERROR: MASSIVE IMPACT: selected enemy is not within Engagement Range of the source model")
            return False
        if self._tyr_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: MASSIVE IMPACT: selected enemy unit is not enemy")
            return False
        if not self._tyr_on_battlefield(enemy_root, require_targetable=False):
            logger.error("ERROR: MASSIVE IMPACT: selected enemy unit must be on the battlefield")
            return False

        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            target_model=source_model,
            model=source_model,
            enemy_unit=enemy_root,
            phase_name="Charge phase",
        ):
            logger.error("ERROR: MASSIVE IMPACT: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False

        rolls = [dice_module.get_roll("D6") for _ in range(6)]
        mortal_wounds = sum(1 for roll in rolls if int(roll or 0) >= 4)
        if mortal_wounds > 0:
            apply_mortals = getattr(enemy_root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortals):
                try:
                    apply_mortals(enemy_root, int(mortal_wounds), game_map=getattr(self.game, "map", None))
                except TypeError:
                    apply_mortals(target_unit=enemy_root, amount=int(mortal_wounds), game_map=getattr(self.game, "map", None))

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MASSIVE IMPACT: %s rolled six D6 %s and dealt %d mortal wound(s) to %s.",
            getattr(root, "name", "Unit"),
            list(rolls),
            int(mortal_wounds),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_tyranids_rampaging_monstrosities(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = candidates[0]
        if selected is None:
            logger.error("ERROR: RAMPAGING MONSTROSITIES: no target unit provided")
            return False

        root = self._tyr_root(selected)
        if root is None:
            return False
        if not self._is_tyranids_crusher_stampede_detachment():
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "fight phase":
            logger.error("ERROR: RAMPAGING MONSTROSITIES: wrong phase")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: RAMPAGING MONSTROSITIES: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: RAMPAGING MONSTROSITIES: target unit must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: RAMPAGING MONSTROSITIES: target must be a TYRANIDS unit")
            return False
        is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
        if not is_monster:
            logger.error("ERROR: RAMPAGING MONSTROSITIES: target must be a MONSTER unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: RAMPAGING MONSTROSITIES: target has already been selected to fight this phase")
            return False
        eligible = candidates or self._tyr_rampaging_monstrosities_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: RAMPAGING MONSTROSITIES: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Fight phase"):
            logger.error("ERROR: RAMPAGING MONSTROSITIES: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tyranids_rampaging_monstrosities_active"] = True
        sr["tyranids_rampaging_monstrosities_expires_phase"] = "FIGHT_PHASE"
        sr["tyranids_rampaging_monstrosities_source"] = str(
            getattr(stratagem, "name", "") or "RAMPAGING MONSTROSITIES"
        )
        owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id:
            sr["tyranids_rampaging_monstrosities_turn_owner"] = owner_id
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if turn:
            sr["tyranids_rampaging_monstrosities_turn"] = turn
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RAMPAGING MONSTROSITIES: %s can re-roll melee Hit rolls this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_savage_roar(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or [])

        if target_unit is None or attacking_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SAVAGE ROAR":
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break

        root = self._tyr_root(target_unit)
        attacker_root = self._tyr_root(attacking_unit)
        if root is None:
            logger.error("ERROR: SAVAGE ROAR: no target unit provided")
            return False
        if attacker_root is None:
            logger.error("ERROR: SAVAGE ROAR: missing attacking unit context")
            return False
        if not self._is_tyranids_crusher_stampede_detachment():
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "fight phase":
            logger.error("ERROR: SAVAGE ROAR: wrong phase")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: SAVAGE ROAR: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SAVAGE ROAR: target unit must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: SAVAGE ROAR: target must be a TYRANIDS unit")
            return False
        is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
        if not is_monster:
            logger.error("ERROR: SAVAGE ROAR: target must be a MONSTER unit")
            return False
        if self._tyr_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: SAVAGE ROAR: attacker must be an enemy unit")
            return False
        eligible = candidates or self._tyr_savage_roar_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: SAVAGE ROAR: target must be one of the attacking unit's selected targets")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            target_unit=root,
            unit=root,
            attacking_unit=attacker_root,
            phase_name="Fight phase",
        ):
            logger.error("ERROR: SAVAGE ROAR: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root, enemy_unit=attacker_root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "SAVAGE ROAR").strip() or "SAVAGE ROAR"
        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        was_battle_shocked = False
        is_battle_shocked = getattr(attacker_root, "is_battle_shocked", None)
        if callable(is_battle_shocked):
            was_battle_shocked = bool(is_battle_shocked())

        result: dict[str, Any] = {"captured": False, "passed": None}
        event_system = getattr(self.game, "event_system", None) if self.game is not None else None
        event_group = f"tyranids_crusher_savage_roar:{self._tyr_sort_key(attacker_root)}:{current_turn}"

        def _capture_battle_shock_result(unit: Any = None, passed: Any = None, **_event_kwargs: Any) -> None:
            if self._tyr_root(unit) is not attacker_root:
                return
            result["captured"] = True
            result["passed"] = bool(passed)

        if event_system is not None and callable(getattr(event_system, "subscribe", None)):
            event_system.subscribe("battle_shock_test_resolved", _capture_battle_shock_result, group=event_group)
        try:
            force_test = getattr(attacker_root, "force_battle_shock_test", None)
            if callable(force_test):
                force_test(current_turn, source=source_name)
            else:
                take_test = getattr(attacker_root, "take_battle_shock_test", None)
                if callable(take_test):
                    take_test(current_turn)
        finally:
            if event_system is not None and callable(getattr(event_system, "unsubscribe_group", None)):
                event_system.unsubscribe_group(event_group)
            elif event_system is not None and callable(getattr(event_system, "unsubscribe", None)):
                event_system.unsubscribe("battle_shock_test_resolved", _capture_battle_shock_result)

        failed_test = False
        if result["captured"] is True and result["passed"] is False:
            failed_test = True
        elif hasattr(attacker_root, "_last_leadership_test_passed"):
            failed_test = not bool(getattr(attacker_root, "_last_leadership_test_passed", True))
        elif callable(is_battle_shocked):
            failed_test = (not was_battle_shocked) and bool(is_battle_shocked())

        attacker_key_fn = getattr(self, "_attacker_unit_key", None)
        attacker_key = attacker_key_fn(attacker_root) if callable(attacker_key_fn) else self._tyr_sort_key(attacker_root)
        entry = {
            "value": 1,
            "attack_type": "melee",
            "attacker_key": attacker_key,
            "expires_phase": "FIGHT_PHASE",
            "source": source_name,
        }
        append_defensive_effect = getattr(self, "_append_defensive_effect", None)
        if callable(append_defensive_effect):
            append_defensive_effect(root, "defensive_hit_mods", dict(entry))
            if failed_test:
                append_defensive_effect(root, "defensive_wound_mods", dict(entry))
        else:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            hit_mods = list(sr.get("defensive_hit_mods", []) or [])
            hit_mods.append(dict(entry))
            sr["defensive_hit_mods"] = hit_mods
            if failed_test:
                wound_mods = list(sr.get("defensive_wound_mods", []) or [])
                wound_mods.append(dict(entry))
                sr["defensive_wound_mods"] = wound_mods
            root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SAVAGE ROAR: %s suffers -1 to hit%s against %s this phase.",
            getattr(attacker_root, "name", "Enemy"),
            " and -1 to wound" if failed_test else "",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_swarm_guided_salvoes(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = candidates[0]
        if selected is None:
            logger.error("ERROR: SWARM-GUIDED SALVOES: no target unit provided")
            return False

        root = self._tyr_root(selected)
        if root is None:
            return False
        if not self._is_tyranids_crusher_stampede_detachment():
            return False
        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "shooting phase":
            logger.error("ERROR: SWARM-GUIDED SALVOES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SWARM-GUIDED SALVOES: not your turn")
            return False
        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: SWARM-GUIDED SALVOES: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: SWARM-GUIDED SALVOES: target unit must be on the battlefield")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: SWARM-GUIDED SALVOES: target must be a TYRANIDS unit")
            return False
        is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
        if not is_monster:
            logger.error("ERROR: SWARM-GUIDED SALVOES: target must be a MONSTER unit")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "shot_this_phase", False) or getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: SWARM-GUIDED SALVOES: target has already been selected to shoot this phase")
            return False
        eligible = candidates or self._tyr_swarm_guided_salvoes_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: SWARM-GUIDED SALVOES: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: SWARM-GUIDED SALVOES: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        source_name = str(getattr(stratagem, "name", "") or "SWARM-GUIDED SALVOES").strip() or "SWARM-GUIDED SALVOES"
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for model_index, model in enumerate(list(models or [])):
            if model is None:
                continue
            is_alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
            if not is_alive:
                continue
            model_id = str(get_entity_id(model) or model_index)
            for wargear_index, wargear in enumerate(list(getattr(model, "wargear", []) or [])):
                if wargear is None:
                    continue
                is_ranged = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged) or not bool(is_ranged()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                key_base = f"tyranids_swarm_guided_salvoes:{model_id}:{wargear_index}:{weapon_name}".lower()
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if callable(set_keywords):
                    set_keywords(
                        key=key_base,
                        weapon_name=weapon_name,
                        keywords=["IGNORES COVER"],
                        source=source_name,
                        expires_phase="SHOOTING_PHASE",
                        attack_type="ranged",
                    )

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["tyranids_swarm_guided_salvoes_active"] = True
        sr["tyranids_swarm_guided_salvoes_expires_phase"] = "SHOOTING_PHASE"
        sr["tyranids_swarm_guided_salvoes_source"] = source_name
        owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id:
            sr["tyranids_swarm_guided_salvoes_turn_owner"] = owner_id
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if turn:
            sr["tyranids_swarm_guided_salvoes_turn"] = turn
        root.special_rules = sr

        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SWARM-GUIDED SALVOES: %s gains [IGNORES COVER] on ranged weapons and ignores Ballistic Skill and Hit roll modifiers this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_tyranids_untrammelled_ferocity(self, stratagem: Any, **kwargs) -> bool:
        selected = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if selected is None and len(candidates) == 1:
            selected = candidates[0]
        if selected is None:
            logger.error("ERROR: UNTRAMMELLED FEROCITY: no target unit provided")
            return False

        root = self._tyr_root(selected)
        if root is None:
            return False
        if not self._is_tyranids_crusher_stampede_detachment():
            return False

        phase_name = self._tyr_phase_name(kwargs.get("phase_name") or getattr(self, "_current_phase_name", ""))
        if phase_name != "movement phase":
            logger.error("ERROR: UNTRAMMELLED FEROCITY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: UNTRAMMELLED FEROCITY: not your turn")
            return False

        if not self._tyr_owned_by_player(root, self.player):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: target unit is not yours")
            return False
        if not self._tyr_on_battlefield(root, require_targetable=True):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: target must be on the battlefield and targetable")
            return False
        if not self._is_tyranids_unit(root):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: target must be a TYRANIDS unit")
            return False
        is_monster = bool(getattr(root, "is_monster", False)) or self._tyr_has_keyword(root, "MONSTER")
        if not is_monster:
            logger.error("ERROR: UNTRAMMELLED FEROCITY: target must be a MONSTER unit")
            return False
        if bool(getattr(getattr(root, "round_state", None), "moved_this_round", False)):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: target already moved this phase")
            return False

        eligible = candidates or self._tyr_untrammelled_ferocity_candidates()
        if eligible and not self._tyr_unit_in_candidates(root, eligible):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: selected unit is not currently eligible")
            return False
        if not stratagem.can_use(self.player, self.game, target_unit=root, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: UNTRAMMELLED FEROCITY: cannot be used in current state")
            return False
        if not self._tyr_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}

        move_types = {"move", "advance", "fall_back"}

        def _merge_move_types(rule_key: str, added_key: str) -> None:
            current = set(sr.get(rule_key) or [])
            added = sorted([move_type for move_type in move_types if move_type not in current])
            merged = sorted(current.union(move_types))
            if merged:
                sr[rule_key] = merged
            if added:
                sr[added_key] = added
            else:
                sr.pop(added_key, None)

        _merge_move_types("bearer_unit_phase_move_types", "tyranids_untrammelled_ferocity_added_phase_move_types")
        _merge_move_types(
            "bearer_unit_phase_move_block_titanic_types",
            "tyranids_untrammelled_ferocity_added_phase_move_block_titanic_types",
        )
        _merge_move_types(
            "bearer_unit_phase_move_engagement_types",
            "tyranids_untrammelled_ferocity_added_phase_move_engagement_types",
        )

        stride_height_present = "titanic_stride_tall_terrain_height" in sr
        stride_source_present = "titanic_stride_source" in sr
        sr["tyranids_untrammelled_ferocity_prev_stride_height_present"] = bool(stride_height_present)
        sr["tyranids_untrammelled_ferocity_prev_stride_source_present"] = bool(stride_source_present)
        if stride_height_present:
            sr["tyranids_untrammelled_ferocity_prev_stride_height_value"] = float(
                sr.get("titanic_stride_tall_terrain_height", 4.0) or 4.0
            )
        if stride_source_present:
            sr["tyranids_untrammelled_ferocity_prev_stride_source_value"] = str(sr.get("titanic_stride_source", "") or "")

        sr["titanic_stride_tall_terrain_height"] = 4.0
        sr["titanic_stride_source"] = str(getattr(stratagem, "name", "") or "UNTRAMMELLED FEROCITY")
        sr["tyranids_untrammelled_ferocity_active"] = True
        sr["tyranids_untrammelled_ferocity_expires_phase"] = "MOVEMENT_PHASE"
        sr["tyranids_untrammelled_ferocity_source"] = str(getattr(stratagem, "name", "") or "UNTRAMMELLED FEROCITY")

        owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id:
            sr["tyranids_untrammelled_ferocity_turn_owner"] = owner_id
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        if turn:
            sr["tyranids_untrammelled_ferocity_turn"] = turn

        root.special_rules = sr
        self._tyr_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNTRAMMELLED FEROCITY: %s can move through models (excluding TITANIC) and terrain this phase.",
            getattr(root, "name", "Unit"),
        )
        return True
