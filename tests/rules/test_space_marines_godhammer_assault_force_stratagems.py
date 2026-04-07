from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.movement import _validate_disembark
from warhammer40k_ai.engine.decision_kinds import DECISION_DISEMBARK, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.dice_rolls import DiceRollState
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.roll_handlers import handle_charge_roll
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


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
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "10" if "VEHICLE" in self.keywords else "4",
                "Sv": "2" if "VEHICLE" in self.keywords else "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "5" if "VEHICLE" in self.keywords else "1",
                "base_size": "80mm" if "VEHICLE" in self.keywords else "32mm",
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

    sm_army = Army.with_detachment("Space Marines", "Godhammer Assault Force")
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
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _embark_unit(transport: Unit, passenger: Unit) -> None:
    passenger.embarked_in = transport
    passenger.deployed = False
    passenger.reserve_status = "embarked"
    transport.transport_passengers = [passenger]


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


def _queued_disembark_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if getattr(request, "decision_type", None) == DECISION_DISEMBARK:
            return request
    return None


def _queued_move_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if getattr(request, "decision_type", None) == DECISION_MOVE_UNIT:
            return request
    return None


def test_godhammer_assault_force_stratagem_descriptors_registered():
    expected = {
        "000010401002": ("A Ceaseless Cause", "end_of_fight_normal_move_up_to_six_no_embark_if_disembarked"),
        "000010401003": ("Uncompromising Egress", "reactive_disembark_within_six_and_allow_engagement"),
        "000010401004": ("Gauntlet of the God-Emperor", "normal_and_advance_move_through_terrain"),
        "000010401005": ("Focused Hatred", "charge_move_through_models_against_declared_targets_only"),
        "000010401006": ("Condemnatory Info-screed", "disembarked_wound_reroll_ones_or_full_if_land_raider"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_gauntlet_of_the_god_emperor_grants_move_through_terrain_until_phase_end():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    land_raider = _make_unit(
        "Land Raider Redeemer",
        keywords=["VEHICLE", "TRANSPORT", "LAND RAIDER"],
        wounds=16,
    )
    sm_army.add_unit(land_raider)
    _deploy_unit(game, land_raider, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "GAUNTLET OF THE GOD-EMPEROR")
    assert pending is not None

    ok = sm_player.stratagems.use("GAUNTLET OF THE GOD-EMPEROR", unit=land_raider, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    special_rules = getattr(land_raider, "special_rules", {}) or {}
    assert set(special_rules.get("bearer_unit_phase_move_terrain_only_types", []) or []) == {"move", "advance"}
    assert set(
        special_rules.get("space_marines_gauntlet_of_the_god_emperor_added_phase_move_terrain_only_types", []) or []
    ) == {"move", "advance"}

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    special_rules = getattr(land_raider, "special_rules", {}) or {}
    assert "space_marines_gauntlet_of_the_god_emperor_active" not in special_rules
    assert "bearer_unit_phase_move_terrain_only_types" not in special_rules


def test_uncompromising_egress_allows_engagement_range_disembark_validation():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    land_raider = _make_unit(
        "Land Raider Crusader",
        keywords=["VEHICLE", "TRANSPORT", "LAND RAIDER"],
        wounds=16,
    )
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        model_count=1,
    )
    sm_army.add_unit(land_raider)
    sm_army.add_unit(intercessors)
    _deploy_unit(game, land_raider, 12.0, 12.0)
    _embark_unit(land_raider, intercessors)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "UNCOMPROMISING EGRESS")
    assert pending is not None

    ok = sm_player.stratagems.use("UNCOMPROMISING EGRESS", unit=land_raider, dequeue=True)
    assert ok
    request = _queued_disembark_request(game)
    assert request is not None
    assert bool((request.context or {}).get("disembark_require_not_in_engagement")) is False
    assert float((request.context or {}).get("disembark_max_distance", 0.0) or 0.0) == 6.0

    chosen = next(
        option
        for option in list(getattr(request, "options", []) or [])
        if str((getattr(option, "payload", {}) or {}).get("unit_id", "") or "") == str(get_entity_id(intercessors))
    )
    captured = {}

    def _validate_placement(model, x, y, z, *, transport_unit, game_map, max_distance, require_not_in_engagement, min_enemy_horizontal_distance):
        captured["require_not_in_engagement"] = bool(require_not_in_engagement)
        captured["transport_id"] = str(get_entity_id(transport_unit) or "")
        captured["max_distance"] = float(max_distance)
        return {"valid": True}

    intercessors.validate_disembark_placement = _validate_placement
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=sm_player.id,
        option_id=chosen.option_id,
        payload={
            "model_positions": [
                {
                    "model_id": str(get_entity_id(intercessors.models[0]) or ""),
                    "position": [13.0, 12.0, 0.0],
                }
            ]
        },
    )
    assert _validate_disembark(game, request, result) == ()
    assert captured["require_not_in_engagement"] is False
    assert captured["transport_id"] == str(get_entity_id(land_raider))
    assert captured["max_distance"] == 6.0


