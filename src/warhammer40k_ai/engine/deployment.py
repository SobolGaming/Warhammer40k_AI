from typing import List, Tuple, Dict, Any, Optional, TYPE_CHECKING
import hashlib
import json
import logging
from abc import ABC, abstractmethod

from .game import Game
from .decision_kinds import DECISION_MOVE_UNIT
from .decisions import DecisionOption, DecisionRequest
from .decision_requests import (
    build_deployment_zone_request,
    build_select_next_deploy_unit_request,
    canonical_deployment_zone_key,
)
from .prospective_positions import calculate_prospective_model_positions
from ..roster.player import Player
from ..utility.calcs import get_dist
from ..utility.decision_utils import resolve_decision_command
from ..utility.entity_ids import get_entity_id, maybe_entity_id
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

    def choose_deployment_zone_option(
        self,
        request: DecisionRequest,
        available_zones: List[dict],
    ) -> Optional[str]:
        del request, available_zones
        return None
    
    @abstractmethod
    def declare_reserves(self, player: Player) -> dict:
        """Decide which units go into reserves, strategic reserves, or deploy normally."""
        pass

    def choose_reserves_allocation_option(
        self,
        request: DecisionRequest,
        player: Player,
        proposed_decisions: Dict[str, str],
    ) -> Optional[str]:
        del request, player, proposed_decisions
        return None
    
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

    def choose_next_deploy_unit_option(
        self,
        request: DecisionRequest,
        deployable_units: List['Unit'],
        deployment_zone: dict,
        already_deployed: List['Unit'],
    ) -> Optional[str]:
        del request, deployable_units, deployment_zone, already_deployed
        return None

    def build_deployment_move_candidates(
        self,
        unit: 'Unit',
        deployment_zone: dict,
        already_deployed: List['Unit'],
        *,
        max_candidates: int = 8,
    ) -> List[dict]:
        del unit, deployment_zone, already_deployed, max_candidates
        return []

    def choose_deployment_move_option(
        self,
        request: DecisionRequest,
        unit: 'Unit',
        deployment_zone: dict,
        already_deployed: List['Unit'],
    ) -> Optional[str]:
        del request, unit, deployment_zone, already_deployed
        return None

    def deployment_candidate_limit(
        self,
        *,
        unit: Optional['Unit'] = None,
        deployment_zone: Optional[dict] = None,
        already_deployed: Optional[List['Unit']] = None,
    ) -> int:
        del unit, deployment_zone, already_deployed
        return 8

    def build_deployment_intent(
        self,
        *,
        decision_kind: str,
        player: Optional[Player] = None,
        deployment_zone: Optional[dict] = None,
        unit: Optional['Unit'] = None,
        deployable_units: Optional[List['Unit']] = None,
        already_deployed: Optional[List['Unit']] = None,
    ) -> dict:
        return {}

    def build_deployment_decision_context(
        self,
        *,
        decision_kind: str,
        player: Optional[Player] = None,
        deployment_zone: Optional[dict] = None,
        unit: Optional['Unit'] = None,
        deployable_units: Optional[List['Unit']] = None,
        already_deployed: Optional[List['Unit']] = None,
    ) -> dict:
        return {}


