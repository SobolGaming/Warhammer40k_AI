from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        movement: int = 10,
        toughness: int = 9,
        wounds: int = 10,
        leadership: int = 7,
        objective_control: int = 3,
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
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": "60mm",
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
    movement: int = 10,
    toughness: int = 9,
    wounds: int = 10,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Headhunter Task Force")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)

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
        model.set_location(float(x) + (float(index) * 2.0), float(y), 0.0, 0.0)
    assert game.map.place_unit(unit), f"failed to place {getattr(unit, 'name', 'Unit')}"


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


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _ranged_profile(ap: str = "0") -> WargearProfile:
    parent = SimpleNamespace(name="Test Cannon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "36",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": str(ap),
            "D": "D6",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_headhunter_task_force_stratagem_descriptors_registered():
    expected = {
        "000010784004": ("Kill Shot", "ranged_wound_rerolls_against_monster_or_vehicle_targets"),
        "000010784005": ("Rapid Gunnery", "eligible_to_shoot_after_fall_back"),
        "000010784003": ("Target Weak Point", "ranged_ap_bonus_against_monster_or_vehicle_targets"),
        "000010784007": ("Machine Vengeance", "reactive_shooting_restricted_to_attacker"),
        "000010784006": ("Reactive Repositioning", "reactive_normal_move_d6"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_kill_shot_and_rapid_gunnery_queue_apply_and_reject_mutual_target_weak_point():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    predator = _make_unit("Predator Destructor", keywords=["VEHICLE"])
    intercessors = _make_unit("Intercessor Squad", keywords=["INFANTRY"], wounds=2)
    enemy_vehicle = _make_unit(
        "Enemy Vehicle",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        wounds=12,
    )
    sm_army.add_unit(predator)
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy_vehicle)
    _deploy_unit(game, predator, 10.0, 10.0)
    _deploy_unit(game, intercessors, 10.0, 20.0)
    _deploy_unit(game, enemy_vehicle, 25.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "KILL SHOT") is not None
    rapid = _pending_by_name(sm_player.stratagems, "RAPID GUNNERY")
    assert rapid is not None
    assert intercessors in list(rapid.get("candidates") or [])
    assert _pending_by_name(sm_player.stratagems, "TARGET WEAK POINT") is not None

    assert sm_player.stratagems.use("KILL SHOT", unit=predator, dequeue=True) is True
    profile = _ranged_profile()
    mods = predator.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy_vehicle,
        attacker_model=predator.models[0],
        weapon_profile=profile,
    )
    assert 1 in set(mods.get("reroll_wound_values") or ())
    assert bool(mods.get("reroll_wound_full", False)) is False

    enemy_vehicle.models[0].wounds -= 1
    mods = predator.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy_vehicle,
        attacker_model=predator.models[0],
        weapon_profile=profile,
    )
    assert bool(mods.get("reroll_wound_full", False)) is True
    assert sm_player.stratagems.use("TARGET WEAK POINT", unit=predator) is False

    intercessors.round_state.fell_back_this_round = True
    assert intercessors.can_shoot_after_fall_back(profile, model=intercessors.models[0]) is False
    assert sm_player.stratagems.use("RAPID GUNNERY", unit=intercessors, dequeue=True) is True
    assert intercessors.can_shoot_after_fall_back(profile, model=intercessors.models[0]) is True


def test_target_weak_point_ap_bonus_and_mutual_kill_shot_rejection():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    predator = _make_unit("Predator Destructor", keywords=["VEHICLE"])
    enemy_vehicle = _make_unit(
        "Enemy Rhino",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    enemy_infantry = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(predator)
    enemy_army.add_unit(enemy_vehicle)
    enemy_army.add_unit(enemy_infantry)
    _deploy_unit(game, predator, 10.0, 10.0)
    _deploy_unit(game, enemy_vehicle, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert sm_player.stratagems.use("TARGET WEAK POINT", unit=predator, dequeue=True) is True
    profile = _ranged_profile(ap="0")
    assert profile.get_effective_ap(predator.models[0], enemy_vehicle) == -1
    assert profile.get_effective_ap(predator.models[0], enemy_infantry) == 0
    assert sm_player.stratagems.use("KILL SHOT", unit=predator) is False


def test_machine_vengeance_queues_after_targeted_by_enemy_and_excludes_wounds_16_plus():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    predator = _make_unit("Predator Destructor", keywords=["VEHICLE"], wounds=10)
    repulsor = _make_unit("Repulsor Executioner", keywords=["VEHICLE"], wounds=16)
    enemy = _make_unit(
        "Enemy Tank Hunters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(predator)
    sm_army.add_unit(repulsor)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, predator, 10.0, 10.0)
    _deploy_unit(game, repulsor, 10.0, 20.0)
    _deploy_unit(game, enemy, 22.0, 15.0)
    game.rebuild_entity_registry()
    game._setup_reactive_can_shoot_target = lambda _unit, _target: True

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[predator, repulsor])
    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy)

    pending = _pending_by_name(sm_player.stratagems, "MACHINE VENGEANCE")
    assert pending is not None
    assert list(pending.get("candidates") or []) == [predator]
    assert sm_player.stratagems.use(
        "MACHINE VENGEANCE",
        unit=repulsor,
        enemy_unit=enemy,
        candidates=list(pending.get("candidates") or []),
        phase_name="Shooting phase",
    ) is False

    assert sm_player.stratagems.use(
        "MACHINE VENGEANCE",
        unit=predator,
        enemy_unit=enemy,
        candidates=list(pending.get("candidates") or []),
        phase_name="Shooting phase",
        dequeue=True,
    ) is True
    request = _first_request(game, DECISION_DECLARE_SHOTS)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert bool(context.get("out_of_phase", False)) is True
    assert bool(context.get("machine_vengeance_flow", False)) is True
    assert str(context.get("force_target_unit_id", "") or "") == str(get_entity_id(enemy) or "")


def test_reactive_repositioning_queues_d6_move_and_excludes_wounds_16_plus():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    predator = _make_unit("Predator Destructor", keywords=["VEHICLE"], wounds=10)
    repulsor = _make_unit("Repulsor Executioner", keywords=["VEHICLE"], wounds=16)
    enemy = _make_unit(
        "Enemy Scouts",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(predator)
    sm_army.add_unit(repulsor)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, predator, 10.0, 10.0)
    _deploy_unit(game, repulsor, 10.0, 20.0)
    _deploy_unit(game, enemy, 16.0, 15.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="advance")
    pending = _pending_by_name(sm_player.stratagems, "REACTIVE REPOSITIONING")
    assert pending is not None
    assert list(pending.get("candidates") or []) == [predator]
    assert sm_player.stratagems.use(
        "REACTIVE REPOSITIONING",
        unit=repulsor,
        enemy_unit=enemy,
        action="advance",
        candidates=list(pending.get("candidates") or []),
        phase_name="Movement phase",
    ) is False

    with patch("warhammer40k_ai.rules.stratagems_space_marines.dice_module.get_roll", return_value=4):
        assert sm_player.stratagems.use(
            "REACTIVE REPOSITIONING",
            unit=predator,
            enemy_unit=enemy,
            action="advance",
            candidates=list(pending.get("candidates") or []),
            phase_name="Movement phase",
            dequeue=True,
        ) is True

    request = _first_request(game, DECISION_MOVE_UNIT)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert context["reactive_move_kind"] == "headhunter_reactive_repositioning"
    assert context["movement_type"] == "reactive"
    assert context["max_distance"] == 4
    assert context["allow_skip"] is True
    assert context["ability"] == "space_marines_headhunter_reactive_repositioning"
