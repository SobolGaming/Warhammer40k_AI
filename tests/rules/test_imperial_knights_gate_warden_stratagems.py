from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, faction_name: str, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "6",
                "OC": "8",
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


def _make_unit(name: str, *, faction_name: str, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description=f"Control {name}",
        conditions=lambda _game: False,
        location=point,
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ik_army = Army.with_detachment("Imperial Knights", detachment_type="Gate Warden Lance")
    ik_army.faction_id = "QI"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    ik_player = Player("IK", PlayerControl.LOCAL, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    ik_player.command_points = 6
    enemy_player.command_points = 6
    ik_army.configure_rule_managers(force=True)
    ik_player.stratagems.refresh_available()

    obj_alpha = _make_objective("Alpha", 0.0, 0.0)
    obj_beta = _make_objective("Beta", 20.0, 0.0)
    obj_gamma = _make_objective("Gamma", 40.0, 0.0)
    game.objectives = [obj_alpha, obj_beta, obj_gamma]
    game.map.objectives = [obj_alpha, obj_beta, obj_gamma]
    return game, ik_army, enemy_army, ik_player, enemy_player, obj_alpha, obj_beta, obj_gamma


def _find_dauntless_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "")
        == "gate_warden_dauntless_defenders_foundation"
    ]


def _select_objective(game: Game, request, *, player_id: str, objective_id: str) -> None:
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("objective_id", "") or "").strip() == str(objective_id or "").strip()
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def _select_dauntless_foundations(game: Game, ik_player: Player, *objectives: Objective) -> None:
    for objective in objectives:
        request = _find_dauntless_requests(game)[0]
        _select_objective(
            game,
            request,
            player_id=ik_player.id,
            objective_id=str(get_entity_id(objective) or ""),
        )


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").replace("\u2019", "'").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        reaction_name = str(reaction.get("stratagem", "") or "").replace("\u2019", "'").strip().upper()
        if reaction_name == target:
            return reaction
    return None


def _make_ranged_profile(*, strength: int = 10) -> WargearProfile:
    parent = SimpleNamespace(name="Test Cannon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Test Cannon",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "-2",
            "D": "3",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_melee_profile(*, strength: int = 10) -> WargearProfile:
    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Test Blade",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "-2",
            "D": "3",
            "description": "",
        },
        parent_wargear=parent,
    )


@pytest.mark.parametrize(
    ("stratagem_id", "name", "effect"),
    [
        ("000010498002", "Drive Them Out!", "conditional_crit_hit_threshold"),
        ("000010498003", "Lancebreaker", "worsen_incoming_wound_roll_if_strength_gt_toughness"),
        ("000010498004", "Steadfast Superiority", "reroll_hits"),
        ("000010498005", "Marshal the Defence", "movement_bonus"),
        ("000010498006", "Titanic Bombardment", "ranged_sustained_hits"),
        ("000010498007", "Fortress of Intimidation", "charge_target_battle_shock"),
    ],
)
def test_gate_warden_stratagem_descriptors_registered(stratagem_id: str, name: str, effect: str):
    desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
    assert desc is not None
    assert desc.name == name
    assert desc.effect == effect
    assert int(desc.cp_cost or 0) == 1


