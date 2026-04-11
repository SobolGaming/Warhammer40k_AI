from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility.entity_ids import get_entity_id
from ..utility.modifiers import Modifier, ModifierOp

logger = logging.getLogger(__name__)


class ImperialAgentsStratagemMixin:
    @staticmethod
    def _ia_norm_stratagem_name(name: str) -> str:
        text = str(name or "")
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-")
        text = text.replace("\u2013", "-").replace("\u2014", "-")
        text = text.replace("\u00e2\u20ac\u2122", "'")
        text = text.replace("\u0192?T", "'")
        return text.strip().upper()

    @staticmethod
    def _ia_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _ia_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    @staticmethod
    def _ia_has_keyword(unit: Any, keyword: str) -> bool:
        if unit is None:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            if bool(has_keyword(keyword)):
                return True
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        return bool(has_any_keyword(keyword)) if callable(has_any_keyword) else False

    @staticmethod
    def _ia_unit_name_key(unit: Any) -> str:
        return " ".join(str(getattr(unit, "name", "") or "").strip().lower().split())

    @classmethod
    def _ia_is_vindicare_assassin_unit(cls, unit: Any) -> bool:
        root = cls._ia_root(unit)
        return cls._ia_unit_name_key(root) == "vindicare assassin"

    @classmethod
    def _ia_is_callidus_assassin_unit(cls, unit: Any) -> bool:
        root = cls._ia_root(unit)
        return cls._ia_unit_name_key(root) == "callidus assassin"

    @classmethod
    def _ia_is_eversor_assassin_unit(cls, unit: Any) -> bool:
        root = cls._ia_root(unit)
        return cls._ia_unit_name_key(root) == "eversor assassin"

    @classmethod
    def _ia_is_culexus_assassin_unit(cls, unit: Any) -> bool:
        root = cls._ia_root(unit)
        return cls._ia_unit_name_key(root) == "culexus assassin"

    @staticmethod
    def _ia_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _ia_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return True
        in_reserves = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves):
            return bool(in_reserves())
        return bool(getattr(unit, "is_in_reserves", False))

    @classmethod
    def _ia_is_on_battlefield(cls, unit: Any) -> bool:
        root = cls._ia_root(unit)
        if root is None:
            return False
        if not cls._ia_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        if cls._ia_is_in_reserves(root):
            return False
        if bool(getattr(root, "is_embarked", False)):
            return False
        if getattr(root, "embarked_in", None) is not None:
            return False
        return True

    @staticmethod
    def _ia_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    def _ia_detachment_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "imperial_agents_detachments", None)

    def _is_veiled_blade_elimination_force(self) -> bool:
        mgr = self._ia_detachment_mgr()
        checker = getattr(mgr, "is_veiled_blade_elimination_force", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_imperialis_fleet(self) -> bool:
        mgr = self._ia_detachment_mgr()
        checker = getattr(mgr, "is_imperialis_fleet", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_ordo_hereticus_purgation_force(self) -> bool:
        mgr = self._ia_detachment_mgr()
        checker = getattr(mgr, "is_ordo_hereticus_purgation_force", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_ordo_malleus_daemon_hunters(self) -> bool:
        mgr = self._ia_detachment_mgr()
        checker = getattr(mgr, "is_ordo_malleus_daemon_hunters", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _ia_exact_punishment_snapshots(self) -> dict[str, dict[str, Any]]:
        snapshots = getattr(self, "_imperial_agents_exact_punishment_snapshots_cache", None)
        if isinstance(snapshots, dict):
            return snapshots
        snapshots = {}
        setattr(self, "_imperial_agents_exact_punishment_snapshots_cache", snapshots)
        return snapshots

    def _ia_is_agents_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        if self._ia_has_keyword(root, "AGENTS OF THE IMPERIUM"):
            return True
        return str(getattr(root, "faction_id", "") or "").strip().upper() == "AOI"

    def _ia_is_agents_infantry_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        if not self._ia_is_agents_unit(root):
            return False
        return self._ia_has_keyword(root, "INFANTRY")

    def _ia_is_ordo_hereticus_purgation_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        if not self._ia_is_agents_unit(root):
            return False
        return bool(
            self._ia_has_keyword(root, "ADEPTUS ARBITES")
            or self._ia_has_keyword(root, "INQUISITORIAL AGENTS")
            or self._ia_has_keyword(root, "ORDO HERETICUS")
        )

    def _ia_is_agents_character_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        if not self._ia_is_agents_unit(root):
            return False
        return self._ia_has_keyword(root, "CHARACTER")

    def _ia_is_voidfarers_character_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        if not self._ia_is_agents_character_unit(root):
            return False
        return self._ia_has_keyword(root, "VOIDFARERS")

    @staticmethod
    def _ia_selected_to_shoot_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "shot_this_round", False))

    @staticmethod
    def _ia_selected_to_fight_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "fought_this_phase", False))

    @staticmethod
    def _ia_unit_models(unit: Any) -> list[Any]:
        if unit is None:
            return []
        get_attached_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_attached_models):
            return list(get_attached_models() or [])
        return list(getattr(unit, "models", []) or [])

    def _ia_is_attached_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        return bool(getattr(root, "attached_leaders", []) or [])

    def _ia_unit_has_character_model(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        if self._ia_has_keyword(root, "CHARACTER"):
            return True
        if bool(getattr(root, "attached_leaders", []) or []):
            return True
        for model in list(self._ia_unit_models(root) or []):
            if model is None or bool(getattr(model, "_pending_placement", False)):
                continue
            alive_attr = getattr(model, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            if bool(getattr(model, "is_character", False)):
                return True
            has_keyword = getattr(model, "has_keyword", None)
            if callable(has_keyword) and bool(has_keyword("CHARACTER")):
                return True
        return False

    def _ia_is_officio_assassinorum_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        return self._ia_has_keyword(root, "OFFICIO ASSASSINORUM")

    def _ia_unit_within_engagement_range(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return False
        for enemy in list(game_map.get_enemy_units(root) or []):
            enemy_root = self._ia_root(enemy)
            if enemy_root is None or not self._ia_is_alive(enemy_root):
                continue
            if bool(game_map.is_within_engagement_range(root, enemy_root)):
                return True
        return False

    def _ia_unit_within_objective_range(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        is_within = getattr(root, "is_within_objective_range", None)
        if not callable(is_within):
            return False
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return False
        for objective in list(getattr(game_map, "objectives", []) or []):
            location = getattr(objective, "location", None)
            if location is None or bool(getattr(location, "removed", False)):
                continue
            try:
                if bool(is_within(location)):
                    return True
            except (AttributeError, TypeError, ValueError):
                continue
        return False

    def _ia_effect_is_current(self, sr: dict[str, Any], *, prefix: str, phase_key: str = "") -> bool:
        if not isinstance(sr, dict) or not bool(sr.get(f"{prefix}_active")):
            return False
        game = getattr(self, "game", None)
        if game is None:
            return True
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        try:
            current_owner = str(getattr(game.get_current_player(), "id", "") or "")
        except (AttributeError, TypeError, ValueError):
            current_owner = ""
        marked_owner = str(sr.get(f"{prefix}_turn_owner", "") or "")
        if marked_owner and current_owner and marked_owner != current_owner:
            return False
        try:
            marked_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            marked_turn = 0
        if marked_turn and current_turn and marked_turn != current_turn:
            return False
        if phase_key:
            expected_phase = str(sr.get(f"{prefix}_expires_phase", "") or "").strip().upper()
            if expected_phase and expected_phase != str(phase_key or "").strip().upper():
                return False
        return True

    def _ia_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None, enemy_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_fn = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_fn):
            preview = apply_fn(stratagem, target_unit=target_unit, enemy_unit=enemy_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _ia_spend_cp(self, stratagem: Any, *, target_unit: Any = None, enemy_unit: Any = None) -> bool:
        cp_cost = self._ia_effective_cp_cost(stratagem, target_unit=target_unit, enemy_unit=enemy_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _ia_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _ia_pending_context(self, stratagem_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        context = dict(kwargs or {})
        wanted = self._ia_norm_stratagem_name(stratagem_name)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            current = self._ia_norm_stratagem_name(reaction.get("stratagem", ""))
            if current != wanted:
                continue
            merged = dict(reaction)
            merged.update(context)
            return merged
        return context

    def _ia_blind_grenades_candidates(self, target_units: list[Any]) -> list[Any]:
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_agents_unit(root):
                continue
            has_grenades = self._ia_has_keyword(root, "GRENADES")
            if not has_grenades and not self._ia_is_vindicare_assassin_unit(root):
                continue
            engaged = False
            for enemy in list(game_map.get_enemy_units(root) or []):
                enemy_root = self._ia_root(enemy)
                if enemy_root is None or not self._ia_is_alive(enemy_root):
                    continue
                if bool(game_map.is_within_engagement_range(root, enemy_root)):
                    engaged = True
                    break
            if engaged:
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_ensnaring_enemy_candidates_for_unit(self, unit: Any) -> list[Any]:
        root = self._ia_root(unit)
        if root is None:
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for enemy in list(game_map.get_enemy_units(root) or []):
            enemy_root = self._ia_root(enemy)
            if enemy_root is None:
                continue
            eid = self._ia_sort_key(enemy_root)
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            if not self._ia_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if self._ia_is_in_reserves(enemy_root):
                continue
            try:
                distance = float(game_map.get_distance_between_units(root, enemy_root))
            except (TypeError, ValueError):
                continue
            if distance > 6.0:
                continue
            can_charge = getattr(root, "can_declare_charge_against", None)
            if not callable(can_charge):
                continue
            if not bool(can_charge(enemy_root, self.game, out_of_turn=True)):
                continue
            out.append(enemy_root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_ensnaring_trap_candidates(self) -> tuple[list[Any], dict[str, list[Any]]]:
        if not self._is_veiled_blade_elimination_force():
            return [], {}
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return [], {}
        out: list[Any] = []
        enemy_by_unit: dict[str, list[Any]] = {}
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_agents_infantry_unit(root):
                continue
            enemies = self._ia_ensnaring_enemy_candidates_for_unit(root)
            if not enemies:
                continue
            out.append(root)
            if uid:
                enemy_by_unit[uid] = enemies
        return sorted(out, key=self._ia_sort_key), enemy_by_unit

    def _ia_enemy_battlefield_units(self) -> list[Any]:
        game = getattr(self, "game", None)
        if game is None:
            return []
        collect = getattr(game, "_collect_enemy_unit_roots", None)
        if callable(collect):
            return sorted(list(collect(self.player) or []), key=self._ia_sort_key)
        out: list[Any] = []
        seen: set[str] = set()
        for enemy in list(getattr(game, "get_enemy_units", lambda _player: [])(self.player) or []):
            root = self._ia_root(enemy)
            if root is None:
                continue
            eid = self._ia_sort_key(root)
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            if not self._ia_is_on_battlefield(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_ordo_hereticus_enemy_character_candidates(self) -> list[Any]:
        if not self._is_ordo_hereticus_purgation_force():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for enemy_root in list(self._ia_enemy_battlefield_units() or []):
            eid = self._ia_sort_key(enemy_root)
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            if not self._ia_unit_has_character_model(enemy_root):
                continue
            out.append(enemy_root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_ordo_hereticus_stun_grenades_enemy_candidates_for_unit(self, unit: Any) -> list[Any]:
        if not self._is_ordo_hereticus_purgation_force():
            return []
        root = self._ia_root(unit)
        if root is None or not self._ia_is_on_battlefield(root):
            return []
        if not self._ia_is_ordo_hereticus_purgation_unit(root):
            return []
        if not self._ia_has_keyword(root, "GRENADES"):
            return []
        if self._ia_unit_within_engagement_range(root):
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game is None or game_map is None:
            return []
        visible = getattr(game, "_visible_enemy_candidates_for_model", None)
        if not callable(visible):
            return []
        enemy_roots = list(self._ia_enemy_battlefield_units() or [])
        out: list[Any] = []
        seen: set[str] = set()
        for model in list(self._ia_unit_models(root) or []):
            if model is None or bool(getattr(model, "_pending_placement", False)):
                continue
            alive_attr = getattr(model, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            for enemy_root in list(
                visible(
                    source_unit=root,
                    model=model,
                    enemy_roots=enemy_roots,
                    range_value=8.0,
                    game_map=game_map,
                )
                or []
            ):
                eid = self._ia_sort_key(enemy_root)
                if eid and eid in seen:
                    continue
                if eid:
                    seen.add(eid)
                if self._ia_has_keyword(enemy_root, "MONSTER") or self._ia_has_keyword(enemy_root, "VEHICLE"):
                    continue
                out.append(enemy_root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_prime_target_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_veiled_blade_elimination_force():
            return []
        phase_key = str(phase_name or "").strip().lower()
        if phase_key not in {"shooting phase", "fight phase"}:
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_agents_unit(root):
                continue
            if phase_key == "shooting phase" and self._ia_selected_to_shoot_this_phase(root):
                continue
            if phase_key == "fight phase" and self._ia_selected_to_fight_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_hyperstimms_candidates(self, target_units: list[Any]) -> list[Any]:
        if not self._is_veiled_blade_elimination_force():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_agents_character_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_orbital_oversight_candidates(self, target_units: list[Any]) -> list[Any]:
        if not self._is_veiled_blade_elimination_force():
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_agents_infantry_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_will_sapping_salvo_candidates(self) -> list[Any]:
        if not self._is_veiled_blade_elimination_force():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_agents_infantry_unit(root):
                continue
            if self._ia_selected_to_shoot_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_masters_of_the_void_candidates(self) -> list[Any]:
        if not self._is_imperialis_fleet():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_voidfarers_character_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_imperialis_fleet_candidate_units(
        self,
        *,
        candidate_units: Optional[list[Any]] = None,
        require_voidfarers: bool = False,
        require_character: bool = False,
        require_attached: bool = False,
        exclude_officio_assassinorum: bool = False,
    ) -> list[Any]:
        if not self._is_imperialis_fleet():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        source_units = list(candidate_units) if candidate_units is not None else list(getattr(army, "units", []) or [])
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(source_units or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_agents_unit(root):
                continue
            if require_voidfarers and not self._ia_has_keyword(root, "VOIDFARERS"):
                continue
            if require_character and not self._ia_unit_has_character_model(root):
                continue
            if require_attached and not self._ia_is_attached_unit(root):
                continue
            if exclude_officio_assassinorum and self._ia_is_officio_assassinorum_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_ordo_hereticus_candidate_units(
        self,
        *,
        candidate_units: Optional[list[Any]] = None,
        require_infantry: bool = False,
        require_grenades: bool = False,
        require_objective_range: bool = False,
        phase_name: str = "",
        require_not_selected: bool = False,
    ) -> list[Any]:
        if not self._is_ordo_hereticus_purgation_force():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        source_units = list(candidate_units) if candidate_units is not None else list(getattr(army, "units", []) or [])
        phase_key = str(phase_name or getattr(self, "_current_phase_name", "") or "").strip().lower()
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(source_units or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_ordo_hereticus_purgation_unit(root):
                continue
            if require_infantry and not self._ia_has_keyword(root, "INFANTRY"):
                continue
            if require_grenades and not self._ia_has_keyword(root, "GRENADES"):
                continue
            if require_objective_range and not self._ia_unit_within_objective_range(root):
                continue
            if require_grenades and self._ia_unit_within_engagement_range(root):
                continue
            if require_not_selected:
                if phase_key == "shooting phase" and self._ia_selected_to_shoot_this_phase(root):
                    continue
                if phase_key == "fight phase" and self._ia_selected_to_fight_this_phase(root):
                    continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_is_grey_knights_terminator_squad_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        return "grey knights terminator squad" in self._ia_unit_name_key(root)

    def _ia_is_ordo_malleus_unit(self, unit: Any) -> bool:
        root = self._ia_root(unit)
        if root is None:
            return False
        if not self._ia_is_agents_unit(root):
            return False
        return bool(
            self._ia_has_keyword(root, "INQUISITOR")
            or self._ia_has_keyword(root, "INQUISITORIAL AGENTS")
            or self._ia_has_keyword(root, "ORDO MALLEUS")
            or self._ia_is_grey_knights_terminator_squad_unit(root)
        )

    def _ia_ordo_malleus_candidate_units(
        self,
        *,
        candidate_units: Optional[list[Any]] = None,
        require_grey_knights_terminators: bool = False,
        require_objective_range: bool = False,
        phase_name: str = "",
        require_not_selected: bool = False,
    ) -> list[Any]:
        if not self._is_ordo_malleus_daemon_hunters():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        source_units = list(candidate_units) if candidate_units is not None else list(getattr(army, "units", []) or [])
        phase_key = str(phase_name or getattr(self, "_current_phase_name", "") or "").strip().lower()
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(source_units or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._ia_is_ordo_malleus_unit(root):
                continue
            if require_grey_knights_terminators and not self._ia_is_grey_knights_terminator_squad_unit(root):
                continue
            if require_objective_range and not self._ia_unit_within_objective_range(root):
                continue
            if require_not_selected and phase_key == "shooting phase" and self._ia_selected_to_shoot_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_ordo_malleus_enemy_daemon_candidates_for_unit(self, unit: Any) -> list[Any]:
        if not self._is_ordo_malleus_daemon_hunters():
            return []
        root = self._ia_root(unit)
        if root is None or not self._ia_is_on_battlefield(root):
            return []
        if not self._ia_is_ordo_malleus_unit(root):
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game is None or game_map is None:
            return []
        visible = getattr(game, "_visible_enemy_candidates_for_model", None)
        if not callable(visible):
            return []
        enemy_roots = list(self._ia_enemy_battlefield_units() or [])
        out: list[Any] = []
        seen: set[str] = set()
        for model in list(self._ia_unit_models(root) or []):
            if model is None or bool(getattr(model, "_pending_placement", False)):
                continue
            alive_attr = getattr(model, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            for enemy_root in list(
                visible(
                    source_unit=root,
                    model=model,
                    enemy_roots=enemy_roots,
                    range_value=12.0,
                    game_map=game_map,
                )
                or []
            ):
                eid = self._ia_sort_key(enemy_root)
                if eid and eid in seen:
                    continue
                if eid:
                    seen.add(eid)
                if not self._ia_has_keyword(enemy_root, "DAEMON"):
                    continue
                out.append(enemy_root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_ritual_of_warding_objective_candidates(self, unit: Any) -> list[Any]:
        root = self._ia_root(unit)
        if root is None or not self._ia_is_on_battlefield(root):
            return []
        if not self._ia_is_ordo_malleus_unit(root):
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for objective in list(getattr(game_map, "objectives", []) or []):
            location = getattr(objective, "location", None)
            if location is None or bool(getattr(location, "removed", False)):
                continue
            update_fn = getattr(location, "update_control", None)
            if callable(update_fn):
                update_fn(game)
            controller = getattr(location, "controlling_player", None)
            sticky_controller = getattr(location, "sticky_controller", None)
            if controller is not self.player and sticky_controller is not self.player:
                continue
            is_within = getattr(root, "is_within_objective_range", None)
            if not callable(is_within) or not bool(is_within(location)):
                continue
            objective_id = self._ia_sort_key(objective)
            if objective_id and objective_id in seen:
                continue
            if objective_id:
                seen.add(objective_id)
            out.append(objective)
        return sorted(out, key=self._ia_sort_key)

    def _ia_ritual_of_warding_candidates(self) -> tuple[list[Any], dict[str, list[Any]]]:
        if not self._is_ordo_malleus_daemon_hunters():
            return [], {}
        candidates = self._ia_ordo_malleus_candidate_units(require_objective_range=True)
        out: list[Any] = []
        objectives_by_unit: dict[str, list[Any]] = {}
        for root in list(candidates or []):
            objective_candidates = self._ia_ritual_of_warding_objective_candidates(root)
            if not objective_candidates:
                continue
            out.append(root)
            unit_id = self._ia_sort_key(root)
            if unit_id:
                objectives_by_unit[unit_id] = objective_candidates
        return sorted(out, key=self._ia_sort_key), objectives_by_unit

    def _ia_psybolt_ammunition_candidates(self) -> list[Any]:
        return self._ia_ordo_malleus_candidate_units(
            require_grey_knights_terminators=True,
            phase_name="Shooting phase",
            require_not_selected=True,
        )

    def _ia_steel_heart_candidates(self, *, moved_unit: Any = None) -> list[Any]:
        candidates = self._ia_ordo_malleus_candidate_units(
            candidate_units=[moved_unit] if moved_unit is not None else None,
            require_grey_knights_terminators=True,
        )
        out: list[Any] = []
        for root in list(candidates or []):
            round_state = getattr(root, "round_state", None)
            if not bool(getattr(round_state, "fell_back_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ia_sort_key)

    def _ia_hexagrammic_wards_candidates(self, target_units: list[Any]) -> list[Any]:
        return self._ia_ordo_malleus_candidate_units(candidate_units=list(target_units or []))

    def _ia_dispense_justice_candidates(self, *, phase_name: str) -> list[Any]:
        return self._ia_ordo_hereticus_candidate_units(
            phase_name=phase_name,
            require_not_selected=True,
        )

    def _ia_execution_order_candidates(self) -> list[Any]:
        return self._ia_ordo_hereticus_candidate_units(require_infantry=True)

    def _ia_inviolate_jurisdiction_candidates(self, target_units: list[Any]) -> list[Any]:
        return self._ia_ordo_hereticus_candidate_units(
            candidate_units=list(target_units or []),
            require_infantry=True,
            require_objective_range=True,
        )

    def _ia_line_of_fire_candidates(self) -> list[Any]:
        return self._ia_ordo_hereticus_candidate_units(
            phase_name="Shooting phase",
            require_not_selected=True,
        )

    def _ia_stun_grenades_candidates(self) -> tuple[list[Any], dict[str, list[Any]]]:
        if not self._is_ordo_hereticus_purgation_force():
            return [], {}
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return [], {}
        out: list[Any] = []
        enemy_by_unit: dict[str, list[Any]] = {}
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            enemies = self._ia_ordo_hereticus_stun_grenades_enemy_candidates_for_unit(root)
            if not enemies:
                continue
            out.append(root)
            if uid:
                enemy_by_unit[uid] = enemies
        return sorted(out, key=self._ia_sort_key), enemy_by_unit

    def _queue_imperial_agents_imperialis_fleet_targets_selected_reaction(
        self,
        *,
        event_name: str,
        phase_name: str,
        stratagem: Any,
        attacking_unit: Any,
        target_units: list[Any],
        candidates: list[Any],
    ) -> None:
        if stratagem is None or attacking_unit is None or not candidates:
            return
        expected_name = self._ia_norm_stratagem_name(getattr(stratagem, "name", ""))
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name or ""):
                continue
            if self._ia_norm_stratagem_name(reaction.get("stratagem", "")) != expected_name:
                continue
            if self._ia_root(reaction.get("attacking_unit")) is attacking_unit:
                return
        payload = {
            "event": str(event_name or ""),
            "phase_name": str(phase_name or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "enemy_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": list(candidates or []),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_imperial_agents_imperialis_fleet_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        self._queue_imperial_agents_imperialis_fleet_targets_selected_reactions(
            attacking_unit=attacking_unit,
            target_units=target_units,
            event_name="shooting_targets_selected",
            phase_name="Shooting phase",
        )

    def _queue_imperial_agents_imperialis_fleet_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        self._queue_imperial_agents_imperialis_fleet_targets_selected_reactions(
            attacking_unit=attacking_unit,
            target_units=target_units,
            event_name="fight_targets_selected",
            phase_name="Fight phase",
        )

    def _queue_imperial_agents_imperialis_fleet_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        event_name: str,
        phase_name: str,
    ) -> None:
        if not self._is_imperialis_fleet():
            return
        current_phase = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if current_phase != str(phase_name or "").strip().lower():
            return
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None or not self._ia_is_alive(attacking_root):
            return
        if self._ia_owned_by_player(attacking_root, self.player):
            return

        selfless = self.get_by_name("SELFLESS BODYGUARD")
        if (
            selfless is not None
            and self.player.command_points >= self._ia_effective_cp_cost(selfless, enemy_unit=attacking_root)
            and (selfless.name or "").strip().upper() not in self._used_stratagems_this_phase
        ):
            candidates = self._ia_imperialis_fleet_candidate_units(
                candidate_units=list(target_units or []),
                require_attached=True,
            )
            self._queue_imperial_agents_imperialis_fleet_targets_selected_reaction(
                event_name=event_name,
                phase_name=phase_name,
                stratagem=selfless,
                attacking_unit=attacking_root,
                target_units=list(target_units or []),
                candidates=candidates,
            )

        if str(phase_name or "").strip().lower() != "shooting phase":
            return
        displacer = self.get_by_name("DISPLACER FIELD")
        if (
            displacer is None
            or self.player.command_points < self._ia_effective_cp_cost(displacer, enemy_unit=attacking_root)
            or (displacer.name or "").strip().upper() in self._used_stratagems_this_phase
        ):
            return
        displacer_candidates = self._ia_imperialis_fleet_candidate_units(
            candidate_units=list(target_units or []),
            require_character=True,
            exclude_officio_assassinorum=True,
        )
        self._queue_imperial_agents_imperialis_fleet_targets_selected_reaction(
            event_name=event_name,
            phase_name=phase_name,
            stratagem=displacer,
            attacking_unit=attacking_root,
            target_units=list(target_units or []),
            candidates=displacer_candidates,
        )

    def _queue_imperial_agents_imperialis_fleet_shooting_resolved_reactions(
        self,
        *,
        attacker_unit: Any,
        hits_by_target: Any = None,
    ) -> None:
        del hits_by_target
        if not self._is_imperialis_fleet():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacking_root = self._ia_root(attacker_unit)
        if attacking_root is None or not self._ia_is_alive(attacking_root):
            return
        queue_move = getattr(game, "_queue_reactive_move_movement_decision", None)
        if not callable(queue_move):
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        attacker_id = self._ia_sort_key(attacking_root)
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not self._ia_effect_is_current(
                sr,
                prefix="imperial_agents_displacer_field",
                phase_key="SHOOTING_PHASE",
            ):
                continue
            if str(sr.get("imperial_agents_displacer_field_attacker_unit_id", "") or "") != attacker_id:
                continue
            if bool(sr.get("imperial_agents_displacer_field_move_triggered")):
                continue
            sr["imperial_agents_displacer_field_move_triggered"] = True
            root.special_rules = sr
            if not self._ia_is_on_battlefield(root):
                continue
            if self._ia_unit_within_engagement_range(root):
                continue
            source = str(sr.get("imperial_agents_displacer_field_source", "") or "Displacer Field").strip()
            queue_move(
                player=self.player,
                unit=root,
                max_distance=6,
                kind="imperial_agents_displacer_field",
                movement_type="reactive",
                reactive_movement_type="move",
                source=source or "Displacer Field",
                moving_unit=attacking_root,
                attacker_unit=attacking_root,
                allow_engagement_range=False,
                allow_skip=True,
            )

    def _queue_imperial_agents_ordo_hereticus_targets_selected_reaction(
        self,
        *,
        event_name: str,
        phase_name: str,
        stratagem: Any,
        attacking_unit: Any,
        target_units: list[Any],
        candidates: list[Any],
    ) -> None:
        if stratagem is None or attacking_unit is None or not candidates:
            return
        expected_name = self._ia_norm_stratagem_name(getattr(stratagem, "name", ""))
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name or ""):
                continue
            if self._ia_norm_stratagem_name(reaction.get("stratagem", "")) != expected_name:
                continue
            if self._ia_root(reaction.get("attacking_unit")) is attacking_unit:
                return
        payload = {
            "event": str(event_name or ""),
            "phase_name": str(phase_name or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "enemy_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": list(candidates or []),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_imperial_agents_ordo_hereticus_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        self._queue_imperial_agents_ordo_hereticus_targets_selected_reactions(
            attacking_unit=attacking_unit,
            target_units=target_units,
            event_name="shooting_targets_selected",
            phase_name="Shooting phase",
        )

    def _queue_imperial_agents_ordo_hereticus_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        self._queue_imperial_agents_ordo_hereticus_targets_selected_reactions(
            attacking_unit=attacking_unit,
            target_units=target_units,
            event_name="fight_targets_selected",
            phase_name="Fight phase",
        )

    def _queue_imperial_agents_ordo_hereticus_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        event_name: str,
        phase_name: str,
    ) -> None:
        if not self._is_ordo_hereticus_purgation_force():
            return
        current_phase = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if current_phase != str(phase_name or "").strip().lower():
            return
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None or not self._ia_is_alive(attacking_root):
            return
        if self._ia_owned_by_player(attacking_root, self.player):
            return

        inv = self.get_by_name("INVIOLATE JURISDICTION")
        if (
            inv is not None
            and self.player.command_points >= self._ia_effective_cp_cost(inv, enemy_unit=attacking_root)
            and (inv.name or "").strip().upper() not in self._used_stratagems_this_phase
        ):
            candidates = self._ia_inviolate_jurisdiction_candidates(list(target_units or []))
            self._queue_imperial_agents_ordo_hereticus_targets_selected_reaction(
                event_name=event_name,
                phase_name=phase_name,
                stratagem=inv,
                attacking_unit=attacking_root,
                target_units=list(target_units or []),
                candidates=candidates,
            )

    def _queue_imperial_agents_ordo_hereticus_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        snapshots = self._ia_exact_punishment_snapshots()
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "SHOOTING_PHASE" or player is self.player:
            snapshots.clear()
        if not self._is_ordo_hereticus_purgation_force():
            return
        if phase_key == "COMMAND_PHASE":
            if player is self.player:
                get_army = getattr(self.player, "get_army", None)
                army = get_army() if callable(get_army) else getattr(self.player, "army", None)
                if army is not None:
                    seen: set[str] = set()
                    for unit in list(getattr(army, "units", []) or []):
                        root = self._ia_root(unit)
                        if root is None:
                            continue
                        uid = self._ia_sort_key(root)
                        if uid and uid in seen:
                            continue
                        if uid:
                            seen.add(uid)
                        sr = getattr(root, "special_rules", None)
                        if not isinstance(sr, dict) or not bool(sr.get("imperial_agents_execution_order_active")):
                            continue
                        try:
                            marked_turn = int(sr.get("imperial_agents_execution_order_turn", 0) or 0)
                        except (TypeError, ValueError):
                            marked_turn = 0
                        try:
                            current_turn = int(getattr(getattr(self, "game", None), "turn", 0) or 0)
                        except (TypeError, ValueError):
                            current_turn = 0
                        if current_turn and marked_turn and current_turn > marked_turn:
                            for key in (
                                "imperial_agents_execution_order_active",
                                "imperial_agents_execution_order_source",
                                "imperial_agents_execution_order_turn",
                                "imperial_agents_execution_order_turn_owner",
                                "imperial_agents_execution_order_enemy_unit_id",
                                "imperial_agents_execution_order_enemy_unit_name",
                            ):
                                sr.pop(key, None)
                            root.special_rules = sr
            return
        stratagem = self.get_by_name("STUN GRENADES")
        if stratagem is None:
            return
        if self.player.command_points < self._ia_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates, enemy_by_unit = self._ia_stun_grenades_candidates()
        if not candidates:
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip() or str(getattr(phase, "name", "") or "")
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                str(reaction.get("event", "") or "") == "phase_start"
                and str(reaction.get("phase_name", "") or "").strip().lower() == str(phase_name or "").strip().lower()
                and self._ia_norm_stratagem_name(reaction.get("stratagem", "")) == "STUN GRENADES"
            ):
                return
        payload = {
            "event": "phase_start",
            "phase": phase_name,
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
            "enemy_candidates_by_unit": enemy_by_unit,
        }
        if len(candidates) == 1:
            only = candidates[0]
            only_id = self._ia_sort_key(only)
            payload["unit"] = only
            payload["target_unit"] = only
            only_targets = list(enemy_by_unit.get(only_id) or [])
            if len(only_targets) == 1:
                payload["enemy_unit"] = only_targets[0]
                payload["target_enemy_unit"] = only_targets[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_imperial_agents_ordo_malleus_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_ordo_malleus_daemon_hunters():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "COMMAND_PHASE":
            return
        stratagem = self.get_by_name("RITUAL OF WARDING")
        if stratagem is None:
            return
        if self.player.command_points < self._ia_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates, objectives_by_unit = self._ia_ritual_of_warding_candidates()
        if not candidates:
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "").strip() or "Command phase"
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                str(reaction.get("event", "") or "") == "phase_start"
                and str(reaction.get("phase_name", "") or "").strip().lower() == "command phase"
                and self._ia_norm_stratagem_name(reaction.get("stratagem", "")) == "RITUAL OF WARDING"
            ):
                return
        payload = {
            "event": "phase_start",
            "phase": phase_name,
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
            "objective_candidates_by_unit": objectives_by_unit,
        }
        if len(candidates) == 1:
            only = candidates[0]
            only_id = self._ia_sort_key(only)
            payload["unit"] = only
            payload["target_unit"] = only
            only_objectives = list(objectives_by_unit.get(only_id) or [])
            if len(only_objectives) == 1:
                payload["objective"] = only_objectives[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_imperial_agents_ordo_malleus_targets_selected_reaction(
        self,
        *,
        event_name: str,
        phase_name: str,
        stratagem: Any,
        attacking_unit: Any,
        target_units: list[Any],
        candidates: list[Any],
    ) -> None:
        if stratagem is None or attacking_unit is None or not candidates:
            return
        expected_name = self._ia_norm_stratagem_name(getattr(stratagem, "name", ""))
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name or ""):
                continue
            if self._ia_norm_stratagem_name(reaction.get("stratagem", "")) != expected_name:
                continue
            if self._ia_root(reaction.get("attacking_unit")) is attacking_unit:
                return
        payload = {
            "event": str(event_name or ""),
            "phase_name": str(phase_name or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "enemy_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": list(candidates or []),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_imperial_agents_ordo_malleus_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        self._queue_imperial_agents_ordo_malleus_targets_selected_reactions(
            attacking_unit=attacking_unit,
            target_units=target_units,
            event_name="shooting_targets_selected",
            phase_name="Shooting phase",
        )

    def _queue_imperial_agents_ordo_malleus_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        self._queue_imperial_agents_ordo_malleus_targets_selected_reactions(
            attacking_unit=attacking_unit,
            target_units=target_units,
            event_name="fight_targets_selected",
            phase_name="Fight phase",
        )

    def _queue_imperial_agents_ordo_malleus_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        event_name: str,
        phase_name: str,
    ) -> None:
        if not self._is_ordo_malleus_daemon_hunters():
            return
        current_phase = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if current_phase != str(phase_name or "").strip().lower():
            return
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None or not self._ia_is_alive(attacking_root):
            return
        if self._ia_owned_by_player(attacking_root, self.player):
            return
        hexagrammic = self.get_by_name("HEXAGRAMMIC WARDS")
        if (
            hexagrammic is None
            or self.player.command_points < self._ia_effective_cp_cost(hexagrammic, enemy_unit=attacking_root)
            or (hexagrammic.name or "").strip().upper() in self._used_stratagems_this_phase
        ):
            return
        candidates = self._ia_hexagrammic_wards_candidates(list(target_units or []))
        self._queue_imperial_agents_ordo_malleus_targets_selected_reaction(
            event_name=event_name,
            phase_name=phase_name,
            stratagem=hexagrammic,
            attacking_unit=attacking_root,
            target_units=list(target_units or []),
            candidates=candidates,
        )

    def _queue_imperial_agents_ordo_malleus_move_end_reactions(self, *, unit: Any, action: str) -> None:
        if not self._is_ordo_malleus_daemon_hunters():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "movement phase":
            return
        action_key = str(action or "").strip().lower()
        if action_key != "fall_back":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return
        moved_root = self._ia_root(unit)
        if moved_root is None or not self._ia_owned_by_player(moved_root, self.player):
            return
        stratagem = self.get_by_name("STEEL HEART")
        if stratagem is None:
            return
        if self.player.command_points < self._ia_effective_cp_cost(stratagem, target_unit=moved_root):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._ia_steel_heart_candidates(moved_unit=moved_root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                str(reaction.get("event", "") or "") == "unit_move_ended"
                and self._ia_norm_stratagem_name(reaction.get("stratagem", "")) == "STEEL HEART"
                and self._ia_root(reaction.get("unit")) is moved_root
            ):
                return
        payload = {
            "event": "unit_move_ended",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": moved_root,
            "target_unit": moved_root,
            "candidates": candidates,
            "action": str(action or ""),
        }
        self._queue_reaction(payload)

    def _resolve_imperial_agents_ordo_malleus_battle_shock_effects(self, *, unit: Any, passed: bool) -> None:
        if not self._is_ordo_malleus_daemon_hunters():
            return
        root = self._ia_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("imperial_agents_rites_of_exorcism_pending")):
            return
        owner_id = str(sr.get("imperial_agents_rites_of_exorcism_owner", "") or "")
        current_owner_id = str(getattr(self.player, "id", "") or "")
        if owner_id and current_owner_id and owner_id != current_owner_id:
            return
        source = str(sr.get("imperial_agents_rites_of_exorcism_source", "") or "Rites of Exorcism").strip()
        marked_turn = int(sr.get("imperial_agents_rites_of_exorcism_turn", 0) or 0)
        for key in (
            "imperial_agents_rites_of_exorcism_pending",
            "imperial_agents_rites_of_exorcism_owner",
            "imperial_agents_rites_of_exorcism_turn",
            "imperial_agents_rites_of_exorcism_source",
            "imperial_agents_rites_of_exorcism_source_unit_id",
        ):
            sr.pop(key, None)
        if not passed:
            active_player = getattr(getattr(self, "game", None), "get_current_player", lambda: None)()
            phase_key = str(getattr(getattr(getattr(self, "game", None), "phase", None), "name", "") or "").strip().upper()
            sr["imperial_agents_rites_of_exorcism_active"] = True
            sr["imperial_agents_rites_of_exorcism_source"] = source or "Rites of Exorcism"
            sr["imperial_agents_rites_of_exorcism_expires_phase"] = phase_key
            sr["imperial_agents_rites_of_exorcism_turn"] = int(marked_turn)
            sr["imperial_agents_rites_of_exorcism_turn_owner"] = str(getattr(active_player, "id", "") or "")
        root.special_rules = sr

    def _capture_imperial_agents_exact_punishment_destroyed_unit(
        self,
        *,
        unit: Any,
        destroyed_by_unit: Any,
    ) -> None:
        if not self._is_ordo_hereticus_purgation_force():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        destroyed_root = self._ia_root(unit)
        attacker_root = self._ia_root(destroyed_by_unit)
        if destroyed_root is None or attacker_root is None:
            return
        if not self._ia_owned_by_player(destroyed_root, self.player):
            return
        if not self._ia_is_agents_unit(destroyed_root):
            return
        if self._ia_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("EXACT PUNISHMENT")
        if stratagem is None:
            return
        if self.player.command_points < self._ia_effective_cp_cost(stratagem, enemy_unit=attacker_root):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        game_map = getattr(game, "map", None)
        can_shoot_fn = getattr(game, "_setup_reactive_can_shoot_target", None)
        if game_map is None or not callable(can_shoot_fn):
            return
        candidates: list[Any] = []
        for candidate in list(self._ia_ordo_hereticus_candidate_units() or []):
            root = self._ia_root(candidate)
            if root is None or root is destroyed_root:
                continue
            try:
                distance = float(game_map.get_distance_between_units(root, destroyed_root))
            except (AttributeError, TypeError, ValueError):
                continue
            if distance > 6.0:
                continue
            if not can_shoot_fn(root, attacker_root):
                continue
            candidates.append(root)
        if not candidates:
            return
        attacker_id = self._ia_sort_key(attacker_root)
        if not attacker_id:
            return
        entry = dict(self._ia_exact_punishment_snapshots().get(attacker_id) or {})
        candidate_by_id = dict(entry.get("candidate_by_id") or {})
        for candidate in list(candidates or []):
            candidate_id = self._ia_sort_key(candidate)
            if candidate_id:
                candidate_by_id[candidate_id] = candidate
        if not candidate_by_id:
            return
        self._ia_exact_punishment_snapshots()[attacker_id] = {
            "attacker_unit": attacker_root,
            "candidate_by_id": candidate_by_id,
        }

    def _queue_imperial_agents_ordo_hereticus_shooting_resolved_reactions(self, *, attacker_unit: Any) -> None:
        if not self._is_ordo_hereticus_purgation_force():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._ia_root(attacker_unit)
        if attacker_root is None or not self._ia_is_alive(attacker_root):
            return
        if self._ia_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("EXACT PUNISHMENT")
        if stratagem is None:
            return
        if self.player.command_points < self._ia_effective_cp_cost(stratagem, enemy_unit=attacker_root):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_id = self._ia_sort_key(attacker_root)
        if not attacker_id:
            return
        entry = dict(self._ia_exact_punishment_snapshots().pop(attacker_id, {}) or {})
        candidate_by_id = dict(entry.get("candidate_by_id") or {})
        if not candidate_by_id:
            return
        can_shoot_fn = getattr(game, "_setup_reactive_can_shoot_target", None)
        if not callable(can_shoot_fn):
            return
        candidates: list[Any] = []
        for candidate_id in sorted(candidate_by_id):
            root = self._ia_root(candidate_by_id.get(candidate_id))
            if root is None:
                continue
            if not self._ia_owned_by_player(root, self.player):
                continue
            if not self._ia_is_on_battlefield(root):
                continue
            if not self._ia_is_ordo_hereticus_purgation_unit(root):
                continue
            if not can_shoot_fn(root, attacker_root):
                continue
            candidates.append(root)
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                str(reaction.get("event", "") or "") == "unit_shooting_resolved"
                and self._ia_norm_stratagem_name(reaction.get("stratagem", "")) == "EXACT PUNISHMENT"
                and self._ia_root(reaction.get("enemy_unit")) is attacker_root
            ):
                return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "enemy_unit": attacker_root,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_imperial_agents_veiled_blade_targets_selected_reaction(
        self,
        *,
        event_name: str,
        phase_name: str,
        stratagem: Any,
        attacking_unit: Any,
        target_units: list[Any],
        candidates: list[Any],
    ) -> None:
        if stratagem is None or attacking_unit is None or not candidates:
            return
        expected_name = self._ia_norm_stratagem_name(getattr(stratagem, "name", ""))
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name or ""):
                continue
            if self._ia_norm_stratagem_name(reaction.get("stratagem", "")) != expected_name:
                continue
            if self._ia_root(reaction.get("attacking_unit")) is attacking_unit:
                return
        payload = {
            "event": str(event_name or ""),
            "phase_name": str(phase_name or ""),
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacking_unit,
            "enemy_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": list(candidates or []),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_imperial_agents_veiled_blade_charge_declared_reactions(
        self,
        *,
        charging_unit: Any,
        target_units: list[Any],
    ) -> None:
        if not self._is_veiled_blade_elimination_force():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "charge phase":
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        charging_root = self._ia_root(charging_unit)
        if charging_root is None or not self._ia_is_alive(charging_root):
            return
        stratagem = self.get_by_name("BLIND GRENADES")
        if stratagem is None:
            return
        if self.player.command_points < self._ia_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._ia_blind_grenades_candidates(list(target_units or []))
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                str(reaction.get("event", "") or "") == "charge_declared"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "BLIND GRENADES"
                and self._ia_root(reaction.get("charging_unit")) is charging_root
            ):
                return
        payload = {
            "event": "charge_declared",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "charging_unit": charging_root,
            "enemy_unit": charging_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_imperial_agents_veiled_blade_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        self._queue_imperial_agents_veiled_blade_targets_selected_reactions(
            attacking_unit=attacking_unit,
            target_units=target_units,
            event_name="shooting_targets_selected",
            phase_name="Shooting phase",
        )

    def _queue_imperial_agents_veiled_blade_fight_target_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> None:
        self._queue_imperial_agents_veiled_blade_targets_selected_reactions(
            attacking_unit=attacking_unit,
            target_units=target_units,
            event_name="fight_targets_selected",
            phase_name="Fight phase",
        )

    def _queue_imperial_agents_veiled_blade_targets_selected_reactions(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
        event_name: str,
        phase_name: str,
    ) -> None:
        if not self._is_veiled_blade_elimination_force():
            return
        current_phase = str(getattr(self, "_current_phase_name", "") or "").strip().lower()
        if current_phase != str(phase_name or "").strip().lower():
            return
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None or not self._ia_is_alive(attacking_root):
            return
        if self._ia_owned_by_player(attacking_root, self.player):
            return

        stratagem = self.get_by_name("HYPERSTIMMS")
        if (
            stratagem is not None
            and self.player.command_points >= self._ia_effective_cp_cost(stratagem, enemy_unit=attacking_root)
            and (stratagem.name or "").strip().upper() not in self._used_stratagems_this_phase
        ):
            candidates = self._ia_hyperstimms_candidates(list(target_units or []))
            self._queue_imperial_agents_veiled_blade_targets_selected_reaction(
                event_name=event_name,
                phase_name=phase_name,
                stratagem=stratagem,
                attacking_unit=attacking_root,
                target_units=list(target_units or []),
                candidates=candidates,
            )

        if str(phase_name or "").strip().lower() != "shooting phase":
            return
        orbital = self.get_by_name("ORBITAL OVERSIGHT")
        if (
            orbital is None
            or self.player.command_points < self._ia_effective_cp_cost(orbital, enemy_unit=attacking_root)
            or (orbital.name or "").strip().upper() in self._used_stratagems_this_phase
        ):
            return
        orbital_candidates = self._ia_orbital_oversight_candidates(list(target_units or []))
        self._queue_imperial_agents_veiled_blade_targets_selected_reaction(
            event_name=event_name,
            phase_name=phase_name,
            stratagem=orbital,
            attacking_unit=attacking_root,
            target_units=list(target_units or []),
            candidates=orbital_candidates,
        )

    def _queue_imperial_agents_veiled_blade_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_veiled_blade_elimination_force():
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return
        if player is self.player:
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "charge phase":
            return
        stratagem = self.get_by_name("ENSNARING TRAP")
        if stratagem is None:
            return
        if self.player.command_points < self._ia_effective_cp_cost(stratagem):
            return
        if (stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates, enemy_by_unit = self._ia_ensnaring_trap_candidates()
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if (
                str(reaction.get("event", "") or "") == "phase_end"
                and str(reaction.get("phase_name", "") or "").strip().lower() == "charge phase"
                and str(reaction.get("stratagem", "") or "").strip().upper() == "ENSNARING TRAP"
            ):
                return
        payload = {
            "event": "phase_end",
            "phase": "Charge phase",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
            "enemy_candidates_by_unit": enemy_by_unit,
        }
        if len(candidates) == 1:
            only = candidates[0]
            payload["unit"] = only
            payload["target_unit"] = only
            only_id = self._ia_sort_key(only)
            only_targets = list(enemy_by_unit.get(only_id) or [])
            if len(only_targets) == 1:
                payload["enemy_unit"] = only_targets[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_imperial_agents_veiled_blade_phase_end_effects(self, *, phase: Any) -> None:
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key not in {"COMMAND_PHASE", "MOVEMENT_PHASE", "CHARGE_PHASE", "SHOOTING_PHASE", "FIGHT_PHASE"}:
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        for p in list(getattr(game, "players", []) or []):
            army = getattr(p, "get_army", lambda: None)()
            if army is None:
                continue
            seen: set[str] = set()
            for unit in list(getattr(army, "units", []) or []):
                root = self._ia_root(unit)
                if root is None:
                    continue
                uid = self._ia_sort_key(root)
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                changed = False
                if phase_key == "CHARGE_PHASE":
                    mods = sr.get("charge_roll_modifiers")
                    if isinstance(mods, list):
                        keep: list[Any] = []
                        for item in mods:
                            if not isinstance(item, dict):
                                keep.append(item)
                                continue
                            if str(item.get("source_key", "") or "") != "imperial_agents_blind_grenades":
                                keep.append(item)
                                continue
                            exp = str(item.get("expires_phase", "") or "").strip().upper()
                            if exp and exp != phase_key:
                                keep.append(item)
                                continue
                            changed = True
                        if keep:
                            sr["charge_roll_modifiers"] = keep
                        elif "charge_roll_modifiers" in sr:
                            sr.pop("charge_roll_modifiers", None)
                if phase_key == "COMMAND_PHASE" and bool(sr.get("imperial_agents_execution_order_active")):
                    exp_owner = str(sr.get("imperial_agents_execution_order_turn_owner", "") or "")
                    current_owner = str(getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or "")
                    try:
                        current_turn = int(getattr(game, "turn", 0) or 0)
                    except (TypeError, ValueError):
                        current_turn = 0
                    try:
                        marked_turn = int(sr.get("imperial_agents_execution_order_turn", 0) or 0)
                    except (TypeError, ValueError):
                        marked_turn = 0
                    if (
                        current_turn
                        and marked_turn
                        and current_turn > marked_turn
                        and (not exp_owner or exp_owner == current_owner)
                    ):
                        for key in (
                            "imperial_agents_execution_order_active",
                            "imperial_agents_execution_order_source",
                            "imperial_agents_execution_order_turn",
                            "imperial_agents_execution_order_turn_owner",
                            "imperial_agents_execution_order_enemy_unit_id",
                            "imperial_agents_execution_order_enemy_unit_name",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key == "FIGHT_PHASE" and bool(sr.get("ensnaring_trap_callidus_melee_wound_bonus_active")):
                    exp = str(sr.get("ensnaring_trap_callidus_melee_wound_bonus_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "ensnaring_trap_callidus_melee_wound_bonus_active",
                            "ensnaring_trap_callidus_melee_wound_bonus",
                            "ensnaring_trap_callidus_melee_wound_bonus_source",
                            "ensnaring_trap_callidus_melee_wound_bonus_expires_phase",
                            "ensnaring_trap_callidus_melee_wound_bonus_turn",
                            "ensnaring_trap_callidus_melee_wound_bonus_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"} and bool(sr.get("imperial_agents_hyperstimms_active")):
                    exp = str(sr.get("imperial_agents_hyperstimms_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        remove_modifiers = getattr(root, "remove_characteristic_modifiers_by_source", None)
                        if callable(remove_modifiers):
                            remove_modifiers("stratagem:imperial_agents_hyperstimms")
                        for model in list(getattr(root, "models", []) or []):
                            clear_fnp = getattr(model, "set_temporary_fnp", None)
                            if callable(clear_fnp):
                                clear_fnp(key="imperial_agents_hyperstimms", value=0)
                            else:
                                effects = getattr(model, "_temporary_effects", None)
                                if isinstance(effects, dict):
                                    effects.pop("imperial_agents_hyperstimms", None)
                        for key in (
                            "imperial_agents_hyperstimms_active",
                            "imperial_agents_hyperstimms_source",
                            "imperial_agents_hyperstimms_expires_phase",
                            "imperial_agents_hyperstimms_turn",
                            "imperial_agents_hyperstimms_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"} and bool(sr.get("imperial_agents_dispense_justice_active")):
                    exp = str(sr.get("imperial_agents_dispense_justice_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_dispense_justice_active",
                            "imperial_agents_dispense_justice_source",
                            "imperial_agents_dispense_justice_expires_phase",
                            "imperial_agents_dispense_justice_turn",
                            "imperial_agents_dispense_justice_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"} and bool(sr.get("imperial_agents_prime_target_active")):
                    exp = str(sr.get("imperial_agents_prime_target_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_prime_target_active",
                            "imperial_agents_prime_target_source",
                            "imperial_agents_prime_target_expires_phase",
                            "imperial_agents_prime_target_turn",
                            "imperial_agents_prime_target_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"} and bool(sr.get("imperial_agents_inviolate_jurisdiction_active")):
                    exp = str(sr.get("imperial_agents_inviolate_jurisdiction_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for model in self._ia_unit_models(root):
                            clear_fnp = getattr(model, "set_temporary_fnp", None)
                            if callable(clear_fnp):
                                clear_fnp(key="imperial_agents_inviolate_jurisdiction", value=0)
                            else:
                                effects = getattr(model, "_temporary_effects", None)
                                if isinstance(effects, dict):
                                    effects.pop("imperial_agents_inviolate_jurisdiction", None)
                        for key in (
                            "imperial_agents_inviolate_jurisdiction_active",
                            "imperial_agents_inviolate_jurisdiction_source",
                            "imperial_agents_inviolate_jurisdiction_expires_phase",
                            "imperial_agents_inviolate_jurisdiction_turn",
                            "imperial_agents_inviolate_jurisdiction_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key == "SHOOTING_PHASE" and bool(sr.get("imperial_agents_orbital_oversight_active")):
                    exp = str(sr.get("imperial_agents_orbital_oversight_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_orbital_oversight_active",
                            "imperial_agents_orbital_oversight_source",
                            "imperial_agents_orbital_oversight_targeting_range",
                            "imperial_agents_orbital_oversight_lone_operative_targeting_range",
                            "imperial_agents_orbital_oversight_expires_phase",
                            "imperial_agents_orbital_oversight_turn",
                            "imperial_agents_orbital_oversight_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key == "SHOOTING_PHASE" and bool(sr.get("imperial_agents_will_sapping_salvo_active")):
                    exp = str(sr.get("imperial_agents_will_sapping_salvo_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for model in self._ia_unit_models(root):
                            effects = getattr(model, "_temporary_effects", None)
                            if not isinstance(effects, dict):
                                continue
                            remove_keys = [
                                key
                                for key in list(effects.keys())
                                if str(key or "").strip().lower().startswith("imperial_agents_will_sapping_salvo")
                            ]
                            for key in remove_keys:
                                effects.pop(key, None)
                        for key in (
                            "imperial_agents_will_sapping_salvo_active",
                            "imperial_agents_will_sapping_salvo_source",
                            "imperial_agents_will_sapping_salvo_expires_phase",
                            "imperial_agents_will_sapping_salvo_turn",
                            "imperial_agents_will_sapping_salvo_owner",
                            "imperial_agents_will_sapping_salvo_culexus_damage_override",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key == "MOVEMENT_PHASE" and bool(sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_active")):
                    exp = str(sr.get("imperial_agents_masters_of_the_void_enemy_dz_override_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_masters_of_the_void_enemy_dz_override_active",
                            "imperial_agents_masters_of_the_void_enemy_dz_override_turn_owner",
                            "imperial_agents_masters_of_the_void_enemy_dz_override_turn",
                            "imperial_agents_masters_of_the_void_enemy_dz_override_expires_phase",
                            "imperial_agents_masters_of_the_void_enemy_dz_override_source",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key == "SHOOTING_PHASE" and bool(sr.get("imperial_agents_close_quarters_barrage_active")):
                    exp = str(sr.get("imperial_agents_close_quarters_barrage_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_close_quarters_barrage_active",
                            "imperial_agents_close_quarters_barrage_source",
                            "imperial_agents_close_quarters_barrage_expires_phase",
                            "imperial_agents_close_quarters_barrage_turn",
                            "imperial_agents_close_quarters_barrage_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key == "SHOOTING_PHASE" and bool(sr.get("imperial_agents_line_of_fire_active")):
                    exp = str(sr.get("imperial_agents_line_of_fire_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_line_of_fire_active",
                            "imperial_agents_line_of_fire_source",
                            "imperial_agents_line_of_fire_expires_phase",
                            "imperial_agents_line_of_fire_turn",
                            "imperial_agents_line_of_fire_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"} and bool(sr.get("imperial_agents_violent_acquisition_active")):
                    exp = str(sr.get("imperial_agents_violent_acquisition_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_violent_acquisition_active",
                            "imperial_agents_violent_acquisition_source",
                            "imperial_agents_violent_acquisition_expires_phase",
                            "imperial_agents_violent_acquisition_turn",
                            "imperial_agents_violent_acquisition_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"} and bool(sr.get("imperial_agents_selfless_bodyguard_active")):
                    exp = str(sr.get("imperial_agents_selfless_bodyguard_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_selfless_bodyguard_active",
                            "imperial_agents_selfless_bodyguard_source",
                            "imperial_agents_selfless_bodyguard_expires_phase",
                            "imperial_agents_selfless_bodyguard_turn",
                            "imperial_agents_selfless_bodyguard_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key == "SHOOTING_PHASE" and bool(sr.get("imperial_agents_displacer_field_active")):
                    exp = str(sr.get("imperial_agents_displacer_field_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        current_move_types = list(sr.get("bearer_unit_phase_move_types") or [])
                        added_move_types = set(sr.get("imperial_agents_displacer_field_added_phase_move_types") or [])
                        if added_move_types:
                            kept_move_types = [move_type for move_type in current_move_types if move_type not in added_move_types]
                            if kept_move_types:
                                sr["bearer_unit_phase_move_types"] = sorted(set(kept_move_types))
                            else:
                                sr.pop("bearer_unit_phase_move_types", None)
                        effects = list(sr.get("ignore_vertical_distance_effects") or [])
                        kept_effects = [
                            effect
                            for effect in list(effects or [])
                            if not (
                                isinstance(effect, dict)
                                and str(effect.get("tag", "") or "").strip().lower() == "imperial_agents_displacer_field"
                            )
                        ]
                        if kept_effects:
                            sr["ignore_vertical_distance_effects"] = kept_effects
                        else:
                            sr.pop("ignore_vertical_distance_effects", None)
                        for model in self._ia_unit_models(root):
                            setter = getattr(model, "set_temporary_invulnerable_save", None)
                            if callable(setter):
                                setter(key="imperial_agents_displacer_field", value=0)
                            else:
                                effects = getattr(model, "_temporary_effects", None)
                                if isinstance(effects, dict):
                                    effects.pop("imperial_agents_displacer_field", None)
                        for key in (
                            "imperial_agents_displacer_field_active",
                            "imperial_agents_displacer_field_source",
                            "imperial_agents_displacer_field_expires_phase",
                            "imperial_agents_displacer_field_turn",
                            "imperial_agents_displacer_field_turn_owner",
                            "imperial_agents_displacer_field_attacker_unit_id",
                            "imperial_agents_displacer_field_move_triggered",
                            "imperial_agents_displacer_field_added_phase_move_types",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key != "COMMAND_PHASE" and bool(sr.get("imperial_agents_stun_grenades_active")):
                    exp = str(sr.get("imperial_agents_stun_grenades_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_stun_grenades_active",
                            "imperial_agents_stun_grenades_source",
                            "imperial_agents_stun_grenades_hit_roll_modifier",
                            "imperial_agents_stun_grenades_expires_phase",
                            "imperial_agents_stun_grenades_turn",
                            "imperial_agents_stun_grenades_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key == "SHOOTING_PHASE" and bool(sr.get("imperial_agents_psybolt_ammunition_active")):
                    exp = str(sr.get("imperial_agents_psybolt_ammunition_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_psybolt_ammunition_active",
                            "imperial_agents_psybolt_ammunition_source",
                            "imperial_agents_psybolt_ammunition_expires_phase",
                            "imperial_agents_psybolt_ammunition_turn",
                            "imperial_agents_psybolt_ammunition_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"} and bool(sr.get("imperial_agents_hexagrammic_wards_active")):
                    exp = str(sr.get("imperial_agents_hexagrammic_wards_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_hexagrammic_wards_active",
                            "imperial_agents_hexagrammic_wards_source",
                            "imperial_agents_hexagrammic_wards_expires_phase",
                            "imperial_agents_hexagrammic_wards_turn",
                            "imperial_agents_hexagrammic_wards_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if phase_key in {"SHOOTING_PHASE", "FIGHT_PHASE"} and bool(sr.get("imperial_agents_rites_of_exorcism_active")):
                    exp = str(sr.get("imperial_agents_rites_of_exorcism_expires_phase", "") or "").strip().upper()
                    if not exp or exp == phase_key:
                        for key in (
                            "imperial_agents_rites_of_exorcism_active",
                            "imperial_agents_rites_of_exorcism_source",
                            "imperial_agents_rites_of_exorcism_expires_phase",
                            "imperial_agents_rites_of_exorcism_turn",
                            "imperial_agents_rites_of_exorcism_turn_owner",
                        ):
                            sr.pop(key, None)
                        changed = True
                if changed:
                    root.special_rules = sr

    def _use_imperial_agents_ordo_hereticus_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_ordo_hereticus_purgation_force():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        name_n = self._ia_norm_stratagem_name(name_u)
        if name_n == "DISPENSE JUSTICE":
            return self._use_imperial_agents_dispense_justice(stratagem, **kwargs)
        if name_n == "EXACT PUNISHMENT":
            return self._use_imperial_agents_exact_punishment(stratagem, **kwargs)
        if name_n == "EXECUTION ORDER":
            return self._use_imperial_agents_execution_order(stratagem, **kwargs)
        if name_n == "INVIOLATE JURISDICTION":
            return self._use_imperial_agents_inviolate_jurisdiction(stratagem, **kwargs)
        if name_n == "LINE OF FIRE":
            return self._use_imperial_agents_line_of_fire(stratagem, **kwargs)
        if name_n == "STUN GRENADES":
            return self._use_imperial_agents_stun_grenades(stratagem, **kwargs)
        return None

    def _use_imperial_agents_ordo_malleus_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_ordo_malleus_daemon_hunters():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        name_n = self._ia_norm_stratagem_name(name_u)
        if name_n == "HEXAGRAMMIC WARDS":
            return self._use_imperial_agents_hexagrammic_wards(stratagem, **kwargs)
        if name_n == "PSYBOLT AMMUNITION":
            return self._use_imperial_agents_psybolt_ammunition(stratagem, **kwargs)
        if name_n == "RITES OF EXORCISM":
            return self._use_imperial_agents_rites_of_exorcism(stratagem, **kwargs)
        if name_n == "RITUAL OF WARDING":
            return self._use_imperial_agents_ritual_of_warding(stratagem, **kwargs)
        if name_n == "STEEL HEART":
            return self._use_imperial_agents_steel_heart(stratagem, **kwargs)
        return None

    def _use_imperial_agents_imperialis_fleet_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_imperialis_fleet():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        name_n = self._ia_norm_stratagem_name(name_u)
        if name_u == "MASTERS OF THE VOID":
            return self._use_imperial_agents_masters_of_the_void(stratagem, **kwargs)
        if name_n in {"CLOSE-QUARTERS BARRAGE", "CLOSE QUARTERS BARRAGE"}:
            return self._use_imperial_agents_close_quarters_barrage(stratagem, **kwargs)
        if name_n == "VIOLENT ACQUISITION":
            return self._use_imperial_agents_violent_acquisition(stratagem, **kwargs)
        if name_n in {"EMPEROR'S WILL", "EMPERORS WILL"}:
            return self._use_imperial_agents_emperors_will(stratagem, **kwargs)
        if name_n == "DISPLACER FIELD":
            return self._use_imperial_agents_displacer_field(stratagem, **kwargs)
        if name_n == "SELFLESS BODYGUARD":
            return self._use_imperial_agents_selfless_bodyguard(stratagem, **kwargs)
        return None

    def _use_imperial_agents_veiled_blade_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        if not self._is_veiled_blade_elimination_force():
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        name_n = self._ia_norm_stratagem_name(name_u)
        if name_u == "BLIND GRENADES":
            return self._use_imperial_agents_blind_grenades(stratagem, **kwargs)
        if name_u == "ENSNARING TRAP":
            return self._use_imperial_agents_ensnaring_trap(stratagem, **kwargs)
        if name_u == "HYPERSTIMMS":
            return self._use_imperial_agents_hyperstimms(stratagem, **kwargs)
        if name_u == "PRIME TARGET":
            return self._use_imperial_agents_prime_target(stratagem, **kwargs)
        if name_n == "ORBITAL OVERSIGHT":
            return self._use_imperial_agents_orbital_oversight(stratagem, **kwargs)
        if name_n == "WILL-SAPPING SALVO":
            return self._use_imperial_agents_will_sapping_salvo(stratagem, **kwargs)
        return None

    def _use_imperial_agents_masters_of_the_void(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_imperialis_fleet():
            return False
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: MASTERS OF THE VOID: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: MASTERS OF THE VOID: not your turn")
            return False

        candidates = self._ia_masters_of_the_void_candidates()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: MASTERS OF THE VOID: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: MASTERS OF THE VOID: target must be an eligible VOIDFARERS CHARACTER unit")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        turn_now = int(getattr(game, "turn", 0) or 0)
        owner_id = str(getattr(active_player, "id", "") or "")
        source = str(getattr(stratagem, "name", "MASTERS OF THE VOID") or "MASTERS OF THE VOID")
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ia_root(unit)
            if root is None:
                continue
            uid = self._ia_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ia_is_agents_unit(root):
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["imperial_agents_masters_of_the_void_enemy_dz_override_active"] = True
            sr["imperial_agents_masters_of_the_void_enemy_dz_override_turn_owner"] = owner_id
            sr["imperial_agents_masters_of_the_void_enemy_dz_override_turn"] = int(turn_now)
            sr["imperial_agents_masters_of_the_void_enemy_dz_override_expires_phase"] = "MOVEMENT_PHASE"
            sr["imperial_agents_masters_of_the_void_enemy_dz_override_source"] = source
            root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_close_quarters_barrage(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CLOSE-QUARTERS BARRAGE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: CLOSE-QUARTERS BARRAGE: not your turn")
            return False
        candidates = self._ia_imperialis_fleet_candidate_units(require_voidfarers=True)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: CLOSE-QUARTERS BARRAGE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: CLOSE-QUARTERS BARRAGE: target must be an eligible VOIDFARERS unit")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        turn_now = int(getattr(game, "turn", 0) or 0)
        owner_id = str(getattr(active_player, "id", "") or "")
        source = str(getattr(stratagem, "name", "") or "Close-Quarters Barrage").strip() or "Close-Quarters Barrage"
        sr["imperial_agents_close_quarters_barrage_active"] = True
        sr["imperial_agents_close_quarters_barrage_source"] = source
        sr["imperial_agents_close_quarters_barrage_expires_phase"] = "SHOOTING_PHASE"
        sr["imperial_agents_close_quarters_barrage_turn"] = int(turn_now)
        sr["imperial_agents_close_quarters_barrage_turn_owner"] = owner_id
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_dispense_justice(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: DISPENSE JUSTICE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: DISPENSE JUSTICE: not your turn")
            return False
        candidates = self._ia_dispense_justice_candidates(phase_name=phase_name)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: DISPENSE JUSTICE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error(
                "ERROR: DISPENSE JUSTICE: target must be an eligible ADEPTUS ARBITES, INQUISITORIAL AGENTS, or ORDO HERETICUS unit that has not acted"
            )
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False

        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_dispense_justice_active"] = True
        sr["imperial_agents_dispense_justice_source"] = str(getattr(stratagem, "name", "DISPENSE JUSTICE") or "DISPENSE JUSTICE")
        sr["imperial_agents_dispense_justice_expires_phase"] = phase_key
        sr["imperial_agents_dispense_justice_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_dispense_justice_turn_owner"] = str(getattr(active_player, "id", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_exact_punishment(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: EXACT PUNISHMENT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: EXACT PUNISHMENT: not opponent's Shooting phase")
            return False
        attacker_unit = context.get("attacking_unit") or context.get("enemy_unit") or context.get("attacker_unit")
        attacker_root = self._ia_root(attacker_unit)
        if attacker_root is None or self._ia_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: EXACT PUNISHMENT: missing or invalid attacking unit")
            return False
        candidates = list(context.get("candidates") or [])
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: EXACT PUNISHMENT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: EXACT PUNISHMENT: target must be a queued nearby Ordo Hereticus unit")
            return False
        setup_can_shoot = getattr(game, "_setup_reactive_can_shoot_target", None)
        if not callable(setup_can_shoot) or not bool(setup_can_shoot(target_root, attacker_root)):
            logger.error("ERROR: EXACT PUNISHMENT: target cannot shoot the attacking unit")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacker_root):
            return False

        request = None
        queue_reactive = getattr(game, "_queue_setup_reactive_shooting_decision", None)
        if callable(queue_reactive):
            request = queue_reactive(
                player=self.player,
                unit=target_root,
                target_unit=attacker_root,
                source=str(getattr(stratagem, "name", "EXACT PUNISHMENT") or "EXACT PUNISHMENT"),
            )
        if request is None:
            logger.error("ERROR: EXACT PUNISHMENT: failed to queue reactive shooting decision")
            return False
        request.context["imperial_agents_exact_punishment_flow"] = True
        request.context["imperial_agents_exact_punishment_source"] = str(
            getattr(stratagem, "name", "EXACT PUNISHMENT") or "EXACT PUNISHMENT"
        )
        request.context["imperial_agents_exact_punishment_enemy_unit_id"] = str(get_entity_id(attacker_root) or "")
        request.context["imperial_agents_exact_punishment_unit_id"] = str(get_entity_id(target_root) or "")
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_execution_order(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: EXECUTION ORDER: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: EXECUTION ORDER: not your Command phase")
            return False
        candidates = self._ia_execution_order_candidates()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: EXECUTION ORDER: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: EXECUTION ORDER: target must be an eligible Ordo Hereticus INFANTRY unit")
            return False
        enemy_candidates = self._ia_ordo_hereticus_enemy_character_candidates()
        enemy_unit = context.get("enemy_unit") or context.get("target_enemy_unit")
        enemy_root = self._ia_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: EXECUTION ORDER: missing enemy CHARACTER unit")
                return False
        if enemy_root not in enemy_candidates:
            logger.error("ERROR: EXECUTION ORDER: selected enemy must be an eligible CHARACTER unit")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_execution_order_active"] = True
        sr["imperial_agents_execution_order_source"] = str(getattr(stratagem, "name", "EXECUTION ORDER") or "EXECUTION ORDER")
        sr["imperial_agents_execution_order_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_execution_order_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["imperial_agents_execution_order_enemy_unit_id"] = str(get_entity_id(enemy_root) or "")
        sr["imperial_agents_execution_order_enemy_unit_name"] = str(getattr(enemy_root, "name", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_inviolate_jurisdiction(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: INVIOLATE JURISDICTION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: INVIOLATE JURISDICTION: not opponent's Shooting phase")
            return False
        attacking_unit = context.get("attacking_unit") or context.get("enemy_unit") or context.get("attacker_unit")
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None or self._ia_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: INVIOLATE JURISDICTION: missing or invalid attacking unit")
            return False
        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        candidates = self._ia_inviolate_jurisdiction_candidates(list(target_units or []))
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: INVIOLATE JURISDICTION: missing target unit")
                return False
        if target_root not in candidates:
            logger.error(
                "ERROR: INVIOLATE JURISDICTION: target must be a selected Ordo Hereticus INFANTRY unit within objective range"
            )
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False

        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        source = str(getattr(stratagem, "name", "INVIOLATE JURISDICTION") or "INVIOLATE JURISDICTION")
        for model in list(self._ia_unit_models(target_root) or []):
            set_temporary_fnp = getattr(model, "set_temporary_fnp", None)
            if callable(set_temporary_fnp):
                set_temporary_fnp(
                    key="imperial_agents_inviolate_jurisdiction",
                    value=5,
                    source=source,
                    expires_phase=phase_key,
                )
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_inviolate_jurisdiction_active"] = True
        sr["imperial_agents_inviolate_jurisdiction_source"] = source
        sr["imperial_agents_inviolate_jurisdiction_expires_phase"] = phase_key
        sr["imperial_agents_inviolate_jurisdiction_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_inviolate_jurisdiction_turn_owner"] = str(getattr(active_player, "id", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_line_of_fire(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: LINE OF FIRE: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: LINE OF FIRE: not your Shooting phase")
            return False
        candidates = self._ia_line_of_fire_candidates()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: LINE OF FIRE: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: LINE OF FIRE: target must be an eligible Ordo Hereticus unit that has not shot")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_line_of_fire_active"] = True
        sr["imperial_agents_line_of_fire_source"] = str(getattr(stratagem, "name", "LINE OF FIRE") or "LINE OF FIRE")
        sr["imperial_agents_line_of_fire_expires_phase"] = "SHOOTING_PHASE"
        sr["imperial_agents_line_of_fire_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_line_of_fire_turn_owner"] = str(getattr(active_player, "id", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_stun_grenades(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name == "command phase" or not phase_name:
            logger.error("ERROR: STUN GRENADES: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        candidates, enemy_by_unit = self._ia_stun_grenades_candidates()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: STUN GRENADES: missing source unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: STUN GRENADES: source unit is not eligible")
            return False
        root_id = self._ia_sort_key(target_root)
        valid_enemies = list(enemy_by_unit.get(root_id) or self._ia_ordo_hereticus_stun_grenades_enemy_candidates_for_unit(target_root))
        enemy_unit = context.get("enemy_unit") or context.get("target_enemy_unit")
        enemy_root = self._ia_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(valid_enemies) == 1:
                enemy_root = valid_enemies[0]
            else:
                logger.error("ERROR: STUN GRENADES: missing enemy target")
                return False
        if enemy_root not in valid_enemies:
            logger.error("ERROR: STUN GRENADES: selected enemy is not eligible")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False

        current_turn = int(getattr(game, "turn", 0) or 0)
        source = str(getattr(stratagem, "name", "STUN GRENADES") or "STUN GRENADES")
        take_test = getattr(enemy_root, "take_battle_shock_test", None)
        if callable(take_test):
            take_test(current_turn)
        enemy_sr = getattr(enemy_root, "special_rules", None)
        if not isinstance(enemy_sr, dict):
            enemy_sr = {}
        enemy_sr["imperial_agents_stun_grenades_active"] = True
        enemy_sr["imperial_agents_stun_grenades_source"] = source
        enemy_sr["imperial_agents_stun_grenades_hit_roll_modifier"] = -1
        enemy_sr["imperial_agents_stun_grenades_expires_phase"] = str(
            getattr(getattr(game, "phase", None), "name", "") or ""
        ).strip().upper()
        enemy_sr["imperial_agents_stun_grenades_turn"] = current_turn
        enemy_sr["imperial_agents_stun_grenades_turn_owner"] = str(
            getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or ""
        )
        enemy_root.special_rules = enemy_sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_hexagrammic_wards(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: HEXAGRAMMIC WARDS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: HEXAGRAMMIC WARDS: not opponent's phase")
            return False
        attacking_unit = context.get("attacking_unit") or context.get("enemy_unit") or context.get("attacker_unit")
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None or self._ia_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: HEXAGRAMMIC WARDS: missing or invalid attacking unit")
            return False
        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        candidates = self._ia_hexagrammic_wards_candidates(list(target_units or []))
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: HEXAGRAMMIC WARDS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: HEXAGRAMMIC WARDS: target must be a selected Ordo Malleus unit")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False

        sr = getattr(attacking_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr["imperial_agents_hexagrammic_wards_active"] = True
        sr["imperial_agents_hexagrammic_wards_source"] = str(
            getattr(stratagem, "name", "HEXAGRAMMIC WARDS") or "HEXAGRAMMIC WARDS"
        )
        sr["imperial_agents_hexagrammic_wards_expires_phase"] = phase_key
        sr["imperial_agents_hexagrammic_wards_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_hexagrammic_wards_turn_owner"] = str(getattr(active_player, "id", "") or "")
        attacking_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_psybolt_ammunition(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PSYBOLT AMMUNITION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: PSYBOLT AMMUNITION: not your Shooting phase")
            return False
        candidates = self._ia_psybolt_ammunition_candidates()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PSYBOLT AMMUNITION: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: PSYBOLT AMMUNITION: target must be an eligible Grey Knights Terminator Squad that has not shot")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_psybolt_ammunition_active"] = True
        sr["imperial_agents_psybolt_ammunition_source"] = str(
            getattr(stratagem, "name", "PSYBOLT AMMUNITION") or "PSYBOLT AMMUNITION"
        )
        sr["imperial_agents_psybolt_ammunition_expires_phase"] = "SHOOTING_PHASE"
        sr["imperial_agents_psybolt_ammunition_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_psybolt_ammunition_turn_owner"] = str(getattr(active_player, "id", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_rites_of_exorcism(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: RITES OF EXORCISM: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: RITES OF EXORCISM: only your Shooting phase is eligible")
            return False
        candidates = self._ia_ordo_malleus_candidate_units()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: RITES OF EXORCISM: missing source unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: RITES OF EXORCISM: source unit is not eligible")
            return False
        enemy_candidates = self._ia_ordo_malleus_enemy_daemon_candidates_for_unit(target_root)
        enemy_unit = context.get("enemy_unit") or context.get("target_enemy_unit")
        enemy_root = self._ia_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(enemy_candidates) == 1:
                enemy_root = enemy_candidates[0]
            else:
                logger.error("ERROR: RITES OF EXORCISM: missing enemy daemon")
                return False
        if enemy_root not in enemy_candidates:
            logger.error("ERROR: RITES OF EXORCISM: selected enemy must be a visible DAEMON within 12\"")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=enemy_root):
            return False

        enemy_sr = getattr(enemy_root, "special_rules", None)
        if not isinstance(enemy_sr, dict):
            enemy_sr = {}
        enemy_sr["imperial_agents_rites_of_exorcism_pending"] = True
        enemy_sr["imperial_agents_rites_of_exorcism_owner"] = str(getattr(self.player, "id", "") or "")
        enemy_sr["imperial_agents_rites_of_exorcism_turn"] = int(getattr(game, "turn", 0) or 0)
        enemy_sr["imperial_agents_rites_of_exorcism_source"] = str(
            getattr(stratagem, "name", "RITES OF EXORCISM") or "RITES OF EXORCISM"
        )
        enemy_sr["imperial_agents_rites_of_exorcism_source_unit_id"] = str(get_entity_id(target_root) or "")
        enemy_root.special_rules = enemy_sr
        force_test = getattr(enemy_root, "force_battle_shock_test", None)
        if callable(force_test):
            force_test(
                int(getattr(game, "turn", 0) or 0),
                source=str(getattr(stratagem, "name", "RITES OF EXORCISM") or "RITES OF EXORCISM"),
            )
        else:
            take_test = getattr(enemy_root, "take_battle_shock_test", None)
            if callable(take_test):
                take_test(int(getattr(game, "turn", 0) or 0))
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_ritual_of_warding(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: RITUAL OF WARDING: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        candidates, objectives_by_unit = self._ia_ritual_of_warding_candidates()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: RITUAL OF WARDING: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: RITUAL OF WARDING: target must be an eligible Ordo Malleus unit within objective range")
            return False
        objective_candidates = list(
            objectives_by_unit.get(self._ia_sort_key(target_root))
            or self._ia_ritual_of_warding_objective_candidates(target_root)
            or []
        )
        objective = context.get("objective") or context.get("objective_marker")
        if objective is None:
            if len(objective_candidates) == 1:
                objective = objective_candidates[0]
            else:
                logger.error("ERROR: RITUAL OF WARDING: missing objective marker")
                return False
        if objective not in objective_candidates:
            logger.error("ERROR: RITUAL OF WARDING: objective marker is not eligible")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False

        location = getattr(objective, "location", None)
        if location is None:
            logger.error("ERROR: RITUAL OF WARDING: selected objective has no location")
            return False
        set_sticky = getattr(location, "set_sticky_control", None)
        if callable(set_sticky):
            set_sticky(self.player, source="imperial_agents_ritual_of_warding")
        else:
            location.sticky_controller = self.player
            location.sticky_source = "imperial_agents_ritual_of_warding"
            location.controlling_player = self.player
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_steel_heart(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: STEEL HEART: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: STEEL HEART: not your turn")
            return False
        candidates = list(context.get("candidates") or self._ia_steel_heart_candidates(moved_unit=context.get("unit") or context.get("target_unit")))
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: STEEL HEART: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: STEEL HEART: target must be a Grey Knights Terminator Squad that just Fell Back")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_steel_heart_active"] = True
        sr["imperial_agents_steel_heart_source"] = str(getattr(stratagem, "name", "STEEL HEART") or "STEEL HEART")
        sr["imperial_agents_steel_heart_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_steel_heart_turn_owner"] = str(getattr(active_player, "id", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_violent_acquisition(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: VIOLENT ACQUISITION: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: VIOLENT ACQUISITION: not your turn")
            return False
        candidates = self._ia_imperialis_fleet_candidate_units()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: VIOLENT ACQUISITION: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: VIOLENT ACQUISITION: target must be an eligible AGENTS OF THE IMPERIUM unit")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        turn_now = int(getattr(game, "turn", 0) or 0)
        owner_id = str(getattr(active_player, "id", "") or "")
        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        source = str(getattr(stratagem, "name", "") or "Violent Acquisition").strip() or "Violent Acquisition"
        sr["imperial_agents_violent_acquisition_active"] = True
        sr["imperial_agents_violent_acquisition_source"] = source
        sr["imperial_agents_violent_acquisition_expires_phase"] = phase_key
        sr["imperial_agents_violent_acquisition_turn"] = int(turn_now)
        sr["imperial_agents_violent_acquisition_turn_owner"] = owner_id
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_emperors_will(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: EMPEROR'S WILL: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: EMPEROR'S WILL: not your turn")
            return False
        candidates = self._ia_imperialis_fleet_candidate_units()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: EMPEROR'S WILL: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: EMPEROR'S WILL: target must be an eligible AGENTS OF THE IMPERIUM unit")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        turn_now = int(getattr(game, "turn", 0) or 0)
        owner_id = str(getattr(active_player, "id", "") or "")
        source = str(getattr(stratagem, "name", "") or "Emperor's Will").strip() or "Emperor's Will"
        sr["imperial_agents_emperors_will_active"] = True
        sr["imperial_agents_emperors_will_source"] = source
        sr["imperial_agents_emperors_will_turn"] = int(turn_now)
        sr["imperial_agents_emperors_will_turn_owner"] = owner_id
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_displacer_field(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: DISPLACER FIELD: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: DISPLACER FIELD: not opponent's Shooting phase")
            return False
        attacking_unit = context.get("attacking_unit") or context.get("enemy_unit") or context.get("attacker_unit")
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None or self._ia_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: DISPLACER FIELD: missing or invalid attacking unit")
            return False
        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        candidates = self._ia_imperialis_fleet_candidate_units(
            candidate_units=list(target_units or []),
            require_character=True,
            exclude_officio_assassinorum=True,
        )
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: DISPLACER FIELD: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: DISPLACER FIELD: target must be an eligible selected AGENTS OF THE IMPERIUM CHARACTER unit")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False
        source = str(getattr(stratagem, "name", "") or "Displacer Field").strip() or "Displacer Field"
        for model in list(self._ia_unit_models(target_root) or []):
            setter = getattr(model, "set_temporary_invulnerable_save", None)
            if callable(setter):
                setter(
                    key="imperial_agents_displacer_field",
                    value=4,
                    source=source,
                    expires_phase="SHOOTING_PHASE",
                )
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current_move_types = set(sr.get("bearer_unit_phase_move_types") or [])
        added_move_types: list[str] = []
        if "move" not in current_move_types:
            current_move_types.add("move")
            added_move_types.append("move")
        if current_move_types:
            sr["bearer_unit_phase_move_types"] = sorted(current_move_types)
        if added_move_types:
            sr["imperial_agents_displacer_field_added_phase_move_types"] = list(added_move_types)
        else:
            sr.pop("imperial_agents_displacer_field_added_phase_move_types", None)
        current_effects = list(sr.get("ignore_vertical_distance_effects") or [])
        kept_effects = [
            effect
            for effect in list(current_effects or [])
            if not (
                isinstance(effect, dict)
                and str(effect.get("tag", "") or "").strip().lower() == "imperial_agents_displacer_field"
            )
        ]
        kept_effects.append(
            {
                "move_types": ["move"],
                "source": source,
                "tag": "imperial_agents_displacer_field",
            }
        )
        sr["ignore_vertical_distance_effects"] = kept_effects
        turn_now = int(getattr(game, "turn", 0) or 0)
        owner_id = str(getattr(active_player, "id", "") or "")
        sr["imperial_agents_displacer_field_active"] = True
        sr["imperial_agents_displacer_field_source"] = source
        sr["imperial_agents_displacer_field_expires_phase"] = "SHOOTING_PHASE"
        sr["imperial_agents_displacer_field_turn"] = int(turn_now)
        sr["imperial_agents_displacer_field_turn_owner"] = owner_id
        sr["imperial_agents_displacer_field_attacker_unit_id"] = self._ia_sort_key(attacking_root)
        sr["imperial_agents_displacer_field_move_triggered"] = False
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_selfless_bodyguard(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: SELFLESS BODYGUARD: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: SELFLESS BODYGUARD: not opponent's Shooting phase")
            return False
        attacking_unit = context.get("attacking_unit") or context.get("enemy_unit") or context.get("attacker_unit")
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None or self._ia_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: SELFLESS BODYGUARD: missing or invalid attacking unit")
            return False
        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        candidates = self._ia_imperialis_fleet_candidate_units(
            candidate_units=list(target_units or []),
            require_attached=True,
        )
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: SELFLESS BODYGUARD: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: SELFLESS BODYGUARD: target must be an eligible selected AGENTS OF THE IMPERIUM Attached unit")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        turn_now = int(getattr(game, "turn", 0) or 0)
        owner_id = str(getattr(active_player, "id", "") or "")
        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        source = str(getattr(stratagem, "name", "") or "Selfless Bodyguard").strip() or "Selfless Bodyguard"
        sr["imperial_agents_selfless_bodyguard_active"] = True
        sr["imperial_agents_selfless_bodyguard_source"] = source
        sr["imperial_agents_selfless_bodyguard_expires_phase"] = phase_key
        sr["imperial_agents_selfless_bodyguard_turn"] = int(turn_now)
        sr["imperial_agents_selfless_bodyguard_turn_owner"] = owner_id
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_blind_grenades(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: BLIND GRENADES: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: BLIND GRENADES: not opponent's turn")
            return False
        charging_unit = context.get("charging_unit") or context.get("enemy_unit") or context.get("attacker_unit")
        charging_root = self._ia_root(charging_unit)
        if charging_root is None:
            logger.error("ERROR: BLIND GRENADES: missing charging unit")
            return False
        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        candidates = self._ia_blind_grenades_candidates(target_units)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: BLIND GRENADES: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: BLIND GRENADES: target was not selected as a charge target")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=charging_root):
            return False
        sr = getattr(charging_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        mods = sr.get("charge_roll_modifiers")
        if not isinstance(mods, list):
            mods = []
        penalty = -2 if self._ia_is_vindicare_assassin_unit(target_root) else -1
        target_id = self._ia_sort_key(target_root)
        mods.append(
            {
                "value": int(penalty),
                "source": str(getattr(stratagem, "name", "BLIND GRENADES") or "BLIND GRENADES"),
                "source_key": "imperial_agents_blind_grenades",
                "expires_phase": "CHARGE_PHASE",
                "target_unit_ids": [target_id] if target_id else [],
            }
        )
        sr["charge_roll_modifiers"] = mods
        charging_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_ensnaring_trap(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: ENSNARING TRAP: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: ENSNARING TRAP: not opponent's turn")
            return False
        candidates, enemy_by_unit = self._ia_ensnaring_trap_candidates()
        unit = context.get("unit") or context.get("target_unit")
        root = self._ia_root(unit) if unit is not None else None
        if root is None:
            if len(candidates) == 1:
                root = candidates[0]
            else:
                logger.error("ERROR: ENSNARING TRAP: missing target unit")
                return False
        if root not in candidates:
            logger.error("ERROR: ENSNARING TRAP: target unit is not eligible")
            return False
        root_id = self._ia_sort_key(root)
        valid_enemies = list(enemy_by_unit.get(root_id) or self._ia_ensnaring_enemy_candidates_for_unit(root))
        enemy_unit = context.get("enemy_unit")
        enemy_root = self._ia_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            if len(valid_enemies) == 1:
                enemy_root = valid_enemies[0]
            elif valid_enemies:
                enemy_root = valid_enemies[0]
            else:
                logger.error("ERROR: ENSNARING TRAP: no eligible enemy target")
                return False
        if enemy_root not in valid_enemies:
            logger.error("ERROR: ENSNARING TRAP: selected enemy is not an eligible target")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=root, enemy_unit=enemy_root):
            return False
        ok = bool(game.attempt_charge(root, enemy_root, out_of_turn=True, count_as_charged=False))
        if ok and self._ia_is_callidus_assassin_unit(root):
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["ensnaring_trap_callidus_melee_wound_bonus_active"] = True
            sr["ensnaring_trap_callidus_melee_wound_bonus"] = 1
            sr["ensnaring_trap_callidus_melee_wound_bonus_source"] = str(
                getattr(stratagem, "name", "ENSNARING TRAP") or "ENSNARING TRAP"
            )
            sr["ensnaring_trap_callidus_melee_wound_bonus_expires_phase"] = "FIGHT_PHASE"
            sr["ensnaring_trap_callidus_melee_wound_bonus_turn"] = int(getattr(game, "turn", 0) or 0)
            sr["ensnaring_trap_callidus_melee_wound_bonus_turn_owner"] = str(
                getattr(getattr(game, "get_current_player", lambda: None)(), "id", "") or ""
            )
            root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        if not ok:
            logger.error("ERROR: ENSNARING TRAP: charge failed")
        return True

    def _use_imperial_agents_hyperstimms(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: HYPERSTIMMS: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is self.player:
            logger.error("ERROR: HYPERSTIMMS: not opponent's Shooting phase")
            return False
        attacking_unit = context.get("attacking_unit") or context.get("enemy_unit")
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None:
            logger.error("ERROR: HYPERSTIMMS: missing attacking unit")
            return False
        if self._ia_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: HYPERSTIMMS: attacking unit is not an enemy unit")
            return False
        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is not None and not target_units:
            target_units = [target_root]
        candidates = self._ia_hyperstimms_candidates(target_units)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: HYPERSTIMMS: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: HYPERSTIMMS: target was not selected as an attack target")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False

        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        source = str(getattr(stratagem, "name", "HYPERSTIMMS") or "HYPERSTIMMS")
        add_modifier = getattr(target_root, "add_characteristic_modifier", None)
        if callable(add_modifier):
            add_modifier("toughness", Modifier(ModifierOp.ADD, 1, source="stratagem:imperial_agents_hyperstimms"))
        if self._ia_is_eversor_assassin_unit(target_root):
            for model in list(getattr(target_root, "models", []) or []):
                set_temporary_fnp = getattr(model, "set_temporary_fnp", None)
                if callable(set_temporary_fnp):
                    set_temporary_fnp(
                        key="imperial_agents_hyperstimms",
                        value=4,
                        source=source,
                        expires_phase=phase_key,
                    )
                else:
                    effects = getattr(model, "_temporary_effects", None)
                    if not isinstance(effects, dict):
                        effects = {}
                        model._temporary_effects = effects
                    effects["imperial_agents_hyperstimms"] = {
                        "expires_phase": phase_key,
                        "temporary_fnp_value": 4,
                        "temporary_fnp_source": source,
                    }

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_hyperstimms_active"] = True
        sr["imperial_agents_hyperstimms_source"] = source
        sr["imperial_agents_hyperstimms_expires_phase"] = phase_key
        sr["imperial_agents_hyperstimms_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_hyperstimms_owner"] = str(getattr(self.player, "id", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_orbital_oversight(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: ORBITAL OVERSIGHT: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            logger.error("ERROR: ORBITAL OVERSIGHT: not opponent's Shooting phase")
            return False

        attacking_unit = context.get("attacking_unit") or context.get("attacker_unit") or context.get("enemy_unit")
        attacking_root = self._ia_root(attacking_unit)
        if attacking_root is None:
            logger.error("ERROR: ORBITAL OVERSIGHT: missing attacking unit")
            return False
        if self._ia_owned_by_player(attacking_root, self.player):
            logger.error("ERROR: ORBITAL OVERSIGHT: attacking unit is not an enemy unit")
            return False

        target_units = context.get("target_units")
        if not isinstance(target_units, list):
            target_units = []
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is not None and not target_units:
            target_units = [target_root]
        candidates = self._ia_orbital_oversight_candidates(target_units)
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: ORBITAL OVERSIGHT: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: ORBITAL OVERSIGHT: target must be an eligible AGENTS INFANTRY attack target")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root, enemy_unit=attacking_root):
            return False

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_orbital_oversight_active"] = True
        sr["imperial_agents_orbital_oversight_source"] = str(
            getattr(stratagem, "name", "ORBITAL OVERSIGHT") or "ORBITAL OVERSIGHT"
        )
        sr["imperial_agents_orbital_oversight_targeting_range"] = 18
        sr["imperial_agents_orbital_oversight_lone_operative_targeting_range"] = 6
        sr["imperial_agents_orbital_oversight_expires_phase"] = "SHOOTING_PHASE"
        sr["imperial_agents_orbital_oversight_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_orbital_oversight_turn_owner"] = str(getattr(self.player, "id", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_will_sapping_salvo(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: WILL-SAPPING SALVO: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            logger.error("ERROR: WILL-SAPPING SALVO: not your Shooting phase")
            return False

        candidates = self._ia_will_sapping_salvo_candidates()
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: WILL-SAPPING SALVO: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: WILL-SAPPING SALVO: target must be eligible AGENTS INFANTRY not yet selected to shoot")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False

        source = str(getattr(stratagem, "name", "WILL-SAPPING SALVO") or "WILL-SAPPING SALVO")
        phase_key = "SHOOTING_PHASE"
        is_culexus = self._ia_is_culexus_assassin_unit(target_root)
        for model_index, model in enumerate(self._ia_unit_models(target_root)):
            if model is None or not bool(getattr(model, "is_alive", True)):
                continue
            model_id = str(get_entity_id(model) or model_index)
            for wargear_index, wargear in enumerate(list(getattr(model, "wargear", []) or [])):
                if wargear is None:
                    continue
                is_ranged_fn = getattr(wargear, "is_ranged", None)
                if not callable(is_ranged_fn) or not bool(is_ranged_fn()):
                    continue
                weapon_name = str(getattr(wargear, "name", "") or "").strip()
                if not weapon_name:
                    continue
                key_base = f"imperial_agents_will_sapping_salvo:{model_id}:{wargear_index}:{weapon_name}".lower()
                set_keywords = getattr(model, "set_temporary_weapon_keyword_bonuses", None)
                if callable(set_keywords):
                    set_keywords(
                        key=key_base,
                        weapon_name=weapon_name,
                        keywords=["SUSTAINED HITS 1"],
                        source=source,
                        expires_phase=phase_key,
                        attack_type="ranged",
                    )
                else:
                    effects = getattr(model, "_temporary_effects", None)
                    if not isinstance(effects, dict):
                        effects = {}
                        model._temporary_effects = effects
                    effects[key_base] = {
                        "expires_phase": phase_key,
                        "weapon_keyword_bonuses": {weapon_name: ["SUSTAINED HITS 1"]},
                        "weapon_keyword_bonuses_source": source,
                        "weapon_keyword_bonuses_attack_type": "ranged",
                    }
                if not is_culexus:
                    continue
                damage_key = f"{key_base}:damage"
                set_damage_override = getattr(model, "set_temporary_weapon_damage_override", None)
                if callable(set_damage_override):
                    set_damage_override(
                        key=damage_key,
                        weapon_name=weapon_name,
                        damage_value=3,
                        source=source,
                        expires_phase=phase_key,
                    )
                else:
                    effects = getattr(model, "_temporary_effects", None)
                    if not isinstance(effects, dict):
                        effects = {}
                        model._temporary_effects = effects
                    effects[damage_key] = {
                        "expires_phase": phase_key,
                        "weapon_damage_override": {weapon_name: 3},
                        "weapon_damage_override_source": source,
                    }

        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_will_sapping_salvo_active"] = True
        sr["imperial_agents_will_sapping_salvo_source"] = source
        sr["imperial_agents_will_sapping_salvo_expires_phase"] = phase_key
        sr["imperial_agents_will_sapping_salvo_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_will_sapping_salvo_owner"] = str(getattr(self.player, "id", "") or "")
        sr["imperial_agents_will_sapping_salvo_culexus_damage_override"] = bool(is_culexus)
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True

    def _use_imperial_agents_prime_target(self, stratagem: Any, **kwargs) -> bool:
        context = self._ia_pending_context(stratagem.name, kwargs)
        phase_name = str(context.get("phase_name") or getattr(self, "_current_phase_name", "") or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: PRIME TARGET: wrong phase")
            return False
        game = getattr(self, "game", None)
        if game is None:
            return False
        active_player = getattr(game, "get_current_player", lambda: None)()
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: PRIME TARGET: can only be used in your Shooting phase")
            return False

        candidates = self._ia_prime_target_candidates(phase_name=phase_name)
        target_unit = context.get("unit") or context.get("target_unit")
        target_root = self._ia_root(target_unit) if target_unit is not None else None
        if target_root is None:
            if len(candidates) == 1:
                target_root = candidates[0]
            else:
                logger.error("ERROR: PRIME TARGET: missing target unit")
                return False
        if target_root not in candidates:
            logger.error("ERROR: PRIME TARGET: target must be an eligible AGENTS unit that has not acted")
            return False
        if not self._ia_spend_cp(stratagem, target_unit=target_root):
            return False

        phase_key = "SHOOTING_PHASE" if phase_name == "shooting phase" else "FIGHT_PHASE"
        sr = getattr(target_root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["imperial_agents_prime_target_active"] = True
        sr["imperial_agents_prime_target_source"] = str(getattr(stratagem, "name", "PRIME TARGET") or "PRIME TARGET")
        sr["imperial_agents_prime_target_expires_phase"] = phase_key
        sr["imperial_agents_prime_target_turn"] = int(getattr(game, "turn", 0) or 0)
        sr["imperial_agents_prime_target_owner"] = str(getattr(self.player, "id", "") or "")
        target_root.special_rules = sr
        self._ia_finalize_use(stratagem, dequeue=bool(context.get("dequeue")))
        return True
