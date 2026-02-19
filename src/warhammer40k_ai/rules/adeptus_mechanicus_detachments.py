from __future__ import annotations

from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class AdeptusMechanicusDetachmentManager(DetachmentManagerBase):
    faction_id = "ADM"

    _RAD_BOMBARDMENT_ABILITY_KEY = "rad_bombardment"
    _RAD_BOMBARDMENT_CHOICE_KEY = "rad_bombardment_choice"
    _RAD_BOMBARDMENT_TAKING_COVER_ROUND_KEY = "rad_bombardment_taking_cover_round"
    _RAD_BOMBARDMENT_TAKING_COVER_ADDED_KEY = "rad_bombardment_taking_cover_added_battleshock"
    _RAD_BOMBARDMENT_CHOICE_STAND_FIRM = "stand_firm"
    _RAD_BOMBARDMENT_CHOICE_TAKE_COVER = "take_cover"

    def is_rad_zone_corps(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Rad-Zone Corps")

    @staticmethod
    def _entity_id(entity) -> str:
        value = get_entity_id(entity)
        return str(value or "")

    @staticmethod
    def _attached_root(unit):
        if unit is None:
            return None
        getter = getattr(unit, "get_attached_unit_root", None)
        if callable(getter):
            root = getter()
            if root is not None:
                return root
        return unit

    @staticmethod
    def _is_model_alive(model) -> bool:
        alive_attr = getattr(model, "is_alive", True)
        return bool(alive_attr() if callable(alive_attr) else alive_attr)

    def _iter_unit_models(self, unit) -> list:
        if unit is None:
            return []
        get_models = getattr(unit, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = list(getattr(unit, "models", []) or [])
        return [model for model in models if model is not None and self._is_model_alive(model)]

    def _iter_player_unit_roots(self, player) -> list:
        if player is None:
            return []
        get_army = getattr(player, "get_army", None)
        army = get_army() if callable(get_army) else getattr(player, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        roots: list = []
        for unit in list(getattr(army, "units", []) or []):
            root = self._attached_root(unit)
            if root is None:
                continue
            root_id = self._entity_id(root) or str(id(root))
            if root_id in seen:
                continue
            seen.add(root_id)
            roots.append(root)
        roots.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))
        return roots

    def _unit_is_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        if getattr(unit, "embarked_in", None) is not None:
            return False
        return True

    def unit_within_player_deployment_zone(self, unit, player_id: str, *, game=None) -> bool:
        if unit is None or not player_id:
            return False
        if game is None:
            owner = getattr(self.army, "player", None)
            game = getattr(owner, "game", None) if owner is not None else None
        if game is None:
            return False
        in_zone = getattr(game, "is_position_in_deployment_zone", None)
        if not callable(in_zone):
            return False
        for model in self._iter_unit_models(unit):
            location = model.get_location()
            if not location or len(location) < 2:
                continue
            if in_zone(float(location[0]), float(location[1]), str(player_id)):
                return True
        return False

    def _opponent_player(self, game):
        if game is None:
            return None
        owner = getattr(self.army, "player", None)
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is owner:
                continue
            return player
        return None

    def _enemy_units_in_player_deployment_zone(self, game, *, enemy_player) -> list:
        if game is None or enemy_player is None:
            return []
        enemy_id = str(getattr(enemy_player, "id", "") or "")
        if not enemy_id:
            return []
        eligible: list = []
        for root in self._iter_player_unit_roots(enemy_player):
            if not self._unit_is_on_battlefield(root):
                continue
            if not self.unit_within_player_deployment_zone(root, enemy_id, game=game):
                continue
            eligible.append(root)
        eligible.sort(key=lambda item: self._entity_id(item) or str(getattr(item, "name", "") or ""))
        return eligible

    def _pending_rad_bombardment_request(self, game, *, target_unit, battle_round: int):
        if game is None or target_unit is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        target_id = self._entity_id(target_unit)
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "")) != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._RAD_BOMBARDMENT_ABILITY_KEY:
                continue
            if str(ctx.get("target_unit_id", "") or "") != target_id:
                continue
            if int(ctx.get("battle_round", 0) or 0) != int(battle_round):
                continue
            return req
        return None

    def _build_rad_bombardment_request(self, game, *, target_unit, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        opponent = self._opponent_player(game)
        if opponent is None or target_unit is None:
            return None
        target_id = self._entity_id(target_unit)
        source_army_id = self._entity_id(self.army)
        options = [
            DecisionOption.create(
                "Stand Firm",
                payload={
                    "army_id": source_army_id,
                    "target_unit_id": target_id,
                    self._RAD_BOMBARDMENT_CHOICE_KEY: self._RAD_BOMBARDMENT_CHOICE_STAND_FIRM,
                },
            ),
            DecisionOption.create(
                "Take Cover",
                payload={
                    "army_id": source_army_id,
                    "target_unit_id": target_id,
                    self._RAD_BOMBARDMENT_CHOICE_KEY: self._RAD_BOMBARDMENT_CHOICE_TAKE_COVER,
                },
            ),
        ]
        prompt = (
            f"Rad-bombardment: choose how {getattr(target_unit, 'name', 'this unit')} responds "
            "in your deployment zone."
        )
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            prompt,
            player_id=getattr(opponent, "id", None),
            options=options,
            context={
                "ability": self._RAD_BOMBARDMENT_ABILITY_KEY,
                "ability_name": "Rad-bombardment",
                "army_id": source_army_id,
                "target_unit_id": target_id,
                "battle_round": int(battle_round),
            },
        )

    def _queue_rad_bombardment_requests(self, game, *, battle_round: int) -> None:
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        opponent = self._opponent_player(game)
        if opponent is None:
            return
        targets = self._enemy_units_in_player_deployment_zone(game, enemy_player=opponent)
        request_decision = getattr(game, "request_decision", None)
        if not callable(request_decision):
            return
        for target in targets:
            if self._pending_rad_bombardment_request(game, target_unit=target, battle_round=int(battle_round)) is not None:
                continue
            request = self._build_rad_bombardment_request(game, target_unit=target, battle_round=int(battle_round))
            if request is not None:
                request_decision(request)

    def _clear_expired_taking_cover_state(self, game, *, battle_round: int) -> None:
        if game is None or int(battle_round or 0) <= 1:
            return
        owner = getattr(self.army, "player", None)
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is owner:
                continue
            for unit in self._iter_player_unit_roots(player):
                special_rules = getattr(unit, "special_rules", None)
                if not isinstance(special_rules, dict):
                    continue
                applied_round = int(special_rules.get(self._RAD_BOMBARDMENT_TAKING_COVER_ROUND_KEY, 0) or 0)
                if applied_round <= 0 or applied_round >= int(battle_round):
                    continue
                added_battleshock = bool(special_rules.get(self._RAD_BOMBARDMENT_TAKING_COVER_ADDED_KEY, False))
                special_rules = dict(special_rules)
                special_rules.pop(self._RAD_BOMBARDMENT_TAKING_COVER_ROUND_KEY, None)
                special_rules.pop(self._RAD_BOMBARDMENT_TAKING_COVER_ADDED_KEY, None)
                unit.special_rules = special_rules
                if added_battleshock:
                    clear_battleshock = getattr(unit, "clear_battle_shock", None)
                    if callable(clear_battleshock):
                        clear_battleshock()

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self.is_rad_zone_corps():
            return
        if game is None:
            owner = getattr(self.army, "player", None)
            game = getattr(owner, "game", None) if owner is not None else None
        br = int(battle_round or 0)
        self._clear_expired_taking_cover_state(game, battle_round=br)
        if br != 1:
            return
        self._queue_rad_bombardment_requests(game, battle_round=br)

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if not self.is_rad_zone_corps():
            return
        if game is None or player is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        battle_round = int(getattr(game, "turn", 0) or 0)
        if battle_round < 2 or battle_round > 5:
            return
        opponent = self._opponent_player(game)
        if opponent is None:
            return
        targets = self._enemy_units_in_player_deployment_zone(game, enemy_player=opponent)
        for target in targets:
            roll = int(get_roll("D6") or 0)
            if roll < 3:
                continue
            apply_mortal_wounds = getattr(target, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal_wounds):
                apply_mortal_wounds(target, 1, game_map=getattr(game, "map", None))
            take_battle_shock_test = getattr(target, "take_battle_shock_test", None)
            if callable(take_battle_shock_test):
                take_battle_shock_test(int(battle_round))
