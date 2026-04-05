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
    from warhammer40k_ai.units.unit import Unit

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


def _setup_players(unit, enemies):
    player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"))
    player.has_control = lambda: False
    enemy_player = SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"))
    enemy_player.has_control = lambda: False
    army = SimpleNamespace(player=player, units=[unit])
    enemy_army = SimpleNamespace(player=enemy_player, units=list(enemies))
    player.army = army
    enemy_player.army = enemy_army
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army
    unit.set_parent_army(army)
    for enemy in enemies:
        enemy.set_parent_army(enemy_army)
    return player, enemy_player


def _set_ids(unit, unit_id, model_id):
    unit._id = unit_id
    if unit.models:
        unit.models[0]._id = model_id


def test_movement_phase_end_mortal_table_applies(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "At the end of your Movement phase, roll one D6 for each enemy unit within 6\" of this model: "
        "on a 2-3, that unit suffers 1 mortal wound; on a 4-5, that unit suffers D3 mortal wounds; "
        "on a 6, that unit suffers D6 mortal wounds."
    )
    unit = _make_unit("Mortalizer", ability_desc=ability, model_count=1)
    enemy1 = _make_unit("Enemy One")
    enemy2 = _make_unit("Enemy Two")
    enemy3 = _make_unit("Enemy Three")
    unit.deployed = True
    enemy1.deployed = True
    enemy2.deployed = True
    enemy3.deployed = True
    unit.reserve_status = "deployed"
    enemy1.reserve_status = "deployed"
    enemy2.reserve_status = "deployed"
    enemy3.reserve_status = "deployed"

    _set_ids(unit, "U1", "U1M1")
    _set_ids(enemy1, "E1", "E1M1")
    _set_ids(enemy2, "E2", "E2M1")
    _set_ids(enemy3, "E3", "E3M1")

    unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy1.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    enemy2.models[0].set_location(5.5, 0.0, 0.0, 0.0)
    enemy3.models[0].set_location(6.0, 0.0, 0.0, 0.0)

    player, enemy_player = _setup_players(unit, [enemy1, enemy2, enemy3])

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied[target_unit._id] = applied.get(target_unit._id, 0) + int(amount or 0)
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    rolls = {"D6": [2, 4, 6, 5], "D3": [2]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_phase_end_movement_phase_mortal_table(player=player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))

    assert applied["E1"] == 1
    assert applied["E2"] == 2
    assert applied["E3"] == 5


def test_movement_phase_end_mortal_table_battleshock(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "At the end of your Movement phase, roll one D6 for each enemy unit within 6\" of this model: "
        "on a 2-3, that unit suffers 1 mortal wound; on a 4-5, that unit suffers D3 mortal wounds; "
        "on a 6, that unit suffers D6 mortal wounds. Each enemy unit within range of this ability must then "
        "take a Battle-shock test."
    )
    unit = _make_unit("Mortalizer", ability_desc=ability, model_count=1)
    enemy1 = _make_unit("Enemy One")
    enemy2 = _make_unit("Enemy Two")
    unit.deployed = True
    enemy1.deployed = True
    enemy2.deployed = True
    unit.reserve_status = "deployed"
    enemy1.reserve_status = "deployed"
    enemy2.reserve_status = "deployed"

    _set_ids(unit, "U1", "U1M1")
    _set_ids(enemy1, "E1", "E1M1")
    _set_ids(enemy2, "E2", "E2M1")

    unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy1.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    enemy2.models[0].set_location(5.5, 0.0, 0.0, 0.0)

    player, enemy_player = _setup_players(unit, [enemy1, enemy2])

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]

    calls = []

    def _take(self, current_turn=1):
        calls.append((self._id, int(current_turn)))

    enemy1.take_battle_shock_test = types.MethodType(_take, enemy1)
    enemy2.take_battle_shock_test = types.MethodType(_take, enemy2)

    rolls = {"D6": [1, 1]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_phase_end_movement_phase_mortal_table(player=player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))

    assert {c[0] for c in calls} == {"E1", "E2"}


def test_movement_phase_end_mortal_threshold_on_3plus(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "At the end of your Movement phase, roll one D6 for each enemy unit within 9\" of one or more models with this ability: "
        "on a 3+, that enemy unit suffers D3 mortal wounds."
    )
    unit = _make_unit("Storm Caller", ability_desc=ability, model_count=2)
    enemy1 = _make_unit("Enemy One")
    enemy2 = _make_unit("Enemy Two")
    unit.deployed = True
    enemy1.deployed = True
    enemy2.deployed = True
    unit.reserve_status = "deployed"
    enemy1.reserve_status = "deployed"
    enemy2.reserve_status = "deployed"

    _set_ids(unit, "U1", "U1M1")
    if len(unit.models) > 1:
        unit.models[1]._id = "U1M2"
    _set_ids(enemy1, "E1", "E1M1")
    _set_ids(enemy2, "E2", "E2M1")

    unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    if len(unit.models) > 1:
        unit.models[1].set_location(1.0, 0.0, 0.0, 0.0)
    enemy1.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    enemy2.models[0].set_location(12.0, 0.0, 0.0, 0.0)

    player, enemy_player = _setup_players(unit, [enemy1, enemy2])

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied[target_unit._id] = applied.get(target_unit._id, 0) + int(amount or 0)
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    rolls = {"D6": [3], "D3": [2]}

    def _fake_get_roll(die):
        assert rolls[die], f"Unexpected extra roll for {die}"
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_phase_end_movement_phase_mortal_table(player=player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))

    assert applied["E1"] == 2
    assert "E2" not in applied
