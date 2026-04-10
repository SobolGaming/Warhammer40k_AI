from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
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
        faction_name: str = "Adeptus Mechanicus",
        keywords=None,
        faction_keywords=None,
        wounds: int = 3,
        base_size: str = "32mm",
        transport: str = "",
    ) -> None:
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
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
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Adeptus Mechanicus",
    keywords=None,
    faction_keywords=None,
    wounds: int = 3,
    base_size: str = "32mm",
    transport: str = "",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            base_size=base_size,
            transport=transport,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    unit.round_state.shot_this_round = False
    unit.round_state.fought_this_phase = False
    unit.round_state.moved_this_round = False
    unit.round_state.advanced_this_round = False
    unit.round_state.fell_back_this_round = False
    unit.round_state.attempted_charge_this_round = False
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.auto_resolve_dice_rolls = False

    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Skitarii Hunter Cohort")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    admech_player = Player("AdMech", PlayerControl.LOCAL, army=admech_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.current_player_idx = 0
    admech_player.command_points = 10
    enemy_player.command_points = 10
    return game, admech_army, enemy_army, admech_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    assert placed, f"Failed to place {getattr(unit, 'name', 'Unit')}"


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
    game.current_player_idx = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    wanted = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
            return reaction
    return None


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _attack_instance() -> dict:
    return {
        "crit_hit": False,
        "crit_wound": False,
        "mortal_wound": False,
        "below_half_distance": False,
        "damage": 0,
        "target_toughness_override": None,
    }


