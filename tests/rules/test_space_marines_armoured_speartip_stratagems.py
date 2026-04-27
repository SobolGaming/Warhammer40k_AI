from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
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
        movement: int = 10,
        toughness: int = 9,
        wounds: int = 10,
        transport: str = "",
        abilities=None,
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
        for ability in list(abilities or []):
            entry = dict(ability)
            entry.setdefault("type", "Datasheet")
            entry.setdefault("parameter", "")
            self.datasheets_abilities.append(entry)
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    movement: int = 10,
    toughness: int = 9,
    wounds: int = 10,
    transport: str = "",
    abilities=None,
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
            transport=transport,
            abilities=abilities,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "Armoured Speartip")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

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
    assert game.map.place_unit(unit), f"failed to place {getattr(unit, 'name', 'Unit')}"


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


def _first_request(game: Game, decision_type: str, *, ability: str = ""):
    ability_key = str(ability or "").strip()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if ability_key:
            ctx = dict(getattr(request, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != ability_key:
                continue
        return request
    return None


def _find_option_by_payload(request, *, key: str, value: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get(key, "") or "") == str(value):
            return option
    return None


def _ranged_profile():
    wargear = Wargear(
        {
            "name": "Test Cannon",
            "type": "Ranged",
            "range": "36",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "0",
            "D": "D6",
            "description": "",
        }
    )
    return wargear.profiles["default"]


def test_armoured_speartip_stratagem_descriptors_registered():
    expected = {
        "000010780006": ("Advanced Deployment", "advanced_transport_allows_after_advance_disembark"),
        "000010780005": (
            "Ceramite Sledgehammer",
            "normal_and_advance_move_through_terrain_with_heavy_transport_enemy_model_traversal",
        ),
        "000010780007": ("Purgation Doctrine", "ranged_hit_bonus_and_heavy_transport_disembark_wound_bonus"),
        "000010780004": ("Rapid Embarkation", "end_of_fight_embark"),
        "000010780002": ("Machine Wrath", "pre_deadly_demise_reactive_normal_or_fall_back_move"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_id.effect == expected_effect
        assert by_name.effect == expected_effect


def test_advanced_deployment_allows_advance_disembark_and_assault_ramp_charge_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    assault_ramp = {
        "name": "Assault Ramp",
        "description": (
            "Each time a unit disembarks from this model after it has made a Normal move, "
            "that unit is still eligible to declare a charge this turn."
        ),
    }
    land_raider = _make_unit(
        "Land Raider",
        keywords=["VEHICLE", "TRANSPORT"],
        wounds=16,
        transport="Transport Capacity 12",
        abilities=[assault_ramp],
    )
    squad = _make_unit("Intercessor Squad", keywords=["INFANTRY"], wounds=2)
    sm_army.add_unit(land_raider)
    sm_army.add_unit(squad)
    _deploy_unit(game, land_raider, 10.0, 10.0)
    _deploy_unit(game, squad, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "ADVANCED DEPLOYMENT")
    assert pending is not None
    assert land_raider in list(pending.get("candidates") or [])

    assert sm_player.stratagems.use("ADVANCED DEPLOYMENT", unit=land_raider, phase_name="Movement phase", dequeue=True)
    land_raider.round_state.moved_this_round = True
    land_raider.round_state.advanced_this_round = True
    overrides = squad._disembark_override_rules(transport_unit=land_raider, game=game)
    assert overrides.get("allow_after_advance") is True
    assert overrides.get("allow_charge_after_advance_disembark") is True

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    rules = dict(getattr(land_raider, "special_rules", {}) or {})
    assert "space_marines_armoured_advanced_deployment_active" not in rules


def test_ceramite_sledgehammer_grants_heavy_transport_traversal_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    land_raider = _make_unit("Land Raider", keywords=["VEHICLE", "TRANSPORT"], wounds=16)
    sm_army.add_unit(land_raider)
    _deploy_unit(game, land_raider, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    assert sm_player.stratagems.use("CERAMITE SLEDGEHAMMER", unit=land_raider, phase_name="Movement phase")

    rules = dict(getattr(land_raider, "special_rules", {}) or {})
    assert sorted(rules.get("bearer_unit_phase_move_terrain_only_types") or []) == ["advance", "move"]
    assert sorted(rules.get("bearer_unit_phase_move_enemy_models_only_types") or []) == ["advance", "move"]
    assert sorted(rules.get("bearer_unit_phase_move_block_monster_vehicle_types") or []) == ["advance", "move"]
    assert rules.get("bearer_unit_auto_pass_desperate_escape") is True

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    rules = dict(getattr(land_raider, "special_rules", {}) or {})
    assert "bearer_unit_phase_move_terrain_only_types" not in rules
    assert "bearer_unit_phase_move_enemy_models_only_types" not in rules
    assert "bearer_unit_phase_move_block_monster_vehicle_types" not in rules
    assert "bearer_unit_auto_pass_desperate_escape" not in rules
    assert "space_marines_armoured_ceramite_sledgehammer_active" not in rules


def test_purgation_doctrine_grants_ranged_hit_and_heavy_transport_disembark_wound_bonus():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    sternguard = _make_unit("Sternguard Veterans", keywords=["INFANTRY"], wounds=2)
    land_raider = _make_unit("Land Raider", keywords=["VEHICLE", "TRANSPORT"], wounds=16)
    enemy = _make_unit("Enemy Target", faction_name="Enemy", keywords=["VEHICLE"], faction_keywords=["ENEMY"], wounds=12)
    sm_army.add_unit(sternguard)
    sm_army.add_unit(land_raider)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, sternguard, 10.0, 10.0)
    _deploy_unit(game, land_raider, 18.0, 10.0)
    _deploy_unit(game, enemy, 24.0, 10.0)
    game.rebuild_entity_registry()
    sternguard.round_state.disembarked_this_round = True
    sternguard.round_state.disembarked_from_transport_id = str(get_entity_id(land_raider) or "")
    profile = _ranged_profile()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "PURGATION DOCTRINE")
    assert pending is not None
    assert sm_player.stratagems.use("PURGATION DOCTRINE", unit=sternguard, phase_name="Shooting phase", dequeue=True)

    hit_mods = sternguard.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=sternguard.models[0],
        weapon_profile=profile,
    )
    wound_mods = sternguard.get_unit_wound_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=sternguard.models[0],
        weapon_profile=profile,
    )
    assert hit_mods.get("hit") == 1
    assert wound_mods.get("wound") == 1

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    rules = dict(getattr(sternguard, "special_rules", {}) or {})
    assert "space_marines_armoured_purgation_doctrine_active" not in rules


def test_rapid_embarkation_targets_heavy_transport_and_allows_existing_passengers():
    game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
    land_raider = _make_unit(
        "Land Raider",
        keywords=["VEHICLE", "TRANSPORT"],
        wounds=16,
        transport="Transport Capacity 12",
    )
    infantry = _make_unit("Assault Intercessors", keywords=["INFANTRY"], wounds=2)
    existing = _make_unit("Embarked Veterans", keywords=["INFANTRY"], wounds=2)
    land_raider.transport_capacity = 12
    land_raider.transport_required_keywords = set()
    land_raider.transport_excluded_keywords = set()
    land_raider.transport_passengers = [existing]
    existing.embarked_in = land_raider

    sm_army.add_unit(land_raider)
    sm_army.add_unit(infantry)
    sm_army.add_unit(existing)
    _deploy_unit(game, land_raider, 10.0, 10.0)
    _deploy_unit(game, infantry, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    sm_player.stratagems.get_pending_reactions(clear=True)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))

    pending = _pending_by_name(sm_player.stratagems, "RAPID EMBARKATION")
    assert pending is not None
    assert pending.get("transport_unit") is land_raider
    assert infantry in list(pending.get("embark_candidates") or [])

    assert sm_player.stratagems.use("RAPID EMBARKATION", unit=land_raider, phase_name="Fight phase", dequeue=True)
    request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="end_of_fight_embark")
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert dict(context.get("spec") or {}).get("allow_existing_passengers") is True
    option = _find_option_by_payload(request, key="target_unit_id", value=str(get_entity_id(infantry) or ""))
    assert option is not None

    result = resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert infantry.embarked_in is land_raider
    assert existing in list(getattr(land_raider, "transport_passengers", []) or [])
    assert infantry in list(getattr(land_raider, "transport_passengers", []) or [])


