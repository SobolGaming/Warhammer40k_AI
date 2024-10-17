from typing import List, Dict, Optional, Tuple
from .wargear import Wargear
from .ability import Ability
from .status_effects import UnitStatsModifier
from ..utility.model_base import Base
import uuid
import logging
from math import degrees
from ..utility.calcs import get_dist, get_angle


logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)


class Model:
    """Represents a Warhammer 40k model with its attributes and wargear."""

    def __init__(self, name: str, movement: int, toughness: int, save: int, 
                 wounds: int, leadership: int, objective_control: int, model_base: Base, 
                 inv_save: Optional[int] = None):
        self.name = name.split(' – ')[0]
        # Model attributes have a base value, but can be modified by wargear, strategems, etc
        # We need to track base value and current value separately
        self._base_movement = movement
        self._movement = movement
        self._base_toughness = toughness
        self._toughness = toughness
        self._base_save = save
        self._save = save
        self._inv_save = inv_save # nothing can modify this
        self._base_wounds = wounds
        self._wounds = wounds
        self._base_leadership = leadership
        self._leadership = leadership
        self._base_objective_control = objective_control
        self._objective_control = objective_control

        self.model_base = model_base
        self.wargear: List[Wargear] = []
        self.abilities: Dict[Ability] = {}
        self.optional_wargear: List[str] = []

        # Gameplay related attributes
        self._id = str(uuid.uuid4())  # Generate a unique ID for each model
        self.parent_unit = None

    @property
    def id(self) -> str:
        """Return the unique ID of the model."""
        return self._id

    @property
    def is_alive(self) -> bool:
        """Return whether the model is alive."""
        return self.wounds > 0

    @property
    def has_circular_base(self) -> bool:
        """Return whether the model has a circular base."""
        return self.model_base.has_circular_base

    @property
    def base_size(self) -> float:
        """Return the base size of the model."""
        return self.model_base.base_size

    @property
    def facing(self) -> float:
        """Return the facing of the model."""
        return self.model_base.facing

    @property
    def is_max_health(self) -> bool:
        """Return whether the model is at full health."""
        return self.wounds == self.base_wounds

    def add_wargear(self, wargear: Wargear) -> None:
        """Add wargear to the model."""
        self.wargear.append(wargear)
    
    def add_optional_wargear(self, wargear: str) -> None:
        """Add optional wargear to the model."""
        self.optional_wargear.append(wargear)

    def get_optional_wargear_by_name(self, wargear_name: str) -> Optional[Ability]:
        for wargear in self.optional_wargear:
            if wargear.lower() == wargear_name.lower():
                for ability in self.parent_unit.possible_abilities:
                    if ability.name.lower() == wargear_name.lower():
                        return ability
        return None

    def add_ability(self, ability: Ability) -> None:
        """Add ability to the model."""
        self.abilities[ability.name] = ability

    def set_parent_unit(self, unit_ptr) -> None:
        """Set the parent unit of the model."""
        self.parent_unit = unit_ptr

    def set_location(self, x: float, y: float, z: float, facing: float) -> None:
        """Set the location and facing of the model."""
        self.model_base.x = x
        self.model_base.y = y
        self.model_base.z = z
        self.model_base.facing = facing

    def get_location(self) -> Tuple[float, float, float, float]:
        """Get the location and facing of the model."""
        return self.model_base.x, self.model_base.y, self.model_base.z, self.model_base.facing

    ################
    ### Modifiers
    ################
    def take_damage(self, amount: int = 0, is_mortal: bool = False):
        self.wounds -= amount
        logger.info(f"{self.name} takes {amount} damage. It is {'Alive' if self.is_alive else 'Dead'}")
        if not self.is_alive:
            self.die()
            if is_mortal and abs(self.wounds) > 0:
                #overage = abs(self.wounds)
                raise Exception("IMPLEMENT MORTAL WOUND DAMAGE OVERAGE HANDLING")
        self._check_damaged_profile()

    def die(self) -> None:
        logger.info(f"{self.name} [{self.id}] has Died!!!")
        #self.callbacks[hook_events.ENEMY_MODEL_KILLED].append(self)
        self.parent_unit.remove_model(self, False)

    # Fleeing is like dying but does not trigger any rules of when a "model is destroyed"
    def flee(self) -> None:
        logger.info(f"{self.name} [{self.id}] has Fled!!!")
        self.parent_unit.remove_model(self, True)

    def heal(self, amount: int = 0) -> None:
        self.wounds = min(self._base_wounds, self.wounds + amount)
        logger.info(f"{self.name} is healed for {amount} damage")
        self._check_damaged_profile()

    def _check_damaged_profile(self) -> None:
        if self.parent_unit and self.parent_unit.damaged_profile and self.parent_unit.damaged_profile_desc:
            if self.is_alive and self.wounds in self.parent_unit.damaged_profile:
                self._apply_damaged_profile(self.parent_unit.damaged_profile_desc)

    def _apply_damaged_profile(self, profile: str) -> None:
        # Implement the logic to apply the damaged profile
        # This could involve updating various attributes of the model
        logger.info(f"Applying damaged profile to {self.name}: {profile}")
        # Need string parsing to handle the profile

    ################
    ### Utility Math
    ################
    def distanceBetweenModels(self, other: "Model") -> float:
        # Calculate the distance between two models using their bases
        # Note: we round to 2 decimal precision (we can increase that if necessary)
        delta_x = other.model_base.x - self.model_base.x
        logger.debug(f"Delta X: {delta_x}")
        delta_y = other.model_base.y - self.model_base.y
        logger.debug(f"Delta Y: {delta_y}")
        angle = get_angle(delta_x, delta_y)
        logger.debug(f"Angle (in Degrees): {degrees(angle)}, (in Radians): {angle}")
        if self.model_base.z == other.model_base.z:
            return round(
                get_dist(delta_x, delta_y)
                - self.model_base.get_radius(angle)
                - other.model_base.get_radius(angle)
            , 2)
        elif self.model_base.z + self.model_base.model_height < other.model_base.z:
            xy_dist = round(
                get_dist(delta_x, delta_y)
                - self.model_base.get_radius(angle)
                - other.model_base.get_radius(angle)
            , 2)
            return get_dist(xy_dist, other.model_base.z - self.model_base.z - self.model_base.model_height)
        elif other.model_base.z + other.model_base.model_height < self.model_base.z:
            xy_dist = round(
                get_dist(delta_x, delta_y)
                - self.model_base.get_radius(angle)
                - other.model_base.get_radius(angle)
            , 2)
            return get_dist(xy_dist, self.model_base.z - other.model_base.z - other.model_base.model_height)
        # otherwise treat it the same as if on the same z-axis since parts of the model overlap in the z-space
        else:
            return round(
                get_dist(delta_x, delta_y)
                - self.model_base.getRadius(angle)
                - other.model_base.getRadius(angle)
            , 2)

    def verticalDistanceBetweenModels(self, other: "Model") -> float:
        """Calculate the distance between two models in vertical space."""
        if self.model_base.z + self.model_base.model_height < other.model_base.z:
            return round(other.model_base.z - self.model_base.z - self.model_base.model_height, 2)
        elif other.model_base.z + other.model_base.model_height < self.model_base.z:
            return round(self.model_base.z - other.model_base.z - other.model_base.model_height, 2)
        else:
            return 0.0

    @property
    def movement(self) -> int:
        if hasattr(self.parent_unit.stats, 'movement'):
            if self.parent_unit.stats['movement'][0] == UnitStatsModifier.OVERRIDE:
                return self.parent_unit.stats['movement'][1]
            elif self.parent_unit.stats['movement'][0] == UnitStatsModifier.ADDITIVE:
                return self._movement + self.parent_unit.stats['movement'][1]
        return self._movement

    @movement.setter
    def movement(self, value: int) -> None:
        self._movement = value

    @property
    def toughness(self) -> int:
        if hasattr(self.parent_unit.stats, 'toughness'):
            if self.parent_unit.stats['toughness'][0] == UnitStatsModifier.OVERRIDE:
                return self.parent_unit.stats['toughness'][1]
            elif self.parent_unit.stats['toughness'][0] == UnitStatsModifier.ADDITIVE:
                return self._toughness + self.parent_unit.stats['toughness'][1]
        return self._toughness

    @toughness.setter
    def toughness(self, value: int) -> None:
        self._toughness = value

    @property
    def save(self) -> int:
        if hasattr(self.parent_unit.stats, 'save'):
            if self.parent_unit.stats['save'][0] == UnitStatsModifier.OVERRIDE:
                return self.parent_unit.stats['save'][1]
            elif self.parent_unit.stats['save'][0] == UnitStatsModifier.ADDITIVE:
                return self._save + self.parent_unit.stats['save'][1]
        return self._save

    @save.setter
    def save(self, value: int) -> None:
        self._save = value

    @property
    def inv_save(self) -> Optional[int]:
        return self._inv_save

    @property
    def wounds(self) -> int:
        return self._wounds

    @wounds.setter
    def wounds(self, value: int) -> None:
        self._wounds = value

    @property
    def leadership(self) -> int:
        if hasattr(self.parent_unit.stats, 'leadership'):
            if self.parent_unit.stats['leadership'][0] == UnitStatsModifier.OVERRIDE:
                return self.parent_unit.stats['leadership'][1]
            elif self.parent_unit.stats['leadership'][0] == UnitStatsModifier.ADDITIVE:
                return self._leadership + self.parent_unit.stats['leadership'][1]
        return self._leadership

    @leadership.setter
    def leadership(self, value: int) -> None:
        self._leadership = value

    @property
    def objective_control(self) -> int:
        if hasattr(self.parent_unit.stats, 'objective_control'):
            if self.parent_unit.stats['objective_control'][0] == UnitStatsModifier.OVERRIDE:
                return self.parent_unit.stats['objective_control'][1]
            elif self.parent_unit.stats['objective_control'][0] == UnitStatsModifier.ADDITIVE:
                return self._objective_control + self.parent_unit.stats['objective_control'][1]
        return self._objective_control

    @objective_control.setter
    def objective_control(self, value: int) -> None:
        self._objective_control = value

    ################
    ### String Representation
    ################
    def __str__(self) -> str:
        return (f"{self.name} (M:{self.movement}\", T:{self.toughness}, Sv:{self.save}+, "
                f"InvSv:{self.inv_save or '-'}+, W:{self.wounds}, Ld:{self.leadership}+, "
                f"OC:{self.objective_control}\nbase_size:{self.model_base}\n"
                f"wargear:{self.wargear}\noptional_wargear:{self.optional_wargear}\n"
                f"abilities:{self.abilities.keys()}\nid:{self.id})")

    def __repr__(self) -> str:
        return (f"Model(id='{self.id}', name='{self.name}', M={self.movement}, "
                f"T={self.toughness}, Sv={self.save}, InvSv={self.inv_save}, "
                f"W={self.wounds}, Ld={self.leadership}, OC={self.objective_control}\n"
                f"base_size={self.model_base}\nwargear={self.wargear}\n"
                f"optional_wargear={self.optional_wargear})\n"
                f"abilities={self.abilities.keys()})")
