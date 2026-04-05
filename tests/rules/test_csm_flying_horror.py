from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(self, name, *, unit_comp="1 Test Model", abilities=None, keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Chaos Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = ["HERETIC ASTARTES"]
        self.datasheets_unit_composition = [{"description": unit_comp}]
        self.datasheets_models_cost = [{"description": unit_comp, "cost": 100}]
        self.datasheets_models = [
            {
                "M": "12",
                "T": "6",
                "Sv": "3",
                "W": "8",
                "Ld": "6",
                "OC": "3",
                "base_size": "60mm",
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


def test_flying_horror_move_over_battleshock_queue_and_apply():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = (
        "Each time this model ends a Normal or Advance move, select one enemy unit that it moved over during that move. "
        "That unit must take a Battle-shock test."
    )
    source = _make_unit("Daemon Prince", ability_desc=ability, keywords=["FLY"])
    enemy = _make_unit("Target Unit")
    source.deployed = True
    enemy.deployed = True

    mover = source.models[0]
    mover.set_location(0.0, 0.0, 0.0, 0.0)
    mover.last_move_path = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
    enemy.models[0].set_location(5.0, 0.0, 0.0, 0.0)

    player, enemy_player = _setup_players(source, [enemy])

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]
    game.map = _MapStub([source, enemy], [enemy])

    game._on_unit_move_ended_move_over_battleshock(unit=source, action="move")

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert str(req.context.get("ability", "")) == "move_over_battleshock"
    assert not any(opt.payload.get("action") == "skip" for opt in list(req.options or []))

    target_id = str(get_entity_id(enemy))
    option_id = None
    for opt in list(req.options or []):
        if str(opt.payload.get("target_unit_id", "")) == target_id:
            option_id = opt.option_id
            break
    assert option_id is not None
    with patch.object(type(enemy), "take_battle_shock_test", autospec=True) as mocked:
        resolve_decision_command(game, req, option_id, player_id=player.id)
        assert mocked.call_count == 1
        args, _kwargs = mocked.call_args
        assert args[0] is enemy
        assert int(args[1]) == int(getattr(game, "turn", 0) or 0)
