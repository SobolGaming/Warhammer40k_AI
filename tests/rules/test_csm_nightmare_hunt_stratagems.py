from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


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


def _norm_name(name: str) -> str:
    return "".join(ch for ch in str(name or "").upper() if ch.isalnum())


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


def _make_profile(
    *,
    melee: bool,
    attacks: str = "2",
    skill: str = "4+",
    range_value: str = "24",
):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else str(range_value),
            "A": str(attacks),
            "BS_WS": str(skill),
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

    nightmare_army = Army("Chaos Space Marines", "Nightmare Hunt")
    nightmare_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    nightmare_player = Player("Nightmare", control=PlayerControl.LOCAL, army=nightmare_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(nightmare_player)
    game.add_player(enemy_player)

    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE

    nightmare_player.command_points = 10
    enemy_player.command_points = 10

    nightmare_army.configure_rule_managers(force=True)
    nightmare_player.stratagems.refresh_available()
    _inject_nightmare_hunt_stratagems(nightmare_player)
    nightmare_player.stratagems.enable_event_subscriptions()
    game.rebuild_entity_registry()
    return game, nightmare_player, enemy_player, nightmare_army, enemy_army


def _inject_nightmare_hunt_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(stratagem, "name", "") or ""): stratagem
        for stratagem in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        (
            "000010642002",
            "Talons Sunk Deep",
            1,
            "Either player's turn",
            "Shooting or Fight phase",
            "Nightmare Hunt - Battle Tactic Stratagem",
        ),
        (
            "000010642003",
            "Prey on the Weak",
            1,
            "Either player's turn",
            "Shooting or Fight phase",
            "Nightmare Hunt - Battle Tactic Stratagem",
        ),
        (
            "000010642004",
            "Sadistic Display",
            1,
            "Either player's turn",
            "Fight phase",
            "Nightmare Hunt - Strategic Ploy Stratagem",
        ),
        (
            "000010642005",
            "Malicious Surge",
            1,
            "Your turn",
            "Charge phase",
            "Nightmare Hunt - Strategic Ploy Stratagem",
        ),
        (
            "000010642006",
            "Relentless Terror",
            1,
            "Your turn",
            "Movement phase",
            "Nightmare Hunt - Strategic Ploy Stratagem",
        ),
        (
            "000010642007",
            "Horrific Incursion",
            1,
            "Your turn",
            "Movement phase",
            "Nightmare Hunt - Strategic Ploy Stratagem",
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
                detachment="Nightmare Hunt",
                faction_id="CSM",
            )
        )


def _deploy_unit(game: Game, unit: Unit, x: float, y: float, *, spacing: float = 2.0) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.position = (float(x), float(y), 0.0)
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * float(spacing)), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = getattr(BattleRoundPhases, str(phase_name or "").strip(), None)
    game.phase = phase if phase is not None else SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = _norm_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _norm_name(str(reaction.get("stratagem", "") or "")) == target:
            return reaction
    return None


def _contains_text(entries, expected: str) -> bool:
    expected_lower = str(expected or "").strip().lower()
    return any(expected_lower in str(entry or "").strip().lower() for entry in list(entries or []))


