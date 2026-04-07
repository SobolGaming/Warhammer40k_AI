from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
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
        self.attached_to = []


def _make_unit(name: str, *, abilities=None) -> Unit:
    return Unit(_MockDatasheet(name, abilities=abilities))


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army_a = Army.with_detachment("Army A", "Detachment A")
    army_a.faction_id = "CSM"
    army_b = Army.with_detachment("Army B", "Detachment B")
    army_b.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.LOCAL, army=army_a)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army_b)
    game.add_player(p1)
    game.add_player(p2)
    return game, p1, p2


def test_trophy_takers_spec_parses_as_first_time_unit_destroyed_oc_bonus():
    ability = {
        "name": "Trophy Takers",
        "description": (
            "The first time this unit destroys an enemy unit, until the end of the battle, while this unit is not "
            "Battle-shocked, add 1 to the Objective Control characteristic of models in this unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit("Red Corsairs Raiders", abilities=[ability])

    specs = [s for s in unit.get_kill_reward_specs() if s.get("type") == "objective_control_bonus_on_destroy"]
    assert len(specs) == 1
    spec = specs[0]
    assert spec.get("trigger") == "unit_destroyed"
    assert int(spec.get("objective_control_bonus", 0) or 0) == 1
    assert bool(spec.get("requires_not_battle_shocked", False)) is True
    assert bool(spec.get("first_time", False)) is True


def test_trophy_takers_applies_once_and_is_suppressed_while_battle_shocked():
    game, p1, p2 = _build_game()
    ability = {
        "name": "Trophy Takers",
        "description": (
            "The first time this unit destroys an enemy unit, until the end of the battle, while this unit is not "
            "Battle-shocked, add 1 to the Objective Control characteristic of models in this unit."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    attacker = _make_unit("Red Corsairs Raiders", abilities=[ability])
    enemy_one = _make_unit("Enemy One")
    enemy_two = _make_unit("Enemy Two")

    p1.army.add_unit(attacker)
    p2.army.add_unit(enemy_one)
    p2.army.add_unit(enemy_two)

    model = attacker.models[0]
    assert int(attacker.get_effective_model_characteristic(model, "objective_control") or 0) == 1

    game._on_unit_destroyed_rules(
        unit=enemy_one,
        destroyed_by_unit=attacker,
        destroyed_by_model=model,
    )
    assert int(attacker.get_effective_model_characteristic(model, "objective_control") or 0) == 2

    attacker.status_effects = [BattleShockEffect()]
    assert int(attacker.get_effective_model_characteristic(model, "objective_control") or 0) == 1

    attacker.status_effects = []
    assert int(attacker.get_effective_model_characteristic(model, "objective_control") or 0) == 2

    game._on_unit_destroyed_rules(
        unit=enemy_two,
        destroyed_by_unit=attacker,
        destroyed_by_model=model,
    )
    assert int(attacker.get_effective_model_characteristic(model, "objective_control") or 0) == 2
