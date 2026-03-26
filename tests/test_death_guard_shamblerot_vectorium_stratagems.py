from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import NurglesGiftManager, PLAGUE_RATTLEJOINT
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        movement: str = "5",
        toughness: str = "5",
        wounds: str = "4",
        leadership: str = "7",
        objective_control: str = "1",
        model_count: int = 1,
        abilities=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        faction_tokens = {str(token).upper() for token in list(faction_keywords or [])}
        self.faction_data = {"name": "Death Guard" if "DEATH GUARD" in faction_tokens else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count))
        model_label = "Test Model" if count == 1 else "Test Models"
        self.datasheets_unit_composition = [{"description": f"{count} {model_label}"}]
        self.datasheets_models_cost = [{"description": f"{count} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": str(leadership),
                "OC": str(objective_control),
                "base_size": "40mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    wounds: str = "4",
    toughness: str = "5",
    quantity: int = 1,
    abilities=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            toughness=toughness,
            model_count=quantity,
            abilities=abilities,
        ),
        quantity=int(quantity),
    )


def _make_profile(*, melee: bool, damage: str = "1"):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": str(damage),
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    dg_army = Army("Death Guard", "Shamblerot Vectorium")
    dg_army.faction_id = "DG"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)

    dg_player.command_points = 10
    enemy_player.command_points = 10
    dg_army.configure_rule_managers(force=True)
    dg_army.nurgles_gift.active_plague_key = PLAGUE_RATTLEJOINT.key
    dg_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, dg_player, enemy_player, dg_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def test_shamblerot_vectorium_stratagems_have_tool_descriptors():
    expected = [
        ("000010140002", "Grip of the Walking Pox"),
        ("000010140003", "Smeared With Filth"),
        ("000010140004", "Gnawing Hunger"),
        ("000010140005", "Hidden Amongst the Dead"),
        ("000010140006", "Shock and Horror"),
        ("000010140007", "Shambling Wall"),
    ]
    for stratagem_id, name in expected:
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=name.upper())
        by_name = get_stratagem_tool_descriptor(name=name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.stratagem_id == stratagem_id
        assert by_name.stratagem_id == stratagem_id


def test_gnawing_hunger_adds_turn_long_move_attacks_and_strength_effects():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    poxwalkers = _make_unit(
        "Poxwalkers",
        keywords=["INFANTRY", "POXWALKERS"],
        faction_keywords=["DEATH GUARD"],
        quantity=10,
    )
    dg_army.add_unit(poxwalkers)
    _deploy_unit(game, poxwalkers, 10.0, 10.0)

    game.turn = 1
    _set_phase(game, dg_player, "COMMAND_PHASE", 0)
    assert dg_player.stratagems.use("GNAWING HUNGER", unit=poxwalkers, phase_name="Command phase")

    effects = list((poxwalkers.special_rules or {}).get("death_guard_temp_effects", []) or [])
    effect_names = {str(entry.get("effect", "") or "") for entry in effects}
    expires_modes = {str(entry.get("expires_mode", "") or "") for entry in effects}
    assert effect_names == {"move_bonus", "attacks_bonus", "strength_bonus"}
    assert expires_modes == {"turn"}


def test_hidden_amongst_the_dead_grants_temp_deep_strike_to_poxwalkers_in_strategic_reserves():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    poxwalkers = _make_unit(
        "Poxwalkers",
        keywords=["INFANTRY", "POXWALKERS"],
        faction_keywords=["DEATH GUARD"],
        quantity=10,
    )
    poxwalkers.reserve_status = "strategic_reserves"
    dg_army.add_unit(poxwalkers)

    game.turn = 1
    _set_phase(game, dg_player, "MOVEMENT_PHASE", 0)
    assert not poxwalkers.has_deep_strike()
    assert dg_player.stratagems.use("HIDDEN AMONGST THE DEAD", unit=poxwalkers, phase_name="Movement phase")
    assert poxwalkers.has_deep_strike()

    dg_player.stratagems._on_phase_end(player=dg_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert not poxwalkers.has_deep_strike()


def test_shock_and_horror_queues_on_charge_end_and_forces_battleshock_at_minus_one():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    chargers = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    enemy_a = _make_unit("Enemy A", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_b = _make_unit("Enemy B", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_a.force_battle_shock_test = Mock()
    enemy_b.force_battle_shock_test = Mock()
    dg_army.add_unit(chargers)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    _deploy_unit(game, chargers, 10.0, 10.0)
    _deploy_unit(game, enemy_a, 10.5, 10.0)
    _deploy_unit(game, enemy_b, 10.0, 10.5)

    game.turn = 1
    _set_phase(game, dg_player, "CHARGE_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=chargers, action="charge")
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "SHOCK AND HORROR" for entry in list(pending or []))

    assert dg_player.stratagems.use(
        "SHOCK AND HORROR",
        unit=chargers,
        action="charge",
        phase_name="Charge phase",
        dequeue=True,
    )

    enemy_a.force_battle_shock_test.assert_called_once()
    enemy_b.force_battle_shock_test.assert_called_once()
    assert enemy_a.force_battle_shock_test.call_args.kwargs["modifier"] == -1
    assert enemy_b.force_battle_shock_test.call_args.kwargs["modifier"] == -1


def test_grip_of_the_walking_pox_queues_and_deals_mortals_based_on_models_destroyed():
    game, dg_player, enemy_player, dg_army, enemy_army = _build_game()
    poxwalkers = _make_unit(
        "Poxwalkers",
        keywords=["INFANTRY", "POXWALKERS"],
        faction_keywords=["DEATH GUARD"],
        quantity=5,
    )
    attacker = _make_unit(
        "Enemy Fighters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="6",
    )
    dg_army.add_unit(poxwalkers)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, poxwalkers, 10.0, 10.0)
    _deploy_unit(game, attacker, 10.5, 10.0)

    game.turn = 1
    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish(
        "fight_targets_selected",
        attacking_unit=attacker,
        target_units=[poxwalkers],
    )
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "GRIP OF THE WALKING POX" for entry in list(pending or []))

    assert dg_player.stratagems.use(
        "GRIP OF THE WALKING POX",
        unit=poxwalkers,
        attacking_unit=attacker,
        phase_name="Fight phase",
        dequeue=True,
    )

    poxwalkers.models[0].die(game_map=game.map)
    poxwalkers.models[1].die(game_map=game.map)

    with patch("warhammer40k_ai.rules.stratagems_death_guard.dice_module.get_roll", side_effect=[6, 1]):
        dg_player.stratagems._on_fight_sequence_complete(unit=attacker)

    assert int(attacker.models[0].wounds) == 5


def test_grip_of_the_walking_pox_counts_kills_for_curse_when_poxwalkers_survive():
    game, dg_player, enemy_player, dg_army, enemy_army = _build_game()
    poxwalkers = _make_unit(
        "Poxwalkers",
        keywords=["INFANTRY", "POXWALKERS"],
        faction_keywords=["DEATH GUARD"],
        quantity=2,
        abilities=[
            {
                "name": "Curse of the Walking Pox",
                "description": "Each time a model in this unit destroys an enemy model, return destroyed Poxwalkers.",
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    attacker = _make_unit(
        "Enemy Fragile",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="1",
    )
    dg_army.add_unit(poxwalkers)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, poxwalkers, 10.0, 10.0)
    _deploy_unit(game, attacker, 10.5, 10.0)

    game.turn = 1
    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish(
        "fight_targets_selected",
        attacking_unit=attacker,
        target_units=[poxwalkers],
    )
    assert dg_player.stratagems.use(
        "GRIP OF THE WALKING POX",
        unit=poxwalkers,
        attacking_unit=attacker,
        phase_name="Fight phase",
        dequeue=True,
    )

    poxwalkers.models[0].die(game_map=game.map)

    with patch("warhammer40k_ai.rules.stratagems_death_guard.dice_module.get_roll", return_value=6):
        dg_player.stratagems._on_fight_sequence_complete(unit=attacker)

    assert int((poxwalkers.special_rules or {}).get("curse_of_walking_pox_pending_kills", 0) or 0) == 1


def test_smeared_with_filth_queues_on_destroyed_poxwalkers_and_marks_enemy_fully_afflicted():
    game, dg_player, enemy_player, dg_army, enemy_army = _build_game()
    poxwalkers = _make_unit(
        "Poxwalkers",
        keywords=["INFANTRY", "POXWALKERS"],
        faction_keywords=["DEATH GUARD"],
        quantity=1,
    )
    attacker = _make_unit(
        "Enemy Butchers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
    )
    dg_army.add_unit(poxwalkers)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, poxwalkers, 10.0, 10.0)
    _deploy_unit(game, attacker, 10.5, 10.0)

    game.turn = 1
    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish(
        "fight_targets_selected",
        attacking_unit=attacker,
        target_units=[poxwalkers],
    )

    poxwalkers._last_destroyed_by_unit = attacker
    poxwalkers._last_destroyed_by_model = attacker.models[0]
    poxwalkers.models[0].die(game_map=game.map)

    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "SMEARED WITH FILTH" for entry in list(pending or []))

    assert dg_player.stratagems.use(
        "SMEARED WITH FILTH",
        unit=poxwalkers,
        enemy_unit=attacker,
        phase_name="Fight phase",
        dequeue=True,
    )

    afflicted = NurglesGiftManager.get_afflicted_plague_for_unit(attacker, game=game, game_map=game.map)
    assert afflicted is not None
    assert afflicted.key == PLAGUE_RATTLEJOINT.key
    assert NurglesGiftManager.get_non_contagion_afflicted_toughness_modifier_for_unit(
        attacker,
        game=game,
        game_map=game.map,
    ) == -1


def test_shambling_wall_queues_and_redirects_allocated_attack_to_support_poxwalkers():
    game, dg_player, enemy_player, dg_army, enemy_army = _build_game()
    protected = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    support = _make_unit(
        "Poxwalkers",
        keywords=["INFANTRY", "POXWALKERS"],
        faction_keywords=["DEATH GUARD"],
        quantity=5,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(protected)
    dg_army.add_unit(support)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, protected, 10.0, 10.0)
    _deploy_unit(game, support, 12.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.map.can_model_see_model = lambda _source, _target: True

    game.turn = 1
    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=attacker,
        target_units=[protected],
    )
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "SHAMBLING WALL" for entry in list(pending or []))

    assert dg_player.stratagems.use(
        "SHAMBLING WALL",
        unit=protected,
        support_unit=support,
        attacking_unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )

    profile = _make_profile(melee=False, damage="2")
    protected_before = int(protected.models[0].wounds)
    support_before = sum(
        1
        for model in list(support.models or [])
        if bool(model.is_alive() if callable(getattr(model, "is_alive", None)) else getattr(model, "is_alive", False))
    )

    redirect_result = protected._apply_death_guard_shamblerot_shambling_wall_redirect(
        attacker_model=attacker.models[0],
        attacker_unit=attacker,
        weapon_profile=profile,
        attack_instance={},
        game_map=game.map,
    )

    support_after = sum(
        1
        for model in list(support.models or [])
        if bool(model.is_alive() if callable(getattr(model, "is_alive", None)) else getattr(model, "is_alive", False))
    )
    assert redirect_result is not None
    assert int(redirect_result.get("damage", 0) or 0) == 2
    assert int(protected.models[0].wounds) == protected_before
    assert support_after == support_before - 2