def test_nightmare_hunt_stratagem_descriptors_registered():
    expected = {
        "000010642002": ("Talons Sunk Deep", "conditional_ap_bonus_vs_battleshocked_or_below_half"),
        "000010642003": ("Prey on the Weak", "hit_reroll_vs_battleshocked_or_below_half"),
        "000010642004": (
            "Sadistic Display",
            "battle_shock_all_visible_non_monster_non_vehicle_enemies_within_range_after_destroying_enemy_unit",
        ),
        "000010642005": ("Malicious Surge", "charge_after_advance"),
        "000010642006": ("Relentless Terror", "eligible_to_shoot_and_charge_after_fall_back"),
        "000010642007": ("Horrific Incursion", "visible_enemy_battleshock_test_minus_one_after_arriving_from_reserves"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert by_id is not None
        assert by_id.name == expected_name
        assert by_id.effect == expected_effect
        if stratagem_id != "000010642006":
            by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
            assert by_name is not None
            assert by_name.stratagem_id == stratagem_id


def test_prey_on_the_weak_queues_grants_conditional_hit_rerolls_and_cleans_up():
    game, nightmare_player, _enemy_player, nightmare_army, enemy_army = _build_game()
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
    nightmare_army.add_unit(shooter)
    enemy_army.add_unit(shocked_target)
    enemy_army.add_unit(full_target)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, shocked_target, 20.0, 10.0)
    _deploy_unit(game, full_target, 24.0, 10.0)
    game.rebuild_entity_registry()

    shocked_target.apply_status_effect(BattleShockEffect(current_turn=game.turn))
    _set_phase(game, nightmare_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(nightmare_player.stratagems, "Prey on the Weak") is not None

    assert nightmare_player.stratagems.use(
        "Prey on the Weak",
        unit=shooter,
        dequeue=True,
        phase_name="Shooting phase",
    )
    assert int(nightmare_player.command_points or 0) == 9

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

    assert hit_shocked["hit"] is True
    assert int(hit_shocked.get("reroll", 0) or 0) == 4
    assert _contains_text(hit_shocked.get("special_effects", []), "Prey on the Weak")
    assert hit_full["hit"] is False
    assert int(hit_full.get("reroll", 0) or 0) == 0

    game.event_system.publish("phase_end", player=nightmare_player, phase=game.phase)
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


def test_talons_sunk_deep_reacts_in_opponent_fight_phase_grants_conditional_ap_and_cleans_up():
    game, nightmare_player, enemy_player, nightmare_army, enemy_army = _build_game()
    fighters = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    shocked_target = _make_unit(
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
    nightmare_army.add_unit(fighters)
    enemy_army.add_unit(shocked_target)
    enemy_army.add_unit(full_target)
    _deploy_unit(game, fighters, 10.0, 10.0)
    _deploy_unit(game, shocked_target, 12.0, 10.0)
    _deploy_unit(game, full_target, 14.0, 10.0)
    game.rebuild_entity_registry()

    shocked_target.apply_status_effect(BattleShockEffect(current_turn=game.turn))
    profile = _make_profile(melee=True)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert _pending_by_name(nightmare_player.stratagems, "Talons Sunk Deep") is not None

    assert nightmare_player.stratagems.use(
        "Talons Sunk Deep",
        unit=fighters,
        dequeue=True,
        phase_name="Fight phase",
    )
    assert int(nightmare_player.command_points or 0) == 9
    assert int(profile.get_effective_ap(fighters.models[0], shocked_target)) == -1
    assert int(profile.get_effective_ap(fighters.models[0], full_target)) == 0

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert int(profile.get_effective_ap(fighters.models[0], shocked_target)) == 0


def test_relentless_terror_reacts_to_fall_back_grants_shoot_and_charge_and_cleans_up():
    game, nightmare_player, _enemy_player, nightmare_army, enemy_army = _build_game()
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
    nightmare_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    ranged_profile = _make_profile(melee=False)
    unit.round_state.fell_back_this_round = True
    assert unit.can_shoot_after_fall_back(ranged_profile) is False
    assert unit.can_charge_after_fall_back() is False
    assert unit.can_declare_charge_against(enemy, game) is False

    _set_phase(game, nightmare_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=unit, action="fall_back")
    assert _pending_by_name(nightmare_player.stratagems, "Relentless Terror") is not None

    assert nightmare_player.stratagems.use(
        "Relentless Terror",
        unit=unit,
        dequeue=True,
        phase_name="Movement phase",
    )
    assert int(nightmare_player.command_points or 0) == 9
    assert unit.can_shoot_after_fall_back(ranged_profile) is True
    assert unit.can_charge_after_fall_back() is True
    assert unit.can_declare_charge_against(enemy, game) is True

    _set_phase(game, nightmare_player, "FIGHT_PHASE", 0)
    game.event_system.publish("phase_end", player=nightmare_player, phase=game.phase)
    assert unit.can_shoot_after_fall_back(ranged_profile) is False
    assert unit.can_charge_after_fall_back() is False


def test_malicious_surge_queues_in_charge_phase_and_grants_charge_after_advance_until_cleanup():
    game, nightmare_player, _enemy_player, nightmare_army, enemy_army = _build_game()
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    nightmare_army.add_unit(legionaries)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, legionaries, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    legionaries.round_state.advanced_this_round = True
    assert legionaries.can_charge_after_advance() is False

    _set_phase(game, nightmare_player, "CHARGE_PHASE", 0)
    assert _pending_by_name(nightmare_player.stratagems, "Malicious Surge") is not None

    assert nightmare_player.stratagems.use(
        "Malicious Surge",
        unit=legionaries,
        dequeue=True,
        phase_name="Charge phase",
    )
    assert int(nightmare_player.command_points or 0) == 9
    assert legionaries.can_charge_after_advance() is True
    assert legionaries.can_declare_charge_against(enemy, game) is True

    game.event_system.publish("phase_end", player=nightmare_player, phase=game.phase)
    assert legionaries.can_charge_after_advance() is False


def test_horrific_incursion_queues_after_reserves_arrival_and_applies_minus_one_battleshock():
    game, nightmare_player, _enemy_player, nightmare_army, enemy_army = _build_game()
    reserve_unit = _make_unit(
        "Raptors",
        keywords=["HERETIC ASTARTES", "INFANTRY", "JUMP PACK"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    visible_enemy = _make_unit(
        "Visible Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    vehicle_enemy = _make_unit(
        "Enemy Tank",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    hidden_enemy = _make_unit(
        "Hidden Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    nightmare_army.add_unit(reserve_unit)
    enemy_army.add_unit(visible_enemy)
    enemy_army.add_unit(vehicle_enemy)
    enemy_army.add_unit(hidden_enemy)
    _deploy_unit(game, reserve_unit, 10.0, 10.0)
    _deploy_unit(game, visible_enemy, 18.0, 10.0)
    _deploy_unit(game, vehicle_enemy, 18.0, 12.0)
    _deploy_unit(game, hidden_enemy, 18.0, 14.0)
    game.rebuild_entity_registry()

    reserve_unit.arrived_from_reserves_this_turn = True
    reserve_unit._attacking_unit_has_any_los_to_target_unit = lambda target, _game_map: target in {
        visible_enemy,
        vehicle_enemy,
    }
    visible_enemy.force_battle_shock_test = Mock()
    vehicle_enemy.force_battle_shock_test = Mock()
    hidden_enemy.force_battle_shock_test = Mock()

    _set_phase(game, nightmare_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_set_up", unit=reserve_unit, set_up_as_reinforcements=True)
    pending = _pending_by_name(nightmare_player.stratagems, "Horrific Incursion")
    assert pending is not None
    enemy_candidates = list(pending.get("enemy_candidates") or [])
    assert visible_enemy in enemy_candidates
    assert vehicle_enemy not in enemy_candidates
    assert hidden_enemy not in enemy_candidates

    assert nightmare_player.stratagems.use(
        "Horrific Incursion",
        unit=reserve_unit,
        enemy_unit=visible_enemy,
        dequeue=True,
        phase_name="Movement phase",
    )
    assert int(nightmare_player.command_points or 0) == 9
    visible_enemy.force_battle_shock_test.assert_called_once()
    args, kwargs = visible_enemy.force_battle_shock_test.call_args
    assert args == (game.turn,)
    assert int(kwargs.get("modifier", 0) or 0) == -1
    assert str(kwargs.get("source", "") or "").strip().upper() == "HORRIFIC INCURSION"
    vehicle_enemy.force_battle_shock_test.assert_not_called()
    hidden_enemy.force_battle_shock_test.assert_not_called()


def test_sadistic_display_queues_on_kill_and_tests_only_visible_non_vehicle_non_monster_targets():
    game, nightmare_player, _enemy_player, nightmare_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    destroyed_enemy = _make_unit(
        "Destroyed Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
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
    vehicle_enemy = _make_unit(
        "Enemy Tank",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    monster_enemy = _make_unit(
        "Enemy Monster",
        faction_name="Enemy",
        keywords=["MONSTER"],
        faction_keywords=["ENEMY"],
    )
    nightmare_army.add_unit(attacker)
    enemy_army.add_unit(destroyed_enemy)
    enemy_army.add_unit(visible_enemy)
    enemy_army.add_unit(hidden_enemy)
    enemy_army.add_unit(vehicle_enemy)
    enemy_army.add_unit(monster_enemy)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, destroyed_enemy, 12.0, 10.0)
    _deploy_unit(game, visible_enemy, 15.0, 10.0)
    _deploy_unit(game, hidden_enemy, 15.0, 14.0)
    _deploy_unit(game, vehicle_enemy, 15.0, 12.0)
    _deploy_unit(game, monster_enemy, 14.0, 8.0)
    game.rebuild_entity_registry()

    destroyed_enemy.remove_model(destroyed_enemy.models[0])
    attacker._attacking_unit_has_any_los_to_target_unit = lambda target, _game_map: target in {
        visible_enemy,
        vehicle_enemy,
        monster_enemy,
    }
    visible_enemy.take_battle_shock_test = Mock()
    hidden_enemy.take_battle_shock_test = Mock()
    vehicle_enemy.take_battle_shock_test = Mock()
    monster_enemy.take_battle_shock_test = Mock()

    _set_phase(game, nightmare_player, "FIGHT_PHASE", 0)
    game.event_system.publish("unit_destroyed", unit=destroyed_enemy, destroyed_by_unit=attacker)
    assert _pending_by_name(nightmare_player.stratagems, "Sadistic Display") is not None

    assert nightmare_player.stratagems.use(
        "Sadistic Display",
        unit=attacker,
        dequeue=True,
        phase_name="Fight phase",
    )
    assert int(nightmare_player.command_points or 0) == 9
    visible_enemy.take_battle_shock_test.assert_called_once_with(game.turn)
    hidden_enemy.take_battle_shock_test.assert_not_called()
    vehicle_enemy.take_battle_shock_test.assert_not_called()
    monster_enemy.take_battle_shock_test.assert_not_called()
