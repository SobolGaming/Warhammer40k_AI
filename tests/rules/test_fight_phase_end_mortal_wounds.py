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


class _MapStub:
    def __init__(self, enemies):
        self._enemies = list(enemies)

    def get_enemy_units(self, _unit):
        return list(self._enemies)


def _set_ids(unit, unit_id, model_id):
    unit._id = unit_id
    if unit.models:
        unit.models[0]._id = model_id


def test_fight_phase_end_mortal_wounds_ai(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = (
        "At the end of the Fight phase, you can select one enemy unit within Engagement Range of this model "
        "and roll eight D6: for each 4+, that enemy unit suffers 1 mortal wound."
    )
    unit = _make_unit("Mortalizer", ability_desc=ability, model_count=1)
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
    enemy_player = SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
    army = SimpleNamespace(player=player, units=[unit])
    enemy_army = SimpleNamespace(player=enemy_player, units=[enemy])
    player.army = army
    enemy_player.army = enemy_army
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army

    unit.set_parent_army(army)
    enemy.set_parent_army(enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]
    game.map = _MapStub([enemy])

    applied = {}

    def _apply(self, target, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    rolls = {"D6": [1, 4, 5, 6, 2, 3, 4, 4]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_phase_end_fight_phase_mortal_wounds(phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert req.context.get("mortal_wounds_kind") == "fight_phase_end"
    target_id = get_entity_id(enemy)
    option_id = None
    for opt in list(req.options or []):
        if opt.payload.get("target_unit_id") == target_id:
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, req, option_id, player_id=player.id)

    assert applied["amount"] == 5
    assert applied["target"] is enemy


def test_fight_phase_end_mortal_wounds_prompts_human(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY

    ability = (
        "At the end of the Fight phase, you can select one enemy unit within Engagement Range of this model "
        "and roll eight D6: for each 4+, that enemy unit suffers 1 mortal wound."
    )
    unit = _make_unit("Mortalizer", ability_desc=ability, model_count=1)
    enemy1 = _make_unit("Enemy One")
    enemy2 = _make_unit("Enemy Two")
    unit.deployed = True
    enemy1.deployed = True
    enemy2.deployed = True

    player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True)
    enemy_player = SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
    army = SimpleNamespace(player=player, units=[unit])
    enemy_army = SimpleNamespace(player=enemy_player, units=[enemy1, enemy2])
    player.army = army
    enemy_player.army = enemy_army
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army

    unit.set_parent_army(army)
    enemy1.set_parent_army(enemy_army)
    enemy2.set_parent_army(enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]
    game.map = _MapStub([enemy1, enemy2])

    game._on_phase_end_fight_phase_mortal_wounds(phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert req.context.get("mortal_wounds_kind") == "fight_phase_end"
    assert len(req.options) == 3


def test_fight_phase_end_enemy_within_range_mortal_threshold_applies(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "At the end of the Fight phase, roll one D6 for each enemy unit within 6\" of this model: "
        "on a 4+, that enemy unit suffers D3 mortal wounds."
    )
    unit = _make_unit("Aura Mortalizer", ability_desc=ability, model_count=1)
    enemy1 = _make_unit("Enemy One")
    enemy2 = _make_unit("Enemy Two")
    enemy3 = _make_unit("Enemy Three")
    unit.deployed = True
    enemy1.deployed = True
    enemy2.deployed = True
    enemy3.deployed = True

    _set_ids(unit, "U1", "U1M1")
    _set_ids(enemy1, "E1", "E1M1")
    _set_ids(enemy2, "E2", "E2M1")
    _set_ids(enemy3, "E3", "E3M1")

    unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy1.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    enemy2.models[0].set_location(5.5, 0.0, 0.0, 0.0)
    enemy3.models[0].set_location(9.0, 0.0, 0.0, 0.0)

    player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
    enemy_player = SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
    army = SimpleNamespace(player=player, units=[unit])
    enemy_army = SimpleNamespace(player=enemy_player, units=[enemy1, enemy2, enemy3])
    player.army = army
    enemy_player.army = enemy_army
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army

    unit.set_parent_army(army)
    enemy1.set_parent_army(enemy_army)
    enemy2.set_parent_army(enemy_army)
    enemy3.set_parent_army(enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]
    game.map = _MapStub([enemy1, enemy2, enemy3])

    applied = {}

    def _apply(self, target, amount, game_map=None):
        applied[target._id] = applied.get(target._id, 0) + int(amount or 0)
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    rolls = {"D6": [4, 3], "D3": [2]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_phase_end_fight_phase_mortal_wounds(phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = list(game.decision_queue.list() or [])
    assert pending == []
    assert applied["E1"] == 2
    assert "E2" not in applied
    assert "E3" not in applied
