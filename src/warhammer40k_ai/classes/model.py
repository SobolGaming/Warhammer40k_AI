from typing import List, Optional
from .wargear import Wargear
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
        self.name = name
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

    def add_wargear(self, wargear: Wargear) -> None:
        """Add wargear to the model."""
        self.wargear.append(wargear)
    
    def add_optional_wargear(self, wargear: str) -> None:
        """Add optional wargear to the model."""
        self.optional_wargear.append(wargear)

    def set_parent_unit(self, unit_ptr) -> None:
        """Set the parent unit of the model."""
        self.parent_unit = unit_ptr

    def set_location(self, x: float, y: float, z: float, facing: float) -> None:
        """Set the location and facing of the model."""
        self.model_base.x = x
        self.model_base.y = y
        self.model_base.z = z
        self.model_base.facing = facing

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
        # TODO: some units/models have new stats when they reach a wound threshold

    def die(self) -> None:
        logger.info(f"{self.name} [{self.id}] has Died!!!")
        #self.callbacks[hook_events.ENEMY_MODEL_KILLED].append(self)
        self.parent_unit.remove_model(self, False)

    # Fleeing is like dying but does not trigger any rules of when a "model is destroyed"
    def flee(self) -> None:
        logger.info(f"{self.name} [{self.id}] has Fled!!!")
        self.parent_unit.remove_model(self, True)

    def heal(self, amount: int = 0) -> None:
        self.wounds += amount
        self.wounds = min(self.base_wounds, self.wounds)
        logger.info(f"{self.name} is healed for {amount} damage")
        # TODO: some units/models have new stats when they reach a wound threshold

    ################
    ### String Representation
    ################
    def __str__(self) -> str:
        return (f"{self.name} (M:{self.movement}\", T:{self.toughness}, Sv:{self.save}+, "
                f"InvSv:{self.inv_save or '-'}+, W:{self.wounds}, Ld:{self.leadership}+, "
                f"OC:{self.objective_control}\nbase_size:{self.model_base}\n"
                f"wargear:{self.wargear}\noptional_wargear:{self.optional_wargear}\nid:{self.id})")

    def __repr__(self) -> str:
        return (f"Model(id='{self.id}', name='{self.name}', M={self.movement}, "
                f"T={self.toughness}, Sv={self.save}, InvSv={self.inv_save}, "
                f"W={self.wounds}, Ld={self.leadership}, OC={self.objective_control}\n"
                f"base_size={self.model_base}\nwargear={self.wargear}\n"
                f"optional_wargear={self.optional_wargear})")
