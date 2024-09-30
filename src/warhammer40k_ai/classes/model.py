from typing import List, Optional
from .wargear import Wargear
from ..utility.model_base import Base
import uuid

class Model:
    """Represents a Warhammer 40k model with its attributes and wargear."""

    def __init__(self, name: str, movement: int, toughness: int, save: int, 
                 wounds: int, leadership: int, objective_control: int, model_base: Base, 
                 inv_save: Optional[int] = None):
        self.name = name
        self.movement = movement
        self.toughness = toughness
        self.save = save
        self.inv_save = inv_save
        self.wounds = wounds
        self.leadership = leadership
        self.objective_control = objective_control
        self.model_base = model_base
        self.wargear: List[Wargear] = []
        self.optional_wargear: List[str] = []

        # Gameplay related attributes
        self._id = str(uuid.uuid4())  # Generate a unique ID for each model
        self.parent_unit = None
        self.is_alive = True
        self.model_height = min(self.model_base.radius) * 2.0  # Assumes typical model height is twice the shortest radius

    @property
    def id(self) -> str:
        """Return the unique ID of the model."""
        return self._id

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
