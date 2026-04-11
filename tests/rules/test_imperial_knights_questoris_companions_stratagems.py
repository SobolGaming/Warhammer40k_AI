from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        wounds: int = 12,
        objective_control: int = 8,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "6",
                "OC": str(int(objective_control)),
                "base_size": "100mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords=None,
    faction_keywords=None,
    wounds: int = 12,
    objective_control: int = 8,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    ik_army = Army.with_detachment("Imperial Knights", detachment_type="Questoris Companions")
    ik_army.faction_id = "QI"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    ik_player = Player("IK", PlayerControl.LOCAL, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    ik_player.command_points = 6
    enemy_player.command_points = 6
    ik_army.configure_rule_managers(force=True)
    ik_player.stratagems.refresh_available()
    return game, ik_army, enemy_army, ik_player, enemy_player


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").replace("\u2019", "'").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        reaction_name = str(reaction.get("stratagem", "") or "").replace("\u2019", "'").strip().upper()
        if reaction_name == target:
            return reaction
    return None


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Cannon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Test Cannon",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "-2",
            "D": "3",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_questoris_companions_stratagem_descriptors_registered():
    expected = {
        "000010503004": ("Moment of Glory", "extend_consolidate_move"),
        "000010503005": ("Hero's Tread", "sticky_objective_with_minimum_control"),
        "000010503006": ("Unstoppable Warrior", "eligible_to_shoot_and_charge_after_fall_back"),
        "000010503007": ("Driven by the Past", "charge_after_advance"),
    }
    for stratagem_id, (name, effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=name.upper())
        by_name = get_stratagem_tool_descriptor(name=name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == name
        assert by_name.name == name
        assert by_id.effect == effect


def test_driven_by_the_past_allows_charge_after_advance_for_the_turn():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Errant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    ik_army.add_unit(knight)
    _set_unit_position(knight, 10.0, 10.0)
    game.map.units = [knight]
    game.rebuild_entity_registry()

    _set_phase(game, ik_player, "CHARGE_PHASE", 0)
    knight.round_state.advanced_this_round = True
    assert knight.can_charge_after_advance() is False

    start_cp = int(ik_player.command_points or 0)
    ok = ik_player.stratagems.use("DRIVEN BY THE PAST", unit=knight, phase_name="Charge phase")
    assert ok is True
    assert int(ik_player.command_points or 0) == start_cp - 1
    assert knight.can_charge_after_advance() is True

    game.current_player_index = 1
    assert knight.can_charge_after_advance() is False


def test_heros_tread_queues_at_command_phase_end_and_sets_sticky_minimum_control():
    game, ik_army, enemy_army, ik_player, enemy_player = _build_game()
    knight = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Objective Holder",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        objective_control=4,
        wounds=2,
    )
    ik_army.add_unit(knight)
    enemy_army.add_unit(enemy)
    _set_unit_position(knight, 10.0, 10.0)
    _set_unit_position(enemy, 30.0, 30.0)
    game.map.units = [knight, enemy]

    objective_point = ObjectivePoint(10.0, 10.0, 0.0, control_radius=3.0)
    objective_point.controlling_player = ik_player
    objective = Objective(
        name="Center Objective",
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="Hold the center",
        conditions=lambda _game: True,
        location=objective_point,
    )
    game.map.objectives = [objective]
    game.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, ik_player, "COMMAND_PHASE", 0)
    game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="COMMAND_PHASE"))
    pending = _pending_by_name(ik_player.stratagems, "HERO'S TREAD")
    assert pending is not None

    start_cp = int(ik_player.command_points or 0)
    ok = ik_player.stratagems.use("HERO'S TREAD", unit=knight, objective=objective, dequeue=True)
    assert ok is True
    assert int(ik_player.command_points or 0) == start_cp - 1
    assert objective_point.sticky_controller is ik_player
    assert int(objective_point.sticky_minimum_control or 0) == 5

    _set_unit_position(knight, 30.0, 30.0)
    _set_unit_position(enemy, 10.0, 10.0)
    enemy.models[0].objective_control = 4
    objective_point.update_control(game)
    assert objective_point.controlling_player is ik_player
    assert objective_point.sticky_controller is ik_player
    assert int(objective_point.sticky_minimum_control or 0) == 5

    enemy.models[0].objective_control = 6
    objective_point.update_control(game)
    assert objective_point.controlling_player is enemy_player
    assert objective_point.sticky_controller is None
    assert int(objective_point.sticky_minimum_control or 0) == 0


def test_moment_of_glory_queues_before_consolidate_and_updates_validation_rules():
    game, ik_army, enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Gallant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        objective_control=2,
    )
    ik_army.add_unit(knight)
    enemy_army.add_unit(enemy)
    _set_unit_position(knight, 10.0, 10.0)
    _set_unit_position(enemy, 13.0, 10.0)
    game.map.units = [knight, enemy]
    game.rebuild_entity_registry()

    _set_phase(game, ik_player, "FIGHT_PHASE", 0)
    game.event_system.publish("fight_attacks_resolved", unit=knight, target_unit=enemy)
    pending = _pending_by_name(ik_player.stratagems, "MOMENT OF GLORY")
    assert pending is not None

    start_cp = int(ik_player.command_points or 0)
    ok = ik_player.stratagems.use("MOMENT OF GLORY", unit=knight, dequeue=True)
    assert ok is True
    assert int(ik_player.command_points or 0) == start_cp - 1

    rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=knight)
    assert float(rules.get("max_distance_override") or 0.0) == 6.0
    assert bool(rules.get("consolidate_requires_engagement", False)) is True

    game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=knight)
    assert float(rules.get("max_distance_override") or 0.0) == 3.0
    assert bool(rules.get("consolidate_requires_engagement", False)) is False


def test_unstoppable_warrior_queues_after_fall_back_and_grants_shoot_and_charge():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Warden",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    ik_army.add_unit(knight)
    _set_unit_position(knight, 10.0, 10.0)
    game.map.units = [knight]
    game.rebuild_entity_registry()

    _set_phase(game, ik_player, "MOVEMENT_PHASE", 0)
    knight.round_state.fell_back_this_round = True
    profile = _ranged_profile()
    assert knight.can_shoot_after_fall_back(profile) is False
    assert knight.can_charge_after_fall_back() is False

    game.event_system.publish("unit_move_ended", unit=knight, action="fall_back")
    pending = _pending_by_name(ik_player.stratagems, "UNSTOPPABLE WARRIOR")
    assert pending is not None

    start_cp = int(ik_player.command_points or 0)
    ok = ik_player.stratagems.use("UNSTOPPABLE WARRIOR", unit=knight, dequeue=True)
    assert ok is True
    assert int(ik_player.command_points or 0) == start_cp - 2
    assert knight.can_shoot_after_fall_back(profile) is True
    assert knight.can_charge_after_fall_back() is True

    game.current_player_index = 1
    assert knight.can_shoot_after_fall_back(profile) is False
    assert knight.can_charge_after_fall_back() is False