def test_machine_wrath_queues_pre_deadly_demise_move_and_cleans_up_after_followup():
    game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
    land_raider = _make_unit("Land Raider", keywords=["VEHICLE", "TRANSPORT"], movement=10, wounds=16)
    sm_army.add_unit(land_raider)
    _deploy_unit(game, land_raider, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    land_raider.remove_model(land_raider.models[0], game_map=game.map)
    pending = _pending_by_name(sm_player.stratagems, "MACHINE WRATH")
    assert pending is not None

    assert sm_player.stratagems.use("MACHINE WRATH", unit=land_raider, phase_name="Shooting phase", dequeue=True)
    request = _first_request(game, DECISION_MOVE_UNIT, ability="space_marines_armoured_speartip_machine_wrath")
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert context["reactive_move_kind"] == "armoured_speartip_machine_wrath"
    assert context["movement_type"] == "move"
    assert context["max_distance"] == 10
    assert context["allow_skip"] is True
    assert context["destroyed_transport_unit_id"] == str(get_entity_id(land_raider) or "")

    rules = dict(getattr(land_raider, "special_rules", {}) or {})
    assert rules.get("space_marines_armoured_machine_wrath_active") is True
    assert rules.get("bearer_unit_auto_pass_desperate_escape") is True
    assert sorted(rules.get("bearer_unit_phase_move_enemy_models_only_types") or []) == ["move"]

    land_raider.resolve_armoured_speartip_machine_wrath_post_move(game.map, use_move=False)
    rules = dict(getattr(land_raider, "special_rules", {}) or {})
    assert "space_marines_armoured_machine_wrath_active" not in rules
    assert "bearer_unit_auto_pass_desperate_escape" not in rules
    assert bool(getattr(land_raider, "_armoured_speartip_machine_wrath_pending_destroyed", False)) is False