def test_skitarii_hunter_stratagem_descriptors_registered():
    expected = {
        "000008561002": ("Bionic Endurance", "feel_no_pain"),
        "000008561003": ("Binharic Offence", "paired_units_ap_bonus"),
        "000008561004": ("Expedited Purge Protocol", "charge_after_advance"),
        "000008561005": ("Isolate and Destroy", "conditional_ranged_wound_bonus_vs_isolated_target"),
        "000008561006": ("Shroud Protocols", "ranged_targeting_range_restriction"),
        "000008561007": ("Programmed Withdrawal", "enter_strategic_reserves"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_binharic_offence_queues_at_phase_start_and_grants_ap_bonus_until_phase_end():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    unit_a = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    unit_b = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(unit_a)
    admech_army.add_unit(unit_b)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit_a, 10.0, 10.0)
    _deploy_unit(game, unit_b, 16.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, admech_player, "SHOOTING_PHASE", 0)

    pending = _pending_by_name(admech_player.stratagems, "BINHARIC OFFENCE")
    assert pending is not None
    assert list(pending.get("enemy_candidates") or [])

    profile = _ranged_profile()
    assert profile.get_effective_ap(unit_a.models[0], enemy) == 0
    assert profile.get_effective_ap(unit_b.models[0], enemy) == 0

    ok = admech_player.stratagems.use(
        "BINHARIC OFFENCE",
        unit=unit_a,
        secondary_unit=unit_b,
        enemy_unit=enemy,
        phase_name="Shooting phase",
    )
    assert ok is True
    assert profile.get_effective_ap(unit_a.models[0], enemy) == -1
    assert profile.get_effective_ap(unit_b.models[0], enemy) == -1

    game.event_system.publish("phase_end", player=admech_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert profile.get_effective_ap(unit_a.models[0], enemy) == 0
    assert profile.get_effective_ap(unit_b.models[0], enemy) == 0


def test_binharic_offence_rejects_selection_with_fewer_than_two_units():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    unit_a = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(unit_a)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit_a, 10.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, admech_player, "SHOOTING_PHASE", 0)
    ok = admech_player.stratagems.use(
        "BINHARIC OFFENCE",
        unit=unit_a,
        enemy_unit=enemy,
        phase_name="Shooting phase",
    )
    assert ok is False


def test_bionic_endurance_queues_on_enemy_shooting_targets_and_applies_fnp():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    defender = _make_unit(
        "Sicarian Ruststalkers",
        keywords=["INFANTRY", "SICARIAN", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit(
        "Enemy Hellblasters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 24.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])

    pending = _pending_by_name(admech_player.stratagems, "BIONIC ENDURANCE")
    assert pending is not None

    ok = admech_player.stratagems.use(
        "BIONIC ENDURANCE",
        unit=defender,
        attacking_unit=attacker,
        target_units=[defender],
        phase_name="Shooting phase",
    )
    assert ok is True

    entries = list((getattr(defender, "special_rules", {}) or {}).get("defensive_fnp_overrides") or [])
    assert any(
        int(entry.get("value", 0) or 0) == 5
        and str(entry.get("source", "") or "").strip().upper() == "BIONIC ENDURANCE"
        for entry in entries
        if isinstance(entry, dict)
    )


def test_expedited_purge_protocol_allows_charge_after_advance_until_charge_phase_end():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    unit = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Legionaries",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    unit.round_state.advanced_this_round = True
    _set_phase(game, admech_player, "CHARGE_PHASE", 0)

    assert unit.can_charge_after_advance() is False
    ok = admech_player.stratagems.use(
        "EXPEDITED PURGE PROTOCOL",
        unit=unit,
        phase_name="Charge phase",
    )
    assert ok is True
    assert unit.can_charge_after_advance() is True

    game.event_system.publish("phase_end", player=admech_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    assert unit.can_charge_after_advance() is False


def test_isolate_and_destroy_only_applies_against_isolated_targets():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    shooter = _make_unit(
        "Sicarian Infiltrators",
        keywords=["INFANTRY", "SICARIAN", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    crowded_target = _make_unit(
        "Enemy Crowded Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    nearby_enemy = _make_unit(
        "Enemy Nearby Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    isolated_target = _make_unit(
        "Enemy Isolated Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(shooter)
    enemy_army.add_unit(crowded_target)
    enemy_army.add_unit(nearby_enemy)
    enemy_army.add_unit(isolated_target)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, crowded_target, 24.0, 10.0)
    _deploy_unit(game, nearby_enemy, 28.0, 10.0)
    _deploy_unit(game, isolated_target, 42.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, admech_player, "SHOOTING_PHASE", 0)
    ok = admech_player.stratagems.use(
        "ISOLATE AND DESTROY",
        unit=shooter,
        phase_name="Shooting phase",
    )
    assert ok is True

    profile = _ranged_profile()
    crowded_result = profile._wound_target_with_tracking(
        crowded_target,
        shooter.models[0],
        dict(_attack_instance()),
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    isolated_result = profile._wound_target_with_tracking(
        isolated_target,
        shooter.models[0],
        dict(_attack_instance()),
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("ISOLATE AND DESTROY" in text for text in list(crowded_result.get("modifiers", []) or []))
    assert any("ISOLATE AND DESTROY" in text for text in list(isolated_result.get("modifiers", []) or []))


def test_shroud_protocols_queues_on_enemy_shooting_targets_and_limits_range_until_phase_end():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    defender = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    attacker = _make_unit(
        "Enemy Havocs",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 30.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])

    pending = _pending_by_name(admech_player.stratagems, "SHROUD PROTOCOLS")
    assert pending is not None

    ok = admech_player.stratagems.use(
        "SHROUD PROTOCOLS",
        unit=defender,
        attacking_unit=attacker,
        target_units=[defender],
        phase_name="Shooting phase",
    )
    assert ok is True

    limit, sources = defender.get_ranged_targeting_restriction(game_map=game.map)
    assert limit == 18.0
    assert "SHROUD PROTOCOLS" in [str(source or "").upper() for source in list(sources or [])]

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    limit_after, sources_after = defender.get_ranged_targeting_restriction(game_map=game.map)
    assert limit_after is None
    assert "SHROUD PROTOCOLS" not in [str(source or "").upper() for source in list(sources_after or [])]


def test_programmed_withdrawal_queues_at_opponent_fight_phase_end_and_places_units_in_reserves():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    sicarian_a = _make_unit(
        "Sicarian Ruststalkers Alpha",
        keywords=["INFANTRY", "SICARIAN", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    sicarian_b = _make_unit(
        "Sicarian Ruststalkers Beta",
        keywords=["INFANTRY", "SICARIAN", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Assault Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(sicarian_a)
    admech_army.add_unit(sicarian_b)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, sicarian_a, 10.0, 10.0)
    _deploy_unit(game, sicarian_b, 16.0, 10.0)
    _deploy_unit(game, enemy, 22.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    calls = []

    def _make_reserve_stub(unit_name: str):
        def _enter_strategic_reserves_midgame(*, game=None, game_map=None, reason=""):
            calls.append((unit_name, game is not None, game_map is not None, str(reason or "")))
            return True

        return _enter_strategic_reserves_midgame

    sicarian_a.enter_strategic_reserves_midgame = _make_reserve_stub(sicarian_a.name)
    sicarian_b.enter_strategic_reserves_midgame = _make_reserve_stub(sicarian_b.name)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(admech_player.stratagems, "PROGRAMMED WITHDRAWAL")
    assert pending is not None

    ok = admech_player.stratagems.use(
        "PROGRAMMED WITHDRAWAL",
        units=[sicarian_a, sicarian_b],
        phase_name="Fight phase",
    )
    assert ok is True
    assert calls == [
        (sicarian_a.name, True, True, "PROGRAMMED WITHDRAWAL"),
        (sicarian_b.name, True, True, "PROGRAMMED WITHDRAWAL"),
    ]


def test_programmed_withdrawal_rejects_mixed_two_unit_selection():
    game, admech_army, enemy_army, admech_player, enemy_player = _build_game()
    sicarian = _make_unit(
        "Sicarian Ruststalkers",
        keywords=["INFANTRY", "SICARIAN", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Assault Squad",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(sicarian)
    admech_army.add_unit(skitarii)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, sicarian, 10.0, 10.0)
    _deploy_unit(game, skitarii, 16.0, 10.0)
    _deploy_unit(game, enemy, 22.0, 10.0)
    _finalize_game(game, admech_army, enemy_army, players=[admech_player, enemy_player])

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = admech_player.stratagems.use(
        "PROGRAMMED WITHDRAWAL",
        units=[sicarian, skitarii],
        phase_name="Fight phase",
    )
    assert ok is False
