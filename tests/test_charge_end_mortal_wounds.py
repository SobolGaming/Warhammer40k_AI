import types
from types import SimpleNamespace

class _MockDatasheet:
    def __init__(self, name, *, unit_comp="1 Test Model", abilities=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "World Eaters"}
        self.keywords = []
        self.faction_keywords = ["WORLD EATERS"]
        self.datasheets_unit_composition = [{"description": unit_comp}]
        self.datasheets_models_cost = [{"description": unit_comp, "cost": 100}]
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


def _make_unit(name, *, ability_desc=None, model_count=1):
    from warhammer40k_ai.classes.unit import Unit

    abilities = []
    if ability_desc:
        abilities.append(
            {
                "name": name,
                "description": ability_desc,
                "type": "Datasheet",
                "parameter": "",
            }
        )
    datasheet = _MockDatasheet(name, unit_comp=f"{model_count} Test Models", abilities=abilities)
    return Unit(datasheet)


class _MapStub:
    def __init__(self, enemies):
        self._enemies = list(enemies)

    def get_enemy_units(self, _unit):
        return list(self._enemies)

    def is_within_engagement_range(self, _unit, _enemy):
        return True


def test_charge_end_mortal_wounds_per_model(monkeypatch):
    from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game

    ability = (
        "Each time this unit ends a Charge move, select one enemy unit within Engagement Range of this unit and roll "
        "one D6 for each model in this unit: for each 4+, that enemy unit suffers D3 mortal wounds."
    )
    unit = _make_unit("Brass Stampede", ability_desc=ability, model_count=3)
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    army = SimpleNamespace(player=SimpleNamespace(name="P1", type=SimpleNamespace(name="AI")))
    enemy_army = SimpleNamespace(player=SimpleNamespace(name="P2", type=SimpleNamespace(name="AI")))
    unit.set_parent_army(army)
    enemy.set_parent_army(enemy_army)

    unit._refresh_charge_end_mortal_wounds_flags()

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.map = _MapStub([enemy])

    applied = {}

    def _apply(self, target, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    rolls = {"D6": [4, 3, 6], "D3": [2, 3]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_unit_move_ended_charge_mortal_wounds(unit=unit, action="charge")

    assert applied["amount"] == 5
    assert applied["target"] is enemy


def test_charge_end_mortal_wounds_table(monkeypatch):
    from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game

    ability = (
        "Each time this model's unit ends a Charge move, select one enemy unit within Engagement Range of this model, "
        "then roll one D6: on a 2-3, that enemy unit suffers 1 mortal wound; on a 4-5, that enemy unit suffers "
        "D3 mortal wounds; on a 6, that enemy unit suffers D3+3 mortal wounds."
    )
    unit = _make_unit("Bloody Stampede", ability_desc=ability, model_count=1)
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    army = SimpleNamespace(player=SimpleNamespace(name="P1", type=SimpleNamespace(name="AI")))
    enemy_army = SimpleNamespace(player=SimpleNamespace(name="P2", type=SimpleNamespace(name="AI")))
    unit.set_parent_army(army)
    enemy.set_parent_army(enemy_army)

    unit._refresh_charge_end_mortal_wounds_flags()

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.map = _MapStub([enemy])

    applied = {}

    def _apply(self, target, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    rolls = {"D6": [6], "D3": [2]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_unit_move_ended_charge_mortal_wounds(unit=unit, action="charge")

    assert applied["amount"] == 5
    assert applied["target"] is enemy


def test_charge_end_mortal_wounds_prompts_for_human(monkeypatch):
    from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game

    ability = (
        "Each time this unit ends a Charge move, select one enemy unit within Engagement Range of this unit and roll "
        "one D6 for each model in this unit: for each 4+, that enemy unit suffers D3 mortal wounds."
    )
    unit = _make_unit("Brass Stampede", ability_desc=ability, model_count=2)
    enemy1 = _make_unit("Enemy One")
    enemy2 = _make_unit("Enemy Two")
    unit.deployed = True
    enemy1.deployed = True
    enemy2.deployed = True

    army = SimpleNamespace(player=SimpleNamespace(name="P1", type=SimpleNamespace(name="HUMAN")))
    enemy_army = SimpleNamespace(player=SimpleNamespace(name="P2", type=SimpleNamespace(name="AI")))
    unit.set_parent_army(army)
    enemy1.set_parent_army(enemy_army)
    enemy2.set_parent_army(enemy_army)

    unit._refresh_charge_end_mortal_wounds_flags()

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.map = _MapStub([enemy1, enemy2])

    published = {}

    def _fake_publish(event_name, **kwargs):
        published["event"] = event_name
        published["kwargs"] = kwargs

    monkeypatch.setattr(game.event_system, "publish", _fake_publish)

    game._on_unit_move_ended_charge_mortal_wounds(unit=unit, action="charge")

    assert published.get("event") == "charge_mortal_wounds_prompt"
    assert len(published["kwargs"]["candidates"]) == 2
    assert callable(published["kwargs"].get("on_select"))
