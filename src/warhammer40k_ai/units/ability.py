from typing import Optional

class Ability:
    def __init__(
        self,
        name: str,
        faction_id: str,
        description: str,
        type: str,
        parameter: Optional[str] = None,
        legend: Optional[str] = None
    ):
        self.name = name
        self.faction_id = faction_id
        self.description = description
        self.type = type
        self.parameter = parameter
        self.legend = legend

    def __str__(self):
        return f"{self.name} ({self.type}) {self.description}"

    def __repr__(self):
        return f"Ability(name='{self.name}', faction_id='{self.faction_id}', type='{self.type}', parameter='{self.parameter}', legend='{self.legend}', description='{self.description}')"
