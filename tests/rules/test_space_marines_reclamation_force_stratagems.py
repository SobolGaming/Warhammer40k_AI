from __future__ import annotations

from types import SimpleNamespace

import warhammer40k_ai.rules.stratagems_space_marines as sm_stratagems_module
from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        objective_control: int = 1,
        wounds: int = 4,
        move: int = 6,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "32mm",
                "inv_sv": "7",
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
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    objective_control: int = 1,
    wounds: int = 4,
    move: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            objective_control=objective_control,
            wounds=wounds,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Reclamation Force")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="",
        conditions=lambda _game: False,
        location=point,
    )


def _ranged_wargear(name: str = "Bolt Rifle", attacks: str = "1") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _melee_wargear(name: str = "Power Sword", attacks: str = "2") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": "5",
            "AP": "-2",
            "D": "1",
            "description": "",
        }
    )


def _make_profile(*, is_melee: bool, attacks: str = "1") -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_reclamation_force_stratagem_descriptors_registered():
    expected = {
        "000010685002": ("Crusading Conquerors", "objective_control_bonus_until_next_command_phase"),
        "000010685003": ("Furious Dedication", "charge_roll_bonus_and_melee_attacks_bonus"),
        "000010685004": ("Fight to the End", "fight_on_death_on_4_plus"),
        "000010685005": ("Scions of Guilliman", "shoot_and_charge_after_fall_back"),
        "000010685006": ("Ultramarian Destiny", "sticky_objective_control"),
        "000010685007": ("Marching Ever On", "reactive_normal_move_after_enemy_fall_back"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_crusading_conquerors_queues_in_your_command_phase_and_lasts_until_your_next_command_phase():
    game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        objective_control=1,
    )
    reserves = _make_unit(
        "Reserve Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    reserves.deployed = False
    reserves.reserve_status = "strategic_reserves"

    sm_army.add_unit(intercessors)
    sm_army.add_unit(reserves)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="COMMAND_PHASE"))
    pending = _pending_by_name(sm_player.stratagems, "CRUSADING CONQUERORS")
    assert pending is not None
    assert intercessors in list(pending.get("candidates", []) or [])
    assert reserves in list(pending.get("candidates", []) or [])

    ok = sm_player.stratagems.use(
        "CRUSADING CONQUERORS",
        unit=intercessors,
        phase_name="Command phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert int(intercessors.get_effective_model_characteristic(intercessors.models[0], "objective_control")) == 2

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert _pending_by_name(sm_player.stratagems, "CRUSADING CONQUERORS") is None
    assert int(intercessors.get_effective_model_characteristic(intercessors.models[0], "objective_control")) == 2

    game.turn = 2
    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert int(intercessors.get_effective_model_characteristic(intercessors.models[0], "objective_control")) == 1


def test_furious_dedication_queues_applies_bonuses_and_is_limited_to_once_per_turn():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    assault = _make_unit(
        "Assault Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    melee_weapon = _melee_wargear(attacks="2")
    assault.models[0].wargear = [melee_weapon]
    sm_army.add_unit(assault)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, assault, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "FURIOUS DEDICATION") is not None

    ok = sm_player.stratagems.use(
        "FURIOUS DEDICATION",
        unit=assault,
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    charge_modifiers = assault.get_charge_roll_target_strength_modifiers([enemy])
    assert any(
        int(bonus or 0) == 2 and "FURIOUS DEDICATION" in str(source or "").upper()
        for bonus, source in charge_modifiers
    )

    attack_preview = melee_weapon.profiles["default"].preview_attack_count(
        enemy,
        assault.models[0],
        game_map=game.map,
        publish_roll_event=False,
    )
    assert int(attack_preview.num_attacks or 0) == 3
    assert any("FURIOUS DEDICATION" in str(note or "").upper() for note in list(attack_preview.special_modifiers or []))

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "FURIOUS DEDICATION") is None

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert not any(
        "FURIOUS DEDICATION" in str(source or "").upper()
        for _bonus, source in assault.get_charge_roll_target_strength_modifiers([enemy])
    )
    cleared_preview = melee_weapon.profiles["default"].preview_attack_count(
        enemy,
        assault.models[0],
        game_map=game.map,
        publish_roll_event=False,
    )
    assert int(cleared_preview.num_attacks or 0) == 2


def test_fight_to_the_end_queues_on_enemy_target_selection_and_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    veterans = _make_unit(
        "Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Bruisers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(veterans)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, veterans, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[veterans])
    assert _pending_by_name(sm_player.stratagems, "FIGHT TO THE END") is not None

    ok = sm_player.stratagems.use(
        "FIGHT TO THE END",
        unit=veterans,
        enemy_unit=enemy,
        target_units=[veterans],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    rule = veterans.get_melee_fight_on_death_after_attacks_rule(model=veterans.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 4
    assert "FIGHT TO THE END" in str(rule.get("source", "") or "").upper()

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert veterans.get_melee_fight_on_death_after_attacks_rule(model=veterans.models[0]) is None


def test_scions_of_guilliman_queues_after_fall_back_and_expires_at_end_of_turn():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    bolt_rifle = _ranged_wargear()
    intercessors.models[0].wargear = [bolt_rifle]
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    intercessors.round_state.fell_back_this_round = True
    game.event_system.publish("unit_move_ended", unit=intercessors, action="fall_back")
    assert _pending_by_name(sm_player.stratagems, "SCIONS OF GUILLIMAN") is not None

    ok = sm_player.stratagems.use(
        "SCIONS OF GUILLIMAN",
        unit=intercessors,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert intercessors.can_shoot_after_fall_back(bolt_rifle.profiles["default"], model=intercessors.models[0]) is True
    assert intercessors.can_charge_after_fall_back() is True

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert intercessors.can_shoot_after_fall_back(bolt_rifle.profiles["default"], model=intercessors.models[0]) is False
    assert intercessors.can_charge_after_fall_back() is False


def test_ultramarian_destiny_queues_and_applies_sticky_objective_control():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    objective = _make_objective("Central Objective", 10.0, 10.0)
    objective.location.controlling_player = sm_player
    sm_army.add_unit(intercessors)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "ULTRAMARIAN DESTINY")
    assert pending is not None
    assert objective in list(pending.get("objective_candidates", []) or [])

    ok = sm_player.stratagems.use(
        "ULTRAMARIAN DESTINY",
        unit=intercessors,
        objective=objective,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert objective.location.sticky_controller is sm_player
    assert objective.location.controlling_player is sm_player


def test_marching_ever_on_uses_phase_start_engagement_snapshot_and_queues_reactive_move(monkeypatch):
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.8, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    for model in list(getattr(enemy, "models", []) or []):
        model.set_location(20.0, 10.0, 0.0, 0.0)
    assert game.map.is_within_engagement_range(intercessors, enemy) is False

    game.event_system.publish("unit_move_ended", unit=enemy, action="fall_back")
    assert _pending_by_name(sm_player.stratagems, "MARCHING EVER ON") is not None

    captured = {}

    def _capture_queue(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="queued_reactive_move")

    monkeypatch.setattr(game, "_queue_reactive_move_movement_decision", _capture_queue)
    monkeypatch.setattr(sm_stratagems_module.dice_module, "get_roll", lambda _expr: 4)

    ok = sm_player.stratagems.use(
        "MARCHING EVER ON",
        unit=intercessors,
        enemy_unit=enemy,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert captured == {
        "player": sm_player,
        "unit": intercessors,
        "max_distance": 5,
        "kind": "marching_ever_on",
        "movement_type": "move",
        "source": "MARCHING EVER ON",
        "moving_unit": enemy,
        "allow_skip": True,
    }
