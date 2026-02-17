from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
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
        toughness: str = "4",
        wounds: str = "3",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Thousand Sons"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
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


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    toughness: str = "4",
    wounds: str = "3",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ts_army = Army("Thousand Sons", "Rubricae Phalanx")
    ts_army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ts_player = Player("TS", control=PlayerControl.LOCAL, army=ts_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ts_player)
    game.add_player(enemy_player)

    ts_player.command_points = 10
    enemy_player.command_points = 10
    ts_army.configure_rule_managers(force=True)
    ts_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, ts_player, enemy_player, ts_army, enemy_army


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


def test_ardent_automata_queues_after_fall_back_and_grants_shoot_and_charge():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    rubricae = _make_unit(
        "Rubric Marines",
        keywords=["INFANTRY", "RUBRICAE"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(rubricae)
    _deploy_unit(game, rubricae, 10.0, 10.0)

    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)
    rubricae.round_state.fell_back_this_round = True
    game.event_system.publish("unit_move_ended", unit=rubricae, action="fall_back")

    pending = [
        r for r in list(ts_player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == "ARDENT AUTOMATA"
    ]
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "ARDENT AUTOMATA",
        unit=rubricae,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok
    assert int(ts_player.command_points or 0) == 9
    assert bool(rubricae.special_rules.get("thousand_sons_ardent_automata_active")) is True
    assert rubricae.has_fell_back_and_shoot() is True
    assert rubricae.can_charge_after_fall_back() is True


def test_ardent_automata_rejects_target_that_did_not_fall_back():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    rubricae = _make_unit(
        "Rubric Marines",
        keywords=["INFANTRY", "RUBRICAE"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(rubricae)
    _deploy_unit(game, rubricae, 10.0, 10.0)

    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)
    rubricae.round_state.fell_back_this_round = False
    blocked = ts_player.stratagems.use(
        "ARDENT AUTOMATA",
        unit=rubricae,
        phase_name="Movement phase",
    )
    assert not blocked
    assert int(ts_player.command_points or 0) == 10


def test_inexorable_advance_grants_ranged_assault_for_shooting_after_advance():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    rubricae = _make_unit(
        "Rubric Marines",
        keywords=["INFANTRY", "RUBRICAE"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(rubricae)
    _deploy_unit(game, rubricae, 10.0, 10.0)

    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)
    ok = ts_player.stratagems.use(
        "INEXORABLE ADVANCE",
        unit=rubricae,
        phase_name="Movement phase",
    )
    assert ok
    assert int(ts_player.command_points or 0) == 9

    _set_phase(game, ts_player, "SHOOTING_PHASE", 0)
    profile = Wargear(
        {
            "name": "Inferno Boltgun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "1",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]
    assert rubricae.can_shoot_after_advance(profile) is True


def test_infernal_fusillade_sets_inferno_strength_and_psychic_attack_type():
    game, ts_player, _enemy_player, ts_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Rubric Marines",
        keywords=["INFANTRY", "RUBRICAE", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    target = _make_unit(
        "Enemy Target",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    ts_army.add_unit(shooter)
    enemy_army.add_unit(target)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, target, 16.0, 10.0)

    _set_phase(game, ts_player, "SHOOTING_PHASE", 0)
    ok = ts_player.stratagems.use(
        "INFERNAL FUSILLADE",
        unit=shooter,
        phase_name="Shooting phase",
    )
    assert ok
    assert int(ts_player.command_points or 0) == 8
    assert bool(shooter.special_rules.get("thousand_sons_infernal_fusillade_active")) is True

    inferno_profile = Wargear(
        {
            "name": "Inferno Boltgun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "1",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]
    inferno_wound = inferno_profile._wound_target_with_tracking(
        target,
        shooter.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(inferno_wound.get("wound")) is True
    assert any("INFERNAL FUSILLADE" in str(m) for m in list(inferno_wound.get("modifiers", []) or []))
    assert inferno_profile._check_invulnerable_save_condition(
        "against psychic attacks",
        {"attacker_model": shooter.models[0]},
    )

    non_inferno_profile = Wargear(
        {
            "name": "Boltgun",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    ).profiles["default"]
    non_inferno_wound = non_inferno_profile._wound_target_with_tracking(
        target,
        shooter.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(non_inferno_wound.get("wound")) is False


def test_implacable_guardians_queues_and_excludes_psyker_models_from_damage_reduction():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    defender = _make_unit(
        "Rubric Marines",
        keywords=["INFANTRY", "RUBRICAE", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ts_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 16.0, 10.0)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])
    pending = [
        r for r in list(ts_player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == "IMPLACABLE GUARDIANS"
    ]
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "IMPLACABLE GUARDIANS",
        unit=defender,
        attacking_unit=attacker,
        dequeue=True,
    )
    assert ok
    assert int(ts_player.command_points or 0) == 8

    profile = Wargear(
        {
            "name": "Enemy Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "2",
            "description": "",
        }
    ).profiles["default"]
    target_model = defender.models[0]
    target_model.wounds = 4

    target_model.keywords = ["RUBRICAE"]
    reduced = profile._damage_target_with_tracking(
        target_model,
        attacker.models[0],
        {},
        allow_rerolls=False,
    )
    assert int(reduced.get("damage_applied", 0) or 0) == 1

    target_model.wounds = 4
    target_model.keywords = ["RUBRICAE", "PSYKER"]
    not_reduced = profile._damage_target_with_tracking(
        target_model,
        attacker.models[0],
        {},
        allow_rerolls=False,
    )
    assert int(not_reduced.get("damage_applied", 0) or 0) == 2


def test_revenge_of_the_rubricae_queues_after_attacker_resolves_and_sets_reactive_shooting():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    victim = _make_unit(
        "Scarab Occult Terminators",
        keywords=["INFANTRY", "RUBRICAE", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    nearby_rubricae = _make_unit(
        "Rubric Marines",
        keywords=["INFANTRY", "RUBRICAE"],
        faction_keywords=["THOUSAND SONS"],
    )
    far_rubricae = _make_unit(
        "Rubric Marines Far",
        keywords=["INFANTRY", "RUBRICAE"],
        faction_keywords=["THOUSAND SONS"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ts_army.add_unit(victim)
    ts_army.add_unit(nearby_rubricae)
    ts_army.add_unit(far_rubricae)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, victim, 10.0, 10.0)
    _deploy_unit(game, nearby_rubricae, 12.0, 10.0)
    _deploy_unit(game, far_rubricae, 28.0, 28.0)
    _deploy_unit(game, attacker, 18.0, 10.0)

    victim.models[0].keywords = ["RUBRICAE", "PSYKER"]
    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "model_destroyed",
        attacker_unit=attacker,
        target_model=victim.models[0],
        target_unit=victim,
    )
    before_resolve = [
        r for r in list(ts_player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == "REVENGE OF THE RUBRICAE"
    ]
    assert not before_resolve

    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={victim: 1})
    pending = [
        r for r in list(ts_player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == "REVENGE OF THE RUBRICAE"
    ]
    assert len(pending) == 1
    candidates = list(pending[0].get("candidates") or [])
    assert nearby_rubricae in candidates
    assert far_rubricae not in candidates

    with patch.object(game, "_queue_setup_reactive_shooting_decision", return_value={"queued": True}) as queue_mock:
        ok = ts_player.stratagems.use(
            "REVENGE OF THE RUBRICAE",
            unit=nearby_rubricae,
            enemy_unit=attacker,
            candidates=[nearby_rubricae],
            phase_name="Shooting phase",
            dequeue=True,
        )
    assert ok
    assert int(ts_player.command_points or 0) == 9
    assert queue_mock.call_count == 1
    _, queued_kwargs = queue_mock.call_args
    assert queued_kwargs.get("unit") is nearby_rubricae
    assert queued_kwargs.get("target_unit") is attacker


def test_rubricae_phalanx_stratagem_descriptors_registered():
    ardent = get_stratagem_tool_descriptor(stratagem_id="000010206002")
    assert ardent is not None
    assert ardent.name == "Ardent Automata"
    assert ardent.effect == "eligible_to_shoot_and_charge_after_fall_back"

    inexorable = get_stratagem_tool_descriptor(stratagem_id="000010206003")
    assert inexorable is not None
    assert inexorable.name == "Inexorable Advance"
    assert inexorable.effect == "ignore_move_and_advance_modifiers_and_gain_ranged_assault"
    assert bool(inexorable.effect_params.get("grant_ranged_assault", False)) is True

    infernal = get_stratagem_tool_descriptor(stratagem_id="000010206004")
    assert infernal is not None
    assert infernal.name == "Infernal Fusillade"
    assert infernal.effect == "inferno_weapons_gain_psychic_and_set_strength"
    assert int(infernal.effect_params.get("set_strength", 0) or 0) == 5

    revenge = get_stratagem_tool_descriptor(stratagem_id="000010206005")
    assert revenge is not None
    assert revenge.name == "Revenge of the Rubricae"
    assert revenge.effect == "reactive_shooting_at_attacker"
    assert bool(revenge.effect_params.get("force_target_attacker", False)) is True

    guardians = get_stratagem_tool_descriptor(stratagem_id="000010206006")
    assert guardians is not None
    assert guardians.name == "Implacable Guardians"
    assert guardians.effect == "reduce_damage_allocated_except_psyker_models"
    assert str(guardians.effect_params.get("exclude_allocated_model_keyword", "") or "") == "PSYKER"
