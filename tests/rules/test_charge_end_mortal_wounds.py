import types
from types import SimpleNamespace

class _MockDatasheet:
    def __init__(self, name, *, unit_comp="1 Test Model", abilities=None, model_wounds=2):
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
                "W": str(model_wounds),
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


def _make_unit(name, *, ability_desc=None, model_count=1, model_wounds=2):
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
    datasheet = _MockDatasheet(
        name,
        unit_comp=f"{model_count} Test Models",
        abilities=abilities,
        model_wounds=model_wounds,
    )
    return Unit(datasheet)


class _MapStub:
    def __init__(self, enemies):
        self._enemies = list(enemies)

    def get_enemy_units(self, _unit):
        return list(self._enemies)

    def is_within_engagement_range(self, _unit, _enemy):
        return True


def test_charge_end_mortal_wounds_per_model(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "Each time this unit ends a Charge move, select one enemy unit within Engagement Range of this unit and roll "
        "one D6 for each model in this unit: for each 4+, that enemy unit suffers D3 mortal wounds."
    )
    unit = _make_unit("Brass Stampede", ability_desc=ability, model_count=3)
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    army = SimpleNamespace(player=SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False))
    enemy_army = SimpleNamespace(player=SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False))
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


def test_charge_end_mortal_wounds_supports_charge_move_wording_without_target_engagement_clause(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "You can re-roll charge rolls made for this unit, and each time this unit makes a Charge move, select one "
        "enemy unit and roll one D6 for each model in this unit that is within Engagement Range of that unit: "
        "for each 4+, that enemy unit suffers D3 mortal wounds."
    )
    unit = _make_unit("Mutilators", ability_desc=ability, model_count=3)
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    army = SimpleNamespace(player=SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False))
    enemy_army = SimpleNamespace(player=SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False))
    unit.set_parent_army(army)
    enemy.set_parent_army(enemy_army)

    unit._refresh_charge_end_mortal_wounds_flags()
    specs = list(getattr(unit, "special_rules", {}).get("charge_end_mortal_wounds", []) or [])
    assert any(str(s.get("kind", "") or "") == "per_model_4plus_d3" for s in specs)
    spec = next(s for s in specs if str(s.get("kind", "") or "") == "per_model_4plus_d3")
    assert bool(spec.get("engagement_only", False))
    assert unit.can_reroll_charge_roll()

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.map = _MapStub([enemy])

    applied = {}

    def _apply(self, target, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    rolls = {"D6": [4, 5], "D3": [2, 1]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    engagement_checks = iter([True, False, True])
    monkeypatch.setattr(
        "warhammer40k_ai.utility.aura_utils.model_within_engagement_range_of_unit",
        lambda *_args, **_kwargs: next(engagement_checks),
    )

    game._on_unit_move_ended_charge_mortal_wounds(unit=unit, action="charge")

    assert applied["amount"] == 3
    assert applied["target"] is enemy


def test_charge_end_mortal_wounds_per_model_flat_one(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "Each time this model's unit ends a Charge move, select one enemy unit within Engagement Range of this model's unit "
        "and roll one D6 for each model in this model's unit that is within Engagement Range of that enemy unit: "
        "for each 4+, that enemy unit suffers 1 mortal wound."
    )
    unit = _make_unit("Head Taker", ability_desc=ability, model_count=3)
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    army = SimpleNamespace(player=SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False))
    enemy_army = SimpleNamespace(player=SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False))
    unit.set_parent_army(army)
    enemy.set_parent_army(enemy_army)

    unit._refresh_charge_end_mortal_wounds_flags()
    specs = list(getattr(unit, "special_rules", {}).get("charge_end_mortal_wounds", []) or [])
    assert any(str(s.get("kind", "") or "") == "per_model_4plus_1" for s in specs)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.map = _MapStub([enemy])

    applied = {}

    def _apply(self, target, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    rolls = {"D6": [4, 2, 6]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_unit_move_ended_charge_mortal_wounds(unit=unit, action="charge")

    assert applied["amount"] == 2
    assert applied["target"] is enemy


def test_charge_end_mortal_wounds_table(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "Each time this model's unit ends a Charge move, select one enemy unit within Engagement Range of this model, "
        "then roll one D6: on a 2-3, that enemy unit suffers 1 mortal wound; on a 4-5, that enemy unit suffers "
        "D3 mortal wounds; on a 6, that enemy unit suffers D3+3 mortal wounds."
    )
    unit = _make_unit("Bloody Stampede", ability_desc=ability, model_count=1)
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    army = SimpleNamespace(player=SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False))
    enemy_army = SimpleNamespace(player=SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False))
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
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command
    from warhammer40k_ai.utility.entity_ids import get_entity_id

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

    unit._refresh_charge_end_mortal_wounds_flags()

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.map = _MapStub([enemy1, enemy2])
    game.players = [player, enemy_player]

    applied = {}

    def _apply(self, target, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)
    rolls = {"D6": [4, 5], "D3": [2, 1]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_unit_move_ended_charge_mortal_wounds(unit=unit, action="charge")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert req.context.get("mortal_wounds_kind") == "charge_end"
    target_id = get_entity_id(enemy1)
    option_id = None
    for opt in list(req.options or []):
        if opt.payload.get("target_unit_id") == target_id:
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, req, option_id, player_id=player.id)

    assert applied["amount"] == 3
    assert applied["target"] is enemy1


def test_charge_end_mortal_wounds_remaining_wounds_max(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "Each time this model ends a Charge move, select one enemy unit within Engagement Range of it and roll one D6 "
        "for each of this model's remaining wounds: for each 4+, that enemy unit suffers 1 mortal wound "
        "(to a maximum of 6 mortal wounds)."
    )
    unit = _make_unit("Wound Stampede", ability_desc=ability, model_count=1, model_wounds=8)
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    army = SimpleNamespace(player=SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False))
    enemy_army = SimpleNamespace(player=SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False))
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

    rolls = {"D6": [4, 5, 6, 3, 4, 4, 5, 6]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_unit_move_ended_charge_mortal_wounds(unit=unit, action="charge")

    assert applied["amount"] == 6
    assert applied["target"] is enemy
