from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules, validate_final_position


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: str = "1",
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "5",
                "W": str(wounds),
                "Ld": "8",
                "OC": "2",
                "base_size": "28mm",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None, wounds: str = "1", quantity: int = 1) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            model_count=quantity,
        ),
        quantity=quantity,
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army.with_detachment("Tyranids", "Unending Swarm")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyranids", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)

    tyr_player.command_points = 10
    enemy_player.command_points = 10
    tyr_army.configure_rule_managers(force=True)
    tyr_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _make_profile(
    *,
    weapon_name: str,
    is_melee: bool,
    attacks: str = "1",
    skill: str = "4+",
    strength: str = "4",
    description: str = "",
) -> WargearProfile:
    parent = SimpleNamespace(
        name=weapon_name,
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )
    return WargearProfile(
        profile_name="Default",
        wargear_data={
            "range": "24",
            "A": attacks,
            "BS_WS": skill,
            "S": strength,
            "AP": "0",
            "D": "1",
            "description": description,
        },
        parent_wargear=parent,
    )


def _ranged_profile(name: str = "Fleshborer") -> WargearProfile:
    return _make_profile(weapon_name=name, is_melee=False)


def _melee_profile(name: str = "Scything Talons") -> WargearProfile:
    return _make_profile(weapon_name=name, is_melee=True, skill="3+")


def _blast_profile(name: str = "Spinefists") -> WargearProfile:
    return _make_profile(weapon_name=name, is_melee=False, attacks="D6", description="[BLAST]")


