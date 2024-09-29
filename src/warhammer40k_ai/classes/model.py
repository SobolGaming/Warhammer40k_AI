from .wargear import Wargear

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

    def add_wargear(self, wargear: Wargear):
        self.wargear.append(wargear)

    def __str__(self):
        return f"{self.name} (M:{self.movement}\", T:{self.toughness}, Sv:{self.save}+, InvSv:{self.inv_save}+, W:{self.wounds}, Ld:{self.leadership}+, OC:{self.objective_control}, base_size:{self.base_size}, wargear:{self.wargear})"

    def __repr__(self):
        return f"Model(name='{self.name}', M={self.movement}, T={self.toughness}, Sv={self.save}, InvSv={self.inv_save}, W={self.wounds}, Ld={self.leadership}, OC={self.objective_control}, base_size={self.base_size}, wargear={self.wargear})"
