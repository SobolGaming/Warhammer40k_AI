from __future__ import annotations

import re
from typing import Optional

from ..utility.aura_utils import model_within_range_of_unit
from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class ImperialAgentsDetachmentManager(DetachmentManagerBase):
    faction_id = "AOI"
    _IMPERIALIS_FLEET_DETACHMENT_NAME = "Imperialis Fleet"
    _AT_ALL_COSTS_NAME = "At all Costs"
    _AT_ALL_COSTS_ABILITY_KEY = "imperialis_fleet_at_all_costs"
    _AT_ALL_COSTS_MODE_ELIMINATE = "eliminate"
    _AT_ALL_COSTS_MODE_ACQUIRE = "acquire"
    _CLANDESTINE_OPERATION_NAME = "Clandestine Operation"
    _CLANDESTINE_OPERATION_ABILITY_KEY = "imperialis_fleet_clandestine_operation_selection"
    _COMBAT_LANDERS_NAME = "Combat Landers"
    _COMBAT_LANDERS_ABILITY_KEY = "imperialis_fleet_combat_landers_selection"
    _DIGITAL_WEAPONS_NAME = "Digital Weapons"
    _DIGITAL_WEAPONS_ABILITY_KEY = "imperialis_fleet_digital_weapons"
    _ORDO_HERETICUS_PURGATION_FORCE_DETACHMENT_NAME = "Ordo Hereticus Purgation Force"
    _ROOT_OUT_HERESY_NAME = "Root out Heresy"
    _WITCH_HUNTER_NAME = "Witch Hunter"
    _ROOT_OUT_HERESY_MODEL_KEYWORDS = (
        "ADEPTUS ARBITES",
        "INQUISITOR",
        "INQUISITORIAL AGENTS",
        "ORDO HERETICUS",
    )
    _ORDO_MALLEUS_DAEMON_HUNTERS_DETACHMENT_NAME = "Ordo Malleus Daemon Hunters"
    _DESTROY_THE_DAEMONIC_NAME = "Destroy the Daemonic"
    _GRIMOIRE_OF_TRUE_NAMES_AURA_NAME = "Grimoire of True Names (Aura)"
    _DESTROY_THE_DAEMONIC_MODEL_KEYWORDS = (
        "INQUISITOR",
        "INQUISITORIAL AGENTS",
        "ORDO MALLEUS",
    )
    _ORDO_XENOS_ALIEN_HUNTERS_DETACHMENT_NAME = "Ordo Xenos Alien Hunters"
    _DEATHWATCH_MISSION_TACTICS_NAME = "Deathwatch Mission Tactics"
    _DEATHWATCH_MISSION_TACTICS_ABILITY_KEY = "ordo_xenos_deathwatch_mission_tactics"
    _DEATHWATCH_MISSION_TACTIC_FUROR = "FUROR_TACTICS"
    _DEATHWATCH_MISSION_TACTIC_MALLEUS = "MALLEUS_TACTICS"
    _DEATHWATCH_MISSION_TACTIC_PURGATUS = "PURGATUS_TACTICS"
    _DEATHWATCH_MISSION_TACTIC_KEYS = (
        _DEATHWATCH_MISSION_TACTIC_FUROR,
        _DEATHWATCH_MISSION_TACTIC_MALLEUS,
        _DEATHWATCH_MISSION_TACTIC_PURGATUS,
    )
    _DEATHWATCH_MISSION_TACTIC_LABELS = {
        _DEATHWATCH_MISSION_TACTIC_FUROR: "Furor Tactics",
        _DEATHWATCH_MISSION_TACTIC_MALLEUS: "Malleus Tactics",
        _DEATHWATCH_MISSION_TACTIC_PURGATUS: "Purgatus Tactics",
    }
    _EXTREMIS_DETACHMENT_NAME = "Veiled Blade Elimination Force"
    _EXTREMIS_SURCHARGE_BY_UNIT_NAME = {
        "callidus assassin": 40,
        "culexus assassin": 40,
        "eversor assassin": 35,
        "vindicare assassin": 45,
    }
    _EXTREMIS_EXTRA_USE_KEY_BY_ABILITY_NAME = {
        "overkill": "movement_phase_normal_move_bonus:overkill",
        "soulless horror": "soulless_horror",
        "shieldbreaker": "shieldbreaker",
    }

    def __init__(self, army=None):
        super().__init__(army)
        self.at_all_costs_selected_round: int = 0
        self.at_all_costs_selected_owner_id: str = ""
        self.at_all_costs_active_mode: str = ""
        self.at_all_costs_target_unit_id: str = ""
        self.at_all_costs_target_objective_id: str = ""
        self.deathwatch_mission_tactics_selected_keys: tuple[str, ...] = ()
        self.deathwatch_mission_tactics_active_key: str = ""
        self.deathwatch_mission_tactics_active_round: int = 0
        self.deathwatch_mission_tactics_last_selection_round: int = 0

    @staticmethod
    def _normalize_name(value: str) -> str:
        text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _entity_id(entity) -> str:
        return str(get_entity_id(entity) or "")

    @staticmethod
    def _coerce_int(value, *, default: int = 0) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if re.fullmatch(r"[+-]?\d+", text):
                return int(text)
        return int(default)

    @staticmethod
    def _phase_key(value) -> str:
        return str(value or "").strip().upper()

    def _current_game(self):
        player = getattr(self.army, "player", None) if self.army is not None else None
        return getattr(player, "game", None) if player is not None else None

    @staticmethod
    def _player_id(player) -> str:
        return str(getattr(player, "id", "") or "")

    def _current_player_id(self, *, game=None) -> str:
        game_obj = game if game is not None else self._current_game()
        if game_obj is None:
            return ""
        current_player = getattr(game_obj, "get_current_player", lambda: None)()
        return self._player_id(current_player)

    @staticmethod
    def _weapon_profile_is_ranged(profile) -> bool:
        if profile is None:
            return False
        parent_wargear = getattr(profile, "parent_wargear", None)
        is_ranged = getattr(parent_wargear, "is_ranged", None) if parent_wargear is not None else None
        return bool(is_ranged()) if callable(is_ranged) else False

    def is_imperialis_fleet(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._IMPERIALIS_FLEET_DETACHMENT_NAME)

    def is_ordo_hereticus_purgation_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._ORDO_HERETICUS_PURGATION_FORCE_DETACHMENT_NAME)

    def is_ordo_malleus_daemon_hunters(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._ORDO_MALLEUS_DAEMON_HUNTERS_DETACHMENT_NAME)

    def is_ordo_xenos_alien_hunters(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._ORDO_XENOS_ALIEN_HUNTERS_DETACHMENT_NAME)

    def is_veiled_blade_elimination_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self._EXTREMIS_DETACHMENT_NAME)

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
        if root is None or self.army is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        return get_parent_army() is self.army

    def _model_in_army(self, model) -> bool:
        if model is None:
            return False
        return self._unit_in_army(getattr(model, "parent_unit", None))

    def _unit_on_battlefield(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        if not bool(getattr(root, "deployed", True)):
            return False
        if bool(getattr(root, "is_embarked", False)) or getattr(root, "embarked_in", None) is not None:
            return False
        is_in_reserves = getattr(root, "is_in_reserves", None)
        if callable(is_in_reserves) and bool(is_in_reserves()):
            return False
        return True

    def _unit_is_enemy_of_player(self, unit, player) -> bool:
        if unit is None or player is None:
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        if not callable(get_parent_army):
            return False
        army = get_parent_army()
        source_army = getattr(player, "army", None)
        if army is None or source_army is None:
            return False
        return army is not source_army

    def _unit_is_agents_of_the_imperium(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        return self._unit_has_keyword(root, "AGENTS OF THE IMPERIUM")

    def _unit_has_any_keyword(self, unit, keywords: tuple[str, ...]) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        for keyword in list(keywords or ()):
            if self._unit_has_keyword(root, str(keyword)):
                return True
        return False

    def _model_has_any_keyword(self, model, keywords: tuple[str, ...]) -> bool:
        if model is None:
            return False
        has_any = getattr(model, "has_any_keyword", None)
        if callable(has_any):
            for keyword in list(keywords or ()):
                if bool(has_any(str(keyword))):
                    return True
        source_unit = self._unit_root(getattr(model, "parent_unit", None))
        return self._unit_has_any_keyword(source_unit, keywords)

    @staticmethod
    def _enhancement_bearer_alive(unit) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "") if isinstance(sr, dict) else ""
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                if model_id != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                return bool(alive_attr() if callable(alive_attr) else alive_attr)
            return False
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            return get_bearer() is not None
        return False

    @staticmethod
    def _enhancement_bearer_model(unit):
        if unit is None:
            return None
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            bearer = get_bearer()
            if bearer is not None:
                return bearer
        sr = getattr(unit, "special_rules", None)
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "") if isinstance(sr, dict) else ""
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                model_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
                if model_id != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                if bool(alive_attr() if callable(alive_attr) else alive_attr):
                    return model
        return None

    def _unit_name_matches_any_pattern(self, unit, patterns) -> bool:
        normalized_name = self._normalize_name(str(getattr(unit, "name", "") or ""))
        if not normalized_name:
            return False
        for value in list(patterns or ()):
            pattern = self._normalize_name(str(value or ""))
            if pattern and pattern in normalized_name:
                return True
        return False

    def _unit_has_all_keywords(self, unit, keywords) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        for keyword in list(keywords or ()):
            if not self._unit_has_keyword(root, str(keyword)):
                return False
        return True

    def _unit_available_for_prebattle_selection(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        is_alive = getattr(root, "is_alive", None)
        if callable(is_alive) and not bool(is_alive()):
            return False
        return True

    def _attached_members(self, unit) -> list:
        root = self._unit_root(unit)
        if root is None:
            return []
        get_members = getattr(root, "get_attached_unit_members", None)
        members = list(get_members() or []) if callable(get_members) else [root]
        if not members:
            members = [root]
        members.sort(key=lambda member: self._entity_id(member))
        return members

    def _unit_alive_model_count(self, unit) -> int:
        root = self._unit_root(unit)
        if root is None:
            return 0
        get_attached_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_attached_models):
            models = list(get_attached_models() or [])
        else:
            models = list(getattr(root, "models", []) or [])
        count = 0
        for model in list(models or []):
            if model is None:
                continue
            if bool(getattr(model, "_pending_placement", False)):
                continue
            if bool(getattr(model, "is_alive", True)):
                count += 1
        return int(count)

    def _iter_enemy_units_on_battlefield(self, *, game=None, player=None) -> list:
        if game is None:
            return []
        enemy_units: list = []
        seen: set[str] = set()
        for candidate_player in list(getattr(game, "players", []) or []):
            if candidate_player is None:
                continue
            if player is not None and candidate_player is player:
                continue
            army = getattr(candidate_player, "army", None)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                root = self._unit_root(unit)
                if root is None:
                    continue
                root_id = self._entity_id(root)
                if not root_id or root_id in seen:
                    continue
                if not self._unit_on_battlefield(root):
                    continue
                if player is not None and not self._unit_is_enemy_of_player(root, player):
                    continue
                seen.add(root_id)
                enemy_units.append(root)
        enemy_units.sort(key=lambda unit: self._entity_id(unit))
        return enemy_units

    def _collect_objective_entries(self, *, game=None, game_map=None) -> list[tuple[str, object, object]]:
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)

        pool = []
        if game_map is not None:
            pool.extend(list(getattr(game_map, "objectives", []) or []))
        if game is not None:
            pool.extend(list(getattr(game, "objectives", []) or []))

        entries: list[tuple[str, object, object]] = []
        seen_ids: set[str] = set()
        for objective in pool:
            objective_id = self._entity_id(objective)
            if not objective_id or objective_id in seen_ids:
                continue
            location = getattr(objective, "location", None)
            if location is None or bool(getattr(location, "removed", False)):
                continue
            seen_ids.add(objective_id)
            entries.append((objective_id, objective, location))
        entries.sort(key=lambda entry: str(entry[0]))
        return entries

    def _objective_entry_by_id(self, objective_id: str, *, game=None, game_map=None):
        objective_key = str(objective_id or "").strip()
        if not objective_key:
            return None
        for entry in self._collect_objective_entries(game=game, game_map=game_map):
            if str(entry[0]) == objective_key:
                return entry
        return None

    def _imperialis_fleet_turn_effect_state(self, unit, *, prefix: str, game=None):
        if not self.is_imperialis_fleet():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(f"{prefix}_active", False)):
            return None, None
        game_obj = game if game is not None else self._current_game()
        current_turn = self._coerce_int(getattr(game_obj, "turn", 0) if game_obj is not None else 0, default=0)
        marked_turn = self._coerce_int(sr.get(f"{prefix}_turn", 0), default=0)
        if marked_turn and current_turn and marked_turn != current_turn:
            return None, None
        owner_id = str(sr.get(f"{prefix}_turn_owner", "") or "")
        current_owner_id = self._current_player_id(game=game_obj)
        if owner_id and current_owner_id and owner_id != current_owner_id:
            return None, None
        return root, sr

    def _imperialis_fleet_phase_effect_state(self, unit, *, prefix: str, game=None):
        root, sr = self._imperialis_fleet_turn_effect_state(unit, prefix=prefix, game=game)
        if root is None or not isinstance(sr, dict):
            return None, None
        game_obj = game if game is not None else self._current_game()
        current_phase = self._phase_key(getattr(getattr(game_obj, "phase", None), "name", "") if game_obj is not None else "")
        marked_phase = self._phase_key(sr.get(f"{prefix}_expires_phase", "") or "")
        if current_phase and marked_phase and current_phase != marked_phase:
            return None, None
        return root, sr

    def _ordo_hereticus_turn_effect_state(self, unit, *, prefix: str, game=None):
        if not self.is_ordo_hereticus_purgation_force():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(f"{prefix}_active", False)):
            return None, None
        game_obj = game if game is not None else self._current_game()
        current_turn = self._coerce_int(getattr(game_obj, "turn", 0) if game_obj is not None else 0, default=0)
        marked_turn = self._coerce_int(sr.get(f"{prefix}_turn", 0), default=0)
        if marked_turn and current_turn and marked_turn != current_turn:
            return None, None
        owner_id = str(sr.get(f"{prefix}_turn_owner", "") or "")
        current_owner_id = self._current_player_id(game=game_obj)
        if owner_id and current_owner_id and owner_id != current_owner_id:
            return None, None
        return root, sr

    def _ordo_hereticus_phase_effect_state(self, unit, *, prefix: str, game=None):
        root, sr = self._ordo_hereticus_turn_effect_state(unit, prefix=prefix, game=game)
        if root is None or not isinstance(sr, dict):
            return None, None
        game_obj = game if game is not None else self._current_game()
        current_phase = self._phase_key(getattr(getattr(game_obj, "phase", None), "name", "") if game_obj is not None else "")
        marked_phase = self._phase_key(sr.get(f"{prefix}_expires_phase", "") or "")
        if current_phase and marked_phase and current_phase != marked_phase:
            return None, None
        return root, sr

    def _ordo_hereticus_execution_order_state(self, unit, *, game=None):
        if not self.is_ordo_hereticus_purgation_force():
            return None, None
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return None, None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("imperial_agents_execution_order_active", False)):
            return None, None
        game_obj = game if game is not None else self._current_game()
        current_turn = self._coerce_int(getattr(game_obj, "turn", 0) if game_obj is not None else 0, default=0)
        marked_turn = self._coerce_int(sr.get("imperial_agents_execution_order_turn", 0), default=0)
        owner_id = str(sr.get("imperial_agents_execution_order_turn_owner", "") or "")
        current_owner_id = self._current_player_id(game=game_obj)
        if marked_turn and current_turn and current_turn < marked_turn:
            return None, None
        if marked_turn and current_turn and current_turn > marked_turn + 1:
            return None, None
        if owner_id and current_owner_id and marked_turn and current_turn and current_turn > marked_turn and current_owner_id == owner_id:
            return None, None
        return root, sr

    def _at_all_costs_pending_request(self, game, *, army_id: str, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "") or "") != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._AT_ALL_COSTS_ABILITY_KEY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            try:
                req_round = int(ctx.get("battle_round", 0) or 0)
            except Exception:
                req_round = 0
            if int(req_round) != int(battle_round):
                continue
            return req
        return None

    def _build_at_all_costs_request(self, game, *, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if game is None or self.army is None:
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None

        enemy_units = self._iter_enemy_units_on_battlefield(game=game, player=owner)
        objective_entries = self._collect_objective_entries(game=game)
        if not enemy_units and not objective_entries:
            return None

        options = [
            DecisionOption.create(
                "None",
                payload={
                    "action": "skip",
                    "skip": True,
                    "mode": "skip",
                    "summary": "Do not use At all Costs this Command phase.",
                },
            )
        ]
        candidate_unit_ids: list[str] = []
        for unit in list(enemy_units or []):
            unit_id = self._entity_id(unit)
            if not unit_id:
                continue
            candidate_unit_ids.append(unit_id)
            unit_name = str(getattr(unit, "name", "") or "Enemy unit")
            options.append(
                DecisionOption.create(
                    f"Eliminate: {unit_name}",
                    payload={
                        "mode": self._AT_ALL_COSTS_MODE_ELIMINATE,
                        "target_unit_id": unit_id,
                        "summary": f"Eliminate At All Costs targeting {unit_name}.",
                    },
                )
            )

        candidate_objective_ids: list[str] = []
        for idx, (objective_id, objective, location) in enumerate(objective_entries):
            candidate_objective_ids.append(str(objective_id))
            objective_name = str(getattr(objective, "name", "") or f"Objective {idx + 1}")
            label = objective_name
            try:
                label = f"{objective_name} ({float(getattr(location, 'x', 0.0)):.1f}, {float(getattr(location, 'y', 0.0)):.1f})"
            except Exception:
                label = objective_name
            options.append(
                DecisionOption.create(
                    f"Acquire: {label}",
                    payload={
                        "mode": self._AT_ALL_COSTS_MODE_ACQUIRE,
                        "objective_id": str(objective_id),
                        "summary": f"Acquire At All Costs targeting {objective_name}.",
                    },
                )
            )

        if len(options) <= 1:
            return None
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "At all Costs: select Eliminate At All Costs, Acquire At All Costs, or None.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._AT_ALL_COSTS_ABILITY_KEY,
                "ability_name": self._AT_ALL_COSTS_NAME,
                "army_id": self._entity_id(self.army),
                "battle_round": int(battle_round),
                "candidate_unit_ids": list(candidate_unit_ids),
                "candidate_objective_ids": list(candidate_objective_ids),
                "optional": True,
            },
        )

    def clear_at_all_costs_effect(self) -> None:
        self.at_all_costs_active_mode = ""
        self.at_all_costs_target_unit_id = ""
        self.at_all_costs_target_objective_id = ""

    def _queue_at_all_costs_request(self, *, game=None, player=None, battle_round: int = 0) -> None:
        if not self.is_imperialis_fleet():
            return
        if game is None or player is None or self.army is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        try:
            br = int(battle_round or getattr(game, "turn", 0) or 0)
        except Exception:
            br = int(getattr(game, "turn", 0) or 0)
        if br <= 0:
            return

        owner_id = str(getattr(player, "id", "") or "")
        if self.at_all_costs_selected_round != int(br) or self.at_all_costs_selected_owner_id != owner_id:
            self.clear_at_all_costs_effect()

        if self.at_all_costs_selected_round == int(br) and self.at_all_costs_selected_owner_id == owner_id:
            return

        army_id = self._entity_id(self.army)
        if self._at_all_costs_pending_request(game, army_id=army_id, battle_round=int(br)) is not None:
            return

        request = self._build_at_all_costs_request(game, battle_round=int(br))
        request_decision = getattr(game, "request_decision", None)
        if callable(request_decision) and request is not None:
            request_decision(request)

    def _deathwatch_mission_tactics_pending_request(self, game, *, army_id: str, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "") or "") != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != self._DEATHWATCH_MISSION_TACTICS_ABILITY_KEY:
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id or ""):
                continue
            try:
                req_round = int(ctx.get("battle_round", 0) or 0)
            except Exception:
                req_round = 0
            if int(req_round) != int(battle_round):
                continue
            return req
        return None

    def clear_active_deathwatch_mission_tactic(self) -> None:
        self.deathwatch_mission_tactics_active_key = ""
        self.deathwatch_mission_tactics_active_round = 0

    def mark_deathwatch_mission_tactics_skipped_for_round(self, *, battle_round=None) -> None:
        try:
            self.deathwatch_mission_tactics_last_selection_round = int(battle_round or 0)
        except Exception:
            self.deathwatch_mission_tactics_last_selection_round = 0

    def deathwatch_mission_tactic_label(self, key: str) -> str:
        key_norm = str(key or "").strip().upper()
        return self._DEATHWATCH_MISSION_TACTIC_LABELS.get(key_norm, key_norm)

    def get_available_deathwatch_mission_tactics(self) -> list[str]:
        selected = {str(v or "").strip().upper() for v in list(self.deathwatch_mission_tactics_selected_keys or ())}
        return [key for key in self._DEATHWATCH_MISSION_TACTIC_KEYS if key not in selected]

    def can_select_deathwatch_mission_tactic(self, *, game=None, battle_round=None) -> bool:
        if not self.is_ordo_xenos_alien_hunters():
            return False
        available = list(self.get_available_deathwatch_mission_tactics() or [])
        if not available:
            return False
        round_now = 0
        try:
            round_now = int(
                battle_round
                or getattr(game, "turn", 0)
                or getattr(getattr(self.army, "player", None), "game", None).turn
                or 0
            )
        except Exception:
            round_now = 0
        if round_now <= 0:
            return False
        return int(self.deathwatch_mission_tactics_last_selection_round or 0) != round_now

    def _build_deathwatch_mission_tactics_request(self, game, *, battle_round: int):
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        if game is None or self.army is None:
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None
        available = list(self.get_available_deathwatch_mission_tactics() or [])
        if not available:
            return None
        options = [
            DecisionOption.create(
                "None",
                payload={
                    "action": "skip",
                    "skip": True,
                    "mode": "skip",
                    "summary": "Do not select a Deathwatch Mission Tactic this Command phase.",
                },
            )
        ]
        for key in list(available):
            label = str(self.deathwatch_mission_tactic_label(key) or key)
            options.append(
                DecisionOption.create(
                    label,
                    payload={
                        "choice_key": str(key),
                        "summary": f"{self._DEATHWATCH_MISSION_TACTICS_NAME}: select {label}.",
                    },
                )
            )
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Deathwatch Mission Tactics: select one available tactic or None.",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._DEATHWATCH_MISSION_TACTICS_ABILITY_KEY,
                "ability_name": self._DEATHWATCH_MISSION_TACTICS_NAME,
                "army_id": self._entity_id(self.army),
                "battle_round": int(battle_round),
                "available_keys": list(available),
                "optional": True,
            },
        )

    def _queue_deathwatch_mission_tactics_request(self, *, game=None, player=None, battle_round: int = 0) -> None:
        if not self.is_ordo_xenos_alien_hunters():
            return
        if game is None or player is None or self.army is None:
            return
        if player is not getattr(self.army, "player", None):
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        try:
            br = int(battle_round or getattr(game, "turn", 0) or 0)
        except Exception:
            br = int(getattr(game, "turn", 0) or 0)
        if br <= 0:
            return
        if not self.can_select_deathwatch_mission_tactic(game=game, battle_round=int(br)):
            return
        army_id = self._entity_id(self.army)
        if self._deathwatch_mission_tactics_pending_request(game, army_id=army_id, battle_round=int(br)) is not None:
            return
        request = self._build_deathwatch_mission_tactics_request(game, battle_round=int(br))
        request_decision = getattr(game, "request_decision", None)
        if callable(request_decision) and request is not None:
            request_decision(request)

    def validate_deathwatch_mission_tactic_choice(
        self,
        *,
        choice_key: str = "",
        skip: bool = False,
        game=None,
        player=None,
        battle_round: int = 0,
        available_keys: Optional[list[str]] = None,
    ) -> tuple[bool, str]:
        if not self.is_ordo_xenos_alien_hunters():
            return False, "Deathwatch Mission Tactics requires the Ordo Xenos Alien Hunters detachment."
        if self.army is None:
            return False, "Deathwatch Mission Tactics army not found."
        owner = getattr(self.army, "player", None)
        if player is not None and owner is not None and player is not owner:
            return False, "Deathwatch Mission Tactics must be resolved by the owning player."
        round_key = int(battle_round or 0)
        if round_key > 0 and int(self.deathwatch_mission_tactics_last_selection_round or 0) == round_key:
            return False, "Deathwatch Mission Tactics has already been selected this Command phase."
        if skip:
            return True, ""

        key = str(choice_key or "").strip().upper()
        if not key:
            return False, "Deathwatch Mission Tactics selection requires choice_key."
        if key not in set(self._DEATHWATCH_MISSION_TACTIC_KEYS):
            return False, "Deathwatch Mission Tactics choice_key is invalid."
        allowed = {
            str(v or "").strip().upper()
            for v in list(available_keys or self.get_available_deathwatch_mission_tactics() or [])
            if str(v or "").strip()
        }
        if allowed and key not in allowed:
            return False, "Deathwatch Mission Tactics choice is not currently available."
        if key in {str(v or "").strip().upper() for v in list(self.deathwatch_mission_tactics_selected_keys or ())}:
            return False, "Deathwatch Mission Tactics choice has already been selected this battle."
        return True, ""

    def select_deathwatch_mission_tactic_choice(
        self,
        *,
        choice_key: str = "",
        skip: bool = False,
        game=None,
        player=None,
        battle_round: int = 0,
        available_keys: Optional[list[str]] = None,
    ):
        valid, reason = self.validate_deathwatch_mission_tactic_choice(
            choice_key=choice_key,
            skip=skip,
            game=game,
            player=player,
            battle_round=battle_round,
            available_keys=available_keys,
        )
        if not valid:
            return None
        if game is not None:
            try:
                round_now = int(getattr(game, "turn", 0) or 0)
            except Exception:
                round_now = int(battle_round or 0)
        else:
            round_now = int(battle_round or 0)
        self.deathwatch_mission_tactics_last_selection_round = int(round_now)
        self.clear_active_deathwatch_mission_tactic()
        if skip:
            return {
                "mode": "skip",
                "source": self._DEATHWATCH_MISSION_TACTICS_NAME,
                "battle_round": int(round_now),
            }

        key = str(choice_key or "").strip().upper()
        selected = list(self.deathwatch_mission_tactics_selected_keys or ())
        if key not in selected:
            selected.append(key)
        self.deathwatch_mission_tactics_selected_keys = tuple(selected)
        self.deathwatch_mission_tactics_active_key = key
        self.deathwatch_mission_tactics_active_round = int(round_now)
        return {
            "choice_key": key,
            "label": self.deathwatch_mission_tactic_label(key),
            "source": self._DEATHWATCH_MISSION_TACTICS_NAME,
            "battle_round": int(round_now),
        }

    def _deathwatch_mission_tactics_recipient(self, unit) -> bool:
        if not self.is_ordo_xenos_alien_hunters():
            return False
        if not str(self.deathwatch_mission_tactics_active_key or "").strip():
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return False
        return self._unit_has_keyword(root, "DEATHWATCH")

    def deathwatch_mission_tactics_lethal_hits(self, attacker_model) -> tuple[bool, str]:
        if str(self.deathwatch_mission_tactics_active_key or "").strip().upper() != self._DEATHWATCH_MISSION_TACTIC_MALLEUS:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None) if attacker_model is not None else None
        if not self._deathwatch_mission_tactics_recipient(attacker_unit):
            return False, ""
        return True, f"{self._DEATHWATCH_MISSION_TACTICS_NAME} ({self.deathwatch_mission_tactic_label(self._DEATHWATCH_MISSION_TACTIC_MALLEUS)})"

    def deathwatch_mission_tactics_sustained_hits(self, attacker_model) -> tuple[int, str]:
        if str(self.deathwatch_mission_tactics_active_key or "").strip().upper() != self._DEATHWATCH_MISSION_TACTIC_FUROR:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None) if attacker_model is not None else None
        if not self._deathwatch_mission_tactics_recipient(attacker_unit):
            return 0, ""
        return 1, f"{self._DEATHWATCH_MISSION_TACTICS_NAME} ({self.deathwatch_mission_tactic_label(self._DEATHWATCH_MISSION_TACTIC_FUROR)})"

    def deathwatch_mission_tactics_precision_on_crit(self, attacker_model) -> tuple[bool, str]:
        if str(self.deathwatch_mission_tactics_active_key or "").strip().upper() != self._DEATHWATCH_MISSION_TACTIC_PURGATUS:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None) if attacker_model is not None else None
        if not self._deathwatch_mission_tactics_recipient(attacker_unit):
            return False, ""
        return True, f"{self._DEATHWATCH_MISSION_TACTICS_NAME} ({self.deathwatch_mission_tactic_label(self._DEATHWATCH_MISSION_TACTIC_PURGATUS)})"

    def _imperialis_fleet_source_units(self, *, flag_key: str) -> list:
        if not self.is_imperialis_fleet() or self.army is None:
            return []
        sources = {}
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            if not self._enhancement_bearer_alive(unit):
                continue
            unit_id = self._entity_id(unit)
            if not unit_id or unit_id in sources:
                continue
            sources[unit_id] = unit
        return [sources[key] for key in sorted(sources.keys())]

    def _imperialis_fleet_selected_units_pending_request(self, game, *, ability_key: str, source_unit_id: str) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != "SELECT_REALM_OF_CHAOS_UNITS":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != str(ability_key or "").strip().lower():
                continue
            if str(ctx.get("source_unit_id", "") or "").strip() != str(source_unit_id or "").strip():
                continue
            return True
        return False

    def _imperialis_fleet_selected_units_candidates(
        self,
        source_unit,
        *,
        required_keywords,
        excluded_unit_name_patterns=(),
    ) -> list:
        if not self.is_imperialis_fleet():
            return []
        if source_unit is None or not self._unit_in_army(source_unit):
            return []
        if not self._enhancement_bearer_alive(source_unit):
            return []

        candidates = []
        for root in self._iter_unique_army_roots():
            if not self._unit_available_for_prebattle_selection(root):
                continue
            if not self._unit_has_all_keywords(root, required_keywords):
                continue
            if excluded_unit_name_patterns and self._unit_name_matches_any_pattern(root, excluded_unit_name_patterns):
                continue
            candidates.append(root)
        candidates.sort(key=lambda unit: self._entity_id(unit))
        return candidates

    def clandestine_operation_selectable_units(self, source_unit, *, game=None) -> list:
        del game
        sr = getattr(source_unit, "special_rules", None)
        required_keywords = list(
            sr.get(
                "enhancement_imperialis_fleet_clandestine_operation_required_keywords",
                ("AGENTS OF THE IMPERIUM", "INFANTRY"),
            )
            if isinstance(sr, dict)
            else ("AGENTS OF THE IMPERIUM", "INFANTRY")
        )
        excluded = list(
            sr.get(
                "enhancement_imperialis_fleet_clandestine_operation_excluded_unit_name_patterns",
                ("GREY KNIGHTS TERMINATOR SQUAD",),
            )
            if isinstance(sr, dict)
            else ("GREY KNIGHTS TERMINATOR SQUAD",)
        )
        return self._imperialis_fleet_selected_units_candidates(
            source_unit,
            required_keywords=required_keywords,
            excluded_unit_name_patterns=excluded,
        )

    def combat_landers_selectable_units(self, source_unit, *, game=None) -> list:
        del game
        sr = getattr(source_unit, "special_rules", None)
        required_keywords = list(
            sr.get(
                "enhancement_imperialis_fleet_combat_landers_required_keywords",
                ("VOIDFARERS",),
            )
            if isinstance(sr, dict)
            else ("VOIDFARERS",)
        )
        return self._imperialis_fleet_selected_units_candidates(
            source_unit,
            required_keywords=required_keywords,
        )

    def _queue_imperialis_fleet_selected_units_request(
        self,
        *,
        game=None,
        player=None,
        source_unit=None,
        ability_key: str,
        ability_name: str,
        max_units: int,
        candidates: list,
        subtitle: str,
        instruction: str,
        resolved_key: str,
        selected_ids_key: str,
    ) -> None:
        if game is None or source_unit is None or self.army is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        source_unit_id = self._entity_id(source_unit)
        if not source_unit_id:
            return
        if self._imperialis_fleet_selected_units_pending_request(
            game,
            ability_key=ability_key,
            source_unit_id=source_unit_id,
        ):
            return

        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        if int(max_units or 0) <= 0 or not list(candidates or []):
            source_sr[resolved_key] = True
            source_sr[selected_ids_key] = []
            source_unit.special_rules = source_sr
            return

        candidate_ids = [self._entity_id(unit) for unit in list(candidates or []) if self._entity_id(unit)]
        if not candidate_ids:
            source_sr[resolved_key] = True
            source_sr[selected_ids_key] = []
            source_unit.special_rules = source_sr
            return

        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        from ..engine.decisions import DecisionOption, DecisionRequest

        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            f"{ability_name}: select up to {int(max_units)} eligible unit(s).",
            player_id=getattr(owner, "id", None),
            options=[
                DecisionOption.create("Confirm", payload={"action": "confirm"}),
                DecisionOption.create("None", payload={"action": "skip"}),
            ],
            context={
                "ability": str(ability_key or "").strip().lower(),
                "ability_name": ability_name,
                "army_id": self._entity_id(self.army),
                "source_unit_id": source_unit_id,
                "unit_id": source_unit_id,
                "max_units": int(max_units),
                "allowed_unit_ids": list(candidate_ids),
                "title": ability_name,
                "subtitle": subtitle,
                "instruction": instruction,
                "skip_label": "None (do not select units)",
                "optional": True,
            },
        )
        request_fn = getattr(game, "request_decision", None)
        if callable(request_fn):
            request_fn(request)

    def clandestine_operation_selection_is_valid(self, unit_ids, *, game=None, player=None, source_unit=None) -> tuple[bool, str]:
        del game
        if not self.is_imperialis_fleet():
            return False, "Clandestine Operation requires the Imperialis Fleet detachment."
        if source_unit is None or not self._unit_in_army(source_unit):
            return False, "Clandestine Operation source unit was not found."
        if player is not None and player is not getattr(self.army, "player", None):
            return False, "Clandestine Operation can only be selected by the controlling player."
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict) or not bool(source_sr.get("enhancement_imperialis_fleet_clandestine_operation")):
            return False, "Clandestine Operation source unit does not have this enhancement."
        if bool(source_sr.get("enhancement_imperialis_fleet_clandestine_operation_resolved")):
            return False, "Clandestine Operation has already resolved."
        if not isinstance(unit_ids, list):
            return False, "Clandestine Operation selection requires unit_ids."
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        max_units = int(source_sr.get("enhancement_imperialis_fleet_clandestine_operation_max_units", 3) or 3)
        if len(selected) > max_units:
            return False, f"Clandestine Operation can select up to {int(max_units)} units."
        candidates_by_id = {
            self._entity_id(unit): unit
            for unit in list(self.clandestine_operation_selectable_units(source_unit) or [])
            if self._entity_id(unit)
        }
        for unit_id in selected:
            if unit_id not in candidates_by_id:
                return False, "Clandestine Operation selection contains an ineligible unit."
        return True, ""

    def combat_landers_selection_is_valid(self, unit_ids, *, game=None, player=None, source_unit=None) -> tuple[bool, str]:
        del game
        if not self.is_imperialis_fleet():
            return False, "Combat Landers requires the Imperialis Fleet detachment."
        if source_unit is None or not self._unit_in_army(source_unit):
            return False, "Combat Landers source unit was not found."
        if player is not None and player is not getattr(self.army, "player", None):
            return False, "Combat Landers can only be selected by the controlling player."
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict) or not bool(source_sr.get("enhancement_imperialis_fleet_combat_landers")):
            return False, "Combat Landers source unit does not have this enhancement."
        if bool(source_sr.get("enhancement_imperialis_fleet_combat_landers_resolved")):
            return False, "Combat Landers has already resolved."
        if not isinstance(unit_ids, list):
            return False, "Combat Landers selection requires unit_ids."
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        max_units = int(source_sr.get("enhancement_imperialis_fleet_combat_landers_max_units", 3) or 3)
        if len(selected) > max_units:
            return False, f"Combat Landers can select up to {int(max_units)} units."
        candidates_by_id = {
            self._entity_id(unit): unit
            for unit in list(self.combat_landers_selectable_units(source_unit) or [])
            if self._entity_id(unit)
        }
        for unit_id in selected:
            if unit_id not in candidates_by_id:
                return False, "Combat Landers selection contains an ineligible unit."
        return True, ""

    def _clear_imperialis_fleet_selected_unit_flag(self, *, flag_key: str, source_id_key: str) -> None:
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            updated = dict(sr)
            updated.pop(flag_key, None)
            updated.pop(source_id_key, None)
            if updated != sr:
                unit.special_rules = updated
                invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
                if callable(invalidate_cache):
                    invalidate_cache()

    def apply_clandestine_operation_selection(self, unit_ids, *, game=None, player=None, source_unit=None) -> list[str]:
        del game
        if source_unit is None:
            source_units = self._imperialis_fleet_source_units(
                flag_key="enhancement_imperialis_fleet_clandestine_operation"
            )
            if not source_units:
                return []
            source_unit = source_units[0]
        valid, _reason = self.clandestine_operation_selection_is_valid(
            unit_ids,
            player=player,
            source_unit=source_unit,
        )
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        if not valid:
            return []
        source_unit_id = self._entity_id(source_unit)
        self._clear_imperialis_fleet_selected_unit_flag(
            flag_key="imperialis_fleet_clandestine_operation_infiltrators",
            source_id_key="imperialis_fleet_clandestine_operation_source_unit_id",
        )
        candidates_by_id = {
            self._entity_id(unit): unit
            for unit in list(self.clandestine_operation_selectable_units(source_unit) or [])
            if self._entity_id(unit)
        }
        applied_ids: list[str] = []
        for unit_id in selected:
            root = candidates_by_id.get(unit_id)
            if root is None:
                continue
            for member in self._attached_members(root):
                member_sr = getattr(member, "special_rules", None)
                if not isinstance(member_sr, dict):
                    member_sr = {}
                member_sr["imperialis_fleet_clandestine_operation_infiltrators"] = True
                member_sr["imperialis_fleet_clandestine_operation_source_unit_id"] = source_unit_id
                member.special_rules = member_sr
                invalidate_cache = getattr(member, "_invalidate_ability_cache", None)
                if callable(invalidate_cache):
                    invalidate_cache()
            applied_ids.append(unit_id)
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        source_sr["enhancement_imperialis_fleet_clandestine_operation_resolved"] = True
        source_sr["enhancement_imperialis_fleet_clandestine_operation_selected_unit_ids"] = list(applied_ids)
        source_unit.special_rules = source_sr
        return list(applied_ids)

    def apply_combat_landers_selection(self, unit_ids, *, game=None, player=None, source_unit=None) -> list[str]:
        del game
        if source_unit is None:
            source_units = self._imperialis_fleet_source_units(
                flag_key="enhancement_imperialis_fleet_combat_landers"
            )
            if not source_units:
                return []
            source_unit = source_units[0]
        valid, _reason = self.combat_landers_selection_is_valid(
            unit_ids,
            player=player,
            source_unit=source_unit,
        )
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        if not valid:
            return []
        source_unit_id = self._entity_id(source_unit)
        self._clear_imperialis_fleet_selected_unit_flag(
            flag_key="imperialis_fleet_combat_landers_deep_strike",
            source_id_key="imperialis_fleet_combat_landers_source_unit_id",
        )
        candidates_by_id = {
            self._entity_id(unit): unit
            for unit in list(self.combat_landers_selectable_units(source_unit) or [])
            if self._entity_id(unit)
        }
        applied_ids: list[str] = []
        for unit_id in selected:
            root = candidates_by_id.get(unit_id)
            if root is None:
                continue
            for member in self._attached_members(root):
                member_sr = getattr(member, "special_rules", None)
                if not isinstance(member_sr, dict):
                    member_sr = {}
                member_sr["imperialis_fleet_combat_landers_deep_strike"] = True
                member_sr["imperialis_fleet_combat_landers_source_unit_id"] = source_unit_id
                member.special_rules = member_sr
                invalidate_cache = getattr(member, "_invalidate_ability_cache", None)
                if callable(invalidate_cache):
                    invalidate_cache()
            applied_ids.append(unit_id)
        source_sr = getattr(source_unit, "special_rules", None)
        if not isinstance(source_sr, dict):
            source_sr = {}
        source_sr["enhancement_imperialis_fleet_combat_landers_resolved"] = True
        source_sr["enhancement_imperialis_fleet_combat_landers_selected_unit_ids"] = list(applied_ids)
        source_unit.special_rules = source_sr
        return list(applied_ids)

    def _attached_member_with_flag(self, unit, flag_key: str):
        root = self._unit_root(unit)
        if root is None:
            return None, {}
        for member in self._attached_members(root):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
                continue
            return member, sr
        return None, {}

    def _digital_weapons_pending_request(self, game, *, source_unit_id: str) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self._DIGITAL_WEAPONS_ABILITY_KEY:
                continue
            if str(ctx.get("source_unit_id", "") or "").strip() != str(source_unit_id or "").strip():
                continue
            return True
        return False

    def digital_weapons_candidate_entries(self, source_unit, *, game=None) -> list[dict]:
        if not self.is_imperialis_fleet() or game is None:
            return []
        game_map = getattr(game, "map", None)
        if game_map is None:
            return []
        root = self._unit_root(source_unit)
        if root is None or not self._unit_on_battlefield(root):
            return []
        source_member, source_sr = self._attached_member_with_flag(
            root,
            "enhancement_imperialis_fleet_digital_weapons",
        )
        if source_member is None or not self._enhancement_bearer_alive(source_member):
            return []
        bearer_model = self._enhancement_bearer_model(source_member)
        if bearer_model is None:
            return []
        within_fn = getattr(root, "_model_within_engagement_range_of_unit", None)
        if not callable(within_fn):
            return []

        entries: list[dict] = []
        seen_units: set[str] = set()
        enemy_units = list(getattr(game_map, "get_enemy_units", lambda *_args: [])(root) or [])
        for enemy in list(enemy_units or []):
            enemy_root = self._unit_root(enemy)
            if enemy_root is None:
                continue
            enemy_id = self._entity_id(enemy_root)
            if not enemy_id or enemy_id in seen_units:
                continue
            seen_units.add(enemy_id)
            if not self._unit_on_battlefield(enemy_root):
                continue
            if not bool(within_fn(bearer_model, enemy_root)):
                continue
            entries.append(
                {
                    "target_unit_id": enemy_id,
                    "target_model_id": "",
                    "label": str(getattr(enemy_root, "name", "Unit") or "Unit"),
                }
            )
            if not bool(source_sr.get("enhancement_imperialis_fleet_digital_weapons_precision_allocation", True)):
                continue
            has_attached_leaders = bool(getattr(enemy_root, "attached_leaders", []) or [])
            if not has_attached_leaders:
                continue
            get_models_for_collision = getattr(enemy_root, "get_models_for_collision", None)
            if callable(get_models_for_collision):
                all_models = list(get_models_for_collision() or [])
            else:
                all_models = list(getattr(enemy_root, "models", []) or [])
            character_models = []
            for model in list(all_models or []):
                if model is None:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                    continue
                is_character = bool(getattr(model, "is_character", False))
                if not is_character:
                    has_keyword = getattr(model, "has_keyword", None)
                    if callable(has_keyword):
                        is_character = bool(has_keyword("CHARACTER"))
                if not is_character:
                    continue
                can_see_fn = getattr(game_map, "can_model_see_model", None)
                if callable(can_see_fn) and not bool(can_see_fn(bearer_model, model)):
                    continue
                character_models.append(model)
            character_models.sort(key=lambda model: self._entity_id(model))
            for model in list(character_models or []):
                model_id = self._entity_id(model)
                if not model_id:
                    continue
                entries.append(
                    {
                        "target_unit_id": enemy_id,
                        "target_model_id": model_id,
                        "label": f"{getattr(enemy_root, 'name', 'Unit')} -> {getattr(model, 'name', 'Character')}",
                    }
                )
        entries.sort(
            key=lambda entry: (
                str(entry.get("target_unit_id", "") or ""),
                str(entry.get("target_model_id", "") or ""),
                str(entry.get("label", "") or "").lower(),
            )
        )
        return entries

    def queue_digital_weapons_request(
        self,
        source_unit,
        *,
        game=None,
        player=None,
        allow_existing_request: bool = False,
    ) -> None:
        if game is None or self.army is None:
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        source_member, source_sr = self._attached_member_with_flag(
            source_unit,
            "enhancement_imperialis_fleet_digital_weapons",
        )
        if source_member is None:
            return
        source_unit_id = self._entity_id(source_member)
        if not source_unit_id:
            return
        if (not allow_existing_request) and self._digital_weapons_pending_request(game, source_unit_id=source_unit_id):
            return
        remaining = self._coerce_int(
            source_sr.get("enhancement_imperialis_fleet_digital_weapons_pending_successes", 0),
            default=0,
        )
        if remaining <= 0:
            return
        candidates = list(self.digital_weapons_candidate_entries(source_member, game=game) or [])
        if not candidates:
            cleared_sr = dict(source_sr)
            cleared_sr.pop("enhancement_imperialis_fleet_digital_weapons_pending_successes", None)
            source_member.special_rules = cleared_sr
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = []
        for entry in list(candidates or []):
            options.append(
                DecisionOption.create(
                    str(entry.get("label", "") or "Unit"),
                    payload={
                        "target_unit_id": str(entry.get("target_unit_id", "") or ""),
                        "target_model_id": str(entry.get("target_model_id", "") or ""),
                    },
                )
            )
        if not options:
            return
        ability_name = str(
            source_sr.get("enhancement_imperialis_fleet_digital_weapons_source", "")
            or self._DIGITAL_WEAPONS_NAME
        ).strip() or self._DIGITAL_WEAPONS_NAME
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target for 1 mortal wound ({int(remaining)} remaining).",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self._DIGITAL_WEAPONS_ABILITY_KEY,
                "ability_name": ability_name,
                "phase": "Fight phase",
                "source_unit_id": source_unit_id,
                "unit_id": source_unit_id,
                "remaining_successes": int(remaining),
            },
        )
        request_fn = getattr(game, "request_decision", None)
        if callable(request_fn):
            request_fn(request)

    def trigger_digital_weapons_on_fight_selected(self, unit, *, game=None, player=None) -> bool:
        if not self.is_imperialis_fleet() or game is None:
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_on_battlefield(root):
            return False
        source_member, source_sr = self._attached_member_with_flag(
            root,
            "enhancement_imperialis_fleet_digital_weapons",
        )
        if source_member is None or not self._enhancement_bearer_alive(source_member):
            return False
        source_unit_id = self._entity_id(source_member)
        if not source_unit_id:
            return False
        pending = self._coerce_int(
            source_sr.get("enhancement_imperialis_fleet_digital_weapons_pending_successes", 0),
            default=0,
        )
        if pending > 0 or self._digital_weapons_pending_request(game, source_unit_id=source_unit_id):
            return False
        candidates = list(self.digital_weapons_candidate_entries(source_member, game=game) or [])
        if not candidates:
            return False

        from ..utility.dice import get_roll
        from ..utility.event_bus import append_dice

        owner = player if player is not None else getattr(self.army, "player", None)
        ability_name = str(
            source_sr.get("enhancement_imperialis_fleet_digital_weapons_source", "")
            or self._DIGITAL_WEAPONS_NAME
        ).strip() or self._DIGITAL_WEAPONS_NAME
        dice_count = int(source_sr.get("enhancement_imperialis_fleet_digital_weapons_dice", 3) or 3)
        threshold = int(source_sr.get("enhancement_imperialis_fleet_digital_weapons_threshold", 4) or 4)
        dice_count = max(1, int(dice_count))
        threshold = max(2, min(6, int(threshold)))
        rolls: list[int] = []
        successes = 0
        for _ in range(dice_count):
            roll = int(get_roll("D6") or 0)
            rolls.append(int(roll))
            if int(roll) >= int(threshold):
                successes += 1
        if owner is not None:
            append_dice(
                owner,
                f"{ability_name}: {', '.join(str(v) for v in rolls)} ({int(successes)} success(es) on {int(threshold)}+).",
            )
        if successes <= 0:
            return False
        updated_sr = dict(source_sr)
        updated_sr["enhancement_imperialis_fleet_digital_weapons_pending_successes"] = int(successes)
        source_member.special_rules = updated_sr
        self.queue_digital_weapons_request(source_member, game=game, player=owner)
        return True

    def advance_digital_weapons_state(self, source_unit, *, game=None, player=None) -> int:
        source_member, source_sr = self._attached_member_with_flag(
            source_unit,
            "enhancement_imperialis_fleet_digital_weapons",
        )
        if source_member is None:
            return 0
        remaining = self._coerce_int(
            source_sr.get("enhancement_imperialis_fleet_digital_weapons_pending_successes", 0),
            default=0,
        )
        remaining = max(0, int(remaining) - 1)
        updated_sr = dict(source_sr)
        if remaining > 0:
            updated_sr["enhancement_imperialis_fleet_digital_weapons_pending_successes"] = int(remaining)
        else:
            updated_sr.pop("enhancement_imperialis_fleet_digital_weapons_pending_successes", None)
        source_member.special_rules = updated_sr
        if remaining > 0:
            self.queue_digital_weapons_request(
                source_member,
                game=game,
                player=player,
                allow_existing_request=True,
            )
        return int(remaining)

    def on_prebattle_rules_start(self, *, game=None) -> None:
        if not self.is_imperialis_fleet() or self.army is None:
            return
        player = getattr(self.army, "player", None)
        if game is None:
            game = getattr(player, "game", None) if player is not None else None
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        for source_unit in self._imperialis_fleet_source_units(
            flag_key="enhancement_imperialis_fleet_clandestine_operation"
        ):
            source_sr = getattr(source_unit, "special_rules", None)
            if not isinstance(source_sr, dict) or bool(
                source_sr.get("enhancement_imperialis_fleet_clandestine_operation_resolved")
            ):
                continue
            self._queue_imperialis_fleet_selected_units_request(
                game=game,
                player=player,
                source_unit=source_unit,
                ability_key=self._CLANDESTINE_OPERATION_ABILITY_KEY,
                ability_name=str(
                    source_sr.get("enhancement_imperialis_fleet_clandestine_operation_source", "")
                    or self._CLANDESTINE_OPERATION_NAME
                ).strip()
                or self._CLANDESTINE_OPERATION_NAME,
                max_units=int(
                    source_sr.get("enhancement_imperialis_fleet_clandestine_operation_max_units", 3) or 3
                ),
                candidates=list(self.clandestine_operation_selectable_units(source_unit) or []),
                subtitle='Select up to 3 AGENTS OF THE IMPERIUM INFANTRY units (excluding Grey Knights Terminator Squad units).',
                instruction="Selected units gain Infiltrators for this battle.",
                resolved_key="enhancement_imperialis_fleet_clandestine_operation_resolved",
                selected_ids_key="enhancement_imperialis_fleet_clandestine_operation_selected_unit_ids",
            )
        for source_unit in self._imperialis_fleet_source_units(
            flag_key="enhancement_imperialis_fleet_combat_landers"
        ):
            source_sr = getattr(source_unit, "special_rules", None)
            if not isinstance(source_sr, dict) or bool(
                source_sr.get("enhancement_imperialis_fleet_combat_landers_resolved")
            ):
                continue
            self._queue_imperialis_fleet_selected_units_request(
                game=game,
                player=player,
                source_unit=source_unit,
                ability_key=self._COMBAT_LANDERS_ABILITY_KEY,
                ability_name=str(
                    source_sr.get("enhancement_imperialis_fleet_combat_landers_source", "")
                    or self._COMBAT_LANDERS_NAME
                ).strip()
                or self._COMBAT_LANDERS_NAME,
                max_units=int(source_sr.get("enhancement_imperialis_fleet_combat_landers_max_units", 3) or 3),
                candidates=list(self.combat_landers_selectable_units(source_unit) or []),
                subtitle='Select up to 3 VOIDFARERS units.',
                instruction="Selected units gain Deep Strike for this battle.",
                resolved_key="enhancement_imperialis_fleet_combat_landers_resolved",
                selected_ids_key="enhancement_imperialis_fleet_combat_landers_selected_unit_ids",
            )

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if game is None or player is None:
            return
        if self.army is None or player is not getattr(self.army, "player", None):
            return
        if self.is_imperialis_fleet():
            self._queue_at_all_costs_request(
                game=game,
                player=player,
                battle_round=int(getattr(game, "turn", 0) or 0),
            )
        if self.is_ordo_xenos_alien_hunters():
            self.clear_active_deathwatch_mission_tactic()
            self._queue_deathwatch_mission_tactics_request(
                game=game,
                player=player,
                battle_round=int(getattr(game, "turn", 0) or 0),
            )

    def validate_at_all_costs_choice(
        self,
        *,
        mode: str,
        target_unit=None,
        objective_id: str = "",
        game=None,
        player=None,
        battle_round: int = 0,
        candidate_unit_ids: Optional[list[str]] = None,
        candidate_objective_ids: Optional[list[str]] = None,
    ) -> tuple[bool, str]:
        if not self.is_imperialis_fleet():
            return False, "At all Costs requires the Imperialis Fleet detachment."
        if self.army is None:
            return False, "At all Costs army not found."
        owner = getattr(self.army, "player", None)
        if player is not None and owner is not None and player is not owner:
            return False, "At all Costs must be resolved by the owning player."
        mode_key = str(mode or "").strip().lower()
        if mode_key not in {"skip", self._AT_ALL_COSTS_MODE_ELIMINATE, self._AT_ALL_COSTS_MODE_ACQUIRE}:
            return False, "At all Costs mode must be eliminate, acquire, or skip."

        owner_id = str(getattr(owner, "id", "") or "")
        round_key = int(battle_round or 0)
        if round_key > 0 and self.at_all_costs_selected_round == round_key and self.at_all_costs_selected_owner_id == owner_id:
            return False, "At all Costs has already been selected this Command phase."

        if mode_key == "skip":
            return True, ""
        if mode_key == self._AT_ALL_COSTS_MODE_ELIMINATE:
            root = self._unit_root(target_unit)
            if root is None:
                return False, "Eliminate At All Costs requires target_unit."
            target_id = self._entity_id(root)
            if not target_id:
                return False, "Eliminate At All Costs target unit was not found."
            if candidate_unit_ids:
                allowed = {str(v or "").strip() for v in list(candidate_unit_ids or []) if str(v or "").strip()}
                if target_id not in allowed:
                    return False, "Eliminate At All Costs selected target is not an eligible candidate."
            if not self._unit_on_battlefield(root):
                return False, "Eliminate At All Costs target must be on the battlefield."
            if player is not None and not self._unit_is_enemy_of_player(root, player):
                return False, "Eliminate At All Costs target must be an enemy unit."
            return True, ""

        objective_key = str(objective_id or "").strip()
        if not objective_key:
            return False, "Acquire At All Costs selection requires objective_id."
        if candidate_objective_ids:
            allowed = {str(v or "").strip() for v in list(candidate_objective_ids or []) if str(v or "").strip()}
            if objective_key not in allowed:
                return False, "Acquire At All Costs selected objective marker is not an eligible candidate."
        if self._objective_entry_by_id(objective_key, game=game) is None:
            return False, "Acquire At All Costs selected objective marker was not found."
        return True, ""

    def select_at_all_costs_choice(
        self,
        *,
        mode: str,
        target_unit=None,
        objective_id: str = "",
        game=None,
        player=None,
        battle_round: int = 0,
        candidate_unit_ids: Optional[list[str]] = None,
        candidate_objective_ids: Optional[list[str]] = None,
    ):
        valid, reason = self.validate_at_all_costs_choice(
            mode=mode,
            target_unit=target_unit,
            objective_id=objective_id,
            game=game,
            player=player,
            battle_round=battle_round,
            candidate_unit_ids=candidate_unit_ids,
            candidate_objective_ids=candidate_objective_ids,
        )
        if not valid:
            return None

        owner = getattr(self.army, "player", None) if self.army is not None else None
        owner_id = str(getattr(owner, "id", "") or "")
        mode_key = str(mode or "").strip().lower()
        if game is not None:
            try:
                self.at_all_costs_selected_round = int(getattr(game, "turn", 0) or 0)
            except Exception:
                self.at_all_costs_selected_round = int(battle_round or 0)
        else:
            self.at_all_costs_selected_round = int(battle_round or 0)
        self.at_all_costs_selected_owner_id = owner_id

        self.clear_at_all_costs_effect()
        if mode_key == "skip":
            return {
                "mode": "skip",
                "source": self._AT_ALL_COSTS_NAME,
                "battle_round": int(self.at_all_costs_selected_round or 0),
            }
        if mode_key == self._AT_ALL_COSTS_MODE_ELIMINATE:
            root = self._unit_root(target_unit)
            target_id = self._entity_id(root)
            target_name = str(getattr(root, "name", "") or "Enemy unit")
            self.at_all_costs_active_mode = self._AT_ALL_COSTS_MODE_ELIMINATE
            self.at_all_costs_target_unit_id = target_id
            return {
                "mode": self._AT_ALL_COSTS_MODE_ELIMINATE,
                "target_unit_id": target_id,
                "target_unit_name": target_name,
                "source": self._AT_ALL_COSTS_NAME,
                "battle_round": int(self.at_all_costs_selected_round or 0),
            }

        objective_key = str(objective_id or "").strip()
        entry = self._objective_entry_by_id(objective_key, game=game)
        if entry is None:
            return None
        _objective_id, objective, _location = entry
        objective_name = str(getattr(objective, "name", "") or "Objective marker")
        self.at_all_costs_active_mode = self._AT_ALL_COSTS_MODE_ACQUIRE
        self.at_all_costs_target_objective_id = objective_key
        return {
            "mode": self._AT_ALL_COSTS_MODE_ACQUIRE,
            "objective_id": objective_key,
            "objective_name": objective_name,
            "source": self._AT_ALL_COSTS_NAME,
            "battle_round": int(self.at_all_costs_selected_round or 0),
        }

    def _unit_within_acquire_objective(self, unit, *, game=None, game_map=None) -> bool:
        if unit is None:
            return False
        if str(self.at_all_costs_active_mode or "").strip().lower() != self._AT_ALL_COSTS_MODE_ACQUIRE:
            return False
        objective_id = str(self.at_all_costs_target_objective_id or "").strip()
        if not objective_id:
            return False
        entry = self._objective_entry_by_id(objective_id, game=game, game_map=game_map)
        if entry is None:
            return False
        _objective_id, _objective, objective_point = entry
        root = self._unit_root(unit)
        if root is None:
            return False
        within = getattr(root, "is_within_objective_range", None)
        if not callable(within):
            return False
        return bool(within(objective_point))

    def at_all_costs_hit_bonus(self, model, attacker_unit, target_unit, *, game=None, game_map=None) -> tuple[int, str]:
        del game, game_map
        if not self.is_imperialis_fleet():
            return 0, ""
        if str(self.at_all_costs_active_mode or "").strip().lower() != self._AT_ALL_COSTS_MODE_ELIMINATE:
            return 0, ""
        if model is None or target_unit is None:
            return 0, ""
        attacker_root = self._unit_root(attacker_unit if attacker_unit is not None else getattr(model, "parent_unit", None))
        target_root = self._unit_root(target_unit)
        if attacker_root is None or target_root is None:
            return 0, ""
        if not self._model_in_army(model) or not self._unit_in_army(attacker_root):
            return 0, ""
        if not self._unit_is_agents_of_the_imperium(attacker_root):
            return 0, ""
        target_id = self._entity_id(target_root)
        if not target_id or target_id != str(self.at_all_costs_target_unit_id or ""):
            return 0, ""
        return 1, f"{self._AT_ALL_COSTS_NAME} (Eliminate)"

    def at_all_costs_acquire_leadership_bonus(self, unit, *, game=None, game_map=None) -> tuple[int, str]:
        if not self.is_imperialis_fleet():
            return 0, ""
        root = self._unit_root(unit)
        if root is None or not self._unit_in_army(root):
            return 0, ""
        if not self._unit_is_agents_of_the_imperium(root):
            return 0, ""
        if not self._unit_within_acquire_objective(root, game=game, game_map=game_map):
            return 0, ""
        # Leadership improves by 1, represented as -1 to the numeric characteristic.
        return -1, f"{self._AT_ALL_COSTS_NAME} (Acquire)"

    def at_all_costs_acquire_objective_control_bonus(self, model, *, unit=None, game=None, game_map=None) -> tuple[int, str]:
        if not self.is_imperialis_fleet():
            return 0, ""
        source_unit = self._unit_root(unit if unit is not None else getattr(model, "parent_unit", None))
        if source_unit is None or not self._unit_in_army(source_unit):
            return 0, ""
        if not self._unit_is_agents_of_the_imperium(source_unit):
            return 0, ""
        if not self._unit_within_acquire_objective(source_unit, game=game, game_map=game_map):
            return 0, ""
        return 1, f"{self._AT_ALL_COSTS_NAME} (Acquire)"

    def at_all_costs_acquire_invulnerable_save(
        self,
        model,
        *,
        unit=None,
        attack_type: str = "",
        game=None,
        game_map=None,
    ) -> tuple[int, str]:
        del attack_type
        if not self.is_imperialis_fleet():
            return 0, ""
        source_unit = self._unit_root(unit if unit is not None else getattr(model, "parent_unit", None))
        if source_unit is None or not self._unit_in_army(source_unit):
            return 0, ""
        if not self._unit_is_agents_of_the_imperium(source_unit):
            return 0, ""
        if not self._unit_within_acquire_objective(source_unit, game=game, game_map=game_map):
            return 0, ""
        return 5, f"{self._AT_ALL_COSTS_NAME} (Acquire)"

    def emperors_will_can_shoot_after_advance(self, unit, *, profile=None, game=None) -> bool:
        if not self._weapon_profile_is_ranged(profile):
            return False
        root, _sr = self._imperialis_fleet_turn_effect_state(
            unit,
            prefix="imperial_agents_emperors_will",
            game=game,
        )
        return bool(root is not None)

    def emperors_will_can_shoot_after_fall_back(self, unit, *, profile=None, game=None) -> bool:
        if not self._weapon_profile_is_ranged(profile):
            return False
        root, _sr = self._imperialis_fleet_turn_effect_state(
            unit,
            prefix="imperial_agents_emperors_will",
            game=game,
        )
        return bool(root is not None)

    def close_quarters_barrage_strength_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        weapon_profile=None,
        attack_instance=None,
        game=None,
    ) -> tuple[int, str]:
        del attack_instance
        if attacker_model is None or target_unit is None or not self._weapon_profile_is_ranged(weapon_profile):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root, sr = self._imperialis_fleet_phase_effect_state(
            attacker_unit,
            prefix="imperial_agents_close_quarters_barrage",
            game=game,
        )
        if root is None or not isinstance(sr, dict) or not self._model_in_army(attacker_model):
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return 0, ""
        if not model_within_range_of_unit(attacker_model, target_root, 12.0):
            return 0, ""
        source = str(sr.get("imperial_agents_close_quarters_barrage_source", "") or "Close-Quarters Barrage").strip()
        return 1, source or "Close-Quarters Barrage"

    def close_quarters_barrage_ap_bonus(
        self,
        attacker_model,
        target_unit,
        *,
        weapon_profile=None,
        attack_instance=None,
        game=None,
    ) -> tuple[int, str]:
        del attack_instance
        if attacker_model is None or target_unit is None or not self._weapon_profile_is_ranged(weapon_profile):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root, sr = self._imperialis_fleet_phase_effect_state(
            attacker_unit,
            prefix="imperial_agents_close_quarters_barrage",
            game=game,
        )
        if root is None or not isinstance(sr, dict) or not self._model_in_army(attacker_model):
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return 0, ""
        if not model_within_range_of_unit(attacker_model, target_root, 12.0):
            return 0, ""
        source = str(sr.get("imperial_agents_close_quarters_barrage_source", "") or "Close-Quarters Barrage").strip()
        return 1, source or "Close-Quarters Barrage"

    def violent_acquisition_attack_keyword_bonus_rules(
        self,
        attacker_model,
        target_unit,
        *,
        attacker_unit=None,
        attack_type: str = "any",
        weapon_profile=None,
        game=None,
        game_map=None,
    ) -> list[dict]:
        del game_map
        if attacker_model is None or target_unit is None:
            return []
        source_unit = self._unit_root(
            attacker_unit if attacker_unit is not None else getattr(attacker_model, "parent_unit", None)
        )
        root, sr = self._imperialis_fleet_phase_effect_state(
            source_unit,
            prefix="imperial_agents_violent_acquisition",
            game=game,
        )
        if root is None or not isinstance(sr, dict) or not self._model_in_army(attacker_model):
            return []
        source = str(sr.get("imperial_agents_violent_acquisition_source", "") or "Violent Acquisition").strip()
        source = source or "Violent Acquisition"
        return [
            {
                "attack_type": "any",
                "keyword": "SUSTAINED HITS 1",
                "source": source,
                "requires_objective": True,
            },
            {
                "attack_type": "any",
                "keyword": "LANCE",
                "source": source,
                "requires_objective": True,
            },
            {
                "attack_type": "any",
                "keyword": "IGNORES COVER",
                "source": source,
                "requires_objective": True,
            },
        ]

    def dispense_justice_attack_keyword_bonus_rules(
        self,
        attacker_model,
        target_unit,
        *,
        attacker_unit=None,
        attack_type: str = "any",
        weapon_profile=None,
        game=None,
        game_map=None,
    ) -> list[dict]:
        del target_unit, attack_type, weapon_profile, game_map
        if attacker_model is None or not self._model_in_army(attacker_model):
            return []
        source_unit = self._unit_root(
            attacker_unit if attacker_unit is not None else getattr(attacker_model, "parent_unit", None)
        )
        root, sr = self._ordo_hereticus_phase_effect_state(
            source_unit,
            prefix="imperial_agents_dispense_justice",
            game=game,
        )
        if root is None or not isinstance(sr, dict):
            return []
        source = str(sr.get("imperial_agents_dispense_justice_source", "") or "Dispense Justice").strip()
        return [
            {
                "attack_type": "any",
                "keyword": "LETHAL HITS",
                "source": source or "Dispense Justice",
            }
        ]

    def execution_order_attack_keyword_bonus_rules(
        self,
        attacker_model,
        target_unit,
        *,
        attacker_unit=None,
        attack_type: str = "any",
        weapon_profile=None,
        game=None,
        game_map=None,
    ) -> list[dict]:
        del attack_type, weapon_profile, game_map
        if attacker_model is None or target_unit is None or not self._model_in_army(attacker_model):
            return []
        source_unit = self._unit_root(
            attacker_unit if attacker_unit is not None else getattr(attacker_model, "parent_unit", None)
        )
        root, sr = self._ordo_hereticus_execution_order_state(source_unit, game=game)
        if root is None or not isinstance(sr, dict):
            return []
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return []
        expected_target_id = str(sr.get("imperial_agents_execution_order_enemy_unit_id", "") or "")
        current_target_id = self._entity_id(target_root)
        if not expected_target_id or not current_target_id or expected_target_id != current_target_id:
            return []
        source = str(sr.get("imperial_agents_execution_order_source", "") or "Execution Order").strip()
        return [
            {
                "attack_type": "any",
                "keyword": "PRECISION",
                "source": source or "Execution Order",
            }
        ]

    def line_of_fire_allows_ranged_target(
        self,
        attacker_unit,
        target_unit,
        *,
        weapon_profile=None,
        game=None,
        game_map=None,
    ) -> bool:
        if target_unit is None or not self._weapon_profile_is_ranged(weapon_profile):
            return False
        is_blast = getattr(weapon_profile, "is_blast", None)
        if callable(is_blast) and bool(is_blast()):
            return False
        source_unit = self._unit_root(attacker_unit)
        root, sr = self._ordo_hereticus_phase_effect_state(
            source_unit,
            prefix="imperial_agents_line_of_fire",
            game=game,
        )
        if root is None or not isinstance(sr, dict):
            return False
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return False
        owner = getattr(self.army, "player", None) if self.army is not None else None
        if owner is not None and not self._unit_is_enemy_of_player(target_root, owner):
            return False
        model_candidates = []
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            model_candidates = list(get_models() or [])
        else:
            model_candidates = list(getattr(root, "models", []) or [])
        in_range = False
        for model in list(model_candidates or []):
            if model is None or bool(getattr(model, "_pending_placement", False)):
                continue
            alive_attr = getattr(model, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            if model_within_range_of_unit(model, target_root, 12.0):
                in_range = True
                break
        if not in_range:
            return False
        resolved_game_map = game_map
        if resolved_game_map is None:
            game_obj = game if game is not None else self._current_game()
            resolved_game_map = getattr(game_obj, "map", None) if game_obj is not None else None
        if resolved_game_map is None:
            return False
        friendly_units = list(getattr(resolved_game_map, "get_friendly_units", lambda _unit: [])(root) or [])
        if root not in friendly_units:
            friendly_units.append(root)
        owner_id = self._player_id(owner)
        for friendly in list(friendly_units or []):
            friendly_root = self._unit_root(friendly)
            if friendly_root is None or not self._unit_on_battlefield(friendly_root):
                continue
            get_parent_army = getattr(friendly_root, "get_parent_army", None)
            if not callable(get_parent_army):
                continue
            friendly_army = get_parent_army()
            friendly_player_id = self._player_id(getattr(friendly_army, "player", None))
            if owner_id and friendly_player_id and friendly_player_id != owner_id:
                continue
            if bool(resolved_game_map.is_within_engagement_range(friendly_root, target_root)):
                return True
        return False

    def selfless_bodyguard_redirect_models(self, unit, character_model, *, game=None) -> tuple[list, str]:
        root, sr = self._imperialis_fleet_phase_effect_state(
            unit,
            prefix="imperial_agents_selfless_bodyguard",
            game=game,
        )
        if root is None or not isinstance(sr, dict) or character_model is None:
            return [], ""
        character_parent = self._unit_root(getattr(character_model, "parent_unit", None))
        if character_parent is not root:
            return [], ""
        is_character = bool(getattr(character_model, "is_character", False))
        if not is_character:
            has_keyword = getattr(character_model, "has_keyword", None)
            is_character = bool(has_keyword("CHARACTER")) if callable(has_keyword) else False
        if not is_character:
            return [], ""
        get_bodyguards = getattr(root, "_get_bodyguard_support_models", None)
        bodyguards = list(get_bodyguards() or []) if callable(get_bodyguards) else list(getattr(root, "models", []) or [])
        eligible: list = []
        for model in list(bodyguards or []):
            if model is None or model is character_model or bool(getattr(model, "_pending_placement", False)):
                continue
            alive_attr = getattr(model, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            eligible.append(model)
        eligible.sort(key=lambda model: self._entity_id(model))
        if not eligible:
            return [], ""
        source = str(sr.get("imperial_agents_selfless_bodyguard_source", "") or "Selfless Bodyguard").strip()
        return eligible, source or "Selfless Bodyguard"

    def root_out_heresy_ranged_ignores_cover(self, model, *, attacker_unit=None, weapon_profile=None) -> tuple[bool, str]:
        del weapon_profile
        if not self.is_ordo_hereticus_purgation_force():
            return False, ""
        source_unit = self._unit_root(attacker_unit if attacker_unit is not None else getattr(model, "parent_unit", None))
        if source_unit is None:
            return False, ""
        if model is None or not self._model_in_army(model) or not self._unit_in_army(source_unit):
            return False, ""
        if not self._model_has_any_keyword(model, self._ROOT_OUT_HERESY_MODEL_KEYWORDS):
            return False, ""
        return True, self._ROOT_OUT_HERESY_NAME

    def root_out_heresy_sustained_hits_bonus(self, model, target_unit, *, attacker_unit=None) -> tuple[int, str]:
        if not self.is_ordo_hereticus_purgation_force():
            return 0, ""
        if target_unit is None:
            return 0, ""
        source_unit = self._unit_root(attacker_unit if attacker_unit is not None else getattr(model, "parent_unit", None))
        if source_unit is None:
            return 0, ""
        if model is None or not self._model_in_army(model) or not self._unit_in_army(source_unit):
            return 0, ""
        if not self._model_has_any_keyword(model, self._ROOT_OUT_HERESY_MODEL_KEYWORDS):
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return 0, ""
        owner = getattr(self.army, "player", None) if self.army is not None else None
        if owner is not None and not self._unit_is_enemy_of_player(target_root, owner):
            return 0, ""
        if not self._unit_has_keyword(target_root, "CHAOS"):
            return 0, ""
        if int(self._unit_alive_model_count(target_root) or 0) < 5:
            return 0, ""
        return 1, self._ROOT_OUT_HERESY_NAME

    def _destroy_the_daemonic_model_applies(self, model, *, attacker_unit=None) -> bool:
        if not self.is_ordo_malleus_daemon_hunters():
            return False
        source_unit = self._unit_root(attacker_unit if attacker_unit is not None else getattr(model, "parent_unit", None))
        if source_unit is None:
            return False
        if model is None or not self._model_in_army(model) or not self._unit_in_army(source_unit):
            return False
        return self._model_has_any_keyword(model, self._DESTROY_THE_DAEMONIC_MODEL_KEYWORDS)

    def destroy_the_daemonic_hit_reroll_ones(
        self,
        model,
        *,
        attacker_unit=None,
        target_unit=None,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[bool, str]:
        del target_unit, weapon_profile, attack_instance
        if not self._destroy_the_daemonic_model_applies(model, attacker_unit=attacker_unit):
            return False, ""
        return True, self._DESTROY_THE_DAEMONIC_NAME

    def destroy_the_daemonic_wound_reroll_ones(
        self,
        model,
        target_unit,
        *,
        attacker_unit=None,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[bool, str]:
        del weapon_profile, attack_instance
        if not self._destroy_the_daemonic_model_applies(model, attacker_unit=attacker_unit):
            return False, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return False, ""
        owner = getattr(self.army, "player", None) if self.army is not None else None
        if owner is not None and not self._unit_is_enemy_of_player(target_root, owner):
            return False, ""
        if not self._unit_has_keyword(target_root, "DAEMON"):
            return False, ""
        return True, self._DESTROY_THE_DAEMONIC_NAME

    def _grimoire_of_true_names_daemon_attack_penalty(self, attacker_unit, *, penalty_key: str) -> tuple[int, str]:
        if not self.is_ordo_malleus_daemon_hunters():
            return 0, ""
        attacker_root = self._unit_root(attacker_unit)
        if attacker_root is None:
            return 0, ""
        owner = getattr(self.army, "player", None) if self.army is not None else None
        if owner is not None and not self._unit_is_enemy_of_player(attacker_root, owner):
            return 0, ""
        for source_root in self._iter_unique_army_roots():
            for member in self._attached_members(source_root):
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict) or not bool(sr.get("enhancement_grimoire_of_true_names_aura", False)):
                    continue
                if not self._enhancement_bearer_alive(member):
                    continue
                required_keywords = [
                    str(value or "").strip().upper()
                    for value in list(sr.get("enhancement_grimoire_of_true_names_required_target_keywords", ("DAEMON",)) or ("DAEMON",))
                    if str(value or "").strip()
                ]
                if required_keywords and not self._unit_has_any_keyword(attacker_root, tuple(required_keywords)):
                    continue
                try:
                    aura_range = float(sr.get("enhancement_grimoire_of_true_names_aura_range", 9.0) or 9.0)
                except (TypeError, ValueError):
                    aura_range = 9.0
                if aura_range <= 0.0:
                    continue
                bearer_model = self._enhancement_bearer_model(member)
                if bearer_model is None:
                    continue
                if not model_within_range_of_unit(
                    bearer_model,
                    attacker_root,
                    float(aura_range),
                    use_attached_aggregate=True,
                ):
                    continue
                penalty = self._coerce_int(sr.get(penalty_key, 1), default=1)
                if penalty <= 0:
                    continue
                source_name = str(
                    sr.get("enhancement_grimoire_of_true_names_source", "") or self._GRIMOIRE_OF_TRUE_NAMES_AURA_NAME
                ).strip()
                return int(penalty), source_name or self._GRIMOIRE_OF_TRUE_NAMES_AURA_NAME
        return 0, ""

    def grimoire_of_true_names_hit_roll_penalty(
        self,
        attacker_unit,
        *,
        target_unit=None,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        del target_unit, weapon_profile, attack_instance
        return self._grimoire_of_true_names_daemon_attack_penalty(
            attacker_unit,
            penalty_key="enhancement_grimoire_of_true_names_daemon_hit_roll_penalty",
        )

    def grimoire_of_true_names_wound_roll_penalty(
        self,
        attacker_unit,
        *,
        target_unit=None,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[int, str]:
        del target_unit, weapon_profile, attack_instance
        return self._grimoire_of_true_names_daemon_attack_penalty(
            attacker_unit,
            penalty_key="enhancement_grimoire_of_true_names_daemon_wound_roll_penalty",
        )

    def witch_hunter_hit_reroll(
        self,
        model,
        *,
        attacker_unit=None,
        target_unit=None,
        weapon_profile=None,
        attack_instance=None,
    ) -> tuple[bool, str]:
        del weapon_profile, attack_instance
        if not self.is_ordo_hereticus_purgation_force():
            return False, ""
        source_root = self._unit_root(attacker_unit if attacker_unit is not None else getattr(model, "parent_unit", None))
        if source_root is None:
            return False, ""
        if model is None or not self._model_in_army(model) or not self._unit_in_army(source_root):
            return False, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return False, ""
        owner = getattr(self.army, "player", None) if self.army is not None else None
        if owner is not None and not self._unit_is_enemy_of_player(target_root, owner):
            return False, ""
        for member in self._attached_members(source_root):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_witch_hunter", False)):
                continue
            if bool(sr.get("enhancement_witch_hunter_requires_bearer_leading", True)) and member is source_root:
                continue
            if not self._enhancement_bearer_alive(member):
                continue
            required_keywords = [
                str(value or "").strip().upper()
                for value in list(sr.get("enhancement_witch_hunter_required_target_keywords", ("PSYKER",)) or ("PSYKER",))
                if str(value or "").strip()
            ]
            if required_keywords and not self._unit_has_any_keyword(target_root, tuple(required_keywords)):
                continue
            source_name = str(sr.get("enhancement_witch_hunter_source", "") or self._WITCH_HUNTER_NAME).strip()
            return True, source_name or self._WITCH_HUNTER_NAME
        return False, ""

    def _iter_unique_army_roots(self) -> list:
        if self.army is None:
            return []
        roots: list = []
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            rid = str(get_entity_id(root) or "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            roots.append(root)
        roots.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return roots

    def _unit_is_officio_assassinorum(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_has_keyword(unit, "OFFICIO ASSASSINORUM"):
            return False
        return True

    def _unit_has_attached_character(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        attached_leaders = list(getattr(root, "attached_leaders", []) or [])
        if attached_leaders:
            return True
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for model in list(models or []):
            if model is None or bool(getattr(model, "_pending_placement", False)):
                continue
            alive_attr = getattr(model, "is_alive", True)
            if not bool(alive_attr() if callable(alive_attr) else alive_attr):
                continue
            if bool(getattr(model, "is_character", False)):
                return True
            has_keyword = getattr(model, "has_keyword", None)
            if callable(has_keyword) and bool(has_keyword("CHARACTER")):
                return True
        return False

    @staticmethod
    def _model_ability_name_keys(model) -> set[str]:
        abilities = getattr(model, "abilities", None)
        if not isinstance(abilities, dict):
            return set()
        names = set()
        for key in list(abilities.keys()):
            name_key = ImperialAgentsDetachmentManager._normalize_name(str(key or ""))
            if name_key:
                names.add(name_key)
        return names

    def _ability_name_keys_for_model(self, unit, model) -> set[str]:
        names = set(self._model_ability_name_keys(model))
        if unit is None or model is None:
            return names
        iter_fn = getattr(unit, "_iter_model_specific_ability_entries", None)
        if not callable(iter_fn):
            return names
        for name, _desc in list(iter_fn(model) or []):
            name_key = self._normalize_name(str(name or ""))
            if name_key:
                names.add(name_key)
        return names

    def _ensure_model_extra_use(self, model, key: str, *, count: int = 1) -> None:
        if model is None:
            return
        key_norm = str(key or "").strip().lower()
        if not key_norm:
            return
        desired = max(0, int(count or 0))
        if desired <= 0:
            return
        extra = getattr(model, "_once_per_battle_extra_uses", None)
        if not isinstance(extra, dict):
            extra = {}
        try:
            current = int(extra.get(key_norm, 0) or 0)
        except Exception:
            current = 0
        add = desired - current
        if add <= 0:
            return
        grant_fn = getattr(model, "grant_once_per_battle_extra_use", None)
        if callable(grant_fn):
            grant_fn(key_norm, uses=int(add))

    def apply_extremis_sanction_extra_uses(self, unit=None) -> None:
        if not self.is_veiled_blade_elimination_force():
            return
        roots: list
        if unit is None:
            roots = self._iter_unique_army_roots()
        else:
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            roots = [root] if root is not None else []

        for root in list(roots or []):
            if root is None or not self._unit_is_officio_assassinorum(root):
                continue
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            for model in list(models or []):
                if model is None:
                    continue
                ability_name_keys = self._ability_name_keys_for_model(root, model)
                if not ability_name_keys:
                    continue
                for ability_name, once_per_battle_key in self._EXTREMIS_EXTRA_USE_KEY_BY_ABILITY_NAME.items():
                    if ability_name not in ability_name_keys:
                        continue
                    self._ensure_model_extra_use(model, once_per_battle_key, count=1)

    def extremis_sanction_points_surcharge_for_unit(self, unit) -> int:
        if not self.is_veiled_blade_elimination_force():
            return 0
        if unit is None:
            return 0
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None or not self._unit_is_officio_assassinorum(root):
            return 0
        unit_name_key = self._normalize_name(str(getattr(root, "name", "") or ""))
        return int(self._EXTREMIS_SURCHARGE_BY_UNIT_NAME.get(unit_name_key, 0) or 0)

    def validate_detachment_rules(self) -> list[str]:
        self.apply_extremis_sanction_extra_uses()
        return []
