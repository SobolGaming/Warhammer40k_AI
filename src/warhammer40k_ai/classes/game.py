from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import logging
import copy
from .event_system import EventSystem
from .map import Map, Objective
from .mission_cards import PrimaryMissionCard, SecondaryMissionCard
from .player import Player
from .unit import Unit
from .model import Model
from ..utility.calcs import get_dist, clear_enemy_model_cache
from ..utility.dice import DiceCollection
from ..utility.constants import TOTAL_ROUNDS

logger = logging.getLogger(__name__)

class SetupPhase(Enum):
    """
    The phases of the setup phase.
    """
    MUSTER_ARMIES = 0
    SELECT_MISSION_OBJECTIVES = 1
    CREATE_BATTLEFIELD = 2  # Place terrain, objectives, etc.
    DETERMINE_ATTACKER_AND_DEFENDER = 3
    DECLARE_BATTLE_FORMATIONS = 4  # Attach leaders to units if you want; declare reserve; declare embarked unts
    DEPLOY_ARMIES = 5
    REDEPLOY_UNITS = 6
    DETERMINE_FIRST_TURN_ORDER = 7
    RESOLVE_PREBATTLE_RULES = 8  # Resolve any pre-battle rules, abilities, or stratagems


class BattleRoundPhases(Enum):
    """
    The phases of a battle round.
    """
    COMMAND_PHASE = 0
    MOVEMENT_PHASE = 1
    SHOOTING_PHASE = 2
    CHARGE_PHASE = 3
    FIGHT_PHASE = 4


class BattlefieldSize(Enum):
    COMBAT_PATROL = "Combat Patrol"
    INCURSION = "Incursion"
    STRIKE_FORCE = "Strike Force"
    ONSLAUGHT = "Onslaught"


class Battlefield:
    SIZES: Dict[BattlefieldSize, Dict[str, Any]] = {
        BattlefieldSize.COMBAT_PATROL: {
            "width": 44,
            "height": 30,
            "points": 500,
            "command_points": 0,
            "detachments": 1
        },
        BattlefieldSize.INCURSION: {
            "width": 44,
            "height": 30,
            "points": 1000,
            "command_points": 0,
            "detachments": 2
        },
        BattlefieldSize.STRIKE_FORCE: {
            "width": 60,
            "height": 44,
            "points": 2000,
            "command_points": 0,
            "detachments": 3
        },
        BattlefieldSize.ONSLAUGHT: {
            "width": 90,
            "height": 44,
            "points": 3000,
            "command_points": 0,
            "detachments": 4
        }
    }

    def __init__(self, size: BattlefieldSize = None, width: int = None, height: int = None):
        if size:
            self.size = size
            self.width = self.SIZES[size]["width"]
            self.height = self.SIZES[size]["height"]
            self.points = self.SIZES[size]["points"]
            self.command_points = self.SIZES[size]["command_points"]
            self.detachments = self.SIZES[size]["detachments"]
        else:
            self.size = None
            self.width = width
            self.height = height
            self.points = None
            self.command_points = None
            self.detachments = None

    def __str__(self):
        return f"Battlefield({self.width}\" x {self.height}\")"


