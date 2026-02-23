from __future__ import annotations

from typing import Iterable, Optional

from ..utility import aura_utils
from ..utility.entity_ids import maybe_entity_id
from .detachment_manager import DetachmentManagerBase


class AdeptusCustodesDetachmentManager(DetachmentManagerBase):
    faction_id = "AC"

    _AGAINST_ALL_ODDS_RANGE = 6.0
    _ASSEMBLAGE_OF_MIGHT_SOURCE = "Assemblage of Might"

    def __init__(self, army=None):
        super().__init__(army=army)
        self.assemblage_of_might_target_unit_id: str = ""
        self.assemblage_of_might_target_name: str = ""

    def is_lions_of_the_emperor(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Lions of the Emperor")

    def is_auric_champions(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Auric Champions")

    def _model_in_army(self, model) -> bool:
        if model is None or self.army is None:
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None or not hasattr(unit, "get_parent_army"):
            return False
        return unit.get_parent_army() is self.army

    def _model_is_custodes(self, model) -> bool:
        if model is None:
            return False
        unit = getattr(model, "parent_unit", None)
        return self._unit_has_keyword_or_faction(unit, "ADEPTUS CUSTODES", faction_id=self.faction_id)

    def _unit_is_vehicle(self, unit) -> bool:
        if unit is None:
            return False
        if bool(getattr(unit, "is_vehicle", False)):
            return True
        return self._unit_has_keyword(unit, "VEHICLE")

    def _root_unit(self, unit):
        if unit is None:
            return None
        if hasattr(unit, "get_attached_unit_root"):
            return unit.get_attached_unit_root()
        return unit

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        get_parent_army = getattr(unit, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _unit_is_character_unit(self, unit) -> bool:
        root = self._root_unit(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, "CHARACTER"):
            return True
        members = []
        get_members = getattr(root, "get_attached_unit_members", None)
        if callable(get_members):
            members = list(get_members() or [])
        if not members:
            members = [root] + list(getattr(root, "attached_leaders", []) or [])
        for member in list(members or []):
            if member is None:
                continue
            if self._unit_has_keyword(member, "CHARACTER"):
                return True
        return False

    def _unit_key(self, unit) -> Optional[str]:
        if unit is None:
            return None
        return maybe_entity_id(unit) or str(id(unit))

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

    def _iter_unique_friendly_roots(self, unit, game_map) -> Iterable:
        if unit is None or game_map is None or not hasattr(game_map, "get_friendly_units"):
            return ()
        source_root = self._root_unit(unit)
        source_key = self._unit_key(source_root)
        seen = {source_key} if source_key else set()
        for friendly in list(game_map.get_friendly_units(source_root) or []):
            root = self._root_unit(friendly)
            if root is source_root:
                continue
            key = self._unit_key(root)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            if root is not None:
                yield root

    def _has_other_friendly_within_range(self, unit, *, radius: float, game_map) -> bool:
        source_root = self._root_unit(unit)
        if source_root is None or game_map is None:
            return False
        for other_root in self._iter_unique_friendly_roots(source_root, game_map):
            if aura_utils.unit_within_range_of_unit(
                source_root,
                other_root,
                radius,
                use_attached_aggregate=True,
            ):
                return True
        return False

    def against_all_odds_applies(self, model, target_unit=None, *, game=None, game_map=None) -> bool:
        if not self.is_lions_of_the_emperor():
            return False
        if model is None:
            return False
        if not self._model_in_army(model):
            return False
        if not self._model_is_custodes(model):
            return False
        unit = getattr(model, "parent_unit", None)
        if unit is None or self._unit_is_vehicle(unit):
            return False
        resolved_map = self._resolve_game_map(game=game, game_map=game_map)
        if resolved_map is None:
            return False
        return not self._has_other_friendly_within_range(
            unit,
            radius=self._AGAINST_ALL_ODDS_RANGE,
            game_map=resolved_map,
        )

    def against_all_odds_hit_bonus(self, model, target_unit=None, *, game=None, game_map=None) -> int:
        if not self.against_all_odds_applies(model, target_unit, game=game, game_map=game_map):
            return 0
        return 1

    def against_all_odds_wound_bonus(self, model, target_unit=None, *, game=None, game_map=None) -> int:
        if not self.against_all_odds_applies(model, target_unit, game=game, game_map=game_map):
            return 0
        return 1

    def clear_assemblage_of_might_target(self) -> None:
        self.assemblage_of_might_target_unit_id = ""
        self.assemblage_of_might_target_name = ""
        if self.army is not None:
            setattr(self.army, "assemblage_of_might_target_unit_id", "")
            setattr(self.army, "assemblage_of_might_target_name", "")

    def set_assemblage_of_might_target(self, target_unit) -> bool:
        if target_unit is None:
            return False
        root = self._root_unit(target_unit)
        if root is None:
            return False
        rid = str(maybe_entity_id(root) or "").strip()
        if not rid:
            return False
        self.assemblage_of_might_target_unit_id = rid
        self.assemblage_of_might_target_name = str(getattr(root, "name", "") or "")
        if self.army is not None:
            setattr(self.army, "assemblage_of_might_target_unit_id", self.assemblage_of_might_target_unit_id)
            setattr(self.army, "assemblage_of_might_target_name", self.assemblage_of_might_target_name)
        return True

    def is_assemblage_of_might_target(self, target_unit) -> bool:
        if target_unit is None:
            return False
        target_id = str(self.assemblage_of_might_target_unit_id or "").strip()
        if not target_id:
            return False
        root = self._root_unit(target_unit)
        if root is None:
            return False
        rid = str(maybe_entity_id(root) or "").strip()
        return bool(rid) and rid == target_id

    def _assemblage_of_might_attacker_eligible(self, attacker_model) -> bool:
        if not self.is_auric_champions():
            return False
        if attacker_model is None:
            return False
        if not self._model_in_army(attacker_model):
            return False
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root = self._root_unit(attacker_unit)
        if root is None:
            return False
        if not self._unit_has_keyword_or_faction(root, "ADEPTUS CUSTODES", faction_id=self.faction_id):
            return False
        return self._unit_is_character_unit(root)

    def assemblage_of_might_wound_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        game=None,
        weapon_profile=None,
        attack_instance=None,
    ) -> int:
        del game
        del weapon_profile
        del attack_instance
        if not self._assemblage_of_might_attacker_eligible(attacker_model):
            return 0
        if not self.is_assemblage_of_might_target(target_unit):
            return 0
        return 1

    def _assemblage_of_might_eligible_enemy_units(self, *, game=None, player=None) -> list:
        if not self.is_auric_champions():
            return []
        if game is None or player is None:
            return []
        get_enemy_units = getattr(game, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        enemy_units = list(get_enemy_units(player) or [])
        if not enemy_units:
            return []

        out: list = []
        seen: set[str] = set()
        for enemy in enemy_units:
            root = self._root_unit(enemy)
            if root is None:
                continue
            rid = str(maybe_entity_id(root) or "").strip()
            if not rid or rid in seen:
                continue
            seen.add(rid)
            is_alive = getattr(root, "is_alive", None)
            if callable(is_alive) and not bool(is_alive()):
                continue
            if not bool(getattr(root, "deployed", True)):
                continue
            reserve_status = str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower()
            if reserve_status != "deployed":
                continue
            if bool(getattr(root, "embarked_in", None)) or bool(getattr(root, "is_embarked", False)):
                continue
            out.append(root)
        out.sort(key=lambda unit: str(maybe_entity_id(unit) or id(unit)))
        return out

    def _pending_assemblage_of_might_request(self, *, game=None, army_id: str = "", command_phase_owner_id: str = "") -> bool:
        queue = getattr(game, "decision_queue", None) if game is not None else None
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "assemblage_of_might":
                continue
            if army_id and str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            if command_phase_owner_id and str(ctx.get("command_phase_owner_id", "") or "") != str(command_phase_owner_id):
                continue
            return True
        return False

    def build_assemblage_of_might_request(self, *, game=None, player=None):
        if not self.is_auric_champions():
            return None
        if game is None or player is None:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        targets = self._assemblage_of_might_eligible_enemy_units(game=game, player=player)
        if not targets:
            return None

        army_id = str(maybe_entity_id(self.army) or "") if self.army is not None else ""
        player_id = str(getattr(player, "id", "") or "")
        if self._pending_assemblage_of_might_request(
            game=game,
            army_id=army_id,
            command_phase_owner_id=player_id,
        ):
            return None

        options = []
        for target in targets:
            target_id = str(maybe_entity_id(target) or "").strip()
            if not target_id:
                continue
            options.append(
                DecisionOption.create(
                    str(getattr(target, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": target_id},
                )
            )
        if not options:
            return None

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Assemblage of Might: select one enemy unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "assemblage_of_might",
                "ability_name": self._ASSEMBLAGE_OF_MIGHT_SOURCE,
                "army_id": army_id,
                "command_phase_owner_id": player_id,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        self.clear_assemblage_of_might_target()
        if self.army is None or player is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        self.build_assemblage_of_might_request(game=game, player=player)
