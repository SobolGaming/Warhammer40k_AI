from __future__ import annotations

from typing import Any, Optional

from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id
import logging
logger = logging.getLogger(__name__)


class GreyKnightsStratagemMixin:
    @staticmethod
    def _gk_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        return get_root() if callable(get_root) else unit

    @staticmethod
    def _gk_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    @staticmethod
    def _gk_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _gk_is_on_battlefield(unit: Any) -> bool:
        if unit is None:
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves) and bool(in_reserves()):
            return False
        if bool(getattr(unit, "is_embarked", False)) or getattr(unit, "embarked_in", None) is not None:
            return False
        return True

    @staticmethod
    def _gk_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    def _get_gk_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "grey_knights_detachments", None) if army is not None else None

    def _is_warpbane_task_force(self) -> bool:
        mgr = self._get_gk_mgr()
        checker = getattr(mgr, "is_warpbane_task_force", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_augurium_task_force(self) -> bool:
        mgr = self._get_gk_mgr()
        checker = getattr(mgr, "is_augurium_task_force", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_banishers(self) -> bool:
        mgr = self._get_gk_mgr()
        checker = getattr(mgr, "is_banishers", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_brotherhood_strike(self) -> bool:
        mgr = self._get_gk_mgr()
        checker = getattr(mgr, "is_brotherhood_strike", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_hallowed_conclave(self) -> bool:
        mgr = self._get_gk_mgr()
        checker = getattr(mgr, "is_hallowed_conclave", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_gk_unit(self, unit: Any) -> bool:
        root = self._gk_root(unit)
        if root is None:
            return False
        mgr = self._get_gk_mgr()
        checker = getattr(mgr, "_is_grey_knights_unit", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        return bool(has_any_keyword("GREY KNIGHTS")) if callable(has_any_keyword) else False

    @staticmethod
    def _is_gk_psyker_unit(unit: Any) -> bool:
        if unit is None:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("PSYKER")):
            return True
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        return bool(has_any_keyword("PSYKER")) if callable(has_any_keyword) else False

    @staticmethod
    def _is_gk_infantry_unit(unit: Any) -> bool:
        if unit is None:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            return bool(has_keyword("INFANTRY"))
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        return bool(has_any_keyword("INFANTRY")) if callable(has_any_keyword) else False

    @staticmethod
    def _is_gk_terminator_unit(unit: Any) -> bool:
        if unit is None:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            return bool(has_keyword("TERMINATOR"))
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        return bool(has_any_keyword("TERMINATOR")) if callable(has_any_keyword) else False

    def _is_purifier_squad_unit(self, unit: Any) -> bool:
        root = self._gk_root(unit)
        if root is None:
            return False
        mgr = self._get_gk_mgr()
        checker = getattr(mgr, "_is_purifier_squad_unit", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        if callable(has_any_keyword) and bool(has_any_keyword("PURIFIER SQUAD")):
            return True
        return "purifier squad" in str(getattr(root, "name", "") or "").strip().lower()

    @staticmethod
    def _unit_includes_castellan_crowe(unit: Any) -> bool:
        if unit is None:
            return False
        get_members = getattr(unit, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [unit]
        for member in members:
            name = str(getattr(member, "name", "") or "").strip().lower()
            if "castellan crowe" in name:
                return True
        return False

    def _warpbane_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _warpbane_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._warpbane_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _warpbane_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    @staticmethod
    def _gk_has_deep_strike(unit: Any) -> bool:
        if unit is None:
            return False
        has_deep_strike = getattr(unit, "has_deep_strike", None)
        return bool(has_deep_strike()) if callable(has_deep_strike) else False

    def _gk_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._gk_root(unit)
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

    def _gk_has_enemy_within_engagement_range(self, unit: Any) -> bool:
        root = self._gk_root(unit)
        if root is None:
            return False
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement_range = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement_range):
            return False
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._gk_root(enemy)
            if enemy_root is None:
                continue
            if not self._gk_is_alive(enemy_root):
                continue
            if not self._gk_is_on_battlefield(enemy_root):
                continue
            if bool(is_within_engagement_range(root, enemy_root)):
                return True
        return False

    @staticmethod
    def _gk_clear_ability_cache(unit: Any) -> None:
        root = GreyKnightsStratagemMixin._gk_root(unit)
        if root is None:
            return
        invalidate = getattr(root, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()
            return
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.clear()
            root._ability_cache = cache

    @staticmethod
    def _gk_unit_already_selected_to_shoot_or_fight_this_phase(unit: Any, *, phase_name: str) -> bool:
        root = GreyKnightsStratagemMixin._gk_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        phase_key = str(phase_name or "").strip().lower()
        if phase_key == "shooting phase":
            return bool(
                getattr(round_state, "shot_this_phase", False)
                or getattr(round_state, "shot_this_round", False)
            )
        if phase_key == "fight phase":
            return bool(getattr(round_state, "fought_this_phase", False))
        return False

    def _augurium_phase_candidates(self, *, phase_name: str) -> list[Any]:
        phase_key = str(phase_name or "").strip().lower()
        if phase_key not in {"shooting phase", "fight phase"}:
            return []
        if not self._is_augurium_task_force():
            return []
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_key == "shooting phase" and active_player is not self.player:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root):
                continue
            if not self._gk_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_gk_unit(root):
                continue
            if not self._is_gk_psyker_unit(root):
                continue
            if self._gk_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name=phase_key):
                continue
            out.append(root)
        return sorted(out, key=self._gk_sort_key)

    def _augurium_necessary_end_candidates(self, target_units: Any) -> list[Any]:
        if not self._is_augurium_task_force():
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root):
                continue
            if not self._gk_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_gk_unit(root):
                continue
            if not self._is_gk_infantry_unit(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _augurium_redirected_strike_candidates(self) -> list[Any]:
        if not self._is_augurium_task_force():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root):
                continue
            if not self._gk_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_gk_unit(root):
                continue
            if not self._is_gk_psyker_unit(root):
                continue
            if not self._gk_has_deep_strike(root):
                continue
            if self._gk_has_enemy_within_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._gk_sort_key)

    def _augurium_mirage_of_echoes_candidates(self, *, enemy_unit: Any) -> list[Any]:
        enemy_root = self._gk_root(enemy_unit)
        if enemy_root is None:
            return []
        if self._gk_owned_by_player(enemy_root, self.player):
            return []
        if not self._gk_is_alive(enemy_root):
            return []
        if not self._gk_is_on_battlefield(enemy_root):
            return []
        from ..utility.aura_utils import unit_within_range_of_unit

        out: list[Any] = []
        for root in self._augurium_redirected_strike_candidates():
            if unit_within_range_of_unit(root, enemy_root, 12.0, use_attached_aggregate=True):
                out.append(root)
        return sorted(out, key=self._gk_sort_key)

    @staticmethod
    def _gk_phase_key(phase_name: Any) -> str:
        return str(phase_name or "").strip().upper().replace(" ", "_")

    def _gk_current_turn(self) -> int:
        try:
            return int(getattr(self.game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _gk_current_turn_owner_id(self) -> str:
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        return str(getattr(active_player, "id", "") or getattr(self.player, "id", "") or "")

    def _gk_pending_reaction_by_name(self, stratagem_name: str) -> Optional[dict[str, Any]]:
        target = str(stratagem_name or "").strip().upper()
        if not target:
            return None
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() == target:
                return reaction
        return None

    @staticmethod
    def _gk_member_units(root: Any) -> list[Any]:
        if root is None:
            return []
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        return [member for member in list(members or []) if member is not None] or [root]

    @staticmethod
    def _gk_alive_models(unit: Any) -> list[Any]:
        if unit is None:
            return []
        get_models = getattr(unit, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(unit, "models", []) or [])
        alive_models: list[Any] = []
        for model in list(models or []):
            alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if is_alive:
                alive_models.append(model)
        return alive_models

    @staticmethod
    def _gk_is_character_unit(unit: Any) -> bool:
        if unit is None:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword("CHARACTER")):
            return True
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        return bool(has_any_keyword("CHARACTER")) if callable(has_any_keyword) else False

    def _banishers_units(
        self,
        *,
        require_psyker: bool = False,
        require_infantry: bool = False,
        require_on_battlefield: bool = True,
        require_targetable: bool = True,
    ) -> list[Any]:
        if not self._is_banishers():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        units: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root):
                continue
            if not self._is_gk_unit(root):
                continue
            if require_psyker and not self._is_gk_psyker_unit(root):
                continue
            if require_infantry and not self._is_gk_infantry_unit(root):
                continue
            if require_on_battlefield and not self._gk_is_on_battlefield(root):
                continue
            if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            units.append(root)
        return sorted(units, key=self._gk_sort_key)

    def _banishers_chaos_bane_candidates(self) -> list[Any]:
        candidates: list[Any] = []
        for root in list(self._banishers_units(require_psyker=True) or []):
            if self._gk_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name="shooting phase"):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _banishers_celerity_candidates(self) -> list[Any]:
        candidates: list[Any] = []
        for root in list(self._banishers_units(require_psyker=True, require_infantry=True) or []):
            round_state = getattr(root, "round_state", None)
            if not bool(getattr(round_state, "advanced_this_round", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _banishers_circle_of_sanctuary_candidates(self) -> list[Any]:
        if not self._is_banishers():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_gk_unit(root):
                continue
            for member in self._gk_member_units(root):
                if not self._gk_is_character_unit(member):
                    continue
                if not self._gk_alive_models(member):
                    continue
                candidate_id = self._gk_sort_key(member) or self._gk_sort_key(root)
                if candidate_id and candidate_id in seen:
                    continue
                if candidate_id:
                    seen.add(candidate_id)
                candidates.append(member)
        return sorted(candidates, key=self._gk_sort_key)

    def _banishers_shadow_of_anarch_candidates(self, *, enemy_unit: Any) -> list[Any]:
        enemy_root = self._gk_root(enemy_unit)
        if enemy_root is None:
            return []
        if self._gk_owned_by_player(enemy_root, self.player):
            return []
        if not self._gk_is_alive(enemy_root) or not self._gk_is_on_battlefield(enemy_root):
            return []
        from ..utility.aura_utils import unit_within_range_of_unit

        candidates: list[Any] = []
        for root in list(self._banishers_units(require_psyker=True) or []):
            if self._gk_has_enemy_within_engagement_range(root):
                continue
            if unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True):
                candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _banishers_warding_chant_candidates(self, target_units: Any) -> list[Any]:
        if not self._is_banishers():
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    @staticmethod
    def _banishers_shadow_of_anarch_choice_keys(root: Any) -> list[str]:
        choices = ["NORMAL_MOVE"]
        if GreyKnightsStratagemMixin._gk_has_deep_strike(root):
            choices.append("STRATEGIC_RESERVES")
        return choices

    @staticmethod
    def _normalize_banishers_shadow_choice(choice: Any) -> str:
        raw = str(choice or "").strip().upper().replace("-", "_").replace(" ", "_")
        if raw in {"MOVE", "NORMAL", "NORMAL_MOVE"}:
            return "NORMAL_MOVE"
        if raw in {"RESERVES", "STRATEGIC_RESERVES", "STRATEGIC"}:
            return "STRATEGIC_RESERVES"
        return raw

    def _banishers_hexwrought_clear_tracking_on_root(self, root: Any) -> None:
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        changed = False
        for key in (
            "banishers_hexwrought_reprisal_total_mortal_wounds",
            "banishers_hexwrought_reprisal_enemy_unit_ids",
            "banishers_hexwrought_reprisal_phase",
            "banishers_hexwrought_reprisal_turn",
            "banishers_hexwrought_reprisal_turn_owner",
        ):
            if key in sr:
                sr.pop(key, None)
                changed = True
        if changed:
            root.special_rules = sr

    def _track_banishers_hexwrought_mortal_wound(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any = None,
        phase_name: str = "",
    ) -> None:
        if not self._is_banishers() or target_unit is None:
            return
        root = self._gk_root(target_unit)
        if root is None:
            return
        if not self._gk_owned_by_player(root, self.player):
            return
        if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root):
            return
        game = getattr(self, "game", None)
        phase_key = self._gk_phase_key(phase_name or getattr(getattr(game, "phase", None), "name", "") or "")
        if not phase_key:
            return
        turn = self._gk_current_turn()
        turn_owner_id = self._gk_current_turn_owner_id()
        sr = dict(getattr(root, "special_rules", None) or {})
        stored_phase = self._gk_phase_key(sr.get("banishers_hexwrought_reprisal_phase", ""))
        try:
            stored_turn = int(sr.get("banishers_hexwrought_reprisal_turn", 0) or 0)
        except (TypeError, ValueError):
            stored_turn = 0
        stored_owner_id = str(sr.get("banishers_hexwrought_reprisal_turn_owner", "") or "")
        if stored_phase != phase_key or stored_turn != turn or stored_owner_id != turn_owner_id:
            sr["banishers_hexwrought_reprisal_total_mortal_wounds"] = 0
            sr["banishers_hexwrought_reprisal_enemy_unit_ids"] = []
        try:
            total = int(sr.get("banishers_hexwrought_reprisal_total_mortal_wounds", 0) or 0)
        except (TypeError, ValueError):
            total = 0
        sr["banishers_hexwrought_reprisal_total_mortal_wounds"] = int(total) + 1
        sr["banishers_hexwrought_reprisal_phase"] = str(phase_key)
        sr["banishers_hexwrought_reprisal_turn"] = int(turn)
        sr["banishers_hexwrought_reprisal_turn_owner"] = str(turn_owner_id)
        enemy_root = self._gk_root(attacker_unit)
        if enemy_root is not None and not self._gk_owned_by_player(enemy_root, self.player):
            existing = {
                str(value or "").strip()
                for value in list(sr.get("banishers_hexwrought_reprisal_enemy_unit_ids", []) or [])
                if str(value or "").strip()
            }
            enemy_id = self._gk_sort_key(enemy_root)
            if enemy_id:
                existing.add(enemy_id)
            sr["banishers_hexwrought_reprisal_enemy_unit_ids"] = sorted(existing)
        root.special_rules = sr

    def _banishers_hexwrought_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_banishers():
            return []
        phase_key = self._gk_phase_key(phase_name)
        turn = self._gk_current_turn()
        turn_owner_id = self._gk_current_turn_owner_id()
        candidates: list[Any] = []
        for root in list(self._banishers_units(require_psyker=True) or []):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if self._gk_phase_key(sr.get("banishers_hexwrought_reprisal_phase", "")) != phase_key:
                continue
            try:
                stored_turn = int(sr.get("banishers_hexwrought_reprisal_turn", 0) or 0)
            except (TypeError, ValueError):
                stored_turn = 0
            if stored_turn != turn:
                continue
            if str(sr.get("banishers_hexwrought_reprisal_turn_owner", "") or "") != str(turn_owner_id):
                continue
            try:
                total = int(sr.get("banishers_hexwrought_reprisal_total_mortal_wounds", 0) or 0)
            except (TypeError, ValueError):
                total = 0
            enemy_ids = [
                str(value or "").strip()
                for value in list(sr.get("banishers_hexwrought_reprisal_enemy_unit_ids", []) or [])
                if str(value or "").strip()
            ]
            if total <= 0 or not enemy_ids:
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _banishers_hexwrought_enemy_candidates(self, unit: Any) -> list[Any]:
        root = self._gk_root(unit)
        if root is None:
            return []
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return []
        enemy_ids = [
            str(value or "").strip()
            for value in list(sr.get("banishers_hexwrought_reprisal_enemy_unit_ids", []) or [])
            if str(value or "").strip()
        ]
        if not enemy_ids:
            return []
        registry = getattr(self.game, "entity_registry", None) if self.game is not None else None
        candidates: list[Any] = []
        seen: set[str] = set()
        for enemy_id in enemy_ids:
            enemy = registry.get(enemy_id, kind="unit") if registry is not None else None
            enemy_root = self._gk_root(enemy)
            if enemy_root is None:
                continue
            resolved_id = self._gk_sort_key(enemy_root)
            if not resolved_id or resolved_id in seen:
                continue
            if self._gk_owned_by_player(enemy_root, self.player):
                continue
            if not self._gk_is_alive(enemy_root) or not self._gk_is_on_battlefield(enemy_root):
                continue
            seen.add(resolved_id)
            candidates.append(enemy_root)
        return sorted(candidates, key=self._gk_sort_key)

    def _warpbane_units(
        self,
        *,
        require_infantry: bool = False,
        require_purifier: bool = False,
        require_on_battlefield: bool = True,
        require_targetable: bool = True,
    ) -> list[Any]:
        if not self._is_warpbane_task_force():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        units: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_is_alive(root):
                continue
            if not self._is_gk_unit(root):
                continue
            if require_infantry and not self._is_gk_infantry_unit(root):
                continue
            if require_purifier and not self._is_purifier_squad_unit(root):
                continue
            if require_on_battlefield and not self._gk_is_on_battlefield(root):
                continue
            if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            units.append(root)
        return sorted(units, key=self._gk_sort_key)

    def _warpbane_sanctified_kill_zone_candidates(self, phase_name: str | None = None) -> list[Any]:
        phase_key = str(phase_name or "").strip().lower()
        if phase_key not in ("shooting phase", "fight phase"):
            return []
        mgr = self._get_gk_mgr()
        if mgr is None:
            return []
        candidates: list[Any] = []
        for root in self._warpbane_units(require_on_battlefield=True, require_targetable=True):
            if not bool(mgr.unit_wholly_within_hallowed_ground(root, game=self.game)):
                continue
            round_state = getattr(root, "round_state", None)
            if phase_key == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if phase_key == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _warpbane_hallowed_beacon_candidates(self) -> list[Any]:
        candidates: list[Any] = []
        for root in self._warpbane_units(
            require_infantry=True,
            require_on_battlefield=False,
            require_targetable=True,
        ):
            if self._is_gk_terminator_unit(root):
                continue
            in_reserves = getattr(root, "is_in_reserves", None)
            if not callable(in_reserves) or not bool(in_reserves()):
                continue
            if str(getattr(root, "reserve_status", "") or "").strip().lower() != "reserves":
                continue
            has_deep_strike = getattr(root, "has_deep_strike", None)
            if not callable(has_deep_strike) or not bool(has_deep_strike()):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _hallowed_conclave_units(
        self,
        *,
        require_infantry: bool = False,
        require_terminator: bool = False,
        require_on_battlefield: bool = True,
        require_targetable: bool = True,
    ) -> list[Any]:
        if not self._is_hallowed_conclave():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        units: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root):
                continue
            if not self._is_gk_unit(root):
                continue
            if require_infantry and not self._is_gk_infantry_unit(root):
                continue
            if require_terminator and not self._is_gk_terminator_unit(root):
                continue
            if require_on_battlefield and not self._gk_is_on_battlefield(root):
                continue
            if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            units.append(root)
        return sorted(units, key=self._gk_sort_key)

    def _hallowed_conclave_giants_of_the_battlefield_candidates(self) -> list[Any]:
        candidates: list[Any] = []
        for root in list(
            self._hallowed_conclave_units(
                require_terminator=True,
                require_on_battlefield=True,
                require_targetable=True,
            )
            or []
        ):
            round_state = getattr(root, "round_state", None)
            if bool(getattr(round_state, "fought_this_phase", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _hallowed_conclave_point_blank_purgation_candidates(self) -> list[Any]:
        candidates: list[Any] = []
        for root in list(
            self._hallowed_conclave_units(
                require_infantry=True,
                require_on_battlefield=True,
                require_targetable=True,
            )
            or []
        ):
            if self._gk_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name="shooting phase"):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _hallowed_conclave_precognitive_strategies_candidates(self, *, enemy_unit: Any) -> list[Any]:
        enemy_root = self._gk_root(enemy_unit)
        if enemy_root is None:
            return []
        if self._gk_owned_by_player(enemy_root, self.player):
            return []
        if not self._gk_is_alive(enemy_root) or not self._gk_is_on_battlefield(enemy_root):
            return []
        from ..utility.aura_utils import unit_within_range_of_unit

        candidates: list[Any] = []
        for root in list(
            self._hallowed_conclave_units(
                require_infantry=True,
                require_on_battlefield=True,
                require_targetable=True,
            )
            or []
        ):
            if self._gk_has_enemy_within_engagement_range(root):
                continue
            if not unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _hallowed_conclave_targeted_infantry_candidates(self, target_units: Any) -> list[Any]:
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_gk_unit(root) or not self._is_gk_infantry_unit(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _hallowed_conclave_shining_resolve_candidates(self, *, target_units: Any) -> list[Any]:
        return self._hallowed_conclave_targeted_infantry_candidates(target_units)

    def _hallowed_conclave_unending_fidelity_candidates(self, *, target_units: Any) -> list[Any]:
        return self._hallowed_conclave_targeted_infantry_candidates(target_units)

    def _hallowed_conclave_grind_them_underfoot_enemy_candidates(self, unit: Any) -> list[Any]:
        root = self._gk_root(unit)
        if root is None:
            return []
        if not self._gk_owned_by_player(root, self.player):
            return []
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        get_enemy_units = getattr(game_map, "get_enemy_units", None) if game_map is not None else None
        is_within_engagement_range = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
        if not callable(get_enemy_units) or not callable(is_within_engagement_range):
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for enemy in list(get_enemy_units(root) or []):
            enemy_root = self._gk_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = self._gk_sort_key(enemy_root)
            if enemy_id and enemy_id in seen:
                continue
            if enemy_id:
                seen.add(enemy_id)
            if self._gk_owned_by_player(enemy_root, self.player):
                continue
            if not self._gk_is_alive(enemy_root) or not self._gk_is_on_battlefield(enemy_root):
                continue
            if not bool(is_within_engagement_range(root, enemy_root)):
                continue
            candidates.append(enemy_root)
        return sorted(candidates, key=self._gk_sort_key)

    def _brotherhood_strike_combat_manifestation_candidates(self) -> list[Any]:
        if not self._is_brotherhood_strike():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root):
                continue
            if not self._is_gk_unit(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            in_reserves = getattr(root, "is_in_reserves", None)
            if not callable(in_reserves) or not bool(in_reserves()):
                continue
            reserve_status = str(getattr(root, "reserve_status", "") or "").strip().lower()
            if reserve_status not in {"reserves", "strategic_reserves"}:
                continue
            if not self._gk_has_deep_strike(root):
                continue
            out.append(root)
        return sorted(out, key=self._gk_sort_key)

    def _brotherhood_strike_units(
        self,
        *,
        require_psyker: bool = False,
        require_infantry: bool = False,
        require_deep_strike: bool = False,
        require_on_battlefield: bool = True,
        require_targetable: bool = True,
    ) -> list[Any]:
        if not self._is_brotherhood_strike():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        units: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root):
                continue
            if not self._is_gk_unit(root):
                continue
            if require_psyker and not self._is_gk_psyker_unit(root):
                continue
            if require_infantry and not self._is_gk_infantry_unit(root):
                continue
            if require_deep_strike and not self._gk_has_deep_strike(root):
                continue
            if require_on_battlefield and not self._gk_is_on_battlefield(root):
                continue
            if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            units.append(root)
        return sorted(units, key=self._gk_sort_key)

    def _track_brotherhood_strike_unit_set_up(
        self,
        *,
        unit: Any,
        set_up_as_reinforcements: bool = False,
        used_deep_strike: bool = False,
    ) -> None:
        if not self._is_brotherhood_strike() or unit is None:
            return
        if not bool(set_up_as_reinforcements) or not bool(used_deep_strike):
            return
        root = self._gk_root(unit)
        if root is None:
            return
        if not self._gk_owned_by_player(root, self.player):
            return
        if not self._is_gk_unit(root):
            return
        sr = dict(getattr(root, "special_rules", None) or {})
        sr["brotherhood_strike_deep_strike_setup_active"] = True
        sr["brotherhood_strike_deep_strike_setup_turn"] = int(self._gk_current_turn())
        sr["brotherhood_strike_deep_strike_setup_turn_owner"] = str(self._gk_current_turn_owner_id() or getattr(self.player, "id", "") or "")
        root.special_rules = sr

    def _brotherhood_strike_purgation_pattern_candidates(self) -> list[Any]:
        if not self._is_brotherhood_strike():
            return []
        turn = self._gk_current_turn()
        turn_owner_id = str(getattr(self.player, "id", "") or "")
        candidates: list[Any] = []
        for root in list(self._brotherhood_strike_units(require_on_battlefield=True, require_targetable=True) or []):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not bool(sr.get("brotherhood_strike_deep_strike_setup_active", False)):
                continue
            try:
                marked_turn = int(sr.get("brotherhood_strike_deep_strike_setup_turn", 0) or 0)
            except (TypeError, ValueError):
                marked_turn = 0
            if marked_turn != turn:
                continue
            if str(sr.get("brotherhood_strike_deep_strike_setup_turn_owner", "") or "") != turn_owner_id:
                continue
            round_state = getattr(root, "round_state", None)
            if bool(getattr(round_state, "shot_this_phase", False)) or bool(getattr(round_state, "shot_this_round", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _brotherhood_strike_note_duty_unending_fall_back_start(self, *, unit: Any, action: str) -> None:
        if not self._is_brotherhood_strike() or unit is None:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        if action_key not in {"fall back", "fallback"}:
            return
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            return
        enemy_root = self._gk_root(unit)
        if enemy_root is None:
            return
        if self._gk_owned_by_player(enemy_root, self.player):
            return
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement_range = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement_range):
            return
        candidate_ids: list[str] = []
        for candidate in list(get_enemy_units(enemy_root) or []):
            root = self._gk_root(candidate)
            if root is None:
                continue
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
                continue
            if not self._is_gk_unit(root):
                continue
            if bool(is_within_engagement_range(enemy_root, root)):
                root_id = self._gk_sort_key(root)
                if root_id:
                    candidate_ids.append(root_id)
        enemy_id = self._gk_sort_key(enemy_root)
        if not enemy_id:
            return
        tracking = getattr(self, "_brotherhood_strike_duty_unending_candidates_by_enemy_id", None)
        if not isinstance(tracking, dict):
            tracking = {}
        tracking[enemy_id] = sorted(set(candidate_ids))
        self._brotherhood_strike_duty_unending_candidates_by_enemy_id = tracking

    def _brotherhood_strike_duty_unending_candidates(self, *, enemy_unit: Any) -> list[Any]:
        enemy_root = self._gk_root(enemy_unit)
        enemy_id = self._gk_sort_key(enemy_root)
        if not enemy_id:
            return []
        tracking = getattr(self, "_brotherhood_strike_duty_unending_candidates_by_enemy_id", None)
        if not isinstance(tracking, dict):
            return []
        candidate_ids = list(tracking.get(enemy_id, []) or [])
        if not candidate_ids:
            return []
        registry = getattr(self.game, "entity_registry", None) if self.game is not None else None
        candidates: list[Any] = []
        seen: set[str] = set()
        for candidate_id in candidate_ids:
            root = self._gk_root(registry.get(candidate_id, kind="unit")) if registry is not None else None
            if root is None:
                continue
            root_id = self._gk_sort_key(root)
            if not root_id or root_id in seen:
                continue
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_gk_unit(root):
                continue
            if self._gk_has_enemy_within_engagement_range(root):
                continue
            if not self._gk_has_deep_strike(root):
                continue
            seen.add(root_id)
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _brotherhood_strike_expeditious_exit_candidates(self) -> list[Any]:
        return self._brotherhood_strike_units(
            require_psyker=True,
            require_infantry=True,
            require_deep_strike=True,
            require_on_battlefield=True,
            require_targetable=True,
        )

    def _brotherhood_strike_shining_veil_candidates(self, *, target_units: Any) -> list[Any]:
        if not self._is_brotherhood_strike():
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_gk_unit(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _brotherhood_strike_truesilver_channelling_candidates(self) -> list[Any]:
        candidates: list[Any] = []
        for root in list(
            self._brotherhood_strike_units(
                require_infantry=True,
                require_on_battlefield=True,
                require_targetable=True,
            )
            or []
        ):
            round_state = getattr(root, "round_state", None)
            if bool(getattr(round_state, "fought_this_phase", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _gk_wargear_has_keyword(self, wargear: Any, *, keyword: str) -> bool:
        if wargear is None:
            return False
        target = str(keyword or "").strip().lower()
        if not target:
            return False
        get_keywords = getattr(wargear, "get_keywords", None)
        if callable(get_keywords):
            for value in list(get_keywords() or []):
                if str(value or "").strip().lower() == target:
                    return True
        profiles = getattr(wargear, "profiles", None)
        if not isinstance(profiles, dict):
            return False
        for profile in list(profiles.values()):
            if profile is None:
                continue
            profile_get_keywords = getattr(profile, "get_keywords", None)
            if not callable(profile_get_keywords):
                continue
            for value in list(profile_get_keywords() or []):
                if str(value or "").strip().lower() == target:
                    return True
        return False

    def _gk_apply_temporary_weapon_keyword_bonuses(
        self,
        root: Any,
        *,
        key_prefix: str,
        keywords: list[str],
        expires_phase: str,
        attack_type: str,
        source: str,
        weapon_filter: Any,
    ) -> None:
        if root is None:
            return
        for member in list(self._gk_member_units(root) or [root]):
            for model in list(self._gk_alive_models(member) or []):
                model_id = str(get_entity_id(model) or "")
                for wargear in list(getattr(model, "wargear", []) or []):
                    if wargear is None or not callable(weapon_filter) or not bool(weapon_filter(wargear)):
                        continue
                    weapon_name = str(getattr(wargear, "name", "") or "").strip()
                    set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                    if not weapon_name or not callable(set_keywords):
                        continue
                    set_keywords(
                        key=f"{key_prefix}:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        keywords=list(keywords or []),
                        source=str(source or "").strip() or "Weapon keyword bonus",
                        expires_phase=str(expires_phase or "").strip().upper(),
                        attack_type=str(attack_type or "").strip().lower() or "any",
                    )

    @staticmethod
    def _gk_wargear_name_contains(wargear: Any, *, needle: str) -> bool:
        if wargear is None:
            return False
        target = str(needle or "").strip().lower()
        if not target:
            return False
        weapon_name = str(getattr(wargear, "name", "") or "").strip().lower()
        return target in weapon_name

    def _gk_apply_temporary_weapon_bonuses(
        self,
        root: Any,
        *,
        key_prefix: str,
        expires_phase: str,
        source: str,
        weapon_filter: Any,
        attacks_bonus: int = 0,
        strength_bonus: int = 0,
        ap_bonus: int = 0,
        damage_bonus: int = 0,
    ) -> None:
        if root is None:
            return
        for member in list(self._gk_member_units(root) or [root]):
            for model in list(self._gk_alive_models(member) or []):
                model_id = str(get_entity_id(model) or "")
                set_bonus = getattr(model, "set_temporary_weapon_bonus", None)
                if not callable(set_bonus):
                    continue
                for wargear in list(getattr(model, "wargear", []) or []):
                    if wargear is None or not callable(weapon_filter) or not bool(weapon_filter(wargear)):
                        continue
                    weapon_name = str(getattr(wargear, "name", "") or "").strip()
                    if not weapon_name:
                        continue
                    set_bonus(
                        key=f"{key_prefix}:{model_id}:{weapon_name}".lower(),
                        weapon_name=weapon_name,
                        attacks_bonus=int(attacks_bonus or 0),
                        strength_bonus=int(strength_bonus or 0),
                        ap_bonus=int(ap_bonus or 0),
                        damage_bonus=int(damage_bonus or 0),
                        source=str(source or "").strip() or "Weapon bonus",
                        expires_phase=str(expires_phase or "").strip().upper(),
                    )

    def _warpbane_aegis_eternal_candidates(self, target_units: Any) -> list[Any]:
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_is_alive(root):
                continue
            if not self._gk_is_on_battlefield(root):
                continue
            if not self._gk_owned_by_player(root, self.player):
                continue
            if not self._is_gk_unit(root):
                continue
            if not self._is_gk_infantry_unit(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _warpbane_fires_of_covenant_candidates(self) -> list[Any]:
        return self._warpbane_units(
            require_infantry=True,
            require_on_battlefield=True,
            require_targetable=True,
        )

    def _warpbane_repelling_sphere_candidates(self) -> list[Any]:
        return self._warpbane_fires_of_covenant_candidates()

    def _warpbane_flames_of_sanctity_candidates(self) -> list[Any]:
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        candidates: list[Any] = []
        for root in self._warpbane_units(
            require_purifier=True,
            require_on_battlefield=True,
            require_targetable=True,
        ):
            round_state = getattr(root, "round_state", None)
            charged = bool(getattr(round_state, "charged_this_round", False))
            fought = bool(getattr(round_state, "fought_this_phase", False))
            eligible = False
            is_eligible = getattr(root, "is_eligible_to_fight", None)
            if callable(is_eligible) and game_map is not None:
                eligible = bool(is_eligible(game_map))
            if charged or fought or eligible:
                candidates.append(root)
        return sorted(candidates, key=self._gk_sort_key)

    def _warpbane_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        enemy_unit: Any = None,
    ) -> bool:
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name):
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != str(phase_name or "").strip().lower():
                continue
            if enemy_unit is not None and reaction.get("enemy_unit") is not enemy_unit:
                continue
            return True
        return False

    def _queue_warpbane_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_warpbane_task_force():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        is_opponents_turn = player is not self.player
        if not is_opponents_turn:
            return

        if phase_name == "MOVEMENT_PHASE":
            stratagem = self.get_by_name("FIRES OF COVENANT")
            if stratagem and int(getattr(self.player, "command_points", 0) or 0) >= int(stratagem.cp_cost or 0):
                key = str(stratagem.name or "").strip().upper()
                if key not in self._used_stratagems_this_phase:
                    candidates = self._warpbane_fires_of_covenant_candidates()
                    if candidates and not self._warpbane_reaction_already_queued(
                        event_name="phase_start",
                        stratagem_name=stratagem.name,
                        phase_name="Movement phase",
                    ):
                        payload = {
                            "event": "phase_start",
                            "phase": "Movement phase",
                            "phase_name": "Movement phase",
                            "stratagem": stratagem.name,
                            "cp_cost": stratagem.cp_cost,
                            "candidates": candidates,
                        }
                        if len(candidates) == 1:
                            payload["target_unit"] = candidates[0]
                        self._queue_reaction(payload, use_timer=False)

        if phase_name == "CHARGE_PHASE":
            stratagem = self.get_by_name("REPELLING SPHERE")
            if stratagem and int(getattr(self.player, "command_points", 0) or 0) >= int(stratagem.cp_cost or 0):
                key = str(stratagem.name or "").strip().upper()
                if key not in self._used_stratagems_this_phase:
                    candidates = self._warpbane_repelling_sphere_candidates()
                    if candidates and not self._warpbane_reaction_already_queued(
                        event_name="phase_start",
                        stratagem_name=stratagem.name,
                        phase_name="Charge phase",
                    ):
                        payload = {
                            "event": "phase_start",
                            "phase": "Charge phase",
                            "phase_name": "Charge phase",
                            "stratagem": stratagem.name,
                            "cp_cost": stratagem.cp_cost,
                            "candidates": candidates,
                        }
                        if len(candidates) == 1:
                            payload["target_unit"] = candidates[0]
                        self._queue_reaction(payload, use_timer=False)

    def _queue_warpbane_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_warpbane_task_force():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return

        stratagem = self.get_by_name("FLAMES OF SANCTITY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        key = str(stratagem.name or "").strip().upper()
        if key in self._used_stratagems_this_phase:
            return
        candidates = self._warpbane_flames_of_sanctity_candidates()
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
        payload = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_augurium_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_augurium_task_force():
            return
        if player is not self.player:
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "COMMAND_PHASE":
            return
        stratagem = self.get_by_name("REDIRECTED STRIKE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        name_u = str(stratagem.name or "").strip().upper()
        if name_u in self._used_stratagems_this_phase:
            return
        candidates = self._augurium_redirected_strike_candidates()
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Command phase",
        ):
            return
        payload = {
            "event": "phase_end",
            "phase": "Command phase",
            "phase_name": "Command phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_augurium_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_augurium_task_force():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_key == "SHOOTING_PHASE":
            if player is not self.player or active_player is not self.player:
                return
            phase_name = "Shooting phase"
        elif phase_key == "FIGHT_PHASE":
            phase_name = "Fight phase"
        else:
            return
        candidates = self._augurium_phase_candidates(phase_name=phase_name)
        if not candidates:
            return
        for stratagem_name in ("AGGRESSIVE ANTICIPATION", "APPOINTED HOUR"):
            stratagem = self.get_by_name(stratagem_name)
            if stratagem is None:
                continue
            if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
                continue
            name_u = str(stratagem.name or "").strip().upper()
            if name_u in self._used_stratagems_this_phase:
                continue
            if self._warpbane_reaction_already_queued(
                event_name="phase_start",
                stratagem_name=stratagem.name,
                phase_name=phase_name,
            ):
                continue
            payload = {
                "event": "phase_start",
                "phase": phase_name,
                "phase_name": phase_name,
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)

    def _queue_augurium_unit_set_up_reactions(
        self,
        *,
        unit: Any,
        set_up_as_reinforcements: bool = False,
        **_kwargs: Any,
    ) -> None:
        if not self._is_augurium_task_force():
            return
        if unit is None:
            return
        if not bool(set_up_as_reinforcements):
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        enemy_root = self._gk_root(unit)
        if enemy_root is None:
            return
        if self._gk_owned_by_player(enemy_root, self.player):
            return
        if not self._gk_is_alive(enemy_root) or not self._gk_is_on_battlefield(enemy_root):
            return
        stratagem = self.get_by_name("MIRAGE OF ECHOES")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        name_u = str(stratagem.name or "").strip().upper()
        if name_u in self._used_stratagems_this_phase:
            return
        candidates = self._augurium_mirage_of_echoes_candidates(enemy_unit=enemy_root)
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="unit_set_up",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            enemy_unit=enemy_root,
        ):
            return
        payload = {
            "event": "unit_set_up",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "set_up_as_reinforcements": True,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_augurium_fight_target_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_augurium_task_force():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacking_root = self._gk_root(attacking_unit)
        if attacking_root is None or not self._gk_is_alive(attacking_root):
            return
        if self._gk_owned_by_player(attacking_root, self.player):
            return
        stratagem = self.get_by_name("NECESSARY END")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        name_u = str(stratagem.name or "").strip().upper()
        if name_u in self._used_stratagems_this_phase:
            return
        candidates = self._augurium_necessary_end_candidates(target_units)
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacking_root,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_root,
            "enemy_unit": attacking_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_banishers_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_banishers():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_key == "SHOOTING_PHASE":
            if player is not self.player or active_player is not self.player:
                return
            phase_name = "Shooting phase"
            stratagem_name = "CHAOS BANE"
            candidates = self._banishers_chaos_bane_candidates()
        elif phase_key == "CHARGE_PHASE":
            if player is not self.player or active_player is not self.player:
                return
            phase_name = "Charge phase"
            stratagem_name = "CELERITY"
            candidates = self._banishers_celerity_candidates()
        elif phase_key == "MOVEMENT_PHASE":
            if player is self.player or active_player is self.player:
                return
            phase_name = "Movement phase"
            stratagem_name = "CIRCLE OF SANCTUARY"
            candidates = self._banishers_circle_of_sanctuary_candidates()
        else:
            return
        if not candidates:
            return
        stratagem = self.get_by_name(stratagem_name)
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        name_u = str(stratagem.name or "").strip().upper()
        if name_u in self._used_stratagems_this_phase:
            return
        if self._warpbane_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
        ):
            return
        payload = {
            "event": "phase_start",
            "phase": phase_name,
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_banishers_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_banishers() or unit is None:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        enemy_root = self._gk_root(unit)
        if enemy_root is None or self._gk_owned_by_player(enemy_root, self.player):
            return
        if not self._gk_is_alive(enemy_root) or not self._gk_is_on_battlefield(enemy_root):
            return
        action_key = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        if action_key not in {"move", "normal_move", "advance", "fall_back", "fallback"}:
            return
        stratagem = self.get_by_name("SHADOW OF ANARCH")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        name_u = str(stratagem.name or "").strip().upper()
        if name_u in self._used_stratagems_this_phase:
            return
        candidates = self._banishers_shadow_of_anarch_candidates(enemy_unit=enemy_root)
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="unit_move_ended",
            stratagem_name=stratagem.name,
            phase_name="Movement phase",
            enemy_unit=enemy_root,
        ):
            return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": enemy_root,
            "action": action,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["allowed_choice_keys"] = self._banishers_shadow_of_anarch_choice_keys(candidates[0])
        self._queue_reaction(payload, use_timer=False)

    def _queue_banishers_shooting_target_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_banishers():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacking_root = self._gk_root(attacking_unit)
        if attacking_root is None or self._gk_owned_by_player(attacking_root, self.player):
            return
        if not self._gk_is_alive(attacking_root) or not self._gk_is_on_battlefield(attacking_root):
            return
        stratagem = self.get_by_name("WARDING CHANT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        name_u = str(stratagem.name or "").strip().upper()
        if name_u in self._used_stratagems_this_phase:
            return
        candidates = self._banishers_warding_chant_candidates(target_units)
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacking_root,
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacking_root,
            "attacking_unit": attacking_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_banishers_fight_target_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_banishers():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacking_root = self._gk_root(attacking_unit)
        if attacking_root is None or self._gk_owned_by_player(attacking_root, self.player):
            return
        if not self._gk_is_alive(attacking_root) or not self._gk_is_on_battlefield(attacking_root):
            return
        stratagem = self.get_by_name("WARDING CHANT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        name_u = str(stratagem.name or "").strip().upper()
        if name_u in self._used_stratagems_this_phase:
            return
        candidates = self._banishers_warding_chant_candidates(target_units)
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacking_root,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacking_root,
            "attacking_unit": attacking_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_banishers_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_banishers():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        phase_label = {
            "COMMAND_PHASE": "Command phase",
            "MOVEMENT_PHASE": "Movement phase",
            "SHOOTING_PHASE": "Shooting phase",
            "CHARGE_PHASE": "Charge phase",
            "FIGHT_PHASE": "Fight phase",
        }.get(phase_name, str(phase_name).replace("_", " ").title())
        stratagem = self.get_by_name("HEXWROUGHT REPRISAL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        name_u = str(stratagem.name or "").strip().upper()
        if name_u in self._used_stratagems_this_phase:
            return
        candidates = self._banishers_hexwrought_candidates(phase_name=phase_name)
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name=phase_label,
        ):
            return
        enemy_candidates_by_unit_id: dict[str, list[Any]] = {}
        mortal_wounds_by_unit_id: dict[str, int] = {}
        for root in list(candidates or []):
            root_id = self._gk_sort_key(root)
            enemy_candidates_by_unit_id[root_id] = self._banishers_hexwrought_enemy_candidates(root)
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                try:
                    mortal_wounds_by_unit_id[root_id] = int(
                        sr.get("banishers_hexwrought_reprisal_total_mortal_wounds", 0) or 0
                    )
                except (TypeError, ValueError):
                    mortal_wounds_by_unit_id[root_id] = 0
        payload = {
            "event": "phase_end",
            "phase_name": phase_label,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
            "enemy_candidates_by_unit_id": enemy_candidates_by_unit_id,
            "mortal_wounds_by_unit_id": mortal_wounds_by_unit_id,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            enemy_candidates = enemy_candidates_by_unit_id.get(self._gk_sort_key(candidates[0]), [])
            if len(enemy_candidates) == 1:
                payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_warpbane_shooting_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_warpbane_task_force():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return

        stratagem = self.get_by_name("AEGIS ETERNAL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        key = str(stratagem.name or "").strip().upper()
        if key in self._used_stratagems_this_phase:
            return
        candidates = self._warpbane_aegis_eternal_candidates(target_units)
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacking_unit,
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_brotherhood_strike_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_brotherhood_strike():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name == "SHOOTING_PHASE" and player is self.player:
            stratagem = self.get_by_name("PURGATION PATTERN")
            if stratagem is not None and int(getattr(self.player, "command_points", 0) or 0) >= int(stratagem.cp_cost or 0):
                key = str(stratagem.name or "").strip().upper()
                if key not in self._used_stratagems_this_phase:
                    candidates = self._brotherhood_strike_purgation_pattern_candidates()
                    if candidates and not self._warpbane_reaction_already_queued(
                        event_name="phase_start",
                        stratagem_name=stratagem.name,
                        phase_name="Shooting phase",
                    ):
                        payload = {
                            "event": "phase_start",
                            "phase": "Shooting phase",
                            "phase_name": "Shooting phase",
                            "stratagem": stratagem.name,
                            "cp_cost": stratagem.cp_cost,
                            "candidates": candidates,
                        }
                        if len(candidates) == 1:
                            payload["target_unit"] = candidates[0]
                        self._queue_reaction(payload, use_timer=False)
        if phase_name == "FIGHT_PHASE":
            stratagem = self.get_by_name("TRUESILVER CHANNELLING")
            if stratagem is not None and int(getattr(self.player, "command_points", 0) or 0) >= int(stratagem.cp_cost or 0):
                key = str(stratagem.name or "").strip().upper()
                if key not in self._used_stratagems_this_phase:
                    candidates = self._brotherhood_strike_truesilver_channelling_candidates()
                    if candidates and not self._warpbane_reaction_already_queued(
                        event_name="phase_start",
                        stratagem_name=stratagem.name,
                        phase_name="Fight phase",
                    ):
                        payload = {
                            "event": "phase_start",
                            "phase": "Fight phase",
                            "phase_name": "Fight phase",
                            "stratagem": stratagem.name,
                            "cp_cost": stratagem.cp_cost,
                            "candidates": candidates,
                        }
                        if len(candidates) == 1:
                            payload["target_unit"] = candidates[0]
                        self._queue_reaction(payload, use_timer=False)

    def _queue_brotherhood_strike_move_start_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_brotherhood_strike():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        self._brotherhood_strike_note_duty_unending_fall_back_start(unit=unit, action=action)

    def _queue_brotherhood_strike_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None or not self._is_brotherhood_strike():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        action_key = str(action or "").strip().lower().replace("_", " ")
        moving_root = self._gk_root(unit)
        moving_id = self._gk_sort_key(moving_root)
        try:
            if action_key not in {"fall back", "fallback"}:
                return
            if moving_root is None or self._gk_owned_by_player(moving_root, self.player):
                return
            if not self._gk_is_alive(moving_root) or not self._gk_is_on_battlefield(moving_root):
                return
            stratagem = self.get_by_name("DUTY UNENDING")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
                return
            key = str(stratagem.name or "").strip().upper()
            if key in self._used_stratagems_this_phase:
                return
            candidates = self._brotherhood_strike_duty_unending_candidates(enemy_unit=moving_root)
            if not candidates:
                return
            if self._warpbane_reaction_already_queued(
                event_name="unit_move_ended",
                stratagem_name=stratagem.name,
                phase_name="Movement phase",
                enemy_unit=moving_root,
            ):
                return
            payload = {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "enemy_unit": moving_root,
                "action": action,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
        finally:
            tracking = getattr(self, "_brotherhood_strike_duty_unending_candidates_by_enemy_id", None)
            if isinstance(tracking, dict) and moving_id:
                tracking.pop(moving_id, None)

    def _queue_brotherhood_strike_shooting_target_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_brotherhood_strike():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        attacking_root = self._gk_root(attacking_unit)
        if attacking_root is None or self._gk_owned_by_player(attacking_root, self.player):
            return
        if not self._gk_is_alive(attacking_root) or not self._gk_is_on_battlefield(attacking_root):
            return
        stratagem = self.get_by_name("SHINING VEIL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        key = str(stratagem.name or "").strip().upper()
        if key in self._used_stratagems_this_phase:
            return
        candidates = self._brotherhood_strike_shining_veil_candidates(target_units=target_units)
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="shooting_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacking_root,
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacking_root,
            "attacking_unit": attacking_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_brotherhood_strike_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_brotherhood_strike():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE" or player is self.player:
            return
        stratagem = self.get_by_name("EXPEDITIOUS EXIT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        key = str(stratagem.name or "").strip().upper()
        if key in self._used_stratagems_this_phase:
            return
        candidates = self._brotherhood_strike_expeditious_exit_candidates()
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="phase_end",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
        payload = {
            "event": "phase_end",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_hallowed_conclave_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_hallowed_conclave():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_key == "SHOOTING_PHASE":
            if player is not self.player or active_player is not self.player:
                return
            phase_name = "Shooting phase"
            stratagem_name = "POINT-BLANK PURGATION"
            candidates = self._hallowed_conclave_point_blank_purgation_candidates()
        elif phase_key == "FIGHT_PHASE":
            phase_name = "Fight phase"
            stratagem_name = "GIANTS OF THE BATTLEFIELD"
            candidates = self._hallowed_conclave_giants_of_the_battlefield_candidates()
        else:
            return
        if not candidates:
            return
        stratagem = self.get_by_name(stratagem_name)
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        name_u = str(stratagem.name or "").strip().upper()
        if name_u in self._used_stratagems_this_phase:
            return
        if self._warpbane_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
        ):
            return
        payload = {
            "event": "phase_start",
            "phase": phase_name,
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_hallowed_conclave_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if unit is None or not self._is_hallowed_conclave():
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        action_key = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        moving_root = self._gk_root(unit)
        if moving_root is None or not self._gk_is_alive(moving_root) or not self._gk_is_on_battlefield(moving_root):
            return

        if phase_name == "movement phase" and active_player is not self.player:
            if self._gk_owned_by_player(moving_root, self.player):
                return
            if action_key not in {"move", "normal_move", "advance", "fall_back", "fallback"}:
                return
            stratagem = self.get_by_name("PRECOGNITIVE STRATEGIES")
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
                return
            name_u = str(stratagem.name or "").strip().upper()
            if name_u in self._used_stratagems_this_phase:
                return
            candidates = self._hallowed_conclave_precognitive_strategies_candidates(enemy_unit=moving_root)
            if not candidates:
                return
            if self._warpbane_reaction_already_queued(
                event_name="unit_move_ended",
                stratagem_name=stratagem.name,
                phase_name="Movement phase",
                enemy_unit=moving_root,
            ):
                return
            payload = {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "enemy_unit": moving_root,
                "attacking_unit": moving_root,
                "moving_unit": moving_root,
                "action": action,
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)
            return

        if phase_name != "charge phase" or active_player is not self.player:
            return
        if not self._gk_owned_by_player(moving_root, self.player):
            return
        if action_key not in {"charge", "charge_move"}:
            return
        if bool(self._unit_cannot_be_target_of_stratagem(moving_root)):
            return
        if not self._is_gk_unit(moving_root) or not self._is_gk_terminator_unit(moving_root):
            return
        stratagem = self.get_by_name("GRIND THEM UNDERFOOT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        name_u = str(stratagem.name or "").strip().upper()
        if name_u in self._used_stratagems_this_phase:
            return
        enemy_candidates = self._hallowed_conclave_grind_them_underfoot_enemy_candidates(moving_root)
        if not enemy_candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_ended":
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != "charge phase":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("unit") is moving_root:
                return
        moving_id = self._gk_sort_key(moving_root)
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": moving_root,
            "target_unit": moving_root,
            "action": action,
            "candidates": [moving_root],
            "enemy_candidates_by_unit_id": {moving_id: enemy_candidates},
        }
        if len(enemy_candidates) == 1:
            payload["enemy_unit"] = enemy_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_hallowed_conclave_shooting_target_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_hallowed_conclave():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            return
        attacking_root = self._gk_root(attacking_unit)
        if attacking_root is None or self._gk_owned_by_player(attacking_root, self.player):
            return
        if not self._gk_is_alive(attacking_root) or not self._gk_is_on_battlefield(attacking_root):
            return
        candidates = self._hallowed_conclave_targeted_infantry_candidates(target_units)
        if not candidates:
            return
        for stratagem_name in ("SHINING RESOLVE", "UNENDING FIDELITY"):
            stratagem = self.get_by_name(stratagem_name)
            if stratagem is None:
                continue
            if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
                continue
            name_u = str(stratagem.name or "").strip().upper()
            if name_u in self._used_stratagems_this_phase:
                continue
            if self._warpbane_reaction_already_queued(
                event_name="shooting_targets_selected",
                stratagem_name=stratagem.name,
                phase_name="Shooting phase",
                enemy_unit=attacking_root,
            ):
                continue
            payload = {
                "event": "shooting_targets_selected",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "enemy_unit": attacking_root,
                "attacking_unit": attacking_root,
                "target_units": list(target_units or []),
                "candidates": candidates,
            }
            if len(candidates) == 1:
                payload["target_unit"] = candidates[0]
            self._queue_reaction(payload, use_timer=False)

    def _queue_hallowed_conclave_fight_target_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_hallowed_conclave():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacking_root = self._gk_root(attacking_unit)
        if attacking_root is None or self._gk_owned_by_player(attacking_root, self.player):
            return
        if not self._gk_is_alive(attacking_root) or not self._gk_is_on_battlefield(attacking_root):
            return
        stratagem = self.get_by_name("UNENDING FIDELITY")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        name_u = str(stratagem.name or "").strip().upper()
        if name_u in self._used_stratagems_this_phase:
            return
        candidates = self._hallowed_conclave_unending_fidelity_candidates(target_units=target_units)
        if not candidates:
            return
        if self._warpbane_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacking_root,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacking_root,
            "attacking_unit": attacking_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_augurium_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_augurium_task_force():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        keys_by_phase: dict[str, tuple[str, ...]] = {
            "SHOOTING_PHASE": (
                "augurium_aggressive_anticipation_active",
                "augurium_aggressive_anticipation_turn_owner",
                "augurium_aggressive_anticipation_turn",
                "augurium_aggressive_anticipation_expires_phase",
                "augurium_aggressive_anticipation_source",
                "augurium_appointed_hour_active",
                "augurium_appointed_hour_crit_threshold",
                "augurium_appointed_hour_turn_owner",
                "augurium_appointed_hour_turn",
                "augurium_appointed_hour_expires_phase",
                "augurium_appointed_hour_source",
            ),
            "FIGHT_PHASE": (
                "augurium_aggressive_anticipation_active",
                "augurium_aggressive_anticipation_turn_owner",
                "augurium_aggressive_anticipation_turn",
                "augurium_aggressive_anticipation_expires_phase",
                "augurium_aggressive_anticipation_source",
                "augurium_appointed_hour_active",
                "augurium_appointed_hour_crit_threshold",
                "augurium_appointed_hour_turn_owner",
                "augurium_appointed_hour_turn",
                "augurium_appointed_hour_expires_phase",
                "augurium_appointed_hour_source",
                "augurium_necessary_end_active",
                "augurium_necessary_end_threshold",
                "augurium_necessary_end_turn_owner",
                "augurium_necessary_end_turn",
                "augurium_necessary_end_expires_phase",
                "augurium_necessary_end_source",
            ),
        }
        keys = keys_by_phase.get(phase_name)
        if not keys:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in keys:
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if not changed:
                continue
            root.special_rules = sr
            self._gk_clear_ability_cache(root)

    def _cleanup_banishers_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_banishers():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        keys_by_phase: dict[str, tuple[str, ...]] = {
            "MOVEMENT_PHASE": (
                "banishers_circle_of_sanctuary_active",
                "banishers_circle_of_sanctuary_turn_owner",
                "banishers_circle_of_sanctuary_turn",
                "banishers_circle_of_sanctuary_expires_phase",
                "banishers_circle_of_sanctuary_source",
                "banishers_circle_of_sanctuary_range",
                "banishers_circle_of_sanctuary_source_model_id",
            ),
            "SHOOTING_PHASE": (
                "banishers_chaos_bane_active",
                "banishers_chaos_bane_turn_owner",
                "banishers_chaos_bane_turn",
                "banishers_chaos_bane_expires_phase",
                "banishers_chaos_bane_source",
            ),
            "FIGHT_PHASE": (
                "banishers_celerity_active",
                "banishers_celerity_turn_owner",
                "banishers_celerity_turn",
                "banishers_celerity_source",
            ),
        }
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in keys_by_phase.get(phase_name, ()):
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if "banishers_hexwrought_reprisal_phase" in sr:
                self._banishers_hexwrought_clear_tracking_on_root(root)
                sr = getattr(root, "special_rules", None)
                changed = True
            if changed:
                root.special_rules = sr
                self._gk_clear_ability_cache(root)

    @staticmethod
    def _warpbane_effect_is_active(
        sr: dict[str, Any],
        *,
        key: str,
        owner_key: str,
        turn_key: str,
        expires_key: str,
        player_id: str,
        turn: int,
        phase_name: str,
    ) -> bool:
        if not bool(sr.get(key)):
            return False
        owner = str(sr.get(owner_key, "") or "")
        if owner and player_id and owner != player_id:
            return False
        effect_turn = int(sr.get(turn_key, 0) or 0)
        if effect_turn and turn and effect_turn != turn:
            return False
        expires = str(sr.get(expires_key, "") or "").strip().upper()
        if expires and phase_name and expires != phase_name:
            return False
        return True

    def _iter_warpbane_active_fires_sources(self) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        game = getattr(self, "game", None)
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        player_id = str(getattr(self.player, "id", "") or "")
        sources: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if self._warpbane_effect_is_active(
                sr,
                key="fires_of_covenant_active",
                owner_key="fires_of_covenant_turn_owner",
                turn_key="fires_of_covenant_turn",
                expires_key="fires_of_covenant_expires_phase",
                player_id=player_id,
                turn=turn,
                phase_name=phase_name,
            ):
                sources.append(root)
        return sorted(sources, key=self._gk_sort_key)

    def _process_warpbane_fires_of_covenant_trigger(
        self,
        *,
        unit: Any,
        trigger_kind: str,
        action: str = "",
    ) -> None:
        if not self._is_warpbane_task_force() or unit is None:
            return
        game = getattr(self, "game", None)
        active_player = getattr(game, "get_current_player", lambda: None)() if game is not None else None
        if active_player is self.player:
            return
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "MOVEMENT_PHASE":
            return

        action_key = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        if trigger_kind == "move_end" and action_key not in ("move", "advance", "fall_back", "normal_move"):
            return

        enemy_root = self._gk_root(unit)
        if enemy_root is None or not self._gk_is_alive(enemy_root):
            return
        if not self._gk_is_on_battlefield(enemy_root):
            return
        if self._gk_owned_by_player(enemy_root, self.player):
            return

        sources = self._iter_warpbane_active_fires_sources()
        if not sources:
            return
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return
        mgr = self._get_gk_mgr()
        if mgr is None:
            return
        from ..utility.aura_utils import unit_within_range_of_unit

        for source in sources:
            if not unit_within_range_of_unit(source, enemy_root, 6.0, use_attached_aggregate=True):
                continue
            roll = int(dice_module.get_roll("D6") or 0)
            if bool(mgr.unit_wholly_within_hallowed_ground(source, game=game)):
                roll += 2
            if roll < 4:
                continue
            mortal_wounds = int(dice_module.get_roll("D3") or 0)
            if mortal_wounds <= 0:
                continue
            apply_mortals = getattr(source, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortals):
                apply_mortals(enemy_root, int(mortal_wounds), game_map=game_map)

    def _cleanup_warpbane_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_warpbane_task_force():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        keys_by_phase: dict[str, tuple[str, ...]] = {
            "SHOOTING_PHASE": (
                "aegis_eternal_active",
                "aegis_eternal_turn_owner",
                "aegis_eternal_turn",
                "aegis_eternal_expires_phase",
                "aegis_eternal_source",
                "sanctified_kill_zone_active",
                "sanctified_kill_zone_reroll_full",
                "sanctified_kill_zone_turn_owner",
                "sanctified_kill_zone_turn",
                "sanctified_kill_zone_expires_phase",
                "sanctified_kill_zone_source",
            ),
            "FIGHT_PHASE": (
                "sanctified_kill_zone_active",
                "sanctified_kill_zone_reroll_full",
                "sanctified_kill_zone_turn_owner",
                "sanctified_kill_zone_turn",
                "sanctified_kill_zone_expires_phase",
                "sanctified_kill_zone_source",
            ),
            "MOVEMENT_PHASE": (
                "fires_of_covenant_active",
                "fires_of_covenant_turn_owner",
                "fires_of_covenant_turn",
                "fires_of_covenant_expires_phase",
                "fires_of_covenant_source",
                "hallowed_beacon_deep_strike_min_distance",
                "hallowed_beacon_requires_hallowed_ground",
                "hallowed_beacon_turn_owner",
                "hallowed_beacon_turn",
                "hallowed_beacon_expires_phase",
                "hallowed_beacon_source",
            ),
            "CHARGE_PHASE": (
                "repelling_sphere_active",
                "repelling_sphere_turn_owner",
                "repelling_sphere_turn",
                "repelling_sphere_expires_phase",
                "repelling_sphere_source",
            ),
        }
        keys = keys_by_phase.get(phase_name)
        if not keys:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in keys:
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = sr

    def _cleanup_brotherhood_strike_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_brotherhood_strike():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        if phase_name == "MOVEMENT_PHASE":
            self._brotherhood_strike_duty_unending_candidates_by_enemy_id = {}
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            keys: tuple[str, ...] = ()
            if phase_name == "MOVEMENT_PHASE":
                keys = (
                    "combat_manifestation_deep_strike_min_distance",
                    "combat_manifestation_deep_strike_turn_owner",
                    "combat_manifestation_deep_strike_turn",
                    "combat_manifestation_deep_strike_expires_phase",
                    "combat_manifestation_source",
                )
            elif phase_name == "FIGHT_PHASE":
                keys = (
                    "brotherhood_strike_deep_strike_setup_active",
                    "brotherhood_strike_deep_strike_setup_turn",
                    "brotherhood_strike_deep_strike_setup_turn_owner",
                )
            for key in keys:
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if (
                phase_name == "SHOOTING_PHASE"
                and bool(sr.get("opponent_shooting_phase_stealth_active", False))
                and str(sr.get("opponent_shooting_phase_stealth_source", "") or "").strip().upper() == "SHINING VEIL"
            ):
                for key in (
                    "opponent_shooting_phase_stealth_active",
                    "opponent_shooting_phase_stealth_owner",
                    "opponent_shooting_phase_stealth_turn",
                    "opponent_shooting_phase_stealth_source",
                    "opponent_shooting_phase_stealth_expires_phase",
                ):
                    if key in sr:
                        sr.pop(key, None)
                        changed = True
            if changed:
                root.special_rules = sr
                self._gk_clear_ability_cache(root)

    def _cleanup_hallowed_conclave_phase_end_effects(self, *, phase: Any) -> None:
        if not self._is_hallowed_conclave():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name not in {"SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        keys_by_phase: dict[str, tuple[str, ...]] = {
            "SHOOTING_PHASE": (
                "hallowed_conclave_shining_resolve_active",
                "hallowed_conclave_shining_resolve_turn_owner",
                "hallowed_conclave_shining_resolve_turn",
                "hallowed_conclave_shining_resolve_expires_phase",
                "hallowed_conclave_shining_resolve_source",
                "hallowed_conclave_unending_fidelity_active",
                "hallowed_conclave_unending_fidelity_mode",
                "hallowed_conclave_unending_fidelity_threshold",
                "hallowed_conclave_unending_fidelity_turn_owner",
                "hallowed_conclave_unending_fidelity_turn",
                "hallowed_conclave_unending_fidelity_expires_phase",
                "hallowed_conclave_unending_fidelity_source",
            ),
            "FIGHT_PHASE": (
                "hallowed_conclave_unending_fidelity_active",
                "hallowed_conclave_unending_fidelity_mode",
                "hallowed_conclave_unending_fidelity_threshold",
                "hallowed_conclave_unending_fidelity_turn_owner",
                "hallowed_conclave_unending_fidelity_turn",
                "hallowed_conclave_unending_fidelity_expires_phase",
                "hallowed_conclave_unending_fidelity_source",
            ),
        }
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        keys = keys_by_phase.get(phase_name, ())
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._gk_root(unit)
            if root is None:
                continue
            uid = self._gk_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in keys:
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if not changed:
                continue
            root.special_rules = sr
            self._gk_clear_ability_cache(root)

    def _use_grey_knights_warpbane_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "AGGRESSIVE ANTICIPATION":
            return self._use_augurium_aggressive_anticipation(stratagem, **kwargs)
        if name_u == "APPOINTED HOUR":
            return self._use_augurium_appointed_hour(stratagem, **kwargs)
        if name_u == "CELERITY":
            return self._use_banishers_celerity(stratagem, **kwargs)
        if name_u == "CHAOS BANE":
            return self._use_banishers_chaos_bane(stratagem, **kwargs)
        if name_u == "CIRCLE OF SANCTUARY":
            return self._use_banishers_circle_of_sanctuary(stratagem, **kwargs)
        if name_u == "COMBAT MANIFESTATION":
            return self._use_brotherhood_strike_combat_manifestation(stratagem, **kwargs)
        if name_u == "DUTY UNENDING":
            return self._use_brotherhood_strike_duty_unending(stratagem, **kwargs)
        if name_u == "EXPEDITIOUS EXIT":
            return self._use_brotherhood_strike_expeditious_exit(stratagem, **kwargs)
        if name_u == "GIANTS OF THE BATTLEFIELD":
            return self._use_hallowed_conclave_giants_of_the_battlefield(stratagem, **kwargs)
        if name_u == "GRIND THEM UNDERFOOT":
            return self._use_hallowed_conclave_grind_them_underfoot(stratagem, **kwargs)
        if name_u == "HEXWROUGHT REPRISAL":
            return self._use_banishers_hexwrought_reprisal(stratagem, **kwargs)
        if name_u == "POINT-BLANK PURGATION":
            return self._use_hallowed_conclave_point_blank_purgation(stratagem, **kwargs)
        if name_u == "PRECOGNITIVE STRATEGIES":
            return self._use_hallowed_conclave_precognitive_strategies(stratagem, **kwargs)
        if name_u == "MIRAGE OF ECHOES":
            return self._use_augurium_mirage_of_echoes(stratagem, **kwargs)
        if name_u == "NECESSARY END":
            return self._use_augurium_necessary_end(stratagem, **kwargs)
        if name_u == "PURGATION PATTERN":
            return self._use_brotherhood_strike_purgation_pattern(stratagem, **kwargs)
        if name_u == "REDIRECTED STRIKE":
            return self._use_augurium_redirected_strike(stratagem, **kwargs)
        if name_u == "SHADOW OF ANARCH":
            return self._use_banishers_shadow_of_anarch(stratagem, **kwargs)
        if name_u == "SHINING RESOLVE":
            return self._use_hallowed_conclave_shining_resolve(stratagem, **kwargs)
        if name_u == "SHINING VEIL":
            return self._use_brotherhood_strike_shining_veil(stratagem, **kwargs)
        if name_u == "TRUESILVER CHANNELLING":
            return self._use_brotherhood_strike_truesilver_channelling(stratagem, **kwargs)
        if name_u == "UNENDING FIDELITY":
            return self._use_hallowed_conclave_unending_fidelity(stratagem, **kwargs)
        if name_u == "WARDING CHANT":
            return self._use_banishers_warding_chant(stratagem, **kwargs)
        if name_u == "SANCTIFIED KILL ZONE":
            return self._use_warpbane_sanctified_kill_zone(stratagem, **kwargs)
        if name_u == "HALLOWED BEACON":
            return self._use_warpbane_hallowed_beacon(stratagem, **kwargs)
        if name_u == "AEGIS ETERNAL":
            return self._use_warpbane_aegis_eternal(stratagem, **kwargs)
        if name_u == "FIRES OF COVENANT":
            return self._use_warpbane_fires_of_covenant(stratagem, **kwargs)
        if name_u == "REPELLING SPHERE":
            return self._use_warpbane_repelling_sphere(stratagem, **kwargs)
        if name_u == "FLAMES OF SANCTITY":
            return self._use_warpbane_flames_of_sanctity(stratagem, **kwargs)
        return None

    def _use_augurium_aggressive_anticipation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_augurium_task_force():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: AGGRESSIVE ANTICIPATION: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: AGGRESSIVE ANTICIPATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: AGGRESSIVE ANTICIPATION: not your Shooting phase")
            return False
        eligible = candidates or self._augurium_phase_candidates(
            phase_name="Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        )
        if eligible and root not in eligible:
            logger.error("ERROR: AGGRESSIVE ANTICIPATION: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: AGGRESSIVE ANTICIPATION: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: AGGRESSIVE ANTICIPATION: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root):
            logger.error("ERROR: AGGRESSIVE ANTICIPATION: target must be a GREY KNIGHTS PSYKER unit")
            return False
        if self._gk_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name=phase_name):
            logger.error("ERROR: AGGRESSIVE ANTICIPATION: target has already been selected this phase")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = dict(getattr(root, "special_rules", None) or {})
        sr["augurium_aggressive_anticipation_active"] = True
        sr["augurium_aggressive_anticipation_turn_owner"] = str(
            getattr(active_player, "id", "") or getattr(self.player, "id", "") or ""
        )
        sr["augurium_aggressive_anticipation_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["augurium_aggressive_anticipation_expires_phase"] = (
            "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        )
        sr["augurium_aggressive_anticipation_source"] = (
            str(getattr(stratagem, "name", "") or "AGGRESSIVE ANTICIPATION").strip()
            or "AGGRESSIVE ANTICIPATION"
        )
        root.special_rules = sr
        self._gk_clear_ability_cache(root)
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: AGGRESSIVE ANTICIPATION: %s can ignore WS/BS and Hit roll modifiers this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_augurium_appointed_hour(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_augurium_task_force():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: APPOINTED HOUR: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: APPOINTED HOUR: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: APPOINTED HOUR: not your Shooting phase")
            return False
        eligible = candidates or self._augurium_phase_candidates(
            phase_name="Shooting phase" if phase_name == "shooting phase" else "Fight phase"
        )
        if eligible and root not in eligible:
            logger.error("ERROR: APPOINTED HOUR: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: APPOINTED HOUR: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: APPOINTED HOUR: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root):
            logger.error("ERROR: APPOINTED HOUR: target must be a GREY KNIGHTS PSYKER unit")
            return False
        if self._gk_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name=phase_name):
            logger.error("ERROR: APPOINTED HOUR: target has already been selected this phase")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = dict(getattr(root, "special_rules", None) or {})
        sr["augurium_appointed_hour_active"] = True
        sr["augurium_appointed_hour_crit_threshold"] = 5
        sr["augurium_appointed_hour_turn_owner"] = str(
            getattr(active_player, "id", "") or getattr(self.player, "id", "") or ""
        )
        sr["augurium_appointed_hour_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["augurium_appointed_hour_expires_phase"] = (
            "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        )
        sr["augurium_appointed_hour_source"] = str(getattr(stratagem, "name", "") or "APPOINTED HOUR").strip() or "APPOINTED HOUR"
        root.special_rules = sr
        self._gk_clear_ability_cache(root)
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: APPOINTED HOUR: %s scores critical hits on unmodified Hit rolls of 5+ this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_augurium_necessary_end(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_augurium_task_force():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        if (unit is None or attacking_unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "NECESSARY END":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not target_units:
                    target_units = list(reaction.get("target_units") or [])
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if "phase_name" not in kwargs:
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: NECESSARY END: no target unit provided")
            return False
        if attacking_unit is None:
            logger.error("ERROR: NECESSARY END: missing enemy attacking unit")
            return False
        root = self._gk_root(unit)
        attacking_root = self._gk_root(attacking_unit)
        if root is None or attacking_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: NECESSARY END: wrong phase")
            return False
        if self._gk_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: NECESSARY END: trigger requires an enemy attacking unit")
            return False
        eligible = candidates or self._augurium_necessary_end_candidates(target_units)
        if eligible and root not in eligible:
            logger.error("ERROR: NECESSARY END: target unit was not selected as an attack target")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: NECESSARY END: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: NECESSARY END: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_infantry_unit(root):
            logger.error("ERROR: NECESSARY END: target must be a GREY KNIGHTS INFANTRY unit")
            return False
        if target_units and root not in [self._gk_root(target) for target in list(target_units or [])]:
            logger.error("ERROR: NECESSARY END: target was not selected as an attack target")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        try:
            current_battle_round = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        except (TypeError, ValueError):
            current_battle_round = 0
        threshold = int(current_battle_round) + 1
        sr = dict(getattr(root, "special_rules", None) or {})
        sr["augurium_necessary_end_active"] = True
        sr["augurium_necessary_end_threshold"] = int(threshold)
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        sr["augurium_necessary_end_turn_owner"] = str(
            getattr(active_player, "id", "") or getattr(self.player, "id", "") or ""
        )
        sr["augurium_necessary_end_turn"] = int(current_battle_round)
        sr["augurium_necessary_end_expires_phase"] = "FIGHT_PHASE"
        sr["augurium_necessary_end_source"] = str(getattr(stratagem, "name", "") or "NECESSARY END").strip() or "NECESSARY END"
        root.special_rules = sr
        self._gk_clear_ability_cache(root)
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: NECESSARY END: %s can fight on death on %d+ this phase.",
            getattr(root, "name", "Unit"),
            int(threshold),
        )
        return True

    def _use_augurium_redirected_strike(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_augurium_task_force():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: REDIRECTED STRIKE: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: REDIRECTED STRIKE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: REDIRECTED STRIKE: not your turn")
            return False
        eligible = candidates or self._augurium_redirected_strike_candidates()
        if eligible and root not in eligible:
            logger.error("ERROR: REDIRECTED STRIKE: target is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: REDIRECTED STRIKE: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: REDIRECTED STRIKE: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root):
            logger.error("ERROR: REDIRECTED STRIKE: target must be a GREY KNIGHTS PSYKER unit")
            return False
        if not self._gk_has_deep_strike(root):
            logger.error("ERROR: REDIRECTED STRIKE: target must have Deep Strike")
            return False
        if self._gk_has_enemy_within_engagement_range(root):
            logger.error("ERROR: REDIRECTED STRIKE: target is within Engagement Range")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        if not self._gk_place_unit_into_strategic_reserves(root, reason=str(getattr(stratagem, "name", "") or "")):
            logger.error("ERROR: REDIRECTED STRIKE: failed to place target into Strategic Reserves")
            return False
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REDIRECTED STRIKE: %s entered Strategic Reserves.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_augurium_mirage_of_echoes(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_augurium_task_force():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit")
        candidates = list(kwargs.get("candidates") or [])
        if (unit is None or enemy_unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "MIRAGE OF ECHOES":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if "phase_name" not in kwargs:
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MIRAGE OF ECHOES: no target unit provided")
            return False
        if enemy_unit is None:
            logger.error("ERROR: MIRAGE OF ECHOES: missing enemy setup context")
            return False

        root = self._gk_root(unit)
        enemy_root = self._gk_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: MIRAGE OF ECHOES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: MIRAGE OF ECHOES: not opponent's Movement phase")
            return False
        if self._gk_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: MIRAGE OF ECHOES: enemy setup context is invalid")
            return False
        eligible = candidates or self._augurium_mirage_of_echoes_candidates(enemy_unit=enemy_root)
        if eligible and root not in eligible:
            logger.error("ERROR: MIRAGE OF ECHOES: target is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: MIRAGE OF ECHOES: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: MIRAGE OF ECHOES: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root):
            logger.error("ERROR: MIRAGE OF ECHOES: target must be a GREY KNIGHTS PSYKER unit")
            return False
        if not self._gk_has_deep_strike(root):
            logger.error("ERROR: MIRAGE OF ECHOES: target must have Deep Strike")
            return False
        if self._gk_has_enemy_within_engagement_range(root):
            logger.error("ERROR: MIRAGE OF ECHOES: target is within Engagement Range")
            return False
        if not self._gk_is_alive(enemy_root) or not self._gk_is_on_battlefield(enemy_root):
            logger.error("ERROR: MIRAGE OF ECHOES: enemy setup unit is no longer on the battlefield")
            return False
        from ..utility.aura_utils import unit_within_range_of_unit

        if not unit_within_range_of_unit(root, enemy_root, 12.0, use_attached_aggregate=True):
            logger.error("ERROR: MIRAGE OF ECHOES: target must be within 12\" of the enemy setup unit")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        if not self._gk_place_unit_into_strategic_reserves(root, reason=str(getattr(stratagem, "name", "") or "")):
            logger.error("ERROR: MIRAGE OF ECHOES: failed to place target into Strategic Reserves")
            return False
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MIRAGE OF ECHOES: %s entered Strategic Reserves.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_banishers_celerity(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_banishers():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = None
        if unit is None or not candidates:
            pending = self._gk_pending_reaction_by_name("CELERITY")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CELERITY: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: CELERITY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CELERITY: not your Charge phase")
            return False
        eligible = candidates or self._banishers_celerity_candidates()
        if eligible and root not in [self._gk_root(candidate) for candidate in list(eligible or [])]:
            logger.error("ERROR: CELERITY: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: CELERITY: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CELERITY: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root) or not self._is_gk_infantry_unit(root):
            logger.error("ERROR: CELERITY: target must be a GREY KNIGHTS PSYKER INFANTRY unit")
            return False
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "advanced_this_round", False)):
            logger.error("ERROR: CELERITY: target must have Advanced this round")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = dict(getattr(root, "special_rules", None) or {})
        sr["banishers_celerity_active"] = True
        sr["banishers_celerity_turn_owner"] = self._gk_current_turn_owner_id()
        sr["banishers_celerity_turn"] = self._gk_current_turn()
        sr["banishers_celerity_source"] = str(getattr(stratagem, "name", "") or "CELERITY").strip() or "CELERITY"
        root.special_rules = sr
        self._gk_clear_ability_cache(root)
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CELERITY: %s can declare a charge after Advancing this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_banishers_chaos_bane(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_banishers():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = None
        if unit is None or not candidates:
            pending = self._gk_pending_reaction_by_name("CHAOS BANE")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CHAOS BANE: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CHAOS BANE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CHAOS BANE: not your Shooting phase")
            return False
        eligible = candidates or self._banishers_chaos_bane_candidates()
        if eligible and root not in [self._gk_root(candidate) for candidate in list(eligible or [])]:
            logger.error("ERROR: CHAOS BANE: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: CHAOS BANE: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CHAOS BANE: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root):
            logger.error("ERROR: CHAOS BANE: target must be a GREY KNIGHTS PSYKER unit")
            return False
        if self._gk_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name="shooting phase"):
            logger.error("ERROR: CHAOS BANE: target has already been selected to shoot this phase")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = dict(getattr(root, "special_rules", None) or {})
        sr["banishers_chaos_bane_active"] = True
        sr["banishers_chaos_bane_turn_owner"] = self._gk_current_turn_owner_id()
        sr["banishers_chaos_bane_turn"] = self._gk_current_turn()
        sr["banishers_chaos_bane_expires_phase"] = "SHOOTING_PHASE"
        sr["banishers_chaos_bane_source"] = str(getattr(stratagem, "name", "") or "CHAOS BANE").strip() or "CHAOS BANE"
        root.special_rules = sr
        self._gk_clear_ability_cache(root)
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CHAOS BANE: %s gains [ANTI-CHAOS 4+] on ranged weapons this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_banishers_circle_of_sanctuary(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_banishers():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("source_unit")
        target_model = kwargs.get("model") or kwargs.get("target_model")
        candidates = list(kwargs.get("candidates") or [])
        pending = None
        if unit is None or not candidates:
            pending = self._gk_pending_reaction_by_name("CIRCLE OF SANCTUARY")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit") or pending.get("source_unit")
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if target_model is None and pending is not None:
            target_model = pending.get("model") or pending.get("target_model")
        if target_model is not None and unit is None:
            unit = getattr(target_model, "parent_unit", None)
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CIRCLE OF SANCTUARY: no target Character unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: CIRCLE OF SANCTUARY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: CIRCLE OF SANCTUARY: only usable in your opponent's Movement phase")
            return False
        eligible = candidates or self._banishers_circle_of_sanctuary_candidates()
        if unit not in eligible:
            matching = [candidate for candidate in list(eligible or []) if self._gk_root(candidate) is root]
            if len(matching) == 1:
                unit = matching[0]
            else:
                logger.error("ERROR: CIRCLE OF SANCTUARY: selected Character is not currently eligible")
                return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: CIRCLE OF SANCTUARY: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CIRCLE OF SANCTUARY: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._gk_is_character_unit(unit):
            logger.error("ERROR: CIRCLE OF SANCTUARY: target must be a GREY KNIGHTS CHARACTER model")
            return False
        alive_models = self._gk_alive_models(unit)
        if target_model is None and len(alive_models) == 1:
            target_model = alive_models[0]
        if target_model is None:
            logger.error("ERROR: CIRCLE OF SANCTUARY: no target Character model provided")
            return False
        if target_model not in alive_models:
            logger.error("ERROR: CIRCLE OF SANCTUARY: selected model is not an alive model in the chosen unit")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = dict(getattr(root, "special_rules", None) or {})
        sr["banishers_circle_of_sanctuary_active"] = True
        sr["banishers_circle_of_sanctuary_turn_owner"] = self._gk_current_turn_owner_id()
        sr["banishers_circle_of_sanctuary_turn"] = self._gk_current_turn()
        sr["banishers_circle_of_sanctuary_expires_phase"] = "MOVEMENT_PHASE"
        sr["banishers_circle_of_sanctuary_source"] = (
            str(getattr(stratagem, "name", "") or "CIRCLE OF SANCTUARY").strip() or "CIRCLE OF SANCTUARY"
        )
        sr["banishers_circle_of_sanctuary_range"] = 12.0
        sr["banishers_circle_of_sanctuary_source_model_id"] = self._gk_sort_key(target_model)
        root.special_rules = sr
        self._gk_clear_ability_cache(root)
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CIRCLE OF SANCTUARY: %s projects a 12\" horizontal Reinforcements denial aura this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_banishers_shadow_of_anarch(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_banishers():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit")
        action = kwargs.get("action")
        candidates = list(kwargs.get("candidates") or [])
        pending = None
        if unit is None or enemy_unit is None or not candidates or action is None:
            pending = self._gk_pending_reaction_by_name("SHADOW OF ANARCH")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if enemy_unit is None and pending is not None:
            enemy_unit = pending.get("enemy_unit") or pending.get("attacking_unit")
        if action is None and pending is not None:
            action = pending.get("action")
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SHADOW OF ANARCH: no target unit provided")
            return False
        if enemy_unit is None:
            logger.error("ERROR: SHADOW OF ANARCH: missing enemy movement trigger unit")
            return False
        root = self._gk_root(unit)
        enemy_root = self._gk_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: SHADOW OF ANARCH: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SHADOW OF ANARCH: only usable in your opponent's Movement phase")
            return False
        if self._gk_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: SHADOW OF ANARCH: trigger unit must be an enemy unit")
            return False
        action_key = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        if action_key not in {"move", "normal_move", "advance", "fall_back", "fallback"}:
            logger.error("ERROR: SHADOW OF ANARCH: invalid trigger action")
            return False
        eligible = candidates or self._banishers_shadow_of_anarch_candidates(enemy_unit=enemy_root)
        if eligible and root not in [self._gk_root(candidate) for candidate in list(eligible or [])]:
            logger.error("ERROR: SHADOW OF ANARCH: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: SHADOW OF ANARCH: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SHADOW OF ANARCH: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root):
            logger.error("ERROR: SHADOW OF ANARCH: target must be a GREY KNIGHTS PSYKER unit")
            return False
        if self._gk_has_enemy_within_engagement_range(root):
            logger.error("ERROR: SHADOW OF ANARCH: target cannot be within Engagement Range")
            return False
        from ..utility.aura_utils import unit_within_range_of_unit

        if not unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True):
            logger.error("ERROR: SHADOW OF ANARCH: target must be within 9\" of the triggering enemy unit")
            return False
        choice_key = self._normalize_banishers_shadow_choice(
            kwargs.get("choice_key")
            or kwargs.get("choice")
            or kwargs.get("key")
            or kwargs.get("selection")
            or (pending.get("choice_key") if isinstance(pending, dict) else "")
        )
        allowed_choice_keys = self._banishers_shadow_of_anarch_choice_keys(root)
        if not choice_key and len(allowed_choice_keys) == 1:
            choice_key = allowed_choice_keys[0]
        if choice_key not in allowed_choice_keys:
            logger.error("ERROR: SHADOW OF ANARCH: choice must be one of %s", ", ".join(allowed_choice_keys))
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        if choice_key == "STRATEGIC_RESERVES":
            if not self._gk_place_unit_into_strategic_reserves(root, reason=str(getattr(stratagem, "name", "") or "")):
                logger.error("ERROR: SHADOW OF ANARCH: failed to place target into Strategic Reserves")
                return False
            self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                "INFO: SHADOW OF ANARCH: %s entered Strategic Reserves.",
                getattr(root, "name", "Unit"),
            )
            return True
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: SHADOW OF ANARCH: reactive move queue unavailable")
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=6,
            kind="grey_knights_shadow_of_anarch",
            movement_type="move",
            reactive_movement_type="shadow_of_anarch",
            source=str(getattr(stratagem, "name", "") or "SHADOW OF ANARCH"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            range_value=9,
        )
        if request is None:
            logger.error("ERROR: SHADOW OF ANARCH: failed to queue reactive move")
            return False
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SHADOW OF ANARCH: %s can make a Normal move of up to 6\".",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_banishers_warding_chant(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_banishers():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        pending = None
        if unit is None or attacking_unit is None or not candidates:
            pending = self._gk_pending_reaction_by_name("WARDING CHANT")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if attacking_unit is None and pending is not None:
            attacking_unit = pending.get("attacking_unit") or pending.get("enemy_unit")
        if not target_units and pending is not None:
            target_units = list(pending.get("target_units") or [])
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: WARDING CHANT: no target unit provided")
            return False
        if attacking_unit is None:
            logger.error("ERROR: WARDING CHANT: missing enemy attacking unit")
            return False
        root = self._gk_root(unit)
        attacking_root = self._gk_root(attacking_unit)
        if root is None or attacking_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: WARDING CHANT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: WARDING CHANT: only usable in your opponent's Shooting phase")
            return False
        if self._gk_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: WARDING CHANT: trigger requires an enemy attacking unit")
            return False
        eligible = candidates or self._banishers_warding_chant_candidates(target_units)
        if eligible and root not in [self._gk_root(candidate) for candidate in list(eligible or [])]:
            logger.error("ERROR: WARDING CHANT: target unit was not selected as an attack target")
            return False
        if target_units and root not in [self._gk_root(target) for target in list(target_units or [])]:
            logger.error("ERROR: WARDING CHANT: target unit was not selected as an attack target")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: WARDING CHANT: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: WARDING CHANT: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root):
            logger.error("ERROR: WARDING CHANT: target must be a GREY KNIGHTS PSYKER unit")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        phase_key = self._gk_phase_key(getattr(getattr(self.game, "phase", None), "name", "") or phase_name)
        source_name = str(getattr(stratagem, "name", "") or "WARDING CHANT").strip() or "WARDING CHANT"
        for model in list(self._gk_alive_models(root) or []):
            set_temporary_fnp = getattr(model, "set_temporary_fnp", None)
            if not callable(set_temporary_fnp):
                continue
            set_temporary_fnp(
                key=f"banishers_warding_chant:{self._gk_current_turn()}:{phase_key}:{self._gk_sort_key(model)}",
                value=5,
                source=source_name,
                condition="against attacks with an unmodified Damage characteristic of 1",
                expires_phase=phase_key,
            )
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: WARDING CHANT: %s gains Feel No Pain 5+ against attacks with Damage 1 this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_banishers_hexwrought_reprisal(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_banishers():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_candidates_by_unit_id = dict(kwargs.get("enemy_candidates_by_unit_id") or {})
        mortal_wounds_by_unit_id = dict(kwargs.get("mortal_wounds_by_unit_id") or {})
        pending = None
        if unit is None or (enemy_unit is None and not enemy_candidates_by_unit_id) or not candidates:
            pending = self._gk_pending_reaction_by_name("HEXWROUGHT REPRISAL")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if enemy_unit is None and pending is not None:
            enemy_unit = pending.get("enemy_unit") or pending.get("attacking_unit")
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if not enemy_candidates_by_unit_id and pending is not None:
            enemy_candidates_by_unit_id = dict(pending.get("enemy_candidates_by_unit_id") or {})
        if not mortal_wounds_by_unit_id and pending is not None:
            mortal_wounds_by_unit_id = dict(pending.get("mortal_wounds_by_unit_id") or {})
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: HEXWROUGHT REPRISAL: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        if not phase_name:
            phase_name = str(getattr(getattr(self.game, "phase", None), "name", "") or "")
        eligible = candidates or self._banishers_hexwrought_candidates(phase_name=phase_name)
        if eligible and root not in [self._gk_root(candidate) for candidate in list(eligible or [])]:
            logger.error("ERROR: HEXWROUGHT REPRISAL: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: HEXWROUGHT REPRISAL: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: HEXWROUGHT REPRISAL: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root):
            logger.error("ERROR: HEXWROUGHT REPRISAL: target must be a GREY KNIGHTS PSYKER unit")
            return False
        root_id = self._gk_sort_key(root)
        enemy_candidates = list(enemy_candidates_by_unit_id.get(root_id) or [])
        if not enemy_candidates:
            enemy_candidates = self._banishers_hexwrought_enemy_candidates(root)
        if enemy_unit is None and len(enemy_candidates) == 1:
            enemy_unit = enemy_candidates[0]
        if enemy_unit is None:
            logger.error("ERROR: HEXWROUGHT REPRISAL: no enemy unit provided")
            return False
        enemy_root = self._gk_root(enemy_unit)
        if enemy_root is None:
            return False
        if enemy_candidates and enemy_root not in [self._gk_root(candidate) for candidate in list(enemy_candidates or [])]:
            logger.error("ERROR: HEXWROUGHT REPRISAL: selected enemy unit did not inflict mortal wounds on the target")
            return False
        if self._gk_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: HEXWROUGHT REPRISAL: selected enemy unit is invalid")
            return False
        if not self._gk_is_alive(enemy_root) or not self._gk_is_on_battlefield(enemy_root):
            logger.error("ERROR: HEXWROUGHT REPRISAL: selected enemy unit is no longer on the battlefield")
            return False
        try:
            mortal_wounds_suffered = int(mortal_wounds_by_unit_id.get(root_id, 0) or 0)
        except (TypeError, ValueError):
            mortal_wounds_suffered = 0
        if mortal_wounds_suffered <= 0:
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                try:
                    mortal_wounds_suffered = int(
                        sr.get("banishers_hexwrought_reprisal_total_mortal_wounds", 0) or 0
                    )
                except (TypeError, ValueError):
                    mortal_wounds_suffered = 0
        if mortal_wounds_suffered <= 0:
            logger.error("ERROR: HEXWROUGHT REPRISAL: target unit did not suffer mortal wounds this phase")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        successes = 0
        for _ in range(int(mortal_wounds_suffered)):
            roll = int(dice_module.get_roll("D6") or 0)
            if roll >= 2:
                successes += 1
        mortal_wounds = min(6, int(successes))
        if mortal_wounds > 0:
            apply_mortals = getattr(root, "_apply_mortal_wounds_to_unit", None)
            if not callable(apply_mortals):
                logger.error("ERROR: HEXWROUGHT REPRISAL: mortal wound application helper unavailable")
                return False
            apply_mortals(
                enemy_root,
                int(mortal_wounds),
                game_map=getattr(self.game, "map", None) if self.game is not None else None,
                attacker_unit=root,
                attacker_model=None,
                is_psychic_attack=True,
                damage_source=str(getattr(stratagem, "name", "") or "HEXWROUGHT REPRISAL"),
            )
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: HEXWROUGHT REPRISAL: %s inflicted %d psychic mortal wound(s) on %s.",
            getattr(root, "name", "Unit"),
            int(mortal_wounds),
            getattr(enemy_root, "name", "Unit"),
        )
        return True

    def _use_hallowed_conclave_giants_of_the_battlefield(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_conclave():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = None
        if unit is None or not candidates:
            pending = self._gk_pending_reaction_by_name("GIANTS OF THE BATTLEFIELD")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: GIANTS OF THE BATTLEFIELD: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: GIANTS OF THE BATTLEFIELD: wrong phase")
            return False
        eligible = candidates or self._hallowed_conclave_giants_of_the_battlefield_candidates()
        if eligible and root not in eligible:
            logger.error("ERROR: GIANTS OF THE BATTLEFIELD: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: GIANTS OF THE BATTLEFIELD: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: GIANTS OF THE BATTLEFIELD: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_terminator_unit(root):
            logger.error("ERROR: GIANTS OF THE BATTLEFIELD: target must be a GREY KNIGHTS TERMINATOR unit")
            return False
        if self._gk_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name="fight phase"):
            logger.error("ERROR: GIANTS OF THE BATTLEFIELD: target has already been selected to fight this phase")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        source_name = str(getattr(stratagem, "name", "") or "GIANTS OF THE BATTLEFIELD").strip()
        source_name = source_name or "GIANTS OF THE BATTLEFIELD"
        self._gk_apply_temporary_weapon_bonuses(
            root,
            key_prefix="hallowed_conclave_giants_of_the_battlefield",
            expires_phase="FIGHT_PHASE",
            source=source_name,
            weapon_filter=lambda wargear: bool(
                callable(getattr(wargear, "is_melee", None)) and wargear.is_melee()
            ),
            attacks_bonus=1,
        )
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: GIANTS OF THE BATTLEFIELD: %s gains +1 Attacks on melee weapons until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_hallowed_conclave_point_blank_purgation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_conclave():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        pending = None
        if unit is None or not candidates:
            pending = self._gk_pending_reaction_by_name("POINT-BLANK PURGATION")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: POINT-BLANK PURGATION: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: POINT-BLANK PURGATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: POINT-BLANK PURGATION: only usable in your Shooting phase")
            return False
        eligible = candidates or self._hallowed_conclave_point_blank_purgation_candidates()
        if eligible and root not in eligible:
            logger.error("ERROR: POINT-BLANK PURGATION: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: POINT-BLANK PURGATION: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: POINT-BLANK PURGATION: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_infantry_unit(root):
            logger.error("ERROR: POINT-BLANK PURGATION: target must be a GREY KNIGHTS INFANTRY unit")
            return False
        if self._gk_unit_already_selected_to_shoot_or_fight_this_phase(root, phase_name="shooting phase"):
            logger.error("ERROR: POINT-BLANK PURGATION: target has already been selected to shoot this phase")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        source_name = str(getattr(stratagem, "name", "") or "POINT-BLANK PURGATION").strip()
        source_name = source_name or "POINT-BLANK PURGATION"
        self._gk_apply_temporary_weapon_keyword_bonuses(
            root,
            key_prefix="hallowed_conclave_point_blank_purgation",
            keywords=["PISTOL", "TWIN-LINKED"],
            expires_phase="SHOOTING_PHASE",
            attack_type="ranged",
            source=source_name,
            weapon_filter=lambda wargear: self._gk_wargear_name_contains(wargear, needle="storm bolter"),
        )
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: POINT-BLANK PURGATION: %s gains [PISTOL] and [TWIN-LINKED] on storm bolters until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_hallowed_conclave_precognitive_strategies(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_conclave():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit") or kwargs.get("moving_unit")
        action = kwargs.get("action")
        candidates = list(kwargs.get("candidates") or [])
        pending = None
        if unit is None or enemy_unit is None or not candidates:
            pending = self._gk_pending_reaction_by_name("PRECOGNITIVE STRATEGIES")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if enemy_unit is None and pending is not None:
            enemy_unit = pending.get("enemy_unit") or pending.get("attacking_unit") or pending.get("moving_unit")
        if action is None and pending is not None:
            action = pending.get("action")
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: no target unit provided")
            return False
        if enemy_unit is None:
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: missing triggering enemy unit")
            return False
        root = self._gk_root(unit)
        enemy_root = self._gk_root(enemy_unit)
        if root is None or enemy_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: only usable in your opponent's Movement phase")
            return False
        if self._gk_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: trigger unit must be an enemy unit")
            return False
        action_key = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        if action_key not in {"move", "normal_move", "advance", "fall_back", "fallback"}:
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: invalid trigger move type")
            return False
        eligible = candidates or self._hallowed_conclave_precognitive_strategies_candidates(enemy_unit=enemy_root)
        if eligible and root not in eligible:
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_infantry_unit(root):
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: target must be a GREY KNIGHTS INFANTRY unit")
            return False
        if self._gk_has_enemy_within_engagement_range(root):
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: target cannot be within Engagement Range")
            return False
        from ..utility.aura_utils import unit_within_range_of_unit

        if not unit_within_range_of_unit(root, enemy_root, 9.0, use_attached_aggregate=True):
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: target must be within 9\" of the triggering enemy unit")
            return False
        queue_move = getattr(self.game, "_queue_reactive_move_movement_decision", None) if self.game is not None else None
        if not callable(queue_move):
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: reactive move queue unavailable")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        max_distance = int(dice_module.get_roll("D6") or 0)
        if max_distance <= 0:
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: failed to determine reactive move distance")
            return False
        request = queue_move(
            player=self.player,
            unit=root,
            max_distance=int(max_distance),
            kind="hallowed_conclave_precognitive_strategies",
            movement_type="move",
            reactive_movement_type="move",
            source=str(getattr(stratagem, "name", "") or "PRECOGNITIVE STRATEGIES"),
            moving_unit=enemy_root,
            attacker_unit=enemy_root,
            allow_skip=True,
        )
        if request is None:
            logger.error("ERROR: PRECOGNITIVE STRATEGIES: failed to queue reactive move")
            return False
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PRECOGNITIVE STRATEGIES: %s can make a reactive Normal move up to %d\".",
            getattr(root, "name", "Unit"),
            int(max_distance),
        )
        return True

    def _use_hallowed_conclave_shining_resolve(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_conclave():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        pending = None
        if unit is None or attacking_unit is None or not candidates:
            pending = self._gk_pending_reaction_by_name("SHINING RESOLVE")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if attacking_unit is None and pending is not None:
            attacking_unit = pending.get("attacking_unit") or pending.get("enemy_unit")
        if not target_units and pending is not None:
            target_units = list(pending.get("target_units") or [])
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SHINING RESOLVE: no target unit provided")
            return False
        if attacking_unit is None:
            logger.error("ERROR: SHINING RESOLVE: missing enemy attacking unit")
            return False
        root = self._gk_root(unit)
        attacking_root = self._gk_root(attacking_unit)
        if root is None or attacking_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SHINING RESOLVE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SHINING RESOLVE: only usable in your opponent's Shooting phase")
            return False
        if self._gk_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: SHINING RESOLVE: trigger requires an enemy attacking unit")
            return False
        eligible = candidates or self._hallowed_conclave_shining_resolve_candidates(target_units=target_units)
        if eligible and root not in eligible:
            logger.error("ERROR: SHINING RESOLVE: target unit was not selected as an attack target")
            return False
        if target_units and root not in [self._gk_root(target) for target in list(target_units or [])]:
            logger.error("ERROR: SHINING RESOLVE: target unit was not selected as an attack target")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: SHINING RESOLVE: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SHINING RESOLVE: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_infantry_unit(root):
            logger.error("ERROR: SHINING RESOLVE: target must be a GREY KNIGHTS INFANTRY unit")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = dict(getattr(root, "special_rules", None) or {})
        sr["hallowed_conclave_shining_resolve_active"] = True
        sr["hallowed_conclave_shining_resolve_turn_owner"] = self._gk_current_turn_owner_id()
        sr["hallowed_conclave_shining_resolve_turn"] = self._gk_current_turn()
        sr["hallowed_conclave_shining_resolve_expires_phase"] = "SHOOTING_PHASE"
        sr["hallowed_conclave_shining_resolve_source"] = (
            str(getattr(stratagem, "name", "") or "SHINING RESOLVE").strip() or "SHINING RESOLVE"
        )
        root.special_rules = sr
        self._gk_clear_ability_cache(root)
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SHINING RESOLVE: %s imposes -1 to wound when an attack's Strength exceeds its Toughness this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_hallowed_conclave_unending_fidelity(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_conclave():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        candidates = list(kwargs.get("candidates") or [])
        pending = None
        if unit is None or attacking_unit is None or not candidates:
            pending = self._gk_pending_reaction_by_name("UNENDING FIDELITY")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if attacking_unit is None and pending is not None:
            attacking_unit = pending.get("attacking_unit") or pending.get("enemy_unit")
        if not target_units and pending is not None:
            target_units = list(pending.get("target_units") or [])
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: UNENDING FIDELITY: no target unit provided")
            return False
        if attacking_unit is None:
            logger.error("ERROR: UNENDING FIDELITY: missing enemy attacking unit")
            return False
        root = self._gk_root(unit)
        attacking_root = self._gk_root(attacking_unit)
        if root is None or attacking_root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: UNENDING FIDELITY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: UNENDING FIDELITY: only usable in your opponent's Shooting phase")
            return False
        if self._gk_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: UNENDING FIDELITY: trigger requires an enemy attacking unit")
            return False
        eligible = candidates or self._hallowed_conclave_unending_fidelity_candidates(target_units=target_units)
        if eligible and root not in eligible:
            logger.error("ERROR: UNENDING FIDELITY: target unit was not selected as an attack target")
            return False
        if target_units and root not in [self._gk_root(target) for target in list(target_units or [])]:
            logger.error("ERROR: UNENDING FIDELITY: target unit was not selected as an attack target")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: UNENDING FIDELITY: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: UNENDING FIDELITY: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_infantry_unit(root):
            logger.error("ERROR: UNENDING FIDELITY: target must be a GREY KNIGHTS INFANTRY unit")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        mode = "shoot" if phase_name == "shooting phase" else "fight"
        sr = dict(getattr(root, "special_rules", None) or {})
        sr["hallowed_conclave_unending_fidelity_active"] = True
        sr["hallowed_conclave_unending_fidelity_mode"] = mode
        sr["hallowed_conclave_unending_fidelity_threshold"] = 4
        sr["hallowed_conclave_unending_fidelity_turn_owner"] = self._gk_current_turn_owner_id()
        sr["hallowed_conclave_unending_fidelity_turn"] = self._gk_current_turn()
        sr["hallowed_conclave_unending_fidelity_expires_phase"] = (
            "SHOOTING_PHASE" if mode == "shoot" else "FIGHT_PHASE"
        )
        sr["hallowed_conclave_unending_fidelity_source"] = (
            str(getattr(stratagem, "name", "") or "UNENDING FIDELITY").strip() or "UNENDING FIDELITY"
        )
        root.special_rules = sr
        self._gk_clear_ability_cache(root)
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNENDING FIDELITY: %s gains %s on-death attacks on 4+ until end of phase.",
            getattr(root, "name", "Unit"),
            "shoot" if mode == "shoot" else "fight",
        )
        return True

    def _use_hallowed_conclave_grind_them_underfoot(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_conclave():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_candidates_by_unit_id = dict(kwargs.get("enemy_candidates_by_unit_id") or {})
        pending = None
        if unit is None or not candidates:
            pending = self._gk_pending_reaction_by_name("GRIND THEM UNDERFOOT")
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        if enemy_unit is None and pending is not None:
            enemy_unit = pending.get("enemy_unit")
        if not candidates and pending is not None:
            candidates = list(pending.get("candidates") or [])
        if not enemy_candidates_by_unit_id and pending is not None:
            enemy_candidates_by_unit_id = dict(pending.get("enemy_candidates_by_unit_id") or {})
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: GRIND THEM UNDERFOOT: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: GRIND THEM UNDERFOOT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: GRIND THEM UNDERFOOT: only usable in your Charge phase")
            return False
        eligible = candidates or [root]
        if eligible and root not in eligible:
            logger.error("ERROR: GRIND THEM UNDERFOOT: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: GRIND THEM UNDERFOOT: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: GRIND THEM UNDERFOOT: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_terminator_unit(root):
            logger.error("ERROR: GRIND THEM UNDERFOOT: target must be a GREY KNIGHTS TERMINATOR unit")
            return False
        root_id = self._gk_sort_key(root)
        enemy_candidates = list(enemy_candidates_by_unit_id.get(root_id) or [])
        if not enemy_candidates:
            enemy_candidates = self._hallowed_conclave_grind_them_underfoot_enemy_candidates(root)
        if enemy_unit is None and len(enemy_candidates) == 1:
            enemy_unit = enemy_candidates[0]
        if enemy_unit is None:
            logger.error("ERROR: GRIND THEM UNDERFOOT: no enemy unit provided")
            return False
        enemy_root = self._gk_root(enemy_unit)
        if enemy_root is None:
            return False
        if enemy_candidates and enemy_root not in [self._gk_root(candidate) for candidate in list(enemy_candidates or [])]:
            logger.error("ERROR: GRIND THEM UNDERFOOT: selected enemy unit is not within Engagement Range")
            return False
        if self._gk_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: GRIND THEM UNDERFOOT: selected enemy unit is invalid")
            return False
        if not self._gk_is_alive(enemy_root) or not self._gk_is_on_battlefield(enemy_root):
            logger.error("ERROR: GRIND THEM UNDERFOOT: selected enemy unit is no longer on the battlefield")
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        within_engagement = getattr(game_map, "is_within_engagement_range", None) if game_map is not None else None
        if callable(within_engagement) and not bool(within_engagement(root, enemy_root)):
            logger.error("ERROR: GRIND THEM UNDERFOOT: selected enemy unit is not within Engagement Range")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        resolve_charge_end = getattr(self.game, "resolve_charge_end_mortal_wounds", None) if self.game is not None else None
        if not callable(resolve_charge_end):
            logger.error("ERROR: GRIND THEM UNDERFOOT: charge-end mortal wounds resolver unavailable")
            return False
        source_name = str(getattr(stratagem, "name", "") or "GRIND THEM UNDERFOOT").strip() or "GRIND THEM UNDERFOOT"
        resolve_charge_end(
            root,
            enemy_root,
            {
                "kind": "per_model_engagement_flat_cap",
                "name": source_name,
                "threshold": 4,
                "mortal_per_success": 1,
                "max_mortal_wounds": 6,
            },
        )
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: GRIND THEM UNDERFOOT: %s rolled charge-end mortals against %s.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Unit"),
        )
        return True

    def _use_brotherhood_strike_duty_unending(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_brotherhood_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: DUTY UNENDING: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: DUTY UNENDING: not opponent's Movement phase")
            return False
        pending = self._gk_pending_reaction_by_name("DUTY UNENDING")
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        enemy_unit = kwargs.get("enemy_unit")
        if isinstance(pending, dict):
            if unit is None:
                unit = pending.get("target_unit")
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if enemy_unit is None:
                enemy_unit = pending.get("enemy_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: DUTY UNENDING: no target unit provided")
            return False
        root = self._gk_root(unit)
        enemy_root = self._gk_root(enemy_unit)
        if root is None:
            return False
        eligible = candidates or self._brotherhood_strike_duty_unending_candidates(enemy_unit=enemy_root)
        if eligible and root not in eligible:
            logger.error("ERROR: DUTY UNENDING: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: DUTY UNENDING: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: DUTY UNENDING: target cannot be selected")
            return False
        if not self._is_gk_unit(root):
            logger.error("ERROR: DUTY UNENDING: target must be GREY KNIGHTS")
            return False
        if self._gk_has_enemy_within_engagement_range(root):
            logger.error("ERROR: DUTY UNENDING: target is still within Engagement Range")
            return False
        if enemy_root is None or self._gk_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: DUTY UNENDING: invalid enemy unit")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        if not self._gk_place_unit_into_strategic_reserves(root, reason=str(getattr(stratagem, "name", "") or "DUTY UNENDING")):
            logger.error("ERROR: DUTY UNENDING: failed to place target into Strategic Reserves")
            return False
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: DUTY UNENDING: %s entered Strategic Reserves after %s fell back.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Unit"),
        )
        return True

    def _use_brotherhood_strike_expeditious_exit(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_brotherhood_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: EXPEDITIOUS EXIT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: EXPEDITIOUS EXIT: not opponent's Fight phase")
            return False
        pending = self._gk_pending_reaction_by_name("EXPEDITIOUS EXIT")
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if isinstance(pending, dict):
            if unit is None:
                unit = pending.get("target_unit")
            if not candidates:
                candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: EXPEDITIOUS EXIT: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        eligible = candidates or self._brotherhood_strike_expeditious_exit_candidates()
        if eligible and root not in eligible:
            logger.error("ERROR: EXPEDITIOUS EXIT: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: EXPEDITIOUS EXIT: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: EXPEDITIOUS EXIT: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_psyker_unit(root) or not self._is_gk_infantry_unit(root):
            logger.error("ERROR: EXPEDITIOUS EXIT: target must be a GREY KNIGHTS PSYKER INFANTRY unit")
            return False
        if not self._gk_has_deep_strike(root):
            logger.error("ERROR: EXPEDITIOUS EXIT: every model in the target must have Deep Strike")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        if not self._gk_place_unit_into_strategic_reserves(root, reason=str(getattr(stratagem, "name", "") or "EXPEDITIOUS EXIT")):
            logger.error("ERROR: EXPEDITIOUS EXIT: failed to place target into Strategic Reserves")
            return False
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: EXPEDITIOUS EXIT: %s entered Strategic Reserves at the end of the opponent's Fight phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_brotherhood_strike_purgation_pattern(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_brotherhood_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PURGATION PATTERN: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PURGATION PATTERN: not your Shooting phase")
            return False
        pending = self._gk_pending_reaction_by_name("PURGATION PATTERN")
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if isinstance(pending, dict):
            if unit is None:
                unit = pending.get("target_unit")
            if not candidates:
                candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PURGATION PATTERN: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        eligible = candidates or self._brotherhood_strike_purgation_pattern_candidates()
        if eligible and root not in eligible:
            logger.error("ERROR: PURGATION PATTERN: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: PURGATION PATTERN: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: PURGATION PATTERN: target cannot be selected")
            return False
        if not self._is_gk_unit(root):
            logger.error("ERROR: PURGATION PATTERN: target must be GREY KNIGHTS")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        self._gk_apply_temporary_weapon_keyword_bonuses(
            root,
            key_prefix="grey_knights_purgation_pattern",
            keywords=["SUSTAINED HITS 1"],
            expires_phase="SHOOTING_PHASE",
            attack_type="ranged",
            source=str(getattr(stratagem, "name", "") or "PURGATION PATTERN"),
            weapon_filter=lambda wargear: bool(callable(getattr(wargear, "is_ranged", None)) and wargear.is_ranged()),
        )
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: PURGATION PATTERN: %s gains [SUSTAINED HITS 1] on ranged weapons until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_brotherhood_strike_shining_veil(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_brotherhood_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SHINING VEIL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SHINING VEIL: not opponent's Shooting phase")
            return False
        pending = self._gk_pending_reaction_by_name("SHINING VEIL")
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("enemy_unit")
        target_units = list(kwargs.get("target_units") or [])
        if isinstance(pending, dict):
            if unit is None:
                unit = pending.get("target_unit")
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit") or pending.get("enemy_unit")
            if not target_units:
                target_units = list(pending.get("target_units") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SHINING VEIL: no target unit provided")
            return False
        root = self._gk_root(unit)
        attacking_root = self._gk_root(attacking_unit)
        if root is None:
            return False
        eligible = candidates or self._brotherhood_strike_shining_veil_candidates(target_units=target_units)
        if eligible and root not in eligible:
            logger.error("ERROR: SHINING VEIL: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: SHINING VEIL: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SHINING VEIL: target cannot be selected")
            return False
        if not self._is_gk_unit(root):
            logger.error("ERROR: SHINING VEIL: target must be GREY KNIGHTS")
            return False
        if attacking_root is None or self._gk_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: SHINING VEIL: invalid attacking unit")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = dict(getattr(root, "special_rules", None) or {})
        sr["opponent_shooting_phase_stealth_active"] = True
        sr["opponent_shooting_phase_stealth_owner"] = str(getattr(active_player, "id", "") or "")
        sr["opponent_shooting_phase_stealth_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["opponent_shooting_phase_stealth_source"] = str(getattr(stratagem, "name", "") or "SHINING VEIL")
        sr["opponent_shooting_phase_stealth_expires_phase"] = "SHOOTING_PHASE"
        root.special_rules = sr
        self._gk_clear_ability_cache(root)
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SHINING VEIL: %s gains Stealth until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_brotherhood_strike_truesilver_channelling(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_brotherhood_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: TRUESILVER CHANNELLING: wrong phase")
            return False
        pending = self._gk_pending_reaction_by_name("TRUESILVER CHANNELLING")
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if isinstance(pending, dict):
            if unit is None:
                unit = pending.get("target_unit")
            if not candidates:
                candidates = list(pending.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: TRUESILVER CHANNELLING: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        eligible = candidates or self._brotherhood_strike_truesilver_channelling_candidates()
        if eligible and root not in eligible:
            logger.error("ERROR: TRUESILVER CHANNELLING: target unit is not currently eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: TRUESILVER CHANNELLING: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: TRUESILVER CHANNELLING: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_infantry_unit(root):
            logger.error("ERROR: TRUESILVER CHANNELLING: target must be GREY KNIGHTS INFANTRY")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: TRUESILVER CHANNELLING: target has already fought this phase")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        self._gk_apply_temporary_weapon_keyword_bonuses(
            root,
            key_prefix="grey_knights_truesilver_channelling",
            keywords=["DEVASTATING WOUNDS"],
            expires_phase="FIGHT_PHASE",
            attack_type="any",
            source=str(getattr(stratagem, "name", "") or "TRUESILVER CHANNELLING"),
            weapon_filter=lambda wargear: self._gk_wargear_has_keyword(wargear, keyword="psychic"),
        )
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: TRUESILVER CHANNELLING: %s gains [DEVASTATING WOUNDS] on Psychic weapons until end of phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_brotherhood_strike_combat_manifestation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_brotherhood_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: COMBAT MANIFESTATION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: COMBAT MANIFESTATION: not your turn")
            return False

        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: COMBAT MANIFESTATION: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False

        eligible = candidates or self._brotherhood_strike_combat_manifestation_candidates()
        if eligible and root not in eligible:
            logger.error("ERROR: COMBAT MANIFESTATION: target unit is not eligible")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: COMBAT MANIFESTATION: target unit is not yours")
            return False
        if not self._gk_is_alive(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: COMBAT MANIFESTATION: target cannot be selected")
            return False
        if not self._is_gk_unit(root):
            logger.error("ERROR: COMBAT MANIFESTATION: target must be GREY KNIGHTS")
            return False
        in_reserves = getattr(root, "is_in_reserves", None)
        if not callable(in_reserves) or not bool(in_reserves()):
            logger.error("ERROR: COMBAT MANIFESTATION: target is not in Reserves")
            return False
        reserve_status = str(getattr(root, "reserve_status", "") or "").strip().lower()
        if reserve_status not in {"reserves", "strategic_reserves"}:
            logger.error("ERROR: COMBAT MANIFESTATION: target is not arriving from Reserves")
            return False
        if not self._gk_has_deep_strike(root):
            logger.error("ERROR: COMBAT MANIFESTATION: target lacks Deep Strike")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["combat_manifestation_deep_strike_min_distance"] = 6.0
        sr["combat_manifestation_deep_strike_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["combat_manifestation_deep_strike_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["combat_manifestation_deep_strike_expires_phase"] = "MOVEMENT_PHASE"
        sr["combat_manifestation_no_charge_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["combat_manifestation_no_charge_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["combat_manifestation_source"] = str(getattr(stratagem, "name", "COMBAT MANIFESTATION") or "COMBAT MANIFESTATION")
        root.special_rules = sr
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: COMBAT MANIFESTATION: %s can be set up more than 6\" away and cannot charge this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_warpbane_sanctified_kill_zone(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SANCTIFIED KILL ZONE: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        if not self._is_warpbane_task_force():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in ("shooting phase", "fight phase"):
            logger.error("ERROR: SANCTIFIED KILL ZONE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: SANCTIFIED KILL ZONE: not your Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SANCTIFIED KILL ZONE: target was not selected")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: SANCTIFIED KILL ZONE: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SANCTIFIED KILL ZONE: target cannot be selected")
            return False
        mgr = self._get_gk_mgr()
        if mgr is None or not bool(mgr.unit_wholly_within_hallowed_ground(root, game=self.game)):
            logger.error("ERROR: SANCTIFIED KILL ZONE: target is not wholly within Hallowed Ground")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: SANCTIFIED KILL ZONE: target already shot this phase")
            return False
        if phase_name == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: SANCTIFIED KILL ZONE: target already fought this phase")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["sanctified_kill_zone_active"] = True
        sr["sanctified_kill_zone_reroll_full"] = bool(self._is_purifier_squad_unit(root))
        sr["sanctified_kill_zone_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["sanctified_kill_zone_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["sanctified_kill_zone_expires_phase"] = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr["sanctified_kill_zone_source"] = stratagem.name
        root.special_rules = sr
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: SANCTIFIED KILL ZONE: {getattr(root, 'name', 'Unit')} gains wound re-roll support until end of phase.")
        return True

    def _use_warpbane_hallowed_beacon(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: HALLOWED BEACON: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        if not self._is_warpbane_task_force():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: HALLOWED BEACON: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: HALLOWED BEACON: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: HALLOWED BEACON: target was not selected")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: HALLOWED BEACON: target unit is not yours")
            return False
        if not self._gk_is_alive(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: HALLOWED BEACON: target cannot be selected")
            return False
        if not self._is_gk_unit(root):
            logger.error("ERROR: HALLOWED BEACON: target is not GREY KNIGHTS")
            return False
        if not self._is_gk_infantry_unit(root):
            logger.error("ERROR: HALLOWED BEACON: target is not INFANTRY")
            return False
        if self._is_gk_terminator_unit(root):
            logger.error("ERROR: HALLOWED BEACON: TERMINATOR units are excluded")
            return False
        in_reserves = getattr(root, "is_in_reserves", None)
        if not callable(in_reserves) or not bool(in_reserves()):
            logger.error("ERROR: HALLOWED BEACON: target is not in Reserves")
            return False
        if str(getattr(root, "reserve_status", "") or "").strip().lower() != "reserves":
            logger.error("ERROR: HALLOWED BEACON: target is not arriving from Reserves")
            return False
        has_deep_strike = getattr(root, "has_deep_strike", None)
        if not callable(has_deep_strike) or not bool(has_deep_strike()):
            logger.error("ERROR: HALLOWED BEACON: target lacks Deep Strike")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["hallowed_beacon_deep_strike_min_distance"] = 6.0
        sr["hallowed_beacon_requires_hallowed_ground"] = True
        sr["hallowed_beacon_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["hallowed_beacon_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["hallowed_beacon_expires_phase"] = "MOVEMENT_PHASE"
        sr["hallowed_beacon_source"] = stratagem.name
        root.special_rules = sr
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: HALLOWED BEACON: {getattr(root, 'name', 'Unit')} can Deep Strike at 6\" and must arrive in Hallowed Ground.")
        return True

    def _use_warpbane_aegis_eternal(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: AEGIS ETERNAL: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        if not self._is_warpbane_task_force():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: AEGIS ETERNAL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: AEGIS ETERNAL: not opponent's Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: AEGIS ETERNAL: target was not selected")
            return False
        target_units = list(kwargs.get("target_units") or [])
        if target_units and root not in [self._gk_root(u) for u in target_units]:
            logger.error("ERROR: AEGIS ETERNAL: target was not selected as a shooting target")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: AEGIS ETERNAL: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: AEGIS ETERNAL: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_infantry_unit(root):
            logger.error("ERROR: AEGIS ETERNAL: target must be GREY KNIGHTS INFANTRY")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["aegis_eternal_active"] = True
        sr["aegis_eternal_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["aegis_eternal_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["aegis_eternal_expires_phase"] = "SHOOTING_PHASE"
        sr["aegis_eternal_source"] = stratagem.name
        root.special_rules = sr
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: AEGIS ETERNAL: {getattr(root, 'name', 'Unit')} gains conditional 4++ in Hallowed Ground.")
        return True

    def _use_warpbane_fires_of_covenant(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FIRES OF COVENANT: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        if not self._is_warpbane_task_force():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: FIRES OF COVENANT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: FIRES OF COVENANT: not opponent's Movement phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: FIRES OF COVENANT: target was not selected")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: FIRES OF COVENANT: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: FIRES OF COVENANT: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_infantry_unit(root):
            logger.error("ERROR: FIRES OF COVENANT: target must be GREY KNIGHTS INFANTRY")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["fires_of_covenant_active"] = True
        sr["fires_of_covenant_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["fires_of_covenant_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["fires_of_covenant_expires_phase"] = "MOVEMENT_PHASE"
        sr["fires_of_covenant_source"] = stratagem.name
        root.special_rules = sr
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: FIRES OF COVENANT: {getattr(root, 'name', 'Unit')} will trigger mortal wound checks this phase.")
        return True

    def _use_warpbane_repelling_sphere(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: REPELLING SPHERE: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        if not self._is_warpbane_task_force():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: REPELLING SPHERE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: REPELLING SPHERE: not opponent's Charge phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: REPELLING SPHERE: target was not selected")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: REPELLING SPHERE: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: REPELLING SPHERE: target cannot be selected")
            return False
        if not self._is_gk_unit(root) or not self._is_gk_infantry_unit(root):
            logger.error("ERROR: REPELLING SPHERE: target must be GREY KNIGHTS INFANTRY")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["repelling_sphere_active"] = True
        sr["repelling_sphere_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["repelling_sphere_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["repelling_sphere_expires_phase"] = "CHARGE_PHASE"
        sr["repelling_sphere_source"] = stratagem.name
        root.special_rules = sr
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: REPELLING SPHERE: {getattr(root, 'name', 'Unit')} imposes charge roll penalties this phase.")
        return True

    def _use_warpbane_flames_of_sanctity(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FLAMES OF SANCTITY: no target unit provided")
            return False
        root = self._gk_root(unit)
        if root is None:
            return False
        if not self._is_warpbane_task_force():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: FLAMES OF SANCTITY: wrong phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: FLAMES OF SANCTITY: target was not selected")
            return False
        if not self._gk_owned_by_player(root, self.player):
            logger.error("ERROR: FLAMES OF SANCTITY: target unit is not yours")
            return False
        if not self._gk_is_alive(root) or not self._gk_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: FLAMES OF SANCTITY: target cannot be selected")
            return False
        if not self._is_purifier_squad_unit(root):
            logger.error("ERROR: FLAMES OF SANCTITY: target must be a Purifier Squad")
            return False
        if not self._warpbane_spend_cp(stratagem, target_unit=root):
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            logger.error("ERROR: FLAMES OF SANCTITY: no map context")
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        enemy_units = list(get_enemy_units(root) or []) if callable(get_enemy_units) else []
        if not enemy_units:
            self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(f"INFO: FLAMES OF SANCTITY: no enemy units within range of {getattr(root, 'name', 'Unit')}.")
            return True
        from ..utility.aura_utils import unit_within_range_of_unit

        bonus = 1 if self._unit_includes_castellan_crowe(root) else 0
        for enemy in sorted(enemy_units, key=self._gk_sort_key):
            enemy_root = self._gk_root(enemy)
            if enemy_root is None or not self._gk_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if not unit_within_range_of_unit(root, enemy_root, 6.0, use_attached_aggregate=True):
                continue
            roll = int(dice_module.get_roll("D6") or 0) + int(bonus or 0)
            if roll < 4:
                continue
            mortal_wounds = int(dice_module.get_roll("D3") or 0)
            if mortal_wounds <= 0:
                continue
            apply_mortals = getattr(root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortals):
                apply_mortals(enemy_root, int(mortal_wounds), game_map=game_map)
        self._warpbane_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: FLAMES OF SANCTITY: resolved mortal wound rolls around {getattr(root, 'name', 'Unit')}.")
        return True
