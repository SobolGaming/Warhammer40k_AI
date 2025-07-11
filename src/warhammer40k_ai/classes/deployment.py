from typing import List, Tuple, Dict, Any, Optional, TYPE_CHECKING
import logging
import torch
from abc import ABC, abstractmethod

from warhammer40k_ai.classes.game import Game
from warhammer40k_ai.classes.player import Player
from warhammer40k_ai.utility.calcs import get_dist

if TYPE_CHECKING:
    from warhammer40k_ai.classes.unit import Unit

logger = logging.getLogger(__name__)


class DeploymentDecisionMaker(ABC):
    """Abstract base class for making deployment decisions (AI or Human)."""
    
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


class DeploymentManager:
    """Manages the official Warhammer 40k 10th Edition deployment sequence."""
    
    def __init__(self, game: Game):
        self.game = game
        self.attacker = None
        self.defender = None
        self.deployment_zones = []
        
    def execute_deployment_sequence(self, decision_makers: Dict[str, DeploymentDecisionMaker]) -> dict:
        """Execute the complete deployment sequence according to Warhammer 40k rules.
        
        Args:
            decision_makers: Dict mapping player names to their DeploymentDecisionMaker instances
        """
        deployment_results = {
            'attacker': None,
            'defender': None,
            'first_turn_player': None,
            'deployment_zones': {},
            'reserves': {},
            'deployment_positions': {}
        }
        
        logger.info("🚀 Starting Official Warhammer 40k Deployment Sequence")
        
        # Step 1: Determine Attacker and Defender
        self.attacker, self.defender = self.determine_attacker_and_defender()
        deployment_results['attacker'] = self.attacker.name
        deployment_results['defender'] = self.defender.name
        logger.info(f"📋 Attacker: {self.attacker.name}, Defender: {self.defender.name}")
        
        # Step 2: Use pre-configured deployment zones (ensures consistency)
        if hasattr(self.game, 'deployment_zones') and self.game.deployment_zones:
            # Use zones already set up in the game (ensures consistency across all game types)
            logger.info("📍 Using pre-configured deployment zones for consistency")
            
            # Convert the game's deployment zones to the format expected by the deployment system
            available_zones = []
            for player_name, zone in self.game.deployment_zones.items():
                zone_copy = zone.copy()
                zone_copy['name'] = f"{player_name}'s Zone"
                available_zones.append(zone_copy)
            
            # Assign zones - defender chooses first
            defender_decision_maker = decision_makers[self.defender.name]
            chosen_zone = defender_decision_maker.choose_deployment_zone(available_zones)
            
            # Find which zone was chosen and assign accordingly
            defender_zone = chosen_zone
            attacker_zone = next(zone for zone in available_zones if zone != chosen_zone)
            
            deployment_results['deployment_zones'][self.defender.name] = defender_zone
            deployment_results['deployment_zones'][self.attacker.name] = attacker_zone
        else:
            # Default: create standard zones if none exist
            logger.warning("No pre-configured zones found, creating standard zones")
            available_zones = self.create_deployment_zones()
            defender_decision_maker = decision_makers[self.defender.name]
            chosen_zone = defender_decision_maker.choose_deployment_zone(available_zones)
            
            # Assign zones
            defender_zone = chosen_zone
            attacker_zone = next(zone for zone in available_zones if zone != chosen_zone)
            
            deployment_results['deployment_zones'][self.defender.name] = defender_zone
            deployment_results['deployment_zones'][self.attacker.name] = attacker_zone
            
            # Store deployment zones in the game for visualization
            self.game.deployment_zones = {
                self.defender.name: defender_zone,
                self.attacker.name: attacker_zone
            }
        
        logger.info(f"🎯 {self.defender.name} chose deployment zone, {self.attacker.name} gets the other")
        
        # Step 3: Declare Reserves & Strategic Reserves (simultaneously)
        defender_reserves = defender_decision_maker.declare_reserves(self.defender)
        attacker_decision_maker = decision_makers[self.attacker.name]
        attacker_reserves = attacker_decision_maker.declare_reserves(self.attacker)
        
        deployment_results['reserves'][self.defender.name] = defender_reserves
        deployment_results['reserves'][self.attacker.name] = attacker_reserves
        
        logger.info(f"📦 Reserves declared - {self.defender.name}: {sum(1 for d in defender_reserves.values() if d != 'deploy')} units, "
                   f"{self.attacker.name}: {sum(1 for d in attacker_reserves.values() if d != 'deploy')} units")
        
        # Step 4: Alternating Deployment (Defender first)
        self.execute_alternating_deployment(deployment_results, decision_makers)
        
        # Step 5: Determine First Turn
        first_turn_player = self.determine_first_turn()
        deployment_results['first_turn_player'] = first_turn_player.name
        
        # Set the game's current player to the first turn player
        if first_turn_player == self.game.players[0]:
            self.game.current_player_index = 0
        else:
            self.game.current_player_index = 1
        
        logger.info(f"🎲 {first_turn_player.name} will take the first turn")
        logger.info("✅ Deployment sequence complete!")
        
        self.set_reserves_status(deployment_results)
        
        return deployment_results
    
    def determine_attacker_and_defender(self) -> Tuple[Player, Player]:
        """Roll off to determine attacker and defender."""
        player1_roll = torch.randint(1, 7, (1,)).item()
        player2_roll = torch.randint(1, 7, (1,)).item()
        
        logger.info(f"🎲 Attacker/Defender roll-off: {self.game.players[0].name}={player1_roll}, {self.game.players[1].name}=${player2_roll}")
        
        # Re-roll ties
        while player1_roll == player2_roll:
            player1_roll = torch.randint(1, 7, (1,)).item()
            player2_roll = torch.randint(1, 7, (1,)).item()
            logger.info(f"🎲 Tie! Re-rolling: {self.game.players[0].name}={player1_roll}, {self.game.players[1].name}={player2_roll}")
        
        if player1_roll > player2_roll:
            return self.game.players[0], self.game.players[1]  # Player 1 is attacker
        else:
            return self.game.players[1], self.game.players[0]  # Player 2 is attacker
    
    def create_deployment_zones(self) -> List[dict]:
        """Create deployment zones based on battlefield size - using same 18\" zones as Human vs AI."""
        battlefield_width, battlefield_height = self.game.get_battlefield_size()
        deployment_depth = 18.0  # 18 inches from edge - consistent with Human vs AI
        
        # Standard deployment zones (18" from opposite table edges)
        zone1 = {
            'name': 'Zone 1',
            'x_range': (0, deployment_depth),
            'y_range': (0, battlefield_height)
        }
        
        zone2 = {
            'name': 'Zone 2', 
            'x_range': (battlefield_width - deployment_depth, battlefield_width),
            'y_range': (0, battlefield_height)
        }
        
        return [zone1, zone2]
    
    def execute_alternating_deployment(self, deployment_results: dict, 
                                     decision_makers: Dict[str, DeploymentDecisionMaker]) -> None:
        """Execute alternating deployment starting with the defender."""
        defender_zone = deployment_results['deployment_zones'][self.defender.name]
        attacker_zone = deployment_results['deployment_zones'][self.attacker.name]
        
        # Get units to deploy (not in reserves)
        defender_units = [unit for unit in self.defender.get_army().units 
                         if deployment_results['reserves'][self.defender.name].get(unit.name, 'deploy') == 'deploy']
        attacker_units = [unit for unit in self.attacker.get_army().units 
                         if deployment_results['reserves'][self.attacker.name].get(unit.name, 'deploy') == 'deploy']
        
        logger.info(f"📍 Alternating deployment: {len(defender_units)} vs {len(attacker_units)} units")
        
        # Track deployment order and positions
        deployment_order = []
        defender_deployed = []
        attacker_deployed = []
        
        # Defender starts
        current_player = self.defender
        current_units = defender_units
        current_zone = defender_zone
        current_decision_maker = decision_makers[self.defender.name]
        current_deployed = defender_deployed
        
        turn_count = 0
        while defender_units or attacker_units:
            if current_units:
                # Deploy next unit
                unit = current_units.pop(0)
                position = current_decision_maker.choose_unit_deployment_position(unit, current_zone, current_deployed)
                
                # Actually deploy the unit
                self.deploy_unit(unit, position, current_zone)
                current_deployed.append(unit)
                deployment_order.append((current_player.name, unit.name, position))
                
                logger.info(f"🚢 {current_player.name} deploys {unit.name} at ({position[0]:.1f}, {position[1]:.1f})")
            
            # Switch to other player
            turn_count += 1
            if current_player == self.defender:
                current_player = self.attacker
                current_units = attacker_units
                current_zone = attacker_zone  
                current_decision_maker = decision_makers[self.attacker.name]
                current_deployed = attacker_deployed
            else:
                current_player = self.defender
                current_units = defender_units
                current_zone = defender_zone
                current_decision_maker = decision_makers[self.defender.name]
                current_deployed = defender_deployed
        
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
        self.game.map.units.append(unit)
    
    def determine_first_turn(self) -> Player:
        """Determine who goes first according to Warhammer 40k rules."""
        # Attacker rolls D6: 1-3 = Defender goes first, 4-6 = Attacker goes first
        roll = torch.randint(1, 7, (1,)).item()
        logger.info(f"🎲 First turn roll: {roll}")
        
        if roll <= 3:
            logger.info(f"🥇 {self.defender.name} (Defender) takes first turn")
            return self.defender
        else:
            logger.info(f"🥇 {self.attacker.name} (Attacker) takes first turn")
            return self.attacker

    def set_reserves_status(self, deployment_results: dict) -> None:
        """Set the reserve status for all units based on deployment decisions."""
        for player_name in [self.attacker.name, self.defender.name]:
            player = self.attacker if player_name == self.attacker.name else self.defender
            reserves_decisions = deployment_results['reserves'].get(player_name, {})
            
            for unit in player.get_army().units:
                reserve_decision = reserves_decisions.get(unit.name, 'deploy')
                
                if reserve_decision == 'deploy':
                    unit.set_reserve_status('deployed')
                elif reserve_decision == 'reserves':
                    unit.set_reserve_status('reserves')
                    logger.info(f"🏗️ {unit.name} placed in standard reserves")
                elif reserve_decision == 'strategic_reserves':
                    unit.set_reserve_status('strategic_reserves')
                    logger.info(f"🏗️ {unit.name} placed in strategic reserves")
                else:
                    # Default to deployed for any unknown status
                    unit.set_reserve_status('deployed')


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
    
    def declare_reserves(self, player: Player) -> dict:
        """Human declares reserves via UI."""
        if self.ui_interface:
            return self.ui_interface.declare_reserves(player)
        else:
            # Interactive console-based reserves selection
            logger.info(f"🪂 {player.name}: Choose reserves for your units")
            reserves_decisions = {}
            
            for unit in player.get_army().units:
                print(f"\n📋 {unit.name} ({len(unit.models)} models, {unit.get_unit_cost()} pts)")
                
                # Check if unit can use standard reserves
                can_use_reserves = unit.has_deep_strike() or "Deep Strike" in unit.keywords
                
                if can_use_reserves:
                    print("Options: (1) Deploy normally, (2) Standard Reserves, (3) Strategic Reserves")
                    choice = input(f"Choice for {unit.name} [1/2/3]: ").strip()
                    
                    if choice == '2':
                        reserves_decisions[unit.name] = 'reserves'
                        print(f"✅ {unit.name} placed in Standard Reserves")
                    elif choice == '3':
                        reserves_decisions[unit.name] = 'strategic_reserves'
                        print(f"✅ {unit.name} placed in Strategic Reserves")
                    else:
                        reserves_decisions[unit.name] = 'deploy'
                        print(f"✅ {unit.name} will deploy normally")
                else:
                    print("Options: (1) Deploy normally, (3) Strategic Reserves")
                    choice = input(f"Choice for {unit.name} [1/3]: ").strip()
                    
                    if choice == '3':
                        reserves_decisions[unit.name] = 'strategic_reserves'
                        print(f"✅ {unit.name} placed in Strategic Reserves")
                    else:
                        reserves_decisions[unit.name] = 'deploy'
                        print(f"✅ {unit.name} will deploy normally")
            
            return reserves_decisions
    
    def choose_unit_deployment_position(self, unit: 'Unit', deployment_zone: dict, 
                                       already_deployed: List['Unit']) -> Tuple[float, float]:
        """Human chooses unit position via UI."""
        if self.ui_interface:
            return self.ui_interface.choose_unit_deployment_position(unit, deployment_zone, already_deployed)
        else:
            # Interactive console-based position selection
            print(f"\n🎯 Place {unit.name} in deployment zone:")
            print(f"   X range: {deployment_zone['x_range'][0]:.1f}\" to {deployment_zone['x_range'][1]:.1f}\"")
            print(f"   Y range: {deployment_zone['y_range'][0]:.1f}\" to {deployment_zone['y_range'][1]:.1f}\"")
            
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
                
                print(f"✅ {unit.name} positioned at ({x:.1f}, {y:.1f})")
                return x, y
                
            except ValueError:
                logger.warning(f"Invalid input for {unit.name} position, using center of zone")
                return x_center, y_center 