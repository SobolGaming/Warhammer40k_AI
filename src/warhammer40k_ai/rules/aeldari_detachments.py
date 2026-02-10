from __future__ import annotations

from .detachment_manager import DetachmentManagerBase


class AeldariDetachmentManager(DetachmentManagerBase):
    faction_id = "AE"
    _DEFEND_AT_ALL_COSTS_MODEL_KEYWORDS = (
        "DIRE AVENGERS",
        "DIRE AVENGER",
        "GUARDIANS",
        "GUARDIAN",
        "SUPPORT WEAPON",
        "WAR WALKERS",
        "WAR WALKER",
    )
    _DEFEND_AT_ALL_COSTS_MODEL_NAME_SNIPPETS = (
        "dire avenger",
        "guardian",
        "support weapon",
        "war walker",
    )

    def is_warhost_detachment(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Warhost")

    def is_armoured_warhost(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Armoured Warhost")

    def is_aspect_host(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Aspect Host")

    def is_devoted_of_ynnead(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Devoted of Ynnead")

    def is_ghosts_of_the_webway(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Ghosts of the Webway")

    def is_guardian_battlehost(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Guardian Battlehost")

    def is_seer_council(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Seer Council")

    def is_serpents_brood(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Serpent's Brood")

    def is_spirit_conclave(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Spirit Conclave")

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        try:
            return unit.get_parent_army() is self.army
        except Exception:
            return False

    def _unit_is_aeldari_vehicle(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "AELDARI") and self._unit_has_keyword(unit, "VEHICLE")

    def _unit_is_aeldari_vehicle_fly(self, unit) -> bool:
        if unit is None:
            return False
        return (
            self._unit_has_keyword(unit, "AELDARI")
            and self._unit_has_keyword(unit, "VEHICLE")
            and self._unit_has_keyword(unit, "FLY")
        )

    def _unit_is_aspect_warriors(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "ASPECT WARRIORS")

    def _unit_is_avatar_of_khaine(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "AVATAR OF KHAINE")

    def skilled_crews_assault_applies(self, unit) -> bool:
        if not self.is_armoured_warhost():
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_is_aeldari_vehicle(unit)

    def skilled_crews_reroll_advance_applies(self, unit) -> bool:
        if not self.is_armoured_warhost():
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_is_aeldari_vehicle_fly(unit)

    def path_of_the_warrior_applies(self, unit) -> bool:
        if not self.is_aspect_host():
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_is_aspect_warriors(unit) or self._unit_is_avatar_of_khaine(unit)

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None or not hasattr(unit, "get_parent_army"):
            return False
        return unit.get_parent_army() is self.army

    def _resolve_game_map(self, *, game=None, game_map=None):
        if game_map is not None:
            return game_map
        if game is not None:
            resolved = getattr(game, "map", None)
            if resolved is not None:
                return resolved
        player = getattr(self.army, "player", None) if self.army is not None else None
        game_obj = getattr(player, "game", None) if player is not None else None
        return getattr(game_obj, "map", None) if game_obj is not None else None

    def _model_matches_defend_at_all_costs(self, model) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            for keyword in self._DEFEND_AT_ALL_COSTS_MODEL_KEYWORDS:
                if bool(has_any(keyword)):
                    return True
        has_kw = getattr(model, "has_keyword", None)
        if callable(has_kw):
            for keyword in self._DEFEND_AT_ALL_COSTS_MODEL_KEYWORDS:
                if bool(has_kw(keyword)):
                    return True
        model_name = str(getattr(model, "name", "") or "").strip().lower()
        if model_name:
            for snippet in self._DEFEND_AT_ALL_COSTS_MODEL_NAME_SNIPPETS:
                if snippet in model_name:
                    return True
        return False

    def _unit_within_any_objective(self, unit, game_map) -> bool:
        if unit is None or game_map is None:
            return False
        objectives = list(getattr(game_map, "objectives", []) or [])
        if not objectives:
            return False
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None:
                loc = obj
            if loc is None:
                continue
            if bool(getattr(loc, "removed", False)):
                continue
            within_fn = getattr(unit, "is_within_objective_range", None)
            if callable(within_fn) and bool(within_fn(loc)):
                return True
        return False

    def defend_at_all_costs_hit_bonus(self, model, attacker_unit, target_unit, *, game=None, game_map=None) -> tuple[int, str]:
        if not self.is_guardian_battlehost():
            return 0, ""
        if model is None or attacker_unit is None or target_unit is None:
            return 0, ""
        if not self._unit_in_army(attacker_unit):
            return 0, ""
        if not self._model_in_army(model):
            return 0, ""
        if not self._model_matches_defend_at_all_costs(model):
            return 0, ""
        resolved_map = self._resolve_game_map(game=game, game_map=game_map)
        if resolved_map is None:
            return 0, ""
        attacker_within_objective = self._unit_within_any_objective(attacker_unit, resolved_map)
        target_within_objective = self._unit_within_any_objective(target_unit, resolved_map)
        if attacker_within_objective or target_within_objective:
            return 1, "Defend at All Costs (+1 to hit near objectives)"
        return 0, ""
