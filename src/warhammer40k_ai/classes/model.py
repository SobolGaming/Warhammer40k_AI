from typing import List, Dict, Optional, Tuple
from .wargear import Wargear
from .ability import Ability
from ..utility.model_base import Base
import uuid
import logging

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
        self.base_movement = movement
        self.movement = movement
        self.base_toughness = toughness
        self.toughness = toughness
        self.base_save = save
        self.save = save
        self.inv_save = inv_save # nothing can modify this
        self.base_wounds = wounds
        self.wounds = wounds
        self.base_leadership = leadership
        self.leadership = leadership
        self.base_objective_control = objective_control
        self.objective_control = objective_control

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
        self.wounds = min(self.base_wounds, self.wounds + amount)
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
