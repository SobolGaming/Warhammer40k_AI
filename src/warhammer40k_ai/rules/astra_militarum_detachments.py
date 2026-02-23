from __future__ import annotations

from typing import Any

from .detachment_manager import DetachmentManagerBase


class AstraMilitarumDetachmentManager(DetachmentManagerBase):
    faction_id = "AM"

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def is_bridgehead_strike(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Bridgehead Strike")

    def is_grizzled_company(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Grizzled Company")

    def _unit_root(self, unit):
        if unit is None:
            return None
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
            if root is not None:
                return root
        return unit

    def _unit_in_army(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        army = self.army
        if army is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        if callable(get_parent_army):
            parent = get_parent_army()
            if parent is not None:
                return parent is army
        return root in list(getattr(army, "units", []) or [])

    @staticmethod
    def _model_has_keyword(model, keyword: str) -> bool:
        if model is None:
            return False
        kw = str(keyword or "").strip()
        if not kw:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            return bool(has_any(kw))
        raw = [str(k or "") for k in (getattr(model, "keywords", []) or [])]
        raw += [str(k or "") for k in (getattr(model, "faction_keywords", []) or [])]
        return kw.lower() in {k.lower() for k in raw if str(k).strip()}

    def _model_or_unit_has_keyword(self, model, unit, keyword: str) -> bool:
        root = self._unit_root(unit)
        if self._model_has_keyword(model, keyword):
            return True
        return self._unit_has_keyword(root, keyword)

    def _attached_unit_was_set_up_this_turn(self, unit, *, game=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False

        was_set_up = getattr(root, "_was_set_up_this_turn", None)
        if callable(was_set_up):
            return bool(was_set_up(game=game))

        if bool(getattr(root, "arrived_from_reserves_this_turn", False)):
            return True

        round_state = getattr(root, "round_state", None)
        if bool(getattr(round_state, "reinforced_this_round", False)):
            return True

        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game_obj = getattr(player, "game", None) if player is not None else None
        if game_obj is None:
            return False

        turn_now = self._safe_int(getattr(game_obj, "turn", 0) or 0, 0)
        reserve_turn = self._safe_int(getattr(root, "reserve_turn_deployed", 0) or 0, 0)
        return bool(turn_now > 0 and reserve_turn == turn_now)

    def _attached_unit_disembarked_from_transport_this_round(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        if round_state is None:
            return False
        if not bool(getattr(round_state, "disembarked_this_round", False)):
            return False
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "").strip()
        return bool(transport_id)

    def _unit_is_astra_militarum_infantry_model(self, unit, model) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self.unit_is_astra_militarum(root):
            return False
        return self._model_or_unit_has_keyword(model, root, "INFANTRY")

    def _unit_is_militarum_tempestus_model(self, unit, model) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self.unit_is_astra_militarum(root):
            return False
        return self._model_or_unit_has_keyword(model, root, "MILITARUM TEMPESTUS")

    def unit_is_astra_militarum(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "ASTRA MILITARUM"):
            return True
        has_keywords = bool(getattr(unit, "keywords", None)) or bool(getattr(unit, "faction_keywords", None))
        if has_keywords:
            return False
        return self._army_faction_matches(self.faction_id)

    def unit_is_officer(self, unit) -> bool:
        return self._unit_has_keyword(unit, "OFFICER")

    def _unit_has_order(self, unit) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict) and str(sr.get("voice_of_command_order_key", "") or "").strip():
            return True
        return False

    def _attached_unit_has_order(self, unit) -> bool:
        if unit is None:
            return False
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
        members = None
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            members = list(get_members() or [])
        if not members:
            members = [root]
        for member in members:
            if self._unit_has_order(member):
                return True
        return False

    def ruthless_discipline_orders_bonus(self, unit) -> int:
        if not self.is_grizzled_company():
            return 0
        if unit is None:
            return 0
        if not self.unit_is_astra_militarum(unit):
            return 0
        if not self.unit_is_officer(unit):
            return 0
        return 1

    def ruthless_discipline_reroll_hit_ones(self, unit) -> bool:
        if not self.is_grizzled_company():
            return False
        if unit is None:
            return False
        if not self.unit_is_astra_militarum(unit):
            return False
        return self._attached_unit_has_order(unit)

    def only_the_best_hit_reroll_mods(
        self,
        attacker_model,
        target_unit=None,
        *,
        attack_type: str = "any",
        game=None,
        game_map=None,
        target_visible=None,
    ) -> dict:
        _ = target_unit
        _ = game
        _ = game_map
        _ = target_visible
        if not self.is_bridgehead_strike():
            return {}
        if str(attack_type or "any").strip().lower() != "ranged":
            return {}
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return {}
        if not self._unit_in_army(root):
            return {}
        if not self._unit_is_astra_militarum_infantry_model(root, attacker_model):
            return {}
        return {
            "reroll_values": (1,),
            "reroll_reasons": ("Only the Best: re-roll Hit roll of 1",),
        }

    def fire_zone_purge_hit_bonus(
        self,
        attacker_model,
        *,
        attack_type: str = "any",
        game=None,
    ) -> tuple[int, str]:
        if not self.is_bridgehead_strike():
            return 0, ""
        if str(attack_type or "any").strip().lower() != "ranged":
            return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(unit)
        if root is None:
            return 0, ""
        if not self._unit_in_army(root):
            return 0, ""
        if not self._unit_is_militarum_tempestus_model(root, attacker_model):
            return 0, ""
        set_up = self._attached_unit_was_set_up_this_turn(root, game=game)
        disembarked = self._attached_unit_disembarked_from_transport_this_round(root)
        if not (set_up or disembarked):
            return 0, ""
        return 1, "Fire Zone Purge"
