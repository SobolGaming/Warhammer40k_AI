from __future__ import annotations

import logging
import math
from typing import Any, Optional

from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class ThousandSonsStratagemMixin:
    @staticmethod
    def _ts_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _ts_sort_key(entity: Any) -> str:
        return str(get_entity_id(entity) or "")

    def _ts_detachment_mgr(self) -> Any:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        return getattr(army, "thousand_sons_detachments", None)

    def _is_thousand_sons_rubricae_phalanx_detachment(self) -> bool:
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "is_rubricae_phalanx", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_thousand_sons_changehost_of_deceit_detachment(self) -> bool:
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "is_changehost_of_deceit", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    @staticmethod
    def _ts_has_any_keyword(entity: Any, keyword: str) -> bool:
        if entity is None:
            return False
        has_any = getattr(entity, "has_any_keyword", None)
        if callable(has_any) and has_any(keyword):
            return True
        has_kw = getattr(entity, "has_keyword", None)
        if callable(has_kw) and has_kw(keyword):
            return True
        return False

    def _is_thousand_sons_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        mgr = self._ts_detachment_mgr()
        checker = getattr(mgr, "_unit_has_keyword_or_faction", None) if mgr is not None else None
        if callable(checker):
            try:
                if bool(checker(root, "THOUSAND SONS", faction_id="TS")):
                    return True
            except TypeError:
                pass
        faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if faction_id == "TS":
            return True
        return self._ts_has_any_keyword(root, "THOUSAND SONS")

    def _is_rubricae_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        if not self._is_thousand_sons_unit(root):
            return False
        if self._ts_has_any_keyword(root, "RUBRICAE"):
            return True
        return "RUBRIC" in str(getattr(root, "name", "") or "").strip().upper()

    def _is_scintillating_legions_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        if self._ts_has_any_keyword(root, "SCINTILLATING LEGIONS"):
            return True
        faction_id = str(getattr(root, "faction_id", "") or "").strip().upper()
        if faction_id in {"SL", "SCINTILLATING LEGIONS", "SCINTILLATING_LEGIONS"}:
            return True
        for keyword in list(getattr(root, "faction_keywords", []) or []):
            if str(keyword or "").strip().upper() == "SCINTILLATING LEGIONS":
                return True
        return False

    def _is_monster_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        return self._ts_has_any_keyword(root, "MONSTER")

    def _is_rubric_marines_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        if not self._is_rubricae_unit(root):
            return False
        if self._ts_has_any_keyword(root, "RUBRIC MARINES"):
            return True
        return "RUBRIC MARINES" in str(getattr(root, "name", "") or "").strip().upper()

    @staticmethod
    def _ts_model_has_keyword(model: Any, keyword: str) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            try:
                if bool(has_any(keyword)):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        has_kw = getattr(model, "has_keyword", None)
        if callable(has_kw):
            try:
                if bool(has_kw(keyword)):
                    return True
            except (AttributeError, TypeError, ValueError):
                pass
        return False

    @staticmethod
    def _ts_model_is_alive(model: Any) -> bool:
        if model is None:
            return False
        alive = getattr(model, "is_alive", None)
        if callable(alive):
            try:
                return bool(alive())
            except (AttributeError, TypeError, ValueError):
                return False
        return bool(alive)

    def _is_psyker_unit(self, unit: Any) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        if self._ts_has_any_keyword(root, "PSYKER"):
            return True
        for model in list(getattr(root, "models", []) or []):
            if not self._ts_model_is_alive(model):
                continue
            if self._ts_model_has_keyword(model, "PSYKER"):
                return True
        return False

    def _ts_model_is_psyker(self, model: Any, *, unit: Any = None) -> bool:
        if model is None:
            return False
        if self._ts_model_has_keyword(model, "PSYKER"):
            return True
        root = self._ts_root(unit) if unit is not None else self._ts_root(getattr(model, "parent_unit", None))
        if root is None:
            return False
        return self._ts_has_any_keyword(root, "PSYKER")

    @staticmethod
    def _ts_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    def _ts_owned_by_player(self, unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(army, "player", None) is player

    def _ts_on_battlefield(self, unit: Any, *, require_targetable: bool = True) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        if not self._ts_is_alive(root):
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

    def _ts_unit_in_candidates(self, root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = self._ts_sort_key(root)
        for candidate in list(candidates or []):
            candidate_root = self._ts_root(candidate)
            if candidate_root is None:
                continue
            if candidate_root is root:
                return True
            if rid and self._ts_sort_key(candidate_root) == rid:
                return True
        return False

    @staticmethod
    def _ts_has_shot_this_phase(unit: Any) -> bool:
        round_state = getattr(unit, "round_state", None)
        return bool(getattr(round_state, "shot_this_round", False))

    def _ts_model_distance_inches(self, source_model: Any, target_model: Any) -> Optional[float]:
        if source_model is None or target_model is None:
            return None
        source_base = getattr(source_model, "model_base", None)
        target_base = getattr(target_model, "model_base", None)
        if source_base is not None and target_base is not None and hasattr(source_base, "edge_to_edge_distance"):
            try:
                return float(source_base.edge_to_edge_distance(target_base))
            except (AttributeError, TypeError, ValueError):
                pass
        get_source = getattr(source_model, "get_location", None)
        get_target = getattr(target_model, "get_location", None)
        if callable(get_source) and callable(get_target):
            try:
                sx, sy, sz = get_source()
                tx, ty, tz = get_target()
                return float(math.dist((float(sx), float(sy), float(sz)), (float(tx), float(ty), float(tz))))
            except (AttributeError, TypeError, ValueError):
                return None
        return None

    def _ts_model_horizontal_distance_inches(self, source_model: Any, target_model: Any) -> Optional[float]:
        if source_model is None or target_model is None:
            return None
        source_base = getattr(source_model, "model_base", None)
        target_base = getattr(target_model, "model_base", None)
        if source_base is not None and target_base is not None:
            try:
                from ..utility.aura_utils import horizontal_distance_between_bases_2d

                return float(horizontal_distance_between_bases_2d(source_base, target_base))
            except (AttributeError, TypeError, ValueError):
                pass
        get_source = getattr(source_model, "get_location", None)
        get_target = getattr(target_model, "get_location", None)
        if callable(get_source) and callable(get_target):
            try:
                sx, sy, _sz, *_rest_s = get_source()
                tx, ty, _tz, *_rest_t = get_target()
                return float(math.hypot(float(sx) - float(tx), float(sy) - float(ty)))
            except (AttributeError, TypeError, ValueError):
                return None
        return None

    def _ts_unit_within_distance_of_model(self, unit: Any, model: Any, *, distance: float) -> bool:
        root = self._ts_root(unit)
        if root is None or model is None:
            return False
        max_distance = float(distance)
        for candidate in list(getattr(root, "models", []) or []):
            if not self._ts_model_is_alive(candidate):
                continue
            dist = self._ts_model_distance_inches(model, candidate)
            if dist is not None and dist <= max_distance + 1e-6:
                return True
        return False

    def _ts_unit_within_horizontal_distance_of_unit(
        self,
        unit: Any,
        other_unit: Any,
        *,
        distance: float,
    ) -> bool:
        root = self._ts_root(unit)
        other_root = self._ts_root(other_unit)
        if root is None or other_root is None:
            return False
        max_distance = float(distance)
        source_models = [m for m in list(getattr(root, "models", []) or []) if self._ts_model_is_alive(m)]
        target_models = [m for m in list(getattr(other_root, "models", []) or []) if self._ts_model_is_alive(m)]
        if not source_models or not target_models:
            return False
        for source_model in source_models:
            for target_model in target_models:
                dist = self._ts_model_horizontal_distance_inches(source_model, target_model)
                if dist is not None and dist <= max_distance + 1e-6:
                    return True
        return False

    def _ts_has_enemy_within_horizontal_distance(self, unit: Any, *, distance: float) -> bool:
        root = self._ts_root(unit)
        if root is None:
            return False
        game_map = getattr(getattr(self, "game", None), "map", None)
        if game_map is None:
            return False
        enemies: list[Any] = []
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        if callable(get_enemy_units):
            enemies = list(get_enemy_units(root) or [])
        elif isinstance(getattr(game_map, "units", None), list):
            enemies = list(getattr(game_map, "units", []) or [])
        for enemy in enemies:
            enemy_root = self._ts_root(enemy)
            if enemy_root is None:
                continue
            if self._ts_owned_by_player(enemy_root, self.player):
                continue
            if not self._ts_on_battlefield(enemy_root, require_targetable=False):
                continue
            if self._ts_unit_within_horizontal_distance_of_unit(root, enemy_root, distance=distance):
                return True
        return False

    def _ts_reaction_exists(
        self,
        event_name: str,
        stratagem_name: str,
        *,
        enemy_unit: Any = None,
    ) -> bool:
        event_u = str(event_name or "").strip().lower()
        strat_u = str(stratagem_name or "").strip().upper()
        enemy_root = self._ts_root(enemy_unit)
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "").strip().lower() != event_u:
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != strat_u:
                continue
            if enemy_root is not None:
                existing_enemy = self._ts_root(
                    reaction.get("enemy_unit")
                    or reaction.get("attacking_unit")
                )
                if existing_enemy is not enemy_root:
                    continue
            return True
        return False

    def _ts_revenge_pending_entries(self) -> list[dict[str, Any]]:
        pending = getattr(self, "_thousand_sons_revenge_pending", None)
        if isinstance(pending, list):
            return pending
        pending = []
        setattr(self, "_thousand_sons_revenge_pending", pending)
        return pending

    def _ts_prune_revenge_pending(self) -> None:
        game = getattr(self, "game", None)
        current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        phase_key = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() if game is not None else ""
        keep: list[dict[str, Any]] = []
        for entry in list(self._ts_revenge_pending_entries()):
            if not isinstance(entry, dict):
                continue
            if current_turn and int(entry.get("turn", 0) or 0) != current_turn:
                continue
            entry_phase = str(entry.get("phase_key", "") or "").strip().upper()
            if entry_phase and phase_key and entry_phase != phase_key:
                continue
            keep.append(entry)
        setattr(self, "_thousand_sons_revenge_pending", keep)

    def _ts_rubricae_battlefield_candidates(self, *, require_fell_back: bool) -> list[Any]:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_rubricae_unit(root):
                continue
            if require_fell_back and not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_ardent_automata_candidates(self) -> list[Any]:
        return self._ts_rubricae_battlefield_candidates(require_fell_back=True)

    def _ts_inexorable_advance_candidates(self) -> list[Any]:
        return self._ts_rubricae_battlefield_candidates(require_fell_back=False)

    def _ts_infernal_fusillade_candidates(self) -> list[Any]:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_thousand_sons_unit(root):
                continue
            if not self._is_psyker_unit(root):
                continue
            if self._ts_has_shot_this_phase(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_implacable_guardians_candidates(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> list[Any]:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return []
        if attacking_unit is not None:
            attacker_root = self._ts_root(attacking_unit)
            if attacker_root is None:
                return []
            if self._ts_owned_by_player(attacker_root, self.player):
                return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_rubric_marines_unit(root):
                continue
            if not self._is_psyker_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_unwavering_phalanx_candidates(
        self,
        *,
        attacking_unit: Any = None,
    ) -> list[Any]:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return []
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None:
            return []
        if self._ts_owned_by_player(attacker_root, self.player):
            return []
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return []
        game = getattr(self, "game", None)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is None or not hasattr(game_map, "is_within_engagement_range"):
            return []

        out: list[Any] = []
        for root in self._ts_rubricae_battlefield_candidates(require_fell_back=False):
            if not self._is_rubric_marines_unit(root):
                continue
            try:
                if not bool(game_map.is_within_engagement_range(root, attacker_root)):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_revenge_of_the_rubricae_candidates(
        self,
        *,
        attacker_unit: Any = None,
        destroyed_model: Any = None,
    ) -> list[Any]:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return []
        if attacker_unit is not None:
            attacker_root = self._ts_root(attacker_unit)
            if attacker_root is None:
                return []
            if self._ts_owned_by_player(attacker_root, self.player):
                return []
        if destroyed_model is None:
            return []
        out: list[Any] = []
        for root in self._ts_rubricae_battlefield_candidates(require_fell_back=False):
            if not self._ts_unit_within_distance_of_model(root, destroyed_model, distance=6.0):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_glimmershift_portal_candidates(self) -> list[Any]:
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._ts_owned_by_player(root, self.player):
                continue
            if not self._ts_on_battlefield(root, require_targetable=True):
                continue
            if not self._is_scintillating_legions_unit(root):
                continue
            if self._ts_has_enemy_within_horizontal_distance(root, distance=6.0):
                continue
            out.append(root)
        return sorted(out, key=self._ts_sort_key)

    def _ts_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._ts_root(unit)
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

    def _ts_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
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

    def _ts_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue and hasattr(self, "_dequeue_reaction_by_name"):
            self._dequeue_reaction_by_name(getattr(stratagem, "name", ""))
        used = getattr(self, "_used_stratagems_this_phase", None)
        if isinstance(used, set):
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u:
                used.add(name_u)

    def _queue_thousand_sons_rubricae_phalanx_fall_back_reactions(self, *, unit: Any, action: str) -> None:
        if str(action or "").strip().lower() != "fall_back":
            return
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return
        root = self._ts_root(unit)
        if root is None:
            return
        if not self._ts_owned_by_player(root, self.player):
            return
        if not self._ts_on_battlefield(root, require_targetable=True):
            return
        if not self._is_rubricae_unit(root):
            return
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            return

        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "MOVEMENT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is not self.player:
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("ARDENT AUTOMATA")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            return

        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if reaction.get("event") != "unit_move_ended":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != name_u:
                continue
            if reaction.get("unit") is root:
                return

        queue_reaction = getattr(self, "_queue_reaction", None)
        if not callable(queue_reaction):
            return
        queue_reaction(
            {
                "event": "unit_move_ended",
                "phase_name": "Movement phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": root,
                "target_unit": root,
                "action": "fall_back",
                "candidates": [root],
            }
        )

    def _queue_thousand_sons_rubricae_phalanx_charge_reactions(
        self,
        *,
        charging_unit: Any = None,
        action: str = "",
    ) -> None:
        if str(action or "").strip().lower() != "charge":
            return
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "CHARGE_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        attacker_root = self._ts_root(charging_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        if not self._ts_on_battlefield(attacker_root, require_targetable=False):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("UNWAVERING PHALANX")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._ts_unwavering_phalanx_candidates(attacking_unit=attacker_root)
        if not candidates:
            return
        if self._ts_reaction_exists(
            "unit_move_ended",
            stratagem.name,
            enemy_unit=attacker_root,
        ):
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            phase_name="Charge phase",
            attacking_unit=attacker_root,
            enemy_unit=attacker_root,
        ):
            return

        payload = {
            "event": "unit_move_ended",
            "phase_name": "Charge phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "action": "charge",
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_thousand_sons_rubricae_phalanx_shooting_target_reactions(
        self,
        *,
        attacking_unit: Any = None,
        target_units: Any = None,
    ) -> None:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("IMPLACABLE GUARDIANS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._ts_implacable_guardians_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not candidates:
            return
        if self._ts_reaction_exists(
            "shooting_targets_selected",
            stratagem.name,
            enemy_unit=attacker_root,
        ):
            return
        if not stratagem.can_use(
            self.player,
            self.game,
            phase_name="Shooting phase",
            attacking_unit=attacker_root,
            target_units=list(target_units or []),
        ):
            return
        payload = {
            "event": "shooting_targets_selected",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_root,
            "attacking_unit": attacker_root,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload)

    def _queue_thousand_sons_rubricae_revenge_on_model_destroyed(
        self,
        *,
        attacker_unit: Any = None,
        target_model: Any = None,
        target_unit: Any = None,
        weapon_profile: Any = None,
    ) -> None:
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._ts_root(attacker_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        if not self._ts_is_alive(attacker_root):
            return
        if target_model is None:
            return
        target_root = self._ts_root(target_unit)
        if target_root is None:
            return
        if not self._ts_owned_by_player(target_root, self.player):
            return
        if not self._is_thousand_sons_unit(target_root):
            return
        if not self._ts_model_is_psyker(target_model, unit=target_root):
            return
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        if parent_wargear is not None:
            is_ranged = getattr(parent_wargear, "is_ranged", None)
            if callable(is_ranged):
                try:
                    if not bool(is_ranged()):
                        return
                except (AttributeError, TypeError, ValueError):
                    return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("REVENGE OF THE RUBRICAE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        candidates = self._ts_revenge_of_the_rubricae_candidates(
            attacker_unit=attacker_root,
            destroyed_model=target_model,
        )
        if not candidates:
            return
        if not stratagem.can_use(self.player, self.game, phase_name="Shooting phase"):
            return
        attacker_key = self._ts_sort_key(attacker_root)
        if not attacker_key:
            return
        self._ts_prune_revenge_pending()
        current_turn = int(getattr(game, "turn", 0) or 0)
        phase_key = "SHOOTING_PHASE"
        merged = False
        pending = list(self._ts_revenge_pending_entries())
        for entry in pending:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("attacker_key", "") or "") != attacker_key:
                continue
            if int(entry.get("turn", 0) or 0) != current_turn:
                continue
            entry_phase = str(entry.get("phase_key", "") or "").strip().upper()
            if entry_phase and entry_phase != phase_key:
                continue
            existing: list[Any] = []
            seen_ids: set[str] = set()
            for cand in list(entry.get("candidates", []) or []):
                cand_root = self._ts_root(cand)
                if cand_root is None:
                    continue
                cid = self._ts_sort_key(cand_root)
                if cid and cid in seen_ids:
                    continue
                if cid:
                    seen_ids.add(cid)
                existing.append(cand_root)
            for cand in list(candidates or []):
                cand_root = self._ts_root(cand)
                if cand_root is None:
                    continue
                cid = self._ts_sort_key(cand_root)
                if cid and cid in seen_ids:
                    continue
                if cid:
                    seen_ids.add(cid)
                existing.append(cand_root)
            entry["candidates"] = sorted(existing, key=self._ts_sort_key)
            merged = True
            break
        if not merged:
            pending.append(
                {
                    "attacker_key": attacker_key,
                    "attacker_unit": attacker_root,
                    "candidates": sorted(list(candidates or []), key=self._ts_sort_key),
                    "turn": int(current_turn),
                    "phase_key": phase_key,
                    "stratagem": stratagem.name,
                }
            )
        setattr(self, "_thousand_sons_revenge_pending", pending)

    def _queue_thousand_sons_rubricae_revenge_after_shooting_resolved(
        self,
        *,
        attacker_unit: Any = None,
        hits_by_target: Any = None,
    ) -> None:
        del hits_by_target  # Not needed for this trigger; we queue from destroy-time snapshots.
        if not self._is_thousand_sons_rubricae_phalanx_detachment():
            return
        game = getattr(self, "game", None)
        if game is None:
            return
        if str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper() != "SHOOTING_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return
        attacker_root = self._ts_root(attacker_unit)
        if attacker_root is None or self._ts_owned_by_player(attacker_root, self.player):
            return
        stratagem = getattr(self, "get_by_name", lambda _name: None)("REVENGE OF THE RUBRICAE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return
        self._ts_prune_revenge_pending()
        attacker_key = self._ts_sort_key(attacker_root)
        current_turn = int(getattr(game, "turn", 0) or 0)
        keep: list[dict[str, Any]] = []
        queued = False
        for entry in list(self._ts_revenge_pending_entries()):
            if not isinstance(entry, dict):
                continue
            if str(entry.get("attacker_key", "") or "") != attacker_key:
                keep.append(entry)
                continue
            if int(entry.get("turn", 0) or 0) != current_turn:
                continue
            candidates: list[Any] = []
            seen_ids: set[str] = set()
            for unit in list(entry.get("candidates", []) or []):
                root = self._ts_root(unit)
                if root is None:
                    continue
                uid = self._ts_sort_key(root)
                if uid and uid in seen_ids:
                    continue
                if uid:
                    seen_ids.add(uid)
                if not self._ts_owned_by_player(root, self.player):
                    continue
                if not self._ts_on_battlefield(root, require_targetable=True):
                    continue
                if not self._is_rubricae_unit(root):
                    continue
                candidates.append(root)
            if not candidates:
                continue
            if self._ts_reaction_exists(
                "unit_shooting_resolved",
                stratagem.name,
                enemy_unit=attacker_root,
            ):
                queued = True
                continue
            payload = {
                "event": "unit_shooting_resolved",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "enemy_unit": attacker_root,
                "attacking_unit": attacker_root,
                "candidates": sorted(candidates, key=self._ts_sort_key),
            }
            if len(candidates) == 1:
                payload["target_unit"] = candidates[0]
            queue_reaction = getattr(self, "_queue_reaction", None)
            if callable(queue_reaction):
                queue_reaction(payload)
                queued = True
        setattr(self, "_thousand_sons_revenge_pending", keep)
        if queued:
            return

    def _queue_thousand_sons_changehost_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        _ = player
        game = getattr(self, "game", None)
        if game is None:
            return
        if not self._is_thousand_sons_changehost_of_deceit_detachment():
            return
        phase_key = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_key != "FIGHT_PHASE":
            return
        active_player = getattr(game, "get_current_player", lambda: None)()
        if active_player is self.player:
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("GLIMMERSHIFT PORTAL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates = self._ts_glimmershift_portal_candidates()
        if not candidates:
            return
        if self._ts_reaction_exists("phase_end", stratagem.name):
            return
        if not stratagem.can_use(self.player, self.game, phase_name="Fight phase"):
            return

        non_monster_candidates = [unit for unit in candidates if not self._is_monster_unit(unit)]
        max_units = 2 if non_monster_candidates else 1
        payload: dict[str, Any] = {
            "event": "phase_end",
            "phase": "Fight phase",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "candidates": candidates,
            "max_units": int(max_units),
        }
        if len(candidates) == 1:
            payload["unit"] = candidates[0]
            payload["target_unit"] = candidates[0]
        queue_reaction = getattr(self, "_queue_reaction", None)
        if callable(queue_reaction):
            queue_reaction(payload, use_timer=False)

    def _use_thousand_sons_rubricae_phalanx_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        if stratagem is None:
            return None
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if self._is_thousand_sons_rubricae_phalanx_detachment():
            if name_u == "ARDENT AUTOMATA":
                return self._use_thousand_sons_ardent_automata(stratagem, **kwargs)
            if name_u == "INEXORABLE ADVANCE":
                return self._use_thousand_sons_inexorable_advance(stratagem, **kwargs)
            if name_u == "INFERNAL FUSILLADE":
                return self._use_thousand_sons_infernal_fusillade(stratagem, **kwargs)
            if name_u == "IMPLACABLE GUARDIANS":
                return self._use_thousand_sons_implacable_guardians(stratagem, **kwargs)
            if name_u == "UNWAVERING PHALANX":
                return self._use_thousand_sons_unwavering_phalanx(stratagem, **kwargs)
            if name_u == "REVENGE OF THE RUBRICAE":
                return self._use_thousand_sons_revenge_of_the_rubricae(stratagem, **kwargs)
        if self._is_thousand_sons_changehost_of_deceit_detachment():
            if name_u == "GLIMMERSHIFT PORTAL":
                return self._use_thousand_sons_glimmershift_portal(stratagem, **kwargs)
        return None

    def _use_thousand_sons_ardent_automata(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("action"):
                    kwargs["action"] = reaction.get("action")
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: ARDENT AUTOMATA: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: ARDENT AUTOMATA: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_rubricae_unit(root):
            logger.error("ERROR: ARDENT AUTOMATA: target must be a RUBRICAE unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "movement phase":
            logger.error("ERROR: ARDENT AUTOMATA: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: ARDENT AUTOMATA: not your turn")
            return False
        if str(kwargs.get("action", "") or "").strip().lower() not in {"", "fall_back"}:
            logger.error("ERROR: ARDENT AUTOMATA: invalid trigger")
            return False
        if not bool(getattr(getattr(root, "round_state", None), "fell_back_this_round", False)):
            logger.error("ERROR: ARDENT AUTOMATA: target unit has not Fallen Back this phase")
            return False

        eligible = candidates or self._ts_ardent_automata_candidates()
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: ARDENT AUTOMATA: target is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: ARDENT AUTOMATA: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_ardent_automata_active"] = True
        sr["thousand_sons_ardent_automata_turn_owner"] = owner_id
        sr["thousand_sons_ardent_automata_turn"] = int(current_turn)
        sr["thousand_sons_ardent_automata_source"] = stratagem.name
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ARDENT AUTOMATA: %s can shoot and charge this turn after Falling Back.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_inexorable_advance(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: INEXORABLE ADVANCE: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: INEXORABLE ADVANCE: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_rubricae_unit(root):
            logger.error("ERROR: INEXORABLE ADVANCE: target must be a RUBRICAE unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "movement phase":
            logger.error("ERROR: INEXORABLE ADVANCE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: INEXORABLE ADVANCE: not your turn")
            return False

        eligible = candidates or self._ts_inexorable_advance_candidates()
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: INEXORABLE ADVANCE: target is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Movement phase"):
            logger.error("ERROR: INEXORABLE ADVANCE: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_inexorable_advance_ignore_modifiers_active"] = True
        sr["thousand_sons_inexorable_advance_ignore_modifiers_expires_phase"] = "MOVEMENT_PHASE"
        sr["thousand_sons_inexorable_advance_assault_active"] = True
        sr["thousand_sons_inexorable_advance_assault_expires_phase"] = "SHOOTING_PHASE"
        sr["thousand_sons_inexorable_advance_turn_owner"] = owner_id
        sr["thousand_sons_inexorable_advance_turn"] = int(current_turn)
        sr["thousand_sons_inexorable_advance_source"] = stratagem.name
        # Reuse existing movement/advance modifier-choice plumbing.
        sr["preternatural_agility_ignore_modifiers_active"] = True
        sr["preternatural_agility_ignore_modifiers_expires_phase"] = "MOVEMENT_PHASE"
        sr["preternatural_agility_turn_owner"] = owner_id
        sr["preternatural_agility_turn"] = int(current_turn)
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INEXORABLE ADVANCE: %s can ignore Move/Advance modifiers and gains ranged [ASSAULT] this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_infernal_fusillade(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: INFERNAL FUSILLADE: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: INFERNAL FUSILLADE: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_thousand_sons_unit(root):
            logger.error("ERROR: INFERNAL FUSILLADE: target must be a THOUSAND SONS unit")
            return False
        if not self._is_psyker_unit(root):
            logger.error("ERROR: INFERNAL FUSILLADE: target must be a PSYKER unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: INFERNAL FUSILLADE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: INFERNAL FUSILLADE: not your turn")
            return False
        if self._ts_has_shot_this_phase(root):
            logger.error("ERROR: INFERNAL FUSILLADE: target has already shot this phase")
            return False

        eligible = candidates or self._ts_infernal_fusillade_candidates()
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: INFERNAL FUSILLADE: target is not eligible")
            return False
        if not stratagem.can_use(self.player, self.game, unit=root, phase_name="Shooting phase"):
            logger.error("ERROR: INFERNAL FUSILLADE: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        current_turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        owner_id = str(getattr(self.player, "id", "") or get_entity_id(self.player) or "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["thousand_sons_infernal_fusillade_active"] = True
        sr["thousand_sons_infernal_fusillade_expires_phase"] = "SHOOTING_PHASE"
        sr["thousand_sons_infernal_fusillade_owner"] = owner_id
        sr["thousand_sons_infernal_fusillade_turn"] = int(current_turn)
        sr["thousand_sons_infernal_fusillade_source"] = str(getattr(stratagem, "name", "") or "INFERNAL FUSILLADE")
        root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: INFERNAL FUSILLADE: %s inferno ranged weapons gain [PSYCHIC] and Strength 5 this phase.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_implacable_guardians(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        target_units = list(kwargs.get("target_units") or kwargs.get("targets") or [])

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
            logger.error("ERROR: IMPLACABLE GUARDIANS: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: IMPLACABLE GUARDIANS: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_rubric_marines_unit(root):
            logger.error("ERROR: IMPLACABLE GUARDIANS: target must be a RUBRIC MARINES unit")
            return False
        if not self._is_psyker_unit(root):
            logger.error("ERROR: IMPLACABLE GUARDIANS: target must be a PSYKER unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: IMPLACABLE GUARDIANS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: IMPLACABLE GUARDIANS: not opponent's Shooting phase")
            return False

        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: IMPLACABLE GUARDIANS: missing attacking unit context")
            return False
        if self._ts_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: IMPLACABLE GUARDIANS: attacker is not an enemy unit")
            return False

        eligible = candidates or self._ts_implacable_guardians_candidates(
            attacking_unit=attacker_root,
            target_units=target_units,
        )
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: IMPLACABLE GUARDIANS: target was not selected by the attacking unit")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            phase_name="Shooting phase",
            attacking_unit=attacker_root,
            target_units=list(target_units or []),
        ):
            logger.error("ERROR: IMPLACABLE GUARDIANS: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": "SHOOTING_PHASE",
            "source": str(getattr(stratagem, "name", "") or "IMPLACABLE GUARDIANS"),
            "exclude_allocated_model_keyword": "PSYKER",
        }
        append_defensive_effect = getattr(self, "_append_defensive_effect", None)
        if callable(append_defensive_effect):
            append_defensive_effect(root, "defensive_damage_reductions", entry)
        else:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            items = list(sr.get("defensive_damage_reductions", []) or [])
            items.append(entry)
            sr["defensive_damage_reductions"] = items
            root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: IMPLACABLE GUARDIANS: %s reduces incoming Damage by 1 this phase (excluding attacks allocated to PSYKER models).",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_unwavering_phalanx(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])

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
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: UNWAVERING PHALANX: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        if root is None:
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: UNWAVERING PHALANX: target unit is not yours")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if not self._is_rubric_marines_unit(root):
            logger.error("ERROR: UNWAVERING PHALANX: target must be a RUBRIC MARINES unit")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "charge phase":
            logger.error("ERROR: UNWAVERING PHALANX: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: UNWAVERING PHALANX: not opponent's Charge phase")
            return False

        attacker_root = self._ts_root(attacking_unit)
        if attacker_root is None:
            logger.error("ERROR: UNWAVERING PHALANX: missing attacking unit context")
            return False
        if self._ts_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: UNWAVERING PHALANX: attacker is not an enemy unit")
            return False

        eligible = candidates or self._ts_unwavering_phalanx_candidates(attacking_unit=attacker_root)
        if not eligible or not self._ts_unit_in_candidates(root, eligible):
            logger.error("ERROR: UNWAVERING PHALANX: target must be within Engagement Range of the charging unit")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            phase_name="Charge phase",
            attacking_unit=attacker_root,
            enemy_unit=attacker_root,
        ):
            logger.error("ERROR: UNWAVERING PHALANX: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False

        entry = {
            "value": 1,
            "attack_type": "any",
            "expires_phase": "FIGHT_PHASE",
            "source": str(getattr(stratagem, "name", "") or "UNWAVERING PHALANX"),
        }
        append_defensive_effect = getattr(self, "_append_defensive_effect", None)
        if callable(append_defensive_effect):
            append_defensive_effect(root, "defensive_wound_mods", entry)
        else:
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            items = list(sr.get("defensive_wound_mods", []) or [])
            items.append(entry)
            sr["defensive_wound_mods"] = items
            root.special_rules = sr

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: UNWAVERING PHALANX: %s imposes -1 to wound against incoming attacks in the Fight phase this turn.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_thousand_sons_revenge_of_the_rubricae(self, stratagem: Any, **kwargs) -> bool:
        target_unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit") or kwargs.get("attacker_unit")
        candidates = list(kwargs.get("candidates") or [])

        if target_unit is None or enemy_unit is None or not candidates:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != str(getattr(stratagem, "name", "") or "").strip().upper():
                    continue
                if target_unit is None:
                    target_unit = reaction.get("target_unit") or reaction.get("unit")
                if enemy_unit is None:
                    enemy_unit = reaction.get("enemy_unit") or reaction.get("attacking_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                break
        if target_unit is None and len(candidates) == 1:
            target_unit = candidates[0]
        if target_unit is None:
            logger.error("ERROR: REVENGE OF THE RUBRICAE: no target unit provided")
            return False

        root = self._ts_root(target_unit)
        enemy_root = self._ts_root(enemy_unit)
        if root is None or enemy_root is None:
            logger.error("ERROR: REVENGE OF THE RUBRICAE: missing attacker context")
            return False
        if not self._ts_owned_by_player(root, self.player):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: target unit is not yours")
            return False
        if not self._is_rubricae_unit(root):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: target must be a RUBRICAE unit")
            return False
        if not self._ts_on_battlefield(root, require_targetable=True):
            return False
        if self._ts_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: attacker is not an enemy unit")
            return False
        if not self._ts_is_alive(enemy_root):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: attacker is not alive")
            return False
        if candidates and not self._ts_unit_in_candidates(root, candidates):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: target was not selected by the trigger")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "shooting phase":
            logger.error("ERROR: REVENGE OF THE RUBRICAE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: REVENGE OF THE RUBRICAE: not opponent's Shooting phase")
            return False

        queue_fn = getattr(self.game, "_queue_setup_reactive_shooting_decision", None) if self.game is not None else None
        if not callable(queue_fn):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: reactive shooting decision queue unavailable")
            return False
        if not stratagem.can_use(
            self.player,
            self.game,
            unit=root,
            enemy_unit=enemy_root,
            phase_name="Shooting phase",
        ):
            logger.error("ERROR: REVENGE OF THE RUBRICAE: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=root):
            return False
        request = queue_fn(
            player=self.player,
            unit=root,
            target_unit=enemy_root,
            source=stratagem.name,
        )
        if request is None:
            logger.error("ERROR: REVENGE OF THE RUBRICAE: failed to queue reactive shooting decision")
            return False
        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: REVENGE OF THE RUBRICAE: %s can shoot reactively into %s.",
            getattr(root, "name", "Unit"),
            getattr(enemy_root, "name", "Enemy"),
        )
        return True

    def _use_thousand_sons_glimmershift_portal(self, stratagem: Any, **kwargs) -> bool:
        selected = (
            kwargs.get("units")
            or kwargs.get("target_units")
            or kwargs.get("selected_units")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        candidates = list(kwargs.get("candidates") or [])
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
                if "max_units" not in kwargs:
                    max_units = int(reaction.get("max_units", max_units) or max_units)
                break

        if selected is None and len(candidates) == 1:
            selected = [candidates[0]]
        if selected is None:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: no target units provided")
            return False

        selected_entries = list(selected) if isinstance(selected, (list, tuple)) else [selected]
        resolved: list[Any] = []
        seen_ids: set[str] = set()
        resolve_by_id = getattr(self.game, "_resolve_unit_by_id", None) if self.game is not None else None
        for entry in selected_entries:
            if entry is None:
                continue
            unit = entry
            if isinstance(entry, str):
                unit = resolve_by_id(entry) if callable(resolve_by_id) else None
            root = self._ts_root(unit)
            if root is None:
                continue
            uid = self._ts_sort_key(root)
            if uid and uid in seen_ids:
                continue
            if uid:
                seen_ids.add(uid)
            resolved.append(root)
        if not resolved:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: no valid target units selected")
            return False
        if len(resolved) > max(1, int(max_units)):
            logger.error("ERROR: GLIMMERSHIFT PORTAL: selected too many units")
            return False
        if len(resolved) > 2:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: cannot select more than two units")
            return False

        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower().replace("_", " ")
        if phase_name != "fight phase":
            logger.error("ERROR: GLIMMERSHIFT PORTAL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: not opponent's Fight phase")
            return False

        eligible = candidates or self._ts_glimmershift_portal_candidates()
        if not eligible:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: no eligible units")
            return False
        for root in resolved:
            if not self._ts_unit_in_candidates(root, eligible):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: selected unit is not currently eligible")
                return False
            if not self._ts_owned_by_player(root, self.player):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: selected unit is not yours")
                return False
            if not self._ts_on_battlefield(root, require_targetable=True):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: selected unit must be on the battlefield and targetable")
                return False
            if not self._is_scintillating_legions_unit(root):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: selected unit must be SCINTILLATING LEGIONS")
                return False
            if self._ts_has_enemy_within_horizontal_distance(root, distance=6.0):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: selected unit must be more than 6\" horizontally from all enemies")
                return False

        selected_monsters = [root for root in resolved if self._is_monster_unit(root)]
        if selected_monsters and len(resolved) != 1:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: if selecting a MONSTER unit, exactly one unit must be selected")
            return False

        can_use = False
        try:
            can_use = bool(
                stratagem.can_use(
                    self.player,
                    self.game,
                    phase_name="Fight phase",
                    unit=resolved[0],
                    units=list(resolved),
                )
            )
        except TypeError:
            can_use = bool(stratagem.can_use(self.player, self.game, phase_name="Fight phase", unit=resolved[0]))
        if not can_use:
            logger.error("ERROR: GLIMMERSHIFT PORTAL: cannot be used in current state")
            return False
        if not self._ts_spend_cp(stratagem, target_unit=resolved[0]):
            return False

        for root in resolved:
            if not self._ts_place_unit_into_strategic_reserves(
                root,
                reason=str(getattr(stratagem, "name", "GLIMMERSHIFT PORTAL") or "GLIMMERSHIFT PORTAL"),
            ):
                logger.error("ERROR: GLIMMERSHIFT PORTAL: failed to place %s into Strategic Reserves", getattr(root, "name", "Unit"))
                return False

        self._ts_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        moved_units = ", ".join(getattr(root, "name", "Unit") for root in resolved)
        logger.info("INFO: GLIMMERSHIFT PORTAL: %s entered Strategic Reserves.", moved_units)
        return True
