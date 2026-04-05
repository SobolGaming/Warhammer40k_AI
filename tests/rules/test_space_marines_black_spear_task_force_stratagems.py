from __future__ import annotations

from types import SimpleNamespace

import pytest

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


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
        datasheet_abilities=None,
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
        normalized_abilities = []
        for ability in list(datasheet_abilities or []):
            if isinstance(ability, str):
                normalized_abilities.append({"name": ability, "description": "", "type": "Datasheet", "parameter": ""})
            else:
                normalized_abilities.append(ability)
        self.datasheets_abilities = normalized_abilities
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
    datasheet_abilities=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            datasheet_abilities=datasheet_abilities,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "Black Spear Task Force")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sm_player.command_points = 10
    enemy_player.command_points = 10

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


def _make_ranged_profile(
    *,
    weapon_name: str = "Bolt Rifle",
    weapon_range: str = "24",
    ap: str = "0",
    description: str = "",
) -> WargearProfile:
    parent = SimpleNamespace(name=weapon_name, is_ranged=lambda: True, is_melee=lambda: False)
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": str(weapon_range),
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": str(ap),
            "D": "1",
            "description": str(description),
        },
        parent_wargear=parent,
    )


def _ranged_keyword_bonuses(unit: Unit, profile: WargearProfile, *, target: Unit) -> dict:
    return unit.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=unit.models[0],
        weapon_profile=profile,
        target=target,
    )