def test_drive_them_out_scores_critical_hits_on_five_against_enemy_on_defensive_line():
    game, ik_army, enemy_army, ik_player, _enemy_player, obj_alpha, obj_beta, _obj_gamma = _build_game()
    shooter = _make_unit(
        "Knight Warden",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ik_army.add_unit(shooter)
    enemy_army.add_unit(enemy)
    game.map.units = [shooter, enemy]
    shooter.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(10.0, 0.5, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    _select_dauntless_foundations(game, ik_player, obj_alpha, obj_beta)
    _set_phase(game, ik_player, "SHOOTING_PHASE", 0)

    assert ik_player.stratagems.use("DRIVE THEM OUT!", unit=shooter, phase_name="Shooting phase")

    profile = _make_ranged_profile()
    attack_instance = {}
    hit_result = profile._hit_target_with_tracking(
        enemy,
        shooter.models[0],
        attack_instance,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("crit_hit"))
    assert int(hit_result.get("crit_threshold", 6) or 6) == 5

    game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))

    attack_after = {}
    hit_after = profile._hit_target_with_tracking(
        enemy,
        shooter.models[0],
        attack_after,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(attack_after.get("crit_hit"))
    assert int(hit_after.get("crit_threshold", 6) or 6) == 6


def test_fortress_of_intimidation_queues_and_forces_battleshock_test_at_minus_one():
    game, ik_army, enemy_army, ik_player, enemy_player, obj_alpha, obj_beta, _obj_gamma = _build_game()
    fortress = _make_unit(
        "Knight Castellan",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Chargers",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ik_army.add_unit(fortress)
    enemy_army.add_unit(enemy)
    game.map.units = [fortress, enemy]
    fortress.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(13.0, 0.0, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    _select_dauntless_foundations(game, ik_player, obj_alpha, obj_beta)
    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)

    pending = _pending_by_name(ik_player.stratagems, "FORTRESS OF INTIMIDATION")
    assert pending is not None

    captured: dict[str, object] = {}

    def _take_battle_shock_test(current_turn: int = 1):
        sr = dict(getattr(enemy, "special_rules", {}) or {})
        captured["turn"] = int(current_turn or 0)
        captured["modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0)
        captured["reasons"] = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
        enemy.special_rules.pop("battle_shock_test_modifier", None)
        enemy.special_rules.pop("battle_shock_test_modifier_reasons", None)

    enemy.take_battle_shock_test = _take_battle_shock_test

    assert ik_player.stratagems.use(
        str(pending.get("stratagem", "") or "FORTRESS OF INTIMIDATION"),
        unit=fortress,
        phase_name="Charge phase",
        dequeue=True,
    )
    game.event_system.publish("charge_declared", unit=enemy, target_units=[fortress])

    assert int(captured.get("modifier", 0) or 0) == -1
    assert "FORTRESS OF INTIMIDATION" in list(captured.get("reasons", []) or [])

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    assert not bool(fortress.special_rules.get("gate_warden_fortress_of_intimidation_active"))


def test_lancebreaker_queues_and_penalises_stronger_attacks_until_end_of_phase():
    game, ik_army, enemy_army, ik_player, enemy_player, obj_alpha, obj_beta, _obj_gamma = _build_game()
    defender = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Bruiser",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ik_army.add_unit(defender)
    enemy_army.add_unit(enemy)
    game.map.units = [defender, enemy]
    defender.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(10.5, 0.0, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    _select_dauntless_foundations(game, ik_player, obj_alpha, obj_beta)
    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)

    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[defender])
    pending = _pending_by_name(ik_player.stratagems, "LANCEBREAKER")
    assert pending is not None

    assert ik_player.stratagems.use(
        str(pending.get("stratagem", "") or "LANCEBREAKER"),
        unit=defender,
        attacking_unit=enemy,
        target_units=[defender],
        phase_name="Fight phase",
        dequeue=True,
    )

    profile = _make_melee_profile(strength=12)
    wound_result = profile._wound_target_with_tracking(
        defender,
        enemy.models[0],
        {"distance_to_target": 1.0},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(wound_result.get("wound"))
    assert any("LANCEBREAKER" in str(reason) for reason in list(wound_result.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    wound_after = profile._wound_target_with_tracking(
        defender,
        enemy.models[0],
        {"distance_to_target": 1.0},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_after.get("wound"))


def test_marshal_the_defence_grants_plus_three_move_to_up_to_two_units_until_phase_end():
    game, ik_army, _enemy_army, ik_player, _enemy_player, *_objectives = _build_game()
    unit_a = _make_unit(
        "Knight Errant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    unit_b = _make_unit(
        "Armiger Helverin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    ik_army.add_unit(unit_a)
    ik_army.add_unit(unit_b)
    game.map.units = [unit_a, unit_b]
    unit_a.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    unit_b.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    _set_phase(game, ik_player, "MOVEMENT_PHASE", 0)
    base_a = int(unit_a.movement)
    base_b = int(unit_b.movement)

    assert ik_player.stratagems.use(
        "MARSHAL THE DEFENCE",
        selected_units=[unit_a, unit_b],
        phase_name="Movement phase",
    )
    assert int(unit_a.movement) == base_a + 3
    assert int(unit_b.movement) == base_b + 3

    game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert int(unit_a.movement) == base_a
    assert int(unit_b.movement) == base_b


def test_steadfast_superiority_grants_full_melee_hit_rerolls_until_end_of_phase():
    game, ik_army, enemy_army, ik_player, _enemy_player, obj_alpha, obj_beta, _obj_gamma = _build_game()
    fighter = _make_unit(
        "Knight Gallant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Duelists",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ik_army.add_unit(fighter)
    enemy_army.add_unit(enemy)
    game.map.units = [fighter, enemy]
    fighter.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(10.5, 0.0, 0.0, 0.0)
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    _select_dauntless_foundations(game, ik_player, obj_alpha, obj_beta)
    _set_phase(game, ik_player, "FIGHT_PHASE", 0)

    assert ik_player.stratagems.use("STEADFAST SUPERIORITY", unit=fighter, phase_name="Fight phase")

    profile = _make_melee_profile()
    hit_result = profile._hit_target_with_tracking(
        enemy,
        fighter.models[0],
        {"distance_to_target": 1.0},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("STEADFAST SUPERIORITY" in str(reason) for reason in list(hit_result.get("reroll_full_reasons", []) or []))

    game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    hit_after = profile._hit_target_with_tracking(
        enemy,
        fighter.models[0],
        {"distance_to_target": 1.0},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("STEADFAST SUPERIORITY" in str(reason) for reason in list(hit_after.get("reroll_full_reasons", []) or []))


def test_titanic_bombardment_grants_sustained_hits_two_until_end_of_phase():
    game, ik_army, enemy_army, ik_player, _enemy_player, obj_alpha, obj_beta, _obj_gamma = _build_game()
    shooter = _make_unit(
        "Knight Castellan",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Target",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ik_army.add_unit(shooter)
    enemy_army.add_unit(enemy)
    game.map.units = [shooter, enemy]
    shooter.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(16.0, 0.0, 0.0, 0.0)
    shooter.round_state.remained_stationary_this_round = True
    game.turn = 1
    game.rebuild_entity_registry()

    ik_army.on_battle_round_start(1)
    _select_dauntless_foundations(game, ik_player, obj_alpha, obj_beta)
    _set_phase(game, ik_player, "SHOOTING_PHASE", 0)

    assert ik_player.stratagems.use("TITANIC BOMBARDMENT", unit=shooter, phase_name="Shooting phase")

    profile = _make_ranged_profile()
    attack_instance = {}
    hit_result = profile._hit_target_with_tracking(
        enemy,
        shooter.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("crit_hit"))
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 2

    game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))

    attack_after = {}
    hit_after = profile._hit_target_with_tracking(
        enemy,
        shooter.models[0],
        attack_after,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_after.get("crit_hit"))
    assert int(attack_after.get("sustained_hit", 0) or 0) == 1
