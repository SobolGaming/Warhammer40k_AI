from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        wounds: int = 12,
        base_size: str = "100mm",
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
                "Ld": "6",
                "OC": "8" if "VEHICLE" in set(self.keywords) else "2",
                "base_size": str(base_size),
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "name": str(entry.get("name", "")),
                "description": str(entry.get("description", "")),
                "type": str(entry.get("type", "Ability")),
                "parameter": entry.get("parameter"),
            }
            for entry in list(abilities or [])
        ]
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Imperial Knights",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    wounds: int = 12,
    base_size: str = "100mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            wounds=wounds,
            base_size=base_size,
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
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    ik_army = Army.with_detachment("Imperial Knights", detachment_type="Freeblade Company")
    ik_army.faction_id = "QI"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    ik_player = Player("IK", PlayerControl.LOCAL, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.current_player_idx = 0
    ik_player.command_points = 10
    enemy_player.command_points = 10
    return game, ik_army, enemy_army, ik_player, enemy_player


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
    wanted = str(name or "").replace("\u2019", "'").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        reaction_name = str(reaction.get("stratagem", "") or "").replace("\u2019", "'").strip().upper()
        if reaction_name == wanted:
            return reaction
    return None


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="QI",
        detachment="Freeblade Company",
        points=0,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _make_ranged_profile(*, strength: str = "5") -> WargearProfile:
    parent = SimpleNamespace(name="Test Cannon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Test Cannon",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_blast_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Siege Mortar", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Siege Mortar",
        wargear_data={
            "range": "24",
            "A": "D6",
            "BS_WS": "3+",
            "S": "8",
            "AP": "-1",
            "D": "2",
            "description": "Blast",
        },
        parent_wargear=parent,
    )


@pytest.mark.parametrize(
    ("enhancement_id", "name", "effect"),
    [
        ("000010755002", "Bringer of Justice", "bearer_melee_attacks_bonus_and_hit_bonus"),
        ("000010755003", "Hunter's Eye", "bearer_ranged_weapons_gain_keywords"),
        ("000010755004", "Mysterious Guardian", "bearer_deep_strike_and_end_of_opponent_turn_strategic_reserves"),
        ("000010755005", "Sanctuary", "bearer_unit_invulnerable_save"),
    ],
)
def test_freeblade_enhancement_descriptors_registered(enhancement_id: str, name: str, effect: str) -> None:
    by_id = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
    by_name = get_enhancement_tool_descriptor(name=name)
    assert by_id is not None
    assert by_name is not None
    assert by_id.name == name
    assert by_name.name == name
    assert by_id.effect == effect


@pytest.mark.parametrize(
    ("stratagem_id", "name", "effect"),
    [
        ("000010756003", "STRENGTH FROM EXILE", "reroll_hit_and_wound_ones_if_no_other_friendly_units_within_9"),
        ("000010756002", "NOBLE SACRIFICE", "deadly_demise_trigger_threshold_on_destroyed_unit"),
        ("000010756006", "SURVIVOR OF STRIFE", "worsen_incoming_wound_roll_if_strength_gt_toughness"),
        ("000010756007", "FLANKING MANOEUVRES", "enter_strategic_reserves"),
        ("000010756005", "POINT-BLANK BARRAGE", "blast_can_target_own_engagement_with_self_mortal_backlash"),
        ("000010756004", "FULL TILT", "fixed_advance_distance_by_keyword"),
    ],
)
def test_freeblade_stratagem_descriptors_registered(stratagem_id: str, name: str, effect: str) -> None:
    by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=name)
    by_name = get_stratagem_tool_descriptor(name=name)
    assert by_id is not None
    assert by_name is not None
    assert by_id.name == name
    if str(name).upper() != "FULL TILT":
        assert by_name.name == name
    assert by_id.effect == effect


