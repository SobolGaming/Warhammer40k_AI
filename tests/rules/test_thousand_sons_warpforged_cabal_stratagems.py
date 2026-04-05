from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _HashableNamespace(SimpleNamespace):
    __hash__ = object.__hash__


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        toughness: str = "8",
        wounds: str = "10",
        save: str = "3",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
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
                "T": str(toughness),
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": "3",
                "base_size": "60mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Thousand Sons",
    keywords=None,
    faction_keywords=None,
    toughness: str = "8",
    wounds: str = "10",
    save: str = "3",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            save=save,
        )
    )


def _make_profile(
    *,
    name: str = "Warp Cannon",
    range_val: str = "24",
    strength: str = "4",
    damage: str = "1",
) -> WargearProfile:
    parent = SimpleNamespace(
        name=name,
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": str(range_val),
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def _aura_stub(*, hit: int = 0, wound: int = 0):
    return SimpleNamespace(
        hit=int(hit),
        wound=int(wound),
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    ts_army = Army("Thousand Sons", "Warpforged Cabal")
    ts_army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ts_player = Player("TS", control=PlayerControl.LOCAL, army=ts_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ts_player)
    game.add_player(enemy_player)

    ts_player.command_points = 10
    enemy_player.command_points = 10

    ts_army.configure_rule_managers(force=True)
    enemy_army.configure_rule_managers(force=True)
    _refresh(game, ts_player, enemy_player)
    return game, ts_player, enemy_player, ts_army, enemy_army


def _refresh(game: Game, *players: Player) -> None:
    for player in players:
        player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    game.refresh_rule_subscribers()


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = getattr(BattleRoundPhases, str(phase_name or "").strip().upper())
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _add_objective(game: Game, controller, *, x: float, y: float, name: str = "Objective"):
    location = _HashableNamespace(
        x=float(x),
        y=float(y),
        z=0.0,
        control_radius=3.0,
        removed=False,
        controlling_player=controller,
        sticky_controller=None,
        sticky_source="",
    )

    def _set_sticky_control(player, source: str = "") -> None:
        location.sticky_controller = player
        location.sticky_source = str(source or "")
        location.controlling_player = player

    location.set_sticky_control = _set_sticky_control
    location.update_control = lambda _game: None
    objective = SimpleNamespace(
        id=f"obj_{name.lower().replace(' ', '_')}",
        name=name,
        location=location,
    )
    objectives = list(getattr(game.map, "objectives", []) or [])
    objectives.append(objective)
    game.map.objectives = objectives
    return objective


def _pending_by_name(stratagems, name: str):
    name_u = str(name or "").strip().upper()
    return [
        reaction
        for reaction in list(stratagems.get_pending_reactions() or [])
        if str(reaction.get("stratagem", "") or "").strip().upper() == name_u
    ]


def test_warpforged_cabal_stratagem_descriptors_registered():
    expected = {
        "000010210003": ("Mutate Landscape", "sticky_objective_with_move_end_mortal_wound_trap"),
        "000010210004": ("Cyberspirit Machinations", "eligible_to_shoot_and_charge_after_fall_back"),
        "000010210005": ("Malevolent Animus", "ignore_characteristic_roll_and_test_modifiers_except_saves"),
        "000010210006": ("Ensorcelled Infusion", "ranged_psychic_and_wound_bonus"),
        "000010210007": ("Warpflame Gargoyles", "charge_end_mortal_wound_burst_and_battleshock"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_mutate_landscape_queues_and_triggers_move_end_mortal_wounds():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    psyker = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
        toughness="4",
        wounds="4",
    )
    enemy = _make_unit(
        "Enemy Raiders",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
        wounds="6",
    )
    ts_army.add_unit(psyker)
    enemy_army.add_unit(enemy)
    _refresh(game, ts_player, enemy_player)
    _deploy_unit(game, psyker, 15.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    objective = _add_objective(game, ts_player, x=15.0, y=10.0, name="Center")

    recorded: list[int] = []
    enemy._apply_mortal_wounds_to_unit = lambda unit, amount, game_map=None: recorded.append(int(amount))
    enemy.is_within_objective_range = lambda location: location is objective.location

    _set_phase(game, ts_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(ts_player.stratagems, "MUTATE LANDSCAPE")
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "MUTATE LANDSCAPE",
        unit=psyker,
        objective=objective,
        phase_name="Command phase",
        dequeue=True,
    )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9
    assert objective.location.sticky_controller is ts_player
    assert objective.location.thousand_sons_warpforged_mutate_landscape_sources[str(ts_player.id)] == "MUTATE LANDSCAPE"

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    with patch("warhammer40k_ai.rules.stratagems_thousand_sons.dice_module.get_roll", side_effect=[4, 2]):
        game.event_system.publish("unit_move_ended", unit=enemy, action="normal_move")

    assert recorded == [2]


def test_malevolent_animus_ignores_modifiers_and_clears_next_command_phase():
    game, ts_player, _enemy_player, ts_army, enemy_army = _build_game()
    vehicle = _make_unit(
        "Forgefiend",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
    )
    psyker = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
        toughness="4",
        wounds="4",
    )
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
        wounds="6",
    )
    ts_army.add_unit(vehicle)
    ts_army.add_unit(psyker)
    enemy_army.add_unit(target)
    _refresh(game, ts_player)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _deploy_unit(game, psyker, 14.0, 10.0)
    _deploy_unit(game, target, 20.0, 10.0)

    _set_phase(game, ts_player, "COMMAND_PHASE", 0)
    ok = ts_player.stratagems.use(
        "MALEVOLENT ANIMUS",
        unit=vehicle,
        phase_name="Command phase",
    )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9

    ignore_rule = vehicle.get_move_advance_charge_modifier_ignore_rule()
    assert ignore_rule is not None
    assert ignore_rule.get("forced_choice") == "ignore_all"

    profile = _make_profile()
    hit = profile._hit_target_with_tracking(
        target,
        vehicle.models[0],
        {"_aura_attack_mods": _aura_stub(hit=-1)},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )

    assert hit["hit"] is True
    assert int(hit.get("hit_modifier_total", 0) or 0) == 0

    game.turn = 2
    _set_phase(game, ts_player, "COMMAND_PHASE", 0)
    assert bool(vehicle.special_rules.get("thousand_sons_malevolent_animus_active")) is False


def test_cyberspirit_machinations_queues_and_grants_shoot_and_charge_after_fall_back():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    vehicle = _make_unit(
        "Forgefiend",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
    )
    psyker = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
        toughness="4",
        wounds="4",
    )
    ts_army.add_unit(vehicle)
    ts_army.add_unit(psyker)
    _refresh(game, ts_player)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _deploy_unit(game, psyker, 14.0, 10.0)
    vehicle.round_state.fell_back_this_round = True

    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=vehicle, action="fall_back")
    pending = _pending_by_name(ts_player.stratagems, "CYBERSPIRIT MACHINATIONS")
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "CYBERSPIRIT MACHINATIONS",
        unit=vehicle,
        phase_name="Movement phase",
        dequeue=True,
    )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9
    assert vehicle.has_fell_back_and_shoot() is True
    assert vehicle.can_charge_after_fall_back() is True

    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.event_system.publish("phase_end", player=ts_player, phase=game.phase)
    assert vehicle.has_fell_back_and_shoot() is False
    assert vehicle.can_charge_after_fall_back() is False


