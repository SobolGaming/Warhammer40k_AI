from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 3,
        move: int = 6,
    ):
        self.id = str(name).lower().replace(" ", "_")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(move)),
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
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
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 3,
    move: int = 6,
) -> Unit:
    unit = Unit(
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
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _norm_name(name: str) -> str:
    return "".join(ch for ch in str(name or "").upper() if ch.isalnum())


def _make_profile(*, melee: bool) -> object:
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    csm_army = Army("Chaos Space Marines", "Dread Talons")
    csm_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    csm_player = Player("CSM", control=PlayerControl.LOCAL, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)

    game.current_player_index = 0
    game.turn = 1
    game.phase = SimpleNamespace(name="COMMAND_PHASE")

    csm_player.command_points = 10
    enemy_player.command_points = 10

    csm_army.configure_rule_managers(force=True)
    csm_player.stratagems.refresh_available()
    _inject_dread_talons_stratagems(csm_player)
    csm_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, csm_player, enemy_player, csm_army, enemy_army


def _inject_dread_talons_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        (
            "000008973002",
            "Depthless Cruelty",
            1,
            "Your turn",
            "Fight phase",
            "Dread Talons - Battle Tactic Stratagem",
        ),
        (
            "000008973003",
            "Bloody Example",
            1,
            "Your turn",
            "Fight phase",
            "Dread Talons - Strategic Ploy Stratagem",
        ),
        (
            "000008973004",
            "Pitiless Hunters",
            1,
            "Your turn",
            "Shooting phase",
            "Dread Talons - Battle Tactic Stratagem",
        ),
        (
            "000008973005",
            "Relentless Terror",
            1,
            "Your turn",
            "Movement phase",
            "Dread Talons - Strategic Ploy Stratagem",
        ),
        (
            "000008973006",
            "Screaming Descent",
            1,
            "Your turn",
            "Movement phase",
            "Dread Talons - Strategic Ploy Stratagem",
        ),
        (
            "000008973007",
            "Merciless Pursuit",
            1,
            "Opponent's turn",
            "Movement phase",
            "Dread Talons - Strategic Ploy Stratagem",
        ),
    )
    for stratagem_id, name, cp_cost, turn, phase, stratagem_type in specs:
        if _norm_name(name) in existing:
            continue
        player.stratagems.available.append(
            Stratagem(
                id=stratagem_id,
                name=name,
                type=stratagem_type,
                description="",
                cp_cost=int(cp_cost),
                turn=turn,
                phase=phase,
                detachment="Dread Talons",
                faction_id="CSM",
            )
        )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.position = (float(x), float(y), 0.0)
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * 2.0), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(str(reaction.get("stratagem", "") or "")) == target:
            return reaction
    return None


def _find_request(game: Game, decision_type: str, *, attacker_unit=None):
    attacker_unit_id = str(get_entity_id(attacker_unit) or "") if attacker_unit is not None else ""
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if attacker_unit_id:
            context = dict(getattr(request, "context", {}) or {})
            if str(context.get("attacker_unit_id", "") or "") != attacker_unit_id:
                continue
        return request
    return None


def _find_option(request, *, unit_id: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("unit_id", "") or "") == str(unit_id):
            return option
    return None


def _contains_text(entries, expected: str) -> bool:
    expected_lower = str(expected or "").strip().lower()
    return any(expected_lower in str(entry or "").strip().lower() for entry in list(entries or []))


