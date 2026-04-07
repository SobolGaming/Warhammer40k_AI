from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import (
    NurglesGiftManager,
    PLAGUE_RATTLEJOINT,
)
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        movement: str = "5",
        toughness: str = "5",
        wounds: str = "4",
        leadership: str = "7",
        objective_control: str = "1",
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count))
        self.datasheets_unit_composition = [{"description": f"{count} Test Model"}]
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords=None,
    faction_keywords=None,
    toughness: str = "5",
    wounds: str = "4",
    quantity: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            model_count=quantity,
        ),
        quantity=int(quantity),
    )


def _make_ranged_profile(*, name: str = "Rot Rifle", damage: str = "1"):
    weapon = Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": "24",
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

    dg_army = Army.with_detachment("Death Guard", "Tallyband Summoners")
    dg_army.faction_id = "DG"
    enemy_army = Army.with_detachment("Enemy", "Other")
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
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in list(getattr(game.map, "units", []) or []):
        game.map.units.append(unit)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def test_tallyband_summoners_stratagems_have_tool_descriptors():
    expected = [
        ("000010136002", "Persistent Pests"),
        ("000010136003", "Clutching Corruption"),
        ("000010136004", "All Is Rot"),
        ("000010136005", "Fleshy Avalanche"),
        ("000010136006", "Avatars of Decay"),
        ("000010136007", "Mireslick"),
    ]
    for stratagem_id, name in expected:
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=name.upper())
        by_name = get_stratagem_tool_descriptor(name=name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.stratagem_id == stratagem_id
        assert by_name.stratagem_id == stratagem_id


def test_all_is_rot_allows_ranged_targeting_out_of_own_engagement_and_applies_self_mortals():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Plaguebearers",
        faction_name="Chaos Daemons",
        keywords=["INFANTRY", "PLAGUE LEGIONS"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    engaged_enemy = _make_unit(
        "Enemy Frontline",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    distant_enemy = _make_unit(
        "Enemy Backline",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(shooter)
    enemy_army.add_unit(engaged_enemy)
    enemy_army.add_unit(distant_enemy)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, engaged_enemy, 10.5, 10.0)
    _deploy_unit(game, distant_enemy, 18.0, 12.0)
    game.rebuild_entity_registry()

    _set_phase(game, dg_player, "SHOOTING_PHASE", 0)
    weapon_profile = _make_ranged_profile()
    firing_model = shooter.models[0]

    assert not shooter._can_model_shoot_weapon_at_target(
        firing_model,
        weapon_profile,
        distant_enemy,
        game.map,
    )

    assert dg_player.stratagems.use("ALL IS ROT", unit=shooter, phase_name="Shooting phase")
    assert shooter._can_model_shoot_weapon_at_target(
        firing_model,
        weapon_profile,
        distant_enemy,
        game.map,
    )

    wounds_before = int(shooter.models[0].wounds)
    with patch("warhammer40k_ai.rules.stratagems_death_guard.dice_module.get_roll", side_effect=[5, 2]):
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=shooter,
            damage_by_target_while_engaged={engaged_enemy: 2},
        )

    assert int(shooter.models[0].wounds) == wounds_before - 1


def test_avatars_of_decay_afflicts_enemies_within_six_as_non_contagion_source():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    source = _make_unit(
        "Plaguebearers",
        faction_name="Chaos Daemons",
        keywords=["INFANTRY", "PLAGUE LEGIONS"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    near_enemy = _make_unit(
        "Enemy Near",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    far_enemy = _make_unit(
        "Enemy Far",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(near_enemy)
    enemy_army.add_unit(far_enemy)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, near_enemy, 15.0, 10.0)
    _deploy_unit(game, far_enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, dg_player, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use("AVATARS OF DECAY", unit=source, phase_name="Shooting phase")

    near_plague = NurglesGiftManager.get_afflicted_plague_for_unit(
        near_enemy,
        game=game,
        game_map=game.map,
        include_contagion_sources=False,
    )
    far_plague = NurglesGiftManager.get_afflicted_plague_for_unit(
        far_enemy,
        game=game,
        game_map=game.map,
        include_contagion_sources=False,
    )

    assert near_plague is not None
    assert str(near_plague.key or "").strip().upper() == PLAGUE_RATTLEJOINT.key
    assert far_plague is None
    assert (
        NurglesGiftManager.get_non_contagion_afflicted_toughness_modifier_for_unit(
            near_enemy,
            game=game,
            game_map=game.map,
        )
        == -1
    )


def test_clutching_corruption_only_matches_enemies_engaged_with_friendly_plague_legions():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    plague_legions_anchor = _make_unit(
        "Nurglings",
        faction_name="Chaos Daemons",
        keywords=["INFANTRY", "PLAGUE LEGIONS", "NURGLINGS"],
        faction_keywords=["LEGIONES DAEMONICA"],
        quantity=3,
    )
    engaged_enemy = _make_unit(
        "Enemy Engaged",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    free_enemy = _make_unit(
        "Enemy Free",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(attacker)
    dg_army.add_unit(plague_legions_anchor)
    enemy_army.add_unit(engaged_enemy)
    enemy_army.add_unit(free_enemy)
    _deploy_unit(game, attacker, 8.0, 10.0)
    _deploy_unit(game, plague_legions_anchor, 10.0, 10.0)
    _deploy_unit(game, engaged_enemy, 10.5, 10.0)
    _deploy_unit(game, free_enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, dg_player, "FIGHT_PHASE", 0)
    assert dg_player.stratagems.use("CLUTCHING CORRUPTION", unit=attacker, phase_name="Fight phase")

    engaged_effects = list(
        attacker.iter_active_death_guard_temp_effects(
            effect_type="hit_reroll",
            attack_type="melee",
            target=engaged_enemy,
        )
    )
    free_effects = list(
        attacker.iter_active_death_guard_temp_effects(
            effect_type="hit_reroll",
            attack_type="melee",
            target=free_enemy,
        )
    )

    assert len(engaged_effects) == 1
    assert str(engaged_effects[0].get("reroll_mode", "") or "") == "full"
    assert free_effects == []


def test_fleshy_avalanche_grants_phase_limited_terrain_movement_in_movement_and_charge():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    monster = _make_unit(
        "Great Unclean One",
        faction_name="Chaos Daemons",
        keywords=["MONSTER", "PLAGUE LEGIONS"],
        faction_keywords=["LEGIONES DAEMONICA"],
        wounds="16",
        toughness="10",
    )
    dg_army.add_unit(monster)
    _deploy_unit(game, monster, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, dg_player, "MOVEMENT_PHASE", 0)
    assert dg_player.stratagems.use("FLESHY AVALANCHE", unit=monster, phase_name="Movement phase")
    move_types = set((monster.special_rules or {}).get("bearer_unit_phase_move_terrain_only_types", []) or [])
    assert move_types == {"advance", "move"}

    dg_player.stratagems._on_phase_end(player=dg_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    move_types = set((monster.special_rules or {}).get("bearer_unit_phase_move_terrain_only_types", []) or [])
    assert move_types == set()

    _set_phase(game, dg_player, "CHARGE_PHASE", 0)
    assert dg_player.stratagems.use("FLESHY AVALANCHE", unit=monster, phase_name="Charge phase")
    move_types = set((monster.special_rules or {}).get("bearer_unit_phase_move_terrain_only_types", []) or [])
    assert move_types == {"charge"}

    dg_player.stratagems._on_phase_end(player=dg_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    move_types = set((monster.special_rules or {}).get("bearer_unit_phase_move_terrain_only_types", []) or [])
    assert move_types == set()


def test_mireslick_queues_on_enemy_fall_back_and_failed_test_keeps_enemy_stationary():
    game, dg_player, enemy_player, dg_army, enemy_army = _build_game()
    source = _make_unit(
        "Plaguebearers",
        faction_name="Chaos Daemons",
        keywords=["INFANTRY", "PLAGUE LEGIONS"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, enemy, 10.5, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_started", unit=enemy, action="fall_back")
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(entry.get("stratagem", "") or "").strip().upper() == "MIRESLICK" for entry in list(pending or []))

    assert dg_player.stratagems.use(
        "MIRESLICK",
        unit=source,
        enemy_unit=enemy,
        phase_name="Movement phase",
        dequeue=True,
    )

    enemy.pass_leadership_check = lambda: False
    assert not enemy.fall_back((18.0, 10.0, 0.0), [], game.map)
    assert bool(getattr(enemy.round_state, "remained_stationary_this_round", False))


def test_persistent_pests_replaces_destroyed_nurglings_in_strategic_reserves():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    nurglings = _make_unit(
        "Nurglings",
        faction_name="Chaos Daemons",
        keywords=["INFANTRY", "PLAGUE LEGIONS", "NURGLINGS"],
        faction_keywords=["LEGIONES DAEMONICA"],
        quantity=3,
    )
    dg_army.add_unit(nurglings)
    _deploy_unit(game, nurglings, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, dg_player, "FIGHT_PHASE", 0)
    game.map.units.remove(nurglings)
    nurglings.is_alive = lambda: False
    existing_unit_ids = {id(unit) for unit in list(dg_army.units or [])}

    game.event_system.publish("unit_destroyed", unit=nurglings)
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(
        str(entry.get("stratagem", "") or "").strip().upper() == "PERSISTENT PESTS"
        for entry in list(pending or [])
    )

    assert dg_player.stratagems.use(
        "PERSISTENT PESTS",
        destroyed_unit=nurglings,
        phase_name="Fight phase",
        dequeue=True,
    )

    replacement_units = [unit for unit in list(dg_army.units or []) if id(unit) not in existing_unit_ids]
    assert len(replacement_units) == 1
    replacement = replacement_units[0]
    assert replacement is not nurglings
    assert bool(replacement.is_in_reserves())
    assert str(getattr(replacement, "reserve_status", "") or "") == "strategic_reserves"
    assert int(getattr(replacement, "starting_model_count", 0) or 0) == int(getattr(nurglings, "starting_model_count", 0) or 0)
    assert bool(replacement.is_alive())
    assert replacement not in list(getattr(game.map, "units", []) or [])
