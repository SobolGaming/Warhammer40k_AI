from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: int = 3,
        base_size: str = "32mm",
    ) -> None:
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ASTRA MILITARUM"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10" if "VEHICLE" in set(self.keywords) else "6",
                "T": "10" if "VEHICLE" in set(self.keywords) else "4",
                "Sv": "3" if "VEHICLE" in set(self.keywords) else "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "3" if "VEHICLE" in set(self.keywords) else "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "",
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
    keywords=None,
    faction_keywords=None,
    wounds: int = 3,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            base_size=base_size,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.round_state.shot_this_round = False
    unit.round_state.moved_this_round = False
    unit.round_state.advanced_this_round = False
    unit.round_state.fell_back_this_round = False
    unit.round_state.attempted_charge_this_round = False
    return unit


def _weapon(
    name: str,
    *,
    range_text: str = "24",
    ap: str = "0",
    damage: str = "1",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": str(range_text),
            "A": "1",
            "BS_WS": "4+",
            "S": "8",
            "AP": str(ap),
            "D": str(damage),
            "description": str(description),
        }
    )


def _build_game(*, am_control: PlayerControl = PlayerControl.LOCAL):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    am_army = Army.with_detachment("Astra Militarum", "Hammer of the Emperor")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    am_player = Player("Astra Militarum", control=am_control, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    am_player.command_points = 10
    enemy_player.command_points = 10
    return game, am_player, enemy_player, am_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


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


def test_hammer_of_the_emperor_stratagem_descriptors_registered():
    expected = {
        "000009866002": ("Final Hour", "ranged_weapons_gain_hazardous_and_ignore_ballistic_skill_and_hit_modifiers"),
        "000009866003": ("Blazing Advance", "shoot_after_advance"),
        "000009866004": ("Tactical Withdrawal", "shoot_after_fall_back"),
        "000009866005": ("Crash Through", "move_horizontally_through_terrain"),
        "000009866006": ("Furious Cannonade", "ranged_ap_bonus_within_12"),
        "000009866007": ("Ablative Plating", "defensive_damage_reduction"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_ablative_plating_queues_and_reduces_damage_until_phase_end():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    vehicle = _make_unit("Leman Russ", keywords=["VEHICLE", "SQUADRON"], wounds=12, base_size="100mm")
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(vehicle)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _deploy_unit(game, attacker, 24.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[vehicle])
    pending = _pending_by_name(am_player.stratagems, "ABLATIVE PLATING")
    assert pending is not None
    assert vehicle in list(pending.get("candidates") or [])

    ok = am_player.stratagems.use("ABLATIVE PLATING", unit=vehicle, phase_name="Shooting phase", dequeue=True)
    assert ok is True
    assert int(am_player.command_points or 0) == 8

    entries = list(vehicle.special_rules.get("defensive_damage_reductions", []) or [])
    assert any(
        int(entry.get("value", 0) or 0) == 1
        and str(entry.get("expires_phase", "") or "").strip().upper() == "SHOOTING_PHASE"
        for entry in entries
        if isinstance(entry, dict)
    )

    profile = _weapon("Enemy Cannon", damage="2").profiles["default"]
    target_model = vehicle.models[0]
    target_model.wounds = 12
    reduced = profile._damage_target_with_tracking(target_model, attacker.models[0], {}, allow_rerolls=False)
    assert int(reduced.get("damage_applied", 0) or 0) == 1

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    target_model.wounds = 12
    normal = profile._damage_target_with_tracking(target_model, attacker.models[0], {}, allow_rerolls=False)
    assert int(normal.get("damage_applied", 0) or 0) == 2


def test_blazing_advance_queues_after_advance_and_allows_shooting():
    game, am_player, _enemy_player, am_army, enemy_army = _build_game()
    unit = _make_unit("Scout Sentinel", keywords=["SQUADRON", "VEHICLE"], wounds=7, base_size="80mm")
    am_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, _enemy_player])

    profile = _weapon("Multilaser").profiles["default"]
    _set_phase(game, am_player, "MOVEMENT_PHASE", 0)
    unit.round_state.advanced_this_round = True
    game.event_system.publish("unit_move_ended", unit=unit, action="advance")

    pending = _pending_by_name(am_player.stratagems, "BLAZING ADVANCE")
    assert pending is not None
    assert unit in list(pending.get("candidates") or [])

    ok = am_player.stratagems.use("BLAZING ADVANCE", unit=unit, phase_name="Movement phase", dequeue=True)
    assert ok is True
    assert int(am_player.command_points or 0) == 9
    assert unit.can_shoot_after_advance(profile) is True


def test_tactical_withdrawal_queues_after_fall_back_and_allows_shooting():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    unit = _make_unit("Hellhound", keywords=["SQUADRON", "VEHICLE"], wounds=11, base_size="100mm")
    am_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    profile = _weapon("Inferno Cannon").profiles["default"]
    _set_phase(game, am_player, "MOVEMENT_PHASE", 0)
    unit.round_state.fell_back_this_round = True
    game.event_system.publish("unit_move_ended", unit=unit, action="fall_back")

    pending = _pending_by_name(am_player.stratagems, "TACTICAL WITHDRAWAL")
    assert pending is not None
    assert unit in list(pending.get("candidates") or [])

    ok = am_player.stratagems.use("TACTICAL WITHDRAWAL", unit=unit, phase_name="Movement phase", dequeue=True)
    assert ok is True
    assert int(am_player.command_points or 0) == 9
    assert unit.can_shoot_after_fall_back(profile) is True


def test_crash_through_allows_vehicle_to_move_horizontally_through_terrain_until_phase_end():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    vehicle = _make_unit("Rogal Dorn", keywords=["VEHICLE", "SQUADRON"], wounds=18, base_size="130mm")
    am_army.add_unit(vehicle)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    _set_phase(game, am_player, "MOVEMENT_PHASE", 0)
    ok = am_player.stratagems.use("CRASH THROUGH", unit=vehicle, phase_name="Movement phase")
    assert ok is True
    assert int(am_player.command_points or 0) == 9

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=vehicle)
    charge_rules = get_validation_rules(MovementType.CHARGE, moving_unit=vehicle)
    assert bool(move_rules.get("can_move_through_terrain")) is True
    assert bool(charge_rules.get("can_move_through_terrain")) is True

    game.event_system.publish("phase_end", player=am_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    move_rules_after = get_validation_rules(MovementType.MOVE, moving_unit=vehicle)
    charge_rules_after = get_validation_rules(MovementType.CHARGE, moving_unit=vehicle)
    assert bool(move_rules_after.get("can_move_through_terrain")) is False
    assert bool(charge_rules_after.get("can_move_through_terrain")) is False


def test_final_hour_grants_hazardous_and_ignores_ballistic_and_hit_modifiers():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    squadron = _make_unit("Scout Sentinel", keywords=["SQUADRON", "VEHICLE"], wounds=7, base_size="80mm")
    enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    squadron.is_below_half_strength = lambda: True
    am_army.add_unit(squadron)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, squadron, 10.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    normal_profile = _weapon("Autocannon").profiles["default"]
    one_shot_profile = _weapon("Hunter-killer Missile").profiles["default"]
    one_shot_profile.get_keywords = lambda: ["One Shot"]

    _set_phase(game, am_player, "COMMAND_PHASE", 0)
    ok = am_player.stratagems.use("FINAL HOUR", unit=squadron, phase_name="Command phase")
    assert ok is True
    assert int(am_player.command_points or 0) == 9

    mgr = am_army.astra_militarum_detachments
    applies, _source = mgr.hammer_of_the_emperor_final_hour_hazardous_applies(
        squadron.models[0],
        weapon_profile=normal_profile,
        game=game,
    )
    assert applies is True
    one_shot_applies, _source = mgr.hammer_of_the_emperor_final_hour_hazardous_applies(
        squadron.models[0],
        weapon_profile=one_shot_profile,
        game=game,
    )
    assert one_shot_applies is False

    rule = normal_profile._ignore_hit_modifier_rule(squadron.models[0], target_unit=enemy)
    assert rule is not None
    assert str(rule.get("attack_type", "") or "") == "ranged"
    assert "ballistic" in set(rule.get("skill_kinds", set()) or set())
    assert bool(rule.get("allow_hit")) is True

    game.turn = 2
    am_army.on_battle_round_start(2)
    applies_after, _source = mgr.hammer_of_the_emperor_final_hour_hazardous_applies(
        squadron.models[0],
        weapon_profile=normal_profile,
        game=game,
    )
    assert applies_after is False
    assert normal_profile._ignore_hit_modifier_rule(squadron.models[0], target_unit=enemy) is None


def test_furious_cannonade_improves_ap_within_twelve_only():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    squadron = _make_unit("Leman Russ", keywords=["SQUADRON", "VEHICLE"], wounds=12, base_size="100mm")
    enemy_near = _make_unit("Enemy Near", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_far = _make_unit("Enemy Far", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(squadron)
    enemy_army.add_unit(enemy_near)
    enemy_army.add_unit(enemy_far)
    _deploy_unit(game, squadron, 10.0, 10.0)
    _deploy_unit(game, enemy_near, 20.0, 10.0)
    _deploy_unit(game, enemy_far, 40.0, 10.0)
    _finalize_game(game, am_army, enemy_army, players=[am_player, enemy_player])

    profile = _weapon("Battle Cannon", ap="0").profiles["default"]
    _set_phase(game, am_player, "SHOOTING_PHASE", 0)
    ok = am_player.stratagems.use("FURIOUS CANNONADE", unit=squadron, phase_name="Shooting phase")
    assert ok is True
    assert int(am_player.command_points or 0) == 9

    assert int(profile.get_effective_ap(squadron.models[0], enemy_near) or 0) == -1
    assert int(profile.get_effective_ap(squadron.models[0], enemy_far) or 0) == 0

    game.event_system.publish("phase_end", player=am_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert int(profile.get_effective_ap(squadron.models[0], enemy_near) or 0) == 0
