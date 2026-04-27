from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, Wargear, WargearProfile
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        movement: str = "8",
        toughness: str = "8",
        wounds: str = "8",
        objective_control: str = "2",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "6",
                "OC": str(objective_control),
                "base_size": "80mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


class _DummyProfile:
    def __init__(self, *, blast: bool = False, indirect: bool = True):
        self._blast = bool(blast)
        self._indirect = bool(indirect)
        self.name = "Dummy Weapon"
        self.range = SimpleNamespace(max=999.0)

    def is_pistol(self) -> bool:
        return False

    def is_blast(self) -> bool:
        return self._blast

    def is_indirect_fire(self) -> bool:
        return self._indirect


class _DummyMap:
    def __init__(self, units, engaged_pairs):
        self.units = list(units)
        self._engaged = set(frozenset({id(a), id(b)}) for (a, b) in engaged_pairs)

    def get_enemy_units(self, unit):
        return [u for u in self.units if u.get_parent_army() != unit.get_parent_army()]

    def get_friendly_units(self, unit):
        return [u for u in self.units if u.get_parent_army() == unit.get_parent_army()]

    def is_within_engagement_range(self, a, b) -> bool:
        return frozenset({id(a), id(b)}) in self._engaged


def create_unit(
    name: str,
    x: float,
    y: float,
    *,
    keywords=None,
    faction_keywords=None,
    movement: str = "8",
    toughness: str = "8",
    wounds: str = "8",
) -> Unit:
    unit = Unit(
        MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
        )
    )
    for model in list(unit.models or []):
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    guard_army = Army.with_detachment("Astra Militarum", detachment_type="Steel Hammer")
    guard_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    guard_player = Player("Guard", PlayerControl.REMOTE, army=guard_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(guard_player)
    game.add_player(enemy_player)
    return game, guard_player, enemy_player


def _place_unit(game: Game, unit: Unit) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    if unit not in game.map.units:
        game.map.units.append(unit)


def _finalize_game(game: Game, *players: Player) -> None:
    game.rebuild_entity_registry()
    for player in players:
        player.army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


def _make_hit_profile(*, indirect: bool = False):
    profile = WargearProfile.__new__(WargearProfile)
    profile.skill = 3
    profile.parent_wargear = SimpleNamespace(is_ranged=lambda: True, is_melee=lambda: False)
    profile.is_torrent = lambda: False
    profile.is_heavy = lambda: False
    profile.is_pistol = lambda: False
    profile.is_indirect_fire = lambda: bool(indirect)
    profile.is_lethal_hits = lambda: False
    profile.is_sustained_hits = lambda: False
    return profile


def _make_melee_profile(*, attacks: str = "3", ap: str = "-1"):
    weapon = Wargear(
        {
            "name": "Titanic Feet",
            "type": "Melee",
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": "4+",
            "S": "8",
            "AP": str(ap),
            "D": "2",
        }
    )
    return weapon.profiles["default"]


def _attack_result(profile, attacker, target_unit):
    return AttackResult(
        weapon_name=str(getattr(profile, "name", "") or "Weapon"),
        attacker_name=str(getattr(attacker, "name", "") or "Attacker"),
        target_unit_name=str(getattr(target_unit, "name", "") or "Target"),
        attacks_rolled=0,
        attacks_dice_expression=str(getattr(profile, "attacks", "")),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def test_ceaseless_cannonade_muster_selection_applies_character_to_titanic_units():
    game, player, _enemy = _make_game()
    baneblade = create_unit(
        "Baneblade",
        10.0,
        10.0,
        keywords=["VEHICLE", "TITANIC"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="24",
    )
    shadowsword = create_unit(
        "Shadowsword",
        12.0,
        10.0,
        keywords=["VEHICLE", "TITANIC"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="24",
    )
    leman_russ = create_unit(
        "Leman Russ",
        14.0,
        10.0,
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="13",
    )
    player.army.add_unit(baneblade)
    player.army.add_unit(shadowsword)
    player.army.add_unit(leman_russ)
    game.rebuild_entity_registry()

    mgr = player.army.astra_militarum_detachments
    mgr.queue_steel_hammer_titanic_character_selection_request(game=game, player=player)

    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_REALM_OF_CHAOS_UNITS
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower()
        == "steel_hammer_titanic_character_selection"
    ]
    assert len(requests) == 1
    request = requests[0]
    assert str(getattr(request, "context", {}).get("ability_name", "") or "") == "Ceaseless Cannonade"
    allowed_ids = set(getattr(request, "context", {}).get("allowed_unit_ids", []) or [])
    assert str(get_entity_id(baneblade) or "") in allowed_ids
    assert str(get_entity_id(shadowsword) or "") in allowed_ids
    assert str(get_entity_id(leman_russ) or "") not in allowed_ids

    confirm_option = next(
        option
        for option in list(getattr(request, "options", []) or [])
        if str((getattr(option, "payload", {}) or {}).get("action", "") or "").strip().lower() == "confirm"
    )
    cmd = resolve_decision_command(
        game,
        request,
        confirm_option.option_id,
        result_payload={"unit_ids": [str(get_entity_id(baneblade) or "")]},
        player_id=player.id,
    )
    assert bool(getattr(cmd, "ok", False))
    assert baneblade.has_any_keyword("CHARACTER")
    assert baneblade.models[0].has_any_keyword("CHARACTER")
    assert not shadowsword.has_any_keyword("CHARACTER")
    assert not leman_russ.has_any_keyword("CHARACTER")


def test_ceaseless_cannonade_allows_blast_into_own_engagement_only():
    game, player, enemy_player = _make_game()
    squadron = create_unit(
        "Leman Russ",
        10.0,
        10.0,
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="13",
    )
    friendly = create_unit(
        "Infantry Squad",
        11.0,
        10.0,
        keywords=["INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="1",
    )
    enemy = create_unit("Enemy", 10.0, 11.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    player.army.add_unit(squadron)
    player.army.add_unit(friendly)
    enemy_player.army.add_unit(enemy)

    game.get_current_player = lambda: player
    game.is_shooting_phase = lambda: True
    blast = _DummyProfile(blast=True, indirect=True)
    own_combat_map = _DummyMap([squadron, friendly, enemy], [(squadron, enemy)])
    game.map = own_combat_map

    assert squadron._can_model_shoot_weapon_at_target(squadron.models[0], blast, enemy, own_combat_map)

    shared_combat_map = _DummyMap([squadron, friendly, enemy], [(squadron, enemy), (friendly, enemy)])
    game.map = shared_combat_map
    assert not squadron._can_model_shoot_weapon_at_target(squadron.models[0], blast, enemy, shared_combat_map)


def test_ceaseless_cannonade_suppresses_bgnt_hit_penalty_except_indirect_fire(monkeypatch):
    from warhammer40k_ai.units import wargear as wargear_mod

    game, player, enemy_player = _make_game()
    squadron = create_unit(
        "Leman Russ",
        10.0,
        10.0,
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="13",
    )
    enemy = create_unit("Enemy", 10.0, 11.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    player.army.add_unit(squadron)
    enemy_player.army.add_unit(enemy)
    game.get_current_player = lambda: player
    game.is_shooting_phase = lambda: True
    game.map = _DummyMap([squadron, enemy], [(squadron, enemy)])
    setattr(squadron, "_bgnt_locked_at_target_selection", True)

    monkeypatch.setattr(wargear_mod, "get_roll", lambda _dice: 4)
    non_indirect = _make_hit_profile(indirect=False)
    hit = non_indirect._hit_target_with_tracking(enemy, squadron.models[0], {})
    assert hit["final_needed"] == 3
    assert not any("Big Guns Never Tire" in str(mod or "") for mod in list(hit.get("modifiers", []) or []))

    indirect = _make_hit_profile(indirect=True)
    indirect_hit = indirect._hit_target_with_tracking(enemy, squadron.models[0], {})
    assert any("Big Guns Never Tire" in str(mod or "") for mod in list(indirect_hit.get("modifiers", []) or []))


def test_steel_hammer_accuracy_under_pressure_descriptor_registered():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010788007")

    assert descriptor is not None
    assert descriptor.name == "Accuracy Under Pressure"
    assert descriptor.cp_cost == 2
    assert descriptor.effect == "full_hit_reroll"
    assert descriptor.effect_params["requires_not_selected_to_shoot_this_phase"] is True
    assert descriptor.effect_params["attack_type"] == "ranged"


def test_steel_hammer_adamantine_behemoth_descriptor_registered():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010788004")

    assert descriptor is not None
    assert descriptor.name == "Adamantine Behemoth"
    assert descriptor.cp_cost == 1
    assert descriptor.effect == "move_through_terrain_horizontally"
    assert descriptor.effect_params["target_keywords_all"] == ["VEHICLE"]
    assert descriptor.effect_params["movement_types"] == ["move", "advance", "charge"]


def test_steel_hammer_engine_of_wrath_descriptor_registered():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010788002")

    assert descriptor is not None
    assert descriptor.name == "Engine of Wrath"
    assert descriptor.cp_cost == 1
    assert descriptor.effect == "target_locked_melee_attacks_and_ap_bonus"
    assert descriptor.effect_params["target_keywords_all"] == ["TITANIC"]
    assert descriptor.effect_params["melee_attacks_bonus"] == 6
    assert descriptor.effect_params["melee_ap_bonus"] == 2


def test_steel_hammer_imposing_arrival_descriptor_registered():
    descriptor = get_stratagem_tool_descriptor(stratagem_id="000010788003")

    assert descriptor is not None
    assert descriptor.name == "Imposing Arrival"
    assert descriptor.cp_cost == 1
    assert descriptor.effect == "custom_reserves_arrival"
    assert descriptor.effect_params["target_keywords_all"] == ["TITANIC"]
    assert descriptor.effect_params["battlefield_edge_wholly_within"] == 8
    assert descriptor.effect_params["min_enemy_horizontal_distance"] == 6


def test_accuracy_under_pressure_grants_hit_rerolls_until_phase_end():
    game, player, enemy_player = _make_game()
    squadron = create_unit(
        "Leman Russ",
        10.0,
        10.0,
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="13",
    )
    infantry = create_unit(
        "Infantry Squad",
        12.0,
        10.0,
        keywords=["INFANTRY", "REGIMENT"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="1",
    )
    enemy = create_unit("Enemy", 20.0, 10.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    player.army.add_unit(squadron)
    player.army.add_unit(infantry)
    enemy_player.army.add_unit(enemy)
    for unit in (squadron, infantry, enemy):
        _place_unit(game, unit)
    player.command_points = 10
    _finalize_game(game, player, enemy_player)

    game.current_player_index = game.players.index(player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")

    assert player.stratagems.use("ACCURACY UNDER PRESSURE", unit=squadron, phase_name="Shooting phase") is True
    assert int(player.command_points or 0) == 8
    assert squadron.special_rules.get("steel_hammer_accuracy_under_pressure_active") is True

    mods = squadron.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=squadron.models[0],
    )
    assert mods.get("reroll_hit_full") is True
    assert any("ACCURACY UNDER PRESSURE" in str(item).upper() for item in mods.get("reroll_hit_full_reasons", ()))

    melee_mods = squadron.get_unit_hit_reroll_modifiers(
        "melee",
        target=enemy,
        attacker_model=squadron.models[0],
    )
    assert melee_mods.get("reroll_hit_full") is False
    other_mods = infantry.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=infantry.models[0],
    )
    assert other_mods.get("reroll_hit_full") is False

    game.event_system.publish("phase_end", player=player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    expired_mods = squadron.get_unit_hit_reroll_modifiers(
        "ranged",
        target=enemy,
        attacker_model=squadron.models[0],
    )
    assert expired_mods.get("reroll_hit_full") is False


def test_accuracy_under_pressure_rejects_units_that_already_shot():
    game, player, enemy_player = _make_game()
    already_shot = create_unit(
        "Rogal Dorn Battle Tank",
        10.0,
        10.0,
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="18",
    )
    valid = create_unit(
        "Leman Russ",
        12.0,
        10.0,
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="13",
    )
    player.army.add_unit(already_shot)
    player.army.add_unit(valid)
    for unit in (already_shot, valid):
        _place_unit(game, unit)
    already_shot.round_state.shot_this_round = True
    player.command_points = 10
    _finalize_game(game, player, enemy_player)

    game.current_player_index = game.players.index(player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")

    assert player.stratagems.use("ACCURACY UNDER PRESSURE", unit=already_shot, phase_name="Shooting phase") is False
    assert int(player.command_points or 0) == 10
    assert player.stratagems.use("ACCURACY UNDER PRESSURE", unit=valid, phase_name="Shooting phase") is True
    assert int(player.command_points or 0) == 8


def test_adamantine_behemoth_allows_vehicle_to_move_horizontally_through_terrain_until_phase_end():
    game, player, enemy_player = _make_game()
    vehicle = create_unit(
        "Rogal Dorn Battle Tank",
        10.0,
        10.0,
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="18",
    )
    player.army.add_unit(vehicle)
    _place_unit(game, vehicle)
    player.command_points = 10
    _finalize_game(game, player, enemy_player)

    game.current_player_index = game.players.index(player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")

    assert player.stratagems.use("ADAMANTINE BEHEMOTH", unit=vehicle, phase_name="Movement phase") is True
    assert int(player.command_points or 0) == 9
    assert vehicle.special_rules.get("steel_hammer_adamantine_behemoth_active") is True

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=vehicle)
    advance_rules = get_validation_rules(MovementType.ADVANCE, moving_unit=vehicle)
    charge_rules = get_validation_rules(MovementType.CHARGE, moving_unit=vehicle)
    assert bool(move_rules.get("can_move_through_terrain")) is True
    assert bool(advance_rules.get("can_move_through_terrain")) is True
    assert bool(charge_rules.get("can_move_through_terrain")) is True

    game.event_system.publish("phase_end", player=player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    move_rules_after = get_validation_rules(MovementType.MOVE, moving_unit=vehicle)
    charge_rules_after = get_validation_rules(MovementType.CHARGE, moving_unit=vehicle)
    assert bool(move_rules_after.get("can_move_through_terrain")) is False
    assert bool(charge_rules_after.get("can_move_through_terrain")) is False


def test_adamantine_behemoth_rejects_non_vehicle_or_already_selected_units():
    game, player, enemy_player = _make_game()
    infantry = create_unit(
        "Infantry Squad",
        10.0,
        10.0,
        keywords=["INFANTRY", "REGIMENT"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="1",
    )
    moved_vehicle = create_unit(
        "Leman Russ",
        12.0,
        10.0,
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="13",
    )
    valid = create_unit(
        "Rogal Dorn Battle Tank",
        14.0,
        10.0,
        keywords=["VEHICLE", "SQUADRON"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="18",
    )
    for unit in (infantry, moved_vehicle, valid):
        player.army.add_unit(unit)
        _place_unit(game, unit)
    moved_vehicle.round_state.moved_this_round = True
    player.command_points = 10
    _finalize_game(game, player, enemy_player)

    game.current_player_index = game.players.index(player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")

    assert player.stratagems.use("ADAMANTINE BEHEMOTH", unit=infantry, phase_name="Movement phase") is False
    assert player.stratagems.use("ADAMANTINE BEHEMOTH", unit=moved_vehicle, phase_name="Movement phase") is False
    assert int(player.command_points or 0) == 10
    assert player.stratagems.use("ADAMANTINE BEHEMOTH", unit=valid, phase_name="Movement phase") is True
    assert int(player.command_points or 0) == 9


def test_engine_of_wrath_locks_titanic_unit_and_improves_melee_until_phase_end():
    game, player, enemy_player = _make_game()
    titan = create_unit(
        "Baneblade",
        10.0,
        10.0,
        keywords=["VEHICLE", "TITANIC"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="24",
    )
    enemy = create_unit("Enemy One", 10.0, 11.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    other = create_unit("Enemy Two", 11.0, 10.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    player.army.add_unit(titan)
    enemy_player.army.add_unit(enemy)
    enemy_player.army.add_unit(other)
    game.map = _DummyMap([titan, enemy, other], [(titan, enemy), (titan, other)])
    player.command_points = 10
    _finalize_game(game, player, enemy_player)

    game.current_player_index = game.players.index(player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="FIGHT_PHASE")

    assert player.stratagems.use("ENGINE OF WRATH", unit=titan, enemy_unit=enemy, phase_name="Fight phase") is True
    assert int(player.command_points or 0) == 9
    assert titan.special_rules.get("steel_hammer_engine_of_wrath_active") is True

    eligible = FightPhaseManager(game)._get_eligible_targets(titan)
    assert eligible == [enemy]

    profile = _make_melee_profile(attacks="3", ap="-1")
    attack_result = _attack_result(profile, titan.models[0], enemy)
    attack_count = profile._resolve_attack_count(enemy, titan.models[0], attack_result, publish_roll_event=False)
    assert int(attack_count.num_attacks or 0) == 9
    assert any("ENGINE OF WRATH" in str(item).upper() for item in attack_result.attacks_special_modifiers)
    assert int(profile.get_effective_ap(titan.models[0], enemy) or 0) == -3

    other_result = _attack_result(profile, titan.models[0], other)
    other_count = profile._resolve_attack_count(other, titan.models[0], other_result, publish_roll_event=False)
    assert int(other_count.num_attacks or 0) == 3
    assert int(profile.get_effective_ap(titan.models[0], other) or 0) == -1

    game.event_system.publish("phase_end", player=player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    expired_result = _attack_result(profile, titan.models[0], enemy)
    expired_count = profile._resolve_attack_count(enemy, titan.models[0], expired_result, publish_roll_event=False)
    assert int(expired_count.num_attacks or 0) == 3
    assert int(profile.get_effective_ap(titan.models[0], enemy) or 0) == -1


def test_engine_of_wrath_rejects_non_titanic_or_already_fought_units():
    game, player, enemy_player = _make_game()
    infantry = create_unit(
        "Infantry Squad",
        10.0,
        10.0,
        keywords=["INFANTRY", "REGIMENT"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="1",
    )
    fought_titan = create_unit(
        "Shadowsword",
        12.0,
        10.0,
        keywords=["VEHICLE", "TITANIC"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="24",
    )
    valid = create_unit(
        "Baneblade",
        14.0,
        10.0,
        keywords=["VEHICLE", "TITANIC"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="24",
    )
    enemy = create_unit("Enemy", 13.0, 10.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    for unit in (infantry, fought_titan, valid):
        player.army.add_unit(unit)
    enemy_player.army.add_unit(enemy)
    game.map = _DummyMap([infantry, fought_titan, valid, enemy], [(infantry, enemy), (fought_titan, enemy), (valid, enemy)])
    fought_titan.round_state.fought_this_phase = True
    player.command_points = 10
    _finalize_game(game, player, enemy_player)

    game.current_player_index = game.players.index(player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="FIGHT_PHASE")

    assert player.stratagems.use("ENGINE OF WRATH", unit=infantry, enemy_unit=enemy, phase_name="Fight phase") is False
    assert player.stratagems.use("ENGINE OF WRATH", unit=fought_titan, enemy_unit=enemy, phase_name="Fight phase") is False
    assert int(player.command_points or 0) == 10
    assert player.stratagems.use("ENGINE OF WRATH", unit=valid, enemy_unit=enemy, phase_name="Fight phase") is True
    assert int(player.command_points or 0) == 9


def test_imposing_arrival_sets_up_titanic_unit_from_reserves():
    game, player, enemy_player = _make_game()
    titan = create_unit(
        "Baneblade",
        10.0,
        10.0,
        keywords=["VEHICLE", "TITANIC"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="24",
    )
    titan.reserve_status = "strategic_reserves"
    titan.deployed = False
    enemy = create_unit("Enemy", 20.0, 20.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    player.army.add_unit(titan)
    enemy_player.army.add_unit(enemy)
    _place_unit(game, enemy)
    player.command_points = 10
    game.turn = 2
    game.reinforcements_step_active = True
    _finalize_game(game, player, enemy_player)

    game.current_player_index = game.players.index(player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")

    assert player.stratagems.use(
        "IMPOSING ARRIVAL",
        unit=titan,
        position=(3.0, 20.0, 0.0),
        phase_name="Movement phase",
    ) is True
    assert int(player.command_points or 0) == 9
    assert str(getattr(titan, "reserve_status", "") or "") == "deployed"
    assert bool(getattr(titan, "deployed", False)) is True
    assert titan in game.map.units
    assert bool(getattr(titan, "arrived_from_reserves_this_turn", False)) is True


def test_imposing_arrival_rejects_round_one_non_titanic_and_invalid_placement():
    game, player, enemy_player = _make_game()
    titan = create_unit(
        "Baneblade",
        10.0,
        10.0,
        keywords=["VEHICLE", "TITANIC"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="24",
    )
    infantry = create_unit(
        "Infantry Squad",
        10.0,
        12.0,
        keywords=["INFANTRY", "REGIMENT"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds="1",
    )
    enemy = create_unit("Enemy", 8.0, 20.0, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    for unit in (titan, infantry):
        unit.reserve_status = "strategic_reserves"
        unit.deployed = False
        player.army.add_unit(unit)
    enemy_player.army.add_unit(enemy)
    _place_unit(game, enemy)
    player.command_points = 10
    game.turn = 1
    game.reinforcements_step_active = True
    _finalize_game(game, player, enemy_player)

    game.current_player_index = game.players.index(player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")

    assert player.stratagems.use(
        "IMPOSING ARRIVAL",
        unit=titan,
        position=(3.0, 20.0, 0.0),
        phase_name="Movement phase",
    ) is False

    game.turn = 2
    assert player.stratagems.use(
        "IMPOSING ARRIVAL",
        unit=infantry,
        position=(3.0, 20.0, 0.0),
        phase_name="Movement phase",
    ) is False
    assert player.stratagems.use(
        "IMPOSING ARRIVAL",
        unit=titan,
        position=(3.0, 20.0, 0.0),
        phase_name="Movement phase",
    ) is False
    assert int(player.command_points or 0) == 10
    assert str(getattr(titan, "reserve_status", "") or "") == "strategic_reserves"