def test_dread_talons_stratagem_descriptors_registered():
    expected = {
        "000008973002": ("Depthless Cruelty", "conditional_melee_ap_bonus_vs_battleshocked_or_below_half"),
        "000008973003": ("Bloody Example", "battle_shock_all_visible_enemies_within_range_after_destroying_character"),
        "000008973004": ("Pitiless Hunters", "ranged_hit_and_wound_reroll_vs_battleshocked_or_below_half"),
        "000008973005": ("Relentless Terror", "charge_after_fall_back"),
        "000008973006": ("Screaming Descent", "deep_strike_min_distance_override_with_no_charge_and_post_arrival_battleshock"),
        "000008973007": ("Merciless Pursuit", "out_of_turn_charge_without_charge_bonus"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.stratagem_id == stratagem_id
        assert by_id.effect == expected_effect


def test_depthless_cruelty_queues_grants_melee_ap_and_cleans_up():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    broken_target = _make_unit(
        "Broken Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    full_target = _make_unit(
        "Fresh Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(attacker)
    enemy_army.add_unit(broken_target)
    enemy_army.add_unit(full_target)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, broken_target, 16.0, 10.0)
    _deploy_unit(game, full_target, 18.0, 10.0)
    game.rebuild_entity_registry()

    broken_target.apply_status_effect(BattleShockEffect(current_turn=game.turn))
    _set_phase(game, csm_player, "FIGHT_PHASE", 0)
    assert _pending_by_name(csm_player.stratagems, "Depthless Cruelty") is not None

    assert csm_player.stratagems.use("Depthless Cruelty", unit=attacker, dequeue=True, phase_name="Fight phase")
    assert int(csm_player.command_points or 0) == 9

    profile = _make_profile(melee=True)
    assert int(profile.get_effective_ap(attacker.models[0], broken_target)) == -1
    assert int(profile.get_effective_ap(attacker.models[0], full_target)) == 0

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    assert int(profile.get_effective_ap(attacker.models[0], broken_target)) == 0


def test_pitiless_hunters_queues_grants_conditional_rerolls_and_cleans_up():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Havocs",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    shocked_target = _make_unit(
        "Shocked Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    full_target = _make_unit(
        "Fresh Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(shooter)
    enemy_army.add_unit(shocked_target)
    enemy_army.add_unit(full_target)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, shocked_target, 20.0, 10.0)
    _deploy_unit(game, full_target, 24.0, 10.0)
    game.rebuild_entity_registry()

    shocked_target.apply_status_effect(BattleShockEffect(current_turn=game.turn))
    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(csm_player.stratagems, "Pitiless Hunters") is not None

    assert csm_player.stratagems.use("Pitiless Hunters", unit=shooter, dequeue=True, phase_name="Shooting phase")
    assert int(csm_player.command_points or 0) == 9

    profile = _make_profile(melee=False)
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        hit_shocked = profile._hit_target_with_tracking(
            shocked_target,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        hit_full = profile._hit_target_with_tracking(
            full_target,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        wound_shocked = profile._wound_target_with_tracking(
            shocked_target,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        wound_full = profile._wound_target_with_tracking(
            full_target,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

    assert hit_shocked["hit"] is True
    assert int(hit_shocked.get("reroll", 0) or 0) == 4
    assert _contains_text(hit_shocked.get("special_effects", []), "Pitiless Hunters")
    assert hit_full["hit"] is False
    assert int(hit_full.get("reroll", 0) or 0) == 0
    assert wound_shocked["wound"] is True
    assert int(wound_shocked.get("reroll", 0) or 0) == 4
    assert _contains_text(wound_shocked.get("special_effects", []), "Pitiless Hunters")
    assert wound_full["wound"] is False
    assert int(wound_full.get("reroll", 0) or 0) == 0

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        post_cleanup = profile._hit_target_with_tracking(
            shocked_target,
            shooter.models[0],
            {},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(post_cleanup.get("reroll", 0) or 0) == 0


def test_relentless_terror_reacts_to_fall_back_grants_charge_and_cleans_up():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    unit = _make_unit(
        "Warp Talons",
        keywords=["HERETIC ASTARTES", "INFANTRY", "JUMP PACK"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    unit.round_state.fell_back_this_round = True
    assert unit.can_charge_after_fall_back() is False
    assert unit.can_declare_charge_against(enemy, game) is False

    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=unit, action="fall_back")
    assert _pending_by_name(csm_player.stratagems, "Relentless Terror") is not None

    assert csm_player.stratagems.use("Relentless Terror", unit=unit, dequeue=True, phase_name="Movement phase")
    assert int(csm_player.command_points or 0) == 9
    assert unit.can_charge_after_fall_back() is True
    assert unit.can_declare_charge_against(enemy, game) is True

    _set_phase(game, csm_player, "FIGHT_PHASE", 0)
    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    assert unit.can_charge_after_fall_back() is False


def test_merciless_pursuit_queues_at_opponent_movement_phase_end_and_attempts_charge():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    pursuer = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(pursuer)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, pursuer, 10.0, 10.0)
    _deploy_unit(game, enemy, 15.0, 10.0)
    game.rebuild_entity_registry()

    enemy.round_state.fell_back_this_round = True
    game.attempt_charge = Mock(return_value=True)

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert _pending_by_name(csm_player.stratagems, "Merciless Pursuit") is not None

    assert csm_player.stratagems.use(
        "Merciless Pursuit",
        unit=pursuer,
        enemy_unit=enemy,
        dequeue=True,
        phase_name="Movement phase",
    )
    assert int(csm_player.command_points or 0) == 9
    game.attempt_charge.assert_called_once_with(
        pursuer,
        enemy,
        out_of_turn=True,
        count_as_charged=False,
    )


def test_bloody_example_queues_on_character_kill_and_tests_only_visible_targets():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    destroyed_character = _make_unit(
        "Enemy Character",
        faction_name="Enemy",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ENEMY"],
    )
    visible_enemy = _make_unit(
        "Visible Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    hidden_enemy = _make_unit(
        "Hidden Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    far_enemy = _make_unit(
        "Far Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(attacker)
    enemy_army.add_unit(destroyed_character)
    enemy_army.add_unit(visible_enemy)
    enemy_army.add_unit(hidden_enemy)
    enemy_army.add_unit(far_enemy)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, destroyed_character, 13.0, 10.0)
    _deploy_unit(game, visible_enemy, 17.0, 10.0)
    _deploy_unit(game, hidden_enemy, 21.0, 10.0)
    _deploy_unit(game, far_enemy, 30.0, 10.0)
    game.rebuild_entity_registry()

    destroyed_character.remove_model(destroyed_character.models[0])
    attacker._attacking_unit_has_any_los_to_target_unit = (
        lambda target, _game_map: target is visible_enemy
    )
    visible_enemy.take_battle_shock_test = Mock()
    hidden_enemy.take_battle_shock_test = Mock()
    far_enemy.take_battle_shock_test = Mock()

    _set_phase(game, csm_player, "FIGHT_PHASE", 0)
    game.event_system.publish("unit_destroyed", unit=destroyed_character, destroyed_by_unit=attacker)
    assert _pending_by_name(csm_player.stratagems, "Bloody Example") is not None

    assert csm_player.stratagems.use("Bloody Example", unit=attacker, dequeue=True, phase_name="Fight phase")
    assert int(csm_player.command_points or 0) == 9
    visible_enemy.take_battle_shock_test.assert_called_once_with(game.turn)
    hidden_enemy.take_battle_shock_test.assert_not_called()
    far_enemy.take_battle_shock_test.assert_not_called()


def test_screaming_descent_queues_in_reinforcements_step_and_creates_post_setup_choice():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    reserve_unit = _make_unit(
        "Raptors",
        keywords=["HERETIC ASTARTES", "INFANTRY", "JUMP PACK"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    reserve_unit.reserve_status = "reserves"
    reserve_unit.deployed = True
    enemy_a = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_b = _make_unit(
        "Enemy Mounted",
        faction_name="Enemy",
        keywords=["MOUNTED"],
        faction_keywords=["ENEMY"],
    )
    csm_army.add_unit(reserve_unit)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    _deploy_unit(game, enemy_a, 15.0, 10.0)
    _deploy_unit(game, enemy_b, 16.0, 12.0)
    game.rebuild_entity_registry()

    game.turn = 2
    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)
    game.handle_reserves_arrival_phase()
    assert _pending_by_name(csm_player.stratagems, "Screaming Descent") is not None

    assert csm_player.stratagems.use("Screaming Descent", unit=reserve_unit, dequeue=True, phase_name="Movement phase")
    assert int(csm_player.command_points or 0) == 9
    assert reserve_unit.has_deep_strike() is True
    assert float(reserve_unit.get_deep_strike_min_distance_override() or 0.0) == 6.0
    assert str(reserve_unit.special_rules.get("dread_talons_screaming_descent_no_charge_turn_owner", "") or "") == str(csm_player.id)
    assert int(reserve_unit.special_rules.get("dread_talons_screaming_descent_no_charge_turn", 0) or 0) == 2

    reserve_unit._attacking_unit_has_any_los_to_target_unit = (
        lambda target, _game_map: target in {enemy_a, enemy_b}
    )
    enemy_a.take_battle_shock_test = Mock()
    enemy_b.take_battle_shock_test = Mock()
    _deploy_unit(game, reserve_unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    game._on_unit_set_up_csm_detachment_rules(
        unit=reserve_unit,
        set_up_as_reinforcements=True,
        used_deep_strike=True,
    )

    request = _find_request(
        game,
        DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
        attacker_unit=reserve_unit,
    )
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert str(context.get("ability_name", "") or "").strip().upper() == "SCREAMING DESCENT"
    assert bool(reserve_unit.special_rules.get("dread_talons_screaming_descent_post_setup_battleshock_pending", False)) is False

    option = _find_option(request, unit_id=str(get_entity_id(enemy_b) or ""))
    assert option is not None
    result = resolve_decision_command(game, request, option.option_id, player_id=csm_player.id)
    assert bool(getattr(result, "ok", False))
    enemy_a.take_battle_shock_test.assert_not_called()
    enemy_b.take_battle_shock_test.assert_called_once_with(2)
