from typing import List, Optional, Tuple, Dict, Any
from ..units.unit import Unit
from ..units.model import Model
from ..utility.calcs import get_dist, convert_mm_to_inches, can_traverse_freely, _resolve_ruins_floor_level, get_pivot_cost
from ..utility.constants import RUINS_FLOOR_HEIGHT, RUINS_FLOOR_THICKNESS, RUINS_WALL_THICKNESS
from ..engine.combat_timing import (
    CombatEngagementState,
    engagement_state_for_models,
    geometry_profile_for_context,
)
from shapely.geometry import Polygon, Point, LineString, box
from shapely.errors import GEOSException
from shapely.ops import unary_union
from shapely.affinity import scale, translate

from typing import Union
from .map_geometry import battlefield_edge_repulsors, create_boundary_polygon as build_boundary_polygon
from .objective_sites import Objective, ObjectiveCategory, ObjectivePoint
from .terrain_presets import (
    create_preset_ruin_rect_10x5_variant1 as terrain_create_preset_ruin_rect_10x5_variant1,
    create_preset_ruin_rect_10x5_variant2 as terrain_create_preset_ruin_rect_10x5_variant2,
    create_preset_ruin_rect_10x5_variant3 as terrain_create_preset_ruin_rect_10x5_variant3,
    create_preset_ruin_rect_12x6_variant1 as terrain_create_preset_ruin_rect_12x6_variant1,
    create_preset_ruin_rect_12x6_variant2 as terrain_create_preset_ruin_rect_12x6_variant2,
    create_preset_ruin_rect_12x6_variant3 as terrain_create_preset_ruin_rect_12x6_variant3,
    create_preset_ruin_rect_12x6_variant4 as terrain_create_preset_ruin_rect_12x6_variant4,
    create_preset_ruin_rect_12x6_variant5 as terrain_create_preset_ruin_rect_12x6_variant5,
    create_preset_ruin_rect_12x6_variant6 as terrain_create_preset_ruin_rect_12x6_variant6,
    create_preset_ruin_rect_6x4_variant1 as terrain_create_preset_ruin_rect_6x4_variant1,
    create_preset_ruin_rect_6x4_variant2 as terrain_create_preset_ruin_rect_6x4_variant2,
)
from .terrain_cover import (
    _footprint_and_bounding_box_for_models as terrain_footprint_and_bounding_box_for_models,
    get_benefit_of_cover_for_ranged_attack as terrain_get_benefit_of_cover_for_ranged_attack,
    get_benefit_of_cover_from_fortifications as terrain_get_benefit_of_cover_from_fortifications,
    get_defence_line_bonus_for_ranged_attack as terrain_get_defence_line_bonus_for_ranged_attack,
    get_selfless_protector_bonus_for_ranged_attack as terrain_get_selfless_protector_bonus_for_ranged_attack,
)
from .terrain_elevation import (
    _candidate_base_for_pose as terrain_candidate_base_for_pose,
    _compound_part_surface_entry as terrain_compound_part_surface_entry,
    _iter_emplacement_platform_surface_entries as terrain_iter_emplacement_platform_surface_entries,
    _iter_root_models as terrain_iter_root_models,
    _shape_covers as terrain_shape_covers,
    _unit_has_keyword as terrain_unit_has_keyword,
    _unit_root as terrain_unit_root,
    get_emplacement_platform_placement as terrain_get_emplacement_platform_placement,
    get_emplacement_platform_surface_entries as terrain_get_emplacement_platform_surface_entries,
    get_height_at_point as terrain_get_height_at_point,
    get_plunging_fire_context as terrain_get_plunging_fire_context,
    get_surface_height_for_model as terrain_get_surface_height_for_model,
    get_surface_options_for_model as terrain_get_surface_options_for_model,
    validate_model_surface_placement as terrain_validate_model_surface_placement,
)
from .terrain_runtime import TerrainArea, TerrainFeature, TerrainType
from .terrain_ruins_placement import validate_ruins_placement as terrain_validate_ruins_placement
from .terrain_visibility import (
    can_model_see_model as terrain_can_model_see_model,
    get_visibility_context_for_models as terrain_get_visibility_context_for_models,
    is_fully_visible_due_to_terrain as terrain_is_fully_visible_due_to_terrain,
    sample_model_points_3d as terrain_sample_model_points_3d,
    segment_blocked_by_terrain_feature as terrain_segment_blocked_by_terrain_feature,
)
from ..utility.entity_ids import maybe_entity_id
import logging
logger = logging.getLogger(__name__)