def test_bounding_advance_descriptor_registered():
    expected = {
        "000008409002": ("Synaptic Goading", "horde_move_reroll_and_objective_override"),
        "000008409003": ("Unending Waves", "clone_unit_to_strategic_reserves"),
        "000008409004": ("Teeming Masses", "defensive_hit_penalty_vs_attacker"),
        "000008409005": ("Swarming Masses", "sustained_hits_and_conditional_crit_hit_threshold"),
        "000008409006": ("Bounding Advance", "advance_no_roll_plus_6"),
        "000008409007": ("Preservation Imperative", "blast_model_count_cap"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert desc is not None
        assert desc.name == expected_name
        assert desc.effect == expected_effect
    bounding = get_stratagem_tool_descriptor(stratagem_id="000008409006")
    assert int(bounding.effect_params.get("advance_distance", 0) or 0) == 6


def test_bounding_advance_sets_fixed_advance_and_cleans_up_at_phase_end():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    ok = tyr_player.stratagems.use("BOUNDING ADVANCE", unit=unit, phase_name="Movement phase")
    assert ok
    assert int(tyr_player.command_points or 0) == 9

    effect = unit._get_advance_no_roll_effect()
    assert effect is not None
    assert int(effect.get("distance", 0) or 0) == 6
    assert str(effect.get("tag", "") or "") == "stratagem:tyranids_bounding_advance"

    roll = unit.prepare_advance()
    assert int(roll or 0) == 6
    assert int(getattr(unit.round_state, "advance_roll", 0) or 0) == 6

    game.event_system.publish("phase_end", player=tyr_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert unit._get_advance_no_roll_effect() is None


def test_bounding_advance_requires_endless_multitude_unit():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Warriors",
        keywords=["INFANTRY", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    ok = tyr_player.stratagems.use("BOUNDING ADVANCE", unit=unit, phase_name="Movement phase")
    assert not ok


def test_bounding_advance_requires_target_not_selected_to_move():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Hormagaunts",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    tyr_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)

    _set_phase(game, tyr_player, "MOVEMENT_PHASE", 0)
    unit.round_state.moved_this_round = True
    ok = tyr_player.stratagems.use("BOUNDING ADVANCE", unit=unit, phase_name="Movement phase")
    assert not ok


def test_teeming_masses_queues_on_enemy_target_selection_and_cleans_up_hit_penalty():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    defender = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
        quantity=12,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])
    pending = _pending_by_name(tyr_player.stratagems, "TEEMING MASSES")
    assert pending is not None

    ok = tyr_player.stratagems.use("TEEMING MASSES", phase_name="Shooting phase", dequeue=True)
    assert ok
    hit_mods = list(defender.special_rules.get("defensive_hit_mods", []) or [])
    assert any("TEEMING MASSES" in str(entry.get("source", "")).upper() for entry in hit_mods if isinstance(entry, dict))

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(defender.special_rules.get("defensive_hit_mods", []) or []) == []


def test_preservation_imperative_caps_blast_model_count_this_phase():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    defender = _make_unit(
        "Hormagaunts",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
        quantity=10,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])
    assert _pending_by_name(tyr_player.stratagems, "PRESERVATION IMPERATIVE") is not None
    assert tyr_player.stratagems.use("PRESERVATION IMPERATIVE", phase_name="Shooting phase", dequeue=True)

    profile = _blast_profile()
    attack_result = SimpleNamespace(attacks_rolled=0, attacks_dice_rolls=[], attacks_special_modifiers=[])
    count = profile._resolve_attack_count(
        defender,
        attacker.models[0],
        attack_result,
        game_map=game.map,
        roll_value=2,
    )
    assert int(count.num_attacks) == 2
    assert any("Blast +0" in str(entry or "") for entry in list(attack_result.attacks_special_modifiers or []))

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert "tyranids_preservation_imperative_active" not in defender.special_rules


def test_swarming_masses_grants_ranged_sustained_hits_and_crit_hits_on_five_plus_at_fifteen_models():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
        quantity=16,
    )
    defender = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(attacker)
    enemy_army.add_unit(defender)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, defender, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "SHOOTING_PHASE", 0)
    assert tyr_player.stratagems.use("SWARMING MASSES", unit=attacker, phase_name="Shooting phase")
    assert int(attacker.special_rules.get("bearer_unit_sustained_hits_value_ranged", 0) or 0) == 1

    profile = _ranged_profile()
    attack_instance = {
        "target_model": defender.models[0],
        "crit_hit": False,
        "crit_wound": False,
        "mortal_wound": False,
        "below_half_distance": False,
        "damage": 0,
        "target_toughness_override": None,
    }
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        hit = profile._hit_target_with_tracking(defender, attacker.models[0], attack_instance, roll_value=5)
    assert bool(hit.get("hit"))
    assert int(hit.get("crit_threshold", 0) or 0) == 5
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1

    game.event_system.publish("phase_end", player=tyr_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert "bearer_unit_sustained_hits_value_ranged" not in attacker.special_rules
    assert "tyranids_swarming_masses_active" not in attacker.special_rules


def test_swarming_masses_grants_melee_sustained_hits_until_fight_phase_end():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Hormagaunts",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
        quantity=12,
    )
    defender = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(attacker)
    enemy_army.add_unit(defender)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, defender, 11.5, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    assert tyr_player.stratagems.use("SWARMING MASSES", unit=attacker, phase_name="Fight phase")
    profile = _melee_profile()
    attack_instance = {
        "target_model": defender.models[0],
        "crit_hit": False,
        "crit_wound": False,
        "mortal_wound": False,
        "below_half_distance": False,
        "damage": 0,
        "target_toughness_override": None,
    }
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        hit = profile._hit_target_with_tracking(defender, attacker.models[0], attack_instance)
    assert bool(hit.get("hit"))
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1

    game.event_system.publish("phase_end", player=tyr_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert "bearer_unit_sustained_hits_value_melee" not in attacker.special_rules
    assert "tyranids_swarming_masses_active" not in attacker.special_rules


def test_synaptic_goading_queues_for_pending_surge_move_and_allows_reroll_and_objective_override():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    target = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
        quantity=12,
    )
    synapse = _make_unit(
        "Warriors",
        keywords=["INFANTRY", "SYNAPSE", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(target)
    tyr_army.add_unit(synapse)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, synapse, 12.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()

    objective_loc = SimpleNamespace(id="obj-a", x=6.0, y=10.0, z=0.0, removed=False)
    game.map.objectives = [SimpleNamespace(id="obj-a", location=objective_loc)]

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[target])
    target.models[0].wounds = 0
    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={target: 1})

    assert _pending_by_name(tyr_player.stratagems, "SYNAPTIC GOADING") is not None
    assert tyr_player.stratagems.use("SYNAPTIC GOADING", unit=target, phase_name="Shooting phase", dequeue=True)

    rules = get_validation_rules(MovementType.HORDE_MOVE, moving_unit=target)
    assert bool(rules.get("allow_closest_objective_marker_instead_of_closest_enemy_unit", False))
    rules["blood_surge_max_distance"] = 6.0
    valid = validate_final_position(target.models[1], (6.0, 10.0, 0.0), rules, game.map)
    assert bool(valid.get("valid", False))

    provider_calls: list[dict] = []
    game.map.roll_reroll_provider = lambda **kw: provider_calls.append(dict(kw)) or True
    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[2, 5]):
        distance = game.roll_horde_move_distance(target)
    assert distance == 5
    assert provider_calls
    assert provider_calls[0]["roll_type"] == "horde_move"
    assert provider_calls[0]["allow_reroll"] is True
    assert provider_calls[0]["source"] == "SYNAPTIC GOADING"


