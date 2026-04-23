from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
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
                "OC": "1",
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
            wounds=wounds,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Saga of the Hunter")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Wolves", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sm_player.command_points = 10
    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 2.0, float(y), 0.0, 0.0)
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


def _ranged_wargear(name: str = "Bolt Rifle") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _make_profile(*, is_melee: bool) -> WargearProfile:
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
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_saga_of_the_hunter_stratagem_descriptors_exist():
    expected = {
        "000010262002": ("Hunters' Trail", "extend_pile_in_and_consolidate_to_six_and_ignore_closest_model_requirement"),
        "000010262003": ("Territorial Advantage", "sticky_objective"),
        "000010262004": ("Overwhelming Onslaught", "attacking_enemy_hit_penalty"),
        "000010262005": ("Chosen Prey", "shoot_and_charge_after_fall_back"),
        "000010262006": ("Bounding Advance", "move_through_models_with_titanic_block_and_movement_phase_engagement_pass"),
        "000010262007": ("Marked for Destruction", "shared_target_lock_and_reroll_wound_ones"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        descriptor = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert descriptor is not None
        assert descriptor.name == expected_name
        assert descriptor.effect == expected_effect


def test_saga_of_the_hunter_phase_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    hunters = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    shooters_a = _make_unit(
        "Long Fangs A",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    shooters_b = _make_unit(
        "Long Fangs B",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    beast = _make_unit(
        "Fenrisian Wolves",
        keywords=["BEASTS", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        model_count=2,
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    objective = _make_objective("Midfield", 10.0, 10.0)
    objective.location.controlling_player = sm_player

    for shooter in (shooters_a, shooters_b):
        shooter.models[0].wargear = [_ranged_wargear()]

    sm_army.add_unit(hunters)
    sm_army.add_unit(shooters_a)
    sm_army.add_unit(shooters_b)
    sm_army.add_unit(beast)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, hunters, 10.0, 10.0)
    _deploy_unit(game, shooters_a, 10.0, 14.0)
    _deploy_unit(game, shooters_b, 10.0, 18.0)
    _deploy_unit(game, beast, 14.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "BOUNDING ADVANCE") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    hunters.round_state.fell_back_this_round = True
    game.event_system.publish("unit_move_ended", unit=hunters, action="fall_back")
    assert _pending_by_name(sm_player.stratagems, "CHOSEN PREY") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    marked = _pending_by_name(sm_player.stratagems, "MARKED FOR DESTRUCTION")
    assert marked is not None
    assert int(marked.get("max_units", 0) or 0) == 2
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "HUNTERS' TRAIL") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    game.map.is_within_engagement_range = lambda first, second: {first, second} == {enemy, beast}
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[hunters])
    assert _pending_by_name(sm_player.stratagems, "OVERWHELMING ONSLAUGHT") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    enemy.models = []
    game.event_system.publish(
        "fight_attacks_resolved",
        unit=hunters,
        target_unit=enemy,
        killing_models_by_target={enemy: {object()}},
    )
    assert _pending_by_name(sm_player.stratagems, "TERRITORIAL ADVANTAGE") is not None


def test_bounding_advance_applies_and_cleans_up_for_movement_phase():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    hunters = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    sm_army.add_unit(hunters)
    _deploy_unit(game, hunters, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    ok = sm_player.stratagems.use("BOUNDING ADVANCE", unit=hunters, phase_name="Movement phase")
    assert ok is True
    sr = dict(getattr(hunters, "special_rules", {}) or {})
    assert bool(sr.get("space_marines_bounding_advance_active")) is True
    assert set(sr.get("bearer_unit_phase_move_models_only_types", []) or []) >= {"move", "advance", "fall_back"}
    assert set(sr.get("bearer_unit_phase_move_models_only_block_titanic_types", []) or []) >= {
        "move",
        "advance",
        "fall_back",
    }
    assert set(sr.get("bearer_unit_phase_move_engagement_types", []) or []) >= {"move", "advance", "fall_back"}

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=hunters)
    assert bool(move_rules.get("can_move_through_enemy_models")) is True
    assert bool(move_rules.get("block_titanic_models")) is True
    assert bool(move_rules.get("cannot_move_within_engagement_range", True)) is False
    assert bool(move_rules.get("cannot_end_in_engagement_range")) is True

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    sr_after = dict(getattr(hunters, "special_rules", {}) or {})
    assert bool(sr_after.get("space_marines_bounding_advance_active", False)) is False
    assert "bearer_unit_phase_move_models_only_types" not in sr_after


def test_chosen_prey_grants_shoot_and_charge_after_fall_back_until_turn_end():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    hunters = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    sm_army.add_unit(hunters)
    _deploy_unit(game, hunters, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    ok = sm_player.stratagems.use("CHOSEN PREY", unit=hunters, action="fall_back", phase_name="Movement phase")
    assert ok is True
    assert hunters.has_fell_back_and_shoot() is True
    assert hunters.can_charge_after_fall_back() is True

    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    assert hunters.has_fell_back_and_shoot() is False
    assert hunters.can_charge_after_fall_back() is False


def test_hunters_trail_sets_fight_move_override_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    hunters = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    sm_army.add_unit(hunters)
    _deploy_unit(game, hunters, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    assert sm_player.stratagems.can_use("HUNTERS' TRAIL", unit=hunters, phase_name="Fight phase") is True
    ok = sm_player.stratagems.use("HUNTERS' TRAIL", unit=hunters, phase_name="Fight phase")
    assert ok is True
    assert hunters.get_fight_phase_move_distance_override("pile_in") == 6.0
    assert hunters.get_fight_phase_move_distance_override("consolidate") == 6.0

    pile_in_rules = get_validation_rules(MovementType.PILE_IN, moving_unit=hunters)
    assert bool(pile_in_rules.get("must_end_as_close_as_possible_to_closest_enemy_unit")) is True
    assert bool(pile_in_rules.get("must_end_closer_to_enemies", True)) is False

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    assert hunters.get_fight_phase_move_distance_override("pile_in") is None


def test_marked_for_destruction_locks_targets_and_grants_wound_reroll_ones():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    shooters = []
    for name, y in (("Long Fangs A", 10.0), ("Long Fangs B", 14.0)):
        unit = _make_unit(
            name,
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        unit.models[0].wargear = [_ranged_wargear()]
        sm_army.add_unit(unit)
        _deploy_unit(game, unit, 10.0, y)
        shooters.append(unit)
    marked_enemy = _make_unit("Marked Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    other_enemy = _make_unit("Other Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_army.add_unit(marked_enemy)
    enemy_army.add_unit(other_enemy)
    _deploy_unit(game, marked_enemy, 18.0, 12.0)
    _deploy_unit(game, other_enemy, 20.0, 12.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use(
        "MARKED FOR DESTRUCTION",
        units=list(shooters),
        enemy_unit=marked_enemy,
        phase_name="Shooting phase",
    )
    assert ok is True

    profile = next(iter(shooters[0].models[0].wargear[0].profiles.values()))
    valid_target = shooters[0]._validate_shooting_declaration(profile, marked_enemy, [shooters[0].models[0]], game.map)
    invalid_target = shooters[0]._validate_shooting_declaration(profile, other_enemy, [shooters[0].models[0]], game.map)
    assert bool(valid_target.get("valid", False)) is True
    assert bool(invalid_target.get("valid", True)) is False

    wound_mods = shooters[0].get_unit_wound_reroll_modifiers("ranged", target=marked_enemy)
    assert 1 in set(wound_mods.get("reroll_wound_values", ()) or ())

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    sr_after = dict(getattr(shooters[0], "special_rules", {}) or {})
    assert bool(sr_after.get("space_marines_marked_for_destruction_active", False)) is False


def test_overwhelming_onslaught_applies_enemy_hit_penalty_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    defenders_a = _make_unit(
        "Grey Hunters A",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    defenders_b = _make_unit(
        "Grey Hunters B",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    attacker = _make_unit("Enemy Assault Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(defenders_a)
    sm_army.add_unit(defenders_b)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defenders_a, 10.0, 10.0)
    _deploy_unit(game, defenders_b, 14.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()
    game.map.is_within_engagement_range = (
        lambda first, second: {first, second} in ({defenders_a, attacker}, {defenders_b, attacker})
    )

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    ok = sm_player.stratagems.use(
        "OVERWHELMING ONSLAUGHT",
        units=[defenders_a, defenders_b],
        enemy_unit=attacker,
        phase_name="Fight phase",
    )
    assert ok is True

    profile = _make_profile(is_melee=True)
    result = profile._hit_target_with_tracking(
        defenders_a,
        attacker.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(result.get("hit", True)) is False
    assert any("OVERWHELMING ONSLAUGHT" in str(mod).upper() for mod in list(result.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    sr_after = dict(getattr(attacker, "special_rules", {}) or {})
    assert bool(sr_after.get("space_marines_overwhelming_onslaught_active", False)) is False


def test_territorial_advantage_makes_objective_sticky():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    hunters = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    objective = _make_objective("Midfield", 10.0, 10.0)
    objective.location.controlling_player = sm_player

    sm_army.add_unit(hunters)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, hunters, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.8, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    enemy.models = []
    ok = sm_player.stratagems.use(
        "TERRITORIAL ADVANTAGE",
        unit=hunters,
        objective=objective,
        killing_models_by_target={enemy: {object()}},
        phase_name="Fight phase",
    )
    assert ok is True
    assert objective.location.sticky_controller is sm_player
    assert objective.location.controlling_player is sm_player
