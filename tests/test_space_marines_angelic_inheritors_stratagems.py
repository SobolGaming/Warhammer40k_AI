from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile


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
        self.datasheets_abilities = []
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
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "Angelic Inheritors")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)

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


def _melee_wargear(name: str = "Encarmine Blade") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-2",
            "D": "2",
            "description": "",
        }
    )


def _ranged_wargear(name: str = "Bolt Rifle") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        }
    )


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Enemy Rifle", is_ranged=lambda: True, is_melee=lambda: False)
    profile = WargearProfile(
        profile_name="Default",
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
    profile.is_indirect_fire = lambda: True
    profile.is_torrent = lambda: False
    profile.is_pistol = lambda: False
    profile.is_blast = lambda: False
    return profile


def test_angelic_inheritors_stratagem_descriptors_registered():
    expected = {
        "000009836003": ("Focused Fury", "melee_lethal_hits_and_conditional_lance"),
        "000009836006": ("In the Shadow of Great Wings", "ranged_targeting_range_restriction"),
        "000009836004": ("Instant of Grace", "temporary_model_character_keyword_and_unit_character_status"),
        "000009836005": ("Strike Now for Glory", "ranged_sustained_hits"),
        "000009836007": ("Unto the Burning Skies", "enter_strategic_reserves"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_focused_fury_queues_grants_melee_keywords_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    captain = _make_unit(
        "Captain",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    captain.models[0].wargear = [_melee_wargear()]
    sm_army.add_unit(captain)
    _deploy_unit(game, captain, 10.0, 10.0)

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "FOCUSED FURY")
    assert pending is not None

    ok = sm_player.stratagems.use("FOCUSED FURY", unit=captain, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    bonuses = captain.models[0].get_temporary_weapon_keyword_bonuses("Encarmine Blade")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "LETHAL HITS"
        and str(item.get("attack_type", "") or "").strip().lower() == "melee"
        for item in list(bonuses or [])
    )
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "LANCE"
        and str(item.get("attack_type", "") or "").strip().lower() == "melee"
        for item in list(bonuses or [])
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    bonuses_after = captain.models[0].get_temporary_weapon_keyword_bonuses("Encarmine Blade")
    assert list(bonuses_after or []) == []


def test_strike_now_for_glory_queues_grants_ranged_sustained_hits_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors.models[0].wargear = [_ranged_wargear()]
    sm_army.add_unit(intercessors)
    _deploy_unit(game, intercessors, 10.0, 10.0)

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "STRIKE NOW FOR GLORY")
    assert pending is not None

    ok = sm_player.stratagems.use("STRIKE NOW FOR GLORY", unit=intercessors, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    bonuses = intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "SUSTAINED HITS 1"
        and str(item.get("attack_type", "") or "").strip().lower() == "ranged"
        for item in list(bonuses or [])
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    bonuses_after = intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle")
    assert list(bonuses_after or []) == []


def test_in_the_shadow_of_great_wings_queues_applies_targeting_cap_and_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    defender = _make_unit(
        "Captain",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 30.0, 10.0)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])
    pending = _pending_by_name(sm_player.stratagems, "IN THE SHADOW OF GREAT WINGS")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "IN THE SHADOW OF GREAT WINGS",
        unit=defender,
        attacking_unit=attacker,
        target_units=[defender],
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    limit, sources = defender.get_ranged_targeting_restriction(game_map=game.map)
    assert float(limit or 0.0) == 18.0
    assert any("SHADOW OF GREAT WINGS" in str(source).upper() for source in list(sources or []))

    can_target_far = attacker._can_model_shoot_weapon_at_target(
        attacker.models[0],
        _ranged_profile(),
        defender,
        game.map,
    )
    assert not can_target_far

    attacker.models[0].set_location(24.0, 10.0, 0.0, 0.0)
    can_target_near = attacker._can_model_shoot_weapon_at_target(
        attacker.models[0],
        _ranged_profile(),
        defender,
        game.map,
    )
    assert can_target_near

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    sr_after = getattr(defender, "special_rules", {}) or {}
    assert not bool(sr_after.get("space_marines_in_the_shadow_active"))
    _limit_after, sources_after = defender.get_ranged_targeting_restriction(game_map=game.map)
    assert not any("SHADOW OF GREAT WINGS" in str(source).upper() for source in list(sources_after or []))


def test_instant_of_grace_queues_makes_unit_character_for_legacy_and_expires_next_command_phase():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    assault = _make_unit(
        "Assault Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
    )
    sm_army.add_unit(assault)
    _deploy_unit(game, assault, 10.0, 10.0)
    mgr = sm_army.space_marines_detachments
    assert mgr.select_angelic_legacy_options(["SANGUINARY_GRACE", "CARMINE_WRATH"], battle_round=1)
    assert not mgr.legacy_of_the_angel_sanguinary_grace_applies(assault)

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "INSTANT OF GRACE")
    assert pending is not None

    selected_model = assault.models[1]
    ok = sm_player.stratagems.use(
        "INSTANT OF GRACE",
        unit=assault,
        target_model=selected_model,
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert selected_model.has_keyword("CHARACTER")
    assert mgr.legacy_of_the_angel_sanguinary_grace_applies(assault)

    game.turn = 2
    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert not selected_model.has_keyword("CHARACTER")
    assert not mgr.legacy_of_the_angel_sanguinary_grace_applies(assault)


def test_unto_the_burning_skies_queues_enters_strategic_reserves_and_sanguinor_exception_applies():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    jump_unit = _make_unit(
        "Vanguard Veterans",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sanguinor = _make_unit(
        "The Sanguinor",
        keywords=["INFANTRY", "CHARACTER", "JUMP PACK", "FLY", "THE SANGUINOR"],
        faction_keywords=["ADEPTUS ASTARTES", "BLOOD ANGELS"],
    )
    enemy = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(jump_unit)
    sm_army.add_unit(sanguinor)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, jump_unit, 10.0, 10.0)
    _deploy_unit(game, sanguinor, 14.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.map.is_within_engagement_range = (
        lambda unit_a, unit_b: {
            frozenset({jump_unit, enemy}),
            frozenset({sanguinor, enemy}),
        }.__contains__(frozenset({unit_a, unit_b}))
    )

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(sm_player.stratagems, "UNTO THE BURNING SKIES")
    assert pending is not None
    candidate_names = {str(getattr(unit, "name", "") or "") for unit in list(pending.get("candidates") or [])}
    assert "The Sanguinor" in candidate_names
    assert "Vanguard Veterans" not in candidate_names

    ok = sm_player.stratagems.use("UNTO THE BURNING SKIES", unit=sanguinor, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert str(getattr(sanguinor, "reserve_status", "") or "") == "strategic_reserves"
    assert sanguinor not in list(getattr(game.map, "units", []) or [])
