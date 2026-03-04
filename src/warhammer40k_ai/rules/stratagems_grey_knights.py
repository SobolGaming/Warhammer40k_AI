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

    def _is_brotherhood_strike(self) -> bool:
        mgr = self._get_gk_mgr()
        checker = getattr(mgr, "is_brotherhood_strike", None) if mgr is not None else None
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
        if phase_name != "MOVEMENT_PHASE":
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
            for key in (
                "combat_manifestation_deep_strike_min_distance",
                "combat_manifestation_deep_strike_turn_owner",
                "combat_manifestation_deep_strike_turn",
                "combat_manifestation_deep_strike_expires_phase",
                "combat_manifestation_source",
            ):
                if key in sr:
                    sr.pop(key, None)
                    changed = True
            if changed:
                root.special_rules = sr

    def _use_grey_knights_warpbane_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "COMBAT MANIFESTATION":
            return self._use_brotherhood_strike_combat_manifestation(stratagem, **kwargs)
        if name_u == "MIRAGE OF ECHOES":
            return self._use_augurium_mirage_of_echoes(stratagem, **kwargs)
        if name_u == "REDIRECTED STRIKE":
            return self._use_augurium_redirected_strike(stratagem, **kwargs)
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
