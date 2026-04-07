from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

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
        abilities=None,
        model_count: int = 1,
        wounds: int = 4,
        toughness: int = 4,
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
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count: int = 1,
    wounds: int = 4,
    toughness: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Inner Circle Task Force")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

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
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
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


def _make_profile(*, is_melee: bool, strength: str = "4", skill: str = "3+", damage: str = "1") -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def test_inner_circle_task_force_stratagem_descriptors_registered():
    expected = {
        "000008775003": ("Martial Mastery", "melee_wound_reroll_ones_or_full_if_within_vowed_objective"),
        "000008775004": ("Duty Unto Death", "melee_fight_on_death_after_attacks_with_vowed_objective_bonus"),
        "000008775005": ("Relic Teleportarium", "deep_strike_min_distance_override_with_no_charge"),
        "000008775006": ("Wrath of the Lion", "charge_end_capped_mortal_wound_burst"),
        "000008775007": ("Unmatched Fortitude", "defensive_wound_penalty_vs_higher_strength_ranged"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_martial_mastery_queues_and_switches_between_reroll_ones_and_full_rerolls():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    deathwing = _make_unit(
        "Deathwing Knights",
        keywords=["DEATHWING", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=3,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(deathwing)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, deathwing, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    objective = _make_objective("Vowed Objective", 10.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "MARTIAL MASTERY")
    assert pending is not None

    ok = sm_player.stratagems.use("MARTIAL MASTERY", unit=deathwing, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    profile = _make_profile(is_melee=True, strength="6")
    attacker_model = deathwing.models[0]

    no_vow_result = profile._wound_target_with_tracking(
        enemy,
        attacker_model,
        {},
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert 1 in list(no_vow_result.get("reroll_values", []) or [])
    assert not any("Martial Mastery" in reason for reason in list(no_vow_result.get("reroll_full_reasons", []) or []))

    mgr = sm_army.space_marines_detachments
    mgr.vowed_objective_ids = (str(objective.id),)
    mgr.vowed_target_objective_locations = lambda game=None: [objective.location]

    with_vow_result = profile._wound_target_with_tracking(
        enemy,
        attacker_model,
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any(
        "MARTIAL MASTERY" in str(reason).upper()
        for reason in list(with_vow_result.get("reroll_full_reasons", []) or [])
    )


def test_duty_unto_death_queues_and_uses_vowed_objective_bonus_for_fight_on_death():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    target = _make_unit(
        "Deathwing Terminators",
        keywords=["DEATHWING", "INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
        wounds=4,
    )
    enemy = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=2,
        wounds=4,
    )
    sm_army.add_unit(target)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    objective = _make_objective("Vowed Objective", 10.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[target])
    pending = _pending_by_name(sm_player.stratagems, "DUTY UNTO DEATH")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "DUTY UNTO DEATH",
        unit=target,
        attacking_unit=enemy,
        target_units=[target],
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    model = target.models[0]
    base_rule = target.get_melee_fight_on_death_after_attacks_rule(model=model)
    assert isinstance(base_rule, dict)
    assert int(base_rule.get("threshold", 0) or 0) == 4

    mgr = sm_army.space_marines_detachments
    mgr.vowed_objective_ids = (str(objective.id),)
    mgr.vowed_target_objective_locations = lambda game=None: [objective.location]
    bonus_rule = target.get_melee_fight_on_death_after_attacks_rule(model=model)
    assert int(bonus_rule.get("threshold", 0) or 0) == 3

    target.round_state.fought_this_phase = False
    target._last_destroyed_by_weapon_profile = _make_profile(is_melee=True, strength="6", damage="2")
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=3):
        model._wounds = 0
        target._handle_model_destroyed(model, game.map)
    pending_models = list(getattr(target, "_melee_fight_on_death_pending_models", []) or [])
    assert model in pending_models

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert target.get_melee_fight_on_death_after_attacks_rule(model=model) is None


def test_relic_teleportarium_sets_deep_strike_override_blocks_charge_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    deep_strike = {
        "name": "Deep Strike",
        "description": "Deep Strike",
        "type": "Core",
        "parameter": "",
    }
    deathwing = _make_unit(
        "Deathwing Terminators",
        keywords=["DEATHWING", "INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
        abilities=[deep_strike],
        model_count=2,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(deathwing)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, enemy, 14.0, 10.0)

    deathwing.deployed = False
    deathwing.reserve_status = "reserves"

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "RELIC TELEPORTARIUM")
    assert pending is not None

    ok = sm_player.stratagems.use("RELIC TELEPORTARIUM", unit=deathwing, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert float(deathwing.get_deep_strike_min_distance_override() or 0.0) == 6.0

    deathwing.deployed = True
    deathwing.reserve_status = "deployed"
    deathwing.arrived_from_reserves_this_turn = True
    for model in list(deathwing.models or []):
        model.set_location(10.0, 10.0, 0.0, 0.0)
    if deathwing not in list(getattr(game.map, "units", []) or []):
        game.map.place_unit(deathwing)
    assert deathwing.can_declare_charge_against(enemy, game) is False

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert "space_marines_inner_circle_relic_teleportarium_deep_strike_min_distance" not in dict(
        getattr(deathwing, "special_rules", {}) or {}
    )


def test_unmatched_fortitude_queues_and_applies_strength_gt_toughness_wound_penalty():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    target = _make_unit(
        "Deathwing Knights",
        keywords=["DEATHWING", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        toughness=4,
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(target)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
    pending = _pending_by_name(sm_player.stratagems, "UNMATCHED FORTITUDE")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "UNMATCHED FORTITUDE",
        unit=target,
        attacking_unit=enemy,
        target_units=[target],
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    ranged_profile = _make_profile(is_melee=False, strength="5")
    attacker_model = enemy.models[0]
    ranged_result = ranged_profile._wound_target_with_tracking(
        target,
        attacker_model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("UNMATCHED FORTITUDE" in reason for reason in list(ranged_result.get("modifiers", []) or []))

    equal_strength_profile = _make_profile(is_melee=False, strength="4")
    equal_result = equal_strength_profile._wound_target_with_tracking(
        target,
        attacker_model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("UNMATCHED FORTITUDE" in reason for reason in list(equal_result.get("modifiers", []) or []))

    melee_profile = _make_profile(is_melee=True, strength="6")
    melee_result = melee_profile._wound_target_with_tracking(
        target,
        attacker_model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("UNMATCHED FORTITUDE" in reason for reason in list(melee_result.get("modifiers", []) or []))


def test_wrath_of_the_lion_queues_and_deals_capped_mortal_wounds_with_vowed_bonus():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    deathwing = _make_unit(
        "Deathwing Knights",
        keywords=["DEATHWING", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=4,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=6,
    )
    sm_army.add_unit(deathwing)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, deathwing, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    objective = _make_objective("Vowed Objective", 11.5, 10.0)
    mgr = sm_army.space_marines_detachments
    mgr.vowed_objective_ids = (str(objective.id),)
    mgr.vowed_target_objective_locations = lambda game=None: [objective.location]
    enemy.is_within_objective_range = lambda _location: True

    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    deathwing.round_state.charged_this_round = True
    enemy.models[0].set_location(11.5, 10.0, 0.0, 0.0)
    game.event_system.publish("unit_move_ended", unit=deathwing, action="charge")
    pending = _pending_by_name(sm_player.stratagems, "WRATH OF THE LION")
    assert pending is not None
    assert enemy in list(pending.get("enemy_candidates") or [])

    before_wounds = int(enemy.models[0].wounds or 0)
    with patch("warhammer40k_ai.rules.stratagems_space_marines.dice_module.get_roll", side_effect=[3, 3, 3, 3]):
        ok = sm_player.stratagems.use(
            "WRATH OF THE LION",
            unit=deathwing,
            enemy_unit=enemy,
            dequeue=True,
        )
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert int(before_wounds - int(enemy.models[0].wounds or 0)) == 3
