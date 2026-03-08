from typing import List, Tuple, Dict, Any, Optional, TYPE_CHECKING
import logging
from abc import ABC, abstractmethod

from .game import Game
from .decision_kinds import DECISION_MOVE_UNIT
from .decisions import DecisionOption, DecisionRequest
from .decision_requests import (
    build_deployment_zone_request,
    build_reserves_allocation_request,
    build_select_next_deploy_unit_request,
    canonical_deployment_zone_key,
)
from ..roster.player import Player
from ..utility.calcs import get_dist
from ..utility.decision_utils import resolve_decision_command
from ..utility.dice import get_dice_roll
from ..utility.entity_ids import get_entity_id
from .missions import OfficialMission, MissionRegistry, DeploymentZoneType, create_objectives_from_mission

if TYPE_CHECKING:
    from ..units.unit import Unit

logger = logging.getLogger(__name__)


class DeploymentDecisionMaker(ABC):
    """Abstract base class for making deployment decisions (UI or external controller)."""
    
    @abstractmethod
    def choose_deployment_zone(self, available_zones: List[dict]) -> dict:
        """Choose deployment zone as the defender."""
        pass
    
    @abstractmethod
    def declare_reserves(self, player: Player) -> dict:
        """Decide which units go into reserves, strategic reserves, or deploy normally."""
        pass
    
    @abstractmethod
    def choose_unit_deployment_position(self, unit: 'Unit', deployment_zone: dict, 
                                       already_deployed: List['Unit']) -> Tuple[float, float]:
        """Choose where to deploy a specific unit within the deployment zone."""
        pass

    def choose_next_deploy_unit(
        self,
        deployable_units: List['Unit'],
        deployment_zone: dict,
        already_deployed: List['Unit'],
    ) -> 'Unit':
        """Choose which unit to deploy next when multiple are available."""
        if not deployable_units:
            raise ValueError("No deployable units provided.")
        return deployable_units[0]


