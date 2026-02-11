from __future__ import annotations

from typing import Any, Optional

import logging

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

    def _use_astra_militarum_grizzled_stratagem(self, stratagem: Any, **kwargs) -> Optional[bool]:
        name_u = str(getattr(stratagem, "name", "") or "").strip().upper()
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
