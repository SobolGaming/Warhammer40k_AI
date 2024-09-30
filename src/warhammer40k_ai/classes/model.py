from .wargear import Wargear
import uuid

class Model:
    def __init__(self, name, movement, toughness, save, inv_save, wounds, leadership, objective_control, base_size):        
        self.name = name
        self.movement = movement
        self.toughness = toughness
        self.save = save
        self.inv_save = inv_save
        self.wounds = wounds
        self.leadership = leadership
        self.objective_control = objective_control
        self.base_size = base_size
        self.wargear = []
        self.optional_wargear = []

        self.id = str(uuid.uuid4())  # Generate a unique ID for each model

    def add_wargear(self, wargear: Wargear):
        self.wargear.append(wargear)
    
    def add_optional_wargear(self, wargear: str):
        self.optional_wargear.append(wargear)

    def __str__(self):
        return f"{self.name} (M:{self.movement}\", T:{self.toughness}, Sv:{self.save}+, InvSv:{self.inv_save}+, W:{self.wounds}, Ld:{self.leadership}+, OC:{self.objective_control}\nbase_size:{self.base_size}\nwargear:{self.wargear}\noptional_wargear:{self.optional_wargear}\nid:{self.id})"

    def __repr__(self):
        return f"Model(id='{self.id}', name='{self.name}', M={self.movement}, T={self.toughness}, Sv={self.save}, InvSv={self.inv_save}, W={self.wounds}, Ld={self.leadership}, OC={self.objective_control}\nbase_size={self.base_size}\nwargear={self.wargear}\noptional_wargear={self.optional_wargear}\nid={self.id})"
