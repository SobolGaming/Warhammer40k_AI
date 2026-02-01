import types
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(self, name, *, unit_comp="1 Test Model", abilities=None, keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "World Eaters"}
        self.keywords = list(keywords or [])
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


def _make_unit(name, *, ability_desc=None, model_count=1, keywords=None):
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
    datasheet = _MockDatasheet(name, unit_comp=f"{model_count} Test Models", abilities=abilities, keywords=keywords)
    return Unit(datasheet)


class _MapStub:
    def __init__(self, units, enemies):
        self.units = list(units)
        self._enemies = list(enemies)

    def get_enemy_units(self, _unit):
        return list(self._enemies)


def _setup_players(unit, enemies, *, human=False):
    player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL" if human else "REMOTE"))
    player.has_control = (lambda: True) if human else (lambda: False)
    enemy_player = SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
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


def _resolve_optional_reroll(game, player_id):
    from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_DICE_REROLL
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command

    pending = list(game.decision_queue.list() or [])
    for req in pending:
        if req.decision_type != DECISION_SELECT_DICE_REROLL:
            continue
        option_id = None
        for opt in list(req.options or []):
            if opt.payload.get("action_id") == "none":
                option_id = opt.option_id
                break
        if option_id is None and req.options:
            option_id = req.options[0].option_id
        if option_id is not None:
            resolve_decision_command(game, req, option_id, player_id=player_id)
        break


