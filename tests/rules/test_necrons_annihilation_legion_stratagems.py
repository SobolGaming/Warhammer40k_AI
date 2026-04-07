from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count: int = 1,
        wounds: int = 3,
        movement: int = 6,
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(movement)),
                "T": "5",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        normalized_abilities = []
        for ability in list(abilities or []):
            entry = dict(ability)
            entry.setdefault("type", "")
            entry.setdefault("parameter", "")
            normalized_abilities.append(entry)
        self.datasheets_abilities = normalized_abilities
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count: int = 1,
    wounds: int = 3,
    movement: int = 6,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            model_count=model_count,
            wounds=wounds,
            movement=movement,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    necron_army = Army.with_detachment("Necrons", "Annihilation Legion")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    necron_player = Player("Necrons", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)

    necron_player.command_points = 10
    enemy_player.command_points = 10
    return game, necron_player, enemy_player, necron_army, enemy_army


def _reanimation_ability():
    return [{"name": "Reanimation Protocols", "description": "", "type": "Datasheet", "parameter": ""}]


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _finalize_game(game: Game, necron_player: Player, necron_army: Army) -> None:
    game.rebuild_entity_registry()
    necron_army.configure_rule_managers(force=True)
    necron_player.stratagems.refresh_available()


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> SimpleNamespace:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if getattr(request, "decision_type", None) == decision_type:
            return request
    return None


def _first_option(request, predicate):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if predicate(payload):
            return option
    return None


def _shifted_model_positions(unit: Unit, *, x_delta: float = 0.0, y_delta: float = 0.0):
    positions = []
    for model in list(getattr(unit, "models", []) or []):
        x, y, z, facing = model.get_location()
        positions.append(
            {
                "model_id": get_entity_id(model),
                "position": [float(x) + float(x_delta), float(y) + float(y_delta), float(z)],
                "facing": float(facing),
            }
        )
    return positions


