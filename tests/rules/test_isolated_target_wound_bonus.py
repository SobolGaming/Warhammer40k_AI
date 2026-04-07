from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.roster.army import Army


class MockDatasheet:
    def __init__(
        self,
        name: str,
        movement=6,
        model_count=1,
        base_size="32mm",
        save="4",
        *,
        datasheet_id: str | None = None,
        abilities=None,
    ):
        self.name = name
        self.id = datasheet_id or name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [
            {"description": f"{model_count} Test Models"}
        ]
        self.datasheets_models_cost = [
            {"description": f"{model_count} models", "cost": 100}
        ]
        self.datasheets_models = [{
            "M": str(movement), "T": "4", "Sv": str(save), "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none"
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = []
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing"


def create_unit(
    name: str,
    x: float,
    y: float,
    faction: str,
    *,
    abilities=None,
) -> Unit:
    ds = MockDatasheet(
        name,
        abilities=abilities,
    )
    unit = Unit(ds)
    for i, m in enumerate(unit.models):
        m.set_location(x + (i * 1.5), y, 0.0, 0.0)
    unit.deployed = True
    unit.faction = faction
    return unit


def attach_to_armies(game_map: Map, units_a, units_b):
    army_a = Army.with_detachment("Army A", "Detachment A")
    army_b = Army.with_detachment("Army B", "Detachment B")
    for u in units_a:
        army_a.add_unit(u)
    for u in units_b:
        army_b.add_unit(u)
    game_map.units = units_a + units_b
    return army_a, army_b


def test_isolated_target_wound_bonus_applies_when_no_other_enemy_within_6():
    ability_text = (
        "Each time this model makes an attack that targets an enemy unit, "
        "if there are no other units from your opponent's army within 6\" of that target, "
        "add 1 to the Wound roll."
    )
    abilities = [{
        "name": "Isolated Hunter",
        "description": ability_text,
        "type": "Ability",
        "parameter": "",
    }]

    game_map = Map(width=48, height=72)
    attacker = create_unit("Attacker", 10.0, 10.0, faction="A", abilities=abilities)
    target = create_unit("Target", 20.0, 10.0, faction="B")
    other_enemy = create_unit("Other", 40.0, 10.0, faction="B")

    army_a, army_b = attach_to_armies(game_map, [attacker], [target, other_enemy])
    game = SimpleNamespace(map=game_map)
    army_a.player = SimpleNamespace(game=game, name="P1", id="P1")
    army_b.player = SimpleNamespace(game=game, name="P2", id="P2")

    mods = attacker.model_attack_roll_modifiers_vs_weakened_target(
        attacker.models[0],
        attack_type="ranged",
        target=target,
    )

    assert mods.get("wound") == 1
    assert "isolated targets" in " ".join(mods.get("wound_reasons", ()))


def test_isolated_target_wound_bonus_does_not_apply_with_enemy_within_6():
    ability_text = (
        "Each time this model makes an attack that targets an enemy unit, "
        "if there are no other units from your opponent's army within 6\" of that target, "
        "add 1 to the Wound roll."
    )
    abilities = [{
        "name": "Isolated Hunter",
        "description": ability_text,
        "type": "Ability",
        "parameter": "",
    }]

    game_map = Map(width=48, height=72)
    attacker = create_unit("Attacker", 10.0, 10.0, faction="A", abilities=abilities)
    target = create_unit("Target", 20.0, 10.0, faction="B")
    other_enemy = create_unit("Other", 24.0, 10.0, faction="B")

    army_a, army_b = attach_to_armies(game_map, [attacker], [target, other_enemy])
    game = SimpleNamespace(map=game_map)
    army_a.player = SimpleNamespace(game=game, name="P1", id="P1")
    army_b.player = SimpleNamespace(game=game, name="P2", id="P2")

    mods = attacker.model_attack_roll_modifiers_vs_weakened_target(
        attacker.models[0],
        attack_type="ranged",
        target=target,
    )

    assert mods.get("wound") == 0
