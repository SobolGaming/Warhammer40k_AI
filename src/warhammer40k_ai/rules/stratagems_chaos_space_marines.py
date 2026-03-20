from __future__ import annotations

import logging
from typing import Any, Optional

from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class ChaosSpaceMarinesStratagemMixin:
    @staticmethod
    def _csm_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _csm_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    @staticmethod
    def _csm_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _csm_is_on_battlefield(unit: Any) -> bool:
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
    def _csm_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _csm_has_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        key = str(keyword or "").strip()
        if not key:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and bool(has_any(key)):
            return True
        has_keyword = getattr(entity, "has_keyword", None)
        if callable(has_keyword) and bool(has_keyword(key)):
            return True
        return False

    def _get_chaos_space_marines_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "chaos_space_marines_detachments", None) if army is not None else None

    def _is_cabal_of_chaos_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_cabal_of_chaos", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_chaos_cult_detachment(self) -> bool:
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "is_chaos_cult", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_heretic_astartes_unit(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "_unit_is_heretic_astartes", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._csm_has_keyword(root, "HERETIC ASTARTES")

    def _is_heretic_astartes_infantry(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_heretic_astartes_unit(root):
            return False
        return self._csm_has_keyword(root, "INFANTRY")

    def _is_damned_unit(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        mgr = self._get_chaos_space_marines_mgr()
        checker = getattr(mgr, "_unit_is_damned", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._csm_has_keyword(root, "DAMNED")

    def _is_cabal_psyker_source_unit(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_heretic_astartes_unit(root):
            return False
        return self._csm_has_keyword(root, "PSYKER")

    def _is_cabal_daemon_prince_source_unit(self, unit: Any) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_heretic_astartes_unit(root):
            return False
        if self._csm_has_keyword(root, "DAEMON PRINCE") or self._csm_has_keyword(root, "DAEMON PRINCE WITH WINGS"):
            return True
        normalized_name = " ".join(str(getattr(root, "name", "") or "").strip().lower().split())
        return "daemon prince" in normalized_name

    def _is_cabal_shroud_source_unit(self, unit: Any) -> bool:
        return self._is_cabal_psyker_source_unit(unit) or self._is_cabal_daemon_prince_source_unit(unit)

    def _cabal_within_empyric_support(self, unit: Any, *, radius: float = 9.0) -> bool:
        root = self._csm_root(unit)
        if root is None:
            return False
        helper = getattr(root, "_friendly_empyric_source_within_range", None)
        if callable(helper):
            if bool(helper(choice="LEAPING_WARPFLAME", radius=float(radius))):
                return True
            if bool(helper(choice="MONSTROUS_MANIFESTATION", radius=float(radius))):
                return True

        from ..utility.aura_utils import unit_within_range_of_unit

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return False
        seen: set[str] = set()
        for candidate in list(getattr(army, "units", []) or []):
            source_root = self._csm_root(candidate)
            if source_root is None:
                continue
            uid = self._csm_sort_key(source_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._is_cabal_shroud_source_unit(source_root):
                continue
            if not self._csm_is_alive(source_root) or not self._csm_is_on_battlefield(source_root):
                continue
            if unit_within_range_of_unit(source_root, root, float(radius), use_attached_aggregate=True):
                return True
        return False

    def _cabal_targetable_units(
        self,
        *,
        require_infantry: bool = False,
        require_not_shot: bool = False,
        require_not_attempted_charge: bool = False,
        require_psyker: bool = False,
        require_within_empyric_support: bool = False,
        require_shroud_source: bool = False,
    ) -> list[Any]:
        if not self._is_cabal_of_chaos_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_heretic_astartes_unit(root):
                continue
            if require_infantry and not self._is_heretic_astartes_infantry(root):
                continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_not_attempted_charge and bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
                continue
            if require_psyker and not self._is_cabal_psyker_source_unit(root):
                continue
            if require_within_empyric_support and not self._cabal_within_empyric_support(root, radius=9.0):
                continue
            if require_shroud_source and not self._is_cabal_shroud_source_unit(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _cabal_baleful_blessing_candidates(self) -> list[Any]:
        return self._cabal_targetable_units()

    def _cabal_soulseekers_candidates(self) -> list[Any]:
        return self._cabal_targetable_units(require_not_shot=True)

    def _cabal_unholy_haste_candidates(self) -> list[Any]:
        return self._cabal_targetable_units(require_infantry=True, require_not_attempted_charge=True)

    def _cabal_no_rest_in_death_candidates(self) -> list[Any]:
        return self._cabal_targetable_units(require_within_empyric_support=True)

    def _cabal_mutations_curse_source_candidates(self) -> list[Any]:
        return self._cabal_targetable_units(require_psyker=True)

    def _cabal_shroud_of_chaos_candidates(self) -> list[Any]:
        return self._cabal_targetable_units(require_shroud_source=True)

    def _chaos_cult_targetable_units(
        self,
        *,
        require_damned: bool = False,
        require_heretic_astartes: bool = False,
        require_dark_pacts: bool = False,
        require_not_shot: bool = False,
        require_not_fought: bool = False,
        require_not_attempted_charge: bool = False,
    ) -> list[Any]:
        if not self._is_chaos_cult_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        mgr = self._get_chaos_space_marines_mgr()
        has_dark_pacts = getattr(mgr, "_unit_has_dark_pacts", None) if mgr is not None else None

        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if require_damned and not self._is_damned_unit(root):
                continue
            if require_heretic_astartes and not self._is_heretic_astartes_unit(root):
                continue
            if require_dark_pacts and callable(has_dark_pacts) and not bool(has_dark_pacts(root)):
                continue
            round_state = getattr(root, "round_state", None)
            if require_not_shot and bool(getattr(round_state, "shot_this_round", False)):
                continue
            if require_not_fought and bool(getattr(round_state, "fought_this_phase", False)):
                continue
            if require_not_attempted_charge and bool(getattr(round_state, "attempted_charge_this_round", False)):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _chaos_cult_damned_shooting_candidates(self) -> list[Any]:
        return self._chaos_cult_targetable_units(
            require_damned=True,
            require_dark_pacts=True,
            require_not_shot=True,
        )

    def _chaos_cult_damned_fight_candidates(self) -> list[Any]:
        return self._chaos_cult_targetable_units(
            require_damned=True,
            require_dark_pacts=True,
            require_not_fought=True,
        )

    def _chaos_cult_reckless_haste_candidates(self) -> list[Any]:
        return self._chaos_cult_targetable_units(
            require_damned=True,
            require_not_attempted_charge=True,
        )

    def _csm_find_pending_reaction(self, stratagem_name: str, *, unit: Any = None):
        name_u = str(stratagem_name or "").strip().upper()
        expected_root = self._csm_root(unit)
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if expected_root is None:
                return reaction
            reaction_root = self._csm_root(reaction.get("unit") or reaction.get("target_unit"))
            if reaction_root is expected_root:
                return reaction
        return None

    def _chaos_cult_unit_visible_to_unit(self, source_unit: Any, target_unit: Any) -> bool:
        source_root = self._csm_root(source_unit)
        target_root = self._csm_root(target_unit)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if source_root is None or target_root is None or game_map is None:
            return False
        los_checker = getattr(source_root, "_attacking_unit_has_any_los_to_target_unit", None)
        return bool(callable(los_checker) and los_checker(target_root, game_map))

    def _chaos_cult_mortal_thralls_support_candidates(
        self,
        *,
        protected_unit: Any,
        attacking_unit: Any,
    ) -> list[Any]:
        protected_root = self._csm_root(protected_unit)
        attacker_root = self._csm_root(attacking_unit)
        if protected_root is None or attacker_root is None:
            return []
        from ..utility.aura_utils import unit_within_range_of_unit

        support_pool = self._chaos_cult_targetable_units(require_damned=True)
        candidates: list[Any] = []
        for support_root in list(support_pool or []):
            if not unit_within_range_of_unit(protected_root, support_root, 3.0, use_attached_aggregate=True):
                continue
            if not self._chaos_cult_unit_visible_to_unit(protected_root, support_root):
                continue
            if not self._chaos_cult_unit_visible_to_unit(attacker_root, support_root):
                continue
            candidates.append(support_root)
        return sorted(candidates, key=self._csm_sort_key)

    def _chaos_cult_mortal_thralls_candidate_map(
        self,
        *,
        attacking_unit: Any,
        target_units: list[Any],
    ) -> dict[str, dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for target in list(target_units or []):
            protected_root = self._csm_root(target)
            if protected_root is None:
                continue
            uid = self._csm_sort_key(protected_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(protected_root, self.player):
                continue
            if not self._csm_is_alive(protected_root) or not self._csm_is_on_battlefield(protected_root):
                continue
            if self._unit_cannot_be_target_of_stratagem(protected_root):
                continue
            if not self._is_heretic_astartes_unit(protected_root):
                continue
            support_candidates = self._chaos_cult_mortal_thralls_support_candidates(
                protected_unit=protected_root,
                attacking_unit=attacking_unit,
            )
            if not support_candidates:
                continue
            candidates[uid] = {"unit": protected_root, "support_candidates": support_candidates}
        return candidates

    def _chaos_cult_selfless_demise_candidates(self, *, target_units: list[Any]) -> list[Any]:
        candidates: list[Any] = []
        seen: set[str] = set()
        for target in list(target_units or []):
            root = self._csm_root(target)
            if root is None:
                continue
            uid = self._csm_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_owned_by_player(root, self.player):
                continue
            if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
                continue
            if self._unit_cannot_be_target_of_stratagem(root):
                continue
            if not self._is_damned_unit(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._csm_sort_key)

    def _cabal_mutations_curse_enemy_candidates(self, source_unit: Any, *, radius: float = 12.0) -> list[Any]:
        source_root = self._csm_root(source_unit)
        if source_root is None:
            return []
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            return []

        from ..utility.aura_utils import unit_within_range_of_unit

        candidates: list[Any] = []
        seen: set[str] = set()
        los_checker = getattr(source_root, "_attacking_unit_has_any_los_to_target_unit", None)
        for enemy in list(getattr(game_map, "get_enemy_units", lambda _u: [])(source_root) or []):
            enemy_root = self._csm_root(enemy)
            if enemy_root is None:
                continue
            uid = self._csm_sort_key(enemy_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._csm_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", False)):
                continue
            if not unit_within_range_of_unit(source_root, enemy_root, float(radius), use_attached_aggregate=True):
                continue
            if callable(los_checker) and not bool(los_checker(enemy_root, game_map)):
                continue
            candidates.append(enemy_root)
        return sorted(candidates, key=self._csm_sort_key)

    def _cabal_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _cabal_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._cabal_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _cabal_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _cabal_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        target_unit: Any = None,
    ) -> bool:
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name):
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != str(phase_name or "").strip().lower():
                continue
            if target_unit is not None and reaction.get("target_unit") is not target_unit and reaction.get("unit") is not target_unit:
                continue
            return True
        return False

    def _queue_cabal_of_chaos_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_cabal_of_chaos_detachment():
            return
        if str(getattr(phase, "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        if player is self.player:
            return

        stratagem = self.get_by_name("SHROUD OF CHAOS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates = self._cabal_shroud_of_chaos_candidates()
        if not candidates:
            return
        if self._cabal_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
        ):
            return

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
            payload["unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_cabal_of_chaos_mortal_wound_reaction(
        self,
        *,
        target_unit: Any,
        attacker_unit: Any = None,
        target_model: Any = None,
        phase_name: str = "",
    ) -> None:
        if not self._is_cabal_of_chaos_detachment():
            return
        root = self._csm_root(target_unit)
        if root is None:
            return
        if not self._csm_owned_by_player(root, self.player):
            return
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return
        if self._unit_cannot_be_target_of_stratagem(root):
            return
        if not self._is_heretic_astartes_unit(root):
            return

        stratagem = self.get_by_name("BALEFUL BLESSING")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        if not phase_name:
            phase_name = str(getattr(self, "_current_phase_name", "") or "")
        if not phase_name:
            phase_key = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
            name_map = {
                "COMMAND_PHASE": "Command phase",
                "MOVEMENT_PHASE": "Movement phase",
                "SHOOTING_PHASE": "Shooting phase",
                "CHARGE_PHASE": "Charge phase",
                "FIGHT_PHASE": "Fight phase",
            }
            phase_name = name_map.get(phase_key, phase_key.title().replace("_", " ")) if phase_key else ""
        if not phase_name:
            phase_name = "Any phase"

        if self._cabal_reaction_already_queued(
            event_name="mortal_wound_allocated",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            target_unit=root,
        ):
            return

        payload = {
            "event": "mortal_wound_allocated",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "target_unit": root,
            "unit": root,
            "attacking_unit": attacker_unit,
            "target_model": target_model,
            "candidates": [root],
            "mortal_wound_allocated": True,
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_chaos_cult_shooting_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_chaos_cult_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "shooting phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None:
            return
        if self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("MORTAL THRALLS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidate_map = self._chaos_cult_mortal_thralls_candidate_map(
            attacking_unit=attacking_unit,
            target_units=list(target_units or []),
        )
        if not candidate_map:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "shooting_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "MORTAL THRALLS":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        ordered_candidates = [entry["unit"] for entry in candidate_map.values()]
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": ordered_candidates,
            "support_candidates_by_unit": {
                key: list(entry["support_candidates"] or [])
                for key, entry in candidate_map.items()
            },
        }
        if len(ordered_candidates) == 1:
            protected_root = ordered_candidates[0]
            protected_key = self._csm_sort_key(protected_root)
            payload["unit"] = protected_root
            payload["target_unit"] = protected_root
            support_candidates = list(payload["support_candidates_by_unit"].get(protected_key, []) or [])
            if len(support_candidates) == 1:
                payload["support_unit"] = support_candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_chaos_cult_fight_target_reactions(self, *, attacking_unit: Any, target_units: list[Any]) -> None:
        if not self._is_chaos_cult_detachment():
            return
        if str(getattr(self, "_current_phase_name", "") or "").strip().lower() != "fight phase":
            return
        attacker_root = self._csm_root(attacking_unit)
        if attacker_root is None:
            return
        if self._csm_owned_by_player(attacker_root, self.player):
            return
        stratagem = self.get_by_name("SELFLESS DEMISE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if str(stratagem.name or "").strip().upper() in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._chaos_cult_selfless_demise_candidates(target_units=list(target_units or []))
        if not candidates:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "fight_targets_selected":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != "SELFLESS DEMISE":
                continue
            if self._csm_root(reaction.get("attacking_unit")) is attacker_root:
                return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_cabal_of_chaos_phase_end_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if not phase_name:
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return

        for unit in list(getattr(army, "units", []) or []):
            root = self._csm_root(unit)
            if root is None:
                continue

            if phase_name == "SHOOTING_PHASE":
                sr = getattr(root, "special_rules", None)
                if isinstance(sr, dict) and bool(sr.get("shroud_of_chaos_aura_active")):
                    for key in (
                        "shroud_of_chaos_aura_active",
                        "shroud_of_chaos_expires_phase",
                        "shroud_of_chaos_owner",
                        "shroud_of_chaos_turn",
                        "shroud_of_chaos_source",
                    ):
                        sr.pop(key, None)
                    root.special_rules = sr
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict):
                remove_prefixes = (
                    "chaos_cult_chosen_for_glory",
                    "chaos_cult_crazed_focus",
                    "chaos_cult_infernal_sacrifice",
                    "chaos_cult_selfless_demise",
                    "chaos_cult_mortal_thralls",
                )
                remove_keys = [
                    key
                    for key in list(sr.keys())
                    if any(str(key).startswith(prefix) for prefix in remove_prefixes)
                ]
                if remove_keys:
                    for key in remove_keys:
                        sr.pop(key, None)
                    root.special_rules = sr

            models = []
            get_models = getattr(root, "get_attached_unit_models", None)
            if callable(get_models):
                models = list(get_models() or [])
            if not models:
                models = list(getattr(root, "models", []) or [])
            for model in models:
                effects = getattr(model, "_temporary_effects", None)
                if not isinstance(effects, dict) or not effects:
                    continue
                remove_keys: list[str] = []
                for key, value in list(effects.items()):
                    if not str(key or "").startswith("baleful_blessing:"):
                        continue
                    exp_phase = str(value.get("expires_phase", "") or "").strip().upper() if isinstance(value, dict) else ""
                    if not exp_phase or exp_phase == phase_name:
                        remove_keys.append(str(key))
                for key in remove_keys:
                    effects.pop(key, None)

    def _use_cabal_baleful_blessing(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        from_pending = False
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BALEFUL BLESSING":
                    continue
                from_pending = True
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("mortal_wound_allocated", reaction.get("mortal_wound_allocated"))
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BALEFUL BLESSING: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not from_pending:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BALEFUL BLESSING":
                    continue
                pending_root = self._csm_root(reaction.get("unit") or reaction.get("target_unit"))
                if pending_root is not root:
                    continue
                from_pending = True
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                kwargs.setdefault("mortal_wound_allocated", reaction.get("mortal_wound_allocated"))
                break
        if not self._is_cabal_of_chaos_detachment():
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: BALEFUL BLESSING: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: BALEFUL BLESSING: target is not currently eligible")
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: BALEFUL BLESSING: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: BALEFUL BLESSING: target must be HERETIC ASTARTES")
            return False

        trigger_flag = bool(kwargs.get("mortal_wound_allocated", False))
        trigger_name = str(kwargs.get("trigger", "") or "").strip().lower()
        if not from_pending and not trigger_flag and trigger_name not in {"mortal_wound_allocated", "mortal_wound"}:
            logger.error("ERROR: BALEFUL BLESSING: missing mortal-wound trigger context")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "")
        phase_key = self._phase_key_from_name(phase_name) if phase_name else ""
        models = []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        if not models:
            models = list(getattr(root, "models", []) or [])
        for index, model in enumerate(models):
            is_alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr)
            if not is_alive:
                continue
            key = f"baleful_blessing:{get_entity_id(model) or index}"
            set_temporary_fnp = getattr(model, "set_temporary_fnp", None)
            if callable(set_temporary_fnp):
                set_temporary_fnp(
                    key=key,
                    value=5,
                    source=stratagem.name,
                    condition="against mortal wounds",
                    expires_phase=phase_key,
                )
                continue
            effects = getattr(model, "_temporary_effects", None)
            if not isinstance(effects, dict):
                effects = {}
                model._temporary_effects = effects
            effects[key] = {
                "expires_phase": str(phase_key or "").strip().upper(),
                "temporary_fnp_value": 5,
                "temporary_fnp_source": str(stratagem.name or "BALEFUL BLESSING"),
                "temporary_fnp_condition": "against mortal wounds",
            }

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: BALEFUL BLESSING: {getattr(root, 'name', 'Unit')} gains FNP 5+ vs mortal wounds this phase.")
        return True

    def _use_cabal_shroud_of_chaos(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SHROUD OF CHAOS":
                    continue
                unit = reaction.get("unit") or reaction.get("target_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SHROUD OF CHAOS: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_cabal_of_chaos_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SHROUD OF CHAOS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: SHROUD OF CHAOS: not opponent's Shooting phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SHROUD OF CHAOS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SHROUD OF CHAOS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SHROUD OF CHAOS: target cannot be selected")
            return False
        if not self._is_cabal_shroud_source_unit(root):
            logger.error("ERROR: SHROUD OF CHAOS: target must be HERETIC ASTARTES PSYKER or DAEMON PRINCE source")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["shroud_of_chaos_aura_active"] = True
        sr["shroud_of_chaos_expires_phase"] = "SHOOTING_PHASE"
        sr["shroud_of_chaos_owner"] = str(getattr(self.player, "id", "") or "")
        sr["shroud_of_chaos_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["shroud_of_chaos_source"] = str(stratagem.name or "SHROUD OF CHAOS")
        root.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: SHROUD OF CHAOS: {getattr(root, 'name', 'Unit')} projects a 6\" Stealth aura this phase.")
        return True

    def _use_cabal_soulseekers(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SOULSEEKERS: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_cabal_of_chaos_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SOULSEEKERS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SOULSEEKERS: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SOULSEEKERS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SOULSEEKERS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SOULSEEKERS: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: SOULSEEKERS: target must be HERETIC ASTARTES")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: SOULSEEKERS: target has already been selected to shoot")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["warp_vision_ignores_cover_active"] = True
        sr["warp_vision_expires_phase"] = "SHOOTING_PHASE"
        sr["warp_vision_owner"] = str(getattr(self.player, "id", "") or "")
        sr["warp_vision_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["warp_vision_source"] = str(stratagem.name or "SOULSEEKERS")
        root.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: SOULSEEKERS: {getattr(root, 'name', 'Unit')} gains [IGNORES COVER] on ranged weapons this phase.")
        return True

    def _use_cabal_unholy_haste(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: UNHOLY HASTE: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_cabal_of_chaos_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: UNHOLY HASTE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: UNHOLY HASTE: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: UNHOLY HASTE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: UNHOLY HASTE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: UNHOLY HASTE: target cannot be selected")
            return False
        if not self._is_heretic_astartes_infantry(root):
            logger.error("ERROR: UNHOLY HASTE: target must be HERETIC ASTARTES INFANTRY")
            return False
        if bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
            logger.error("ERROR: UNHOLY HASTE: target has already attempted a charge this phase")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["warp_surge_charge_after_advance"] = True
        sr["warp_surge_expires_phase"] = "CHARGE_PHASE"
        sr["warp_surge_source"] = str(stratagem.name or "UNHOLY HASTE")
        root.special_rules = sr

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: UNHOLY HASTE: {getattr(root, 'name', 'Unit')} can charge after Advancing this phase.")
        return True

    def _use_cabal_no_rest_in_death(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: NO REST IN DEATH: no target unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_cabal_of_chaos_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: NO REST IN DEATH: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: NO REST IN DEATH: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: NO REST IN DEATH: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: NO REST IN DEATH: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: NO REST IN DEATH: target cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: NO REST IN DEATH: target must be HERETIC ASTARTES")
            return False
        if not self._cabal_within_empyric_support(root, radius=9.0):
            logger.error("ERROR: NO REST IN DEATH: target must be within 9\" of a friendly Psyker/Daemon Prince source")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        is_battleline = self._csm_has_keyword(root, "BATTLELINE")
        mode = kwargs.get("mode") or kwargs.get("no_rest_in_death_mode") or kwargs.get("choice")
        if isinstance(mode, dict):
            mode = mode.get("mode") or mode.get("choice")
        mode = str(mode or "").strip().lower()
        if mode and mode not in {"heal", "return", "return_models", "return model", "return models"}:
            logger.error("ERROR: NO REST IN DEATH: invalid mode")
            return False

        models = []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        if not models:
            models = list(getattr(root, "models", []) or [])

        def _is_alive_model(model: Any) -> bool:
            alive_attr = getattr(model, "is_alive", True)
            return bool(alive_attr() if callable(alive_attr) else alive_attr)

        def _missing_wounds(model: Any) -> int:
            base_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 0)) or 0)
            current_wounds = int(getattr(model, "wounds", 0) or 0)
            return max(0, int(base_wounds - current_wounds))

        wounded_models = [m for m in models if _is_alive_model(m) and _missing_wounds(m) > 0]
        wounded_models = sorted(wounded_models, key=lambda m: str(get_entity_id(m) or ""))

        destroyed_pool = list(getattr(root, "models_lost", []) or [])

        def _model_is_character(model: Any) -> bool:
            char_attr = getattr(model, "is_character", None)
            if bool(char_attr() if callable(char_attr) else char_attr):
                return True
            if self._csm_has_keyword(model, "CHARACTER"):
                return True
            parent = getattr(model, "parent_unit", None)
            return bool(parent is not None and self._csm_has_keyword(parent, "CHARACTER"))

        destroyed_candidates = []
        can_return = getattr(root, "_horrors_can_return_model", None)
        for model in list(destroyed_pool):
            if model is None:
                continue
            if _model_is_character(model):
                continue
            if callable(can_return) and not bool(can_return(model)):
                continue
            destroyed_candidates.append(model)
        destroyed_candidates = sorted(destroyed_candidates, key=lambda m: str(get_entity_id(m) or ""))

        if not mode:
            if is_battleline and destroyed_candidates and not wounded_models:
                mode = "return"
            else:
                mode = "heal"

        returned = 0
        healed = 0

        if mode.startswith("return"):
            if not is_battleline:
                logger.error("ERROR: NO REST IN DEATH: return-models mode requires a BATTLELINE unit")
                return False
            return_roll = int(dice_module.get_roll("D3") or 0)
            max_return = max(0, int(return_roll))
            chosen = kwargs.get("return_models") or kwargs.get("chosen_models")
            if chosen is not None:
                selected = set()
                filtered = []
                for entry in list(chosen or []):
                    candidate_id = str(get_entity_id(entry) or entry or "")
                    if not candidate_id or candidate_id in selected:
                        continue
                    for model in destroyed_candidates:
                        if str(get_entity_id(model) or "") == candidate_id:
                            filtered.append(model)
                            selected.add(candidate_id)
                            break
                destroyed_candidates = filtered
            returned = int(
                root.return_destroyed_bodyguard_models(
                    max_return,
                    game_map=getattr(self.game, "map", None),
                    chosen_models=destroyed_candidates,
                    wounds=None,
                    placement_source=stratagem.name,
                )
                or 0
            )
        else:
            heal_roll = int(dice_module.get_roll("D3") or 0)
            heal_amount = max(0, int(heal_roll)) + 1
            heal_model = kwargs.get("model") or kwargs.get("target_model")
            if heal_model is None and wounded_models:
                heal_model = wounded_models[0]
            if heal_model is not None:
                if heal_model not in models:
                    logger.error("ERROR: NO REST IN DEATH: heal model does not belong to target unit")
                    return False
                missing = _missing_wounds(heal_model)
                if missing > 0 and heal_amount > 0:
                    healed = min(int(heal_amount), int(missing))
                    heal_fn = getattr(heal_model, "heal", None)
                    if callable(heal_fn):
                        heal_fn(int(heal_amount))
                    else:
                        base_wounds = int(getattr(heal_model, "_base_wounds", getattr(heal_model, "base_wounds", 0)) or 0)
                        current_wounds = int(getattr(heal_model, "wounds", 0) or 0)
                        heal_model.wounds = min(base_wounds, current_wounds + int(heal_amount))

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: NO REST IN DEATH: %s healed=%d returned=%d.",
            getattr(root, "name", "Unit"),
            int(healed),
            int(returned),
        )
        return True

    def _use_cabal_mutations_curse(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MUTATION'S CURSE: no source unit provided")
            return False

        root = self._csm_root(unit)
        if root is None:
            return False
        if not self._is_cabal_of_chaos_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: MUTATION'S CURSE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MUTATION'S CURSE: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: MUTATION'S CURSE: source unit is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: MUTATION'S CURSE: source unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: MUTATION'S CURSE: source unit cannot be selected")
            return False
        if not self._is_cabal_psyker_source_unit(root):
            logger.error("ERROR: MUTATION'S CURSE: source unit must be HERETIC ASTARTES PSYKER")
            return False

        enemy_candidates = self._cabal_mutations_curse_enemy_candidates(root, radius=12.0)
        if not enemy_candidates:
            logger.error("ERROR: MUTATION'S CURSE: no visible enemy unit within 12\"")
            return False
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("target_enemy_unit")
        if enemy_unit is None and len(enemy_candidates) == 1:
            enemy_unit = enemy_candidates[0]
        enemy_root = self._csm_root(enemy_unit) if enemy_unit is not None else None
        if enemy_root is None:
            logger.error("ERROR: MUTATION'S CURSE: missing enemy target selection")
            return False
        if enemy_root not in enemy_candidates:
            logger.error("ERROR: MUTATION'S CURSE: selected enemy target is not eligible")
            return False

        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False

        roll = int(dice_module.get_roll("D6") or 0)
        mortal_wounds = 0
        if roll <= 1:
            mortal_wounds = 1
        elif roll <= 4:
            mortal_wounds = int(dice_module.get_roll("D3") or 0)
        else:
            mortal_wounds = int(dice_module.get_roll("D3") or 0) + int(dice_module.get_roll("D3") or 0)

        if mortal_wounds > 0:
            apply_mortals = getattr(root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortals):
                apply_mortals(enemy_root, int(mortal_wounds), game_map=getattr(self.game, "map", None))

        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MUTATION'S CURSE: %s dealt %d mortal wound(s) to %s (roll=%d).",
            getattr(root, "name", "Unit"),
            int(mortal_wounds),
            getattr(enemy_root, "name", "enemy"),
            int(roll),
        )
        return True

    def _use_chaos_cult_chosen_for_glory(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CHOSEN FOR GLORY: no target unit provided")
            return False
        root = self._csm_root(unit)
        if root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name not in {"shooting phase", "fight phase"}:
            logger.error("ERROR: CHOSEN FOR GLORY: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if phase_name == "shooting phase" and active_player is not self.player:
            logger.error("ERROR: CHOSEN FOR GLORY: shooting phase use requires your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: CHOSEN FOR GLORY: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: CHOSEN FOR GLORY: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CHOSEN FOR GLORY: target cannot be selected")
            return False
        if not self._is_damned_unit(root):
            logger.error("ERROR: CHOSEN FOR GLORY: target must be DAMNED")
            return False
        mgr = self._get_chaos_space_marines_mgr()
        has_dark_pacts = getattr(mgr, "_unit_has_dark_pacts", None) if mgr is not None else None
        if not callable(has_dark_pacts) or not bool(has_dark_pacts(root)):
            logger.error("ERROR: CHOSEN FOR GLORY: target must be able to make a Desperate Pact")
            return False
        round_state = getattr(root, "round_state", None)
        if phase_name == "shooting phase" and bool(getattr(round_state, "shot_this_round", False)):
            logger.error("ERROR: CHOSEN FOR GLORY: target has already been selected to shoot")
            return False
        if phase_name == "fight phase" and bool(getattr(round_state, "fought_this_phase", False)):
            logger.error("ERROR: CHOSEN FOR GLORY: target has already been selected to fight")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        pact_result = mgr.resolve_chaos_cult_desperate_pact(root, game=self.game)
        mgr._set_chaos_cult_effect_state(
            root,
            prefix=mgr._CHAOS_CULT_CHOSEN_FOR_GLORY_PREFIX,
            source=stratagem.name or "CHOSEN FOR GLORY",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._CHAOS_CULT_CHOSEN_FOR_GLORY_PREFIX}_leadership_passed": bool(
                    pact_result.get("leadership_passed", False)
                )
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CHOSEN FOR GLORY: %s gains Hit re-rolls%s until end of phase.",
            getattr(root, "name", "Unit"),
            " and Wound re-rolls" if bool(pact_result.get("leadership_passed", False)) else "",
        )
        return True

    def _use_chaos_cult_crazed_focus(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CRAZED FOCUS: no target unit provided")
            return False
        root = self._csm_root(unit)
        if root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: CRAZED FOCUS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CRAZED FOCUS: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: CRAZED FOCUS: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: CRAZED FOCUS: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: CRAZED FOCUS: target cannot be selected")
            return False
        if not self._is_damned_unit(root):
            logger.error("ERROR: CRAZED FOCUS: target must be DAMNED")
            return False
        mgr = self._get_chaos_space_marines_mgr()
        has_dark_pacts = getattr(mgr, "_unit_has_dark_pacts", None) if mgr is not None else None
        if not callable(has_dark_pacts) or not bool(has_dark_pacts(root)):
            logger.error("ERROR: CRAZED FOCUS: target must be able to make a Desperate Pact")
            return False
        if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
            logger.error("ERROR: CRAZED FOCUS: target has already been selected to shoot")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        pact_result = mgr.resolve_chaos_cult_desperate_pact(root, game=self.game)
        mgr._set_chaos_cult_effect_state(
            root,
            prefix=mgr._CHAOS_CULT_CRAZED_FOCUS_PREFIX,
            source=stratagem.name or "CRAZED FOCUS",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._CHAOS_CULT_CRAZED_FOCUS_PREFIX}_leadership_passed": bool(
                    pact_result.get("leadership_passed", False)
                )
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CRAZED FOCUS: %s gains +1 AP%s on ranged attacks until end of phase.",
            getattr(root, "name", "Unit"),
            " and +1 Strength" if bool(pact_result.get("leadership_passed", False)) else "",
        )
        return True

    def _use_chaos_cult_infernal_sacrifice(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: INFERNAL SACRIFICE: no target unit provided")
            return False
        root = self._csm_root(unit)
        if root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: INFERNAL SACRIFICE: wrong phase")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: INFERNAL SACRIFICE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: INFERNAL SACRIFICE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: INFERNAL SACRIFICE: target cannot be selected")
            return False
        if not self._is_damned_unit(root):
            logger.error("ERROR: INFERNAL SACRIFICE: target must be DAMNED")
            return False
        mgr = self._get_chaos_space_marines_mgr()
        has_dark_pacts = getattr(mgr, "_unit_has_dark_pacts", None) if mgr is not None else None
        if not callable(has_dark_pacts) or not bool(has_dark_pacts(root)):
            logger.error("ERROR: INFERNAL SACRIFICE: target must be able to make a Desperate Pact")
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: INFERNAL SACRIFICE: target has already been selected to fight")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        pact_result = mgr.resolve_chaos_cult_desperate_pact(root, game=self.game)
        extra_mortals = mgr._apply_chaos_cult_self_mortals(root, roll_spec="D3", game=self.game)
        mgr._set_chaos_cult_effect_state(
            root,
            prefix=mgr._CHAOS_CULT_INFERNAL_SACRIFICE_PREFIX,
            source=stratagem.name or "INFERNAL SACRIFICE",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._CHAOS_CULT_INFERNAL_SACRIFICE_PREFIX}_leadership_passed": bool(
                    pact_result.get("leadership_passed", False)
                )
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INFERNAL SACRIFICE: %s gains +1 Attacks%s and suffers %d mortal wound(s).",
            getattr(root, "name", "Unit"),
            " and +1 Strength" if bool(pact_result.get("leadership_passed", False)) else "",
            int(extra_mortals) + int(pact_result.get("mortal_wounds", 0) or 0),
        )
        return True

    def _use_chaos_cult_reckless_haste(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RECKLESS HASTE: no target unit provided")
            return False
        root = self._csm_root(unit)
        if root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "charge phase":
            logger.error("ERROR: RECKLESS HASTE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: RECKLESS HASTE: not your turn")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: RECKLESS HASTE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: RECKLESS HASTE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: RECKLESS HASTE: target cannot be selected")
            return False
        if not self._is_damned_unit(root):
            logger.error("ERROR: RECKLESS HASTE: target must be DAMNED")
            return False
        if bool(getattr(getattr(root, "round_state", None), "attempted_charge_this_round", False)):
            logger.error("ERROR: RECKLESS HASTE: target has already attempted a charge this phase")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["warp_surge_charge_after_advance"] = True
        sr["warp_surge_expires_phase"] = "CHARGE_PHASE"
        sr["warp_surge_source"] = str(stratagem.name or "RECKLESS HASTE")
        root.special_rules = sr
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: RECKLESS HASTE: %s can charge after Advancing this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_chaos_cult_mortal_thralls(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        support_unit = kwargs.get("support_unit")
        candidates = list(kwargs.get("candidates") or [])
        support_by_unit = dict(kwargs.get("support_candidates_by_unit") or {})
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("MORTAL THRALLS", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if not support_by_unit:
                support_by_unit = dict(pending.get("support_candidates_by_unit") or {})
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
            if support_unit is None:
                support_unit = pending.get("support_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MORTAL THRALLS: no protected unit provided")
            return False
        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: MORTAL THRALLS: wrong phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: MORTAL THRALLS: attacking unit must be an enemy unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: MORTAL THRALLS: protected unit is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: MORTAL THRALLS: protected unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: MORTAL THRALLS: protected unit cannot be selected")
            return False
        if not self._is_heretic_astartes_unit(root):
            logger.error("ERROR: MORTAL THRALLS: protected unit must be HERETIC ASTARTES")
            return False
        protected_key = self._csm_sort_key(root)
        support_candidates = list(support_by_unit.get(protected_key, []) or [])
        if support_unit is None and len(support_candidates) == 1:
            support_unit = support_candidates[0]
        support_root = self._csm_root(support_unit)
        if support_root is None:
            logger.error("ERROR: MORTAL THRALLS: no support DAMNED unit provided")
            return False
        if support_candidates and support_root not in support_candidates:
            logger.error("ERROR: MORTAL THRALLS: support unit is not currently eligible")
            return False
        if not self._csm_owned_by_player(support_root, self.player):
            logger.error("ERROR: MORTAL THRALLS: support unit is not yours")
            return False
        if not self._csm_is_alive(support_root) or not self._csm_is_on_battlefield(support_root):
            return False
        if self._unit_cannot_be_target_of_stratagem(support_root):
            logger.error("ERROR: MORTAL THRALLS: support unit cannot be selected")
            return False
        if not self._is_damned_unit(support_root):
            logger.error("ERROR: MORTAL THRALLS: support unit must be DAMNED")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        mgr = self._get_chaos_space_marines_mgr()
        mgr._set_chaos_cult_effect_state(
            root,
            prefix=mgr._CHAOS_CULT_MORTAL_THRALLS_PREFIX,
            source=stratagem.name or "MORTAL THRALLS",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._CHAOS_CULT_MORTAL_THRALLS_PREFIX}_attacker_unit_id": mgr._unit_entity_key(attacker_root),
                f"{mgr._CHAOS_CULT_MORTAL_THRALLS_PREFIX}_support_unit_id": mgr._unit_entity_key(support_root),
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: MORTAL THRALLS: %s redirects eligible wound rolls to %s this phase.",
            getattr(root, "name", "Unit"),
            getattr(support_root, "name", "Unit"),
        )
        return True

    def _use_chaos_cult_selfless_demise(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        attacking_unit = kwargs.get("attacking_unit")
        pending = self._csm_find_pending_reaction("SELFLESS DEMISE", unit=unit)
        if pending is not None:
            if not candidates:
                candidates = list(pending.get("candidates") or [])
            if attacking_unit is None:
                attacking_unit = pending.get("attacking_unit")
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SELFLESS DEMISE: no target unit provided")
            return False
        root = self._csm_root(unit)
        attacker_root = self._csm_root(attacking_unit)
        if root is None or attacker_root is None or not self._is_chaos_cult_detachment():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: SELFLESS DEMISE: wrong phase")
            return False
        if self._csm_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: SELFLESS DEMISE: attacking unit must be an enemy unit")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SELFLESS DEMISE: target is not currently eligible")
            return False
        if not self._csm_owned_by_player(root, self.player):
            logger.error("ERROR: SELFLESS DEMISE: target unit is not yours")
            return False
        if not self._csm_is_alive(root) or not self._csm_is_on_battlefield(root):
            return False
        if self._unit_cannot_be_target_of_stratagem(root):
            logger.error("ERROR: SELFLESS DEMISE: target cannot be selected")
            return False
        if not self._is_damned_unit(root):
            logger.error("ERROR: SELFLESS DEMISE: target must be DAMNED")
            return False
        if not self._cabal_spend_cp(stratagem, target_unit=root):
            return False
        mgr = self._get_chaos_space_marines_mgr()
        mgr._set_chaos_cult_effect_state(
            root,
            prefix=mgr._CHAOS_CULT_SELFLESS_DEMISE_PREFIX,
            source=stratagem.name or "SELFLESS DEMISE",
            player=self.player,
            game=self.game,
            extra_state={
                f"{mgr._CHAOS_CULT_SELFLESS_DEMISE_PREFIX}_attacker_unit_id": mgr._unit_entity_key(attacker_root),
            },
        )
        self._cabal_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: SELFLESS DEMISE: %s rolls for post-attack mortal retaliation against %s this phase.",
            getattr(root, "name", "Unit"),
            getattr(attacker_root, "name", "enemy"),
        )
        return True

    def _use_chaos_space_marines_cabal_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "CHOSEN FOR GLORY":
            return self._use_chaos_cult_chosen_for_glory(stratagem, **kwargs)
        if name_u == "CRAZED FOCUS":
            return self._use_chaos_cult_crazed_focus(stratagem, **kwargs)
        if name_u == "INFERNAL SACRIFICE":
            return self._use_chaos_cult_infernal_sacrifice(stratagem, **kwargs)
        if name_u == "MORTAL THRALLS":
            return self._use_chaos_cult_mortal_thralls(stratagem, **kwargs)
        if name_u == "RECKLESS HASTE":
            return self._use_chaos_cult_reckless_haste(stratagem, **kwargs)
        if name_u == "SELFLESS DEMISE":
            return self._use_chaos_cult_selfless_demise(stratagem, **kwargs)
        if name_u == "BALEFUL BLESSING":
            return self._use_cabal_baleful_blessing(stratagem, **kwargs)
        if name_u == "MUTATION'S CURSE":
            return self._use_cabal_mutations_curse(stratagem, **kwargs)
        if name_u == "NO REST IN DEATH":
            return self._use_cabal_no_rest_in_death(stratagem, **kwargs)
        if name_u == "SHROUD OF CHAOS":
            return self._use_cabal_shroud_of_chaos(stratagem, **kwargs)
        if name_u == "SOULSEEKERS":
            return self._use_cabal_soulseekers(stratagem, **kwargs)
        if name_u == "UNHOLY HASTE":
            return self._use_cabal_unholy_haste(stratagem, **kwargs)
        return None
