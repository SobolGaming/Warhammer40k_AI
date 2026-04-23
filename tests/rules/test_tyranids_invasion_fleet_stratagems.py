from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: str = "6",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "5",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None, wounds: str = "6") -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army.with_detachment("Tyranids", "Invasion Fleet")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
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


def test_adrenal_surge_applies_melee_critical_hits_on_5plus():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Hormagaunts",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds="2",
    )
    target = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="6",
    )
    tyr_army.add_unit(attacker)
    enemy_army.add_unit(target)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, target, 20.0, 10.0)
    attacker.round_state.charged_this_round = True

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    ok = tyr_player.stratagems.use("ADRENAL SURGE", unit=attacker, phase_name="Fight phase")
    assert ok
    assert int(tyr_player.command_points or 0) == 8

    weapon = Wargear(
        {
            "name": "Talons",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]
    attack_state = {}
    hit = profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        attack_state,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit.get("hit") is True
    assert int(hit.get("crit_threshold", 0) or 0) == 5
    assert any("critical hit (5+)" in str(effect).lower() for effect in list(hit.get("special_effects", []) or []))


def test_adrenal_surge_allows_two_synapse_targets():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    unit_a = _make_unit(
        "Warriors Alpha",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="3",
    )
    unit_b = _make_unit(
        "Warriors Beta",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="3",
    )
    tyr_army.add_unit(unit_a)
    tyr_army.add_unit(unit_b)
    _deploy_unit(game, unit_a, 10.0, 10.0)
    _deploy_unit(game, unit_b, 25.0, 25.0)
    unit_a.round_state.charged_this_round = True
    unit_b.round_state.charged_this_round = True

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "ADRENAL SURGE",
        units=[unit_a, unit_b],
        phase_name="Fight phase",
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 8
    assert bool(unit_a.special_rules.get("tyranids_adrenal_surge_active")) is True
    assert bool(unit_b.special_rules.get("tyranids_adrenal_surge_active")) is True


def test_adrenal_surge_rejects_two_targets_when_one_is_outside_synapse():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    synapse_unit = _make_unit(
        "Hive Node",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="3",
    )
    non_synapse_unit = _make_unit(
        "Termagants",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds="1",
    )
    tyr_army.add_unit(synapse_unit)
    tyr_army.add_unit(non_synapse_unit)
    _deploy_unit(game, synapse_unit, 10.0, 10.0)
    _deploy_unit(game, non_synapse_unit, 30.0, 30.0)  # Outside 6" Synapse range.
    synapse_unit.round_state.charged_this_round = True
    non_synapse_unit.round_state.charged_this_round = True

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    blocked = tyr_player.stratagems.use(
        "ADRENAL SURGE",
        units=[synapse_unit, non_synapse_unit],
        phase_name="Fight phase",
    )
    assert not blocked
    assert int(tyr_player.command_points or 0) == 10


def test_death_frenzy_queues_and_grants_melee_fight_on_death_rule():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    defender = _make_unit(
        "Tyranid Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds="3",
    )
    attacker = _make_unit(
        "Enemy Fighters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="6",
    )
    tyr_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 12.0, 10.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[defender])
    pending = [
        r for r in list(tyr_player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == "DEATH FRENZY"
    ]
    assert len(pending) == 1

    ok = tyr_player.stratagems.use(
        "DEATH FRENZY",
        unit=defender,
        attacking_unit=attacker,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 9
    rule = defender.get_melee_fight_on_death_after_attacks_rule()
    assert rule is not None
    assert int(rule.get("threshold", 0) or 0) == 4


def test_overrun_queues_and_enables_synapse_normal_move_mode():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    unit = _make_unit(
        "Tyranid Warriors",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="3",
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="6",
    )
    tyr_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, unit, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 20.0)  # Not in Engagement Range.

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    game.event_system.publish("fight_attacks_resolved", unit=unit, target_unit=enemy)
    pending = [
        r for r in list(tyr_player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == "OVERRUN"
    ]
    assert len(pending) == 1

    ok = tyr_player.stratagems.use(
        "OVERRUN",
        unit=unit,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 9

    sr = unit.special_rules
    assert float(sr.get("stratagem_consolidate_distance_override", 0.0) or 0.0) >= 6.0
    assert bool(sr.get("stratagem_consolidate_requires_engagement")) is True
    assert bool(sr.get("tyranids_overrun_normal_move_active")) is True

    rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=unit)
    assert bool(rules.get("must_end_closer_to_enemies_or_objectives", False)) is False
    assert bool(rules.get("cannot_move_within_engagement_range", False)) is True
    assert bool(rules.get("cannot_end_in_engagement_range", False)) is True
    assert int(float(rules.get("max_distance_override", 0.0) or 0.0)) == 6


def test_rapid_regeneration_queues_and_applies_fnp_in_shooting_phase():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    defender = _make_unit(
        "Termagants",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds="2",
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="6",
    )
    tyr_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 16.0, 10.0)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])
    pending = [
        r for r in list(tyr_player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == "RAPID REGENERATION"
    ]
    assert len(pending) == 1

    ok = tyr_player.stratagems.use(
        "RAPID REGENERATION",
        unit=defender,
        attacking_unit=attacker,
        dequeue=True,
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 9

    profile = Wargear(
        {
            "name": "Test Gun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=6):
        dmg = profile._apply_damage_with_tracking(
            defender.models[0],
            attacker.models[0],
            damage_amount=1,
            is_mortal=False,
            attack_instance={},
            game_map=game.map,
        )
    assert int(dmg.get("fnp_saves", 0) or 0) == 1
    assert int(dmg.get("fnp_rolls", [{}])[0].get("needed", 0) or 0) == 6


def test_rapid_regeneration_upgrades_to_fnp_five_plus_with_synapse():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    defender = _make_unit(
        "Warrior Node",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="3",
    )
    attacker = _make_unit(
        "Enemy Fighters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="6",
    )
    tyr_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 12.0, 10.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[defender])
    ok = tyr_player.stratagems.use(
        "RAPID REGENERATION",
        unit=defender,
        attacking_unit=attacker,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok

    profile = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=5):
        dmg = profile._apply_damage_with_tracking(
            defender.models[0],
            attacker.models[0],
            damage_amount=1,
            is_mortal=False,
            attack_instance={},
            game_map=game.map,
        )
    assert int(dmg.get("fnp_saves", 0) or 0) == 1
    assert int(dmg.get("fnp_rolls", [{}])[0].get("needed", 0) or 0) == 5


def test_predatory_imperative_applies_additional_hyper_adaptation_to_selected_units():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    mgr = tyr_army.tyranids_detachments
    assert mgr.select_hyper_adaptation("SWARMING_INSTINCTS", battle_round=1)

    unit_a = _make_unit(
        "Warriors Alpha",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="3",
    )
    unit_b = _make_unit(
        "Warriors Beta",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="3",
    )
    target = _make_unit(
        "Enemy Monster",
        keywords=["MONSTER"],
        faction_keywords=["ENEMY"],
        wounds="8",
    )
    tyr_army.add_unit(unit_a)
    tyr_army.add_unit(unit_b)
    enemy_army.add_unit(target)
    _deploy_unit(game, unit_a, 10.0, 10.0)
    _deploy_unit(game, unit_b, 25.0, 25.0)
    _deploy_unit(game, target, 16.0, 10.0)

    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "PREDATORY IMPERATIVE",
        units=[unit_a, unit_b],
        adaptation="HYPER_AGGRESSION",
        phase_name="Command phase",
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 9
    assert bool(unit_a.special_rules.get("tyranids_predatory_imperative_active")) is True
    assert str(unit_a.special_rules.get("tyranids_predatory_imperative_adaptation_key", "")) == "HYPER_AGGRESSION"

    weapon = Wargear(
        {
            "name": "Talons",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]
    hit = profile._hit_target_with_tracking(
        target,
        unit_a.models[0],
        {},
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("lethal hits" in str(effect).lower() for effect in list(hit.get("special_effects", []) or []))


def test_predatory_imperative_rejects_first_round_hyper_adaptation_choice():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    mgr = tyr_army.tyranids_detachments
    assert mgr.select_hyper_adaptation("HYPER_AGGRESSION", battle_round=1)

    unit = _make_unit(
        "Warriors",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="3",
    )
    tyr_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)

    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    blocked = tyr_player.stratagems.use(
        "PREDATORY IMPERATIVE",
        unit=unit,
        adaptation="HYPER_AGGRESSION",
        phase_name="Command phase",
    )
    assert not blocked
    assert int(tyr_player.command_points or 0) == 10


def test_endless_swarm_returns_destroyed_models_for_selected_units():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    unit_a = _make_unit(
        "Termagants Alpha",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="1",
    )
    unit_b = _make_unit(
        "Termagants Beta",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="1",
    )
    tyr_army.add_unit(unit_a)
    tyr_army.add_unit(unit_b)
    _deploy_unit(game, unit_a, 10.0, 10.0)
    _deploy_unit(game, unit_b, 25.0, 25.0)

    # Seed one destroyed model marker per unit.
    unit_a.models_lost.append(unit_a.models[0])
    unit_b.models_lost.append(unit_b.models[0])

    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    with patch("warhammer40k_ai.rules.stratagems_tyranids.dice_module.get_roll", return_value=1):
        ok = tyr_player.stratagems.use(
            "ENDLESS SWARM",
            units=[unit_a, unit_b],
            phase_name="Command phase",
        )
    assert ok
    assert int(tyr_player.command_points or 0) == 9
    assert len(unit_a.models_lost) == 0
    assert len(unit_b.models_lost) == 0


def test_endless_swarm_tool_action_context_only_exposes_damaged_endless_multitude_units():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    damaged_endless = _make_unit(
        "Termagants Alpha",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="1",
    )
    damaged_non_endless = _make_unit(
        "Hive Guard",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="2",
    )
    full_endless = _make_unit(
        "Hormagaunts",
        keywords=["INFANTRY", "ENDLESS MULTITUDE", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        wounds="1",
    )
    tyr_army.add_unit(damaged_endless)
    tyr_army.add_unit(damaged_non_endless)
    tyr_army.add_unit(full_endless)
    _deploy_unit(game, damaged_endless, 10.0, 10.0)
    _deploy_unit(game, damaged_non_endless, 20.0, 10.0)
    _deploy_unit(game, full_endless, 30.0, 10.0)
    damaged_endless.models_lost.append(damaged_endless.models[0])
    damaged_non_endless.models_lost.append(damaged_non_endless.models[0])

    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    assert tyr_player.stratagems.can_use(
        "ENDLESS SWARM",
        unit=damaged_endless,
        phase_name="Command phase",
    )
    assert not tyr_player.stratagems.can_use(
        "ENDLESS SWARM",
        unit=damaged_non_endless,
        phase_name="Command phase",
    )
    assert not tyr_player.stratagems.can_use(
        "ENDLESS SWARM",
        unit=full_endless,
        phase_name="Command phase",
    )

    items = tyr_player.stratagems.get_phase_stratagem_items()
    endless_item = next(item for item in items if str(item.get("name", "")).upper() == "ENDLESS SWARM")
    assert [unit.name for unit in endless_item["context"]["candidates"]] == ["Termagants Alpha"]

    specs = tyr_player.stratagems._build_tool_action_specs_for_item(endless_item)
    specs = tyr_player.stratagems._filter_legal_tool_action_specs(specs)
    assert specs
    labels = [str(spec.get("label", "") or "") for spec in specs]
    assert any("Termagants Alpha" in label for label in labels)
    assert not any("Hive Guard" in label or "Hormagaunts" in label for label in labels)
    payload_texts = [str((spec.get("payload", {}) or {}).get("resolved_kwargs", {}) or {}) for spec in specs]
    assert all(str(damaged_endless.id) in payload_text for payload_text in payload_texts)
    assert not any(str(damaged_non_endless.id) in payload_text for payload_text in payload_texts)
    assert not any(str(full_endless.id) in payload_text for payload_text in payload_texts)


def test_invasion_fleet_stratagem_descriptors_registered():
    rapid = get_stratagem_tool_descriptor(stratagem_id="000008349002")
    assert rapid is not None
    assert rapid.name == "Rapid Regeneration"
    assert rapid.effect == "conditional_feel_no_pain_by_synapse"
    assert int(rapid.effect_params.get("base_fnp", 0) or 0) == 6
    assert int(rapid.effect_params.get("boosted_fnp", 0) or 0) == 5

    adrenal = get_stratagem_tool_descriptor(stratagem_id="000008349003")
    assert adrenal is not None
    assert adrenal.name == "Adrenal Surge"
    assert adrenal.effect == "melee_critical_hits_on_5plus"

    death = get_stratagem_tool_descriptor(stratagem_id="000008349004")
    assert death is not None
    assert death.name == "Death Frenzy"
    assert death.effect == "fight_on_death_after_attacks"
    assert int(death.effect_params.get("roll_threshold", 0) or 0) == 4

    overrun = get_stratagem_tool_descriptor(stratagem_id="000008349005")
    assert overrun is not None
    assert overrun.name == "Overrun"
    assert overrun.effect == "consolidate_plus_3_with_synapse_normal_move_option"
    assert int(overrun.effect_params.get("consolidate_distance", 0) or 0) == 6

    predatory = get_stratagem_tool_descriptor(stratagem_id="000008349006")
    assert predatory is not None
    assert predatory.name == "Predatory Imperative"
    assert predatory.effect == "grant_additional_hyper_adaptation"
    assert bool(predatory.effect_params.get("cannot_select_first_round_hyper_adaptation", False)) is True

    endless = get_stratagem_tool_descriptor(stratagem_id="000008349007")
    assert endless is not None
    assert endless.name == "Endless Swarm"
    assert endless.effect == "return_destroyed_models"
    assert str(endless.effect_params.get("return_roll", "")).upper() == "D3+3"