class DeploymentManager:
    """Manages the official Warhammer 40k 10th Edition deployment sequence."""
    
    def __init__(self, game: Game, mission_name: str = "Crucible of Battle"):
        self.game = game
        self.mission = MissionRegistry.get_mission(mission_name)
        self.attacker = None
        self.defender = None
        self.deployment_zones = []
        logger.info(f"DeploymentManager initialized with mission: {self.mission.name}")

    def _current_setup_roles(self) -> Tuple[Player, Player]:
        attacker_idx = getattr(self.game, "attacker_index", None)
        defender_idx = getattr(self.game, "defender_index", None)
        if attacker_idx is None or defender_idx is None:
            raise RuntimeError("Attacker and defender must be determined before DEPLOY_ARMIES.")
        players = list(getattr(self.game, "players", []) or [])
        attacker_index = int(attacker_idx)
        defender_index = int(defender_idx)
        if attacker_index == defender_index:
            raise RuntimeError("Attacker and defender indices must refer to different players.")
        if not (0 <= attacker_index < len(players)):
            raise RuntimeError("Attacker index is out of range for DEPLOY_ARMIES.")
        if not (0 <= defender_index < len(players)):
            raise RuntimeError("Defender index is out of range for DEPLOY_ARMIES.")
        self.attacker = players[attacker_index]
        self.defender = players[defender_index]
        return self.attacker, self.defender

    def _current_reserves_decisions(self, player: Player) -> Dict[str, str]:
        army = player.get_army()
        if army is None:
            return {}
        root_fn = getattr(army, "_reserve_group_roots", None)
        if callable(root_fn):
            roots = list(root_fn() or [])
        else:
            roots = [
                unit
                for unit in list(getattr(army, "units", []) or [])
                if not bool(getattr(unit, "is_attached_leader", False))
                and not bool(getattr(unit, "is_joined_support", False))
            ]
        decisions: Dict[str, str] = {}
        for root in list(roots or []):
            unit_id = str(maybe_entity_id(root) or "")
            if not unit_id:
                continue
            reserve_status = str(getattr(root, "reserve_status", "deployed") or "deployed").strip().lower()
            if reserve_status == "reserves":
                decisions[unit_id] = "reserves"
            elif reserve_status == "strategic_reserves":
                decisions[unit_id] = "strategic_reserves"
            else:
                decisions[unit_id] = "deploy"
        return decisions
        
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

        # DEPLOY_ARMIES reuses the setup state established in earlier setup phases.
        self.attacker, self.defender = self._current_setup_roles()
        deployment_results['attacker'] = self.attacker.id
        deployment_results['defender'] = self.defender.id
        logger.info(f"Using setup roles - attacker: {self.attacker.name}, defender: {self.defender.name}")

        # Step 1: Use pre-configured deployment zones (ensures consistency)
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

        # Step 2: Reuse the reserve declarations already resolved in DECLARE_BATTLE_FORMATIONS.
        deployment_results['reserves'][self.defender.id] = self._current_reserves_decisions(self.defender)
        deployment_results['reserves'][self.attacker.id] = self._current_reserves_decisions(self.attacker)

        logger.info(
            f"Using existing reserves declarations - {self.defender.name}: "
            f"{sum(1 for d in deployment_results['reserves'][self.defender.id].values() if d != 'deploy')} units, "
            f"{self.attacker.name}: "
            f"{sum(1 for d in deployment_results['reserves'][self.attacker.id].values() if d != 'deploy')} units"
        )

        # Step 3: Alternating Deployment (Defender first)
        self.execute_alternating_deployment(deployment_results, decision_makers)
        logger.info("Deployment sequence complete!")
        
        self.set_reserves_status(deployment_results)
        
        return deployment_results
    
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

    def _resolve_deployment_zone_decision(
        self,
        player: Player,
        decision_maker: DeploymentDecisionMaker,
        available_zones: List[dict],
    ) -> dict:
        if not available_zones:
            raise RuntimeError("Deployment zone choice requires at least one available zone.")
        deployment_intent = decision_maker.build_deployment_intent(
            decision_kind="zone_choice",
            player=player,
            deployable_units=[],
            already_deployed=[],
        )
        extra_context = decision_maker.build_deployment_decision_context(
            decision_kind="zone_choice",
            player=player,
            deployable_units=[],
            already_deployed=[],
        )
        extra_context = dict(extra_context or {})
        extra_context["decision_owner"] = "deployment_manager"
        request = build_deployment_zone_request(
            self.game,
            player,
            available_zones,
            deployment_intent=deployment_intent,
            extra_context=extra_context,
            queue_requests=True,
        )
        selected_option: Optional[DecisionOption] = None
        if request is None:
            chosen_zone = decision_maker.choose_deployment_zone(list(available_zones))
            if not isinstance(chosen_zone, dict):
                raise RuntimeError(
                    f"Deployment zone choice for {player.name} must return a zone dict."
                )
            for zone in available_zones:
                if zone == chosen_zone:
                    return zone
            raise RuntimeError(f"Deployment zone choice for {player.name} did not match any available zone.")
        option_id = str(
            decision_maker.choose_deployment_zone_option(
                request,
                list(available_zones),
            )
            or ""
        )
        if option_id:
            for option in list(getattr(request, "options", []) or []):
                if str(getattr(option, "option_id", "") or "") == option_id:
                    selected_option = option
                    break
            if selected_option is None:
                raise RuntimeError(
                    f"Deployment zone option selection for {player.name} returned unknown option id: {option_id}"
                )
        if selected_option is None:
            chosen_zone = decision_maker.choose_deployment_zone(list(available_zones))
            if not isinstance(chosen_zone, dict):
                raise RuntimeError(
                    f"Deployment zone choice for {player.name} must return a zone dict."
                )
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
            already_deployed_units=already_deployed,
            deployment_intent=decision_maker.build_deployment_intent(
                decision_kind="next_unit",
                player=player,
                deployment_zone=deployment_zone,
                deployable_units=deployable_units,
                already_deployed=already_deployed,
            ),
            extra_context=decision_maker.build_deployment_decision_context(
                decision_kind="next_unit",
                player=player,
                deployment_zone=deployment_zone,
                deployable_units=deployable_units,
                already_deployed=already_deployed,
            )
            | {"decision_owner": "deployment_manager"},
            queue_requests=True,
        )
        selected_option = None
        chosen_unit_id = ""
        if request is not None:
            option_id = str(
                decision_maker.choose_next_deploy_unit_option(
                    request,
                    list(deployable_units),
                    deployment_zone,
                    list(already_deployed),
                )
                or ""
            )
            if option_id:
                for option in list(getattr(request, "options", []) or []):
                    if str(getattr(option, "option_id", "") or "") == option_id:
                        selected_option = option
                        break
                if selected_option is None:
                    raise RuntimeError(
                        f"Deployment unit option selection for {player.name} returned unknown option id: {option_id}"
                    )

        if selected_option is None:
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
                for option in list(getattr(request, "options", []) or []):
                    payload = dict(getattr(option, "payload", {}) or {})
                    if str(payload.get("unit_id", "") or "") == chosen_unit_id:
                        selected_option = option
                        break
                if selected_option is None:
                    raise RuntimeError(
                        f"Deployment unit selection for {player.name} returned unknown unit id: {chosen_unit_id}"
                    )
        elif request is not None:
            payload = dict(getattr(selected_option, "payload", {}) or {})
            chosen_unit_id = str(payload.get("unit_id", "") or "")
            if not chosen_unit_id:
                raise RuntimeError(
                    f"Deployment unit option selection for {player.name} did not provide unit_id."
                )

        if request is not None and selected_option is not None:
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

    def _build_deployment_move_candidates(
        self,
        unit: 'Unit',
        *,
        decision_maker: DeploymentDecisionMaker,
        deployment_zone: dict,
        already_deployed: List['Unit'],
        max_candidates: int = 8,
    ) -> List[dict]:
        candidate_limit = max(1, int(max_candidates))
        builder = getattr(decision_maker, "build_deployment_move_candidates", None)
        if callable(builder):
            raw_candidates = list(
                builder(
                    unit,
                    deployment_zone,
                    list(already_deployed or []),
                    max_candidates=candidate_limit,
                )
                or []
            )
            normalized: List[dict] = []
            seen: set[str] = set()
            for entry in list(raw_candidates or []):
                normalized_candidate = self._normalize_deployment_move_candidate(
                    unit,
                    entry,
                    decision_maker=decision_maker,
                )
                if normalized_candidate is None:
                    continue
                signature = self._deployment_placement_candidate_id(
                    str(get_entity_id(unit) or ""),
                    (float(normalized_candidate["anchor"][0]), float(normalized_candidate["anchor"][1])),
                    list(normalized_candidate["model_positions"] or []),
                    candidate_index=0,
                )
                if signature in seen:
                    continue
                seen.add(signature)
                normalized.append(normalized_candidate)
                if len(normalized) >= candidate_limit:
                    break
            if normalized:
                return normalized
        return []

    def _normalize_deployment_move_candidate(
        self,
        unit: 'Unit',
        candidate: object,
        *,
        decision_maker: Optional[DeploymentDecisionMaker] = None,
    ) -> Optional[dict]:
        if not isinstance(candidate, dict):
            return None
        raw_anchor = candidate.get("anchor", candidate.get("deployment_anchor"))
        if not isinstance(raw_anchor, (list, tuple)) or len(raw_anchor) < 2:
            return None
        try:
            anchor_x = float(raw_anchor[0])
            anchor_y = float(raw_anchor[1])
        except (TypeError, ValueError):
            return None
        raw_positions = list(candidate.get("model_positions", []) or [])
        model_positions: List[dict] = []
        for entry in raw_positions:
            if isinstance(entry, dict):
                model_positions.append(dict(entry or {}))
        if not model_positions:
            if decision_maker is None:
                return None
            try:
                model_positions = self._build_deployment_model_positions(
                    unit,
                    (float(anchor_x), float(anchor_y)),
                    decision_maker=decision_maker,
                )
            except RuntimeError:
                return None
        if not model_positions:
            return None
        source = str(candidate.get("source", "") or "").strip().lower()
        if not source:
            source = "decision_maker"
        return {
            "anchor": [float(anchor_x), float(anchor_y)],
            "model_positions": [dict(entry or {}) for entry in list(model_positions or [])],
            "source": source,
        }

    @staticmethod
    def _deployment_move_option_from_id(request: DecisionRequest, option_id: str) -> Optional[DecisionOption]:
        if not option_id:
            return None
        for option in list(getattr(request, "options", []) or []):
            if str(getattr(option, "option_id", "") or "") == option_id:
                return option
        return None

    def _select_deployment_move_option(
        self,
        *,
        request: DecisionRequest,
        decision_maker: DeploymentDecisionMaker,
        unit: 'Unit',
        deployment_zone: dict,
        already_deployed: List['Unit'],
    ) -> DecisionOption:
        option_id = str(
            decision_maker.choose_deployment_move_option(
                request,
                unit,
                deployment_zone,
                list(already_deployed or []),
            )
            or ""
        )
        selected_option = self._deployment_move_option_from_id(request, option_id)
        if option_id and selected_option is None:
            raise RuntimeError(
                f"Deployment placement option selection returned unknown option id for "
                f"{getattr(unit, 'name', 'Unit')}: {option_id}"
            )
        if selected_option is not None:
            return selected_option
        if getattr(request, "options", None):
            return request.options[0]
        raise RuntimeError(
            f"Deployment placement request for {getattr(unit, 'name', 'Unit')} has no selectable options."
        )

    @staticmethod
    def _deployment_placement_candidate_id(
        unit_id: str,
        anchor: Tuple[float, float],
        model_positions: List[dict],
        *,
        candidate_index: int,
    ) -> str:
        canonical_positions: List[dict] = []
        for entry in list(model_positions or []):
            model_id = str(dict(entry or {}).get("model_id", "") or "")
            pos = list(dict(entry or {}).get("position", []) or [])
            facing = dict(entry or {}).get("facing", 0.0)
            if not model_id or len(pos) < 2:
                continue
            try:
                px = float(pos[0])
                py = float(pos[1])
                pz = float(pos[2]) if len(pos) >= 3 else 0.0
                pf = float(facing)
            except (TypeError, ValueError):
                continue
            canonical_positions.append(
                {
                    "model_id": model_id,
                    "position": [round(px, 4), round(py, 4), round(pz, 4)],
                    "facing": round(pf, 4),
                }
            )
        canonical_positions.sort(key=lambda item: str(item.get("model_id", "") or ""))
        canonical_payload = {
            "unit_id": str(unit_id or "unit"),
            "candidate_index": int(candidate_index),
            "anchor": [round(float(anchor[0]), 4), round(float(anchor[1]), 4)],
            "model_positions": canonical_positions,
        }
        digest = hashlib.sha256(
            json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()[:16]
        return f"{str(unit_id or 'unit')}:deploy:{int(candidate_index):02d}:{digest}"

    def _build_deployment_move_request(
        self,
        unit: 'Unit',
        *,
        placement_candidates: Optional[List[dict]] = None,
        deployment_anchor: Tuple[float, float] | None = None,
        deployment_model_positions: Optional[List[dict]] = None,
        deployment_zone: Optional[dict] = None,
        already_deployed: Optional[List['Unit']] = None,
        deployment_intent: Optional[dict] = None,
        extra_context: Optional[dict] = None,
    ) -> DecisionRequest:
        unit_id = get_entity_id(unit)
        player_id = None
        army = getattr(unit, "get_parent_army", None)
        if callable(army):
            army = army()
        else:
            army = getattr(unit, "parent_army", None)
        if army is not None:
            player = getattr(army, "player", None)
            player_id = getattr(player, "id", None) if player is not None else None

        normalized_candidates: List[dict] = []
        for candidate in list(placement_candidates or []):
            normalized = self._normalize_deployment_move_candidate(
                unit,
                candidate,
                decision_maker=None,
            )
            if normalized is not None:
                normalized_candidates.append(normalized)
        if not normalized_candidates and deployment_anchor is not None and deployment_model_positions:
            normalized_candidates = [
                {
                    "anchor": [float(deployment_anchor[0]), float(deployment_anchor[1])],
                    "model_positions": [dict(entry or {}) for entry in list(deployment_model_positions or [])],
                    "source": "legacy_single_anchor",
                }
            ]
        if not normalized_candidates:
            raise RuntimeError(f"Deployment move request for {getattr(unit, 'name', 'Unit')} has no candidates.")

        options: List[DecisionOption] = []
        candidate_summaries: List[dict] = []
        player_key = str(player_id or "")
        for idx, candidate in enumerate(list(normalized_candidates or [])):
            anchor = list(candidate.get("anchor", []) or [])
            model_positions = [dict(entry or {}) for entry in list(candidate.get("model_positions", []) or [])]
            if len(anchor) < 2 or not model_positions:
                continue
            anchor_x = float(anchor[0])
            anchor_y = float(anchor[1])
            candidate_id = str(
                candidate.get("candidate_id")
                or self._deployment_placement_candidate_id(
                    str(unit_id or ""),
                    (anchor_x, anchor_y),
                    model_positions,
                    candidate_index=idx,
                )
            )
            action_id = f"{DECISION_MOVE_UNIT}:{player_key}:{unit_id}:deployment:{candidate_id}"
            payload = {
                "unit_id": unit_id,
                "movement_type": "deploy",
                "action": "confirm",
                "placement_candidate_id": candidate_id,
                "placement_candidate_index": int(idx),
                "deployment_anchor": [anchor_x, anchor_y],
                "model_positions": model_positions,
                "action_id": action_id,
            }
            source = str(candidate.get("source", "") or "").strip().lower()
            if source:
                payload["candidate_source"] = source
            option = DecisionOption.create(
                f"Place at ({anchor_x:.1f}, {anchor_y:.1f})",
                payload=payload,
            )
            options.append(option)
            candidate_summaries.append(
                {
                    "placement_candidate_id": candidate_id,
                    "placement_candidate_index": int(idx),
                    "deployment_anchor": [anchor_x, anchor_y],
                    "candidate_source": source,
                }
            )
        if not options:
            raise RuntimeError(f"Deployment move request for {getattr(unit, 'name', 'Unit')} has no valid options.")

        allowed_model_ids = [get_entity_id(m) for m in list(getattr(unit, "models", []) or [])]
        context = {
            "unit_id": unit_id,
            "movement_type": "deploy",
            "placement_kind": "deployment",
            "allowed_model_ids": allowed_model_ids,
            "allow_skip": False,
            "max_distance": 0.0,
            "deployment_candidate_count": int(len(options)),
        }
        first_payload = dict(options[0].payload or {})
        first_anchor = list(first_payload.get("deployment_anchor", []) or [])
        first_positions = list(first_payload.get("model_positions", []) or [])
        if len(first_anchor) >= 2:
            context["deployment_anchor"] = [float(first_anchor[0]), float(first_anchor[1])]
        if first_positions:
            context["deployment_model_positions"] = [dict(entry or {}) for entry in list(first_positions or [])]
        if candidate_summaries:
            context["deployment_candidate_summaries"] = candidate_summaries
        if isinstance(deployment_zone, dict):
            zone_data = dict(deployment_zone or {})
            context["deployment_zone_key"] = canonical_deployment_zone_key(zone_data)
            context["deployment_zone_type"] = str(zone_data.get("zone_type", "") or "")
            zone_name = str(zone_data.get("name", "") or "")
            if zone_name:
                context["deployment_zone_name"] = zone_name
        if already_deployed is not None:
            deployed_ids: List[str] = []
            for deployed_unit in list(already_deployed or []):
                deployed_id = str(maybe_entity_id(deployed_unit) or "")
                if deployed_id:
                    deployed_ids.append(deployed_id)
            if deployed_ids:
                context["already_deployed_unit_ids"] = sorted(set(deployed_ids))
                context["already_deployed_count"] = int(len(set(deployed_ids)))
        context["deployment_intent"] = dict(
            deployment_intent
            or {
                "desired_affordances": [
                    "SAFE_STAGING",
                    "SCREEN_DEPTH",
                    "RESERVE_DENIAL",
                    "COUNTERCHARGE_POCKET",
                ],
                "weights": {
                    "score": 0.3,
                    "deny": 0.2,
                    "safety": 0.3,
                    "staging": 0.2,
                    "reserve_deny": 0.22,
                    "screen": 0.24,
                    "countercharge": 0.18,
                    "cover": 0.22,
                    "los": 0.12,
                    "aura": 0.12,
                },
            }
        )
        if isinstance(extra_context, dict):
            for key, value in dict(extra_context or {}).items():
                if key in context:
                    continue
                context[str(key)] = value
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
        model_positions = calculate_prospective_model_positions(
            unit,
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

    def _handle_unplaceable_deployment_unit(
        self,
        unit: 'Unit',
        *,
        player: Player,
        reason: str,
    ) -> None:
        unit_name = getattr(unit, "name", "Unit")
        logger.warning(
            "Skipping battlefield placement for %s (%s): %s.",
            unit_name,
            getattr(player, "name", "Player"),
            str(reason or "unknown reason"),
        )
        setattr(unit, "_deployment_skipped_no_position", True)

        player_army = player.get_army()
        destroy_fn = getattr(player_army, "_destroy_unit_models", None) if player_army is not None else None
        if callable(destroy_fn):
            destroy_fn(unit, game_map=getattr(self.game, "map", None))
        else:
            for model in list(getattr(unit, "models", []) or []):
                if hasattr(model, "is_alive"):
                    model.is_alive = False

        set_reserve_status = getattr(unit, "set_reserve_status", None)
        if callable(set_reserve_status):
            set_reserve_status("deployed")
        elif hasattr(unit, "reserve_status"):
            unit.reserve_status = "deployed"
        unit.deployed = True

        for leader in list(getattr(unit, "attached_leaders", []) or []):
            leader_set_reserve_status = getattr(leader, "set_reserve_status", None)
            if callable(leader_set_reserve_status):
                leader_set_reserve_status("deployed")
            elif hasattr(leader, "reserve_status"):
                leader.reserve_status = "deployed"
            leader.deployed = True
    
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
                candidate_limit = max(
                    1,
                    int(
                        getattr(current_decision_maker, "deployment_candidate_limit", lambda **_kwargs: 8)(
                            unit=unit,
                            deployment_zone=current_zone,
                            already_deployed=current_deployed,
                        )
                    ),
                )
                placement_candidates = self._build_deployment_move_candidates(
                    unit,
                    decision_maker=current_decision_maker,
                    deployment_zone=current_zone,
                    already_deployed=current_deployed,
                    max_candidates=candidate_limit,
                )
                if not placement_candidates:
                    self._handle_unplaceable_deployment_unit(
                        unit,
                        player=current_player,
                        reason="no placement candidates were generated",
                    )
                    continue
                first_anchor = list(dict(placement_candidates[0] or {}).get("anchor", []) or [])
                if len(first_anchor) < 2:
                    raise RuntimeError(
                        f"Deployment placement candidates for {getattr(unit, 'name', 'Unit')} are missing anchors."
                    )
                primary_position = (float(first_anchor[0]), float(first_anchor[1]))
                deployment_intent = current_decision_maker.build_deployment_intent(
                    decision_kind="placement",
                    player=current_player,
                    deployment_zone=current_zone,
                    unit=unit,
                    deployable_units=current_units,
                    already_deployed=current_deployed,
                )
                extra_context = current_decision_maker.build_deployment_decision_context(
                    decision_kind="placement",
                    player=current_player,
                    deployment_zone=current_zone,
                    unit=unit,
                    deployable_units=current_units,
                    already_deployed=current_deployed,
                )
                extra_context = dict(extra_context or {})
                extra_context["decision_owner"] = "deployment_manager"

                # Route deployment placement through DecisionRequest/Command API.
                request = self._build_deployment_move_request(
                    unit,
                    placement_candidates=placement_candidates,
                    deployment_zone=current_zone,
                    already_deployed=current_deployed,
                    deployment_intent=deployment_intent,
                    extra_context=extra_context,
                )
                self.game.request_decision(request)
                selected_option = self._select_deployment_move_option(
                    request=request,
                    decision_maker=current_decision_maker,
                    unit=unit,
                    deployment_zone=current_zone,
                    already_deployed=current_deployed,
                )
                selected_payload = dict(getattr(selected_option, "payload", {}) or {})
                selected_positions = [
                    dict(entry or {})
                    for entry in list(selected_payload.get("model_positions", []) or [])
                    if isinstance(entry, dict)
                ]
                if not selected_positions:
                    raise RuntimeError(
                        f"Deployment placement option for {getattr(unit, 'name', 'Unit')} is missing model_positions."
                    )
                selected_anchor_data = list(selected_payload.get("deployment_anchor", []) or [])
                if len(selected_anchor_data) >= 2:
                    selected_position = (float(selected_anchor_data[0]), float(selected_anchor_data[1]))
                else:
                    selected_position = primary_position
                queue = getattr(self.game, "decision_queue", None)
                pending = queue.get(request.decision_id) if queue is not None and hasattr(queue, "get") else request
                if pending is not None:
                    apply_result = resolve_decision_command(
                        self.game,
                        request,
                        selected_option.option_id,
                        result_payload={"model_positions": selected_positions},
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
                deployment_order.append((current_player.id, unit.id, selected_position))
                
                logger.info(
                    f"{current_player.name} deploys {unit.name} at "
                    f"({selected_position[0]:.1f}, {selected_position[1]:.1f})"
                )

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