def test_knights_of_legend_heals_and_grants_feel_no_pain() -> None:
    game, ik_army, _enemy_army, ik_player, enemy_player = _build_game()
    knight = _make_unit(
        "Knight Paladin",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        wounds=12,
    )
    ik_army.add_unit(knight)
    _deploy_unit(game, knight, 10.0, 10.0)
    _finalize_game(game, ik_army, players=[ik_player, enemy_player])

    knight.models[0].wounds = 9
    fnp_entries = list(knight.has_feel_no_pain(target_model=knight.models[0]) or [])
    assert (6, "Knights of Legend") in fnp_entries

    ik_army.imperial_knights_detachments.on_command_phase_start(game=game, player=ik_player)
    assert int(knight.models[0].wounds or 0) == 10


def test_freeblade_enhancements_apply_expected_bonuses() -> None:
    game, ik_army, _enemy_army, ik_player, enemy_player = _build_game()
    bringer = _make_unit(
        "Knight Gallant",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "CHARACTER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    hunter = _make_unit(
        "Knight Crusader",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "CHARACTER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    sanctuary = _make_unit(
        "Knight Warden",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "CHARACTER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    for unit, x in ((bringer, 10.0), (hunter, 20.0), (sanctuary, 30.0)):
        ik_army.add_unit(unit)
        _deploy_unit(game, unit, x, 10.0)
    _finalize_game(game, ik_army, players=[ik_player, enemy_player])

    _apply_enhancement(bringer, enhancement_id="000010755002", enhancement_name="Bringer of Justice")
    _apply_enhancement(hunter, enhancement_id="000010755003", enhancement_name="Hunter's Eye")
    _apply_enhancement(sanctuary, enhancement_id="000010755005", enhancement_name="Sanctuary")

    bringer_sr = dict(getattr(bringer, "special_rules", {}) or {})
    assert int(bringer_sr.get("enhancement_bearer_melee_attacks_bonus", 0) or 0) == 2
    assert int(bringer_sr.get("enhancement_bearer_melee_hit_bonus", 0) or 0) == 1

    hunter_bonuses = hunter.get_model_weapon_keyword_bonuses(model=hunter.models[0], attack_type="ranged")
    assert bool(hunter_bonuses.get("ignores_cover"))
    assert any("Hunter" in str(source or "") for source in list(hunter_bonuses.get("sources", []) or []))

    invuln, source = sanctuary.get_model_invulnerable_save_override(sanctuary.models[0])
    assert int(invuln or 0) == 5
    assert "Sanctuary" in str(source or "")


def test_mysterious_guardian_grants_deep_strike_and_end_of_opponent_turn_reserves_ability() -> None:
    game, ik_army, enemy_army, ik_player, enemy_player = _build_game()
    guardian = _make_unit(
        "Knight Errant",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "CHARACTER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit("Enemy Squad", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ik_army.add_unit(guardian)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, guardian, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    _finalize_game(game, ik_army, enemy_army, players=[ik_player, enemy_player])

    _apply_enhancement(guardian, enhancement_id="000010755004", enhancement_name="Mysterious Guardian")

    assert guardian.has_deep_strike()
    ability = guardian.get_end_of_opponent_turn_strategic_reserves_ability()
    assert isinstance(ability, dict)
    assert str(ability.get("ability_key", "") or "") == "mysterious_guardian"
    assert bool(ability.get("once_per_battle"))


@pytest.mark.parametrize(
    ("name", "keywords", "distance"),
    [
        ("Knight Paladin", ["IMPERIAL KNIGHTS", "VEHICLE"], 6),
        ("Armiger Helverin", ["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"], 9),
        ("Knight Destrier", ["IMPERIAL KNIGHTS", "VEHICLE"], 9),
    ],
)
def test_freeblade_full_tilt_sets_fixed_advance_and_cleans_up(name: str, keywords: list[str], distance: int) -> None:
    game, ik_army, enemy_army, ik_player, enemy_player = _build_game()
    unit = _make_unit(name, keywords=keywords, faction_keywords=["IMPERIAL KNIGHTS"])
    ik_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    _finalize_game(game, ik_army, players=[ik_player, enemy_player])

    _set_phase(game, ik_player, "MOVEMENT_PHASE", 0)
    assert ik_player.stratagems.use("FULL TILT", unit=unit, phase_name="Movement phase")

    effect = unit._get_advance_no_roll_effect()
    assert effect is not None
    assert int(effect.get("distance", 0) or 0) == int(distance)

    game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert unit._get_advance_no_roll_effect() is None


def test_strength_from_exile_grants_reroll_ones_only_while_isolated() -> None:
    game, ik_army, enemy_army, ik_player, enemy_player = _build_game()
    knight = _make_unit(
        "Knight Crusader",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    ally = _make_unit(
        "Knight Warden",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit("Enemy Target", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ik_army.add_unit(knight)
    ik_army.add_unit(ally)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, knight, 10.0, 10.0)
    _deploy_unit(game, ally, 30.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    _finalize_game(game, ik_army, enemy_army, players=[ik_player, enemy_player])

    profile = _make_ranged_profile(strength="5")
    _set_phase(game, ik_player, "SHOOTING_PHASE", 0)
    assert ik_player.stratagems.use("STRENGTH FROM EXILE", unit=knight, phase_name="Shooting phase")

    hit_result = profile._hit_target_with_tracking(
        enemy,
        knight.models[0],
        {"distance_to_target": 6.0},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    wound_result = profile._wound_target_with_tracking(
        enemy,
        knight.models[0],
        {"distance_to_target": 6.0},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert 1 in list(hit_result.get("reroll_values", []) or [])
    assert any("Strength from Exile" in str(reason or "") for reason in list(hit_result.get("reroll_value_reasons", []) or []))
    assert 1 in list(wound_result.get("reroll_values", []) or [])
    assert any("Strength from Exile" in str(reason or "") for reason in list(wound_result.get("reroll_value_reasons", []) or []))

    ally.models[0].set_location(15.0, 10.0, 0.0, 0.0)
    hit_blocked = profile._hit_target_with_tracking(
        enemy,
        knight.models[0],
        {"distance_to_target": 6.0},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    wound_blocked = profile._wound_target_with_tracking(
        enemy,
        knight.models[0],
        {"distance_to_target": 6.0},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert 1 not in list(hit_blocked.get("reroll_values", []) or [])
    assert 1 not in list(wound_blocked.get("reroll_values", []) or [])


def test_survivor_of_strife_queues_on_enemy_target_selection_and_applies_wound_penalty() -> None:
    game, ik_army, enemy_army, ik_player, enemy_player = _build_game()
    knight = _make_unit(
        "Knight Paladin",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit("Enemy Shooters", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ik_army.add_unit(knight)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, knight, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, ik_army, enemy_army, players=[ik_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[knight])

    pending = _pending_by_name(ik_player.stratagems, "SURVIVOR OF STRIFE")
    assert pending is not None

    assert ik_player.stratagems.use("SURVIVOR OF STRIFE", phase_name="Shooting phase", dequeue=True)
    effects = list(getattr(knight, "special_rules", {}).get("defensive_wound_mods", []) or [])
    assert any(
        int(entry.get("value", 0) or 0) == 1 and bool(entry.get("requires_strength_gt_toughness"))
        for entry in effects
        if isinstance(entry, dict)
    )


def test_flanking_manoeuvres_queues_and_enters_strategic_reserves() -> None:
    game, ik_army, enemy_army, ik_player, enemy_player = _build_game()
    armiger = _make_unit(
        "Armiger Helverin",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        base_size="60mm",
    )
    enemy = _make_unit("Enemy Brawlers", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ik_army.add_unit(armiger)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, armiger, 4.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    _finalize_game(game, ik_army, enemy_army, players=[ik_player, enemy_player])

    calls: list[tuple[bool, bool, str]] = []

    def _enter_strategic_reserves_midgame(*, game=None, game_map=None, reason=""):
        calls.append((game is not None, game_map is not None, str(reason or "")))
        return True

    armiger.enter_strategic_reserves_midgame = _enter_strategic_reserves_midgame

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(ik_player.stratagems, "FLANKING MANOEUVRES")
    assert pending is not None
    assert ik_player.stratagems.use("FLANKING MANOEUVRES", phase_name="Fight phase", dequeue=True)
    assert calls == [(True, True, "FLANKING MANOEUVRES")]


def test_noble_sacrifice_queues_and_lowers_deadly_demise_threshold() -> None:
    game, ik_army, enemy_army, ik_player, enemy_player = _build_game()
    knight = _make_unit(
        "Knight Gallant",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=[
            {
                "name": "Deadly Demise",
                "description": "Deadly Demise",
                "type": "Ability",
                "parameter": "D3",
            }
        ],
    )
    enemy = _make_unit("Enemy Victim", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ik_army.add_unit(knight)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, knight, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    _finalize_game(game, ik_army, enemy_army, players=[ik_player, enemy_player])

    destroyed_model = knight.models[0]
    knight.models = []
    knight.models_lost.append(destroyed_model)
    destroyed_model.wounds = 0

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ik_player.stratagems._on_model_destroyed_before_removal(unit=knight, model=destroyed_model)

    pending = _pending_by_name(ik_player.stratagems, "NOBLE SACRIFICE")
    assert pending is not None
    assert ik_player.stratagems.use("NOBLE SACRIFICE", phase_name="Fight phase", dequeue=True)
    assert int(getattr(destroyed_model, "_imperial_knights_noble_sacrifice_trigger_threshold_once", 0) or 0) == 4

    explosion_calls = []
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=4), patch.object(
        knight,
        "_apply_deadly_demise_explosion",
        side_effect=lambda **kwargs: explosion_calls.append(dict(kwargs)),
    ):
        triggered = knight._trigger_deadly_demise(destroyed_model, game.map)
    assert triggered is False
    assert len(explosion_calls) == 1
    assert explosion_calls[0]["game_map"] is game.map
    assert int(getattr(destroyed_model, "_imperial_knights_noble_sacrifice_trigger_threshold_once", 0) or 0) == 0


def test_point_blank_barrage_allows_blast_into_own_engagement_and_applies_backlash() -> None:
    game, ik_army, enemy_army, ik_player, enemy_player = _build_game()
    knight = _make_unit(
        "Knight Crusader",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    ally = _make_unit(
        "Knight Support",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit("Enemy Screen", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ik_army.add_unit(knight)
    ik_army.add_unit(ally)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, knight, 10.0, 10.0)
    _deploy_unit(game, ally, 30.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    _finalize_game(game, ik_army, enemy_army, players=[ik_player, enemy_player])

    _set_phase(game, ik_player, "SHOOTING_PHASE", 0)
    assert ik_player.stratagems.use("POINT-BLANK BARRAGE", unit=knight, phase_name="Shooting phase")
    assert knight._ignore_engagement_for_ranged_targeting_active(game=game, phase_name="Shooting phase")

    blast_profile = _make_blast_profile()
    assert knight._can_model_shoot_weapon_at_target(knight.models[0], blast_profile, enemy, game.map)

    ally.models[0].set_location(13.5, 10.0, 0.0, 0.0)
    assert not knight._can_model_shoot_weapon_at_target(knight.models[0], blast_profile, enemy, game.map)
    ally.models[0].set_location(30.0, 10.0, 0.0, 0.0)

    knight._model_has_weapon_profile = lambda _model, _profile: True
    blast_profile.attack = lambda *_args, **_kwargs: SimpleNamespace(
        total_hits=1,
        hit_results=[{"roll": 1}, {"roll": 4}],
        models_killed=0,
        total_damage_dealt=0,
    )
    knight.models[0].wounds = 12

    knight._execute_weapon_attacks(
        blast_profile,
        enemy,
        [knight.models[0]],
        game.map,
        skip_target_checks=True,
        target_was_within_attacker_engagement=True,
    )
    assert int(getattr(knight, "special_rules", {}).get("freeblade_point_blank_barrage_pending_mortal_wounds", 0) or 0) == 1

    game.event_system.publish("unit_shooting_resolved", attacker_unit=knight)
    assert int(knight.models[0].wounds or 0) == 11
    assert int(getattr(knight, "special_rules", {}).get("freeblade_point_blank_barrage_pending_mortal_wounds", 0) or 0) == 0
