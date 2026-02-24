from __future__ import annotations

import re
from typing import Optional

from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class ImperialAgentsDetachmentManager(DetachmentManagerBase):
    faction_id = "AOI"
    _IMPERIALIS_FLEET_DETACHMENT_NAME = "Imperialis Fleet"
    _AT_ALL_COSTS_NAME = "At all Costs"
    _AT_ALL_COSTS_ABILITY_KEY = "imperialis_fleet_at_all_costs"
    _AT_ALL_COSTS_MODE_ELIMINATE = "eliminate"
    _AT_ALL_COSTS_MODE_ACQUIRE = "acquire"
    _ORDO_HERETICUS_PURGATION_FORCE_DETACHMENT_NAME = "Ordo Hereticus Purgation Force"
    _ROOT_OUT_HERESY_NAME = "Root out Heresy"
    _ROOT_OUT_HERESY_MODEL_KEYWORDS = (
        "ADEPTUS ARBITES",
        "INQUISITOR",
        "INQUISITORIAL AGENTS",
        "ORDO HERETICUS",
    )
    _ORDO_MALLEUS_DAEMON_HUNTERS_DETACHMENT_NAME = "Ordo Malleus Daemon Hunters"
    _DESTROY_THE_DAEMONIC_NAME = "Destroy the Daemonic"
    _DESTROY_THE_DAEMONIC_MODEL_KEYWORDS = (
        "INQUISITOR",
        "INQUISITORIAL AGENTS",
        "ORDO MALLEUS",
    )
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

    @staticmethod
    def _normalize_name(value: str) -> str:
        text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _entity_id(entity) -> str:
        return str(get_entity_id(entity) or "")

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
