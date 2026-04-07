from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, abilities=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _deep_strike_ability() -> dict:
    return {
        "name": "Deep Strike",
        "description": "Deep Strike",
        "type": "Core",
        "parameter": "",
    }


def _make_unit(name: str, *, keywords=None, faction_keywords=None, abilities=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords or ["ASTRA MILITARUM"],
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.round_state.shot_this_round = False
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", "Bridgehead Strike")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    am_player = Player("Astra Militarum", control=PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    am_player.command_points = 5
    enemy_player.command_points = 5
    am_army.configure_rule_managers(force=True)
    am_player.stratagems.refresh_available()
    return game, am_player, enemy_player, am_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _norm_name(name: str) -> str:
    return (
        str(name or "")
        .strip()
        .upper()
        .replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Ëœ", "-")
    )


def _pending_by_name(stratagems, name: str):
    target = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(reaction.get("stratagem", "")) == target:
            return reaction
    return None


def test_bridgehead_stratagem_descriptors_registered():
    expected = {
        "000009802002": ("Bellicosa Drop", "deep_strike_min_distance_override_with_no_charge"),
        "000009802003": ("Firing Hot", "conditional_hot_shot_strength_ap_bonus"),
        "000009802004": ("Fire and Relocate", "shoot_after_advance"),
        "000009802005": ("Servo-Designators", "post_shoot_no_cover"),
        "000009802006": ("Aerial Extraction", "enter_strategic_reserves"),
        "000009802007": ("On My Position", "engagement_mortal_wounds_and_self_mortal_wounds"),
    }
    for stratagem_id, (name, effect) in expected.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_bellicosa_drop_sets_override_and_blocks_charge():
    game, am_player, _enemy_player, am_army, enemy_army = _build_game()
    scions = _make_unit(
        "Tempestus Scions",
        keywords=["INFANTRY", "MILITARUM TEMPESTUS"],
        abilities=[_deep_strike_ability()],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(scions)
    enemy_army.add_unit(enemy)
    scions.deployed = False
    scions.set_reserve_status("reserves")
    scions._started_in_reserves = True
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, am_player, "MOVEMENT_PHASE", 0)
    ok = am_player.stratagems.use("BELLICOSA DROP", unit=scions, phase_name="Movement phase")
    assert ok
    assert int(am_player.command_points or 0) == 4
    assert float(scions.get_deep_strike_min_distance_override() or 0.0) == 6.0

    scions.deployed = True
    scions.reserve_status = "deployed"
    scions.arrived_from_reserves_this_turn = True
    _deploy_unit(game, scions, 10.0, 10.0)
    game.phase = SimpleNamespace(name="CHARGE_PHASE")
    game.current_player_index = 0

    assert not scions.can_declare_charge_against(enemy, game)


def test_fire_and_relocate_allows_shooting_after_advance_until_phase_end():
    game, am_player, _enemy_player, am_army, _enemy_army = _build_game()
    unit = _make_unit("Kasrkin", keywords=["INFANTRY", "REGIMENT"])
    am_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    weapon = Wargear(
        {
            "name": "Lasgun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "3",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]

    _set_phase(game, am_player, "SHOOTING_PHASE", 0)
    ok = am_player.stratagems.use("FIRE AND RELOCATE", unit=unit, phase_name="Shooting phase")
    assert ok
    assert unit.can_shoot_after_advance(profile) is True

    game.event_system.publish("phase_end", player=am_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert unit.can_shoot_after_advance(profile) is False
    assert not bool((getattr(unit, "special_rules", {}) or {}).get("bridgehead_fire_and_relocate_active"))


def test_firing_hot_improves_strength_and_ap_within_12_until_phase_end():
    game, am_player, _enemy_player, am_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Tempestus Scions",
        keywords=["INFANTRY", "MILITARUM TEMPESTUS"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(shooter)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    weapon = Wargear(
        {
            "name": "Hot-shot Lasgun",
            "type": "Ranged",
            "range": "18",
            "A": "1",
            "BS_WS": "4+",
            "S": "3",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]

    _set_phase(game, am_player, "SHOOTING_PHASE", 0)
    ok = am_player.stratagems.use("FIRING HOT", unit=shooter, phase_name="Shooting phase")
    assert ok

    wound = profile._wound_target_with_tracking(
        enemy,
        shooter.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound.get("wound"))
    assert any("FIRING HOT" in str(item).upper() for item in list(wound.get("modifiers", []) or []))
    assert int(profile.get_effective_ap(shooter.models[0], enemy) or 0) == -1

    game.event_system.publish("phase_end", player=am_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert int(profile.get_effective_ap(shooter.models[0], enemy) or 0) == 0


def test_servo_designators_queues_and_applies_no_cover_via_decision():
    game, am_player, _enemy_player, am_army, enemy_army = _build_game()
    shooter = _make_unit("Scions", keywords=["INFANTRY", "MILITARUM TEMPESTUS"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(shooter)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    shooter._has_line_of_sight_to_target = lambda _model, _target, _game_map: True
    game.rebuild_entity_registry()

    _set_phase(game, am_player, "SHOOTING_PHASE", 0)
    game.event_system.publish("unit_shooting_resolved", attacker_unit=shooter, hits_by_target={enemy: 1})
    pending = _pending_by_name(am_player.stratagems, "SERVO-DESIGNATORS")
    assert pending is not None

    ok = am_player.stratagems.use(str(pending.get("stratagem", "")), unit=shooter, phase_name="Shooting phase", dequeue=True)
    assert ok
    assert int(am_player.command_points or 0) == 4

    queued = list(game.decision_queue.list() or [])
    assert len(queued) == 1
    request = queued[0]
    assert str(getattr(request, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
    assert str((request.context or {}).get("ability", "") or "") == "post_shoot_no_cover"

    resolve_decision_command(game, request, request.options[0].option_id, player_id=am_player.id)
    assert bool((getattr(enemy, "special_rules", {}) or {}).get("post_shoot_no_cover_active"))


def test_aerial_extraction_queues_at_enemy_fight_phase_end_and_enters_strategic_reserves():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    scions = _make_unit(
        "Tempestus Scions",
        keywords=["INFANTRY", "MILITARUM TEMPESTUS"],
        abilities=[_deep_strike_ability()],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(scions)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, scions, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(am_player.stratagems, "AERIAL EXTRACTION")
    assert pending is not None

    ok = am_player.stratagems.use(str(pending.get("stratagem", "")), unit=scions, phase_name="Fight phase", dequeue=True)
    assert ok
    assert int(am_player.command_points or 0) == 4
    assert str(getattr(scions, "reserve_status", "") or "") == "strategic_reserves"
    assert scions not in list(getattr(game.map, "units", []) or [])


def test_on_my_position_queues_at_enemy_fight_phase_end_and_applies_mortal_wounds():
    game, am_player, enemy_player, am_army, enemy_army = _build_game()
    infantry = _make_unit("Cadian Shock Troops", keywords=["INFANTRY", "REGIMENT"])
    enemy_one = _make_unit("Enemy One", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_two = _make_unit("Enemy Two", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    am_army.add_unit(infantry)
    enemy_army.add_unit(enemy_one)
    enemy_army.add_unit(enemy_two)
    _deploy_unit(game, infantry, 10.0, 10.0)
    _deploy_unit(game, enemy_one, 20.0, 10.0)
    _deploy_unit(game, enemy_two, 30.0, 10.0)
    game.rebuild_entity_registry()

    game.map.get_enemy_units = lambda unit: [enemy_one, enemy_two] if unit is infantry else [infantry]
    game.map.is_within_engagement_range = (
        lambda unit_a, unit_b: (
            unit_a is infantry and unit_b in {enemy_one, enemy_two}
        ) or (
            unit_b is infantry and unit_a in {enemy_one, enemy_two}
        )
    )

    mortal_events: list[tuple[str, int]] = []

    def _record_mortals(target_unit, mortal_wounds, *, game_map=None):
        mortal_events.append((str(getattr(target_unit, "name", "Unit") or "Unit"), int(mortal_wounds or 0)))

    infantry._apply_mortal_wounds_to_unit = _record_mortals

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(am_player.stratagems, "ON MY POSITION")
    assert pending is not None

    with patch(
        "warhammer40k_ai.rules.stratagems_astra_militarum.get_roll",
        side_effect=[2, 4, 1, 1, 2, 3],
    ):
        ok = am_player.stratagems.use(str(pending.get("stratagem", "")), unit=infantry, phase_name="Fight phase", dequeue=True)

    assert ok
    assert int(am_player.command_points or 0) == 4
    assert mortal_events == [("Enemy One", 4), ("Cadian Shock Troops", 6)]