class Map:
    def __init__(self, width: int, height: int):
        self.game = None
        self.width = width
        self.height = height
        self.boundary = self.create_boundary_polygon()
        self.terrain_features: List['TerrainFeature'] = []
        self.terrain_areas: List['TerrainArea'] = []
        self.preview_visibility_semantics_enabled = False
        self.preview_visibility_ruleset = ""
        self.objectives = []
        self.deployment_zones = {}
        self.units = []
        self.occupied_positions = set()
        # UI hook (optional): set by GameView to allow combat code to request modals (e.g., PRECISION allocation)
        self.precision_allocation_provider = None
        # UI hooks (optional): set by GameView to allow core damage code to request allocation choices
        # Signature: provider(target_unit, eligible_models, ctx_dict) -> chosen_model | None
        self.damage_allocation_provider = None
        # Signature: provider(attacker_unit_root, eligible_models, ctx_dict) -> chosen_model | None
        self.hazardous_allocation_provider = None
        # Signature: provider(target_unit_root, eligible_models, ctx_dict) -> chosen_model | None
        self.reanimation_allocation_provider = None
        # Signature: provider(player, leader_unit, bodyguard_unit, candidates, ability_name) -> chosen_model | None
        self.bodyguard_loss_provider = None
        # Assigned fallback/UI hook for reroll choices. Access through the property below so
        # engine and UI/headless flows settle the same DECISION_REROLL_ROLL request.
        self._roll_reroll_provider = None
        # Signature: provider(player, unit, roll_type, dice_count, die_faces, pool, needed) -> chosen_value | None
        self.miracle_dice_provider = None
        # Signature: provider(player, unit, roll_type, value, needed, tokens_remaining, ...) -> "use" | "skip" | "suppress"
        self.aspect_shrine_provider = None
        # Signature: provider(player, unit, roll_type, value, needed, options, ...) -> ability_key | "skip"
        self.leading_unmodified_six_provider = None
        # Signature: provider(player, model, ability_name, ability_key, ...) -> "use" | "skip"
        self.model_allocated_damage_zero_provider = None
        # Signature: provider(player, unit, target_model, ability_name, ability_key, fnp_value, condition, ...) -> "use" | "skip"
        self.unit_mortal_wound_fnp_provider = None
        # Signature: provider(player, attacker, target, weapon_profile, ability_name, choices) -> choice_key | None
        self.hit_modifier_choice_provider = None
        # Signature: provider(player, attacker, target, weapon_profile, ability_name, choices) -> choice_key | None
        self.skill_modifier_choice_provider = None
        # Signature: provider(player, unit, action_type, ability_name, choices) -> choice_key | None
        self.move_modifier_choice_provider = None
        # Signature: provider(player, unit, ability_name, choices) -> choice_key | None
        self.advance_modifier_choice_provider = None
        # Signature: provider(player, unit, target_unit_ids, ability_name, choices) -> choice_key | None
        self.charge_modifier_choice_provider = None

    @staticmethod
    def _reroll_prompt_title(roll_type: str) -> str:
        rt = str(roll_type or "").strip().lower()
        if rt == "advance":
            return "Advance Roll"
        if rt == "charge":
            return "Charge Roll"
        if rt in ("blood_surge", "blood surge"):
            return "Blood Surge Roll"
        if rt == "hit":
            return "Hit Roll"
        if rt == "wound":
            return "Wound Roll"
        return "Re-roll?"

    def _fallback_roll_reroll_choice(
        self,
        *,
        player=None,
        unit=None,
        roll_type: str = "",
        value=None,
        dice=None,
        allow_reroll: bool = True,
        **kwargs,
    ) -> bool:
        if not bool(allow_reroll):
            return False
        provider = getattr(self, "_roll_reroll_provider", None)
        if callable(provider):
            return bool(
                provider(
                    player=player,
                    unit=unit,
                    roll_type=roll_type,
                    value=value,
                    dice=dice,
                    allow_reroll=allow_reroll,
                    **kwargs,
                )
            )
        if "fallback_choice" in kwargs and kwargs.get("fallback_choice", None) is not None:
            return bool(kwargs.get("fallback_choice"))
        success = kwargs.get("success", None)
        if success is not None:
            return not bool(success)
        needed = kwargs.get("needed", None)
        try:
            if needed is not None and value is not None:
                return float(value) < float(needed)
        except (TypeError, ValueError):
            return False
        return False

    def _resolve_roll_reroll_provider(self, player=None, unit=None, roll_type: str = "", value=None, dice=None, **kwargs):
        allow_reroll = bool(kwargs.get("allow_reroll", True))
        fallback_kwargs = dict(kwargs or {})
        fallback_kwargs["allow_reroll"] = bool(allow_reroll)
        fallback_kwargs.pop("game", None)
        if not allow_reroll:
            return False
        game = kwargs.get("game", None)
        if game is None:
            game = getattr(self, "game", None)
        if game is None and player is not None:
            game = getattr(player, "game", None)
        request_fn = getattr(game, "request_decision", None) if game is not None else None
        if not callable(request_fn):
            return self._fallback_roll_reroll_choice(
                player=player,
                unit=unit,
                roll_type=roll_type,
                value=value,
                dice=dice,
                **fallback_kwargs,
            )

        from ..engine.decision_kinds import DECISION_REROLL_ROLL
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import (
            decision_request_is_pending,
            require_synchronous_decision_resolution,
            resolve_or_reuse_payload_choice,
        )

        rt = str(roll_type or "").strip().lower()
        request = DecisionRequest.create(
            DECISION_REROLL_ROLL,
            self._reroll_prompt_title(rt),
            player_id=getattr(player, "id", None) if player is not None else None,
            options=[
                DecisionOption.create("Keep", payload={"reroll": False}),
                DecisionOption.create("Re-roll", payload={"reroll": True}),
            ],
            context={
                "roll_type": rt,
                "roll_value": value,
                "unit_id": str(maybe_entity_id(unit) or ""),
            },
        )
        try:
            request_fn(request)
        except ValueError:
            return self._fallback_roll_reroll_choice(
                player=player,
                unit=unit,
                roll_type=roll_type,
                value=value,
                dice=dice,
                **fallback_kwargs,
            )

        fallback_choice = None
        if decision_request_is_pending(game, request):
            provider = getattr(self, "_roll_reroll_provider", None)
            if callable(provider):
                try:
                    fallback_choice = bool(
                        provider(
                            player=player,
                            unit=unit,
                            roll_type=roll_type,
                            value=value,
                            dice=dice,
                            **fallback_kwargs,
                        )
                    )
                except Exception:
                    fallback_choice = None

        resolved_choice, apply_result = resolve_or_reuse_payload_choice(
            game,
            request,
            payload_key="reroll",
            fallback_value=fallback_choice,
            player_id=getattr(player, "id", None) if player is not None else None,
        )
        require_synchronous_decision_resolution(
            game,
            request,
            detail="Reroll decision remained pending without a synchronous decision owner.",
        )
        return bool(resolved_choice and apply_result is not None and getattr(apply_result, "ok", False))

    @property
    def roll_reroll_provider(self):
        return self._resolve_roll_reroll_provider

    @roll_reroll_provider.setter
    def roll_reroll_provider(self, provider) -> None:
        self._roll_reroll_provider = provider if callable(provider) else None

    def create_boundary_polygon(self) -> Polygon:
        """
        Creates a Shapely Polygon representing the battlefield boundaries.
        """
        return build_boundary_polygon(self.width, self.height)

    def add_terrain_feature(self, terrain_feature: 'TerrainFeature') -> None:
        """Add terrain feature."""
        self.terrain_features.append(terrain_feature)

    def add_terrain_features(self, terrain_features: List['TerrainFeature']) -> None:
        """Add multiple terrain features."""
        self.terrain_features.extend(terrain_features)

    def add_terrain_area(self, terrain_area: 'TerrainArea') -> None:
        """Add terrain area."""
        self.terrain_areas.append(terrain_area)

    def add_terrain_areas(self, terrain_areas: List['TerrainArea']) -> None:
        """Add multiple terrain areas."""
        self.terrain_areas.extend(terrain_areas)

    def add_objective(self, objective: 'Objective') -> None:
        self.objectives.append(objective)

    def add_objectives(self, objectives: List['Objective']) -> None:
        self.objectives.extend(objectives)

    def get_objectives(self, is_secret: bool = False) -> List['Objective']:
        return [objective for objective in self.objectives if objective.category == ObjectiveCategory.SECRET]

    @staticmethod
    def _unit_collision_models(unit: Unit) -> List[Model]:
        getter = getattr(unit, "get_models_for_collision", None)
        if callable(getter):
            return list(getter() or [])
        return list(getattr(unit, "models", []) or [])

    def place_unit(self, unit: Unit) -> bool:
        models = self._unit_collision_models(unit)
        for model in models:
            if not self.is_within_boundary(model):
                return False
            if self.check_collision_with_terrain(model):
                return False
            if self.check_collision_with_other_friendly_units(model):
                return False
            if self.check_collision_with_other_enemy_units(model):
                return False
        self.units.append(unit)
        return True

    def get_all_models(self, units: Optional[List[Unit]] = None) -> List[Model] :
        if units is None:
            units = self.units
        all_models = []
        for unit in units:
            all_models.extend(self._unit_collision_models(unit))
        return all_models

    def get_enemy_units(self, unit: Unit) -> List[Unit]:
        enemy_units = []
        for test_unit in self.units:
            if unit.get_parent_army() != test_unit.get_parent_army():
                enemy_units.append(test_unit)
        return enemy_units

    def get_enemy_models(self, unit: Unit) -> List[Model]:
        enemy_models = []
        for test_unit in self.get_enemy_units(unit):
            enemy_models.extend(self._unit_collision_models(test_unit))
        return enemy_models

    def get_friendly_units(self, unit: Unit) -> List[Unit]:
        friendly_units = []
        for test_unit in self.units:
            if unit.get_parent_army() == test_unit.get_parent_army():
                friendly_units.append(test_unit)
        return friendly_units

    def get_friendly_models(self, unit: Unit) -> List[Model]:
        friendly_models = []
        for test_unit in self.get_friendly_units(unit):
            friendly_models.extend(self._unit_collision_models(test_unit))
        return friendly_models

    def is_within_boundary(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        """
        Checks if a given Shapely geometry is fully contained within the battlefield boundary.
        """
        test_shape = model.model_base.get_base_shape()
        if destination:
            test_shape = translate(test_shape, destination[0] - model.model_base.x, destination[1] - model.model_base.y)
        min_x, min_y, max_x, max_y = test_shape.bounds
        return bool(min_x >= 0.0 and min_y >= 0.0 and max_x <= float(self.width) and max_y <= float(self.height))

    def is_within_engagement_range(self, source_unit: Unit, target_unit: Unit) -> bool:
        """
        Check if any model in the source unit is within engagement range of any model in the target unit.

        Args:
            source_unit: The source unit to check from
            target_unit: The target unit to check against

        Returns:
            bool: True if any model in source unit is within engagement range of any model in target unit
        """
        # Attached units are treated as aggregates for rules purposes.
        source_models = source_unit.get_models_for_collision()
        target_models = target_unit.get_models_for_collision()
        geometry = geometry_profile_for_context(source_unit=source_unit, target_unit=target_unit)

        for source_model in source_models:
            if not source_model.is_alive:
                continue
            for target_model in target_models:
                if not target_model.is_alive:
                    continue
                state = engagement_state_for_models(
                    source_model,
                    target_model,
                )
                if state is not CombatEngagementState.UNENGAGED:
                    source_pos = source_model.get_location()
                    target_pos = target_model.get_location()
                    logger.debug(f"DEBUG: ENGAGEMENT DETECTED!")
                    logger.debug(f"DEBUG: {source_unit.name} model at {source_pos}")
                    logger.debug(f"DEBUG: {target_unit.name} model at {target_pos}")
                    logger.debug(
                        "DEBUG: Engagement profile: horizontal %.2f\" / vertical %.2f\"",
                        float(geometry.engagement_range_horizontal or 0.0),
                        float(geometry.engagement_range_vertical or 0.0),
                    )
                    return True
        return False

    def calculate_pivot_cost(self, unit: Unit) -> float:
        """
        Calculate the pivot cost for a unit based on its characteristics.
        """
        return get_pivot_cost(unit)

    def check_collision_with_terrain(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        """Check collision with terrain features."""
        shape = model.model_base.get_base_shape()
        if destination:
            shape = translate(shape, destination[0] - model.model_base.x, destination[1] - model.model_base.y)

        # Check collision with terrain features using the new system
        from ..utility.calcs import get_terrain_blocking_polygons
        for terrain_feature in self.terrain_features:
            blocking_polygons = get_terrain_blocking_polygons(model.parent_unit, terrain_feature)
            for blocking_polygon in blocking_polygons:
                if shape.intersects(blocking_polygon):
                    return True
        return False

    def check_collision_with_other_friendly_units(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        test_base = model.model_base
        if destination:
            test_base = model.parent_unit._create_potential_base(destination[0], destination[1], test_base.z, test_base.facing)
        for unit in self.get_friendly_units(model.parent_unit):
            if unit != model.parent_unit:  #  inter-unit collisions check done elsewhere
                other_models = self._unit_collision_models(unit)
                for other_model in other_models:
                    #print(f"Friendly Unit Check :: {model.parent_unit.name} checking collision with friendly units :: {other_model.parent_unit.name}")
                    if test_base.collides_with(other_model.model_base):
                        return True
        return False

    def check_collision_with_other_enemy_units(self, model: Model, destination: Tuple[float, float] = None) -> bool:
        test_base = model.model_base
        if destination:
            test_base = model.parent_unit._create_potential_base(destination[0], destination[1], test_base.z, test_base.facing)
        
        for unit in self.get_enemy_units(model.parent_unit):
            other_models = self._unit_collision_models(unit)
            for other_model in other_models:
                #print(f"Enemy Unit Check :: {model.parent_unit.name} checking collision with enemy units :: {other_model.parent_unit.name}")
                if test_base.collides_with(other_model.model_base):
                    return True
        return False

    ###########################################################################
    # Benefit of Cover (terrain-based save bonus)
    ###########################################################################
    def _sample_model_points_3d(self, model: Model, perimeter_points: int = 8, z_levels: int = 3) -> List[Tuple[float, float, float]]:
        return terrain_sample_model_points_3d(model, perimeter_points=perimeter_points, z_levels=z_levels)

    def _segment_blocked_by_terrain_feature(
        self,
        p0: Tuple[float, float, float],
        p1: Tuple[float, float, float],
        terrain: 'TerrainFeature',
        shooter_model: Model,
        target_model: Model,
    ) -> bool:
        return terrain_segment_blocked_by_terrain_feature(p0, p1, terrain, shooter_model, target_model)

    def _is_fully_visible_due_to_terrain(self, shooter_model: Model, target_model: Model, terrain: 'TerrainFeature') -> bool:
        return terrain_is_fully_visible_due_to_terrain(shooter_model, target_model, terrain)

    def get_visibility_context_for_models(self, shooter_model: Model, target_model: Model) -> Dict[str, Any]:
        return terrain_get_visibility_context_for_models(self, shooter_model, target_model)

    def can_model_see_model(self, shooter_model: Model, target_model: Model) -> bool:
        return terrain_can_model_see_model(self, shooter_model, target_model)

    def get_benefit_of_cover_for_ranged_attack(
        self,
        attacking_unit: Unit,
        target_model: Model,
        weapon_profile: Optional[Any] = None,
        ap: Optional[int] = None,
    ) -> Dict[str, Any]:
        return terrain_get_benefit_of_cover_for_ranged_attack(
            self,
            attacking_unit=attacking_unit,
            target_model=target_model,
            weapon_profile=weapon_profile,
            ap=ap,
        )

    @staticmethod
    def _unit_root(unit: Optional[Unit]) -> Optional[Unit]:
        return terrain_unit_root(unit)

    @staticmethod
    def _unit_has_keyword(unit: Optional[Unit], keyword: str) -> bool:
        return terrain_unit_has_keyword(unit, keyword)

    @staticmethod
    def _iter_root_models(root: Optional[Unit]) -> list[Model]:
        return terrain_iter_root_models(root)

    @staticmethod
    def _shape_covers(container: Any, target: Any) -> bool:
        return terrain_shape_covers(container, target)

    @staticmethod
    def _candidate_base_for_pose(model: Optional[Model], x: float, y: float, z: float) -> Optional[Any]:
        return terrain_candidate_base_for_pose(model, x, y, z)

    @staticmethod
    def _compound_part_surface_entry(
        source_model: Optional[Model],
        *,
        part_id: str,
    ) -> Optional[dict[str, Any]]:
        return terrain_compound_part_surface_entry(
            source_model,
            part_id=part_id,
        )

    def _iter_emplacement_platform_surface_entries(
        self,
        *,
        moving_model: Optional[Model] = None,
        require_eligibility: bool = True,
    ) -> tuple[dict[str, Any], ...]:
        return terrain_iter_emplacement_platform_surface_entries(
            self,
            moving_model=moving_model,
            require_eligibility=require_eligibility,
        )

    def get_emplacement_platform_surface_entries(
        self,
        *,
        moving_model: Optional[Model] = None,
        require_eligibility: bool = True,
    ) -> tuple[dict[str, Any], ...]:
        return terrain_get_emplacement_platform_surface_entries(
            self,
            moving_model=moving_model,
            require_eligibility=require_eligibility,
        )

    def get_emplacement_platform_placement(
        self,
        moving_model: Optional[Model],
        *,
        x: float,
        y: float,
        z: Optional[float] = None,
        require_eligibility: bool = True,
    ) -> Dict[str, Any]:
        return terrain_get_emplacement_platform_placement(
            self,
            moving_model,
            x=x,
            y=y,
            z=z,
            require_eligibility=require_eligibility,
        )

    def validate_model_surface_placement(
        self,
        model: Optional[Model],
        position: tuple[float, float, float],
    ) -> Dict[str, Any]:
        return terrain_validate_model_surface_placement(self, model, position)

    def get_surface_options_for_model(self, model: Optional[Model], x: float, y: float) -> list[float]:
        return terrain_get_surface_options_for_model(self, model, x, y)

    def get_surface_height_for_model(self, model: Optional[Model], x: float, y: float) -> float:
        return terrain_get_surface_height_for_model(self, model, x, y)

    @staticmethod
    def _footprint_and_bounding_box_for_models(models: list[Model]) -> tuple[Any, Optional[dict]]:
        return terrain_footprint_and_bounding_box_for_models(models)

    def get_benefit_of_cover_from_fortifications(
        self,
        attacking_unit: Unit,
        target_model: Model,
        fortification_units: list,
        weapon_profile: Optional[Any] = None,
    ) -> Dict[str, Any]:
        return terrain_get_benefit_of_cover_from_fortifications(
            self,
            attacking_unit=attacking_unit,
            target_model=target_model,
            fortification_units=fortification_units,
            weapon_profile=weapon_profile,
        )

    def get_selfless_protector_bonus_for_ranged_attack(
        self,
        attacking_unit: Unit,
        target_model: Model,
        protector_units: list,
        weapon_profile: Optional[Any] = None,
    ) -> Dict[str, Any]:
        return terrain_get_selfless_protector_bonus_for_ranged_attack(
            self,
            attacking_unit=attacking_unit,
            target_model=target_model,
            protector_units=protector_units,
            weapon_profile=weapon_profile,
        )

    def get_defence_line_bonus_for_ranged_attack(
        self,
        attacking_unit: Unit,
        target_model: Model,
        fortification_units: list,
        weapon_profile: Optional[Any] = None,
    ) -> Dict[str, Any]:
        return terrain_get_defence_line_bonus_for_ranged_attack(
            self,
            attacking_unit=attacking_unit,
            target_model=target_model,
            fortification_units=fortification_units,
            weapon_profile=weapon_profile,
        )

    def get_height_at_point(self, x: float, y: float) -> float:
        return terrain_get_height_at_point(self, x, y)

    def get_plunging_fire_context(self, attacker: Model, target: Unit) -> Dict[str, Any]:
        return terrain_get_plunging_fire_context(self, attacker, target)

    def get_distance_between_units(self, unit1: Unit, unit2: Unit) -> float:
        """Calculate the shortest distance between two units.
        
        Args:
            unit1 (Unit): First unit
            unit2 (Unit): Second unit
            
        Returns:
            float: The shortest distance between any models in the two units
        """
        from ..utility.aura_utils import min_distance_between_units_3d
        return float(min_distance_between_units_3d(unit1, unit2, use_attached_aggregate=True))

    def is_path_blocked(self, unit: Unit, target: Unit) -> bool:
        """Check if there's a clear path between two units considering terrain and obstacles.

        Args:
            unit (Unit): The unit checking the path
            target (Unit): The target unit

        Returns:
            bool: True if path is blocked, False if clear
        """
        # Get the positions from first alive model in each unit
        unit_pos = None
        unit_models = self._unit_collision_models(unit)
        for model in unit_models:
            if model.is_alive:
                unit_pos = model.get_location()
                break

        target_pos = None
        target_models = self._unit_collision_models(target)
        for model in target_models:
            if model.is_alive:
                target_pos = model.get_location()
                break

        if not unit_pos or not target_pos:
            return True  # Consider path blocked if we can't determine positions

        # Create a line representing the path
        path = LineString([(unit_pos[0], unit_pos[1]), (target_pos[0], target_pos[1])])

        # Check for intersections with terrain features
        for terrain_feature in self.terrain_features:
            if path.intersects(terrain_feature.footprint):
                if not can_traverse_freely(unit, terrain_feature):
                    return True  # Path is blocked

        return False  # Path is clear

    def get_battlefield_edge_repulsors(self) -> List:
        """Generate battlefield edge repulsors for movement collision detection.
        
        Returns:
            List of Shapely polygons representing battlefield edge repulsors
        """
        return battlefield_edge_repulsors(self.width, self.height)


class RuinsTerrain(TerrainFeature):
    """RUINS terrain with walls, floors, and openings."""

    def __init__(self, footprint: Polygon, walls: List[dict] = None,
                 openings: List[dict] = None, floors: List[dict] = None,
                 height_map: dict = None):
        """
        Args:
            footprint: 2D ground outline of the ruins
            walls: List of wall definitions with polygon, z_bottom, z_top, thickness
            openings: List of opening definitions (windows/doors)
            floors: List of floor definitions with polygon and elevation
            height_map: Optional detailed elevation map {(x,y): z}
        """
        self.walls = walls or []
        self.openings = openings or []
        self.floors = floors or []
        self.height_map = height_map or {}

        # Calculate bounding box
        bounds = footprint.bounds  # (minx, miny, maxx, maxy)
        max_z = max([wall["z_top"] for wall in self.walls] +
                   [floor["elevation"] + floor.get("thickness", 0.5) for floor in self.floors] + [0.0])

        bounding_box = {
            "min": (bounds[0], bounds[1], 0.0),
            "max": (bounds[2], bounds[3], max_z)
        }

        # Traversal rules for RUINS
        traversal_rules = {
            "infantry_can_pass_walls": True,
            "beast_can_pass_walls": True,
            "imperium_primarch_can_pass_walls": True,
            "belisarius_cawl_can_pass_walls": True,
            "vehicle_can_pass_walls": False,
            "monster_can_pass_walls": False,
            "flying_can_pass_walls": False,
            "titanic_can_pass_walls": False,
        }

        super().__init__(TerrainType.RUINS, footprint, bounding_box, traversal_rules)

    def check_wall_collision(self, position: Tuple[float, float, float]) -> bool:
        """Check if a position collides with any wall."""
        if not self.point_in_bounds(position):
            return False

        x, y, z = position
        point = Point(x, y)

        for wall in self.walls:
            if (wall["z_bottom"] <= z <= wall["z_top"] and
                wall["polygon"].contains(point)):
                return True
        return False

    def check_opening_passage(self, position: Tuple[float, float, float]) -> bool:
        """Check if a position is within an opening that allows movement."""
        x, y, z = position
        point = Point(x, y)

        for opening in self.openings:
            if (opening.get("allows_movement", False) and
                opening["z_bottom"] <= z <= opening["z_top"] and
                opening["polygon"].contains(point)):
                return True
        return False

    def can_unit_move_through(self, unit, position: Tuple[float, float, float]) -> bool:
        """Check if a unit can move through a specific position in the ruins."""
        if not self.point_in_bounds(position):
            return True

        x, y, z = position
        point = Point(x, y)
        colliding_walls = []
        for wall in self.walls:
            if (wall["z_bottom"] <= z <= wall["z_top"] and
                wall["polygon"].contains(point)):
                colliding_walls.append(wall)

        if not colliding_walls:
            return True

        from ..utility.calcs import get_freely_climbable_range
        threshold = get_freely_climbable_range(unit)
        all_low = True
        for wall in colliding_walls:
            height = float(wall.get("z_top", 0.0)) - float(wall.get("z_bottom", 0.0))
            if height > threshold:
                all_low = False
                break
        if all_low:
            return True

        can_breach = False
        fn = getattr(unit, "can_move_through_ruins_walls", None)
        if callable(fn):
            can_breach = bool(fn())
        if can_breach:
            return True

        return self.check_opening_passage(position)

    def _get_unit_type(self, unit) -> str:
        """Get unit type string for traversal rule lookup."""
        try:
            fn = getattr(unit, "counts_as_infantry_for_terrain", None)
            if callable(fn) and fn():
                return "infantry"
        except (AttributeError, TypeError, ValueError):
            pass
        if getattr(unit, 'is_infantry', False):
            return "infantry"
        elif getattr(unit, 'is_beast', False):
            return "beast"
        elif getattr(unit, 'is_flying', False):
            return "flying"
        elif getattr(unit, 'is_imperium_primarch', False):
            return "imperium_primarch"
        elif getattr(unit, 'is_belisarius_cawl', False):
            return "belisarius_cawl"
        elif getattr(unit, 'is_titanic', False):
            return "titanic"
        elif 'Vehicle' in getattr(unit, 'keywords', []):
            return "vehicle"
        elif 'Monster' in getattr(unit, 'keywords', []):
            return "monster"
        else:
            return "infantry"  # Default to infantry rules

class WoodsTerrain(TerrainFeature):
    """WOODS terrain - all units can traverse freely."""

    def __init__(self, footprint: Polygon, height: float = 6.0, density: float = 0.7):
        """
        Args:
            footprint: 2D outline of the woods
            height: Height of the tree canopy
            density: Tree density (0.0 to 1.0) affects line of sight
        """
        self.height = height
        self.density = density

        bounds = footprint.bounds
        bounding_box = {
            "min": (bounds[0], bounds[1], 0.0),
            "max": (bounds[2], bounds[3], height)
        }

        traversal_rules = {
            "all_units_can_traverse": True,
            "blocks_line_of_sight": density > 0.5,
            "provides_cover": True
        }

        super().__init__(TerrainType.WOODS, footprint, bounding_box, traversal_rules)

class CraterTerrain(TerrainFeature):
    """CRATER_AND_RUBBLE terrain - difficult ground, all units can traverse."""

    def __init__(self, footprint: Polygon, depth: float = 2.0, rim_height: float = 1.0):
        """
        Args:
            footprint: 2D outline of the crater
            depth: How deep the crater goes (negative Z)
            rim_height: Height of crater rim above ground
        """
        self.depth = depth
        self.rim_height = rim_height

        bounds = footprint.bounds
        bounding_box = {
            "min": (bounds[0], bounds[1], -depth),
            "max": (bounds[2], bounds[3], rim_height)
        }

        traversal_rules = {
            "all_units_can_traverse": True,
            "difficult_terrain": True,
            "provides_cover": True
        }

        super().__init__(TerrainType.CRATER_AND_RUBBLE, footprint, bounding_box, traversal_rules)

class BarricadeTerrain(TerrainFeature):
    """BARRICADE_AND_FUEL_PIPES terrain - linear obstacles that can be climbed over."""

    def __init__(self, footprint: Polygon, height: float = 3.0, thickness: float = 1.0):
        """
        Args:
            footprint: 2D outline of the barricade
            height: Height of the barricade
            thickness: Thickness of the barricade structure
        """
        self.height = height
        self.thickness = thickness

        bounds = footprint.bounds
        bounding_box = {
            "min": (bounds[0], bounds[1], 0.0),
            "max": (bounds[2], bounds[3], height)
        }

        traversal_rules = {
            "all_units_can_traverse": True,
            "requires_climbing": height > 2.0,
            "provides_cover": True,
            "blocks_vehicles": height > 4.0  # Very tall barricades block vehicles
        }

        super().__init__(TerrainType.BARRICADE_AND_FUEL_PIPES, footprint, bounding_box, traversal_rules)

class DebrisTerrain(TerrainFeature):
    """DEBRIS_AND_STATUARY terrain - scattered obstacles, can traverse but not end on."""

    def __init__(self, footprint: Polygon, height: float = 2.0, scatter_density: float = 0.6):
        """
        Args:
            footprint: 2D outline of the debris field
            height: Average height of debris pieces
            scatter_density: How densely packed the debris is
        """
        self.height = height
        self.scatter_density = scatter_density

        bounds = footprint.bounds
        bounding_box = {
            "min": (bounds[0], bounds[1], 0.0),
            "max": (bounds[2], bounds[3], height)
        }

        traversal_rules = {
            "all_units_can_traverse": True,
            "cannot_end_move_on": True,  # Can move through but not stop on
            "difficult_terrain": scatter_density > 0.5,
            "provides_cover": True
        }

        super().__init__(TerrainType.DEBRIS_AND_STATUARY, footprint, bounding_box, traversal_rules)

class HillsBuildingsTerrain(TerrainFeature):
    """HILLS_AND_SEALED_BUILDINGS terrain - elevated surfaces with access restrictions."""

    def __init__(self, footprint: Polygon, height: float = 6.0,
                 access_points: List[Polygon] = None, max_base_size: float = 3.0):
        """
        Args:
            footprint: 2D outline of the hill/building
            height: Height of the elevated surface
            access_points: Areas where units can climb up (ramps, stairs)
            max_base_size: Maximum base size that can fit without overhanging
        """
        self.height = height
        self.access_points = access_points or []
        self.max_base_size = max_base_size

        bounds = footprint.bounds
        bounding_box = {
            "min": (bounds[0], bounds[1], 0.0),
            "max": (bounds[2], bounds[3], height)
        }

        traversal_rules = {
            "requires_access_point": len(self.access_points) > 0,
            "base_overhang_check": True,
            "max_base_size": max_base_size,
            "provides_elevation_advantage": True
        }

        super().__init__(TerrainType.HILLS_AND_SEALED_BUILDINGS, footprint, bounding_box, traversal_rules)

    def can_base_fit(self, base_size: float) -> bool:
        """Check if a model's base can fit on this terrain without overhanging."""
        return base_size <= self.max_base_size

    def has_access_from(self, position: Tuple[float, float]) -> bool:
        """Check if there's an access point near the given position."""
        if not self.access_points:
            return True  # No restrictions if no access points defined

        point = Point(position[0], position[1])
        return any(access.contains(point) or access.distance(point) < 2.0
                  for access in self.access_points)

class TerrainFactory:
    """Factory class for creating terrain features."""

    @staticmethod
    def create_ruins(footprint_vertices: List[Tuple[float, float]],
                    wall_height: float = RUINS_FLOOR_HEIGHT, num_floors: int = 1,
                    has_windows: bool = True, has_doors: bool = True) -> RuinsTerrain:
        """Create a RUINS terrain with walls, floors, and openings."""
        footprint = Polygon(footprint_vertices)

        walls = []
        openings = []
        floors = []

        # Create floors for each level
        for floor_level in range(num_floors + 1):  # Include ground floor
            floors.append({
                "polygon": footprint,
                "elevation": floor_level * wall_height,
                "thickness": RUINS_FLOOR_THICKNESS
            })

        # Create walls around perimeter
        coords = list(footprint.exterior.coords)[:-1]  # Remove duplicate last point
        for i in range(len(coords)):
            start_point = coords[i]
            end_point = coords[(i + 1) % len(coords)]

            # Create wall segment with thickness
            wall_line = LineString([start_point, end_point])
            wall_polygon = wall_line.buffer(RUINS_WALL_THICKNESS / 2.0)

            for floor_level in range(num_floors + 1):
                walls.append({
                    "polygon": wall_polygon,
                    "z_bottom": floor_level * wall_height,
                    "z_top": (floor_level + 1) * wall_height,
                    "thickness": RUINS_WALL_THICKNESS
                })

                # Add windows and doors
                if has_windows and floor_level > 0:  # Windows on upper floors
                    window_polygon = wall_line.interpolate(0.5, normalized=True).buffer(1.0)
                    openings.append({
                        "polygon": window_polygon,
                        "z_bottom": floor_level * wall_height + 1.0,
                        "z_top": floor_level * wall_height + 3.0,
                        "allows_movement": False,
                        "allows_los": True
                    })

                if has_doors and floor_level == 0 and i == 0:  # Door on ground floor, first wall
                    door_polygon = wall_line.interpolate(0.5, normalized=True).buffer(1.5)
                    openings.append({
                        "polygon": door_polygon,
                        "z_bottom": 0.0,
                        "z_top": 3.0,
                        "allows_movement": True,
                        "allows_los": True
                    })

        return RuinsTerrain(footprint, walls, openings, floors)

    @staticmethod
    def create_woods(footprint_vertices: List[Tuple[float, float]],
                    height: float = 6.0, density: float = 0.7) -> WoodsTerrain:
        """Create WOODS terrain."""
        footprint = Polygon(footprint_vertices)
        return WoodsTerrain(footprint, height, density)

    @staticmethod
    def create_crater(footprint_vertices: List[Tuple[float, float]],
                     depth: float = 2.0, rim_height: float = 1.0) -> CraterTerrain:
        """Create CRATER_AND_RUBBLE terrain."""
        footprint = Polygon(footprint_vertices)
        return CraterTerrain(footprint, depth, rim_height)

    @staticmethod
    def create_barricade(start_point: Tuple[float, float], end_point: Tuple[float, float],
                        height: float = 3.0, thickness: float = 1.0) -> BarricadeTerrain:
        """Create BARRICADE_AND_FUEL_PIPES terrain."""
        line = LineString([start_point, end_point])
        footprint = line.buffer(thickness / 2.0)
        return BarricadeTerrain(footprint, height, thickness)

    @staticmethod
    def create_debris(footprint_vertices: List[Tuple[float, float]],
                     height: float = 2.0, density: float = 0.6) -> DebrisTerrain:
        """Create DEBRIS_AND_STATUARY terrain."""
        footprint = Polygon(footprint_vertices)
        return DebrisTerrain(footprint, height, density)

    @staticmethod
    def create_hill(footprint_vertices: List[Tuple[float, float]],
                   height: float = 6.0, access_points: List[List[Tuple[float, float]]] = None,
                   max_base_size: float = 3.0) -> HillsBuildingsTerrain:
        """Create HILLS_AND_SEALED_BUILDINGS terrain."""
        footprint = Polygon(footprint_vertices)
        access_polygons = []
        if access_points:
            access_polygons = [Polygon(points) for points in access_points]
        return HillsBuildingsTerrain(footprint, height, access_polygons, max_base_size)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant1() -> RuinsTerrain:
        return terrain_create_preset_ruin_rect_12x6_variant1(RuinsTerrain)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant2() -> RuinsTerrain:
        return terrain_create_preset_ruin_rect_12x6_variant2(RuinsTerrain)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant3() -> RuinsTerrain:
        return terrain_create_preset_ruin_rect_12x6_variant3(RuinsTerrain)

    @staticmethod
    def create_preset_ruin_rect_6x4_variant1() -> RuinsTerrain:
        return terrain_create_preset_ruin_rect_6x4_variant1(RuinsTerrain)

    @staticmethod
    def create_preset_ruin_rect_6x4_variant2() -> RuinsTerrain:
        return terrain_create_preset_ruin_rect_6x4_variant2(RuinsTerrain)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant4() -> RuinsTerrain:
        return terrain_create_preset_ruin_rect_12x6_variant4(RuinsTerrain)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant5() -> RuinsTerrain:
        return terrain_create_preset_ruin_rect_12x6_variant5(RuinsTerrain)

    @staticmethod
    def create_preset_ruin_rect_12x6_variant6() -> RuinsTerrain:
        return terrain_create_preset_ruin_rect_12x6_variant6(RuinsTerrain)

    @staticmethod
    def create_preset_ruin_rect_10x5_variant1() -> RuinsTerrain:
        return terrain_create_preset_ruin_rect_10x5_variant1(RuinsTerrain)

    @staticmethod
    def create_preset_ruin_rect_10x5_variant2() -> RuinsTerrain:
        return terrain_create_preset_ruin_rect_10x5_variant2(RuinsTerrain)

    @staticmethod
    def create_preset_ruin_rect_10x5_variant3() -> RuinsTerrain:
        return terrain_create_preset_ruin_rect_10x5_variant3(RuinsTerrain)


def validate_ruins_placement(
    unit: 'Unit',
    position: Tuple[float, float, float],
    terrain_features: List['TerrainFeature'],
    moving_model: Optional['Model'] = None,
) -> dict:
    return terrain_validate_ruins_placement(
        unit,
        position,
        terrain_features,
        moving_model=moving_model,
    )