def test_condemnatory_info_screed_applies_wound_reroll_ones_after_non_land_raider_disembark():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    rhino = _make_unit(
        "Rhino",
        keywords=["VEHICLE", "TRANSPORT"],
        wounds=10,
    )
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
    )
    sm_army.add_unit(rhino)
    sm_army.add_unit(intercessors)
    _deploy_unit(game, rhino, 10.0, 10.0)
    _deploy_unit(game, intercessors, 13.0, 10.0)
    intercessors.round_state.disembarked_this_round = True
    intercessors.round_state.disembarked_from_transport_id = str(get_entity_id(rhino) or "")
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    ok = sm_player.stratagems.use("CONDEMNATORY INFO-SCREED", unit=intercessors)
    assert ok

    modifiers = intercessors.get_unit_wound_reroll_modifiers("melee")
    assert set(modifiers.get("reroll_wound_values", ()) or ()) == {1}
    assert not bool(modifiers.get("reroll_wound_full", False))


def test_condemnatory_info_screed_upgrades_to_full_wound_reroll_for_land_raider_disembark():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    land_raider = _make_unit(
        "Land Raider Redeemer",
        keywords=["VEHICLE", "TRANSPORT", "LAND RAIDER"],
        wounds=16,
    )
    bladeguard = _make_unit(
        "Bladeguard Veteran Squad",
        keywords=["INFANTRY"],
    )
    sm_army.add_unit(land_raider)
    sm_army.add_unit(bladeguard)
    _deploy_unit(game, land_raider, 8.0, 8.0)
    _deploy_unit(game, bladeguard, 11.0, 8.0)
    bladeguard.round_state.disembarked_this_round = True
    bladeguard.round_state.disembarked_from_transport_id = str(get_entity_id(land_raider) or "")
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    ok = sm_player.stratagems.use("CONDEMNATORY INFO-SCREED", unit=bladeguard)
    assert ok

    modifiers = bladeguard.get_unit_wound_reroll_modifiers("melee")
    assert bool(modifiers.get("reroll_wound_full", False))
    assert any("CONDEMNATORY INFO-SCREED" in str(reason).upper() for reason in list(modifiers.get("reroll_wound_full_reasons", ()) or ()))


def test_focused_hatred_reacts_to_charge_roll_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    land_raider = _make_unit(
        "Land Raider Crusader",
        keywords=["VEHICLE", "TRANSPORT", "LAND RAIDER"],
        wounds=16,
    )
    sword_brethren = _make_unit(
        "Primaris Sword Brethren",
        keywords=["INFANTRY"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(land_raider)
    sm_army.add_unit(sword_brethren)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, land_raider, 10.0, 10.0)
    _deploy_unit(game, sword_brethren, 15.0, 10.0)
    _deploy_unit(game, enemy, 19.0, 10.0)
    sword_brethren.round_state.disembarked_this_round = True
    sword_brethren.round_state.disembarked_from_transport_id = str(get_entity_id(land_raider) or "")
    sword_brethren.round_state.attempted_charge_this_round = True
    sword_brethren.round_state.charge_target_ids = {str(get_entity_id(enemy) or "")}
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    state = DiceRollState(
        roll_id=1,
        player_id=sm_player.id,
        spec={
            "unit_id": str(get_entity_id(sword_brethren) or ""),
            "target_unit_ids": [str(get_entity_id(enemy) or "")],
            "charge_spec": {"dice_count": 2, "keep_highest": 2},
        },
        dice=[{"value": 4}, {"value": 5}],
        total=9,
    )
    handle_charge_roll(game, state)
    pending = _pending_by_name(sm_player.stratagems, "FOCUSED HATRED")
    assert pending is not None

    ok = sm_player.stratagems.use("FOCUSED HATRED", unit=sword_brethren, dequeue=True)
    assert ok
    special_rules = getattr(sword_brethren, "special_rules", {}) or {}
    assert set(special_rules.get("bearer_unit_phase_move_models_only_types", []) or []) == {"charge"}
    assert bool(special_rules.get("space_marines_focused_hatred_active"))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    special_rules = getattr(sword_brethren, "special_rules", {}) or {}
    assert "space_marines_focused_hatred_active" not in special_rules
    assert "bearer_unit_phase_move_models_only_types" not in special_rules


def test_a_ceaseless_cause_queues_end_of_fight_normal_move():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    crusader_squad = _make_unit(
        "Crusader Squad",
        keywords=["INFANTRY"],
    )
    sm_army.add_unit(crusader_squad)
    _deploy_unit(game, crusader_squad, 10.0, 10.0)
    crusader_squad.round_state.eligible_to_fight_this_phase = True
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(sm_player.stratagems, "A CEASELESS CAUSE")
    assert pending is not None

    ok = sm_player.stratagems.use("A CEASELESS CAUSE", unit=crusader_squad, dequeue=True)
    assert ok
    request = _queued_move_request(game)
    assert request is not None
    assert str((request.context or {}).get("movement_type", "") or "").strip().lower() == "move"
    assert int((request.context or {}).get("max_distance", 0) or 0) == 6