class Game:
    def __init__(self, battlefield: Battlefield, players: List[Player] | None = None):
        self.battlefield = battlefield
        # Avoid mutable default arg: always create a fresh list per Game instance.
        self.players = list(players) if players else []
        self.turn = 1
        self.current_player_index = 0
        self.map = Map(battlefield.width, battlefield.height)
        self.event_system = EventSystem()
        self.objectives = []
        self.commands = []
        self.phase = BattleRoundPhases.COMMAND_PHASE  # Initialize phase to COMMAND_PHASE
        self.do_ai_action = False  # Initialize AI action flag
        
        # Wire game reference into any pre-supplied players
        for p in self.players:
            p.set_game(self)

        # Install default rules subscribers (e.g. on-kill rewards)
        try:
            self._install_default_event_subscribers()
        except Exception:
            pass

        # Setup phase tracking
        self.setup_phase = SetupPhase.MUSTER_ARMIES  # Start with first setup phase
        self.setup_complete = False  # Track when setup is finished
        
        # Deployment tracking
        self.deployment_turn_index = 0  # Track whose turn it is to deploy (0 = defender, 1 = attacker)
        self.attacker_index = None  # Index of the attacking player (will be set during DETERMINE_ATTACKER_AND_DEFENDER)
        self.defender_index = None  # Index of the defending player (will be set during DETERMINE_ATTACKER_AND_DEFENDER)
        self.deployment_zones = {}  # Store deployment zones for visualization {player_name: zone_dict}
        self.waiting_for_deployment_input = False  # Flag for manual phases during deployment
        self.deployment_actions = {}  # Track last deployment action for each player
        self.first_turn_player_index = None  # Index of player who goes first (will be set during DETERMINE_FIRST_TURN_ORDER)
        self.battle_round_starting_player_index = None  # Track who started the current battle round
        # Mission actions and event tracking
        self.in_progress_actions: List[Dict[str, Any]] = []
        self.destroyed_units_this_turn: List['Unit'] = []
        self.completed_actions_this_turn: List[Dict[str, Any]] = []
        self.models_destroyed_this_turn: List['Model'] = []
        self.destroyed_units_this_battle_round_by_player: Dict[Player, int] = {}

    def _install_default_event_subscribers(self) -> None:
        """Install non-UI rule subscribers that operate off the event system."""
        self.event_system.subscribe("model_destroyed", self._on_model_destroyed_rules)
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_rules)
        # Transport core rules (Destroyed Transport -> Disembark + mortals + battleshock)
        self.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_transport_rules)

    def _on_model_destroyed_rules(self, attacker_model=None, attacker_unit=None, target_model=None, target_unit=None, **_kwargs) -> None:
        # Generic partial support for "gain CP when this model destroys an enemy KEYWORD unit/model".
        if attacker_unit is None or target_unit is None:
            return

        # Must be an enemy destroy event
        try:
            if attacker_unit.get_parent_army() == target_unit.get_parent_army():
                return
        except Exception:
            return

        specs = []
        try:
            specs = attacker_unit.get_kill_reward_specs(model=attacker_model)
        except Exception:
            specs = []

        if not specs:
            return

        target_keywords = set()
        try:
            target_keywords = {str(k).upper() for k in getattr(target_unit, "keywords", []) or []}
        except Exception:
            target_keywords = set()

        for spec in specs:
            if spec.get("trigger") != "model_destroyed":
                continue

            # Optional restriction: melee only (Feared Interrogator)
            if spec.get("requires_melee", False):
                try:
                    wp = _kwargs.get("weapon_profile", None)
                    pw = getattr(wp, "parent_wargear", None)
                    if pw is None or not getattr(pw, "is_melee", lambda: False)():
                        continue
                except Exception:
                    continue

            # Keyword matching
            required = set(spec.get("target_keywords", spec.get("required_target_keywords", set())) or set())
            mode = (spec.get("target_keyword_mode", "all") or "all").lower()
            if required:
                if mode == "any":
                    if required.isdisjoint(target_keywords):
                        continue
                else:
                    if not required.issubset(target_keywords):
                        continue

            if spec.get("type") == "gain_cp_on_destroy":
                cp = int(spec.get("cp", 1) or 1)
                try:
                    player = attacker_unit.get_parent_army().player
                    if player is None:
                        continue
                    gained = 0
                    try:
                        if hasattr(player, "gain_command_points"):
                            gained = int(player.gain_command_points(cp, reason=spec.get("source_ability", "")) or 0)
                        else:
                            before = player.command_points
                            player.gain_command_point() if cp == 1 else setattr(player, "command_points", before + cp)
                            gained = cp
                    except Exception:
                        gained = 0
                    try:
                        self.event_system.publish(
                            "command_points_gained",
                            player=player,
                            amount=gained,
                            reason=spec.get("source_ability", ""),
                            attacker_unit=attacker_unit,
                            target_unit=target_unit,
                            attacker_model=attacker_model,
                            target_model=target_model,
                        )
                    except Exception:
                        pass
                except Exception:
                    continue

            if spec.get("type") == "heal_on_destroy":
                # Heal the destroying model (if present)
                if attacker_model is None:
                    continue
                heal_expr = spec.get("heal_expr")
                if not heal_expr:
                    continue
                try:
                    from warhammer40k_ai.utility.dice import get_roll
                    amount = get_roll(heal_expr)
                    attacker_model.heal(amount)
                    try:
                        self.event_system.publish(
                            "model_healed",
                            model=attacker_model,
                            unit=attacker_unit,
                            amount=amount,
                            reason=spec.get("source_ability", ""),
                        )
                    except Exception:
                        pass
                except Exception:
                    continue

    def _on_unit_destroyed_rules(self, unit=None, destroyed_by_unit=None, destroyed_by_model=None, destroyed_by_weapon_profile=None, **_kwargs) -> None:
        # Generic partial support for "... destroys an enemy <KEYWORD> unit, gain X CP".
        if unit is None or destroyed_by_unit is None:
            return

        try:
            if destroyed_by_unit.get_parent_army() == unit.get_parent_army():
                return
        except Exception:
            return

        specs = []
        try:
            specs = destroyed_by_unit.get_kill_reward_specs(model=destroyed_by_model)
        except Exception:
            specs = []

        if not specs:
            return

        target_keywords = set()
        try:
            target_keywords = {str(k).upper() for k in getattr(unit, "keywords", []) or []}
        except Exception:
            target_keywords = set()

        for spec in specs:
            if spec.get("trigger") != "unit_destroyed":
                continue

            # Optional restriction: melee only
            if spec.get("requires_melee", False):
                try:
                    wp = destroyed_by_weapon_profile
                    pw = getattr(wp, "parent_wargear", None)
                    if wp is None or pw is None or not getattr(pw, "is_melee", lambda: False)():
                        continue
                except Exception:
                    continue

            required = set(spec.get("target_keywords", spec.get("required_target_keywords", set())) or set())
            mode = (spec.get("target_keyword_mode", "all") or "all").lower()
            if required:
                if mode == "any":
                    if required.isdisjoint(target_keywords):
                        continue
                else:
                    if not required.issubset(target_keywords):
                        continue

            if spec.get("type") == "gain_cp_on_destroy":
                cp = int(spec.get("cp", 1) or 1)
                try:
                    player = destroyed_by_unit.get_parent_army().player
                    if player is None:
                        continue
                    gained = 0
                    try:
                        if hasattr(player, "gain_command_points"):
                            gained = int(player.gain_command_points(cp, reason=spec.get("source_ability", "")) or 0)
                        else:
                            before = player.command_points
                            player.gain_command_point() if cp == 1 else setattr(player, "command_points", before + cp)
                            gained = cp
                    except Exception:
                        gained = 0
                    try:
                        self.event_system.publish(
                            "command_points_gained",
                            player=player,
                            amount=gained,
                            reason=spec.get("source_ability", ""),
                            attacker_unit=destroyed_by_unit,
                            target_unit=unit,
                            attacker_model=destroyed_by_model,
                        )
                    except Exception:
                        pass
                except Exception:
                    continue

            if spec.get("type") == "heal_on_destroy":
                if destroyed_by_model is None:
                    continue
                heal_expr = spec.get("heal_expr")
                if not heal_expr:
                    continue
                try:
                    from warhammer40k_ai.utility.dice import get_roll
                    amount = get_roll(heal_expr)
                    destroyed_by_model.heal(amount)
                    try:
                        self.event_system.publish(
                            "model_healed",
                            model=destroyed_by_model,
                            unit=destroyed_by_unit,
                            amount=amount,
                            reason=spec.get("source_ability", ""),
                        )
                    except Exception:
                        pass
                except Exception:
                    continue

    def _on_unit_destroyed_transport_rules(self, unit=None, last_model=None, game_map=None, **_kwargs) -> None:
        """
        10th edition core Transport rule: when a Transport is destroyed, any embarked units must
        immediately disembark (or emergency disembark), take mortal wounds, and become battle-shocked.
        """
        if unit is None or game_map is None:
            return
        try:
            if not getattr(unit, "is_transport", False):
                return
        except Exception:
            return

        passengers = list(getattr(unit, "transport_passengers", []) or [])
        if not passengers:
            return

        # Capture last known transport base for disembark distance checks.
        try:
            if last_model is not None and getattr(last_model, "model_base", None) is not None:
                unit._last_known_base = copy.deepcopy(last_model.model_base)
        except Exception:
            unit._last_known_base = getattr(unit, "_last_known_base", None)

        for p in passengers:
            try:
                # Ensure passenger is not still in map list before disembarking (avoid duplicates)
                if hasattr(game_map, "units") and p in game_map.units:
                    game_map.units.remove(p)
            except Exception:
                pass
            try:
                p.disembark(
                    game_map=game_map,
                    transport_unit=unit,
                    destroyed_transport=True,
                    emergency=False,
                    current_turn=self.turn,
                )
            except Exception:
                # Never allow transport destruction to crash the game loop
                continue

        # Clear passengers list (disembark() should already remove them, but be defensive)
        try:
            unit.transport_passengers = []
        except Exception:
            pass

    def add_player(self, player: Player) -> None:
        """Add a player to the game."""
        self.players.append(player)
        player.set_game(self)

    def add_objective(self, objective: Objective) -> None:
        """Add an objective to the game."""
        self.objectives.append(objective)

    def add_command(self, command: str) -> None:
        """Add a command to the game."""
        self.commands.append(command)

    def get_current_player(self) -> Player:
        """Get the current player."""
        return self.players[self.current_player_index]

    def get_opponent(self) -> Player:
        """Get the opponent of the current player."""
        return self.players[(self.current_player_index + 1) % len(self.players)]

    def get_enemy_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to the opponent of the given player."""
        # Get their opponent (skip players without armies to avoid crashes in partial test setups).
        for p in self.players:
            if p is player:
                continue
            army = getattr(p, "get_army", lambda: None)()
            if army is not None:
                return list(getattr(army, "units", []) or [])
        return []

    def get_battlefield_size(self) -> tuple[int, int]:
        return self.battlefield.width, self.battlefield.height
    
    def set_attacker_defender(self, attacker_index: int, defender_index: int) -> None:
        """DEPRECATED: Set which player is the attacker and which is the defender.
        
        This method should not be used - attacker/defender roles are determined
        during the DETERMINE_ATTACKER_AND_DEFENDER setup phase only.
        """
        import warnings
        warnings.warn("set_attacker_defender is deprecated. Roles are determined during setup phase.", 
                     DeprecationWarning, stacklevel=2)
        self.attacker_index = attacker_index
        self.defender_index = defender_index
        # Defender always starts deployment
        self.deployment_turn_index = self.defender_index
    
    def get_current_deployment_player(self) -> Player:
        """Get the player whose turn it is to deploy."""
        return self.players[self.deployment_turn_index]
    
    def get_attacker(self) -> Player:
        """Get the attacking player."""
        return self.players[self.attacker_index]
    
    def get_defender(self) -> Player:
        """Get the defending player."""
        return self.players[self.defender_index]
    
    def is_deployment_phase(self) -> bool:
        """Check if we're in the deployment phase."""
        # We're in deployment phase if any units are not deployed and it's turn 1
        if self.turn != 1:
            return False
        
        for player in self.players:
            army = player.get_army()
            if army:
                undeployed_units = [u for u in army.units if not u.deployed]
                if undeployed_units:
                    return True
        return False
    
    def can_player_deploy_unit(self, player: Player) -> bool:
        """Check if the given player can deploy a unit (i.e., it's their deployment turn)."""
        if not self.is_deployment_phase():
            return False
        return player == self.get_current_deployment_player()
    
    def get_deployable_units(self, player: Player) -> List['Unit']:
        """Get units that the player can deploy during the deployment phase."""
        if not player.get_army():
            return []
        # Units with deployed=False still need deployment decisions made
        # Units with deployed=True have been assigned (battlefield, reserves, or strategic reserves)
        return [u for u in player.get_army().units if not u.deployed]
    
    def record_deployment_action(self, player: Player, unit: 'Unit', action: str, location: tuple = None) -> None:
        """Record a deployment action for display in the InfoPane."""
        if action == 'deployed' and location:
            # Accept both 2D (x,y) and 3D (x,y,z) tuples; ignore extra fields (e.g. facing)
            try:
                x = float(location[0])
                y = float(location[1])
                z = float(location[2]) if len(location) > 2 else 0.0
            except Exception:
                x = y = None
                z = 0.0

            if x is not None and y is not None:
                if abs(z) > 1e-6:
                    action_text = f"{unit.name} deployed at ({x:.1f}, {y:.1f}, {z:.1f})"
                else:
                    action_text = f"{unit.name} deployed at ({x:.1f}, {y:.1f})"
            else:
                action_text = f"{unit.name} deployed"
        elif action == 'reserves':
            action_text = f"{unit.name} placed in Reserves"
        elif action == 'strategic_reserves':
            action_text = f"{unit.name} placed in Strategic Reserves"
        else:
            action_text = f"{unit.name} - {action}"
        
        self.deployment_actions[player.name] = action_text

    def clear_deployment_actions(self) -> None:
        """Clear deployment action history after deployment phase ends."""
        self.deployment_actions = {}

    def advance_deployment_turn(self) -> None:
        """Advance to the next player's deployment turn."""
        if not self.is_deployment_phase():
            return
        
        # Get current and next player's deployable units
        current_player = self.get_current_deployment_player()
        current_deployable = self.get_deployable_units(current_player)
        
        # Switch to the other player
        self.deployment_turn_index = (self.deployment_turn_index + 1) % len(self.players)
        next_player = self.get_current_deployment_player()
        next_deployable = self.get_deployable_units(next_player)
        
        # If the next player has no units to deploy, keep switching until we find someone who does
        # or until everyone is done
        attempts = 0
        while not next_deployable and attempts < len(self.players):
            self.deployment_turn_index = (self.deployment_turn_index + 1) % len(self.players)
            next_player = self.get_current_deployment_player()
            next_deployable = self.get_deployable_units(next_player)
            attempts += 1
    
    def complete_deployment_phase(self, manual_phases: bool = False) -> None:
        """Force complete the deployment phase by auto-deploying remaining units one at a time."""
        print("🚀 Starting auto-deployment...")
        
        # Deploy units one at a time, respecting the deployment turn system
        max_attempts = 100  # Safety limit to prevent infinite loops
        attempts = 0
        
        while self.is_deployment_phase() and attempts < max_attempts:
            attempts += 1
            current_player = self.get_current_deployment_player()
            
            if not current_player:
                print("❌ No current deployment player found")
                break
            
            # Get units that need to be deployed for the current player
            undeployed_units = self.get_deployable_units(current_player)
            
            if not undeployed_units:
                # Current player has no more units to deploy, advance to next player
                print(f"Player {current_player.name} has no more units to deploy")
                self.advance_deployment_turn()
                continue
            
            # Auto-deploy the first undeployed unit for the current player
            unit = undeployed_units[0]
            print(f"Auto-deploying {unit.name} for {current_player.name}...")
            
            success = self.auto_deploy_unit(unit)
            if success:
                # Record deployment action
                if unit.position:
                    self.record_deployment_action(current_player, unit, 'deployed', unit.position)
                # Mark unit as deployed and advance to next player's turn
                unit.deployed = True
                self.advance_deployment_turn()
            else:
                print(f"❌ Failed to auto-deploy {unit.name}, advancing anyway")
                # Force deployment to prevent infinite loop
                unit.deployed = True
                unit.reserve_status = 'reserves'  # Mark as failed deployment
                # Record reserves action
                self.record_deployment_action(current_player, unit, 'reserves')
                self.advance_deployment_turn()
            
            # In manual phases mode, pause after each deployment action and require SPACE to continue
            if manual_phases and self.is_deployment_phase():  # Only pause if deployment isn't finished
                print(f"🔧 Deployment action {attempts} completed. Press SPACE to continue deployment...")
                # Set a flag to indicate we're waiting for manual input during deployment
                self.waiting_for_deployment_input = True
                return  # Exit and wait for manual input
        
        if attempts >= max_attempts:
            print(f"⚠️ Auto-deployment stopped after {max_attempts} attempts to prevent infinite loop")
        
        print(f"🎯 Auto-deployment complete after {attempts} deployment actions")
        self.waiting_for_deployment_input = False
    
    def auto_deploy_unit(self, unit: 'Unit') -> bool:
        """Auto-deploy a unit using systematic grid-based search to avoid crowded areas."""
        import random
        
        # Get the unit's player for deployment zone lookup
        player_name = unit.get_parent_army().player.name if unit.get_parent_army() and unit.get_parent_army().player else None
        
        if not player_name:
            logger.error(f"Cannot auto-deploy {unit.name}: No player found")
            return False
        
        # Get deployment constraints
        battlefield_width, battlefield_height = self.get_battlefield_size()
        
        # Determine search area based on unit type and deployment zones
        if unit.has_infiltrate():
            # Infiltrate units can deploy anywhere except restricted areas
            search_zones = self._get_infiltrate_search_zones(player_name, battlefield_width, battlefield_height)
        else:
            # Normal units must deploy within their deployment zone
            if hasattr(self, 'deployment_zones') and player_name in self.deployment_zones:
                zone = self.deployment_zones[player_name]

                # Helper: maximum model base radius approximation
                def _max_base_radius(u: 'Unit') -> float:
                    max_r = 0.5
                    for m in u.models:
                        r = getattr(m.model_base, 'radius', None)
                        if r is None and hasattr(m.model_base, 'get_radius'):
                            r = m.model_base.get_radius()
                        try:
                            r = float(r)
                        except Exception:
                            try:
                                r = float(max(r))
                            except Exception:
                                r = 0.5
                        max_r = max(max_r, r)
                    return max_r

                # Prepare effective mission polygons eroded by base radius to improve hit-rate
                mission_effective_zones = []

                # Check if this is the new mission zone system or old system
                if 'mission_zones' in zone and zone['mission_zones']:
                    from shapely.geometry import Point as _ShPoint, Polygon as _ShPoly
                    from shapely.ops import unary_union as _sh_union

                    # Compute erosion distance based on unit footprint
                    erosion = _max_base_radius(unit)
                    # Reasonable extra margin for formation spread
                    erosion += max(0.25, 0.1 * len(unit.models))

                    # Build effective (cutout-subtracted) polygons and erode
                    for mz in zone['mission_zones']:
                        poly = _ShPoly(mz.vertices)
                        # Subtract cutouts if any
                        if getattr(mz, 'cutouts', None):
                            for c in mz.cutouts:
                                cg = c.get_shapely_geometry()
                                if cg is not None:
                                    poly = poly.difference(cg)
                        # Erode polygon by erosion distance (buffer with negative value)
                        eff = poly.buffer(-erosion)
                        if not eff.is_empty:
                            mission_effective_zones.append(eff)

                    # If nothing usable after erosion, fall back to un-eroded zones
                    if not mission_effective_zones:
                        for mz in zone['mission_zones']:
                            mission_effective_zones.append(_ShPoly(mz.vertices))

                    # Construct an overall bbox to seed grid, but we will filter by polygon.contains
                    if mission_effective_zones:
                        union = _sh_union(mission_effective_zones)
                        min_x, min_y, max_x, max_y = union.bounds
                    else:
                        min_x = min_y = 0.0
                        max_x, max_y = battlefield_width, battlefield_height

                    search_zones = [(max(min_x, 0.0), min(max_x, battlefield_width),
                                     max(min_y, 0.0), min(max_y, battlefield_height))]
                else:
                    # No mission_zones present -> invalid configuration for deployment
                    return False
            else:
                logger.error(f"No deployment zone found for {player_name}")
                return False
        
        # Use systematic grid-based search instead of random
        for zone_idx, zone in enumerate(search_zones):
            x_min, x_max, y_min, y_max = zone
            
            if x_max <= x_min or y_max <= y_min:
                continue  # Skip invalid zones
            
            # Create a finer grid of potential positions
            grid_spacing = 1.0  # Reduced from 2.0 to 1.0 for finer search
            x_positions = []
            y_positions = []
            
            # Generate grid positions (adaptive to unit size)
            x = x_min
            # Use diameter-based spacing where possible to reduce futile tests
            base_step = 2.0 * max(0.5, len(unit.models) * 0.05)
            step = max(0.75, min(2.0, base_step))
            while x <= x_max:
                x_positions.append(x)
                x += step
            
            y = y_min
            while y <= y_max:
                y_positions.append(y)
                y += step
            
            # Shuffle the positions to avoid predictable patterns
            test_positions = [(x, y) for x in x_positions for y in y_positions]
            random.shuffle(test_positions)
            
            # Test positions systematically
            for x, y in test_positions:
                z = 0.0
                
                # If using mission polygons, skip points outside eroded zones early
                try:
                    if 'mission_effective_zones' not in locals():
                        pass
                    else:
                        inside_any = False
                        for eff in mission_effective_zones:
                            if eff.contains(_ShPoint(x, y)):
                                inside_any = True
                                break
                        if not inside_any:
                            continue
                except Exception:
                    # If Shapely not available or error, continue with regular checks
                    pass

                # Quick check: is this position too close to existing units?
                if self._is_position_too_crowded(x, y, unit, player_name):
                    continue
                
                # Check if this position would place all models wholly within the deployment zone
                try:
                    if self.is_valid_deployment_position(unit, x, y, player_name):
                        # Use the proper deployment flow
                        if self._deploy_unit_at_position(unit, x, y, z):
                            print(f"✅ Successfully auto-deployed {unit.name} at ({x:.1f}, {y:.1f})")
                            return True
                except Exception as e:
                    # If formation finding fails, continue to next position
                    continue
        
        print(f"❌ Failed to auto-deploy {unit.name} - no valid positions found")
        return False
    
    def _is_position_too_crowded(self, x: float, y: float, unit: 'Unit', player_name: str) -> bool:
        """Quick check if a position is too close to existing units to likely succeed."""
        # Much more reasonable minimum distance - just need to avoid immediate overlap
        min_distance = max(2.0, len(unit.models) * 0.4)  # Reduced from 4.0 and 0.8
        
        # Check distance to all deployed units
        for player in self.players:
            if not player.get_army():
                continue
            for existing_unit in player.get_army().units:
                if not existing_unit.deployed or existing_unit.reserve_status != 'deployed':
                    continue
                
                # Check distance to closest model in existing unit
                closest_distance = float('inf')
                for model in existing_unit.models:
                    if model.is_alive:
                        model_pos = model.get_location()
                        if model_pos:
                            distance = ((x - model_pos[0]) ** 2 + (y - model_pos[1]) ** 2) ** 0.5
                            closest_distance = min(closest_distance, distance)

                if closest_distance < min_distance:
                    return True
        
        return False

    def _get_infiltrate_search_zones(self, player_name: str, battlefield_width: float, battlefield_height: float) -> list:
        """Get valid search zones for infiltrate units (avoiding enemy deployment zones and 9\" buffer)."""
        # We intentionally do NOT derive "safe" search rectangles from deployment-zone bounding boxes.
        # Infiltrate legality is enforced by the validation logic itself (enemy zone + 9" buffer + enemy models).
        margin = 3.0
        return [(margin, battlefield_width - margin, margin, battlefield_height - margin)]

    def _deploy_unit_at_position(self, unit: 'Unit', x: float, y: float, z: float) -> bool:
        """Deploy a unit at the specified position using the same flow as manual deployment."""
        try:
            # Use the exact same approach as manual deployment in GameView.on_mouse_press
            # Calculate model positions (this also sets the positions internally)
            # CRITICAL: Use deployment-specific boundary repulsors to ensure models stay within deployment zones
            # This must match the repulsors used in is_valid_deployment_position for consistency
            deployment_repulsors = self.get_boundary_repulsors(unit, context='deployment')
            model_positions = unit.calculate_model_positions(x, y, self.map, avoid_friendly_units=False, boundary_repulsors=deployment_repulsors)
            
            if not model_positions:
                try:
                    print(f"🔴 DEBUG: Infiltrate - no model positions found for {unit.name} at candidate ({x:.1f}, {y:.1f})")
                except Exception:
                    pass
                return False
            
            # CRITICAL: Validate that all models are actually within deployment zone after positioning
            # This is a final safety check to catch any edge cases where models extend outside zones
            # EXCEPTION: Skip this check for Infiltrate units as they can deploy outside deployment zones
            player_name = unit.get_parent_army().player.name if unit.get_parent_army() and unit.get_parent_army().player else None
            if player_name and not unit.has_infiltrate():
                for model, position in zip(unit.models, model_positions):
                    model_x, model_y = position[0], position[1]
                    if not self.is_position_wholly_in_deployment_zone(model_x, model_y, model.model_base, player_name):
                        print(f"🔴 CRITICAL: Auto-deployment validation failed - {unit.name} {model.name} at ({model_x:.1f}, {model_y:.1f}) extends outside deployment zone")
                        return False
            
            # Unit position is now determined by model positions
            
            # Place unit on map (same as manual)
            if self.map and self.map.place_unit(unit):
                # Don't set unit.deployed here - let the calling function handle it
                return True
            else:
                return False
                
        except Exception as e:
            return False



    def _auto_position_models(self, unit: 'Unit', center_x: float, center_y: float, center_z: float) -> None:
        """Simple model positioning for auto-deployment without complex validation."""
        import math
        
        if len(unit.models) == 1:
            # Single model - place at center
            unit.models[0].set_location(center_x, center_y, center_z, 0.0)
        else:
            # Multiple models - arrange in a simple circle or line
            coherency_distance = unit.coherency_distance
            models_per_row = min(len(unit.models), 5)  # Max 5 models per row
            
            for i, model in enumerate(unit.models):
                if len(unit.models) <= 5:
                    # Small unit - arrange in a line
                    offset_x = (i - (len(unit.models) - 1) / 2) * (coherency_distance * 0.8)
                    model_x = center_x + offset_x
                    model_y = center_y
                else:
                    # Larger unit - arrange in rows
                    row = i // models_per_row
                    col = i % models_per_row
                    offset_x = (col - (models_per_row - 1) / 2) * (coherency_distance * 0.8)
                    offset_y = row * (coherency_distance * 0.8)
                    model_x = center_x + offset_x
                    model_y = center_y + offset_y
                
                model.set_location(model_x, model_y, center_z, 0.0)

    def is_position_in_deployment_zone(self, x: float, y: float, player_name: str) -> bool:
        """Check if a position is within a player's deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False
        
        if player_name not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_name]
        
        # Only mission zones are supported
        if 'mission_zones' in zone and zone['mission_zones']:
            for mission_zone in zone['mission_zones']:
                if mission_zone.contains_point(x, y):
                    return True
        return False

    def is_model_wholly_in_deployment_zone(self, model: 'Model', player_name: str) -> bool:
        """Check if a model's entire base is wholly within a player's deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            raise RuntimeError("Deployment zones not configured (invalid configuration).")
        
        if player_name not in self.deployment_zones:
            return False
        
        zone = self.deployment_zones[player_name]
        
        # Get model position and base size
        model_x, model_y = model.get_location()[:2]
        base = model.model_base
        base_radius = base.get_radius()
        
        # Require mission_zones polygons
        if 'mission_zones' not in zone or not zone['mission_zones']:
            raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")

        for mission_zone in zone['mission_zones']:
            if base.base_type.name == 'CIRCULAR':
                if mission_zone.contains_circular_base(model_x, model_y, base_radius):
                    return True
            else:
                base_vertices = base.get_vertices_at_position(model_x, model_y)
                if mission_zone.contains_polygon_base(base_vertices):
                    return True
        return False

    def is_position_wholly_in_deployment_zone(self, x: float, y: float, model_base, player_name: str) -> bool:
        """Check if a model base at (x,y) is wholly within the player's deployment zone,
        using mission zones with cutout-aware Shapely checks when available."""
        # Require configured zones
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False

        # Player must have a zone
        if player_name not in self.deployment_zones:
            return False

        zone_info = self.deployment_zones[player_name]

        # Only support mission_zones from missions.py with cutouts
        if 'mission_zones' in zone_info and zone_info['mission_zones']:
            for mission_zone in zone_info['mission_zones']:
                if model_base.base_type.name == 'CIRCULAR':
                    # Coerce radius to scalar
                    radius_val = getattr(model_base, 'radius', None)
                    if radius_val is None:
                        radius_val = model_base.get_radius() if hasattr(model_base, 'get_radius') else 0.5
                    try:
                        radius_val = float(radius_val)
                    except Exception:
                        try:
                            radius_val = float(max(radius_val))
                        except Exception:
                            radius_val = 0.5
                    if mission_zone.contains_circular_base(x, y, radius_val):
                        return True
                else:
                    # Use provided Shapely geometry from the base itself (no legacy vertex fallback)
                    if not hasattr(model_base, 'get_base_shape_at'):
                        return False
                    base_geom = model_base.get_base_shape_at(x, y, getattr(model_base, 'facing', 0.0))
                    if mission_zone.contains_base_geometry(base_geom):
                        return True
            return False
        return False

    def is_position_in_enemy_deployment_zone(self, x: float, y: float, player_name: str) -> bool:
        """Check if a position is within any enemy deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return False
        
        for zone_player_name, zone in self.deployment_zones.items():
            if zone_player_name != player_name:
                # Deployment zones are polygons (mission_zones). No rectangular fallback is supported.
                if 'mission_zones' not in zone or not zone['mission_zones']:
                    raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
                for mission_zone in zone['mission_zones']:
                    if mission_zone.contains_point(x, y):
                        return True
        return False

    def get_distance_to_enemy_deployment_zone(self, x: float, y: float, player_name: str) -> float:
        """Get the minimum distance from a position to any enemy deployment zone."""
        if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
            return float('inf')
        
        min_distance = float('inf')
        
        for zone_player_name, zone in self.deployment_zones.items():
            if zone_player_name != player_name and 'mission_zones' in zone and zone['mission_zones']:
                from shapely.geometry import Point as _ShPoint
                from shapely.geometry import Polygon as _ShPoly
                pt = _ShPoint(x, y)
                for mission_zone in zone['mission_zones']:
                    poly = _ShPoly(mission_zone.vertices)
                    d = pt.distance(poly)
                    if d < min_distance:
                        min_distance = d
        
        return min_distance

    def get_distance_to_enemy_models(self, x: float, y: float, player_name: str) -> float:
        """Get the minimum distance from a position to any enemy model."""
        min_distance = float('inf')
        
        for player in self.players:
            if player.name != player_name and player.get_army():
                for unit in player.get_army().units:
                    if unit.deployed and unit.reserve_status == 'deployed':
                        for model in unit.models:
                            model_x, model_y = model.get_location()[:2]
                            distance = ((x - model_x) ** 2 + (y - model_y) ** 2) ** 0.5
                            min_distance = min(min_distance, distance)
        
        return min_distance

    def get_boundary_repulsors(self, unit: 'Unit', context: str = 'deployment') -> List:
        """Generate boundary repulsors for spatial collision detection.
        
        Args:
            unit: The unit being positioned
            context: 'deployment' or 'movement' - determines which boundaries to include
            
        Returns:
            List of Shapely polygons representing boundary repulsors
        """
        from shapely.geometry import Polygon, Point
        from shapely.affinity import scale
        
        repulsors = []
        battlefield_width, battlefield_height = self.get_battlefield_size()
        player_name = unit.get_parent_army().player.name if unit.get_parent_army() and unit.get_parent_army().player else None
        
        if context == 'deployment':
            # For deployment, add deployment zone boundaries (mission-aware) and cutouts as repulsors
            if hasattr(self, 'deployment_zones') and self.deployment_zones and player_name:
                if player_name in self.deployment_zones:
                    zone = self.deployment_zones[player_name]
                    repulsor_thickness = 0.5  # 0.5 inch thick edge repulsor ring

                    # New mission system: polygon zones + cutouts
                    if 'mission_zones' in zone and zone['mission_zones']:
                        from shapely.geometry import Polygon as _ShPoly
                        for mz in zone['mission_zones']:
                            poly = _ShPoly(mz.vertices)
                            # Outer ring to repel from edges (outside only)
                            ring = poly.buffer(repulsor_thickness).difference(poly)
                            if not ring.is_empty:
                                repulsors.append(ring)
                            # Cutouts act as hard blockers
                            if getattr(mz, 'cutouts', None):
                                for c in mz.cutouts:
                                    cg = c.get_shapely_geometry()
                                    if cg is not None and not cg.is_empty:
                                        repulsors.append(cg)
                    else:
                        raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
        
        elif context == 'movement':
            # For movement, add battlefield edge boundaries as repulsors
            # This prevents units from moving off the battlefield
            repulsor_thickness = 0.5  # 0.5 inch thick repulsor zones
            
            # Left battlefield edge repulsor
            left_edge = Polygon([
                (-repulsor_thickness, -repulsor_thickness),
                (0, -repulsor_thickness),
                (0, battlefield_height + repulsor_thickness),
                (-repulsor_thickness, battlefield_height + repulsor_thickness)
            ])
            repulsors.append(left_edge)
            
            # Right battlefield edge repulsor
            right_edge = Polygon([
                (battlefield_width, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, battlefield_height + repulsor_thickness),
                (battlefield_width, battlefield_height + repulsor_thickness)
            ])
            repulsors.append(right_edge)
            
            # Bottom battlefield edge repulsor
            bottom_edge = Polygon([
                (-repulsor_thickness, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, -repulsor_thickness),
                (battlefield_width + repulsor_thickness, 0),
                (-repulsor_thickness, 0)
            ])
            repulsors.append(bottom_edge)
            
            # Top battlefield edge repulsor
            top_edge = Polygon([
                (-repulsor_thickness, battlefield_height),
                (battlefield_width + repulsor_thickness, battlefield_height),
                (battlefield_width + repulsor_thickness, battlefield_height + repulsor_thickness),
                (-repulsor_thickness, battlefield_height + repulsor_thickness)
            ])
            repulsors.append(top_edge)
        
        return repulsors

    def is_valid_deployment_position(self, unit: 'Unit', x: float, y: float, player_name: str) -> bool:
        """Check if a position is valid for deploying a unit during deployment phase."""
        # Units in reserves don't need position validation
        if unit.reserve_status in ['reserves', 'strategic_reserves']:
            return True
        
        # Check if unit has Infiltrate ability
        if unit.has_infiltrate():
            # Infiltrate units can deploy anywhere except:
            # 1. Inside enemy deployment zone
            # 2. Within 9" of enemy deployment zone
            # 3. Within 9" of enemy models
            
            # For infiltrate units, we need to check each model's base at the proposed position
            # Calculate model positions using the same logic as unit deployment
            # NOTE: Don't use boundary_repulsors for validation - they make formation finding too restrictive
            # During deployment, use relaxed friendly unit avoidance to allow tighter formations
            # Use deployment boundary repulsors (mission-zone aware) to guide formation inside zone
            deployment_repulsors = self.get_boundary_repulsors(unit, context='deployment')
            model_positions = unit.calculate_model_positions(
                x, y, self.map, avoid_friendly_units=False, boundary_repulsors=deployment_repulsors
            )
            
            if not model_positions:
                return False
                
            from .map import validate_ruins_placement
            for model, position in zip(unit.models, model_positions):
                model_x, model_y = position[0], position[1]
                
                # Check if any part of the model is in enemy deployment zone
                if self.is_position_in_enemy_deployment_zone(model_x, model_y, player_name):
                    try:
                        model_name = getattr(model, 'name', 'model')
                        print(f"🔴 DEBUG: Infiltrate - {unit.name} {model_name} at ({model_x:.1f}, {model_y:.1f}) is inside enemy deployment zone")
                    except Exception:
                        pass
                    return False
                
                # Check 9" distance to enemy deployment zone (from model edge)
                base_radius = model.model_base.get_radius()
                distance_to_enemy_zone = self.get_distance_to_enemy_deployment_zone(model_x, model_y, player_name)
                if distance_to_enemy_zone - base_radius < 9.0:
                    try:
                        model_name = getattr(model, 'name', 'model')
                        print(f"🔴 DEBUG: Infiltrate - {unit.name} {model_name} too close to enemy zone: edge_distance={distance_to_enemy_zone:.2f}\" base_radius={base_radius:.2f}\" < 9\"")
                    except Exception:
                        pass
                    return False
                
                # Check 9" distance to enemy models (from model edge)
                distance_to_enemy_models = self.get_distance_to_enemy_models(model_x, model_y, player_name)
                if distance_to_enemy_models - base_radius < 9.0:
                    try:
                        model_name = getattr(model, 'name', 'model')
                        print(f"🔴 DEBUG: Infiltrate - {unit.name} {model_name} too close to enemy models: edge_distance={distance_to_enemy_models:.2f}\" base_radius={base_radius:.2f}\" < 9\"")
                    except Exception:
                        pass
                    return False
                # RUINS validation: cannot start/end overlapping walls/floors
                model_z = position[2] if len(position) > 2 else 0.0
                ruins_validation = validate_ruins_placement(unit, (model_x, model_y, model_z), self.map.terrain_features, moving_model=model)
                if not ruins_validation['valid']:
                    try:
                        model_name = getattr(model, 'name', 'model')
                        reason = ruins_validation.get('reason', 'unknown')
                        floor_level = ruins_validation.get('floor_level', '?')
                        print(f"🔴 DEBUG: Infiltrate - RUINS validation failed for {unit.name} {model_name}: {reason} (floor {floor_level})")
                    except Exception:
                        pass
                    return False
            
            return True
        else:
            # Normal units must be WHOLLY within their own deployment zone
            # Check that every model's entire base would be within the deployment zone at the proposed position
            # Calculate model positions using the same logic as unit deployment
            # NOTE: Don't use boundary_repulsors for validation - they make formation finding too restrictive
            # During deployment, use relaxed friendly unit avoidance to allow tighter formations
            deployment_repulsors = self.get_boundary_repulsors(unit, context='deployment')
            model_positions = unit.calculate_model_positions(
                x, y, self.map, avoid_friendly_units=False, boundary_repulsors=deployment_repulsors
            )
            
            if not model_positions:
                return False
                
            from .map import validate_ruins_placement
            for model, position in zip(unit.models, model_positions):
                model_x, model_y, model_z = position[0], position[1], position[2]
                
                # Check if this model would be wholly within the deployment zone
                if not self.is_position_wholly_in_deployment_zone(model_x, model_y, model.model_base, player_name):
                    try:
                        model_name = getattr(model, 'name', 'model')
                        print(f"🔴 DEBUG: Zone check failed for {unit.name} {model_name} at ({model_x:.1f}, {model_y:.1f}) in player '{player_name}' zone")
                    except Exception:
                        pass
                    return False
                
                # Check RUINS terrain placement rules
                ruins_validation = validate_ruins_placement(unit, (model_x, model_y, model_z), self.map.terrain_features, moving_model=model)
                if not ruins_validation['valid']:
                    try:
                        model_name = getattr(model, 'name', 'model')
                        print(f"🔴 DEBUG: RUINS validation failed for {unit.name} {model_name}: {ruins_validation['reason']}")
                    except Exception:
                        pass
                    return False
            return True

    def is_valid_single_model_deployment(self, model: 'Model', x: float, y: float, z: float, player_name: str) -> dict:
        """Validate deploying a single model at (x,y,z) during deployment.

        Applies deployment-zone rules (infiltrate vs normal) and RUINS placement rules for the model only.

        Returns a dict: { 'valid': bool, 'reason': str }
        """
        unit = model.parent_unit
        # Units destined for reserves are not placed on battlefield
        if unit.reserve_status in ['reserves', 'strategic_reserves']:
            return {'valid': False, 'reason': 'Unit is in reserves'}

        # Infiltrate logic: anywhere except inside enemy zone or within 9" from enemy zone/models (edge of base)
        if unit.has_infiltrate():
            # Inside enemy zone
            if self.is_position_in_enemy_deployment_zone(x, y, player_name):
                return {'valid': False, 'reason': 'Inside enemy deployment zone'}
            # 9" from enemy zone (from model edge)
            base_radius = model.model_base.get_radius()
            distance_to_enemy_zone = self.get_distance_to_enemy_deployment_zone(x, y, player_name)
            if distance_to_enemy_zone - base_radius < 9.0:
                return {'valid': False, 'reason': 'Too close to enemy deployment zone (<9\")'}
            # 9" from enemy models (from model edge)
            distance_to_enemy_models = self.get_distance_to_enemy_models(x, y, player_name)
            if distance_to_enemy_models - base_radius < 9.0:
                return {'valid': False, 'reason': 'Too close to enemy models (<9\")'}
        else:
            # Normal deployment: wholly within own zone
            if not self.is_position_wholly_in_deployment_zone(x, y, model.model_base, player_name):
                return {'valid': False, 'reason': 'Model base not wholly within deployment zone'}

        # RUINS placement validation for this single model
        from .map import validate_ruins_placement
        ruins_validation = validate_ruins_placement(unit, (x, y, z), self.map.terrain_features, moving_model=model)
        if not ruins_validation['valid']:
            return {'valid': False, 'reason': f"RUINS: {ruins_validation.get('reason', 'invalid placement')}"}

        return {'valid': True, 'reason': 'Valid single-model deployment'}

    def get_distance_between_units(self, unit1: 'Unit', unit2: 'Unit') -> float:
        """Calculate the shortest distance between any two models in the units."""
        shortest_distance = float('inf')
        for model1 in unit1.models:
            closest_model, distance = model1.return_closest_model_in_unit(unit2)
            shortest_distance = min(shortest_distance, distance)
        return shortest_distance

    def next_turn(self):
        """Advance to the next turn (legacy method - turn advancement now handled in next_phase)."""
        # This method is kept for compatibility but turn advancement is now handled in next_phase()
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        if self.current_player_index == 0:
            self.turn += 1
            # Reset phase to COMMAND_PHASE at the start of a new turn
            self.phase = BattleRoundPhases.COMMAND_PHASE

    def next_phase(self):
        """Advance to the next phase."""
        # Phase-end system actions that should occur before we publish phase_end.
        # NOTE: Reinforcements (arriving from reserves) occur at the end of the Movement phase.
        try:
            if getattr(self.phase, "name", None) == "MOVEMENT_PHASE":
                self.handle_reserves_arrival_phase()
        except Exception:
            pass

        # Publish end of current phase before advancing
        try:
            self.event_system.publish("phase_end", player=self.get_current_player(), phase=self.phase)
        except Exception:
            pass
        current_phase_value = self.phase.value
        next_phase_value = (current_phase_value + 1) % len(BattleRoundPhases)
        self.phase = BattleRoundPhases(next_phase_value)
        # Publish phase start for stratagem triggers
        try:
            self.event_system.publish("phase_start", player=self.get_current_player(), phase=self.phase)
        except Exception:
            pass
        
        # Phase-specific resets are no longer needed since we reset all round state at battle round start
        
        if next_phase_value == 0:  # If we've wrapped around to COMMAND_PHASE
            # End-of-turn scoring happens when a player's turn ends (before switching current player)
            try:
                self.end_of_turn_scoring()
            except Exception:
                pass
            # This means we've finished all phases for the current player
            # Switch to the next player
            self.current_player_index = (self.current_player_index + 1) % len(self.players)

            # Clear enemy model cache when switching players since enemy positions may have changed
            clear_enemy_model_cache(id(self.map))
            print(f"🔄 Player switched to {self.get_current_player().name} - cleared enemy model cache")
            
            # Track who started this battle round if not already set
            if self.battle_round_starting_player_index is None:
                # This is the first player switch of the game - the previous player started the round
                self.battle_round_starting_player_index = (self.current_player_index - 1) % len(self.players)
            
            # Check if we've completed a full battle round (both players have had their turn)
            if self.current_player_index == self.battle_round_starting_player_index:
                # We've cycled back to the player who started this battle round
                # Score end-of-battle-round primaries
                try:
                    self.end_of_battle_round_scoring()
                except Exception:
                    pass
                self.turn += 1
                self.battle_round_starting_player_index = self.current_player_index  # This player starts the next round
                
                # Reset round state for ALL units at the start of a new battle round
                for player in self.players:
                    for unit in player.get_army().units:
                        unit.initialize_round()
                    # Army-level battle round start hook (faction rules/buffs)
                    player.get_army().on_battle_round_start(self.turn)

                # Publish start-of-battle-round hook for UI/faction rules (best-effort)
                self.event_system.publish("battle_round_started", game=self, battle_round=self.turn)
            # Start of COMMAND_PHASE for the new current player
            try:
                self.start_command_phase()
            except Exception:
                pass

    def is_command_phase(self) -> bool:
        return self.phase == BattleRoundPhases.COMMAND_PHASE
    
    def start_command_phase(self) -> None:
        """Start the command phase: active player gains normal CP, then resolves any bonus CP sources."""
        # Core (per official app wording): at the start of your Command phase, before doing anything else,
        # BOTH players gain the normal Command phase CP. This normal CP does not count toward the
        # per-battle-round "bonus CP" guardrail.
        try:
            for p in list(self.players):
                if p is None:
                    continue
                if hasattr(p, "gain_normal_command_phase_cp"):
                    p.gain_normal_command_phase_cp()
                elif hasattr(p, "gain_command_points") and hasattr(p, "get_normal_command_phase_cp_gain"):
                    p.gain_command_points(p.get_normal_command_phase_cp_gain(), is_normal_command_phase_gain=True, reason="Normal Command phase CP")
                else:
                    # Best-effort fallback for legacy Player implementations.
                    try:
                        p.command_points += 1
                    except Exception:
                        pass
        except Exception:
            pass

        # Bonus CP sources that trigger in *your* Command phase (e.g., character alive -> gain 1CP).
        # This is NOT the normal command phase CP, so it is subject to the per-battle-round guardrail.
        try:
            cp_player = self.get_current_player()
            if cp_player is not None and hasattr(cp_player, "get_command_phase_bonus_cp_gain") and hasattr(cp_player, "gain_command_points"):
                bonus = int(cp_player.get_command_phase_bonus_cp_gain() or 0)
                if bonus > 0:
                    cp_player.gain_command_points(bonus, reason="Command phase bonus CP")
        except Exception:
            pass
        # Explicit phase start publish for command phase entry
        try:
            self.event_system.publish("phase_start", player=self.get_current_player(), phase=self.phase)
        except Exception:
            pass

        # Execute command actions for current player's units (without resetting round state)
        current_player = self.get_current_player()
        # Secondary Missions: draw up to two at the start of your Command phase
        before = [getattr(c, 'name', 'Unknown') for c in getattr(current_player, 'active_secondaries', [])]
        current_player.draw_secondary_until_two(self)
        after = [getattr(c, 'name', 'Unknown') for c in getattr(current_player, 'active_secondaries', [])]
        newly_drawn = [name for name in after if name not in before]
        if newly_drawn:
            print(f"🃏 {current_player.name} active Secondaries: {', '.join(after)}")
        # If in fifth battle round and going second, primary scoring is at end of turn, not here
        for unit in current_player.get_army().units:
            # Do battle shock tests and other command phase actions without resetting round state
            if unit.is_below_half_strength():
                print(f"⚠️  {unit.name} is below half strength - taking Battle-Shock test")
                unit.take_battle_shock_test(self.turn)

        # Primary mission scoring at command phase (2nd battle round onwards)
        if hasattr(current_player, 'primary_mission') and isinstance(current_player.primary_mission, PrimaryMissionCard):
            vp = current_player.primary_mission.score_at_command_phase(self, current_player)
            if vp:
                vp_added = current_player.primary_mission.add_score(vp)
                if vp_added:
                    current_player.add_score(vp_added)
                    print(f"🎯 {current_player.name} scored {vp_added} VP from Primary: {current_player.primary_mission.name}")
        else:
            # Maintain legacy objective control updates for other systems
            for obj in self.map.objectives:
                if hasattr(obj, 'location') and hasattr(obj.location, 'update_control'):
                    obj.location.update_control(self)

        # Publish end of Command phase for Stratagems like NEW ORDERS
        try:
            self.event_system.publish("phase_end", player=self.get_current_player(), phase=self.phase)
        except Exception:
            pass

    def is_movement_phase(self) -> bool:
        return self.phase == BattleRoundPhases.MOVEMENT_PHASE

    def is_shooting_phase(self) -> bool:
        return self.phase == BattleRoundPhases.SHOOTING_PHASE

    def is_charge_phase(self) -> bool:
        return self.phase == BattleRoundPhases.CHARGE_PHASE

    def is_fight_phase(self) -> bool:
        return self.phase == BattleRoundPhases.FIGHT_PHASE

    def can_score_objectives(self) -> bool:
        """Check if objectives can grant points in the current battle round.

        According to Warhammer 40k rules, objectives cannot grant points until
        the 2nd battle round.

        Returns:
            bool: True if objectives can grant points, False otherwise
        """
        return self.turn >= 2

    def get_battle_round(self) -> int:
        """Get the current battle round number.

        Returns:
            int: Current battle round (1-based)
        """
        return self.turn

    # ---------- Scoring windows and tracking ----------

    def end_of_turn_scoring(self) -> None:
        """Apply end-of-turn scoring for primaries and secondaries, manage discard rules and CP gain."""
        current_player = self.get_current_player()

        # Track destroyed units for this turn should already be collected elsewhere; ensure attribute exists
        if not hasattr(self, 'destroyed_units_this_turn'):
            self.destroyed_units_this_turn = []
        if not hasattr(self, 'completed_actions_this_turn'):
            self.completed_actions_this_turn = []

        # Primary: special cases that score at end of turn (e.g., Terraform 1VP per terraformed objective)
        if hasattr(current_player, 'primary_mission') and isinstance(current_player.primary_mission, PrimaryMissionCard):
            vp = current_player.primary_mission.score_at_end_of_turn(self, current_player)
            if vp:
                vp_added = current_player.primary_mission.add_score(vp)
                if vp_added:
                    current_player.add_score(vp_added)
                    print(f"🎯 {current_player.name} scored {vp_added} VP (end of turn) from Primary: {current_player.primary_mission.name}")

        # Secondary: evaluate all active cards at end of either player's turn
        achieved: list[SecondaryMissionCard] = []
        total_secondary_vp = 0
        for card in list(getattr(current_player, 'active_secondaries', [])):
            try:
                result = card.score_at_end_of_turn(self, current_player)
            except Exception:
                result = None
            if not result:
                continue
            if result.vp:
                added = card.add_score(result.vp)
                if added:
                    current_player.add_score(added)
                    total_secondary_vp += added
                    print(f"🎯 {current_player.name} scored {added} VP from Secondary: {card.name}")
            if getattr(result, 'achieved', False):
                achieved.append(card)

        # a) If you scored 1+ VP from a Secondary, discard that card (achieved)
        if total_secondary_vp > 0:
            current_player.discard_achieved_secondaries(achieved)

        # b) Allow voluntary discard for current player to gain 1CP (UI/AI should call explicitly). Here we do nothing automatically.

        # c) If deck runs out, player cannot generate additional secondaries (handled by deck empty check during draws)

        # Complete mission Actions that trigger at this end of turn
        self._complete_actions_for_turn_end(current_player)

        # Clear per-turn event lists
        self.destroyed_units_this_turn = []
        self.completed_actions_this_turn = []
        self.models_destroyed_this_turn = []

    def end_of_battle_round_scoring(self) -> None:
        """Apply end-of-battle-round scoring for primaries that need it (e.g., Purge the Foe)."""
        # Build destroyed counts if not present
        if not hasattr(self, 'destroyed_units_this_battle_round_by_player'):
            self.destroyed_units_this_battle_round_by_player = {}
        for player in self.players:
            # Primary mission score
            if hasattr(player, 'primary_mission') and isinstance(player.primary_mission, PrimaryMissionCard):
                try:
                    vp = player.primary_mission.score_at_end_of_battle_round(self, player)
                except Exception:
                    vp = 0
                if vp:
                    added = player.primary_mission.add_score(vp)
                    if added:
                        player.add_score(added)
                        print(f"🎯 {player.name} scored {added} VP (end of battle round) from Primary: {player.primary_mission.name}")

    def record_unit_destroyed(self, unit: 'Unit') -> None:
        """Record a unit destroyed event and incrementally score relevant secondaries."""
        try:
            self.destroyed_units_this_turn.append(unit)
        except Exception:
            pass
        # Tally for Purge the Foe end-of-battle-round scoring
        try:
            owner_player = unit.get_parent_army().player if unit.get_parent_army() else None
            if owner_player is not None:
                self.destroyed_units_this_battle_round_by_player[owner_player] = self.destroyed_units_this_battle_round_by_player.get(owner_player, 0) + 1
        except Exception:
            pass
        # Incremental scoring for active secondaries (No Prisoners, Overwhelming Force)
        try:
            owner_player = unit.get_parent_army().player if unit.get_parent_army() else None
            for player in self.players:
                if player is owner_player:
                    continue
                for card in getattr(player, 'active_secondaries', []) or []:
                    if hasattr(card, 'on_unit_destroyed'):
                        try:
                            points = card.on_unit_destroyed(self, player, unit)
                        except Exception:
                            points = 0
                        if points:
                            added = card.add_score(points)
                            if added:
                                player.add_score(added)
                                print(f"🎯 {player.name} scored {added} VP from Secondary: {card.name} (unit destroyed)")
        except Exception:
            pass

    # ---------- Mission Action APIs ----------

    def _is_unit_eligible_to_start_action(self, unit: 'Unit') -> Dict[str, Any]:
        # Not if Aircraft
        if getattr(unit, 'is_aircraft', False):
            return {"valid": False, "reason": "Aircraft cannot perform Actions"}
        # Not if Battle-shocked
        if unit.is_battle_shocked():
            return {"valid": False, "reason": "Battle-shocked units cannot perform Actions"}
        # OC 0 cannot perform
        if getattr(unit, 'objective_control', 0) == 0:
            return {"valid": False, "reason": "Units with OC 0 cannot perform Actions"}
        # Not if within engagement range of any enemy (unless TITANIC CHARACTER)
        if any(self.map.is_within_engagement_range(unit, enemy)
               for enemy in self.map.get_enemy_units(unit) if enemy.is_alive()):
            if not (getattr(unit, 'is_titanic', False) and getattr(unit, 'is_character', False)):
                return {"valid": False, "reason": "Units in Engagement Range cannot perform Actions"}
        # Not if advanced or fell back
        if unit.round_state.advanced_this_round or unit.round_state.fell_back_this_round:
            return {"valid": False, "reason": "Units that Advanced or Fell Back cannot perform Actions"}
        # Not if not eligible to shoot this phase (includes units that have already been selected to shoot)
        if unit.round_state.shot_this_round:
            return {"valid": False, "reason": "Units already selected to shoot cannot start an Action this phase"}
        return {"valid": True, "reason": "Eligible"}

    def _unit_is_in_player_deployment(self, player: Player, unit: 'Unit') -> bool:
        try:
            zones = self.deployment_zones.get(player.name, {})
            zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
            if not zone:
                return False
            # Use first alive model position
            for model in unit.models:
                if model.is_alive:
                    pos = model.get_location()
                    if pos and hasattr(zone, 'contains_point') and zone.contains_point(pos[0], pos[1]):
                        return True
            return False
        except Exception:
            return False

    def _objective_in_player_deployment(self, player: Player, objective_point) -> bool:
        try:
            zones = self.deployment_zones.get(player.name, {})
            zone = zones.get('zone') or zones.get('Defender Zone') or zones.get('Attacker Zone')
            if not zone:
                return False
            return hasattr(zone, 'contains_point') and zone.contains_point(objective_point.x, objective_point.y)
        except Exception:
            return False

    def _unit_within_any_terrain_feature(self, unit: 'Unit') -> bool:
        try:
            for model in unit.models:
                if not model.is_alive:
                    continue
                base_geom = model.model_base.get_base_shape()
                for t in self.map.terrain_features:
                    if base_geom.intersects(t.footprint):
                        return True
            return False
        except Exception:
            return False

    def _unit_within_range_of_objective(self, unit: 'Unit') -> Optional[Objective]:
        # Return the Objective (from map.objectives) whose point area intersects the unit
        from shapely.geometry import Point as _ShPoint
        for obj in getattr(self.map, 'objectives', []):
            loc = getattr(obj, 'location', None)
            if not loc:
                continue
            area = _ShPoint(loc.x, loc.y).buffer(loc.control_radius)
            for model in unit.models:
                if not model.is_alive:
                    continue
                try:
                    base = model.model_base.get_base_shape()
                    if base.intersects(area):
                        return obj
                except Exception:
                    # Fallback distance check
                    mpos = model.get_location()
                    if mpos:
                        dx = mpos[0] - loc.x
                        dy = mpos[1] - loc.y
                        if (dx*dx + dy*dy) ** 0.5 <= (loc.control_radius + getattr(model.model_base, 'get_radius', lambda: 1.0)()):
                            return obj
        return None

    def can_start_terraform(self, unit: 'Unit') -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Terraform starts in your Shooting phase"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        # Must be within range of an objective not within your deployment zone
        obj = self._unit_within_range_of_objective(unit)
        if not obj:
            return {"valid": False, "reason": "Unit not within range of an objective"}
        # Objective must not be within your deployment zone
        if self._objective_in_player_deployment(unit.get_parent_army().player, obj.location):
            return {"valid": False, "reason": "Objective is within your deployment zone"}
        return {"valid": True, "reason": "Eligible", "objective": obj}

    def can_start_sabotage(self, unit: 'Unit') -> Dict[str, Any]:
        # Must be Shooting phase
        if not self.is_shooting_phase():
            return {"valid": False, "reason": "Sabotage starts in your Shooting phase"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        # Must be within a terrain feature and not within your deployment zone
        if not self._unit_within_any_terrain_feature(unit):
            return {"valid": False, "reason": "Unit must be within a terrain feature"}
        if self._unit_is_in_player_deployment(unit.get_parent_army().player, unit):
            return {"valid": False, "reason": "Unit is within your deployment zone"}
        return {"valid": True, "reason": "Eligible"}

    def start_terraform_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_terraform(unit)
        if not check["valid"]:
            return check
        objective = check.get("objective")
        # Mark unit round state and add in-progress
        unit.round_state.performing_action_name = 'TERRAFORM'
        unit.round_state.action_locked_until_turn_end = True
        # Complete at end of this player's turn
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'TERRAFORM',
            'started_turn': self.turn,
            'completes_on_player_index': self.current_player_index,
            'metadata': {'objective': objective}
        })
        return {"valid": True, "reason": "Terraform started"}

    def start_sabotage_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_sabotage(unit)
        if not check["valid"]:
            return check
        unit.round_state.performing_action_name = 'SABOTAGE'
        unit.round_state.action_locked_until_turn_end = True
        # Completes at end of opponent's next turn
        opponent_index = (self.current_player_index + 1) % len(self.players)
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'SABOTAGE',
            'started_turn': self.turn,
            'completes_on_player_index': opponent_index,
            'metadata': {}
        })
        return {"valid": True, "reason": "Sabotage started"}

    # Scorched Earth: Burn Objective (BR2+)
    def can_start_burn_objective(self, unit: 'Unit') -> Dict[str, Any]:
        # Only available if player's primary is Scorched Earth
        prim = getattr(unit.get_parent_army().player, 'primary_mission', None)
        from .mission_cards import ScorchedEarthPrimary
        if not isinstance(prim, ScorchedEarthPrimary):
            return {"valid": False, "reason": "Primary mission is not Scorched Earth"}
        if self.get_battle_round() < 2:
            return {"valid": False, "reason": "Burn Objective starts from the second battle round"}
        base = self._is_unit_eligible_to_start_action(unit)
        if not base["valid"]:
            return base
        obj = self._unit_within_range_of_objective(unit)
        if not obj:
            return {"valid": False, "reason": "Unit not within range of an objective"}
        # Not within your deployment zone
        if self._objective_in_player_deployment(unit.get_parent_army().player, obj.location):
            return {"valid": False, "reason": "Objective is within your deployment zone"}
        return {"valid": True, "reason": "Eligible", "objective": obj}

    def start_burn_objective_action(self, unit: 'Unit') -> Dict[str, Any]:
        check = self.can_start_burn_objective(unit)
        if not check["valid"]:
            return check
        objective = check.get("objective")
        unit.round_state.performing_action_name = 'BURN_OBJECTIVE'
        unit.round_state.action_locked_until_turn_end = True
        opponent_index = (self.current_player_index + 1) % len(self.players)
        self.in_progress_actions.append({
            'player': unit.get_parent_army().player,
            'unit': unit,
            'action_name': 'BURN_OBJECTIVE',
            'started_turn': self.turn,
            'completes_on_player_index': opponent_index,
            'metadata': {'objective': objective}
        })
        return {"valid": True, "reason": "Burn Objective started"}

    def _complete_actions_for_turn_end(self, turn_ending_player: Player) -> None:
        # Evaluate any in-progress actions that complete at this player's turn end
        remaining = []
        for entry in self.in_progress_actions:
            completes_on = entry.get('completes_on_player_index')
            if completes_on != self.current_player_index:
                remaining.append(entry)
                continue
            unit = entry.get('unit')
            action_name = entry.get('action_name')
            actor = entry.get('player')
            # Validate unit still on battlefield
            if not unit or not unit.is_alive() or not unit.deployed:
                # Action fails silently
                if unit:
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                continue
            try:
                if action_name == 'TERRAFORM':
                    # Must still be within range of same objective and control it
                    objective = entry['metadata'].get('objective')
                    loc = getattr(objective, 'location', None)
                    if loc and hasattr(loc, 'update_control'):
                        loc.update_control(self)
                    # Check in-range
                    in_range = False
                    if objective:
                        in_range = (self._unit_within_range_of_objective(unit) == objective)
                    controls = loc and getattr(loc, 'controlling_player', None) is actor
                    if in_range and controls:
                        # Mark terraformed and record completed action
                        if loc:
                            loc.terraformed_by = actor
                        self.completed_actions_this_turn.append({
                            'player': actor,
                            'action_name': 'TERRAFORM',
                            'unit_location': unit.get_closest_model_position_to_target((loc.x, loc.y, loc.z)) if loc else None
                        })
                    # Clear unit state
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                elif action_name == 'SABOTAGE':
                    # Completes if the unit is on the battlefield
                    self.completed_actions_this_turn.append({
                        'player': actor,
                        'action_name': 'SABOTAGE',
                        'unit_location': unit.get_closest_model_position_to_target(unit.models[0].get_location() if unit.models else (0, 0, 0))
                    })
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                elif action_name == 'BURN_OBJECTIVE':
                    objective = entry['metadata'].get('objective')
                    loc = getattr(objective, 'location', None)
                    if loc and hasattr(loc, 'update_control'):
                        loc.update_control(self)
                    in_range = False
                    if objective:
                        in_range = (self._unit_within_range_of_objective(unit) == objective)
                    controls = loc and getattr(loc, 'controlling_player', None) is actor
                    if in_range and controls and not getattr(loc, 'removed', False):
                        # Determine zone of objective for VP
                        in_opponent_dz = False
                        try:
                            opponent = [p for p in self.players if p is not actor][0]
                            zones = self.deployment_zones.get(opponent.name, {})
                            zone = zones.get('zone') or zones.get('Attacker Zone') or zones.get('Defender Zone')
                            if zone and hasattr(zone, 'contains_point'):
                                in_opponent_dz = zone.contains_point(loc.x, loc.y)
                        except Exception:
                            in_opponent_dz = False
                        vp = 10 if in_opponent_dz else 5
                        # Remove the objective
                        loc.removed = True
                        print("🔥 Scorched Earth burned objective at ({:.1f}, {:.1f})".format(loc.x, loc.y))
                        # Immediate scoring per mission rules (Any time when burned)
                        added = actor.primary_mission.add_score(vp) if hasattr(actor, 'primary_mission') else vp
                        actor.add_score(added)
                        print(f"🎯 {actor.name} scored {added} VP for burning objective")
                    unit.round_state.performing_action_name = None
                    unit.round_state.action_locked_until_turn_end = False
                else:
                    remaining.append(entry)
            except Exception:
                # On error, keep the action to avoid data loss
                remaining.append(entry)
        self.in_progress_actions = remaining

    def is_game_over(self) -> bool:
        if self.turn > TOTAL_ROUNDS:
            return True
        return False

    def get_winner(self) -> Player | None:
        # Return the winning player or None if the game is not over
        if self.is_game_over():
            return max(self.players, key=lambda player: player.get_score(), default=None)
        return None

    def get_loser(self) -> Player | None:
        if self.is_game_over():
            return min(self.players, key=lambda player: player.get_score(), default=None)
        return None

    def get_state(self) -> Dict[str, Any]:
        # Return the current game state as a dictionary
        # TODO - might be overcome by the implementation of "extract_state_features()" in hrl_agent.py
        return {
            "players": self.players,
            "battlefield": self.battlefield,
            "map": self.map,
            "current_player": self.get_current_player(),
            "turn": self.turn,
            "phase": self.phase,
        }

    def attempt_charge(self, charging_unit: 'Unit', target_unit: 'Unit') -> bool:
        """Attempt a charge move with the given unit against the target.
        
        According to 10th edition rules, a successful charge requires at least one model
        of the charging unit to end their charge with edge-to-edge distance of 1" or less
        from at least one model in the target unit.
        
        CRITICAL: If the charge roll is insufficient to reach within 1" of the enemy,
        the charge fails completely and NO MODELS MOVE AT ALL.
        """
        if not charging_unit.can_declare_charge_against(target_unit, self):
            return False

        # Calculate current edge-to-edge distance between units
        current_distance = self.map.get_distance_between_units(charging_unit, target_unit)
        
        # For a successful charge, we need to achieve edge-to-edge distance of 1" or less
        # So we need to move: current_distance - 1.0 inches
        distance_needed = max(0, current_distance - 1.0)

        # Roll 2D6 for charge distance with modifiers - show individual dice
        dice_collection = DiceCollection.from_string("2D6")
        base_charge_roll, individual_dice = dice_collection.roll_detailed()
        # Publish roll event for Command Re-roll
        try:
            def _reroll():
                new_total, new_individual = DiceCollection.from_string("2D6").roll_detailed()
                nonlocal base_charge_roll
                base_charge_roll = new_total
                return new_total, new_individual
            self.event_system.publish("roll_made", player=charging_unit.get_parent_army().player, unit=charging_unit, roll_type="charge", value=base_charge_roll, dice=individual_dice, reroll=_reroll)
        except Exception:
            pass
        charge_roll = self._apply_charge_modifiers(charging_unit, base_charge_roll)
        
        print(f"⚔️ {charging_unit.name} charging {target_unit.name}")
        print(f"⚔️ Current edge-to-edge distance: {current_distance:.1f}\"")
        print(f"⚔️ Distance needed to achieve ≤1\" edge-to-edge: {distance_needed:.1f}\"")
        print(f"⚔️ Charge roll: {base_charge_roll} (rolled {individual_dice}) (modified: {charge_roll})")
        
        # CRITICAL RULE: If charge roll is insufficient, charge fails and no models move
        if charge_roll < distance_needed:
            print(f"❌ Charge failed: roll {charge_roll}\" insufficient to reach within 1\" (needed {distance_needed:.1f}\")")
            print(f"❌ No models move - charge failed completely")
            return False

        # Charge roll is sufficient - now attempt the movement
        # Find the closest models between the two units for accurate distance calculation
        charging_pos = None
        target_pos = None
        closest_distance = float('inf')

        for charging_model in charging_unit.models:
            if not charging_model.is_alive:
                continue
            for target_model in target_unit.models:
                if not target_model.is_alive:
                    continue

                from ..utility.aura_utils import distance_between_models_bases_3d
                distance = float(distance_between_models_bases_3d(charging_model, target_model))

                if distance < closest_distance:
                    closest_distance = distance
                    c_pos = charging_model.get_location()
                    t_pos = target_model.get_location()
                    charging_pos = c_pos
                    target_pos = t_pos

        if not charging_pos or not target_pos:
            print(f"❌ Charge failed: invalid positions")
            return False

        # CRITICAL: Store original model positions BEFORE attempting movement
        # This allows proper rollback if charge fails to achieve engagement range
        original_model_positions = []
        for model in charging_unit.models:
            original_model_positions.append(model.get_location())
        
        # Calculate direction vector from charging unit to target
        dx = target_pos[0] - charging_pos[0]
        dy = target_pos[1] - charging_pos[1]
        
        # Normalize the direction vector
        distance_to_target = (dx**2 + dy**2)**0.5
        if distance_to_target == 0:
            print(f"❌ Charge failed: units are at same position")
            return False
        
        dx /= distance_to_target
        dy /= distance_to_target
        
        # Move the charging unit towards the target up to the charge roll distance
        # Move as close as possible within the charge roll distance for better pile-in positioning
        movement_distance = min(charge_roll, current_distance - 0.1)  # Get as close as possible without overlapping
        new_x = charging_pos[0] + dx * movement_distance
        new_y = charging_pos[1] + dy * movement_distance
        new_z = self.map.get_height_at_point(new_x, new_y)
        
        # Attempt to move the unit with special charge movement logic
        # During charge, units should be able to move into engagement range
        success = charging_unit.charge_move((new_x, new_y, new_z), self.map, target_unit)
        if success:
            # Check if the charge actually achieved engagement range (≤1.0")
            final_distance = self.map.get_distance_between_units(charging_unit, target_unit)
            
            if final_distance <= 1.0:
                charging_unit.round_state.charged_this_round = True
                print(f"✅ Charge successful: {charging_unit.name} achieved {final_distance:.1f}\" edge-to-edge distance with {target_unit.name}")
                return True
            else:
                print(f"❌ Charge failed: {charging_unit.name} achieved {final_distance:.1f}\" edge-to-edge distance (not ≤1.0\") with {target_unit.name}")
                # CRITICAL: Revert all model positions if charge failed to achieve engagement range
                # This ensures that NO MODELS MOVE when a charge fails
                print(f"❌ Charge failed: Reverting all model positions - no models should move on failed charge")
                
                # Restore original positions
                for i, original_pos in enumerate(original_model_positions):
                    if i < len(charging_unit.models):
                        charging_unit.models[i].set_location(*original_pos)
                
                # Unit position is now derived from model positions, no need to restore
                
                return False
        else:
            print(f"❌ Charge failed: could not move unit")
            # CRITICAL: Restore original positions if charge_move failed completely
            print(f"❌ Charge failed: Reverting all model positions - no models should move on failed charge")
            
            # Restore original positions
            for i, original_pos in enumerate(original_model_positions):
                if i < len(charging_unit.models):
                    charging_unit.models[i].set_location(*original_pos)
            
            # Unit position is now derived from model positions, no need to restore
            
            return False
    
    def _apply_charge_modifiers(self, charging_unit: 'Unit', base_roll: int) -> int:
        """Apply charge roll modifiers based on unit abilities, stratagems, etc."""
        modified_roll = base_roll
        
        # Check for charge modifiers from abilities
        # TODO: Implement ability-based charge modifiers
        # Examples:
        # - Shock Assault Stratagem: +1" to charge roll
        # - Swift and Deadly ability: re-roll one dice
        # - Relentless Advance trait: roll 3 dice and drop the lowest
        
        # For now, just return the base roll
        return modified_roll
    
    def get_eligible_charging_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that are eligible to declare charges."""
        eligible_units = []
        
        for unit in player.get_army().units:
            if not unit.is_alive() or not unit.deployed:
                continue
            
            # Check if unit has already attempted a charge this round
            if unit.round_state.attempted_charge_this_round:
                continue
            
            # Check if unit advanced this round (unless special abilities allow charging after advance)
            if unit.round_state.advanced_this_round:
                # TODO: Check for special abilities that allow charging after advance
                continue
            
            # Check if unit fell back this round (unless special abilities allow charging after fall back)
            if unit.round_state.fell_back_this_round:
                # TODO: Check for special abilities that allow charging after fall back
                continue
            
            # Check if unit is already in engagement range
            enemy_units = self.get_enemy_units(player)
            is_engaged = any(self.map.is_within_engagement_range(unit, enemy) 
                           for enemy in enemy_units if enemy.is_alive())
            if is_engaged:
                continue
            
            # Check if there are any valid charge targets
            has_valid_targets = any(unit.can_declare_charge_against(target, self) 
                                  for target in enemy_units if target.is_alive())
            if has_valid_targets:
                eligible_units.append(unit)
        
        return eligible_units
    
    def is_charge_phase_complete(self, player: Player) -> bool:
        """Check if the charge phase is complete for the current player."""
        eligible_units = self.get_eligible_charging_units(player)
        return len(eligible_units) == 0

    ###########################################################################
    # Fight Phase
    ###########################################################################
    def get_eligible_fighting_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that are eligible to fight in the Fight Phase.
        
        A unit is eligible to fight if it:
        - Is alive and deployed
        - Is within engagement range of enemy units OR made a charge move this turn
        
        Args:
            player: The player whose units to check
            
        Returns:
            List of units eligible to fight
        """
        eligible_units = []
        
        for unit in player.get_army().units:
            if unit.is_eligible_to_fight(self.map):
                eligible_units.append(unit)
        
        return eligible_units
    
    def get_fight_first_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that should fight in the Fight First stage.
        
        Units fight first if they:
        - Charged this turn OR
        - Have an inherent Fight First ability
        
        Args:
            player: The player whose units to check
            
        Returns:
            List of units that should fight in the Fight First stage
        """
        fight_first_units = []
        eligible_units = self.get_eligible_fighting_units(player)
        
        for unit in eligible_units:
            if unit.should_fight_first():
                fight_first_units.append(unit)
        
        return fight_first_units
    
    def get_remaining_combatant_units(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that should fight in the Remaining Combatants stage.
        
        These are units that are eligible to fight but do not fight first.
        
        Args:
            player: The player whose units to check
            
        Returns:
            List of units that should fight in the Remaining Combatants stage
        """
        remaining_units = []
        eligible_units = self.get_eligible_fighting_units(player)
        
        for unit in eligible_units:
            if not unit.should_fight_first():
                remaining_units.append(unit)
        
        return remaining_units
    
    def get_fight_phase_units_by_stage(self, player: Player) -> dict:
        """Get all fighting units for a player categorized by fight stage.
        
        Args:
            player: The player whose units to categorize
            
        Returns:
            Dictionary with 'fight_first' and 'remaining_combatants' keys containing lists of units
        """
        return {
            'fight_first': self.get_fight_first_units(player),
            'remaining_combatants': self.get_remaining_combatant_units(player)
        }
    
    def is_fight_phase_complete(self, player: Player) -> bool:
        """Check if the fight phase is complete for the current player.
        
        The fight phase is complete when there are no more eligible fighting units.
        
        Args:
            player: The player to check
            
        Returns:
            True if the fight phase is complete for this player
        """
        eligible_units = self.get_eligible_fighting_units(player)
        return len(eligible_units) == 0

    ###########################################################################
    ### Reserves System
    ###########################################################################
    def get_units_in_reserves(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that are currently in reserves."""
        return [unit for unit in player.get_army().units if unit.is_in_reserves()]
    
    def get_units_that_can_arrive_from_reserves(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that can arrive from reserves this turn."""
        return [unit for unit in self.get_units_in_reserves(player) 
                if unit.can_arrive_from_reserves(self.turn)]
    
    def get_units_that_must_arrive_from_reserves(self, player: Player) -> List['Unit']:
        """Get all units belonging to a player that must arrive from reserves this turn or be destroyed."""
        return [unit for unit in self.get_units_in_reserves(player) 
                if unit.must_arrive_from_reserves(self.turn)]
    
    def destroy_units_not_arrived_from_reserves(self, player: Player) -> List['Unit']:
        """Destroy all units that did not arrive from reserves by the deadline."""
        units_to_destroy = []
        
        for unit in self.get_units_in_reserves(player):
            if self.turn > 3:  # After turn 3, units in reserves are destroyed
                units_to_destroy.append(unit)
                logger.warning(f"💀 {unit.name} destroyed - failed to arrive from reserves by turn 3")
        
        # Remove destroyed units from the army
        for unit in units_to_destroy:
            player.get_army().units.remove(unit)
        
        return units_to_destroy
    
    def can_place_unit_arriving_from_reserves(self, unit: 'Unit', position: Tuple[float, float, float], 
                                              battlefield_edge: str = None) -> bool:
        """Check if a unit can be legally placed when arriving from reserves.
        
        Args:
            unit: The unit arriving from reserves
            position: (x, y, z) position where the unit would be placed
            battlefield_edge: For strategic reserves, which edge they're arriving from
                             ('own', 'left', 'right', 'enemy') 
        
        Returns:
            bool: True if the placement is legal
        """
        # Check if position is within battlefield bounds
        if (position[0] < 0 or position[0] >= self.battlefield.width or
            position[1] < 0 or position[1] >= self.battlefield.height):
            return False
        
        # Strategic Reserves vs Deep Strike choice:
        # If a unit with Deep Strike arrives from Strategic Reserves, it may be set up using either:
        # - Strategic Reserves rules (edge within 6", plus turn-based allowed edges), OR
        # - Deep Strike rules (anywhere, still respecting the 9" from enemies restriction).
        strategic_ok = True
        if unit.is_in_strategic_reserves():
            strategic_ok = False
            # Determine which edge(s) to validate
            candidate_edges = []
            if battlefield_edge:
                candidate_edges = [battlefield_edge]
            else:
                candidate_edges = ["own", "left", "right", "enemy"]

            for edge in candidate_edges:
                if not self.is_valid_strategic_reserves_edge(edge):
                    continue
                edge_distance = self.get_distance_to_battlefield_edge(position, edge)
                if edge_distance <= 6.0:
                    strategic_ok = True
                    break
        
        # Check 9" restriction from enemy models using base-to-base closest-point distance.
        # We validate against the unit's *actual* prospective formation at this position.
        snapshot = [m.get_location() for m in unit.models]
        try:
            prospective = unit.calculate_model_positions(position[0], position[1], self.map, avoid_friendly_units=True)
        finally:
            for m, loc in zip(unit.models, snapshot):
                if loc:
                    m.set_location(*loc)

        if not prospective:
            return False

        from ..utility.aura_utils import distance_between_bases_3d
        enemy_units = self.get_enemy_units(unit.get_parent_army().player)
        enemy_models = [em for eu in enemy_units if eu.is_alive() and eu.deployed for em in eu.models if em.is_alive]

        for idx, (x, y, z, facing) in enumerate(prospective):
            if idx >= len(unit.models):
                break
            mb = unit._create_potential_base(x, y, z, facing, model=unit.models[idx])
            for em in enemy_models:
                if float(distance_between_bases_3d(mb, em.model_base)) < 9.0:
                    return False

        if unit.is_in_strategic_reserves():
            deep_strike_ok = bool(unit.has_deep_strike())
            return bool(strategic_ok or deep_strike_ok)

        return True
    
    def is_valid_strategic_reserves_edge(self, battlefield_edge: str) -> bool:
        """Check if the specified battlefield edge is valid for strategic reserves arrival.
        
        Args:
            battlefield_edge: 'own', 'left', 'right', 'enemy'
        
        Returns:
            bool: True if the edge is valid for the current turn
        """
        if self.turn == 2:
            # Turn 2: Can only arrive from own battlefield edge
            return battlefield_edge == 'own'
        elif self.turn >= 3:
            # Turn 3+: Can arrive from any edge except enemy's
            return battlefield_edge in ['own', 'left', 'right']
        else:
            # Turn 1: No strategic reserves arrivals allowed
            return False
    
    def get_distance_to_battlefield_edge(self, position: Tuple[float, float, float], 
                                       battlefield_edge: str) -> float:
        """Calculate distance from a position to the specified battlefield edge.
        
        Args:
            position: (x, y, z) position
            battlefield_edge: 'own', 'left', 'right', 'enemy'
        
        Returns:
            float: Distance to the edge in inches
        """
        x, y, z = position
        
        if battlefield_edge == 'own':
            # Assuming own edge is at y=0 (bottom)
            return y
        elif battlefield_edge == 'enemy':
            # Assuming enemy edge is at y=battlefield.height (top)
            return self.battlefield.height - y
        elif battlefield_edge == 'left':
            # Left edge at x=0
            return x
        elif battlefield_edge == 'right':
            # Right edge at x=battlefield.width
            return self.battlefield.width - x
        else:
            return float('inf')  # Invalid edge
    
    def handle_reserves_arrival_phase(self) -> Dict[str, List['Unit']]:
        """Handle the reserves arrival phase at the end of movement phase.
        
        This should be called at the end of each player's movement phase.
        
        Returns:
            Dict mapping player names to lists of units that arrived from reserves
        """
        arrival_results = {}
        current_player = self.get_current_player()
        
        # Handle reserves arrivals for the current player
        units_arrived = self.process_player_reserves_arrivals(current_player)
        arrival_results[current_player.name] = units_arrived
        
        # Destroy units that must arrive but didn't
        destroyed_units = self.destroy_units_not_arrived_from_reserves(current_player)
        if destroyed_units:
            logger.warning(f"💀 {len(destroyed_units)} units destroyed for {current_player.name} - failed to arrive from reserves")
        
        return arrival_results
    
    def process_player_reserves_arrivals(self, player: Player) -> List['Unit']:
        """Process reserves arrivals for a specific player.
        
        This method should be extended or overridden to integrate with AI decision making.
        
        Args:
            player: The player whose reserves arrivals to process
        
        Returns:
            List of units that arrived from reserves
        """
        units_arrived = []
        units_that_can_arrive = self.get_units_that_can_arrive_from_reserves(player)
        units_that_must_arrive = self.get_units_that_must_arrive_from_reserves(player)
        
        # For now, this is a placeholder implementation
        # In the full implementation, this should integrate with AI agents to make decisions
        logger.info(f"🪂 {player.name} has {len(units_that_can_arrive)} units that can arrive from reserves")
        
        # Force arrival of units that must arrive
        for unit in units_that_must_arrive:
            # Try to find a valid placement position
            # Simple automatic deployment - AI agents handle their own deployment decisions
            valid_position = self.find_valid_reserves_position(unit)
            if valid_position:
                if unit.arrive_from_reserves(valid_position, self.turn, self.map):
                    units_arrived.append(unit)
                    self.map.units.append(unit)  # Add to map
                else:
                    logger.error(f"❌ Failed to deploy {unit.name} from reserves despite finding valid position")
            else:
                logger.warning(f"⚠️ No valid position found for {unit.name} - unit will be destroyed")
        
        return units_arrived
    
    def find_valid_reserves_position(self, unit: 'Unit') -> Optional[Tuple[float, float, float]]:
        """Find a valid position for a unit arriving from reserves.
        
        This is a basic implementation that tries to find any valid position.
        Should be enhanced with proper AI decision making.
        
        Args:
            unit: The unit arriving from reserves
        
        Returns:
            Valid position tuple or None if no valid position found
        """
        # Try multiple positions across the battlefield
        attempts = 100
        
        for _ in range(attempts):
            if unit.is_in_strategic_reserves():
                # If the unit also has Deep Strike, it may choose to arrive using Deep Strike rules instead.
                try:
                    if unit.has_deep_strike():
                        import random
                        x = random.uniform(9.0, self.battlefield.width - 9.0)
                        y = random.uniform(9.0, self.battlefield.height - 9.0)
                        z = self.map.get_height_at_point(x, y)
                        position = (x, y, z)
                        if self.can_place_unit_arriving_from_reserves(unit, position):
                            return position
                except Exception:
                    pass

                # For strategic reserves, try positions near valid edges
                edge = 'own' if self.turn == 2 else 'own'  # Could be expanded to try different edges
                if edge == 'own':
                    x = self.battlefield.width * 0.5  # Center of battlefield
                    y = 5.0  # 5" from own edge
                elif edge == 'left':
                    x = 5.0  # 5" from left edge
                    y = self.battlefield.height * 0.5
                elif edge == 'right':
                    x = self.battlefield.width - 5.0  # 5" from right edge
                    y = self.battlefield.height * 0.5
                else:
                    continue
                    
                z = self.map.get_height_at_point(x, y)
                position = (x, y, z)
                
                if self.can_place_unit_arriving_from_reserves(unit, position, edge):
                    return position
            else:
                # For standard reserves (Deep Strike), can arrive anywhere more than 9" from enemies
                import random
                x = random.uniform(9.0, self.battlefield.width - 9.0)
                y = random.uniform(9.0, self.battlefield.height - 9.0)
                z = self.map.get_height_at_point(x, y)
                position = (x, y, z)
                
                if self.can_place_unit_arriving_from_reserves(unit, position):
                    return position
        
        return None  # No valid position found

    def get_first_turn_player_index(self) -> int:
        """Get the index of player who goes first (will be set during DETERMINE_FIRST_TURN_ORDER)"""
        return self.first_turn_player_index
    
    def is_in_setup_phase(self) -> bool:
        """Check if we're still in the setup phase."""
        return not self.setup_complete
    
    def get_current_setup_phase(self) -> SetupPhase:
        """Get the current setup phase."""
        return self.setup_phase
    
    def advance_setup_phase(self) -> bool:
        """Advance to the next setup phase. Returns True if setup is complete."""
        if self.setup_complete:
            return True
        
        current_phase_value = self.setup_phase.value
        next_phase_value = current_phase_value + 1
        
        if next_phase_value >= len(SetupPhase):
            # Setup is complete, start battle rounds
            self.setup_complete = True
            # Set current player to first turn player
            if self.first_turn_player_index is not None:
                self.current_player_index = self.first_turn_player_index
            else:
                # Default: attacker goes first
                self.current_player_index = self.attacker_index if self.attacker_index is not None else 0
            
            # Set the battle round starting player to whoever goes first
            self.battle_round_starting_player_index = self.current_player_index
            self.phase = BattleRoundPhases.COMMAND_PHASE

            # Show detailed first turn information
            first_turn_player = self.get_current_player()
            if self.first_turn_player_index == self.attacker_index:
                role = "Attacker"
            elif self.first_turn_player_index == self.defender_index:
                role = "Defender"
            else:
                role = "Player"

            print(f"🎉 Setup complete! {first_turn_player.name} ({role}) goes first")
            return True
        else:
            self.setup_phase = SetupPhase(next_phase_value)
            print(f"📋 Advanced to setup phase: {self.setup_phase.name}")
            return False

    def execute_muster_armies_phase(self, player1_army_file: str = None, player2_army_file: str = None) -> None:
        """Phase 1: Muster Armies - Load army lists for both players."""
        print("📋 MUSTER ARMIES: Loading army lists...")
        
        # Use army files from game.army_files if not provided as parameters
        if player1_army_file is None:
            player1_army_file = getattr(self, 'army_files', {}).get('player1', 'army_lists/warhammer_app_dump.txt')
        if player2_army_file is None:
            player2_army_file = getattr(self, 'army_files', {}).get('player2', 'army_lists/chaos_daemons_GT2023.txt')
        
        # Validate army files exist
        import os
        if not os.path.exists(player1_army_file):
            raise FileNotFoundError(f"Player 1 army file not found: {player1_army_file}")
        if not os.path.exists(player2_army_file):
            raise FileNotFoundError(f"Player 2 army file not found: {player2_army_file}")
        
        # Load armies for both players
        from ..classes.army import parse_army_list
        from ..waha_helper import WahaHelper

        waha_helper = WahaHelper()
        
        if len(self.players) >= 2:
            # Load army for Player 1
            player1_army = parse_army_list(player1_army_file, waha_helper)
            self.players[0].set_army(player1_army)
            
            # Load army for Player 2  
            player2_army = parse_army_list(player2_army_file, waha_helper)
            self.players[1].set_army(player2_army)
            
            player1_units = len(self.players[0].get_army().units)
            player2_units = len(self.players[1].get_army().units)
            print(f"✅ {self.players[0].name}: {player1_units} units loaded from {player1_army_file}")
            print(f"✅ {self.players[1].name}: {player2_units} units loaded from {player2_army_file}")
        else:
            print("⚠️ Not enough players loaded")
    
    def execute_select_mission_objectives_phase(self) -> None:
        """Phase 2: Select Mission Objectives - Choose mission and objectives."""
        print("📋 SELECT MISSION OBJECTIVES: Setting up mission...")
        
        # Set up available commands for high-level strategy
        self.commands = ["attack", "defend", "move"]
        print(f"✅ Commands configured: {self.commands}")
        
        # Store selected mission info for use in CREATE_BATTLEFIELD phase
        # This will be set by the UI when the mission selection dialog is used
        if not hasattr(self, 'selected_mission_info'):
            # Use a valid default combination - M: Purge the Foe / Crucible of Battle / Layout 1
            self.selected_mission_info = {
                "combination_id": "M",
                "primary": "Purge the Foe",  # Valid with Crucible of Battle
                "deployment": "Crucible of Battle",   
                "layout": 1  # Valid layout for this combination
            }
            print(f"✅ Using default mission: {self.selected_mission_info}")
        else:
            print(f"✅ Mission selected: {self.selected_mission_info}")
        
        # Mission objectives will be placed during CREATE_BATTLEFIELD phase
        print("✅ Mission framework configured")
    
    def execute_create_battlefield_phase(self, mission_name: str = None) -> None:
        """Phase 3: Create Battlefield - Set up map, terrain, deployment zones, and objectives."""
        print("📋 CREATE BATTLEFIELD: Setting up battlefield...")
        
        # Use selected mission info if available, otherwise use provided mission_name or default
        if hasattr(self, 'selected_mission_info'):
            deployment_mission = self.selected_mission_info["deployment"]
            terrain_layout = self.selected_mission_info["layout"]
            primary_mission = self.selected_mission_info["primary"]
        else:
            deployment_mission = mission_name or "Crucible of Battle"
            terrain_layout = 1
            primary_mission = "Take and Hold"
        
        # 1. Create the Map (already done in __init__)
        battlefield_width, battlefield_height = self.get_battlefield_size()
        print(f"✅ Map created: {battlefield_width}\" x {battlefield_height}\"")
        
        # 2. Terrain features based on selected terrain layout
        try:
            from .terrain_layouts import instantiate_layout
            terrain_features = instantiate_layout(terrain_layout)
            if terrain_features:
                self.map.add_terrain_features(terrain_features)
                print(f"✅ Terrain layout {terrain_layout} placed: {len(terrain_features)} features")
                # Debug: print RUINS footprints for verification
                try:
                    from .map import TerrainType
                    for idx, tf in enumerate(terrain_features):
                        if getattr(tf, 'terrain_type', None) == TerrainType.RUINS:
                            coords = list(tf.footprint.exterior.coords)[:-1]
                            pairs = [(round(float(x), 2), round(float(y), 2)) for (x, y) in coords]
                            print(f"   • RUINS #{idx+1} footprint: {pairs}")
                            # Floors detail (ground=0, first=1, second=2)
                            floors = getattr(tf, 'floors', []) or []
                            for fl in floors:
                                poly = fl.get('polygon')
                                elev = float(fl.get('elevation', 0.0))
                                try:
                                    from ..utility.constants import RUINS_FLOOR_HEIGHT
                                    level = int(round(elev / float(RUINS_FLOOR_HEIGHT)))
                                except Exception:
                                    level = 0
                                if hasattr(poly, 'exterior'):
                                    fcoords = list(poly.exterior.coords)[:-1]
                                    fpairs = [(round(float(x), 2), round(float(y), 2)) for (x, y) in fcoords]
                                    print(f"      - Floor L{level} (elev {elev:.1f}\"): {fpairs}")
                except Exception:
                    pass
            else:
                print(f"ℹ️ Terrain layout {terrain_layout} has no registered features")
        except Exception as e:
            print(f"⚠️ Failed to instantiate terrain layout {terrain_layout}: {e}")
        
        # 3. Set up mission-based deployment zones and objectives
        from .deployment import DeploymentManager
        deployment_manager = DeploymentManager(self, deployment_mission)
        
        # Set up deployment zones for the mission
        mission_zones = deployment_manager.create_deployment_zones()
        
        # Convert to the format expected by the game for visualization
        self.deployment_zones = {}
        for zone in mission_zones:
            if zone['zone_type'] == 'defender':
                # Assign to first player as defender (will be properly assigned later)
                self.deployment_zones[self.players[0].name] = zone
            elif zone['zone_type'] == 'attacker':
                # Assign to second player as attacker
                self.deployment_zones[self.players[1].name] = zone
        
        print(f"✅ Mission deployment zones created: {deployment_mission}")
        
        # 4. Set up mission objectives
        deployment_manager.setup_mission_objectives()
        print(f"✅ Mission objectives placed: {len(self.objectives)} objectives")
        print(f"✅ Primary Mission: {primary_mission}")
    
    def execute_determine_attacker_defender_phase(self) -> None:
        """Phase 4: Determine Attacker and Defender - Roll off to determine roles."""
        print("📋 DETERMINE ATTACKER AND DEFENDER: Rolling off...")
        
        import random
        from ..utility.dice import get_roll
        
        player1_roll = get_roll("1D6")
        player2_roll = get_roll("1D6")
        try:
            from ..utility.event_bus import append_dice
            append_dice(self.players[0].name, f"First turn roll: {player1_roll}")
            append_dice(self.players[1].name, f"First turn roll: {player2_roll}")
        except Exception:
            pass
        
        print(f"🎲 {self.players[0].name} rolled: {player1_roll}")
        print(f"🎲 {self.players[1].name} rolled: {player2_roll}")
        
        if player1_roll > player2_roll:
            self.attacker_index = 0
            self.defender_index = 1
            print(f"⚔️ {self.players[0].name} is the Attacker")
            print(f"🛡️ {self.players[1].name} is the Defender")
        elif player2_roll > player1_roll:
            self.attacker_index = 1
            self.defender_index = 0
            print(f"⚔️ {self.players[1].name} is the Attacker")
            print(f"🛡️ {self.players[0].name} is the Defender")
        else:
            # Tie - re-roll
            print("🎲 Tie! Re-rolling...")
            return self.execute_determine_attacker_defender_phase()
        
        # Set deployment turn to defender (defender deploys first)
        self.deployment_turn_index = self.defender_index
    
    def execute_declare_battle_formations_phase(self) -> None:
        """Phase 5: Declare Battle Formations - Attach leaders, declare reserves, etc."""
        print("📋 DECLARE BATTLE FORMATIONS: Configuring formations...")
        # For now, this is empty - battle formations will be implemented later
        print("✅ Battle formations declared")
    
    def execute_deploy_armies_phase(self, manual_phases: bool = False, decision_makers: dict = None) -> None:
        """Phase 6: Deploy Armies - Execute the deployment phase."""
        print("📋 DEPLOY ARMIES: Starting deployment sequence...")
        
        # Check if we have human players that need UI-based deployment
        has_human_players = any(player.type.name == 'HUMAN' for player in self.players)
        
        if has_human_players and manual_phases:
            # For human players in manual mode, set up deployment state but don't auto-deploy
            # The UI will handle the actual deployment decisions
            print("👤 Human deployment mode - use UI to deploy units")
            
            # Set up deployment zones if not already done
            if not hasattr(self, 'deployment_zones') or not self.deployment_zones:
                # Always use mission polygon deployment zones (no rectangular legacy zones).
                try:
                    mission_name = None
                    try:
                        mission_name = (getattr(self, "selected_mission_info", None) or {}).get("deployment")
                    except Exception:
                        mission_name = None
                    mission_name = mission_name or "Crucible of Battle"

                    from .deployment import DeploymentManager
                    deployment_manager = DeploymentManager(self, mission_name=mission_name)
                    zones = deployment_manager.create_deployment_zones()
                    defender_zone = next(z for z in zones if z.get("zone_type") == "defender")
                    attacker_zone = next(z for z in zones if z.get("zone_type") == "attacker")

                    defender_idx = getattr(self, "defender_index", None)
                    attacker_idx = getattr(self, "attacker_index", None)
                    if defender_idx is None or attacker_idx is None:
                        defender_idx, attacker_idx = 0, 1

                    self.deployment_zones = {
                        self.players[defender_idx].name: defender_zone,
                        self.players[attacker_idx].name: attacker_zone,
                    }
                except Exception as e:
                    raise RuntimeError(f"Failed to initialize mission deployment zones: {e}")
            
            # Initialize deployment tracking
            if not hasattr(self, 'deployment_turn_index'):
                self.deployment_turn_index = getattr(self, 'defender_index', 0)
            
            # Mark that we're in deployment phase
            self.waiting_for_deployment_input = False
            print("✅ Deployment phase initialized - deploy units through UI")
        
        elif decision_makers:
            # Use the proper deployment manager with decision makers for AI vs AI
            from .deployment import DeploymentManager
            deployment_manager = DeploymentManager(self)
            deployment_results = deployment_manager.execute_deployment_sequence(decision_makers)
            
            # Store deployment results for reference
            self.deployment_results = deployment_results
            print("✅ Army deployment complete")
        else:
            # Use the existing complete_deployment_phase method for fallback
            self.complete_deployment_phase(manual_phases=manual_phases)
            
            # Only print completion message if not waiting for manual input
            if not getattr(self, 'waiting_for_deployment_input', False):
                print("✅ Army deployment complete")

    def execute_redeploy_units_phase(self) -> None:
        """Phase: Redeploy Units - Alternate resolving redeploy rules, Attacker first.

        Rules:
        - Some rules allow redeploying certain units after both armies are deployed.
        - Players alternate resolving such rules, starting with the Attacker.
        - Redeploy allows selecting a new valid deployment location for eligible units.
        """
        print("📋 REDEPLOY UNITS: Resolving redeploy abilities...")
        if self.attacker_index is None or self.defender_index is None:
            print("ℹ️ Attacker/Defender not set; skipping Redeploy Units phase")
            return

        players_in_order = [self.players[self.attacker_index], self.players[self.defender_index]]

        # Collect eligible units per convention: unit.has_redeploy() -> (has, count, can_place_in_reserves)
        redeploy_pool = {p: [] for p in players_in_order}
        for p in players_in_order:
            army = p.get_army()
            if not army:
                continue
            for u in army.units:
                try:
                    has_redeploy, count, can_place_in_reserves = u.has_redeploy()
                except Exception:
                    has_redeploy, count, can_place_in_reserves = (False, 0, False)
                if has_redeploy and u.deployed and u.reserve_status == 'deployed':
                    redeploy_pool[p].append((u, count, can_place_in_reserves))

        if not any(redeploy_pool.values()):
            print("✅ No units with Redeploy; skipping")
            return

        # Alternate between players until all redeploy options exhausted
        turn_idx = 0
        while any(redeploy_pool[p] for p in players_in_order):
            current_player = players_in_order[turn_idx % 2]
            options = redeploy_pool[current_player]
            if not options:
                turn_idx += 1
                continue
            # Pick the first available unit; in the future, UI/AI should decide
            unit, remaining, can_place_in_reserves = options.pop(0)
            print(f"🔄 {current_player.name} redeploys {unit.name}")
            # If the redeploy count was D3, print the stored roll result if available
            roll_info = getattr(unit, '_redeploy_d_roll', None)
            if roll_info:
                print(f"🎲 Redeploy count ({roll_info['expr']}) for {unit.name}: {roll_info['total']} (rolled {roll_info['rolls']})")
            # Simple random valid redeploy within current DZ for now
            # A proper UI should present valid positions; here we keep rules isolated
            pos = self._find_valid_redeploy_position(current_player, unit)
            if pos:
                # Use unit's deployment placement to set model positions
                try:
                    from shapely.geometry import Polygon as _Poly  # noqa: F401
                except Exception:
                    pass
                positions = unit.calculate_model_positions(
                    pos[0], pos[1], self.map,
                    boundary_repulsors=self.map.get_battlefield_edge_repulsors()
                )
                if positions:
                    print(f"✅ {unit.name} redeployed to ({pos[0]:.1f}, {pos[1]:.1f})")
                else:
                    print(f"⚠️ Redeploy failed to find valid formation for {unit.name}")
            else:
                print(f"⚠️ No valid redeploy position found for {unit.name}")
            # If multiple redeploy counts allowed, requeue
            if remaining > 1:
                options.insert(0, (unit, remaining - 1, can_place_in_reserves))
            turn_idx += 1

        print("✅ Redeploy phase complete")

    def _find_valid_redeploy_position(self, player: 'Player', unit: 'Unit') -> tuple | None:
        # Naive sampling within player's DZ; real impl should mirror deployment validation
        import random
        dz = self.deployment_zones.get(player.name, {})
        zone = dz.get('zone')
        for _ in range(200):
            x = random.uniform(0, self.battlefield.width)
            y = random.uniform(0, self.battlefield.height)
            if zone and hasattr(zone, 'contains_point') and not zone.contains_point(x, y):
                continue
            z = self.map.get_height_at_point(x, y)
            # Reuse arrival placement validation
            if self.can_place_unit_arriving_from_reserves(unit, (x, y, z)):
                return (x, y, z)
        return None
    
    def execute_determine_first_turn_order_phase(self) -> None:
        """Phase 7: Determine First Turn Order - Attacker rolls to see who goes first."""
        print("📋 DETERMINE FIRST TURN ORDER: Rolling for first turn (roll-off)...")

        from ..utility.dice import get_roll

        p1 = self.players[0]
        p2 = self.players[1]

        while True:
            roll1 = get_roll("1D6")
            roll2 = get_roll("1D6")
            try:
                from ..utility.event_bus import append_dice
                append_dice(p1.name, f"First turn roll-off: {roll1}")
                append_dice(p2.name, f"First turn roll-off: {roll2}")
            except Exception:
                pass
            print(f"🎲 {p1.name} rolled: {roll1}")
            print(f"🎲 {p2.name} rolled: {roll2}")
            if roll1 == roll2:
                print("🔁 Tie on roll-off - re-rolling...")
                continue
            if roll1 > roll2:
                self.first_turn_player_index = 0
                print(f"✅ {p1.name} wins the roll-off and takes the first turn")
            else:
                self.first_turn_player_index = 1
                print(f"✅ {p2.name} wins the roll-off and takes the first turn")
            break

        # Clear deployment actions since deployment phase is now complete
        self.clear_deployment_actions()
    
    def execute_resolve_prebattle_rules_phase(self) -> None:
        """Phase 8: Resolve Pre-battle Rules - Resolve any pre-battle rules, abilities, or stratagems."""
        print("📋 RESOLVE PREBATTLE RULES: Resolving pre-battle rules...")
        
        # Handle Scout moves for all players
        self._handle_scout_moves()

        # TODO - other pre-battle rules (e.g., Detachment stuff like WE dice rolls, etc.)
        
        print("✅ Pre-battle rules resolved")
    
    def _handle_scout_moves(self) -> None:
        """Handle scout moves for all players during pre-battle rules phase."""
        print("🔍 Processing Scout moves...")
        
        # Get all units with Scout ability from both players
        scout_units = []
        for player in self.players:
            if player.get_army():
                for unit in player.get_army().units:
                    has_scout, scout_distance = unit.has_scout()
                    if has_scout and unit.deployed and unit.reserve_status == 'deployed':
                        scout_units.append((player, unit, scout_distance))
        
        if not scout_units:
            print("✅ No units with Scout ability found")
            return
        
        print(f"🔍 Found {len(scout_units)} units with Scout ability")
        
        # Sort units by player (first turn player goes first)
        # During setup phase, use first_turn_player_index instead of current_player_index
        if self.first_turn_player_index is not None:
            first_turn_player = self.players[self.first_turn_player_index]
        else:
            # Fallback to attacker if first turn not determined yet
            first_turn_player = self.get_attacker() if self.attacker_index is not None else self.players[0]
        
        scout_units_by_player = {}
        
        for player, unit, scout_distance in scout_units:
            if player not in scout_units_by_player:
                scout_units_by_player[player] = []
            scout_units_by_player[player].append((unit, scout_distance))
        
        # Process scout moves in turn order (first turn player first)
        players_in_order = [first_turn_player]
        for player in self.players:
            if player != first_turn_player:
                players_in_order.append(player)
        
        # Check if we have human players that need UI-based scout moves
        has_human_players = any(player.type.name == 'HUMAN' for player in self.players)
        
        if has_human_players:
            # For human players, let the UI handle scout moves
            # The PreBattlePhaseHandler will manage the scout move sequence
            print("👤 Human scout moves will be handled by UI")
            print("✅ Scout phase initialized - use UI to make scout moves")
        else:
            # For AI-only games, auto-skip scout moves for now
            # In the future, this could integrate with AI decision making
            for player in players_in_order:
                if player in scout_units_by_player:
                    print(f"🔍 {player.name}'s Scout moves:")
                    for unit, scout_distance in scout_units_by_player[player]:
                        print(f"  - {unit.name} (Scout {scout_distance}\")")
                        print(f"    Skipping scout move (auto-skip for AI)")
                        unit.scout_move_made = True  # Mark as skipped
            
            print("✅ Scout moves processed (auto-skipped for AI)")
    
    def execute_current_setup_phase(self, **kwargs) -> None:
        """Execute the current setup phase with any necessary parameters."""
        if self.setup_phase == SetupPhase.MUSTER_ARMIES:
            self.execute_muster_armies_phase(
                kwargs.get('player1_army_file'), 
                kwargs.get('player2_army_file')
            )
        elif self.setup_phase == SetupPhase.SELECT_MISSION_OBJECTIVES:
            self.execute_select_mission_objectives_phase()
        elif self.setup_phase == SetupPhase.CREATE_BATTLEFIELD:
            self.execute_create_battlefield_phase()
        elif self.setup_phase == SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER:
            self.execute_determine_attacker_defender_phase()
        elif self.setup_phase == SetupPhase.DECLARE_BATTLE_FORMATIONS:
            self.execute_declare_battle_formations_phase()
        elif self.setup_phase == SetupPhase.DEPLOY_ARMIES:
            self.execute_deploy_armies_phase(
                manual_phases=kwargs.get('manual_phases', False),
                decision_makers=kwargs.get('decision_makers')
            )
        elif self.setup_phase == SetupPhase.REDEPLOY_UNITS:
            self.execute_redeploy_units_phase()
        elif self.setup_phase == SetupPhase.DETERMINE_FIRST_TURN_ORDER:
            self.execute_determine_first_turn_order_phase()
        elif self.setup_phase == SetupPhase.RESOLVE_PREBATTLE_RULES:
            self.execute_resolve_prebattle_rules_phase()
