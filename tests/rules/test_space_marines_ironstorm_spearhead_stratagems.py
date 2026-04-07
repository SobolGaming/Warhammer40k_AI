from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.dice import DiceCollection
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE
from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        movement: int = 6,
        toughness: int = 4,
        wounds: int = 4,
        leadership: int = 7,
        objective_control: int = 2,
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
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": "60mm",
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
    movement: int = 6,
    toughness: int = 4,
    wounds: int = 4,
    leadership: int = 7,
    objective_control: int = 2,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Ironstorm Spearhead")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
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
        model.set_location(float(x) + (float(index) * 2.0), float(y), 0.0, 0.0)
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


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _ranged_wargear(name: str = "Twin Boltgun") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _make_profile(*, is_melee: bool, strength: str = "4", skill: str = "3+", damage: str = "1") -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def test_ironstorm_spearhead_stratagem_descriptors_registered():
    expected = {
        "000008479006": ("Ancient Fury", "walker_characteristics_and_hit_bonus_until_next_command_phase"),
        "000008479004": ("Mercy Is Weakness", "conditional_sustained_hits_and_vehicle_critical_hits_vs_damaged_target"),
        "000008479007": ("Power of the Machine Spirit", "reactive_shooting_restricted_to_attacker"),
        "000008479002": ("Unbowed Conviction", "ignore_characteristic_and_roll_modifiers_except_saves"),
        "000008479005": ("Vengeful Animus", "auto_trigger_deadly_demise"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_ancient_fury_queues_applies_model_bonuses_and_expires_next_command_phase():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    dreadnought = _make_unit(
        "Redemptor Dreadnought",
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ADEPTUS ASTARTES"],
        movement=8,
        toughness=10,
        wounds=12,
        leadership=7,
        objective_control=3,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(dreadnought)
    enemy_army.add_unit(enemy)
    dreadnought.models[0].wargear = [_ranged_wargear()]
    _deploy_unit(game, dreadnought, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "ANCIENT FURY")
    assert pending is not None
    assert list(pending.get("model_candidates") or []) == [dreadnought.models[0]]

    ok = sm_player.stratagems.use(
        "ANCIENT FURY",
        unit=dreadnought,
        model=dreadnought.models[0],
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    model = dreadnought.models[0]
    assert int(dreadnought.get_effective_model_characteristic(model, "movement", game_map=game.map) or 0) == 9
    assert int(dreadnought.get_effective_model_characteristic(model, "toughness", game_map=game.map) or 0) == 11
    assert int(dreadnought.get_effective_model_characteristic(model, "leadership", game_map=game.map) or 0) == 6
    assert int(dreadnought.get_effective_model_characteristic(model, "objective_control", game_map=game.map) or 0) == 4

    hit_result = _make_profile(is_melee=False)._hit_target_with_tracking(
        enemy,
        model,
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result.get("hit") is True

    game.turn = 2
    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert int(dreadnought.get_effective_model_characteristic(model, "movement", game_map=game.map) or 0) == 9

    game.turn = 3
    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert int(dreadnought.get_effective_model_characteristic(model, "movement", game_map=game.map) or 0) == 8
    assert int(dreadnought.get_effective_model_characteristic(model, "toughness", game_map=game.map) or 0) == 10
    assert int(dreadnought.get_effective_model_characteristic(model, "leadership", game_map=game.map) or 0) == 7
    assert int(dreadnought.get_effective_model_characteristic(model, "objective_control", game_map=game.map) or 0) == 3


def test_mercy_is_weakness_queues_in_both_phases_and_applies_conditional_vehicle_hit_bonuses():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    gladiator = _make_unit(
        "Gladiator Lancer",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=12,
    )
    enemy_damaged = _make_unit(
        "Damaged Enemy",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        wounds=10,
    )
    enemy_fresh = _make_unit(
        "Fresh Enemy",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        wounds=10,
    )
    sm_army.add_unit(gladiator)
    enemy_army.add_unit(enemy_damaged)
    enemy_army.add_unit(enemy_fresh)
    gladiator.models[0].wargear = [_ranged_wargear()]
    _deploy_unit(game, gladiator, 10.0, 10.0)
    _deploy_unit(game, enemy_damaged, 16.0, 10.0)
    _deploy_unit(game, enemy_fresh, 20.0, 10.0)
    enemy_damaged.models[0].wounds = 9
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "MERCY IS WEAKNESS")
    assert pending is not None

    ok = sm_player.stratagems.use("MERCY IS WEAKNESS", unit=gladiator, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 8

    attack_instance = {}
    hit_result = _make_profile(is_melee=False)._hit_target_with_tracking(
        enemy_damaged,
        gladiator.models[0],
        attack_instance,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result.get("hit") is True
    assert int(hit_result.get("crit_threshold", 0) or 0) == 5
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1

    fresh_attack_instance = {}
    fresh_hit_result = _make_profile(is_melee=False)._hit_target_with_tracking(
        enemy_fresh,
        gladiator.models[0],
        fresh_attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert fresh_hit_result.get("hit") is True
    assert int(fresh_hit_result.get("crit_threshold", 0) or 0) == 6
    assert int(fresh_attack_instance.get("sustained_hit", 0) or 0) == 0

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "MERCY IS WEAKNESS")
    assert pending is not None


def test_unbowed_conviction_queues_in_any_command_phase_and_ignores_negative_modifiers_until_turn_end():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    infantry = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=1,
        movement=6,
        toughness=4,
        wounds=5,
        leadership=7,
        objective_control=2,
    )
    target = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=4,
    )
    sm_army.add_unit(infantry)
    enemy_army.add_unit(target)
    _deploy_unit(game, infantry, 10.0, 10.0)
    _deploy_unit(game, target, 16.0, 10.0)
    infantry.models[0].wounds = 4
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    pending = _pending_by_name(sm_player.stratagems, "UNBOWED CONVICTION")
    assert pending is not None

    ok = sm_player.stratagems.use("UNBOWED CONVICTION", unit=infantry, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert infantry.get_move_advance_charge_modifier_ignore_rule() == {
        "source": "UNBOWED CONVICTION",
        "default_choice": "ignore_negative",
    }

    infantry.add_characteristic_modifier("movement", Modifier(ModifierOp.SUB, 2, source="test:move"))
    infantry.add_characteristic_modifier("toughness", Modifier(ModifierOp.SUB, 1, source="test:toughness"))
    infantry.add_characteristic_modifier("leadership", Modifier(ModifierOp.ADD, 1, source="test:leadership"))
    infantry.add_characteristic_modifier("objective_control", Modifier(ModifierOp.SUB, 1, source="test:oc"))

    model = infantry.models[0]
    assert int(infantry.get_effective_model_characteristic(model, "movement", game_map=game.map) or 0) == 6
    assert int(infantry.get_effective_model_characteristic(model, "toughness", game_map=game.map) or 0) == 4
    assert int(infantry.get_effective_model_characteristic(model, "leadership", game_map=game.map) or 0) == 7
    assert int(infantry.get_effective_model_characteristic(model, "objective_control", game_map=game.map) or 0) == 2

    attack_instance = {"hit_roll_modifiers": [(-1, "Test penalty")]}
    hit_result = _make_profile(is_melee=False)._hit_target_with_tracking(
        target,
        model,
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result.get("hit") is True
    assert attack_instance.get("hit_modifier_choice") == CHOICE_IGNORE_NEGATIVE

    attack_instance = {"wound_roll_modifiers": [(-1, "Test penalty")]}
    wound_result = _make_profile(is_melee=False, strength="4")._wound_target_with_tracking(
        target,
        model,
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result.get("wound") is True

    game.turn = 2
    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert infantry.get_move_advance_charge_modifier_ignore_rule() is None
    assert int(infantry.get_effective_model_characteristic(model, "movement", game_map=game.map) or 0) == 4


def test_power_of_the_machine_spirit_queues_after_vehicle_crosses_below_half_strength_and_restricts_target():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    predator = _make_unit(
        "Predator Destructor",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=8,
    )
    enemy = _make_unit(
        "Enemy Tank Hunters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(predator)
    enemy_army.add_unit(enemy)
    predator.models[0].wargear = [_ranged_wargear()]
    _deploy_unit(game, predator, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()
    game._setup_reactive_can_shoot_target = lambda _unit, _target: True

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[predator])
    predator.models[0].wounds = 3
    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy)

    pending = _pending_by_name(sm_player.stratagems, "POWER OF THE MACHINE SPIRIT")
    assert pending is not None
    assert list(pending.get("candidates") or []) == [predator]

    ok = sm_player.stratagems.use(
        "POWER OF THE MACHINE SPIRIT",
        unit=predator,
        enemy_unit=enemy,
        candidates=list(pending.get("candidates") or []),
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    request = _first_request(game, DECISION_DECLARE_SHOTS)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert bool(context.get("out_of_phase", False)) is True
    assert bool(context.get("power_of_the_machine_spirit_flow", False)) is True
    assert str(context.get("force_target_unit_id", "") or "") == str(get_entity_id(enemy) or "")


def test_vengeful_animus_queues_on_destroyed_vehicle_model_and_auto_triggers_deadly_demise():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    vehicle = _make_unit(
        "Brutalis Dreadnought",
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=12,
    )
    sm_army.add_unit(vehicle)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    game.rebuild_entity_registry()

    vehicle.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))
    model = vehicle.models[0]
    model.wounds = 0

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    game.event_system.publish("model_destroyed_before_removal", unit=vehicle, model=model)
    pending = _pending_by_name(sm_player.stratagems, "VENGEFUL ANIMUS")
    assert pending is not None

    with patch.object(vehicle, "_apply_deadly_demise_explosion") as explosion_mock:
        ok = sm_player.stratagems.use(
            "VENGEFUL ANIMUS",
            destroyed_unit=vehicle,
            destroyed_model=model,
            phase_name="Shooting phase",
            dequeue=True,
        )
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert explosion_mock.call_count == 1
