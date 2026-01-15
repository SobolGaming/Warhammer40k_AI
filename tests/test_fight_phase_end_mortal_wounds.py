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


def test_fight_phase_end_mortal_wounds_ai(monkeypatch):
    from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game

    ability = (
        "At the end of the Fight phase, you can select one enemy unit within Engagement Range of this model "
        "and roll eight D6: for each 4+, that enemy unit suffers 1 mortal wound."
    )
    unit = _make_unit("Mortalizer", ability_desc=ability, model_count=1)
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    player = SimpleNamespace(name="P1", type=SimpleNamespace(name="AI"))
    enemy_player = SimpleNamespace(name="P2", type=SimpleNamespace(name="AI"))
    army = SimpleNamespace(player=player, units=[unit])
    enemy_army = SimpleNamespace(player=enemy_player, units=[enemy])
    player.army = army
    enemy_player.army = enemy_army

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
    player._should_use_optional_ability = lambda *_a, **_k: True

    game._on_phase_end_fight_phase_mortal_wounds(phase=SimpleNamespace(name="FIGHT_PHASE"))

    assert applied["amount"] == 5
    assert applied["target"] is enemy


def test_fight_phase_end_mortal_wounds_prompts_human(monkeypatch):
    from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game

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

    player = SimpleNamespace(name="P1", type=SimpleNamespace(name="HUMAN"))
    enemy_player = SimpleNamespace(name="P2", type=SimpleNamespace(name="AI"))
    army = SimpleNamespace(player=player, units=[unit])
    enemy_army = SimpleNamespace(player=enemy_player, units=[enemy1, enemy2])
    player.army = army
    enemy_player.army = enemy_army

    unit.set_parent_army(army)
    enemy1.set_parent_army(enemy_army)
    enemy2.set_parent_army(enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]
    game.map = _MapStub([enemy1, enemy2])

    published = {}

    def _fake_publish(event_name, **kwargs):
        published["event"] = event_name
        published["kwargs"] = kwargs

    monkeypatch.setattr(game.event_system, "publish", _fake_publish)

    game._on_phase_end_fight_phase_mortal_wounds(phase=SimpleNamespace(name="FIGHT_PHASE"))

    assert published.get("event") == "fight_phase_end_mortal_wounds_prompt"
    assert len(published["kwargs"]["candidates"]) == 2
    assert callable(published["kwargs"].get("on_select"))