def test_annihilation_legion_stratagem_descriptors_registered():
    expected = {
        "000008405006": ("Blood-Fuelled Cruelty", "reactive_normal_move_toward_trigger_unit_with_pre_move_mortal_wounds"),
        "000008405007": ("Insanity's Ire", "reactive_normal_move_toward_trigger_unit"),
        "000008405004": ("Murderous Reanimation", "conditional_trigger_reanimation_protocols"),
        "000008405005": ("Pitiless Hunters", "extend_pile_in_and_consolidate_to_six"),
        "000008405003": (
            "The Spoor of Frailty",
            "hit_bonus_vs_targets_below_starting_strength_and_wound_bonus_vs_targets_below_half_strength",
        ),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_blood_fuelled_cruelty_queues_after_enemy_fall_back_from_started_engaged_unit():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    destroyers = _make_unit(
        "Skorpekh Destroyers",
        keywords=["INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    warriors = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(destroyers)
    necron_army.add_unit(warriors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyers, 10.0, 10.0)
    _deploy_unit(game, warriors, 30.0, 30.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _finalize_game(game, necron_player, necron_army)

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    enemy.models[0].set_location(20.0, 10.0, 0.0, 0.0)
    game.event_system.publish("unit_move_ended", unit=enemy, action="fall_back")

    pending = _pending_by_name(necron_player.stratagems, "BLOOD-FUELLED CRUELTY")
    assert pending is not None
    candidates = list(pending.get("candidates") or [])
    assert destroyers in candidates
    assert warriors not in candidates


def test_blood_fuelled_cruelty_use_applies_mortal_wounds_and_queues_reactive_move():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    destroyers = _make_unit(
        "Skorpekh Destroyers",
        keywords=["INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(destroyers)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyers, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _finalize_game(game, necron_player, necron_army)

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    enemy.models[0].set_location(20.0, 10.0, 0.0, 0.0)
    game.event_system.publish("unit_move_ended", unit=enemy, action="fall_back")

    with patch.object(destroyers, "_apply_mortal_wounds_to_unit") as mocked_mortals:
        with patch("warhammer40k_ai.rules.stratagems_necrons.dice_module.get_roll", return_value=6):
            ok = necron_player.stratagems.use("BLOOD-FUELLED CRUELTY", unit=destroyers, dequeue=True)

    assert ok is True
    mocked_mortals.assert_called_once()
    called_enemy = mocked_mortals.call_args.args[0]
    called_amount = mocked_mortals.call_args.args[1]
    assert called_enemy is enemy
    assert int(called_amount) == 3

    request = _first_request(game, DECISION_MOVE_UNIT)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "annihilation_blood_fuelled_cruelty"
    assert str(context.get("annihilation_legion_target_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    assert str(context.get("reactive_move_movement_type", "") or "").strip().lower() == "move"
    assert int(context.get("max_distance", 0) or 0) == int(getattr(destroyers, "movement", 0) or 0)


def test_insanitys_ire_queues_when_enemy_shooting_destroys_models_in_eligible_unit():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    destroyers = _make_unit(
        "Lokhust Destroyers",
        keywords=["INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(destroyers)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyers, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, necron_player, necron_army)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=enemy,
        killing_models_by_target={destroyers: [object()]},
    )

    pending = _pending_by_name(necron_player.stratagems, "INSANITY'S IRE")
    assert pending is not None
    assert destroyers in list(pending.get("candidates") or [])


def test_insanitys_ire_move_request_enforces_closest_possible_end_position():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    destroyers = _make_unit(
        "Lokhust Destroyers",
        keywords=["INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(destroyers)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyers, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, necron_player, necron_army)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=enemy,
        killing_models_by_target={destroyers: [object()]},
    )

    assert necron_player.stratagems.use("INSANITY'S IRE", unit=destroyers, dequeue=True)
    request = _first_request(game, DECISION_MOVE_UNIT)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("reactive_move_kind", "") or "") == "annihilation_insanitys_ire"
    assert str(context.get("annihilation_legion_target_unit_id", "") or "") == str(get_entity_id(enemy) or "")

    confirm = _first_option(request, lambda payload: str(payload.get("action", "")) == "confirm")
    assert confirm is not None
    result = resolve_decision_command(
        game,
        request,
        confirm.option_id,
        player_id=necron_player.id,
        result_payload={"model_positions": _shifted_model_positions(destroyers, x_delta=1.0)},
    )
    assert bool(getattr(result, "ok", False)) is False
    assert any("Insanity's Ire" in str(error) for error in list(getattr(result, "errors", []) or []))


def test_murderous_reanimation_queues_after_enemy_drops_below_half_and_reanimates():
    game, necron_player, _enemy_player, necron_army, enemy_army = _build_game()
    destroyers = _make_unit(
        "Flayed Ones",
        keywords=["INFANTRY", "FLAYED ONES"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy.is_below_half_strength = lambda: False
    necron_army.add_unit(destroyers)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyers, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    _finalize_game(game, necron_player, necron_army)

    _set_phase(game, necron_player, "FIGHT_PHASE", 0)
    game.event_system.publish("fight_targets_selected", attacking_unit=destroyers, target_units=[enemy])
    enemy.is_below_half_strength = lambda: True
    game.event_system.publish("fight_attacks_resolved", unit=destroyers, target_unit=enemy, killing_models_by_target={})

    pending = _pending_by_name(necron_player.stratagems, "MURDEROUS REANIMATION")
    assert pending is not None

    with patch.object(destroyers, "apply_reanimation_protocols") as mocked_reanimation:
        with patch("warhammer40k_ai.rules.stratagems_necrons.dice_module.get_roll", return_value=3):
            ok = necron_player.stratagems.use("MURDEROUS REANIMATION", unit=destroyers, candidates=[destroyers], dequeue=True)

    assert ok is True
    mocked_reanimation.assert_called_once()
    assert int(mocked_reanimation.call_args.args[0]) == 3
    assert str(mocked_reanimation.call_args.kwargs.get("roll_expr", "") or "") == "D3"


def test_pitiless_hunters_extends_fight_moves_until_phase_end():
    game, necron_player, _enemy_player, necron_army, _enemy_army = _build_game()
    destroyers = _make_unit(
        "Skorpekh Destroyers",
        keywords=["INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    necron_army.add_unit(destroyers)
    _deploy_unit(game, destroyers, 10.0, 10.0)
    _finalize_game(game, necron_player, necron_army)

    phase = _set_phase(game, necron_player, "FIGHT_PHASE", 0)
    ok = necron_player.stratagems.use("PITILESS HUNTERS", unit=destroyers, phase_name="Fight phase")
    assert ok is True
    assert float(destroyers.get_fight_phase_move_distance_override("pile_in") or 0.0) == 6.0
    assert float(destroyers.get_fight_phase_move_distance_override("consolidate") or 0.0) == 6.0

    game.event_system.publish("phase_end", player=necron_player, phase=phase)
    assert destroyers.get_fight_phase_move_distance_override("pile_in") is None
    assert destroyers.get_fight_phase_move_distance_override("consolidate") is None


def test_spoor_of_frailty_grants_hit_and_wound_bonuses_and_cleans_up():
    game, necron_player, _enemy_player, necron_army, enemy_army = _build_game()
    destroyers = _make_unit(
        "Skorpekh Destroyers",
        keywords=["INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy.is_below_starting_strength = lambda: True
    enemy.is_below_half_strength = lambda: True
    necron_army.add_unit(destroyers)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyers, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    _finalize_game(game, necron_player, necron_army)

    phase = _set_phase(game, necron_player, "FIGHT_PHASE", 0)
    ok = necron_player.stratagems.use("THE SPOOR OF FRAILTY", unit=destroyers, phase_name="Fight phase")
    assert ok is True

    hit_mods = destroyers.get_unit_hit_reroll_modifiers("melee", target=enemy)
    wound_mods = destroyers.get_unit_wound_reroll_modifiers("melee", target=enemy)
    assert int(hit_mods.get("hit", 0) or 0) == 1
    assert int(wound_mods.get("wound", 0) or 0) == 1

    game.event_system.publish("phase_end", player=necron_player, phase=phase)
    cleared_hit_mods = destroyers.get_unit_hit_reroll_modifiers("melee", target=enemy)
    cleared_wound_mods = destroyers.get_unit_wound_reroll_modifiers("melee", target=enemy)
    assert int(cleared_hit_mods.get("hit", 0) or 0) == 0
    assert int(cleared_wound_mods.get("wound", 0) or 0) == 0
