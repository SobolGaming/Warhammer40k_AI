from __future__ import annotations

from typing import Any, Optional
import math
import logging

from ..utility import dice as dice_module
from ..utility.entity_ids import get_entity_id

logger = logging.getLogger(__name__)


class AdeptaSororitasStratagemMixin:
    @staticmethod
    def _as_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _as_sort_key(unit: Any) -> str:
        return str(get_entity_id(unit) or "")

    @staticmethod
    def _as_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _as_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _as_has_keyword(unit: Any, keyword: str) -> bool:
        if unit is None:
            return False
        kw = str(keyword or "").strip()
        if not kw:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            try:
                if bool(has_keyword(kw)):
                    return True
            except Exception:
                pass
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            try:
                return bool(has_any_keyword(kw))
            except Exception:
                return False
        return False

    @classmethod
    def _as_on_battlefield(cls, unit: Any) -> bool:
        root = cls._as_root(unit)
        if root is None:
            return False
        if not cls._as_is_alive(root):
            return False
        if not bool(getattr(root, "deployed", False)):
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves):
            try:
                if bool(is_in_reserves()):
                    return False
            except Exception:
                return False
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            return False
        return True

    def _get_adepta_sororitas_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "adepta_sororitas_detachments", None) if army is not None else None

    def _is_hallowed_martyrs(self) -> bool:
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "is_hallowed_martyrs", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_army_of_faith(self) -> bool:
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "is_army_of_faith", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_bringers_of_flame(self) -> bool:
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "is_bringers_of_flame", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_adepta_sororitas_unit(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None:
            return False
        mgr = self._get_adepta_sororitas_mgr()
        checker = getattr(mgr, "unit_is_adepta_sororitas", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        return self._as_has_keyword(root, "ADEPTA SORORITAS")

    def _is_adepta_sororitas_infantry_or_walker(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None or not self._is_adepta_sororitas_unit(root):
            return False
        return bool(self._as_has_keyword(root, "INFANTRY") or self._as_has_keyword(root, "WALKER"))

    def _is_adepta_sororitas_vehicle(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None or not self._is_adepta_sororitas_unit(root):
            return False
        if self._as_has_keyword(root, "VEHICLE"):
            return True
        return bool(getattr(root, "is_vehicle", False))

    def _is_adepta_sororitas_transport(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None:
            return False
        if not self._is_adepta_sororitas_vehicle(root):
            return False
        return bool(self._as_has_keyword(root, "TRANSPORT") or bool(getattr(root, "is_transport", False)))

    def _is_adepta_sororitas_character(self, unit: Any) -> bool:
        root = self._as_root(unit)
        if root is None or not self._is_adepta_sororitas_unit(root):
            return False
        return self._as_has_keyword(root, "CHARACTER")

    def _as_resolve_friendly_transport_for_disembarked_unit(self, unit: Any) -> Any:
        root = self._as_root(unit)
        if root is None:
            return None
        round_state = getattr(root, "round_state", None)
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "")
        if not transport_id:
            return None
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return None
        for unit_entry in list(getattr(army, "units", []) or []):
            candidate = self._as_root(unit_entry)
            if candidate is None:
                continue
            if self._as_sort_key(candidate) != transport_id:
                continue
            if not self._as_owned_by_player(candidate, self.player):
                continue
            return candidate
        return None

    @staticmethod
    def _as_is_saint_celestine(unit: Any) -> bool:
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                root = get_root()
            except Exception:
                root = unit
        name = str(getattr(root, "name", "") or "").strip().lower()
        return "saint celestine" in name

    @staticmethod
    def _as_phase_name_lower(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _as_phase_key(value: Any) -> str:
        return str(value or "").strip().upper().replace(" ", "_")

    @staticmethod
    def _as_alive_model_count(unit: Any) -> int:
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            try:
                root = get_root()
            except Exception:
                root = unit
        models = []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            try:
                models = list(get_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
        else:
            models = list(getattr(root, "models", []) or [])
        count = 0
        for model in models:
            alive = getattr(model, "is_alive", None)
            if callable(alive):
                try:
                    if bool(alive()):
                        count += 1
                    continue
                except Exception:
                    continue
            if bool(alive):
                count += 1
                continue
            wounds = int(getattr(model, "wounds", 0) or 0)
            if wounds > 0:
                count += 1
        return int(count)

    @staticmethod
    def _as_total_current_wounds(unit: Any) -> int:
        if unit is None:
            return 0
        models = []
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            try:
                models = list(get_models() or [])
            except Exception:
                models = list(getattr(unit, "models", []) or [])
        else:
            models = list(getattr(unit, "models", []) or [])
        total = 0
        for model in models:
            alive = getattr(model, "is_alive", None)
            if callable(alive):
                try:
                    if not bool(alive()):
                        continue
                except Exception:
                    continue
            elif not bool(alive):
                continue
            try:
                total += max(0, int(getattr(model, "wounds", 0) or 0))
            except Exception:
                continue
        return int(total)

    def _as_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        apply_cost = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(apply_cost):
            preview = apply_cost(stratagem, target_unit=target_unit) or {}
            cp_cost = int(preview.get("cost", cp_cost))
        return cp_cost

    def _as_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._as_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _as_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _as_place_unit_into_strategic_reserves(self, unit: Any, *, reason: str = "") -> bool:
        root = self._as_root(unit)
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

    def _as_has_enemy_within_engagement_range(self, unit: Any) -> bool:
        root = self._as_root(unit)
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
            enemy_root = self._as_root(enemy)
            if enemy_root is None:
                continue
            if not self._as_on_battlefield(enemy_root):
                continue
            if bool(is_within_engagement_range(root, enemy_root)):
                return True
        return False

    @classmethod
    def _as_unit_in_candidates(cls, root: Any, candidates: list[Any]) -> bool:
        if root is None:
            return False
        rid = cls._as_sort_key(root)
        for candidate in list(candidates or []):
            cand_root = cls._as_root(candidate)
            if cand_root is None:
                continue
            if cand_root is root:
                return True
            if rid and rid == cls._as_sort_key(cand_root):
                return True
        return False

    def _army_of_faith_angelic_descent_candidates(self) -> list[Any]:
        if not self._is_army_of_faith():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            if not self._as_has_keyword(root, "JUMP PACK"):
                continue
            if self._as_has_enemy_within_engagement_range(root):
                continue
            candidates.append(root)
        return sorted(candidates, key=self._as_sort_key)

    def _as_battlefield_units(
        self,
        *,
        require_character: bool = False,
        require_infantry_or_walker: bool = False,
        require_vehicle: bool = False,
        require_not_fought: bool = False,
        require_targetable: bool = True,
    ) -> list[Any]:
        if not self._is_hallowed_martyrs():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._as_on_battlefield(root):
                continue
            if require_targetable and bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            if require_character and not self._is_adepta_sororitas_character(root):
                continue
            if require_infantry_or_walker and not self._is_adepta_sororitas_infantry_or_walker(root):
                continue
            if require_vehicle and not self._is_adepta_sororitas_vehicle(root):
                continue
            if require_not_fought and bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            out.append(root)
        return sorted(out, key=self._as_sort_key)

    def _hallowed_righteous_vengeance_candidates(self) -> list[Any]:
        return self._as_battlefield_units(require_not_fought=True, require_targetable=True)

    def _hallowed_suffering_and_sacrifice_candidates(self) -> list[Any]:
        return self._as_battlefield_units(require_infantry_or_walker=True, require_targetable=True)

    def _hallowed_reaction_already_queued(
        self,
        *,
        event_name: str,
        stratagem_name: str,
        phase_name: str,
        enemy_unit: Any = None,
        destroyed_model_id: str = "",
        unit: Any = None,
    ) -> bool:
        unit_id = self._as_sort_key(self._as_root(unit)) if unit is not None else ""
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != str(event_name):
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem_name or "").strip().upper():
                continue
            if str(reaction.get("phase_name", "") or "").strip().lower() != str(phase_name or "").strip().lower():
                continue
            if enemy_unit is not None and reaction.get("enemy_unit") is not enemy_unit:
                continue
            if destroyed_model_id:
                if str(reaction.get("destroyed_model_id", "") or "") != str(destroyed_model_id):
                    continue
            if unit_id:
                rid = self._as_sort_key(self._as_root(reaction.get("unit") or reaction.get("target_unit")))
                if rid != unit_id:
                    continue
            return True
        return False

    def _as_praise_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        snapshots = getattr(self, "_as_praise_targets_before", None)
        if not isinstance(snapshots, dict):
            snapshots = {}
            self._as_praise_targets_before = snapshots
        return snapshots

    def _as_divine_pending(self) -> list[dict[str, Any]]:
        pending = getattr(self, "_as_divine_intervention_pending", None)
        if not isinstance(pending, list):
            pending = []
            self._as_divine_intervention_pending = pending
        return pending

    def _as_divine_used_units(self) -> set[str]:
        used = getattr(self, "_as_divine_intervention_used_unit_ids", None)
        if not isinstance(used, set):
            used = set()
            self._as_divine_intervention_used_unit_ids = used
        return used

    def _as_miracle_dice_manager(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "acts_of_faith", None) if army is not None else None

    def _queue_army_of_faith_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_army_of_faith():
            return
        if player is self.player:
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("ANGELIC DESCENT")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._army_of_faith_angelic_descent_candidates()
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
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

    def _queue_hallowed_martyrs_phase_start_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_hallowed_martyrs():
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        stratagem = self.get_by_name("SUFFERING AND SACRIFICE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates = self._hallowed_suffering_and_sacrifice_candidates()
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="phase_start",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
        ):
            return
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

    def _capture_hallowed_martyrs_praise_the_fallen_targets(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_hallowed_martyrs():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "shooting phase":
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        if self._as_owned_by_player(attacking_unit, self.player):
            return
        stratagem = self.get_by_name("PRAISE THE FALLEN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_key = self._attacker_unit_key(attacking_unit)
        if not attacker_key:
            return
        snapshot_by_unit: dict[str, dict[str, Any]] = {}
        for unit in list(target_units or []):
            root = self._as_root(unit)
            if root is None:
                continue
            if not self._as_is_alive(root):
                continue
            if not self._as_on_battlefield(root):
                continue
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            uid = self._as_sort_key(root)
            if not uid:
                continue
            snapshot_by_unit[uid] = {
                "unit": root,
                "models_before": self._as_alive_model_count(root),
                "wounds_before": self._as_total_current_wounds(root),
            }
        if not snapshot_by_unit:
            return
        snapshots = self._as_praise_snapshots()
        snapshots[attacker_key] = snapshot_by_unit

    def _queue_hallowed_martyrs_fight_target_reactions(self, *, attacking_unit: Any, target_units: Any) -> None:
        if attacking_unit is None or not self._is_hallowed_martyrs():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "fight phase":
            return
        if self._as_owned_by_player(attacking_unit, self.player):
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        stratagem = self.get_by_name("SPIRIT OF THE MARTYR")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for unit in list(target_units or []):
            root = self._as_root(unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_is_alive(root):
                continue
            if not self._as_on_battlefield(root):
                continue
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._as_sort_key)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="fight_targets_selected",
            stratagem_name=stratagem.name,
            phase_name="Fight phase",
            enemy_unit=attacking_unit,
        ):
            return
        payload = {
            "event": "fight_targets_selected",
            "phase_name": "Fight phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacking_unit,
            "attacking_unit": attacking_unit,
            "target_units": list(target_units or []),
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_hallowed_martyrs_shooting_resolved_reactions(self, *, attacker_unit: Any, hits_by_target: Any = None) -> None:
        if attacker_unit is None or not self._is_hallowed_martyrs():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "shooting phase":
            return
        if self._as_owned_by_player(attacker_unit, self.player):
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        stratagem = self.get_by_name("PRAISE THE FALLEN")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        attacker_key = self._attacker_unit_key(attacker_unit)
        if not attacker_key:
            return
        snapshots = self._as_praise_snapshots()
        snapshot_by_unit = snapshots.pop(attacker_key, {})
        if not isinstance(snapshot_by_unit, dict) or not snapshot_by_unit:
            return
        candidates: list[Any] = []
        for entry in list(snapshot_by_unit.values()):
            if not isinstance(entry, dict):
                continue
            root = self._as_root(entry.get("unit"))
            if root is None:
                continue
            if not self._as_is_alive(root):
                continue
            if not self._as_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_adepta_sororitas_unit(root):
                continue
            before = int(entry.get("models_before", 0) or 0)
            after = self._as_alive_model_count(root)
            if after >= before:
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._as_sort_key)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_unit,
        ):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_unit,
            "attacking_unit": attacker_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
        self._queue_reaction(payload)

    def _queue_bringers_of_flame_move_started_reactions(self, *, unit: Any, action: Any) -> None:
        if unit is None or not self._is_bringers_of_flame():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "movement phase":
            return
        if str(action or "").strip().lower() != "advance":
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is not self.player:
            return
        root = self._as_root(unit)
        if root is None:
            return
        if not self._as_owned_by_player(root, self.player):
            return
        if not self._as_on_battlefield(root):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            return
        if not self._is_adepta_sororitas_transport(root):
            return
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "moved_this_round", False)):
            return
        if bool(getattr(round_state, "advanced_this_round", False)):
            return
        if bool(getattr(round_state, "fell_back_this_round", False)):
            return
        stratagem = self.get_by_name("CARRY FORTH THE FAITHFUL")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            if str(reaction.get("event", "") or "") != "unit_move_started":
                continue
            if str(reaction.get("stratagem", "") or "").strip().upper() != str(stratagem.name or "").strip().upper():
                continue
            if reaction.get("unit") is root:
                return
        payload = {
            "event": "unit_move_started",
            "phase_name": "Movement phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "candidates": [root],
            "action": "advance",
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_bringers_of_flame_shooting_resolved_reactions(self, *, attacker_unit: Any, hits_by_target: Any = None) -> None:
        if attacker_unit is None or not self._is_bringers_of_flame():
            return
        if self._as_phase_name_lower(getattr(self, "_current_phase_name", "")) != "shooting phase":
            return
        if self._as_owned_by_player(attacker_unit, self.player):
            return
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            return
        stratagem = self.get_by_name("BLAZING IRE")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        candidates: list[Any] = []
        seen: set[str] = set()
        for target_unit in list((hits_by_target or {}).keys() if isinstance(hits_by_target, dict) else []):
            root = self._as_root(target_unit)
            if root is None:
                continue
            uid = self._as_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._as_on_battlefield(root):
                continue
            if not self._as_owned_by_player(root, self.player):
                continue
            if not self._is_adepta_sororitas_transport(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            embarked = list(getattr(root, "transport_passengers", []) or [])
            if not embarked:
                continue
            candidates.append(root)
        candidates = sorted(candidates, key=self._as_sort_key)
        if not candidates:
            return
        if self._hallowed_reaction_already_queued(
            event_name="unit_shooting_resolved",
            stratagem_name=stratagem.name,
            phase_name="Shooting phase",
            enemy_unit=attacker_unit,
        ):
            return
        payload = {
            "event": "unit_shooting_resolved",
            "phase_name": "Shooting phase",
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "enemy_unit": attacker_unit,
            "attacking_unit": attacker_unit,
            "candidates": candidates,
        }
        if len(candidates) == 1:
            payload["target_unit"] = candidates[0]
            payload["unit"] = candidates[0]
        self._queue_reaction(payload, use_timer=False)

    def _queue_hallowed_martyrs_model_destroyed_reactions(self, *, unit: Any, model: Any) -> None:
        if unit is None or model is None or not self._is_hallowed_martyrs():
            return
        root = self._as_root(unit)
        if root is None:
            return
        if not self._as_owned_by_player(root, self.player):
            return
        if not self._is_adepta_sororitas_vehicle(root):
            return
        has_deadly_demise = getattr(root, "has_deadly_demise", None)
        if not callable(has_deadly_demise):
            return
        try:
            has_deadly, _damage_dice = has_deadly_demise()
        except Exception:
            has_deadly = False
        if not has_deadly:
            return
        stratagem = self.get_by_name("SANCTIFIED IMMOLATION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "")
        destroyed_model_id = str(get_entity_id(model) or "")
        if self._hallowed_reaction_already_queued(
            event_name="model_destroyed_before_removal",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            destroyed_model_id=destroyed_model_id,
        ):
            return
        payload = {
            "event": "model_destroyed_before_removal",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "destroyed_unit": root,
            "destroyed_model": model,
            "destroyed_model_id": destroyed_model_id,
        }
        self._queue_reaction(payload, use_timer=False)

    def _queue_hallowed_martyrs_unit_destroyed_reactions(self, *, unit: Any, last_model: Any) -> None:
        if unit is None or not self._is_hallowed_martyrs():
            return
        root = self._as_root(unit)
        if root is None:
            return
        if not self._as_owned_by_player(root, self.player):
            return
        if not self._is_adepta_sororitas_character(root):
            return
        if self._as_is_saint_celestine(root):
            return
        unit_id = self._as_sort_key(root)
        if unit_id and unit_id in self._as_divine_used_units():
            return
        acts_mgr = self._as_miracle_dice_manager()
        pool = list(getattr(acts_mgr, "miracle_dice", []) or []) if acts_mgr is not None else []
        if not pool:
            return
        stratagem = self.get_by_name("DIVINE INTERVENTION")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(stratagem.cp_cost or 0):
            return
        if str(stratagem.name or "").strip().upper() in self._used_stratagems_this_phase:
            return
        phase_name = str(getattr(self, "_current_phase_name", "") or "")
        if self._hallowed_reaction_already_queued(
            event_name="unit_destroyed",
            stratagem_name=stratagem.name,
            phase_name=phase_name,
            unit=root,
        ):
            return
        destroyed_position = None
        if last_model is not None:
            get_location = getattr(last_model, "get_location", None)
            if callable(get_location):
                try:
                    destroyed_position = get_location()
                except Exception:
                    destroyed_position = None
        payload = {
            "event": "unit_destroyed",
            "phase_name": phase_name,
            "stratagem": stratagem.name,
            "cp_cost": stratagem.cp_cost,
            "unit": root,
            "target_unit": root,
            "destroyed_unit": root,
            "destroyed_model": last_model,
            "destroyed_position": destroyed_position,
            "miracle_dice_pool": list(pool),
        }
        self._queue_reaction(payload, use_timer=False)

    def _cleanup_hallowed_martyrs_fight_phase_effects(self, *, phase: Any) -> None:
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return
        for unit in list(getattr(army, "units", []) or []):
            root = self._as_root(unit)
            if root is None:
                continue
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            changed = False
            for key in (
                "righteous_vengeance_active",
                "righteous_vengeance_expires_phase",
                "righteous_vengeance_turn_owner",
                "righteous_vengeance_turn",
                "righteous_vengeance_source",
                "suffering_and_sacrifice_active",
                "suffering_and_sacrifice_expires_phase",
                "suffering_and_sacrifice_turn_owner",
                "suffering_and_sacrifice_turn",
                "suffering_and_sacrifice_source",
                "spirit_of_martyr_active",
                "spirit_of_martyr_expires_phase",
                "spirit_of_martyr_turn_owner",
                "spirit_of_martyr_turn",
                "spirit_of_martyr_source",
            ):
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = sr

    def _resolve_hallowed_martyrs_phase_end(self, *, player: Any, phase: Any) -> None:
        self._cleanup_hallowed_martyrs_fight_phase_effects(phase=phase)
        self._resolve_hallowed_martyrs_divine_intervention_returns(phase=phase)

    def _resolve_hallowed_martyrs_divine_intervention_returns(self, *, phase: Any) -> None:
        pending = self._as_divine_pending()
        if not pending:
            return
        phase_key = self._as_phase_key(getattr(phase, "name", "") or getattr(self, "_current_phase_name", ""))
        if not phase_key:
            return
        remaining: list[dict[str, Any]] = []
        for entry in list(pending):
            if not isinstance(entry, dict):
                continue
            trigger_key = self._as_phase_key(entry.get("trigger_phase_key") or entry.get("trigger_phase_name") or "")
            if trigger_key and trigger_key != phase_key:
                remaining.append(entry)
                continue
            root = self._as_root(entry.get("unit"))
            model = entry.get("model")
            if root is None or model is None:
                continue
            discarded = int(entry.get("discard_count", 0) or 0)
            if discarded < 1:
                discarded = 1
            try:
                rolled = int(dice_module.get_roll("D3") or 0)
            except Exception:
                rolled = 0
            wounds_remaining = int(rolled + discarded)
            try:
                starting_wounds = int(getattr(model, "_base_wounds", getattr(model, "base_wounds", 1)) or 1)
            except Exception:
                starting_wounds = 1
            wounds_remaining = max(1, min(int(starting_wounds), int(wounds_remaining)))
            in_unit = False
            try:
                in_unit = model in list(getattr(root, "models", []) or [])
            except Exception:
                in_unit = False
            if not in_unit:
                try:
                    if model in list(getattr(root, "models_lost", []) or []):
                        root.models_lost.remove(model)
                except Exception:
                    pass
                try:
                    if hasattr(root, "add_model"):
                        root.add_model(model)
                    else:
                        root.models.append(model)
                except Exception:
                    try:
                        root.models.append(model)
                    except Exception:
                        pass
            try:
                model.wounds = int(wounds_remaining)
            except Exception:
                try:
                    model._wounds = int(wounds_remaining)
                except Exception:
                    pass
            try:
                setattr(model, "_on_death_reactions_resolved", False)
                setattr(model, "_fight_on_death_used", False)
                setattr(model, "_shoot_on_death_used", False)
            except Exception:
                pass
            pos = self._as_find_divine_intervention_position(
                unit=root,
                model=model,
                origin=entry.get("destroyed_position"),
            )
            if pos is not None:
                try:
                    model.set_location(float(pos[0]), float(pos[1]), float(pos[2]), float(pos[3]))
                except Exception:
                    pass
            root.deployed = True
            try:
                root.reserve_status = "deployed"
            except Exception:
                pass
            game_map = getattr(self.game, "map", None) if self.game is not None else None
            if game_map is not None:
                units = list(getattr(game_map, "units", []) or [])
                if root not in units:
                    try:
                        if not bool(game_map.place_unit(root)):
                            game_map.units.append(root)
                    except Exception:
                        game_map.units.append(root)
            logger.info(
                f"INFO: DIVINE INTERVENTION: returned {getattr(model, 'name', 'Model')} "
                f"with {int(wounds_remaining)} wound(s)."
            )
        self._as_divine_intervention_pending = remaining

    def _as_position_is_valid_for_divine_intervention(
        self,
        *,
        unit: Any,
        model: Any,
        x: float,
        y: float,
        z: float,
        facing: float,
    ) -> bool:
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None or unit is None or model is None:
            return False
        get_location = getattr(model, "get_location", None)
        previous = None
        if callable(get_location):
            try:
                previous = get_location()
            except Exception:
                previous = None
        try:
            model.set_location(float(x), float(y), float(z), float(facing))
        except Exception:
            return False
        try:
            if not bool(game_map.is_within_boundary(model)):
                return False
            if bool(game_map.check_collision_with_terrain(model)):
                return False
            if bool(game_map.check_collision_with_other_friendly_units(model)):
                return False
            if bool(game_map.check_collision_with_other_enemy_units(model)):
                return False
            for other in list(getattr(unit, "models", []) or []):
                if other is model:
                    continue
                other_alive = getattr(other, "is_alive", None)
                if callable(other_alive):
                    try:
                        if not bool(other_alive()):
                            continue
                    except Exception:
                        continue
                elif not bool(other_alive):
                    continue
                try:
                    if model.model_base.collides_with(other.model_base):
                        return False
                except Exception:
                    continue
            for enemy in list(game_map.get_enemy_units(unit) or []):
                if enemy is None:
                    continue
                enemy_root = self._as_root(enemy)
                if enemy_root is None:
                    continue
                if not self._as_is_alive(enemy_root):
                    continue
                try:
                    if bool(game_map.is_within_engagement_range(unit, enemy_root)):
                        return False
                except Exception:
                    continue
            return True
        finally:
            if previous is not None:
                try:
                    model.set_location(
                        float(previous[0]),
                        float(previous[1]),
                        float(previous[2]),
                        float(previous[3]),
                    )
                except Exception:
                    pass

    def _as_find_divine_intervention_position(self, *, unit: Any, model: Any, origin: Any) -> Optional[tuple[float, float, float, float]]:
        if unit is None or model is None:
            return None
        x0, y0, z0, facing0 = (0.0, 0.0, 0.0, 0.0)
        origin_tuple = None
        if isinstance(origin, (list, tuple)) and len(origin) >= 4:
            origin_tuple = origin
        if origin_tuple is None:
            get_location = getattr(model, "get_location", None)
            if callable(get_location):
                try:
                    loc = get_location()
                    if isinstance(loc, (list, tuple)) and len(loc) >= 4:
                        origin_tuple = loc
                except Exception:
                    origin_tuple = None
        if origin_tuple is not None:
            try:
                x0 = float(origin_tuple[0])
                y0 = float(origin_tuple[1])
                z0 = float(origin_tuple[2])
                facing0 = float(origin_tuple[3])
            except Exception:
                x0, y0, z0, facing0 = (0.0, 0.0, 0.0, 0.0)
        if self._as_position_is_valid_for_divine_intervention(
            unit=unit,
            model=model,
            x=x0,
            y=y0,
            z=z0,
            facing=facing0,
        ):
            return (x0, y0, z0, facing0)
        max_radius = 12.0
        step = 0.5
        ring = step
        while ring <= max_radius + 1e-6:
            deg = 0
            while deg < 360:
                angle = math.radians(float(deg))
                x = float(x0 + math.cos(angle) * ring)
                y = float(y0 + math.sin(angle) * ring)
                if self._as_position_is_valid_for_divine_intervention(
                    unit=unit,
                    model=model,
                    x=x,
                    y=y,
                    z=z0,
                    facing=facing0,
                ):
                    return (x, y, z0, facing0)
                deg += 15
            ring += step
        return None

    def _use_adepta_sororitas_hallowed_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "BLAZING IRE":
            return self._use_bringers_of_flame_blazing_ire(stratagem, **kwargs)
        if name_u == "CARRY FORTH THE FAITHFUL":
            return self._use_bringers_of_flame_carry_forth_the_faithful(stratagem, **kwargs)
        if name_u == "ANGELIC DESCENT":
            return self._use_army_of_faith_angelic_descent(stratagem, **kwargs)
        if name_u == "RIGHTEOUS VENGEANCE":
            return self._use_hallowed_righteous_vengeance(stratagem, **kwargs)
        if name_u == "SUFFERING AND SACRIFICE":
            return self._use_hallowed_suffering_and_sacrifice(stratagem, **kwargs)
        if name_u == "SPIRIT OF THE MARTYR":
            return self._use_hallowed_spirit_of_the_martyr(stratagem, **kwargs)
        if name_u == "PRAISE THE FALLEN":
            return self._use_hallowed_praise_the_fallen(stratagem, **kwargs)
        if name_u == "SANCTIFIED IMMOLATION":
            return self._use_hallowed_sanctified_immolation(stratagem, **kwargs)
        if name_u == "DIVINE INTERVENTION":
            return self._use_hallowed_divine_intervention(stratagem, **kwargs)
        return None

    def _use_bringers_of_flame_blazing_ire(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_bringers_of_flame():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("transport_unit") or kwargs.get("transport")
        attacking_unit = kwargs.get("attacking_unit") or kwargs.get("attacker_unit") or kwargs.get("enemy_unit")
        candidates = list(kwargs.get("candidates") or [])
        if (unit is None or attacking_unit is None or not candidates) and hasattr(self, "_pending_reactions"):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "BLAZING IRE":
                    continue
                if unit is None:
                    unit = reaction.get("unit") or reaction.get("target_unit")
                if attacking_unit is None:
                    attacking_unit = reaction.get("attacking_unit") or reaction.get("enemy_unit")
                if not candidates:
                    candidates = list(reaction.get("candidates") or [])
                if not kwargs.get("phase_name"):
                    kwargs["phase_name"] = reaction.get("phase_name") or reaction.get("phase")
                break
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BLAZING IRE: no target transport provided")
            return False
        root = self._as_root(unit)
        attacker_root = self._as_root(attacking_unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "shooting phase":
            logger.error("ERROR: BLAZING IRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: BLAZING IRE: not opponent's Shooting phase")
            return False
        if candidates and not self._as_unit_in_candidates(root, candidates):
            logger.error("ERROR: BLAZING IRE: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: BLAZING IRE: target transport is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: BLAZING IRE: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_transport(root):
            logger.error("ERROR: BLAZING IRE: target must be an ADEPTA SORORITAS TRANSPORT")
            return False
        if attacker_root is not None and self._as_owned_by_player(attacker_root, self.player):
            logger.error("ERROR: BLAZING IRE: attacker is not enemy")
            return False
        embarked_units = list(getattr(root, "transport_passengers", []) or [])
        if not embarked_units:
            logger.error("ERROR: BLAZING IRE: no embarked units")
            return False

        queue_fn = getattr(self.game, "_queue_transport_reactive_disembark_decisions", None) if self.game is not None else None
        if not callable(queue_fn):
            logger.error("ERROR: BLAZING IRE: reactive disembark decision queue unavailable")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        requests = list(
            queue_fn(
                player=self.player,
                transport=root,
                enemy_unit=attacker_root,
                ability={"name": str(stratagem.name or "BLAZING IRE")},
                trigger="unit_shooting_resolved",
                max_units=1,
            )
            or []
        )
        if not requests:
            logger.error("ERROR: BLAZING IRE: no disembark decision was queued")
            return False
        enemy_id = self._as_sort_key(attacker_root) if attacker_root is not None else ""
        for req in requests:
            req_ctx = dict(getattr(req, "context", {}) or {})
            req_ctx["reactive_disembark_then_shoot_enemy_only"] = True
            req_ctx["reactive_disembark_shoot_enemy_id"] = str(enemy_id or "")
            req_ctx["reactive_disembark_shoot_source"] = str(stratagem.name or "BLAZING IRE")
            req.context = req_ctx

        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: BLAZING IRE: queued disembark decision and follow-up reactive shooting into the attacking unit."
        )
        return True

    def _use_bringers_of_flame_carry_forth_the_faithful(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_bringers_of_flame():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit") or kwargs.get("transport_unit") or kwargs.get("transport")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: no target transport provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "movement phase":
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: not your Movement phase")
            return False
        if candidates and not self._as_unit_in_candidates(root, candidates):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target transport is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_transport(root):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target must be an ADEPTA SORORITAS TRANSPORT")
            return False
        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "moved_this_round", False)) or bool(getattr(round_state, "advanced_this_round", False)):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target transport already moved")
            return False
        if bool(getattr(round_state, "fell_back_this_round", False)):
            logger.error("ERROR: CARRY FORTH THE FAITHFUL: target transport already Fell Back")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False

        owner_id = str(getattr(self.player, "id", "") or "")
        turn = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["carry_forth_the_faithful_active"] = True
        sr["carry_forth_the_faithful_turn_owner"] = owner_id
        sr["carry_forth_the_faithful_turn"] = int(turn)
        sr["carry_forth_the_faithful_source"] = str(stratagem.name or "CARRY FORTH THE FAITHFUL")
        sr["carry_forth_the_faithful_disembark_allow_after_advance"] = True
        sr["carry_forth_the_faithful_disembark_force_no_charge"] = True
        sr["stratagem_carry_forth_the_faithful_reroll_advance"] = True
        sr["stratagem_carry_forth_the_faithful_reroll_advance_owner"] = owner_id
        sr["stratagem_carry_forth_the_faithful_reroll_advance_turn"] = int(turn)
        root.special_rules = sr

        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: CARRY FORTH THE FAITHFUL: %s can re-roll Advance; disembarking after Advance is allowed but those units cannot charge this turn.",
            getattr(root, "name", "Transport"),
        )
        return True

    def _use_army_of_faith_angelic_descent(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_army_of_faith():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: ANGELIC DESCENT: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: ANGELIC DESCENT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: ANGELIC DESCENT: not opponent's Fight phase")
            return False
        eligible = candidates or self._army_of_faith_angelic_descent_candidates()
        if eligible and not self._as_unit_in_candidates(root, eligible):
            logger.error("ERROR: ANGELIC DESCENT: target is not currently eligible")
            return False
        if not self._as_owned_by_player(root, self.player):
            logger.error("ERROR: ANGELIC DESCENT: target unit is not yours")
            return False
        if not self._as_on_battlefield(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: ANGELIC DESCENT: target cannot be selected")
            return False
        if not self._is_adepta_sororitas_unit(root):
            logger.error("ERROR: ANGELIC DESCENT: target is not ADEPTA SORORITAS")
            return False
        if not self._as_has_keyword(root, "JUMP PACK"):
            logger.error("ERROR: ANGELIC DESCENT: target must have JUMP PACK")
            return False
        if self._as_has_enemy_within_engagement_range(root):
            logger.error("ERROR: ANGELIC DESCENT: target is within Engagement Range")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        if not self._as_place_unit_into_strategic_reserves(root, reason=str(getattr(stratagem, "name", "") or "")):
            logger.error("ERROR: ANGELIC DESCENT: failed to place target into Strategic Reserves")
            return False
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            "INFO: ANGELIC DESCENT: %s entered Strategic Reserves.",
            getattr(root, "name", "Unit"),
        )
        return True

    def _use_hallowed_righteous_vengeance(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: RIGHTEOUS VENGEANCE: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: RIGHTEOUS VENGEANCE: wrong phase")
            return False
        if not self._as_on_battlefield(root):
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if not self._is_adepta_sororitas_unit(root):
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: RIGHTEOUS VENGEANCE: target already fought")
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: RIGHTEOUS VENGEANCE: target cannot be selected")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["righteous_vengeance_active"] = True
        sr["righteous_vengeance_expires_phase"] = "FIGHT_PHASE"
        sr["righteous_vengeance_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["righteous_vengeance_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["righteous_vengeance_source"] = str(getattr(stratagem, "name", "") or "RIGHTEOUS VENGEANCE")
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: RIGHTEOUS VENGEANCE: {getattr(root, 'name', 'Unit')} re-rolls melee hit rolls "
            "and re-rolls melee wound rolls while Below Half-strength this phase."
        )
        return True

    def _use_hallowed_suffering_and_sacrifice(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: SUFFERING AND SACRIFICE: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: SUFFERING AND SACRIFICE: wrong phase")
            return False
        if not self._as_on_battlefield(root):
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if not self._is_adepta_sororitas_infantry_or_walker(root):
            logger.error("ERROR: SUFFERING AND SACRIFICE: target must be ADEPTA SORORITAS INFANTRY or WALKER")
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SUFFERING AND SACRIFICE: target cannot be selected")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["suffering_and_sacrifice_active"] = True
        sr["suffering_and_sacrifice_expires_phase"] = "FIGHT_PHASE"
        sr["suffering_and_sacrifice_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["suffering_and_sacrifice_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["suffering_and_sacrifice_source"] = str(getattr(stratagem, "name", "") or "SUFFERING AND SACRIFICE")
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: SUFFERING AND SACRIFICE: enemy units in Engagement Range must target {getattr(root, 'name', 'Unit')} this phase."
        )
        return True

    def _use_hallowed_spirit_of_the_martyr(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit")
        candidates = list(kwargs.get("candidates") or kwargs.get("target_units") or [])
        if unit is None:
            if len(candidates) == 1:
                unit = candidates[0]
            else:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "SPIRIT OF THE MARTYR":
                        continue
                    unit = reaction.get("unit") or reaction.get("target_unit")
                    enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("attacking_unit")
                    candidates = candidates or list(reaction.get("candidates") or [])
                    break
        if unit is None:
            logger.error("ERROR: SPIRIT OF THE MARTYR: no target unit provided")
            return False
        root = self._as_root(unit)
        if root is None:
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "fight phase":
            logger.error("ERROR: SPIRIT OF THE MARTYR: wrong phase")
            return False
        if not self._as_on_battlefield(root):
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: SPIRIT OF THE MARTYR: target was not selected by the attacker")
            return False
        if enemy_unit is not None and self._as_owned_by_player(enemy_unit, self.player):
            logger.error("ERROR: SPIRIT OF THE MARTYR: attacker is not enemy")
            return False
        if not self._is_adepta_sororitas_unit(root):
            return False
        if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
            logger.error("ERROR: SPIRIT OF THE MARTYR: target already fought")
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: SPIRIT OF THE MARTYR: target cannot be selected")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["spirit_of_martyr_active"] = True
        sr["spirit_of_martyr_expires_phase"] = "FIGHT_PHASE"
        sr["spirit_of_martyr_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["spirit_of_martyr_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["spirit_of_martyr_source"] = str(getattr(stratagem, "name", "") or "SPIRIT OF THE MARTYR")
        root.special_rules = sr
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: SPIRIT OF THE MARTYR: {getattr(root, 'name', 'Unit')} can fight on death this phase.")
        return True

    def _use_hallowed_praise_the_fallen(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        enemy_unit = kwargs.get("enemy_unit") or kwargs.get("attacking_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None:
            if len(candidates) == 1:
                unit = candidates[0]
            else:
                for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                    if str(reaction.get("stratagem", "") or "").strip().upper() != "PRAISE THE FALLEN":
                        continue
                    unit = reaction.get("unit") or reaction.get("target_unit")
                    enemy_unit = enemy_unit or reaction.get("enemy_unit") or reaction.get("attacking_unit")
                    candidates = candidates or list(reaction.get("candidates") or [])
                    break
        if unit is None:
            logger.error("ERROR: PRAISE THE FALLEN: no target unit provided")
            return False
        root = self._as_root(unit)
        enemy_root = self._as_root(enemy_unit)
        if root is None or enemy_root is None:
            logger.error("ERROR: PRAISE THE FALLEN: missing attacker context")
            return False
        phase_name = self._as_phase_name_lower(kwargs.get("phase_name") or self._current_phase_name or "")
        if phase_name != "shooting phase":
            logger.error("ERROR: PRAISE THE FALLEN: wrong phase")
            return False
        get_current_player = getattr(self.game, "get_current_player", None) if self.game is not None else None
        active_player = get_current_player() if callable(get_current_player) else None
        if active_player is self.player:
            logger.error("ERROR: PRAISE THE FALLEN: not opponent's Shooting phase")
            return False
        if not self._as_on_battlefield(root):
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if self._as_owned_by_player(enemy_root, self.player):
            logger.error("ERROR: PRAISE THE FALLEN: attacker is not enemy")
            return False
        if candidates and root not in candidates:
            logger.error("ERROR: PRAISE THE FALLEN: target was not damaged by the attacker")
            return False
        if not self._is_adepta_sororitas_unit(root):
            return False
        if bool(self._unit_cannot_be_target_of_stratagem(root)):
            logger.error("ERROR: PRAISE THE FALLEN: target cannot be selected")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        queued = None
        queue_fn = getattr(self.game, "_queue_setup_reactive_shooting_decision", None) if self.game is not None else None
        if callable(queue_fn):
            queued = queue_fn(
                player=self.player,
                unit=root,
                target_unit=enemy_root,
                source=stratagem.name,
            )
        if queued is None:
            logger.error("ERROR: PRAISE THE FALLEN: failed to queue reactive shooting decision")
            return False
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: PRAISE THE FALLEN: {getattr(root, 'name', 'Unit')} can shoot reactively into {getattr(enemy_root, 'name', 'Unit')}."
        )
        return True

    def _use_hallowed_sanctified_immolation(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        root = self._as_root(
            kwargs.get("destroyed_unit")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        destroyed_model = kwargs.get("destroyed_model") or kwargs.get("model")
        if root is None or destroyed_model is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() != "SANCTIFIED IMMOLATION":
                    continue
                root = root or self._as_root(
                    reaction.get("destroyed_unit")
                    or reaction.get("unit")
                    or reaction.get("target_unit")
                )
                destroyed_model = destroyed_model or reaction.get("destroyed_model")
                break
        if root is None or destroyed_model is None:
            logger.error("ERROR: SANCTIFIED IMMOLATION: missing destroyed model context")
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if not self._is_adepta_sororitas_vehicle(root):
            logger.error("ERROR: SANCTIFIED IMMOLATION: target must be ADEPTA SORORITAS VEHICLE")
            return False
        has_deadly_demise = getattr(root, "has_deadly_demise", None)
        if not callable(has_deadly_demise):
            return False
        try:
            has_deadly, _damage_dice = has_deadly_demise()
        except Exception:
            has_deadly = False
        if not has_deadly:
            logger.error("ERROR: SANCTIFIED IMMOLATION: target model has no Deadly Demise")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        try:
            setattr(destroyed_model, "_sanctified_immolation_auto_trigger_once", True)
        except Exception:
            pass
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: SANCTIFIED IMMOLATION: Deadly Demise auto-triggers for the destroyed model.")
        return True

    def _resolve_divine_intervention_context(self, **kwargs) -> tuple[Any, Any, Optional[tuple]]:
        root = self._as_root(
            kwargs.get("unit")
            or kwargs.get("target_unit")
            or kwargs.get("destroyed_unit")
        )
        model = kwargs.get("destroyed_model") or kwargs.get("model")
        destroyed_position = kwargs.get("destroyed_position")
        if root is not None and model is not None:
            return root, model, destroyed_position
        for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
            if str(reaction.get("stratagem", "") or "").strip().upper() != "DIVINE INTERVENTION":
                continue
            if root is None:
                root = self._as_root(
                    reaction.get("unit")
                    or reaction.get("target_unit")
                    or reaction.get("destroyed_unit")
                )
            if model is None:
                model = reaction.get("destroyed_model")
            if destroyed_position is None:
                destroyed_position = reaction.get("destroyed_position")
            break
        return root, model, destroyed_position

    @staticmethod
    def _resolve_discard_values_from_kwargs(
        *,
        kwargs: dict[str, Any],
        pool: list[int],
    ) -> list[int]:
        discard_values = kwargs.get("miracle_dice_to_discard")
        if discard_values is None:
            discard_values = kwargs.get("discard_miracle_dice_values")
        if discard_values is None:
            discard_values = kwargs.get("miracle_dice_discard")
        values: list[int] = []
        if isinstance(discard_values, (list, tuple)):
            for value in list(discard_values):
                try:
                    values.append(int(value))
                except Exception:
                    continue
        if values:
            return values
        count = kwargs.get("discard_count")
        if count is None:
            count = kwargs.get("miracle_dice_discard_count")
        try:
            discard_count = int(count or 0)
        except Exception:
            discard_count = 0
        if discard_count <= 0:
            return []
        sorted_pool = sorted(int(v) for v in list(pool or []))
        if not sorted_pool:
            return []
        return list(sorted_pool[: min(discard_count, len(sorted_pool))])

    @staticmethod
    def _can_consume_discard_values(*, pool: list[int], values: list[int]) -> bool:
        remaining = list(pool or [])
        for value in list(values or []):
            try:
                idx = remaining.index(int(value))
            except Exception:
                return False
            remaining.pop(idx)
        return True

    @staticmethod
    def _consume_discard_values(*, pool: list[int], values: list[int]) -> list[int]:
        remaining = list(pool or [])
        for value in list(values or []):
            idx = remaining.index(int(value))
            remaining.pop(idx)
        return remaining

    def _use_hallowed_divine_intervention(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_hallowed_martyrs():
            return False
        root, model, destroyed_position = self._resolve_divine_intervention_context(**kwargs)
        if root is None or model is None:
            logger.error("ERROR: DIVINE INTERVENTION: missing destroyed CHARACTER context")
            return False
        if not self._as_owned_by_player(root, self.player):
            return False
        if not self._is_adepta_sororitas_character(root):
            logger.error("ERROR: DIVINE INTERVENTION: target must be an ADEPTA SORORITAS CHARACTER unit")
            return False
        if self._as_is_saint_celestine(root):
            logger.error("ERROR: DIVINE INTERVENTION: Saint Celestine cannot be selected")
            return False
        unit_id = self._as_sort_key(root)
        if unit_id and unit_id in self._as_divine_used_units():
            logger.error("ERROR: DIVINE INTERVENTION: this CHARACTER unit was already selected this battle")
            return False
        acts_mgr = self._as_miracle_dice_manager()
        if acts_mgr is None:
            logger.error("ERROR: DIVINE INTERVENTION: Acts of Faith manager unavailable")
            return False
        pool = list(getattr(acts_mgr, "miracle_dice", []) or [])
        if not pool:
            logger.error("ERROR: DIVINE INTERVENTION: no Miracle dice available to discard")
            return False
        discard_values = self._resolve_discard_values_from_kwargs(kwargs=kwargs, pool=pool)
        if not discard_values:
            logger.error("ERROR: DIVINE INTERVENTION: no Miracle dice selected to discard")
            return False
        if len(discard_values) < 1 or len(discard_values) > 3:
            logger.error("ERROR: DIVINE INTERVENTION: must discard 1-3 Miracle dice")
            return False
        if not self._can_consume_discard_values(pool=pool, values=discard_values):
            logger.error("ERROR: DIVINE INTERVENTION: selected Miracle dice are not available")
            return False
        if not self._as_spend_cp(stratagem, target_unit=root):
            return False
        try:
            acts_mgr.miracle_dice = self._consume_discard_values(pool=pool, values=discard_values)
        except Exception:
            logger.error("ERROR: DIVINE INTERVENTION: failed to discard Miracle dice")
            return False
        trigger_phase = kwargs.get("phase_name") or self._current_phase_name or ""
        self._as_divine_pending().append(
            {
                "unit": root,
                "model": model,
                "destroyed_position": destroyed_position,
                "discard_count": int(len(discard_values)),
                "trigger_phase_name": str(trigger_phase or ""),
                "trigger_phase_key": self._as_phase_key(trigger_phase),
                "source": str(getattr(stratagem, "name", "") or "DIVINE INTERVENTION"),
            }
        )
        if unit_id:
            self._as_divine_used_units().add(unit_id)
        self._as_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(
            f"INFO: DIVINE INTERVENTION: will return {getattr(model, 'name', 'Model')} at phase end after discarding "
            f"{int(len(discard_values))} Miracle dice."
        )
        return True
