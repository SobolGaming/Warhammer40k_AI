from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        objective_control: int = 1,
        cost: int = 100,
    ):
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": cost}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    objective_control: int = 1,
) -> Unit:
    datasheet = MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
        objective_control=objective_control,
    )
    return Unit(datasheet)


def test_inspiring_commander_sets_named_unit_objective_control():
    ability = {
        "name": "INSPIRING COMMANDER",
        "description": (
            "If you include this model in your army, until the end of the battle, "
            "non-CHARACTER models in Assault Intercessors with Jump Packs units from your army "
            "have an Objective Control characteristic of 2 while they are not Battle-shocked."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    army = Army.with_detachment("Space Marines", "Detachment", points_limit=2000)
    source = make_unit("Kayvaan Shrike", abilities=[ability], keywords=["CHARACTER"])
    target = make_unit("Assault Intercessors with Jump Packs", objective_control=1, model_count=2)
    army.add_unit(source)
    army.add_unit(target)

    for model in list(target.models or []):
        assert int(target.get_effective_model_characteristic(model, "objective_control") or 0) == 2


def test_inspiring_commander_supports_multiple_named_target_units():
    ability = {
        "name": "INSPIRING COMMANDER",
        "description": (
            "If you include this model in your army, until the end of the battle, "
            "non-CHARACTER models in Terminator Assault Squad and Terminator Squad units from your army "
            "have an Objective Control characteristic of 2 while they are not Battle-shocked."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    army = Army.with_detachment("Space Marines", "Detachment", points_limit=2000)
    source = make_unit("Darnath Lysander", abilities=[ability], keywords=["CHARACTER"])
    assault = make_unit("Terminator Assault Squad", objective_control=1)
    regular = make_unit("Terminator Squad", objective_control=1)
    other = make_unit("Intercessor Squad", objective_control=1)
    for unit in (source, assault, regular, other):
        army.add_unit(unit)

    assert int(assault.get_effective_model_characteristic(assault.models[0], "objective_control") or 0) == 2
    assert int(regular.get_effective_model_characteristic(regular.models[0], "objective_control") or 0) == 2
    assert int(other.get_effective_model_characteristic(other.models[0], "objective_control") or 0) == 1


def test_inspiring_commander_does_not_apply_to_character_models():
    ability = {
        "name": "INSPIRING COMMANDER",
        "description": (
            "If you include this model in your army, until the end of the battle, "
            "non-CHARACTER models in Sternguard Veteran Squad units from your army "
            "have an Objective Control characteristic of 2 while they are not Battle-shocked."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    army = Army.with_detachment("Space Marines", "Detachment", points_limit=2000)
    source = make_unit("Pedro Kantor", abilities=[ability], keywords=["CHARACTER"])
    target = make_unit("Sternguard Veteran Squad", keywords=["CHARACTER"], objective_control=1)
    army.add_unit(source)
    army.add_unit(target)

    assert int(target.get_effective_model_characteristic(target.models[0], "objective_control") or 0) == 1


def test_inspiring_commander_stops_when_target_is_battle_shocked():
    ability = {
        "name": "INSPIRING COMMANDER",
        "description": (
            "If you include this model in your army, until the end of the battle, "
            "non-CHARACTER models in Outrider Squad units from your army "
            "have an Objective Control characteristic of 3 while they are not Battle-shocked."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    army = Army.with_detachment("Space Marines", "Detachment", points_limit=2000)
    source = make_unit("Kor'sarro Khan", abilities=[ability], keywords=["CHARACTER"])
    target = make_unit("Outrider Squad", objective_control=1)
    army.add_unit(source)
    army.add_unit(target)

    target.status_effects.append(BattleShockEffect())

    assert int(target.get_effective_model_characteristic(target.models[0], "objective_control") or 0) == 1