class DeploymentManager:
    """Manages the official Warhammer 40k 10th Edition deployment sequence."""
    
    def __init__(self, game: Game, mission_name: str = "Crucible of Battle"):
        self.game = game
        self.mission = MissionRegistry.get_mission(mission_name)
        self.attacker = None
        self.defender = None
        self.deployment_zones = []
        logger.info(f"DeploymentManager initialized with mission: {self.mission.name}")
        
    def execute_deployment_sequence(self, decision_makers: Dict[str, DeploymentDecisionMaker]) -> dict:
        """Execute the complete deployment sequence according to Warhammer 40k rules.
        
        Args:
            decision_makers: Dict mapping player ids to their DeploymentDecisionMaker instances
        """
        deployment_results = {
            'attacker': None,
            'defender': None,
            'first_turn_player': None,
            'deployment_zones': {},
            'reserves': {},
            'deployment_positions': {}
        }
        
        logger.info("Starting Official Warhammer 40k Deployment Sequence")
        players_by_id = {p.id: p for p in (self.game.players or []) if p is not None}
        
        # Step 1: Determine Attacker and Defender
        self.attacker, self.defender = self.determine_attacker_and_defender()
        deployment_results['attacker'] = self.attacker.id
        deployment_results['defender'] = self.defender.id
        logger.info(f"Attacker: {self.attacker.name}, Defender: {self.defender.name}")
        
        # Step 2: Use pre-configured deployment zones (ensures consistency)
        if hasattr(self.game, 'deployment_zones') and self.game.deployment_zones:
            # Use zones already set up in the game (ensures consistency across all game types)
            logger.info("Using pre-configured deployment zones for consistency")
            
            # Convert the game's deployment zones to the format expected by the deployment system
            available_zones = []
            for player_id, zone in self.game.deployment_zones.items():
                player_label = getattr(players_by_id.get(player_id), "name", player_id)
                zone_copy = zone.copy()
                zone_copy['name'] = f"{player_label}'s Zone"
                available_zones.append(zone_copy)
            
            # Assign zones - defender chooses first
            defender_decision_maker = decision_makers[self.defender.id]
            defender_zone = self._resolve_deployment_zone_decision(
                self.defender,
                defender_decision_maker,
                available_zones,
            )
            attacker_zone = next(zone for zone in available_zones if zone is not defender_zone)
            
            deployment_results['deployment_zones'][self.defender.id] = defender_zone
            deployment_results['deployment_zones'][self.attacker.id] = attacker_zone
            # Keep game-level deployment zone mapping aligned with selected zones so
            # deployment legality checks use the same assignment during placement.
            self.game.deployment_zones = {
                self.defender.id: defender_zone,
                self.attacker.id: attacker_zone,
            }
        else:
            # Default: create standard zones if none exist
            logger.warning("No pre-configured zones found, creating standard zones")
            available_zones = self.create_deployment_zones()
            defender_decision_maker = decision_makers[self.defender.id]
            defender_zone = self._resolve_deployment_zone_decision(
                self.defender,
                defender_decision_maker,
                available_zones,
            )
            attacker_zone = next(zone for zone in available_zones if zone is not defender_zone)
            
            deployment_results['deployment_zones'][self.defender.id] = defender_zone
            deployment_results['deployment_zones'][self.attacker.id] = attacker_zone
            
            # Store deployment zones in the game for visualization
            self.game.deployment_zones = {
                self.defender.id: defender_zone,
                self.attacker.id: attacker_zone
            }
        
        logger.info(f"{self.defender.name} chose deployment zone, {self.attacker.name} gets the other")
        
        # Step 3: Declare Reserves & Strategic Reserves (simultaneously)
        defender_reserves = self._resolve_reserves_decisions(self.defender, defender_decision_maker)
        attacker_decision_maker = decision_makers[self.attacker.id]
        attacker_reserves = self._resolve_reserves_decisions(self.attacker, attacker_decision_maker)
        
        deployment_results['reserves'][self.defender.id] = defender_reserves
        deployment_results['reserves'][self.attacker.id] = attacker_reserves
        
        logger.info(f"Reserves declared - {self.defender.name}: {sum(1 for d in defender_reserves.values() if d != 'deploy')} units, "
                   f"{self.attacker.name}: {sum(1 for d in attacker_reserves.values() if d != 'deploy')} units")
        
        # Step 4: Alternating Deployment (Defender first)
        self.execute_alternating_deployment(deployment_results, decision_makers)
        
        # Step 5: Determine First Turn
        first_turn_player = self.determine_first_turn()
        deployment_results['first_turn_player'] = first_turn_player.id
        
        # Set the game's current player to the first turn player
        if first_turn_player == self.game.players[0]:
            self.game.current_player_index = 0
        else:
            self.game.current_player_index = 1
        
        logger.info(f"{first_turn_player.name} will take the first turn")
        logger.info("Deployment sequence complete!")
        
        self.set_reserves_status(deployment_results)
        
        return deployment_results
    
    def determine_attacker_and_defender(self) -> Tuple[Player, Player]:
        """Roll off to determine attacker and defender."""
        player1_roll = get_dice_roll(6)
        player2_roll = get_dice_roll(6)
        
        logger.info(
            f"Attacker/Defender roll-off: {self.game.players[0].name}={player1_roll}, "
            f"{self.game.players[1].name}={player2_roll}"
        )
        
        # Re-roll ties
        while player1_roll == player2_roll:
            player1_roll = get_dice_roll(6)
            player2_roll = get_dice_roll(6)
            logger.info(
                f"Tie! Re-rolling: {self.game.players[0].name}={player1_roll}, {self.game.players[1].name}={player2_roll}"
            )
        
        if player1_roll > player2_roll:
            return self.game.players[0], self.game.players[1]  # Player 1 is attacker
        else:
            return self.game.players[1], self.game.players[0]  # Player 2 is attacker
    
    def create_deployment_zones(self) -> List[dict]:
        """Create deployment zones based on the selected mission."""
        # Convert mission deployment zones to the format expected by the game.
        # Deployment legality is always evaluated against mission polygon zones (no legacy x/y ranges).
        zones = []
        
        # Group zones by type
        defender_zones = self.mission.get_defender_zones()
        attacker_zones = self.mission.get_attacker_zones()
        
        # For missions with multiple zones per side, combine them into compound zones
        if defender_zones:
            # Create a compound defender zone that includes all defender areas
            defender_zone = {
                'name': 'Defender Zone',
                'zone_type': 'defender',
                'mission_zones': defender_zones,  # Store original zones for detailed checking
            }
            zones.append(defender_zone)
        
        if attacker_zones:
            # Create a compound attacker zone
            attacker_zone = {
                'name': 'Attacker Zone', 
                'zone_type': 'attacker',
                'mission_zones': attacker_zones,
            }
            zones.append(attacker_zone)
        
        return zones

    def _resolve_reserves_decisions(self, player: Player, decision_maker: DeploymentDecisionMaker) -> dict:
        army = player.get_army()
        if army is None:
            return {}
        decisions = dict(decision_maker.declare_reserves(player) or {})
        request = build_reserves_allocation_request(self.game, army)
        if request is None:
            return decisions
        option_id = request.options[0].option_id if getattr(request, "options", None) else ""
        buckets = {"deploy": [], "reserves": [], "strategic_reserves": []}
        for unit_id, status in decisions.items():
            unit_key = str(unit_id)
            choice = str(status or "deploy")
            if choice not in buckets:
                choice = "deploy"
            buckets[choice].append(unit_key)
        queue = getattr(self.game, "decision_queue", None)
        pending = queue.get(request.decision_id) if queue is not None and hasattr(queue, "get") else request
        if pending is not None:
            apply_result = resolve_decision_command(
                self.game,
                request,
                option_id,
                result_payload={"unit_ids_by_bucket": buckets},
                player_id=getattr(player, "id", None),
            )
            if not bool(getattr(apply_result, "ok", False)):
                errors = tuple(getattr(apply_result, "errors", ()) or ())
                raise RuntimeError(
                    f"Reserves allocation decision rejected for player {getattr(player, 'name', 'Player')}: {list(errors)}"
                )
        return decisions

    def _resolve_deployment_zone_decision(
        self,
        player: Player,
        decision_maker: DeploymentDecisionMaker,
        available_zones: List[dict],
    ) -> dict:
        if not available_zones:
            raise RuntimeError("Deployment zone choice requires at least one available zone.")
        request = build_deployment_zone_request(self.game, player, available_zones, queue_requests=True)
        chosen_zone = decision_maker.choose_deployment_zone(list(available_zones))
        if not isinstance(chosen_zone, dict):
            raise RuntimeError(
                f"Deployment zone choice for {player.name} must return a zone dict."
            )
        if request is None:
            for zone in available_zones:
                if zone == chosen_zone:
                    return zone
            raise RuntimeError(f"Deployment zone choice for {player.name} did not match any available zone.")
        selected_option = self._matching_zone_option(request, chosen_zone, available_zones)
        if selected_option is None:
            raise RuntimeError(
                f"Deployment zone choice for {player.name} did not match any request option."
            )
        queue = getattr(self.game, "decision_queue", None)
        pending = queue.get(request.decision_id) if queue is not None and hasattr(queue, "get") else request
        if pending is not None:
            apply_result = resolve_decision_command(
                self.game,
                request,
                selected_option.option_id,
                result_payload={},
                player_id=getattr(player, "id", None),
            )
            if not bool(getattr(apply_result, "ok", False)):
                errors = tuple(getattr(apply_result, "errors", ()) or ())
                raise RuntimeError(
                    f"Deployment zone decision rejected for player {getattr(player, 'name', 'Player')}: {list(errors)}"
                )
        return self._zone_from_option(selected_option, available_zones)

    def _matching_zone_option(
        self,
        request: DecisionRequest,
        chosen_zone: dict,
        available_zones: List[dict],
    ) -> Optional[DecisionOption]:
        chosen_key = canonical_deployment_zone_key(dict(chosen_zone or {}))
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            option_key = str(payload.get("zone_key", "") or "")
            if option_key and option_key != chosen_key:
                continue
            option_zone = self._zone_from_option(option, available_zones)
            if option_zone is chosen_zone:
                return option
            if option_zone == chosen_zone:
                return option
        return None

    def _zone_from_option(self, option: DecisionOption, available_zones: List[dict]) -> dict:
        payload = dict(getattr(option, "payload", {}) or {})
        zone_index = payload.get("zone_index", None)
        try:
            idx = int(zone_index)
        except (TypeError, ValueError):
            idx = -1
        if 0 <= idx < len(available_zones):
            return available_zones[idx]
        zone_key = str(payload.get("zone_key", "") or "")
        if zone_key:
            for zone in available_zones:
                if canonical_deployment_zone_key(dict(zone or {})) == zone_key:
                    return zone
        raise RuntimeError("Deployment zone option did not map to an available zone.")

    def _resolve_next_deploy_unit_choice(
        self,
        player: Player,
        decision_maker: DeploymentDecisionMaker,
        deployable_units: List['Unit'],
        deployment_zone: dict,
        already_deployed: List['Unit'],
    ) -> 'Unit':
        if not deployable_units:
            raise RuntimeError("Cannot select next deployment unit from an empty list.")
        request = build_select_next_deploy_unit_request(
            self.game,
            player,
            deployable_units,
            deployment_zone=deployment_zone,
            queue_requests=True,
        )
        chosen_unit = decision_maker.choose_next_deploy_unit(
            list(deployable_units),
            deployment_zone,
            list(already_deployed),
        )
        try:
            chosen_unit_id = str(get_entity_id(chosen_unit) or "")
        except ValueError as exc:
            raise RuntimeError("Deployment unit selection returned an unknown unit.") from exc
        if not chosen_unit_id:
            raise RuntimeError("Deployment unit selection returned an invalid unit id.")
        if request is not None:
            selected_option = None
            for option in list(getattr(request, "options", []) or []):
                payload = dict(getattr(option, "payload", {}) or {})
                if str(payload.get("unit_id", "") or "") == chosen_unit_id:
                    selected_option = option
                    break
            if selected_option is None:
                raise RuntimeError(
                    f"Deployment unit selection for {player.name} returned unknown unit id: {chosen_unit_id}"
                )
            queue = getattr(self.game, "decision_queue", None)
            pending = queue.get(request.decision_id) if queue is not None and hasattr(queue, "get") else request
            if pending is not None:
                apply_result = resolve_decision_command(
                    self.game,
                    request,
                    selected_option.option_id,
                    result_payload={},
                    player_id=getattr(player, "id", None),
                )
                if not bool(getattr(apply_result, "ok", False)):
                    errors = tuple(getattr(apply_result, "errors", ()) or ())
                    raise RuntimeError(
                        f"Deployment unit selection rejected for {getattr(player, 'name', 'Player')}: {list(errors)}"
                    )
        for unit in list(deployable_units or []):
            if str(get_entity_id(unit) or "") == chosen_unit_id:
                return unit
        raise RuntimeError(f"Deployment unit selection resolved to unknown unit id: {chosen_unit_id}")

    def _pop_selected_deploy_unit(self, deployable_units: List['Unit'], selected_unit: 'Unit') -> None:
        for idx, candidate in enumerate(list(deployable_units or [])):
            if candidate is selected_unit:
                deployable_units.pop(idx)
                return
        selected_id = str(get_entity_id(selected_unit) or "")
        for idx, candidate in enumerate(list(deployable_units or [])):
            if str(get_entity_id(candidate) or "") == selected_id:
                deployable_units.pop(idx)
                return
        raise RuntimeError(f"Selected deployment unit not found in deployable list: {selected_id}")

    def _build_deployment_move_request(self, unit: 'Unit') -> DecisionRequest:
        unit_id = get_entity_id(unit)
        options = [
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit_id, "movement_type": "deploy", "action": "confirm"},
            )
        ]
        player_id = None
        army = getattr(unit, "get_parent_army", None)
        if callable(army):
            army = army()
        else:
            army = getattr(unit, "parent_army", None)
        if army is not None:
            player = getattr(army, "player", None)
            player_id = getattr(player, "id", None) if player is not None else None
        allowed_model_ids = [get_entity_id(m) for m in list(getattr(unit, "models", []) or [])]
        context = {
            "unit_id": unit_id,
            "movement_type": "deploy",
            "placement_kind": "deployment",
            "allowed_model_ids": allowed_model_ids,
            "allow_skip": False,
            "max_distance": 0.0,
        }
        return DecisionRequest.create(
            DECISION_MOVE_UNIT,
            f"Deploy {getattr(unit, 'name', 'Unit')}",
            player_id=player_id,
            options=options,
            context=context,
        )

    def _build_deployment_model_positions(
        self,
        unit: 'Unit',
        position: Tuple[float, float],
        decision_maker: DeploymentDecisionMaker | None = None,
    ) -> List[dict]:
        x, y = position
        if decision_maker is not None:
            custom_builder = getattr(decision_maker, "build_deployment_model_positions", None)
            if callable(custom_builder):
                payload_positions = list(custom_builder(unit, (float(x), float(y))) or [])
                if payload_positions:
                    return payload_positions
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            raise RuntimeError("Deployment requires an active game map.")
        use_repulsors = True
        has_infiltrate = getattr(unit, "has_infiltrate", None)
        if callable(has_infiltrate) and has_infiltrate():
            use_repulsors = False
        boundary_repulsors = None
        if use_repulsors:
            repulsor_fn = getattr(self.game, "get_boundary_repulsors", None)
            if callable(repulsor_fn):
                boundary_repulsors = repulsor_fn(unit, context="deployment")
        model_positions = unit.calculate_model_positions(
            x,
            y,
            game_map,
            avoid_friendly_units=False,
            boundary_repulsors=boundary_repulsors,
        )
        if not model_positions or len(model_positions) != len(getattr(unit, "models", []) or []):
            raise RuntimeError(f"Unable to calculate deployment positions for {getattr(unit, 'name', 'Unit')}.")
        payload_positions: List[dict] = []
        for model, pos in zip(unit.models, model_positions):
            model_id = get_entity_id(model)
            model_x, model_y, model_z, model_facing = pos
            payload_positions.append(
                {
                    "model_id": model_id,
                    "position": [float(model_x), float(model_y), float(model_z)],
                    "facing": float(model_facing),
                }
            )
        return payload_positions
    
    def setup_mission_objectives(self) -> None:
        """Set up objectives based on the selected mission."""
        # Create objectives from mission markers
        objectives = create_objectives_from_mission(self.mission, self.game)
        
        # Add objectives to the game and map
        self.game.objectives = objectives
        self.game.map.add_objectives(objectives)
        
        logger.info(f"Added {len(objectives)} objectives from mission: {self.mission.name}")
        for obj in objectives:
            if hasattr(obj.location, 'x'):
                logger.info(f"  - {obj.name} at ({obj.location.x:.1f}, {obj.location.y:.1f})")
    
    def execute_alternating_deployment(self, deployment_results: dict, 
                                     decision_makers: Dict[str, DeploymentDecisionMaker]) -> None:
        """Execute alternating deployment starting with the defender."""
        defender_zone = deployment_results['deployment_zones'][self.defender.id]
        attacker_zone = deployment_results['deployment_zones'][self.attacker.id]
        
        def _is_attached_leader(u) -> bool:
            try:
                return bool(getattr(u, "is_leader", False)) and getattr(u, "attached_to", None) is not None
            except Exception:
                return False
        def _is_joined_support(u) -> bool:
            try:
                return bool(getattr(u, "is_joined_support", False))
            except Exception:
                return False

        # Get units to deploy (not in reserves). Attached Leaders deploy as part of their Bodyguard.
        defender_units = [
            unit for unit in self.defender.get_army().units
            if (not _is_attached_leader(unit)) and (not _is_joined_support(unit))
            and deployment_results['reserves'][self.defender.id].get(unit.id, 'deploy') == 'deploy'
            and not bool(getattr(unit, "must_start_in_reserves", lambda: False)())
        ]
        attacker_units = [
            unit for unit in self.attacker.get_army().units
            if (not _is_attached_leader(unit)) and (not _is_joined_support(unit))
            and deployment_results['reserves'][self.attacker.id].get(unit.id, 'deploy') == 'deploy'
            and not bool(getattr(unit, "must_start_in_reserves", lambda: False)())
        ]
        
        logger.info(f"Alternating deployment: {len(defender_units)} vs {len(attacker_units)} units")
        
        # Track deployment order and positions
        deployment_order = []
        defender_deployed = []
        attacker_deployed = []
        
        # Defender starts
        current_player = self.defender
        current_units = defender_units
        current_zone = defender_zone
        current_decision_maker = decision_makers[self.defender.id]
        current_deployed = defender_deployed

        # Special rule: If a player sets up a TITANIC unit when it is their turn to set up a unit,
        # they skip their next turn to set up a unit (opponent deploys twice in a row).
        deployment_skip_turns = {self.defender: 0, self.attacker: 0}
        
        turn_count = 0
        while defender_units or attacker_units:
            if current_units:
                # Select and deploy next unit through the decision API.
                unit = self._resolve_next_deploy_unit_choice(
                    current_player,
                    current_decision_maker,
                    current_units,
                    current_zone,
                    current_deployed,
                )
                self._pop_selected_deploy_unit(current_units, unit)
                position = current_decision_maker.choose_unit_deployment_position(unit, current_zone, current_deployed)

                # Route deployment placement through DecisionRequest/Command API.
                request = self._build_deployment_move_request(unit)
                self.game.request_decision(request)
                model_positions = self._build_deployment_model_positions(
                    unit,
                    position,
                    decision_maker=current_decision_maker,
                )
                option_id = request.options[0].option_id if getattr(request, "options", None) else ""
                queue = getattr(self.game, "decision_queue", None)
                pending = queue.get(request.decision_id) if queue is not None and hasattr(queue, "get") else request
                if pending is not None:
                    apply_result = resolve_decision_command(
                        self.game,
                        request,
                        option_id,
                        result_payload={"model_positions": model_positions},
                        player_id=getattr(request, "player_id", None),
                    )
                    if not bool(getattr(apply_result, "ok", False)):
                        errors = tuple(getattr(apply_result, "errors", ()) or ())
                        raise RuntimeError(
                            f"Deployment placement rejected for {getattr(unit, 'name', 'Unit')}: {list(errors)}"
                        )
                elif not bool(getattr(unit, "deployed", False)):
                    raise RuntimeError(
                        f"Deployment placement unresolved for {getattr(unit, 'name', 'Unit')}: "
                        "decision was consumed by another controller but unit is not deployed."
                    )
                current_deployed.append(unit)
                deployment_order.append((current_player.id, unit.id, position))
                
                logger.info(f"{current_player.name} deploys {unit.name} at ({position[0]:.1f}, {position[1]:.1f})")

                if unit.is_titanic:
                    deployment_skip_turns[current_player] = int(deployment_skip_turns.get(current_player, 0)) + 1
            
            # Switch to other player
            turn_count += 1
            if current_player == self.defender:
                current_player = self.attacker
                current_units = attacker_units
                current_zone = attacker_zone  
                current_decision_maker = decision_makers[self.attacker.id]
                current_deployed = attacker_deployed
            else:
                current_player = self.defender
                current_units = defender_units
                current_zone = defender_zone
                current_decision_maker = decision_makers[self.defender.id]
                current_deployed = defender_deployed

            # Apply skip-turn rule if it would still allow the other player to deploy.
            # (If the other player has no units left, ignore the skip to avoid stalling deployment.)
            other_units_remaining = bool(attacker_units) if current_player == self.defender else bool(defender_units)
            while int(deployment_skip_turns.get(current_player, 0) or 0) > 0 and other_units_remaining:
                deployment_skip_turns[current_player] = int(deployment_skip_turns[current_player]) - 1
                if current_player == self.defender:
                    current_player = self.attacker
                    current_units = attacker_units
                    current_zone = attacker_zone  
                    current_decision_maker = decision_makers[self.attacker.id]
                    current_deployed = attacker_deployed
                else:
                    current_player = self.defender
                    current_units = defender_units
                    current_zone = defender_zone
                    current_decision_maker = decision_makers[self.defender.id]
                    current_deployed = defender_deployed
                other_units_remaining = bool(attacker_units) if current_player == self.defender else bool(defender_units)
        
        deployment_results['deployment_order'] = deployment_order
    
    def deploy_unit(self, unit: 'Unit', position: Tuple[float, float], zone: dict) -> None:
        """Deploy a unit at the specified position."""
        x, y = position
        z = self.game.map.get_height_at_point(x, y)
        
        # Calculate model positions within the unit
        # During deployment, use relaxed friendly unit avoidance to allow tighter formations
        model_positions = unit.calculate_model_positions(x, y, self.game.map, avoid_friendly_units=False)
        
        if model_positions and len(model_positions) == len(unit.models):
            # Use calculated positions
            for model, pos in zip(unit.models, model_positions):
                model_x, model_y, model_z, model_facing = pos
                model.set_location(model_x, model_y, model_z, model_facing)
        else:
            # Default positioning
            for i, model in enumerate(unit.models):
                model_x = x + (i % 3) * 0.5
                model_y = y + (i // 3) * 0.5
                model_z = self.game.map.get_height_at_point(model_x, model_y)
                model.set_location(model_x, model_y, model_z, 0.0)
        
        unit.deployed = True
        # Attached Leaders deploy together with the Bodyguard.
        try:
            for l in list(getattr(unit, "attached_leaders", []) or []):
                l.deployed = True
                l.reserve_status = getattr(unit, "reserve_status", "deployed")
                l.reserve_turn_deployed = getattr(unit, "reserve_turn_deployed", None)
        except Exception:
            pass
        self.game.map.units.append(unit)
    
    def determine_first_turn(self) -> Player:
        """Determine who goes first according to Warhammer 40k rules."""
        # Attacker rolls D6: 1-3 = Defender goes first, 4-6 = Attacker goes first
        roll = get_dice_roll(6)
        logger.info(f"First turn roll: {roll}")
        
        if roll <= 3:
            logger.info(f"{self.defender.name} (Defender) takes first turn")
            return self.defender
        else:
            logger.info(f"{self.attacker.name} (Attacker) takes first turn")
            return self.attacker

    def set_reserves_status(self, deployment_results: dict) -> None:
        """Set the reserve status for all units based on deployment decisions."""
        for player in (self.attacker, self.defender):
            if player is None:
                continue
            reserves_decisions = deployment_results['reserves'].get(player.id, {})
            
            for unit in player.get_army().units:
                # Attached Leaders follow their Bodyguard's reserve decision.
                try:
                    if bool(getattr(unit, "is_leader", False)) and getattr(unit, "attached_to", None) is not None:
                        continue
                except Exception:
                    pass
                reserve_decision = reserves_decisions.get(unit.id, 'deploy')
                try:
                    if bool(getattr(unit, "must_start_in_reserves", lambda: False)()):
                        if reserve_decision != "reserves":
                            logger.info(f"{unit.name} forced into Reserves (AIRCRAFT)")
                        reserve_decision = "reserves"
                except Exception:
                    pass
                applied_decision = reserve_decision
                allow_fn = getattr(player.get_army(), "_ride_the_wind_allows_standard_reserves", None)
                if reserve_decision == "reserves" and callable(allow_fn) and bool(allow_fn(unit)):
                    # Ride the Wind: units selected as "Reserves" arrive and set up using Strategic Reserves rules.
                    applied_decision = "strategic_reserves"
                started = applied_decision in ('reserves', 'strategic_reserves')
                
                if applied_decision == 'deploy':
                    unit.set_reserve_status('deployed')
                elif applied_decision == 'reserves':
                    unit.set_reserve_status('reserves')
                    logger.info(f"{unit.name} placed in standard reserves")
                elif applied_decision == 'strategic_reserves':
                    unit.set_reserve_status('strategic_reserves')
                    logger.info(f"{unit.name} placed in strategic reserves")
                else:
                    # Default to deployed for any unknown status
                    unit.set_reserve_status('deployed')
                    started = False

                # AIRCRAFT TRANSPORT rule: passengers must also start in Reserves
                try:
                    is_transport = bool(getattr(unit, "is_transport", False))
                    must_reserves = bool(getattr(unit, "must_start_in_reserves", lambda: False)())
                except Exception:
                    is_transport = False
                    must_reserves = False
                if is_transport and must_reserves and applied_decision in ("reserves", "strategic_reserves"):
                    try:
                        passengers = list(getattr(unit, "transport_passengers", []) or [])
                    except Exception:
                        passengers = []
                    for p in passengers:
                        try:
                            if hasattr(p, "set_reserve_status"):
                                p.set_reserve_status("reserves")
                            else:
                                p.reserve_status = "reserves"
                        except Exception:
                            pass
                        try:
                            p.deployed = True
                        except Exception:
                            pass
                        try:
                            setattr(p, "_started_in_reserves", True)
                        except Exception:
                            pass
                        try:
                            for l in list(getattr(p, "attached_leaders", []) or []):
                                setattr(l, "_started_in_reserves", True)
                        except Exception:
                            pass

                # Chapter Approved: round-3 destruction only applies to units that STARTED in reserves.
                try:
                    setattr(unit, "_started_in_reserves", bool(started))
                except Exception:
                    pass
                # Propagate to attached leaders and embarked passengers (best-effort group semantics).
                try:
                    for l in list(getattr(unit, "attached_leaders", []) or []):
                        setattr(l, "_started_in_reserves", bool(started))
                except Exception:
                    pass
                try:
                    if bool(getattr(unit, "is_transport", False)):
                        for p in list(getattr(unit, "transport_passengers", []) or []):
                            try:
                                setattr(p, "_started_in_reserves", bool(started))
                            except Exception:
                                pass
                            try:
                                for l in list(getattr(p, "attached_leaders", []) or []):
                                    setattr(l, "_started_in_reserves", bool(started))
                            except Exception:
                                pass
                except Exception:
                    pass

            # Final enforcement: AIRCRAFT TRANSPORT passengers must start in Reserves.
            try:
                for unit in player.get_army().units:
                    try:
                        if not bool(getattr(unit, "is_transport", False)):
                            continue
                        if not bool(getattr(unit, "must_start_in_reserves", lambda: False)()):
                            continue
                        if str(getattr(unit, "reserve_status", "deployed")) not in ("reserves", "strategic_reserves"):
                            continue
                    except Exception:
                        continue
                    try:
                        passengers = list(getattr(unit, "transport_passengers", []) or [])
                    except Exception:
                        passengers = []
                    for p in passengers:
                        try:
                            if hasattr(p, "set_reserve_status"):
                                p.set_reserve_status("reserves")
                            else:
                                p.reserve_status = "reserves"
                        except Exception:
                            pass
                        try:
                            p.deployed = True
                        except Exception:
                            pass
                        try:
                            setattr(p, "_started_in_reserves", True)
                        except Exception:
                            pass
            except Exception:
                pass


class HumanDeploymentDecisionMaker(DeploymentDecisionMaker):
    """Implementation for human players making deployment decisions via UI."""
    
    def __init__(self, ui_interface=None):
        self.ui_interface = ui_interface
    
    def choose_deployment_zone(self, available_zones: List[dict]) -> dict:
        """Human chooses deployment zone via UI."""
        if self.ui_interface:
            return self.ui_interface.choose_deployment_zone(available_zones)
        else:
            # Default: choose first zone
            logger.warning("No UI interface available for human deployment zone selection, using first zone")
            return available_zones[0]

    def choose_next_deploy_unit(
        self,
        deployable_units: List['Unit'],
        deployment_zone: dict,
        already_deployed: List['Unit'],
    ) -> 'Unit':
        if not deployable_units:
            raise ValueError("No deployable units available.")
        return deployable_units[0]
    
    def declare_reserves(self, player: Player) -> dict:
        """Human declares reserves via UI."""
        if self.ui_interface:
            return self.ui_interface.declare_reserves(player)
        else:
            # Interactive console-based reserves selection
            army = player.get_army()
            logger.info(f"{player.name}: Choose reserves for your units")
            reserves_decisions = {}
            current_reserve_units = 0
            current_reserve_points = 0
            
            # Show reserve limits
            limits = army.get_reserve_limits()
            logger.info(f"\nReserve Limits: {limits['max_units']}/{limits['total_units']} units, {limits['max_points']}/{limits['total_points']} points")
            
            for unit in army.units:
                logger.info(f"\n{unit.name} ({len(unit.models)} models, {unit.get_unit_cost()} pts)")

                try:
                    if bool(getattr(unit, "must_start_in_reserves", lambda: False)()):
                        reserves_decisions[unit.id] = 'reserves'
                        current_reserve_units += 1
                        current_reserve_points += unit.get_unit_cost()
                        logger.info(f"{unit.name} forced into Reserves (AIRCRAFT)")
                        continue
                except Exception:
                    pass

                # Check if unit can use standard reserves (Deep Strike or detachment exception).
                allows_detachment_reserves = False
                allow_fn = getattr(army, "_ride_the_wind_allows_standard_reserves", None)
                if callable(allow_fn):
                    allows_detachment_reserves = bool(allow_fn(unit))
                can_use_reserves = unit.has_deep_strike() or "Deep Strike" in unit.keywords or allows_detachment_reserves
                
                # Check if we can still add this unit to reserves
                can_add_to_reserves = army.can_add_unit_to_reserves(unit, current_reserve_units, current_reserve_points)
                
                if can_use_reserves and can_add_to_reserves:
                    logger.info("Options: (1) Deploy normally, (2) Standard Reserves, (3) Strategic Reserves")
                    choice = input(f"Choice for {unit.name} [1/2/3]: ").strip()
                    
                    if choice == '2':
                        reserves_decisions[unit.id] = 'reserves'
                        current_reserve_units += 1
                        current_reserve_points += unit.get_unit_cost()
                        logger.info(f"{unit.name} placed in Standard Reserves")
                    elif choice == '3':
                        reserves_decisions[unit.id] = 'strategic_reserves'
                        current_reserve_units += 1
                        current_reserve_points += unit.get_unit_cost()
                        logger.info(f"{unit.name} placed in Strategic Reserves")
                    else:
                        reserves_decisions[unit.id] = 'deploy'
                        logger.info(f"{unit.name} will deploy normally")
                elif can_use_reserves and not can_add_to_reserves:
                    logger.info("Cannot add to reserves (limits reached) - Options: (1) Deploy normally")
                    choice = input(f"Choice for {unit.name} [1]: ").strip()
                    reserves_decisions[unit.id] = 'deploy'
                    logger.info(f"{unit.name} will deploy normally")
                else:
                    if can_add_to_reserves:
                        logger.info("Options: (1) Deploy normally, (3) Strategic Reserves")
                        choice = input(f"Choice for {unit.name} [1/3]: ").strip()
                        
                        if choice == '3':
                            reserves_decisions[unit.id] = 'strategic_reserves'
                            current_reserve_units += 1
                            current_reserve_points += unit.get_unit_cost()
                            logger.info(f"{unit.name} placed in Strategic Reserves")
                        else:
                            reserves_decisions[unit.id] = 'deploy'
                            logger.info(f"{unit.name} will deploy normally")
                    else:
                        logger.info("Cannot add to reserves (limits reached) - Options: (1) Deploy normally")
                        choice = input(f"Choice for {unit.name} [1]: ").strip()
                        reserves_decisions[unit.id] = 'deploy'
                        logger.info(f"{unit.name} will deploy normally")
                
                # Show current reserve status
                logger.info(f"Current reserves: {current_reserve_units}/{limits['max_units']} units, {current_reserve_points}/{limits['max_points']} points")
            
            # Final validation
            validation_result = army.validate_reserves_decisions(reserves_decisions)
            if not validation_result['valid']:
                logger.error(f"Reserve validation failed: {validation_result['errors']}")
                # Enforce limits
                reserves_decisions = army.enforce_reserves_limits(reserves_decisions)
                logger.info("Reserve limits enforced automatically")
            
            return reserves_decisions
    
    def choose_unit_deployment_position(self, unit: 'Unit', deployment_zone: dict, 
                                       already_deployed: List['Unit']) -> Tuple[float, float]:
        """Human chooses unit position via UI."""
        if self.ui_interface:
            return self.ui_interface.choose_unit_deployment_position(unit, deployment_zone, already_deployed)
        else:
            # Interactive console-based position selection
            logger.info(f"\nPlace {unit.name} in deployment zone:")
            logger.info(f"  X range: {deployment_zone['x_range'][0]:.1f}\" to {deployment_zone['x_range'][1]:.1f}\"")
            logger.info(f"  Y range: {deployment_zone['y_range'][0]:.1f}\" to {deployment_zone['y_range'][1]:.1f}\"")
            
            x_center = (deployment_zone['x_range'][0] + deployment_zone['x_range'][1]) / 2
            y_center = (deployment_zone['y_range'][0] + deployment_zone['y_range'][1]) / 2
            
            try:
                x_input = input(f"X position ({deployment_zone['x_range'][0]:.1f}-{deployment_zone['x_range'][1]:.1f}, default {x_center:.1f}): ").strip()
                x = float(x_input) if x_input else x_center
                
                y_input = input(f"Y position ({deployment_zone['y_range'][0]:.1f}-{deployment_zone['y_range'][1]:.1f}, default {y_center:.1f}): ").strip()
                y = float(y_input) if y_input else y_center
                
                # Clamp to deployment zone
                x = max(deployment_zone['x_range'][0], min(deployment_zone['x_range'][1], x))
                y = max(deployment_zone['y_range'][0], min(deployment_zone['y_range'][1], y))
                
                logger.info(f"{unit.name} positioned at ({x:.1f}, {y:.1f})")
                return x, y
                
            except ValueError:
                logger.warning(f"Invalid input for {unit.name} position, using center of zone")
                return x_center, y_center 
