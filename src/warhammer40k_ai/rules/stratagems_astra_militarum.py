from __future__ import annotations

from typing import Any, Optional

import logging

from ..utility.dice import get_roll
from ..utility.entity_ids import maybe_entity_id

logger = logging.getLogger(__name__)


class AstraMilitarumStratagemMixin:
    @staticmethod
    def _am_root(unit: Any) -> Any:
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            return get_root()
        return unit

    @staticmethod
    def _am_sort_key(unit: Any) -> str:
        return str(maybe_entity_id(unit) or "")

    def _get_astra_militarum_mgr(self):
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        return getattr(army, "astra_militarum_detachments", None) if army is not None else None

    def _is_grizzled_company(self) -> bool:
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "is_grizzled_company", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_bridgehead_strike(self) -> bool:
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "is_bridgehead_strike", None) if mgr is not None else None
        return bool(checker()) if callable(checker) else False

    def _is_astra_militarum_unit(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "unit_is_astra_militarum", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        return bool(has_any_keyword("ASTRA MILITARUM")) if callable(has_any_keyword) else False

    def _is_officer_unit(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        mgr = self._get_astra_militarum_mgr()
        checker = getattr(mgr, "unit_is_officer", None) if mgr is not None else None
        if callable(checker):
            return bool(checker(root))
        has_any_keyword = getattr(root, "has_any_keyword", None)
        return bool(has_any_keyword("OFFICER")) if callable(has_any_keyword) else False

    @staticmethod
    def _am_owned_by_player(unit: Any, player: Any) -> bool:
        if unit is None or player is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(unit, "parent_army", None)
        return getattr(parent_army, "player", None) is player

    @staticmethod
    def _am_is_alive(unit: Any) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive):
            return bool(is_alive())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _am_is_in_reserves(unit: Any) -> bool:
        if unit is None:
            return True
        checker = getattr(unit, "is_in_reserves", None)
        if callable(checker):
            return bool(checker())
        return bool(getattr(unit, "is_in_reserves", False))

    @staticmethod
    def _am_has_keyword(unit: Any, keyword: str) -> bool:
        if unit is None:
            return False
        key = str(keyword or "").strip()
        if not key:
            return False
        has_keyword = getattr(unit, "has_keyword", None)
        if callable(has_keyword):
            return bool(has_keyword(key))
        has_any_keyword = getattr(unit, "has_any_keyword", None)
        if callable(has_any_keyword):
            return bool(has_any_keyword(key))
        return False

    @staticmethod
    def _am_has_deep_strike(unit: Any) -> bool:
        if unit is None:
            return False
        has_deep_strike = getattr(unit, "has_deep_strike", None)
        return bool(has_deep_strike()) if callable(has_deep_strike) else False

    @staticmethod
    def _am_name_matches(unit: Any, phrase: str) -> bool:
        name = str(getattr(unit, "name", "") or "").strip().lower()
        token = str(phrase or "").strip().lower()
        return bool(name and token and token in name)

    def _am_on_battlefield(self, unit: Any) -> bool:
        if not self._am_is_alive(unit):
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if self._am_is_in_reserves(unit):
            return False
        if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
            return False
        return True

    def _am_army_roots(self) -> list[Any]:
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._am_root(unit)
            if root is None:
                continue
            uid = self._am_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _am_is_in_engagement_range(self, unit: Any) -> bool:
        root = self._am_root(unit)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if root is None or game_map is None:
            return False
        get_enemy_units = getattr(game_map, "get_enemy_units", None)
        is_within_engagement_range = getattr(game_map, "is_within_engagement_range", None)
        if not callable(get_enemy_units) or not callable(is_within_engagement_range):
            return False
        for enemy in list(get_enemy_units(root) or []):
            if enemy is None or not self._am_is_alive(enemy):
                continue
            if not bool(getattr(enemy, "deployed", True)):
                continue
            if self._am_is_in_reserves(enemy):
                continue
            if bool(is_within_engagement_range(root, enemy)):
                return True
        return False

    def _am_is_visible_to_unit(self, source_unit: Any, target_unit: Any) -> bool:
        source_root = self._am_root(source_unit)
        target_root = self._am_root(target_unit)
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if source_root is None or target_root is None or game_map is None:
            return False
        has_los = getattr(source_root, "_has_line_of_sight_to_target", None)
        if not callable(has_los):
            return True
        for model in list(getattr(source_root, "models", []) or []):
            if not bool(getattr(model, "is_alive", False)):
                continue
            if bool(has_los(model, target_root, game_map)):
                return True
        return False

    def _am_attached_has_order_key(self, unit: Any, order_key: str) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        key = str(order_key or "").strip().upper()
        if not key:
            return False
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        checker = getattr(voice, "_attached_unit_has_order_key", None)
        if callable(checker):
            return bool(checker(root, key))
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            active = str(sr.get("voice_of_command_order_key", "") or "").strip().upper()
            if active == key:
                return True
        return False

    def _am_attached_has_any_order(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if str(sr.get("voice_of_command_order_key", "") or "").strip():
                return True
        return False

    def _am_within_any_objective_range(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        checker = getattr(root, "is_within_any_objective_range", None)
        if callable(checker):
            return bool(checker(game_map=game_map))
        return False

    def _am_within_controlled_objective_range(self, unit: Any) -> bool:
        root = self._am_root(unit)
        if root is None:
            return False
        game_map = getattr(self.game, "map", None) if self.game is not None else None
        checker = getattr(root, "_within_controlled_objective_range", None)
        if callable(checker):
            return bool(checker(game_map=game_map))
        return False

    def _am_battlefield_units(
        self,
        *,
        require_infantry: bool = False,
        require_officer: bool = False,
        require_not_shot: bool = False,
        require_order_key: str = "",
        require_any_order: bool = False,
        require_within_objective: bool = False,
        require_within_controlled_objective: bool = False,
    ) -> list[Any]:
        if not self._is_grizzled_company():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        if army is None:
            return []
        out: list[Any] = []
        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            root = self._am_root(unit)
            if root is None:
                continue
            uid = self._am_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if require_officer and not self._is_officer_unit(root):
                continue
            if require_infantry:
                has_keyword = getattr(root, "has_keyword", None)
                if not callable(has_keyword) or not bool(has_keyword("INFANTRY")):
                    continue
            if require_not_shot and bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if require_order_key and not self._am_attached_has_order_key(root, require_order_key):
                continue
            if require_any_order and not self._am_attached_has_any_order(root):
                continue
            if require_within_objective and not self._am_within_any_objective_range(root):
                continue
            if require_within_controlled_objective and not self._am_within_controlled_objective_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _grizzled_mordian_minute_candidates(self) -> list[Any]:
        return self._am_battlefield_units(
            require_infantry=True,
            require_not_shot=True,
            require_order_key="FIRST_RANK_FIRE",
        )

    def _grizzled_purging_fire_candidates(self) -> list[Any]:
        return self._am_battlefield_units(
            require_not_shot=True,
            require_any_order=True,
            require_within_objective=True,
        )

    def _grizzled_veteran_sharpshooters_candidates(self) -> list[Any]:
        return self._am_battlefield_units(require_not_shot=True)

    def _grizzled_no_retreat_candidates(self) -> list[Any]:
        return self._am_battlefield_units(
            require_order_key="DUTY_HONOUR",
            require_within_controlled_objective=True,
        )

    def _grizzled_snap_to_it_officer_candidates(self, *, phase_name: str) -> list[Any]:
        if not self._is_grizzled_company():
            return []
        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        if voice is None:
            return []
        getter = getattr(voice, "get_eligible_officers", None)
        if not callable(getter):
            return []
        officers = list(
            getter(
                game=self.game,
                player=self.player,
                phase_name=str(phase_name or "").strip().upper(),
                trigger="snap_to_it",
            )
            or []
        )
        out: list[Any] = []
        seen: set[str] = set()
        for unit in officers:
            root = self._am_root(unit)
            if root is None:
                continue
            uid = self._am_sort_key(root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root) or not self._is_officer_unit(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _grizzled_no_retreat_objective_candidates(self, unit: Any) -> list[Any]:
        if unit is None:
            return []
        helper = getattr(self, "_corrupting_taint_objective_candidates", None)
        if callable(helper):
            candidates = list(helper(unit) or [])
            if candidates:
                return sorted(candidates, key=self._am_sort_key)
        if self.game is None:
            return []
        game_map = getattr(self.game, "map", None)
        root = self._am_root(unit)
        if game_map is None or root is None:
            return []
        out = []
        for obj in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(obj, "location", None)
            if loc is None or bool(getattr(loc, "removed", False)):
                continue
            if getattr(loc, "controlling_player", None) is not self.player:
                continue
            if not bool(root.is_within_objective_range(loc)):
                continue
            out.append(obj)
        return sorted(out, key=self._am_sort_key)

    def _bridgehead_bellicosa_drop_candidates(self) -> list[Any]:
        if not self._is_bridgehead_strike():
            return []
        out: list[Any] = []
        for root in self._am_army_roots():
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_is_alive(root):
                continue
            if not self._am_is_in_reserves(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if not self._am_has_keyword(root, "INFANTRY"):
                continue
            if not self._am_has_deep_strike(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _bridgehead_fire_and_relocate_candidates(self) -> list[Any]:
        if not self._is_bridgehead_strike():
            return []
        out: list[Any] = []
        for root in self._am_army_roots():
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if self._am_has_keyword(root, "TITANIC"):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _bridgehead_firing_hot_candidates(self) -> list[Any]:
        if not self._is_bridgehead_strike():
            return []
        out: list[Any] = []
        for root in self._am_army_roots():
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if bool(getattr(getattr(root, "round_state", None), "shot_this_round", False)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if self._am_has_keyword(root, "MILITARUM TEMPESTUS") or self._am_name_matches(root, "kasrkin"):
                out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _bridgehead_aerial_extraction_candidates(self) -> list[Any]:
        if not self._is_bridgehead_strike():
            return []
        out: list[Any] = []
        for root in self._am_army_roots():
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if self._am_is_in_engagement_range(root):
                continue
            if self._am_has_deep_strike(root) or self._am_name_matches(root, "valkyrie"):
                out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _bridgehead_on_my_position_candidates(self) -> list[Any]:
        if not self._is_bridgehead_strike():
            return []
        out: list[Any] = []
        for root in self._am_army_roots():
            if not self._am_owned_by_player(root, self.player):
                continue
            if not self._am_on_battlefield(root):
                continue
            if bool(self._unit_cannot_be_target_of_stratagem(root)):
                continue
            if not self._is_astra_militarum_unit(root):
                continue
            if not self._am_has_keyword(root, "REGIMENT"):
                continue
            if not self._am_has_keyword(root, "INFANTRY"):
                continue
            if not self._am_is_in_engagement_range(root):
                continue
            out.append(root)
        return sorted(out, key=self._am_sort_key)

    def _bridgehead_reaction_exists(self, event_name: str, stratagem_name: str) -> bool:
        wanted_event = str(event_name or "").strip().lower()
        wanted_name = str(stratagem_name or "").strip().upper()
        for reaction in list(getattr(self, "_pending_reactions", []) or []):
            event = str(reaction.get("event", "") or "").strip().lower()
            name = str(reaction.get("stratagem", "") or "").strip().upper()
            if event == wanted_event and name == wanted_name:
                return True
        return False

    def _queue_bridgehead_servo_designators_target_decision(
        self,
        *,
        stratagem: Any,
        source_unit: Any,
        candidates: list[Any],
    ) -> bool:
        if self.game is None:
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        source_root = self._am_root(source_unit)
        if source_root is None:
            return False
        candidate_units = [
            candidate
            for candidate in list(candidates or [])
            if candidate is not None and self._am_root(candidate) is not None
        ]
        if not candidate_units:
            return False
        options = [
            DecisionOption.create(
                str(getattr(candidate, "name", "Unit") or "Unit"),
                payload={"target_unit_id": maybe_entity_id(candidate)},
            )
            for candidate in candidate_units
        ]
        if not options:
            return False
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "SERVO-DESIGNATORS: select a visible enemy unit hit by that unit.",
            player_id=getattr(self.player, "id", None),
            options=options,
            context={
                "ability": "post_shoot_no_cover",
                "ability_name": str(getattr(stratagem, "name", "") or "SERVO-DESIGNATORS"),
                "attacker_unit_id": maybe_entity_id(source_root),
                "expires_phase": "SHOOTING_PHASE",
                "expires_timing": "PHASE_END",
            },
        )
        request_decision = getattr(self.game, "request_decision", None)
        if callable(request_decision):
            request_decision(request)
            return True
        return False

    def _am_effective_cp_cost(self, stratagem: Any, *, target_unit: Any = None) -> int:
        cp_cost = int(getattr(stratagem, "cp_cost", 0) or 0)
        preview = getattr(self.player, "apply_stratagem_cp_cost", None)
        if callable(preview):
            data = preview(stratagem, target_unit=target_unit) or {}
            cp_cost = int(data.get("cost", cp_cost))
        return cp_cost

    def _am_spend_cp(self, stratagem: Any, *, target_unit: Any = None) -> bool:
        cp_cost = self._am_effective_cp_cost(stratagem, target_unit=target_unit)
        return bool(
            self.player.spend_command_points(
                cp_cost,
                reason=f"Stratagem: {stratagem.name}",
                source="stratagem",
            )
        )

    def _am_finalize_use(self, stratagem: Any, *, dequeue: bool = False) -> None:
        if dequeue:
            self._dequeue_reaction_by_name(stratagem.name)
        self._used_stratagems_this_phase.add((stratagem.name or "").strip().upper())

    def _am_has_voice_prompt_subscriber(self) -> bool:
        event_system = getattr(self.game, "event_system", None) if self.game is not None else None
        subscribers = getattr(event_system, "subscribers", None) if event_system is not None else None
        if event_system is None or not isinstance(subscribers, dict):
            return False
        return bool(subscribers.get("voice_of_command_prompt"))

    def _on_unit_shooting_resolved_bridgehead_servo_designators(
        self,
        attacker_unit=None,
        hits_by_target=None,
        **_kwargs,
    ) -> None:
        if attacker_unit is None or not hits_by_target:
            return
        if not self._is_bridgehead_strike():
            return
        current_phase = str(getattr(getattr(self.game, "phase", None), "name", "") or "").strip().upper()
        if current_phase != "SHOOTING_PHASE":
            return
        source_root = self._am_root(attacker_unit)
        if source_root is None:
            return
        attacker_army = getattr(source_root, "get_parent_army", lambda: None)()
        attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
        if attacker_player is not self.player:
            return
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            return
        if not self._am_on_battlefield(source_root):
            return
        if not self._is_astra_militarum_unit(source_root) or not self._am_has_keyword(source_root, "INFANTRY"):
            return
        if bool(self._unit_cannot_be_target_of_stratagem(source_root)):
            return

        stratagem = getattr(self, "get_by_name", lambda _name: None)("SERVO-DESIGNATORS")
        if stratagem is None:
            return
        if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
            return
        if (str(getattr(stratagem, "name", "") or "").strip().upper()) in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
            return

        candidates: list[Any] = []
        seen: set[str] = set()
        for target_unit, hits in list((hits_by_target or {}).items()):
            target_root = self._am_root(target_unit)
            if target_root is None:
                continue
            if int(hits or 0) <= 0:
                continue
            if not self._am_is_alive(target_root):
                continue
            if self._am_owned_by_player(target_root, self.player):
                continue
            if not self._am_is_visible_to_unit(source_root, target_root):
                continue
            uid = self._am_sort_key(target_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            candidates.append(target_root)
        candidates = sorted(candidates, key=self._am_sort_key)
        if not candidates:
            return
        if self._bridgehead_reaction_exists("unit_shooting_resolved", stratagem.name):
            return
        if not bool(stratagem.can_use(self.player, self.game, unit=source_root, candidates=candidates, phase_name="Shooting phase")):
            return
        self._queue_reaction(
            {
                "event": "unit_shooting_resolved",
                "phase": "Shooting phase",
                "phase_name": "Shooting phase",
                "stratagem": stratagem.name,
                "cp_cost": stratagem.cp_cost,
                "unit": source_root,
                "target_unit": source_root,
                "candidates": candidates,
            },
            use_timer=False,
        )

    def _queue_bridgehead_phase_end_reactions(self, *, player: Any, phase: Any) -> None:
        if not self._is_bridgehead_strike():
            return
        if player is self.player:
            return
        phase_name = str(getattr(phase, "name", "") or "").strip().upper()
        if phase_name != "FIGHT_PHASE":
            return

        def _queue(name: str, candidates: list[Any]) -> None:
            stratagem = getattr(self, "get_by_name", lambda _name: None)(name)
            if stratagem is None:
                return
            if int(getattr(self.player, "command_points", 0) or 0) < int(getattr(stratagem, "cp_cost", 0) or 0):
                return
            name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
            if name_u in set(getattr(self, "_used_stratagems_this_phase", set()) or set()):
                return
            if not candidates or self._bridgehead_reaction_exists("phase_end", stratagem.name):
                return
            if not bool(stratagem.can_use(self.player, self.game, unit=candidates[0], candidates=candidates, phase_name="Fight phase")):
                return
            self._queue_reaction(
                {
                    "event": "phase_end",
                    "phase": "Fight phase",
                    "phase_name": "Fight phase",
                    "stratagem": stratagem.name,
                    "cp_cost": stratagem.cp_cost,
                    "candidates": list(candidates),
                },
                use_timer=False,
            )

        _queue("AERIAL EXTRACTION", self._bridgehead_aerial_extraction_candidates())
        _queue("ON MY POSITION", self._bridgehead_on_my_position_candidates())

    def _use_bridgehead_bellicosa_drop(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: BELLICOSA DROP: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "movement phase":
            logger.error("ERROR: BELLICOSA DROP: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: BELLICOSA DROP: not your Movement phase")
            return False
        if root not in self._bridgehead_bellicosa_drop_candidates():
            logger.error("ERROR: BELLICOSA DROP: target must be ASTRA MILITARUM INFANTRY in Reserves with Deep Strike")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["bridgehead_bellicosa_deep_strike_min_distance"] = 6.0
        sr["bridgehead_bellicosa_expires_phase"] = "MOVEMENT_PHASE"
        sr["bridgehead_bellicosa_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["bridgehead_bellicosa_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["bridgehead_bellicosa_no_charge_turn_owner"] = str(getattr(self.player, "id", "") or "")
        sr["bridgehead_bellicosa_no_charge_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["bridgehead_bellicosa_source"] = str(getattr(stratagem, "name", "") or "BELLICOSA DROP")
        root.special_rules = sr
        ability_cache = getattr(root, "_ability_cache", None)
        if isinstance(ability_cache, dict):
            ability_cache.pop("deep_strike", None)
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: BELLICOSA DROP: unit can Deep Strike more than 6\" away and cannot charge this turn.")
        return True

    def _use_bridgehead_fire_and_relocate(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FIRE AND RELOCATE: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: FIRE AND RELOCATE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FIRE AND RELOCATE: not your Shooting phase")
            return False
        if root not in self._bridgehead_fire_and_relocate_candidates():
            logger.error("ERROR: FIRE AND RELOCATE: target must be non-TITANIC ASTRA MILITARUM unit on the battlefield")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["bridgehead_fire_and_relocate_active"] = True
        sr["bridgehead_fire_and_relocate_expires_phase"] = "SHOOTING_PHASE"
        sr["bridgehead_fire_and_relocate_owner"] = str(getattr(self.player, "id", "") or "")
        sr["bridgehead_fire_and_relocate_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["bridgehead_fire_and_relocate_source"] = str(getattr(stratagem, "name", "") or "FIRE AND RELOCATE")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: FIRE AND RELOCATE: unit can shoot after advancing this phase.")
        return True

    def _use_bridgehead_firing_hot(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        candidates = list(kwargs.get("candidates") or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: FIRING HOT: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: FIRING HOT: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: FIRING HOT: not your Shooting phase")
            return False
        if root not in self._bridgehead_firing_hot_candidates():
            logger.error("ERROR: FIRING HOT: target must be MILITARUM TEMPESTUS or Kasrkin and not yet shot")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["bridgehead_firing_hot_active"] = True
        sr["bridgehead_firing_hot_expires_phase"] = "SHOOTING_PHASE"
        sr["bridgehead_firing_hot_owner"] = str(getattr(self.player, "id", "") or "")
        sr["bridgehead_firing_hot_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["bridgehead_firing_hot_source"] = str(getattr(stratagem, "name", "") or "FIRING HOT")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: FIRING HOT: hot-shot weapons gain +1 Strength and AP within 12\" this phase.")
        return True

    def _use_bridgehead_servo_designators(self, stratagem: Any, **kwargs) -> bool:
        source_unit = kwargs.get("unit") or kwargs.get("source_unit") or kwargs.get("target_unit")
        pending = None
        if source_unit is None or not list(kwargs.get("candidates") or []):
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                name_u = str(reaction.get("stratagem", "") or "").strip().upper()
                if name_u in {"SERVO-DESIGNATORS", "SERVOÃ¢â‚¬â€˜DESIGNATORS", "SERVOÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ËœDESIGNATORS"}:
                    pending = reaction
                    break
        if source_unit is None and pending is not None:
            source_unit = pending.get("unit") or pending.get("target_unit")
        if source_unit is None:
            logger.error("ERROR: SERVO-DESIGNATORS: no source unit provided")
            return False
        root = self._am_root(source_unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: SERVO-DESIGNATORS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: SERVO-DESIGNATORS: not your Shooting phase")
            return False
        if not self._am_on_battlefield(root):
            logger.error("ERROR: SERVO-DESIGNATORS: source unit must be on the battlefield")
            return False
        if not self._is_astra_militarum_unit(root) or not self._am_has_keyword(root, "INFANTRY"):
            logger.error("ERROR: SERVO-DESIGNATORS: source unit must be ASTRA MILITARUM INFANTRY")
            return False
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        candidates = [self._am_root(candidate) for candidate in candidates if self._am_root(candidate) is not None]
        candidates = sorted(candidates, key=self._am_sort_key)
        if not candidates:
            logger.error("ERROR: SERVO-DESIGNATORS: no eligible enemy units were hit and visible")
            return False
        direct_target = kwargs.get("enemy_unit") or kwargs.get("quarry") or kwargs.get("selected_unit")
        if direct_target is not None:
            target_root = self._am_root(direct_target)
            if target_root not in candidates:
                logger.error("ERROR: SERVO-DESIGNATORS: selected enemy unit is not eligible")
                return False
            if not self._am_spend_cp(stratagem, target_unit=root):
                return False
            sr = getattr(target_root, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["post_shoot_no_cover_active"] = True
            sr["post_shoot_no_cover_expires_phase"] = "SHOOTING_PHASE"
            sr["post_shoot_no_cover_source"] = str(getattr(stratagem, "name", "") or "SERVO-DESIGNATORS")
            sr["post_shoot_no_cover_owner"] = str(getattr(self.player, "id", "") or "")
            sr["post_shoot_no_cover_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
            target_root.special_rules = sr
            self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(f"INFO: SERVO-DESIGNATORS: {getattr(target_root, 'name', 'Unit')} loses Benefit of Cover this phase.")
            return True
        request_decision = getattr(self.game, "request_decision", None) if self.game is not None else None
        if self.game is None or not callable(request_decision):
            logger.error("ERROR: SERVO-DESIGNATORS: no decision queue available")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        if not self._queue_bridgehead_servo_designators_target_decision(
            stratagem=stratagem,
            source_unit=root,
            candidates=candidates,
        ):
            logger.error("ERROR: SERVO-DESIGNATORS: failed to queue target selection")
            return False
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: SERVO-DESIGNATORS: choose a hit visible enemy unit to lose Benefit of Cover this phase.")
        return True

    def _use_bridgehead_aerial_extraction(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        pending = None
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() == "AERIAL EXTRACTION":
                    pending = reaction
                    break
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: AERIAL EXTRACTION: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: AERIAL EXTRACTION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: AERIAL EXTRACTION: not opponent's Fight phase")
            return False
        if root not in self._bridgehead_aerial_extraction_candidates():
            logger.error("ERROR: AERIAL EXTRACTION: target must be eligible Deep Strike unit or Valkyrie not in Engagement Range")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        root.enter_strategic_reserves_midgame(
            game=self.game,
            game_map=getattr(self.game, "map", None),
            reason=str(getattr(stratagem, "name", "") or "AERIAL EXTRACTION"),
        )
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: AERIAL EXTRACTION: {getattr(root, 'name', 'Unit')} placed into Strategic Reserves.")
        return True

    def _use_bridgehead_on_my_position(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        pending = None
        if unit is None:
            for reaction in reversed(list(getattr(self, "_pending_reactions", []) or [])):
                if str(reaction.get("stratagem", "") or "").strip().upper() == "ON MY POSITION":
                    pending = reaction
                    break
        if unit is None and pending is not None:
            unit = pending.get("unit") or pending.get("target_unit")
        candidates = list(kwargs.get("candidates") or (pending.get("candidates") if pending is not None else []) or [])
        if unit is None and len(candidates) == 1:
            unit = candidates[0]
        if unit is None:
            logger.error("ERROR: ON MY POSITION: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None or not self._is_bridgehead_strike():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "fight phase":
            logger.error("ERROR: ON MY POSITION: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is self.player:
            logger.error("ERROR: ON MY POSITION: not opponent's Fight phase")
            return False
        if root not in self._bridgehead_on_my_position_candidates():
            logger.error("ERROR: ON MY POSITION: target must be engaged REGIMENT INFANTRY")
            return False

        game_map = getattr(self.game, "map", None) if self.game is not None else None
        if game_map is None:
            logger.error("ERROR: ON MY POSITION: no game map available")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        enemy_targets: list[Any] = []
        seen: set[str] = set()
        for enemy in list(game_map.get_enemy_units(root) or []):
            enemy_root = self._am_root(enemy)
            if enemy_root is None or not self._am_is_alive(enemy_root):
                continue
            if not bool(getattr(enemy_root, "deployed", True)):
                continue
            if self._am_is_in_reserves(enemy_root):
                continue
            if not bool(game_map.is_within_engagement_range(root, enemy_root)):
                continue
            uid = self._am_sort_key(enemy_root)
            if uid and uid in seen:
                continue
            if uid:
                seen.add(uid)
            enemy_targets.append(enemy_root)
        for enemy_root in enemy_targets:
            if int(get_roll("D6") or 0) < 2:
                continue
            mortal_wounds = int(get_roll("D6") or 0)
            if mortal_wounds <= 0:
                continue
            root._apply_mortal_wounds_to_unit(enemy_root, mortal_wounds, game_map=game_map)
        self_mortals = int(get_roll("D3") or 0) + int(get_roll("D3") or 0) + int(get_roll("D3") or 0)
        if self_mortals > 0:
            root._apply_mortal_wounds_to_unit(root, self_mortals, game_map=game_map)
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: ON MY POSITION: resolved mortal wounds against engaged enemies and the target unit.")
        return True

    def _use_astra_militarum_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
        if name_u == "AERIAL EXTRACTION":
            return self._use_bridgehead_aerial_extraction(stratagem, **kwargs)
        if name_u == "BELLICOSA DROP":
            return self._use_bridgehead_bellicosa_drop(stratagem, **kwargs)
        if name_u == "FIRE AND RELOCATE":
            return self._use_bridgehead_fire_and_relocate(stratagem, **kwargs)
        if name_u == "FIRING HOT":
            return self._use_bridgehead_firing_hot(stratagem, **kwargs)
        if name_u == "ON MY POSITION":
            return self._use_bridgehead_on_my_position(stratagem, **kwargs)
        if name_u in {"SERVO-DESIGNATORS", "SERVOÃ¢â‚¬â€˜DESIGNATORS", "SERVOÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ËœDESIGNATORS"}:
            return self._use_bridgehead_servo_designators(stratagem, **kwargs)
        if name_u == "MORDIAN MINUTE":
            return self._use_grizzled_mordian_minute(stratagem, **kwargs)
        if name_u == "NO RETREAT!":
            return self._use_grizzled_no_retreat(stratagem, **kwargs)
        if name_u == "PURGING FIRE":
            return self._use_grizzled_purging_fire(stratagem, **kwargs)
        if name_u == "SNAP TO IT":
            return self._use_grizzled_snap_to_it(stratagem, **kwargs)
        if name_u == "VETERAN SHARPSHOOTERS":
            return self._use_grizzled_veteran_sharpshooters(stratagem, **kwargs)
        return None

    def _use_astra_militarum_grizzled_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        return self._use_astra_militarum_stratagem(stratagem, **kwargs)

    def _use_grizzled_mordian_minute(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: MORDIAN MINUTE: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None:
            return False
        if not self._is_grizzled_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: MORDIAN MINUTE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: MORDIAN MINUTE: not your Shooting phase")
            return False
        if root not in self._grizzled_mordian_minute_candidates():
            logger.error(
                "ERROR: MORDIAN MINUTE: target must be ASTRA MILITARUM INFANTRY with First Rank, Fire! Second Rank, Fire! and not yet shot"
            )
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["mordian_minute_active"] = True
        sr["mordian_minute_strength_bonus"] = 1
        sr["mordian_minute_expires_phase"] = "SHOOTING_PHASE"
        sr["mordian_minute_owner"] = str(getattr(self.player, "id", "") or "")
        sr["mordian_minute_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["mordian_minute_source"] = str(getattr(stratagem, "name", "") or "MORDIAN MINUTE")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: MORDIAN MINUTE: {getattr(root, 'name', 'Unit')} gains +1 Strength with ranged weapons this phase.")
        return True

    def _use_grizzled_purging_fire(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: PURGING FIRE: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None:
            return False
        if not self._is_grizzled_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: PURGING FIRE: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: PURGING FIRE: not your Shooting phase")
            return False
        if root not in self._grizzled_purging_fire_candidates():
            logger.error(
                "ERROR: PURGING FIRE: target must be ASTRA MILITARUM unit with an active Order, within objective range, and not yet shot"
            )
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["purging_fire_active"] = True
        sr["purging_fire_expires_phase"] = "SHOOTING_PHASE"
        sr["purging_fire_owner"] = str(getattr(self.player, "id", "") or "")
        sr["purging_fire_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["purging_fire_source"] = str(getattr(stratagem, "name", "") or "PURGING FIRE")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: PURGING FIRE: {getattr(root, 'name', 'Unit')} gains Lethal Hits with ranged weapons this phase.")
        return True

    def _use_grizzled_veteran_sharpshooters(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: VETERAN SHARPSHOOTERS: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None:
            return False
        if not self._is_grizzled_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "shooting phase":
            logger.error("ERROR: VETERAN SHARPSHOOTERS: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: VETERAN SHARPSHOOTERS: not your Shooting phase")
            return False
        if root not in self._grizzled_veteran_sharpshooters_candidates():
            logger.error("ERROR: VETERAN SHARPSHOOTERS: target must be ASTRA MILITARUM unit that has not yet shot")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["veteran_sharpshooters_active"] = True
        sr["veteran_sharpshooters_expires_phase"] = "SHOOTING_PHASE"
        sr["veteran_sharpshooters_owner"] = str(getattr(self.player, "id", "") or "")
        sr["veteran_sharpshooters_turn"] = int(getattr(self.game, "turn", 0) or 0) if self.game is not None else 0
        sr["veteran_sharpshooters_source"] = str(getattr(stratagem, "name", "") or "VETERAN SHARPSHOOTERS")
        root.special_rules = sr
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info(f"INFO: VETERAN SHARPSHOOTERS: {getattr(root, 'name', 'Unit')} gains Ignores Cover with ranged weapons this phase.")
        return True

    def _use_grizzled_no_retreat(self, stratagem: Any, **kwargs) -> bool:
        unit = kwargs.get("unit") or kwargs.get("target_unit")
        if unit is None:
            candidates = list(kwargs.get("candidates") or [])
            if len(candidates) == 1:
                unit = candidates[0]
        if unit is None:
            logger.error("ERROR: NO RETREAT!: no target unit provided")
            return False
        root = self._am_root(unit)
        if root is None:
            return False
        if not self._is_grizzled_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip().lower()
        if phase_name != "command phase":
            logger.error("ERROR: NO RETREAT!: wrong phase")
            return False
        active_player = getattr(self.game, "get_current_player", lambda: None)() if self.game is not None else None
        if active_player is not self.player:
            logger.error("ERROR: NO RETREAT!: not your Command phase")
            return False
        if root not in self._grizzled_no_retreat_candidates():
            logger.error(
                "ERROR: NO RETREAT!: target must be ASTRA MILITARUM unit with Duty and Honour! while within objective range you control"
            )
            return False
        objective = kwargs.get("objective") or kwargs.get("objective_marker")
        objective_candidates = list(kwargs.get("objective_candidates") or [])
        if not objective_candidates:
            objective_candidates = self._grizzled_no_retreat_objective_candidates(root)
        if objective is None and len(objective_candidates) == 1:
            objective = objective_candidates[0]
        if objective is None:
            logger.error("ERROR: NO RETREAT!: no objective marker selected")
            return False
        if objective_candidates and objective not in objective_candidates:
            logger.error("ERROR: NO RETREAT!: selected objective marker is not eligible")
            return False
        loc = getattr(objective, "location", None)
        if loc is None:
            logger.error("ERROR: NO RETREAT!: objective has no location")
            return False
        if not self._am_spend_cp(stratagem, target_unit=root):
            return False
        setter = getattr(loc, "set_sticky_control", None)
        if callable(setter):
            setter(self.player, source="no_retreat")
        else:
            loc.sticky_controller = self.player
            loc.sticky_source = "no_retreat"
            loc.controlling_player = self.player
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: NO RETREAT!: objective remains under your control until opponent control breaks sticky hold.")
        return True

    def _use_grizzled_snap_to_it(self, stratagem: Any, **kwargs) -> bool:
        if not self._is_grizzled_company():
            return False
        phase_name = str(kwargs.get("phase_name") or self._current_phase_name or "").strip()
        if not phase_name:
            logger.error("ERROR: SNAP TO IT: phase context missing")
            return False

        officer = (
            kwargs.get("officer_unit")
            or kwargs.get("officer")
            or kwargs.get("unit")
            or kwargs.get("target_unit")
        )
        target_unit = (
            kwargs.get("order_target_unit")
            or kwargs.get("order_target")
            or kwargs.get("target_unit")
        )
        order_key = str(kwargs.get("order_key") or kwargs.get("order") or "").strip().upper()

        officer_candidates = self._grizzled_snap_to_it_officer_candidates(phase_name=phase_name)
        if not officer_candidates:
            logger.error("ERROR: SNAP TO IT: no eligible OFFICER can issue Orders")
            return False

        get_army = getattr(self.player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(self.player, "army", None)
        voice = getattr(army, "voice_of_command", None) if army is not None else None
        if voice is None:
            logger.error("ERROR: SNAP TO IT: Voice of Command manager unavailable")
            return False

        if officer is not None and target_unit is not None and order_key:
            officer_root = self._am_root(officer)
            target_root = self._am_root(target_unit)
            if officer_root is None or target_root is None:
                logger.error("ERROR: SNAP TO IT: invalid officer or target")
                return False
            if officer_root not in officer_candidates:
                logger.error("ERROR: SNAP TO IT: selected officer is not eligible")
                return False
            target_getter = getattr(voice, "get_eligible_targets", None)
            if callable(target_getter):
                eligible_targets = list(target_getter(officer_root, game=self.game, order_key=order_key) or [])
                if target_root not in eligible_targets:
                    logger.error("ERROR: SNAP TO IT: selected target is not eligible for the chosen Order")
                    return False
            if not self._am_spend_cp(stratagem, target_unit=officer_root):
                return False
            ok = bool(voice.issue_order(self.game, officer_root, target_root, order_key, phase_name=phase_name))
            if not ok:
                logger.error("ERROR: SNAP TO IT: failed to issue selected Order")
                return False
            self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
            logger.info(
                f"INFO: SNAP TO IT: {getattr(officer_root, 'name', 'Officer')} issued {order_key} to {getattr(target_root, 'name', 'Unit')}."
            )
            return True

        if not bool(getattr(self.player, "has_control", lambda: False)()):
            logger.error("ERROR: SNAP TO IT: remote controllers must provide officer_unit, order_key and order_target_unit")
            return False
        if not self._am_has_voice_prompt_subscriber():
            logger.error("ERROR: SNAP TO IT: no Voice of Command prompt subscriber available")
            return False
        if not self._am_spend_cp(stratagem, target_unit=officer_candidates[0]):
            return False
        event_system = getattr(self.game, "event_system", None) if self.game is not None else None
        event_system.publish(
            "voice_of_command_prompt",
            player=self.player,
            game=self.game,
            phase_name=str(phase_name or "").strip().upper(),
            trigger="snap_to_it",
        )
        self._am_finalize_use(stratagem, dequeue=kwargs.get("dequeue") is True)
        logger.info("INFO: SNAP TO IT: resolve one Voice of Command order now.")
        return True
