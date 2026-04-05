from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(self, name, *, unit_comp="1 Test Model", abilities=None, keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = ["T'AU EMPIRE"]
        self.datasheets_unit_composition = [{"description": unit_comp}]
        self.datasheets_models_cost = [{"description": unit_comp, "cost": 100}]
        self.datasheets_models = [
            {
                "M": "14",
                "T": "7",
                "Sv": "4",
                "W": "7",
                "Ld": "7",
                "OC": "2",
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


def test_drone_harassment_tactics_targets_any_enemy_and_forces_test():
    from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = (
        "At the end of your Movement phase, select one enemy unit within 12\" of this unit; "
        "that enemy unit must take a Battle-shock test."
    )
    source = _make_unit("Piranhas", ability_desc=ability, keywords=["VEHICLE"])
    infantry = _make_unit("Enemy Infantry")
    vehicle = _make_unit("Enemy Vehicle", keywords=["VEHICLE"])
    source.deployed = True
    infantry.deployed = True
    vehicle.deployed = True

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    infantry.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    vehicle.models[0].set_location(8.0, 2.0, 0.0, 0.0)

    player, enemy_player = _setup_players(source, [infantry, vehicle])

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]
    game.map = _MapStub([source, infantry, vehicle], [infantry, vehicle])
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0

    game._on_phase_end_enrage_machine_spirits(player=player, phase=game.phase)

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert str(req.context.get("ability", "")) == "enrage_machine_spirits"
    assert not any(opt.payload.get("action") == "skip" for opt in list(req.options or []))

    infantry_id = str(get_entity_id(infantry))
    vehicle_id = str(get_entity_id(vehicle))
    target_ids = [
        str(opt.payload.get("target_unit_id", ""))
        for opt in list(req.options or [])
        if opt.payload.get("target_unit_id")
    ]
    assert infantry_id in target_ids
    assert vehicle_id in target_ids

    option_id = None
    for opt in list(req.options or []):
        if str(opt.payload.get("target_unit_id", "")) == infantry_id:
            option_id = opt.option_id
            break
    assert option_id is not None

    with patch.object(type(infantry), "take_battle_shock_test", autospec=True) as mocked:
        resolve_decision_command(game, req, option_id, player_id=player.id)
        assert mocked.call_count == 1
        args, _kwargs = mocked.call_args
        assert args[0] is infantry
        assert int(args[1]) == int(getattr(game, "turn", 0) or 0)