def test_synaptic_goading_allows_leaving_engagement_range_toward_closest_objective():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    target = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
        quantity=12,
    )
    synapse = _make_unit(
        "Warriors",
        keywords=["INFANTRY", "SYNAPSE", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(target)
    tyr_army.add_unit(synapse)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, synapse, 8.0, 10.0)
    _deploy_unit(game, attacker, 12.0, 10.0)
    game.rebuild_entity_registry()

    objective_loc = SimpleNamespace(id="obj-a", x=6.0, y=10.0, z=0.0, removed=False)
    game.map.objectives = [SimpleNamespace(id="obj-a", location=objective_loc)]

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[target])
    target.models[0].wounds = 0
    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={target: 1})

    assert _pending_by_name(tyr_player.stratagems, "SYNAPTIC GOADING") is not None
    assert tyr_player.stratagems.use("SYNAPTIC GOADING", unit=target, phase_name="Shooting phase", dequeue=True)

    rules = get_validation_rules(MovementType.HORDE_MOVE, moving_unit=target)
    rules["blood_surge_max_distance"] = 6.0
    valid = validate_final_position(target.models[1], (6.0, 10.0, 0.0), rules, game.map)
    assert bool(valid.get("valid", False))


def test_unending_waves_replaces_destroyed_unit_once_per_battle():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    unit = _make_unit(
        "Termagants",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
        quantity=10,
    )
    enemy = _make_unit(
        "Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    game.map.units.remove(unit)
    unit.is_alive = lambda: False
    existing_ids = {id(entry) for entry in list(tyr_army.units or [])}

    game.event_system.publish("unit_destroyed", unit=unit, destroyed_by_unit=enemy)
    assert _pending_by_name(tyr_player.stratagems, "UNENDING WAVES") is not None
    assert tyr_player.stratagems.use("UNENDING WAVES", destroyed_unit=unit, phase_name="Fight phase", dequeue=True)

    replacements = [entry for entry in list(tyr_army.units or []) if id(entry) not in existing_ids]
    assert len(replacements) == 1
    replacement = replacements[0]
    assert replacement is not unit
    assert str(getattr(replacement, "reserve_status", "") or "") == "strategic_reserves"
    assert bool(replacement.is_in_reserves())
    assert bool(replacement.is_alive())
    assert int(getattr(replacement, "starting_model_count", 0) or 0) == int(getattr(unit, "starting_model_count", 0) or 0)
    assert replacement not in list(getattr(game.map, "units", []) or [])

    tyr_player.stratagems._used_stratagems_this_phase.clear()
    assert not tyr_player.stratagems.use("UNENDING WAVES", destroyed_unit=unit, phase_name="Fight phase")