def test_move_over_mortal_wounds_ai(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_REQUEST_DICE_ROLL
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = (
        "Each time this model ends a Normal or Advance move, you can select one enemy unit that it moved over during "
        "that move and roll six D6: for each 4+, that enemy unit suffers 1 mortal wound."
    )
    unit = _make_unit("Skimmer", ability_desc=ability, model_count=1, keywords=["Fly"])
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    player, enemy_player = _setup_players(unit, [enemy], human=False)

    mover = unit.models[0]
    target = enemy.models[0]
    mover.set_location(0.0, 0.0, 0.0, 0.0)
    target.set_location(5.0, 0.0, 0.0, 0.0)
    mover.last_move_path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.auto_resolve_dice_rolls = False
    game.players = [player, enemy_player]
    game.map = _MapStub([unit, enemy], [enemy])

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target_unit
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    rolls = {"D6": [4, 2, 5, 6, 1, 3]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game._on_unit_move_ended_move_over_mortal_wounds(unit=unit, action="move")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert req.context.get("mortal_wounds_kind") == "move_over"
    target_id = get_entity_id(enemy)
    option_id = None
    for opt in list(req.options or []):
        if opt.payload.get("target_unit_id") == target_id:
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, req, option_id, player_id=player.id)

    roll_requests = [r for r in list(game.decision_queue.list() or []) if r.decision_type == DECISION_REQUEST_DICE_ROLL]
    assert len(roll_requests) == 1
    roll_req = roll_requests[0]
    roll_id = roll_req.context.get("roll_id")
    assert roll_id is not None
    state = game.roll_manager.get_roll(int(roll_id))
    state.spec["fixed_dice"] = [4, 2, 5, 6, 1, 3]
    resolve_decision_command(game, roll_req, roll_req.options[0].option_id, player_id=player.id)
    _resolve_optional_reroll(game, player.id)

    assert applied["amount"] == 3
    assert applied["target"] is enemy


def test_move_over_mortal_wounds_human_prompts(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY

    ability = (
        "Each time this model ends a Normal or Advance move, you can select one enemy unit that it moved over during "
        "that move and roll six D6: for each 4+, that enemy unit suffers 1 mortal wound."
    )
    unit = _make_unit("Skimmer", ability_desc=ability, model_count=1, keywords=["Fly"])
    enemy1 = _make_unit("Enemy One")
    enemy2 = _make_unit("Enemy Two")
    unit.deployed = True
    enemy1.deployed = True
    enemy2.deployed = True

    player, enemy_player = _setup_players(unit, [enemy1, enemy2], human=True)

    mover = unit.models[0]
    mover.set_location(0.0, 0.0, 0.0, 0.0)
    enemy1.models[0].set_location(4.0, 0.0, 0.0, 0.0)
    enemy2.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    mover.last_move_path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.auto_resolve_dice_rolls = False
    game.players = [player, enemy_player]
    game.map = _MapStub([unit, enemy1, enemy2], [enemy1, enemy2])

    game._on_unit_move_ended_move_over_mortal_wounds(unit=unit, action="move")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert req.context.get("mortal_wounds_kind") == "move_over"
    assert len(req.options) == 3


def test_move_over_mortal_wounds_vertical_move_does_not_trigger(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "Each time this model ends a Normal or Advance move, you can select one enemy unit that it moved over during "
        "that move and roll six D6: for each 4+, that enemy unit suffers 1 mortal wound."
    )
    unit = _make_unit("Skimmer", ability_desc=ability, model_count=1, keywords=["Fly"])
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    player, enemy_player = _setup_players(unit, [enemy], human=False)

    mover = unit.models[0]
    target = enemy.models[0]
    mover.set_location(0.0, 0.0, 5.0, 0.0)
    target.set_location(5.0, 0.0, 0.0, 0.0)
    mover.last_move_path = [(0.0, 0.0, 5.0), (10.0, 0.0, 5.0)]

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.auto_resolve_dice_rolls = False
    game.players = [player, enemy_player]
    game.map = _MapStub([unit, enemy], [enemy])

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target_unit
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    game._on_unit_move_ended_move_over_mortal_wounds(unit=unit, action="move")

    assert applied == {}
    assert not list(game.decision_queue.list() or [])


def test_move_over_mortal_wounds_requires_fly(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability = (
        "Each time this model ends a Normal or Advance move, you can select one enemy unit that it moved over during "
        "that move and roll six D6: for each 4+, that enemy unit suffers 1 mortal wound."
    )
    unit = _make_unit("Walker", ability_desc=ability, model_count=1, keywords=[])
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    player, enemy_player = _setup_players(unit, [enemy], human=False)

    mover = unit.models[0]
    target = enemy.models[0]
    mover.set_location(0.0, 0.0, 0.0, 0.0)
    target.set_location(5.0, 0.0, 0.0, 0.0)
    mover.last_move_path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.auto_resolve_dice_rolls = False
    game.players = [player, enemy_player]
    game.map = _MapStub([unit, enemy], [enemy])

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target_unit
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    game._on_unit_move_ended_move_over_mortal_wounds(unit=unit, action="move")

    assert applied == {}
    assert not list(game.decision_queue.list() or [])


def test_move_over_mortal_wounds_fly_bonus_d3(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_REQUEST_DICE_ROLL
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = (
        "Each time this model ends a Normal move, you can select one enemy unit that it moved over during that move "
        "and roll two D6, adding 1 to each result if that enemy unit can FLY: for each 4+, that enemy unit suffers "
        "D3 mortal wounds."
    )
    unit = _make_unit("Heldrake", ability_desc=ability, model_count=1, keywords=["Fly"])
    enemy = _make_unit("Enemy", keywords=["Fly"])
    unit.deployed = True
    enemy.deployed = True

    player, enemy_player = _setup_players(unit, [enemy], human=False)

    mover = unit.models[0]
    target = enemy.models[0]
    mover.set_location(0.0, 0.0, 0.0, 0.0)
    target.set_location(5.0, 0.0, 0.0, 0.0)
    mover.last_move_path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.auto_resolve_dice_rolls = False
    game.players = [player, enemy_player]
    game.map = _MapStub([unit, enemy], [enemy])

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target_unit
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    game._on_unit_move_ended_move_over_mortal_wounds(unit=unit, action="move")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert req.context.get("mortal_wounds_kind") == "move_over"
    target_id = get_entity_id(enemy)
    option_id = None
    for opt in list(req.options or []):
        if opt.payload.get("target_unit_id") == target_id:
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, req, option_id, player_id=player.id)

    roll_requests = [r for r in list(game.decision_queue.list() or []) if r.decision_type == DECISION_REQUEST_DICE_ROLL]
    assert len(roll_requests) == 1
    roll_req = roll_requests[0]
    roll_id = roll_req.context.get("roll_id")
    assert roll_id is not None
    state = game.roll_manager.get_roll(int(roll_id))
    state.spec["fixed_dice"] = [3, 2]

    rolls = {"D3": [2]}

    def _fake_get_roll(die):
        return rolls[die].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    resolve_decision_command(game, roll_req, roll_req.options[0].option_id, player_id=player.id)
    _resolve_optional_reroll(game, player.id)

    assert applied["amount"] == 2
    assert applied["target"] is enemy


def test_move_over_mortal_wounds_unit_level_and_reroll_rule():
    from types import SimpleNamespace

    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_REQUEST_DICE_ROLL
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = (
        "Each time this unit ends a Normal move, you can select one enemy unit that it moved over during that move "
        "and roll one D6 for each model in this unit: for each 4+, that enemy unit suffers 1 mortal wound."
    )
    unit = _make_unit("Jetbikes", ability_desc=ability, model_count=3, keywords=["Fly"])
    enemy = _make_unit("Enemy")
    unit.deployed = True
    enemy.deployed = True

    # Add Cluster Caltrops to one model (reroll one die).
    caltrops = SimpleNamespace(
        name="Cluster Caltrops",
        description="Each time you roll a D6 for the bearer while resolving this unit's Eviscerating Fly-by ability, you can re-roll the result.",
        type="Datasheet",
        parameter="",
    )
    unit.models[0].abilities = {"Cluster Caltrops": caltrops}

    player, enemy_player = _setup_players(unit, [enemy], human=False)

    for m in unit.models:
        m.set_location(0.0, 0.0, 0.0, 0.0)
        m.last_move_path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
    enemy.models[0].set_location(5.0, 0.0, 0.0, 0.0)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.auto_resolve_dice_rolls = False
    game.players = [player, enemy_player]
    game.map = _MapStub([unit, enemy], [enemy])

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target_unit
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)

    game._on_unit_move_ended_move_over_mortal_wounds(unit=unit, action="move")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    target_id = get_entity_id(enemy)
    option_id = None
    for opt in list(req.options or []):
        if opt.payload.get("target_unit_id") == target_id:
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, req, option_id, player_id=player.id)

    roll_requests = [r for r in list(game.decision_queue.list() or []) if r.decision_type == DECISION_REQUEST_DICE_ROLL]
    assert len(roll_requests) == 1
    roll_req = roll_requests[0]
    roll_id = roll_req.context.get("roll_id")
    state = game.roll_manager.get_roll(int(roll_id))
    assert state.spec.get("dice_count") == 3
    reroll_rules = list(state.spec.get("reroll_rules", []) or [])
    assert reroll_rules
    assert int(reroll_rules[0].get("max_select") or 0) == 1
    state.spec["fixed_dice"] = [4, 1, 6]
    resolve_decision_command(game, roll_req, roll_req.options[0].option_id, player_id=player.id)
    _resolve_optional_reroll(game, player.id)

    assert applied["amount"] == 2
    assert applied["target"] is enemy
