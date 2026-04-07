from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        model_name: str = "Test Model",
        move: int = 6,
        toughness: int = 4,
        wounds: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": str(model_name),
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "6",
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
    model_count: int = 1,
    model_name: str = "Test Model",
    move: int = 6,
    toughness: int = 4,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            model_name=model_name,
            move=move,
            toughness=toughness,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    sm_army = Army.with_detachment("Space Marines", "Saga of the Great Wolf")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("SM", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)

    sm_player.command_points = 10
    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * 0.1), float(y), 0.0, 0.0)
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


def _first_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


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


def _make_ranged_profile():
    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_saga_of_the_great_wolf_stratagem_descriptors_exist():
    expected = {
        "000010661003": ("Grimnar's Command", "unit_specific_master_of_wolves_hunting_pack_override"),
        "000010661004": ("Fenrisian Ferocity", "move_through_models_and_terrain_with_titanic_block"),
        "000010661005": ("Unrelenting Hunters", "charge_after_fall_back_and_space_wolves_charge_after_advance"),
        "000010661006": ("Eye of the Pack", "grant_plus_one_to_wound_on_ranged_weapons"),
        "000010661007": ("Battle Instincts", "reactive_normal_move"),
    }
    for stratagem_id, (name, effect) in expected.items():
        descriptor = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert descriptor is not None
        assert descriptor.name == name
        assert descriptor.effect == effect


def test_grimnars_command_queues_choice_and_overrides_active_pack_for_one_unit():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    manager = sm_army.space_marines_detachments
    target = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    other = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit("Enemy Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(target)
    sm_army.add_unit(other)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, other, 14.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "GRIMNAR'S COMMAND")
    assert pending is not None
    options = list(pending.get("choice_options") or [])
    assert {str(option.get("choice_key", "") or "") for option in options} == {
        "ENCIRCLING_JAWS",
        "HUNTERS_EYE",
        "FEROCIOUS_STRIKE",
    }

    assert manager.select_master_of_wolves_pack("ENCIRCLING_JAWS", battle_round=1, game=game)
    assert target.can_reroll_advance_roll() is True
    assert other.can_reroll_advance_roll() is True

    ok = sm_player.stratagems.use(
        "GRIMNAR'S COMMAND",
        unit=target,
        choice_key="HUNTERS_EYE",
        phase_name="Command phase",
    )
    assert ok
    assert target.can_reroll_advance_roll() is False
    assert other.can_reroll_advance_roll() is True

    profile = _make_ranged_profile()
    hit = profile._hit_target_with_tracking(
        enemy,
        target.models[0],
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit.get("hit", False)) is True
    assert any("Hunter's Eye" in str(mod) for mod in list(hit.get("modifiers", []) or []))

    game.turn = 2
    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert target.can_reroll_advance_roll() is False


def test_unrelenting_hunters_grants_fall_back_charge_and_space_wolves_advance_charge():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    regular = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(regular)
    _deploy_unit(game, regular, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    regular.round_state.advanced_this_round = True
    assert regular.can_charge_after_advance() is False
    regular.round_state.advanced_this_round = False
    assert sm_player.stratagems.use("UNRELENTING HUNTERS", unit=regular, phase_name="Movement phase")
    assert int(sm_player.command_points or 0) == 9

    regular.round_state.fell_back_this_round = True
    regular.round_state.advanced_this_round = True
    assert regular.can_charge_after_fall_back() is True
    assert regular.can_charge_after_advance() is True

    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    assert regular.can_charge_after_fall_back() is False

    game2, sm_player2, _enemy_player2, sm_army2, _enemy_army2 = _build_game()
    wolves = _make_unit(
        "Blood Claws",
        keywords=["INFANTRY", "SPACE WOLVES", "BLOOD CLAWS"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    sm_army2.add_unit(wolves)
    _deploy_unit(game2, wolves, 14.0, 10.0)
    game2.rebuild_entity_registry()

    _set_phase(game2, sm_player2, "MOVEMENT_PHASE", 0)
    wolves.round_state.advanced_this_round = True
    assert wolves.can_charge_after_advance() is False
    wolves.round_state.advanced_this_round = False
    assert sm_player2.stratagems.use("UNRELENTING HUNTERS", unit=wolves, phase_name="Movement phase")
    wolves.round_state.fell_back_this_round = True
    wolves.round_state.advanced_this_round = True
    assert wolves.can_charge_after_fall_back() is True
    assert wolves.can_charge_after_advance() is True


def test_eye_of_the_pack_grants_ranged_wound_bonus_until_phase_end():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    unit.models[0].wargear = [_ranged_wargear()]
    sm_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert sm_player.stratagems.use("EYE OF THE PACK", unit=unit, phase_name="Shooting phase")

    bonus, reasons = unit.models[0].get_temporary_weapon_wound_bonus("Bolt Rifle")
    assert int(bonus or 0) == 1
    assert any("eye of the pack" in str(reason).lower() for reason in list(reasons or []))


def test_fenrisian_ferocity_movement_phase_applies_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    cavalry = _make_unit(
        "Thunderwolf Cavalry",
        keywords=["MOUNTED", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    sm_army.add_unit(cavalry)
    _deploy_unit(game, cavalry, 10.0, 10.0)

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    ok = sm_player.stratagems.use("FENRISIAN FEROCITY", unit=cavalry, phase_name="Movement phase")
    assert ok

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=cavalry)
    assert bool(move_rules.get("can_move_through_enemy_models")) is True
    assert bool(move_rules.get("can_move_through_terrain")) is True
    assert bool(move_rules.get("block_titanic_models")) is True
    assert bool(move_rules.get("cannot_move_within_engagement_range")) is False
    assert bool(move_rules.get("cannot_end_in_engagement_range")) is True

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    sr_after = dict(getattr(cavalry, "special_rules", {}) or {})
    assert bool(sr_after.get("space_marines_fenrisian_ferocity_active", False)) is False
    assert "bearer_unit_phase_move_types" not in sr_after


def test_fenrisian_ferocity_charge_phase_applies_charge_passthrough():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    walker = _make_unit(
        "Wulfen Dreadnought",
        keywords=["VEHICLE", "WALKER", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    sm_army.add_unit(walker)
    _deploy_unit(game, walker, 10.0, 10.0)

    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    ok = sm_player.stratagems.use("FENRISIAN FEROCITY", unit=walker, phase_name="Charge phase")
    assert ok

    charge_rules = get_validation_rules(MovementType.CHARGE, moving_unit=walker)
    assert bool(charge_rules.get("can_move_through_enemy_models")) is True
    assert bool(charge_rules.get("can_move_through_terrain")) is True
    assert bool(charge_rules.get("block_titanic_models")) is True
    assert bool(charge_rules.get("cannot_end_in_engagement_range", False)) is False


def test_battle_instincts_queues_after_enemy_shoots_even_when_no_hits():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    target = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY", "SPACE WOLVES"],
        faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
    )
    attacker = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[target])

    with patch("warhammer40k_ai.rules.stratagems_space_marines.dice_module.get_roll", return_value=5):
        game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={})
        pending = _pending_by_name(sm_player.stratagems, "BATTLE INSTINCTS")
        assert pending is not None
        assert sm_player.stratagems.use("BATTLE INSTINCTS", unit=target, phase_name="Shooting phase")

    move_request = _first_request(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    ctx = dict(getattr(move_request, "context", {}) or {})
    assert str(ctx.get("reactive_move_kind", "") or "") == "battle_instincts"
    assert int(ctx.get("max_distance", 0) or 0) == 5
