from warhammer40k_ai.classes.map import Map
from warhammer40k_ai.classes.unit import Unit


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, model_count=1):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        label = "Test Model" if model_count == 1 else "Test Models"
        self.datasheets_unit_composition = [{"description": f"{model_count} {label}"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name, *, abilities=None, quantity=1):
    return Unit(_MockDatasheet(name, abilities=abilities, model_count=quantity), quantity=quantity)


def test_fight_within_3_parses_and_expands_eligible_models():
    ability = {
        "name": "Fight Within 3",
        "description": (
            "Each time this model's unit is selected to fight, you can use this ability. "
            "When determining which models in this unit are eligible to fight, any models "
            "in it that are within 3\" of one or more enemy models are eligible to fight. "
            "When resolving those attacks, such models can target one of those enemy units "
            "that is within 3\" of them and within Engagement Range of their unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }

    unit = _make_unit("Testers", abilities=[ability], quantity=2)
    enemy = _make_unit("Enemy", quantity=1)
    game_map = Map(width=60, height=44)

    unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    unit.models[1].set_location(4.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(1.5, 0.0, 0.0, 0.0)

    assert unit.has_fight_within_3_ability() is True

    base_eligible = unit.get_fight_eligible_models_for_target(
        enemy,
        game_map=game_map,
        allow_within_3=False,
    )
    expanded_eligible = unit.get_fight_eligible_models_for_target(
        enemy,
        game_map=game_map,
        allow_within_3=True,
    )

    assert unit.models[0] in base_eligible
    assert unit.models[1] not in base_eligible
    assert unit.models[0] in expanded_eligible
    assert unit.models[1] in expanded_eligible