def test_black_spear_task_force_stratagem_descriptors_registered():
    expected = {
        "000008523003": ("Adaptive Tactics", "unit_specific_mission_tactic_override"),
        "000008523006": ("Dragonfire Rounds", "ranged_assault_and_ignores_cover"),
        "000008523004": ("Hellfire Rounds", "ranged_anti_infantry_2_and_anti_monster_5_except_devastating_wounds"),
        "000008523005": ("Kraken Rounds", "ranged_ap_and_range_bonus"),
        "000008523007": ("Site-to-Site Teleportation", "enter_strategic_reserves_with_temp_deep_strike"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_black_spear_phase_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    kill_team_a = _make_unit("Deathwatch Kill Team Alpha", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    kill_team_b = _make_unit("Deathwatch Kill Team Beta", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(kill_team_a)
    sm_army.add_unit(kill_team_b)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, kill_team_a, 10.0, 10.0)
    _deploy_unit(game, kill_team_b, 14.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    game.map.is_within_engagement_range = lambda _first, _second: False
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    command_names = {str(item.get("stratagem", "") or "").strip().upper() for item in sm_player.stratagems.get_pending_reactions(clear=True)}
    assert command_names == {"ADAPTIVE TACTICS"}

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    shooting_names = {str(item.get("stratagem", "") or "").strip().upper() for item in sm_player.stratagems.get_pending_reactions(clear=True)}
    assert shooting_names == {"DRAGONFIRE ROUNDS", "HELLFIRE ROUNDS", "KRAKEN ROUNDS"}

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    fight_names = {str(item.get("stratagem", "") or "").strip().upper() for item in sm_player.stratagems.get_pending_reactions(clear=True)}
    assert fight_names == {"SITE-TO-SITE TELEPORTATION"}


def test_adaptive_tactics_applies_unit_specific_malleus_to_non_mission_tactics_unit():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit("Intercessor Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "ADAPTIVE TACTICS") is not None

    ok = sm_player.stratagems.use(
        "ADAPTIVE TACTICS",
        unit=intercessors,
        choice="MALLEUS_TACTICS",
        dequeue=True,
        phase_name="Command phase",
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    active_key, _source = sm_army.space_marines_detachments.black_spear_adaptive_tactics_choice_for_unit(intercessors)
    assert active_key == "MALLEUS_TACTICS"

    profile = _make_ranged_profile()
    attack_instance = {"distance_to_target": 18.0}
    hit = profile._hit_target_with_tracking(
        enemy,
        intercessors.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("lethal_hit", False)) is True
    assert "Lethal Hits" in list(hit.get("special_effects", []) or [])


def test_adaptive_tactics_targets_two_kill_teams_with_independent_choices():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    kill_team_a = _make_unit("Deathwatch Kill Team Alpha", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    kill_team_b = _make_unit("Deathwatch Kill Team Beta", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(kill_team_a)
    sm_army.add_unit(kill_team_b)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, kill_team_a, 10.0, 10.0)
    _deploy_unit(game, kill_team_b, 14.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    ok = sm_player.stratagems.use(
        "ADAPTIVE TACTICS",
        units=[kill_team_a, kill_team_b],
        choices_by_unit={
            kill_team_a: "FUROR_TACTICS",
            kill_team_b: "PURGATUS_TACTICS",
        },
        dequeue=True,
        phase_name="Command phase",
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    assert sm_army.space_marines_detachments.black_spear_adaptive_tactics_choice_for_unit(kill_team_a)[0] == "FUROR_TACTICS"
    assert sm_army.space_marines_detachments.black_spear_adaptive_tactics_choice_for_unit(kill_team_b)[0] == "PURGATUS_TACTICS"

    profile = _make_ranged_profile()
    furor_attack = {"distance_to_target": 18.0}
    profile._hit_target_with_tracking(
        enemy,
        kill_team_a.models[0],
        furor_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(furor_attack.get("sustained_hit", 0) or 0) == 1

    purgatus_attack = {"distance_to_target": 18.0}
    profile._hit_target_with_tracking(
        enemy,
        kill_team_b.models[0],
        purgatus_attack,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(purgatus_attack.get("bonus_precision", False)) is True


def test_adaptive_tactics_rejects_two_non_kill_team_units():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit("Intercessor Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    hellblasters = _make_unit("Hellblasters", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    sm_army.add_unit(intercessors)
    sm_army.add_unit(hellblasters)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, hellblasters, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    ok = sm_player.stratagems.use(
        "ADAPTIVE TACTICS",
        units=[intercessors, hellblasters],
        choices_by_unit={
            intercessors: "FUROR_TACTICS",
            hellblasters: "MALLEUS_TACTICS",
        },
        dequeue=True,
        phase_name="Command phase",
    )
    assert ok is False
    assert int(sm_player.command_points or 0) == 10


def test_dragonfire_rounds_grants_assault_and_ignores_cover_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    kill_team = _make_unit("Deathwatch Kill Team", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(kill_team)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, kill_team, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "DRAGONFIRE ROUNDS") is not None
    ok = sm_player.stratagems.use(
        "DRAGONFIRE ROUNDS",
        unit=kill_team,
        dequeue=True,
        phase_name="Shooting phase",
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    profile = _make_ranged_profile()
    bonuses = _ranged_keyword_bonuses(kill_team, profile, target=enemy)
    assert bool(bonuses.get("assault", False)) is True
    assert bool(bonuses.get("ignores_cover", False)) is True
    assert bool(kill_team.can_shoot_after_advance(profile)) is True

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    after = _ranged_keyword_bonuses(kill_team, profile, target=enemy)
    assert bool(after.get("assault", False)) is False
    assert bool(after.get("ignores_cover", False)) is False


def test_hellfire_rounds_grants_anti_keywords_except_devastating_wounds():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    kill_team = _make_unit("Deathwatch Kill Team", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    enemy = _make_unit("Enemy Monster", faction_name="Enemy", keywords=["MONSTER"], faction_keywords=["ENEMY"])
    sm_army.add_unit(kill_team)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, kill_team, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use(
        "HELLFIRE ROUNDS",
        unit=kill_team,
        dequeue=True,
        phase_name="Shooting phase",
    )
    assert ok is True

    normal_profile = _make_ranged_profile()
    devastating_profile = _make_ranged_profile(weapon_name="Vengeance Launcher", description="[DEVASTATING WOUNDS]")
    normal_bonuses = _ranged_keyword_bonuses(kill_team, normal_profile, target=enemy)
    devastating_bonuses = _ranged_keyword_bonuses(kill_team, devastating_profile, target=enemy)
    assert set(normal_bonuses.get("anti_specs", [])) == {("INFANTRY", 2), ("MONSTER", 5)}
    assert list(devastating_bonuses.get("anti_specs", []) or []) == []


def test_kraken_rounds_improves_ranged_ap_and_range_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    kill_team = _make_unit("Deathwatch Kill Team", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(kill_team)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, kill_team, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ok = sm_player.stratagems.use(
        "KRAKEN ROUNDS",
        unit=kill_team,
        dequeue=True,
        phase_name="Shooting phase",
    )
    assert ok is True

    profile = _make_ranged_profile(weapon_range="24", ap="0")
    assert int(profile._effective_range_max(attacker=kill_team.models[0]) or 0) == 30
    assert int(profile.get_effective_ap(attacker=kill_team.models[0], target=enemy) or 0) == -1

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert int(profile._effective_range_max(attacker=kill_team.models[0]) or 0) == 24
    assert int(profile.get_effective_ap(attacker=kill_team.models[0], target=enemy) or 0) == 0


def test_site_to_site_teleportation_enters_two_kill_teams_into_reserves_with_deep_strike():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    kill_team_a = _make_unit("Deathwatch Kill Team Alpha", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    kill_team_b = _make_unit("Deathwatch Kill Team Beta", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(kill_team_a)
    sm_army.add_unit(kill_team_b)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, kill_team_a, 10.0, 10.0)
    _deploy_unit(game, kill_team_b, 14.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    game.map.is_within_engagement_range = lambda _first, _second: False
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert _pending_by_name(sm_player.stratagems, "SITE-TO-SITE TELEPORTATION") is not None

    ok = sm_player.stratagems.use(
        "SITE-TO-SITE TELEPORTATION",
        units=[kill_team_a, kill_team_b],
        dequeue=True,
        phase_name="Fight phase",
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert bool(kill_team_a.is_in_strategic_reserves())
    assert bool(kill_team_b.is_in_strategic_reserves())

    for unit in (kill_team_a, kill_team_b):
        sr = dict(getattr(unit, "special_rules", {}) or {})
        assert bool(sr.get("midgame_temp_deep_strike"))
        assert str(sr.get("midgame_temp_deep_strike_turn_owner", "") or "") == str(sm_player.id or "")
        assert int(sr.get("midgame_temp_deep_strike_must_arrive_turn", 0) or 0) == 2

    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    assert bool(kill_team_a.has_deep_strike())
    assert bool(kill_team_a.can_arrive_from_reserves(game.turn))
    assert bool(kill_team_a.must_arrive_from_reserves(game.turn))


def test_site_to_site_teleportation_rejects_mixed_two_unit_selection():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    kill_team = _make_unit("Deathwatch Kill Team", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    intercessors = _make_unit("Intercessor Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(kill_team)
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, kill_team, 10.0, 10.0)
    _deploy_unit(game, intercessors, 14.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    game.map.is_within_engagement_range = lambda _first, _second: False
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    ok = sm_player.stratagems.use(
        "SITE-TO-SITE TELEPORTATION",
        units=[kill_team, intercessors],
        dequeue=True,
        phase_name="Fight phase",
    )
    assert ok is False
    assert int(sm_player.command_points or 0) == 10