def test_ensorcelled_infusion_grants_psychic_and_wound_bonus_until_phase_end():
    game, ts_player, _enemy_player, ts_army, enemy_army = _build_game()
    vehicle = _make_unit(
        "Forgefiend",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
    )
    psyker = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
        toughness="4",
        wounds="4",
    )
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
        wounds="6",
    )
    ts_army.add_unit(vehicle)
    ts_army.add_unit(psyker)
    enemy_army.add_unit(target)
    _refresh(game, ts_player)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _deploy_unit(game, psyker, 14.0, 10.0)
    _deploy_unit(game, target, 18.0, 10.0)

    _set_phase(game, ts_player, "SHOOTING_PHASE", 0)
    ok = ts_player.stratagems.use(
        "ENSORCELLED INFUSION",
        unit=vehicle,
        phase_name="Shooting phase",
    )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9

    profile = _make_profile(strength="4")
    assert profile._is_psychic_attack(vehicle.models[0]) is True

    wound = profile._wound_target_with_tracking(
        target,
        vehicle.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert wound["wound"] is True
    assert any("ENSORCELLED INFUSION" in str(entry) for entry in list(wound.get("special_effects", [])) + list(wound.get("modifiers", [])))

    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.event_system.publish("phase_end", player=ts_player, phase=game.phase)
    assert profile._is_psychic_attack(vehicle.models[0]) is False


def test_warpflame_gargoyles_queues_after_enemy_charge_and_forces_battleshock():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    vehicle = _make_unit(
        "Forgefiend",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
    )
    enemy = _make_unit(
        "Enemy Chargers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
        wounds="6",
    )
    ts_army.add_unit(vehicle)
    enemy_army.add_unit(enemy)
    _refresh(game, ts_player, enemy_player)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)

    game.map.is_within_engagement_range = lambda _a, _b: True
    recorded_mortals: list[int] = []
    battle_shock_turns: list[int] = []
    vehicle._apply_mortal_wounds_to_unit = lambda unit, amount, game_map=None: recorded_mortals.append(int(amount))
    enemy.take_battle_shock_test = lambda turn: battle_shock_turns.append(int(turn))

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="charge")
    pending = _pending_by_name(ts_player.stratagems, "WARPFLAME GARGOYLES")
    assert len(pending) == 1

    with patch(
        "warhammer40k_ai.rules.stratagems_thousand_sons.dice_module.get_roll",
        side_effect=[5, 5, 4, 3, 2, 1],
    ):
        ok = ts_player.stratagems.use(
            "WARPFLAME GARGOYLES",
            unit=vehicle,
            attacking_unit=enemy,
            phase_name="Charge phase",
            dequeue=True,
        )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9
    assert recorded_mortals == [2]
    assert battle_shock_turns == [1]
