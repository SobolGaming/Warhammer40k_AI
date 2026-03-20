from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
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
        move: int = 6,
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
                "M": str(int(move)),
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
    move: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "Vindication Task Force")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

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
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _normalize_name(value: str) -> str:
    return str(value or "").strip().upper().replace("’", "'")


def _pending_by_name(stratagems, name: str):
    target = _normalize_name(name)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == target:
            return reaction
    return None


def _pending_names(stratagems) -> set[str]:
    return {_normalize_name(str(item.get("stratagem", "") or "")) for item in list(stratagems.get_pending_reactions(clear=True) or [])}


def _ranged_wargear(
    name: str = "Bolt Rifle",
    *,
    skill: str = "3+",
    strength: str = "4",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": str(description),
        }
    )


def _melee_wargear(
    name: str = "Power Sword",
    *,
    skill: str = "4+",
    strength: str = "5",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "-2",
            "D": "1",
            "description": str(description),
        }
    )


def _first_profile(wargear: Wargear):
    return next(iter(dict(getattr(wargear, "profiles", {}) or {}).values()))


def _publish_model_destroyed(game: Game, *, attacker_unit: Unit, target_unit: Unit, target_model=None, weapon_profile=None) -> None:
    destroyed_model = target_model or target_unit.models[0]
    game.event_system.publish(
        "model_destroyed",
        attacker_model=attacker_unit.models[0],
        attacker_unit=attacker_unit,
        target_model=destroyed_model,
        target_unit=target_unit,
        weapon_profile=weapon_profile,
        game_map=game.map,
    )


def test_vindication_task_force_stratagem_descriptors_registered():
    expected = {
        "000010397002": ("Refusal to Yield", "return_destroyed_model_full_wounds_as_close_as_possible_not_in_engagement"),
        "000010397003": ("Litanies of Purgation", "conditional_melee_ap_bonus_if_attacker_or_target_within_objective_range"),
        "000010397004": ("Spoor of the Unholy", "ranged_weapons_gain_ignores_cover_and_ignore_skill_hit_modifiers"),
        "000010397005": ("Reclaim Our Honour!", "mark_enemy_for_armywide_hit_bonus"),
        "000010397007": ("Perfervid Intervention", "out_of_turn_charge_without_charge_bonus"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_vindication_phase_and_destroyed_model_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    bladeguard = _make_unit(
        "Bladeguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    ancient = _make_unit(
        "Ancient",
        keywords=["INFANTRY", "ANCIENT"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(intercessors)
    sm_army.add_unit(bladeguard)
    sm_army.add_unit(ancient)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, bladeguard, 14.0, 10.0)
    _deploy_unit(game, ancient, 12.0, 13.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"SPOOR OF THE UNHOLY"}

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert _pending_names(sm_player.stratagems) == {"LITANIES OF PURGATION", "SPOOR OF THE UNHOLY"}

    bladeguard.can_declare_charge_against = lambda target, _game, out_of_turn=False: bool(out_of_turn) and target is enemy
    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert _pending_by_name(sm_player.stratagems, "PERFERVID INTERVENTION") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    _publish_model_destroyed(game, attacker_unit=enemy, target_unit=ancient)
    assert _pending_names(sm_player.stratagems) == {"RECLAIM OUR HONOUR!", "REFUSAL TO YIELD"}


def test_spoor_of_the_unholy_grants_ranged_ignores_cover_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    intercessors.models[0].wargear = [_ranged_wargear("Bolt Rifle")]
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "SPOOR OF THE UNHOLY") is not None

    ok = sm_player.stratagems.use(
        "SPOOR OF THE UNHOLY",
        unit=intercessors,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    model = intercessors.models[0]
    bonuses = list(model.get_temporary_weapon_keyword_bonuses("Bolt Rifle") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "IGNORES COVER"
        and str(entry.get("attack_type", "") or "").strip().lower() == "ranged"
        for entry in bonuses
    )

    profile = _first_profile(model.wargear[0])
    attack_instance = {"distance_to_target": 12.0}
    profile._hit_target_with_tracking(
        enemy,
        model,
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("ignores_cover")) is True

    game.event_system.publish("phase_end", player=sm_player, phase=game.phase)
    assert list(model.get_temporary_weapon_keyword_bonuses("Bolt Rifle") or []) == []
    assert bool(getattr(intercessors, "special_rules", {}).get("space_marines_vindication_spoor_of_the_unholy_active", False)) is False


def test_spoor_of_the_unholy_ignores_melee_weapon_skill_penalty():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    bladeguard = _make_unit(
        "Bladeguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    bladeguard.models[0].wargear = [_melee_wargear("Master-crafted Power Sword", skill="4+")]
    bladeguard.special_rules = {
        "data_spike_ws_penalty_active": True,
        "data_spike_ws_penalty": 1,
        "data_spike_ws_penalty_expires_phase": "FIGHT_PHASE",
        "data_spike_ws_penalty_source": "Data-spike",
    }
    sm_army.add_unit(bladeguard)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, bladeguard, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = sm_player.stratagems.use(
        "SPOOR OF THE UNHOLY",
        unit=bladeguard,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True

    model = bladeguard.models[0]
    profile = _first_profile(model.wargear[0])
    ignored = profile._hit_target_with_tracking(
        enemy,
        model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(ignored.get("base_skill", 0) or 0) == 4
    assert bool(ignored.get("hit")) is True

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert bool(getattr(bladeguard, "special_rules", {}).get("space_marines_vindication_spoor_of_the_unholy_active", False)) is False


def test_perfervid_intervention_attempts_out_of_turn_charge_without_charge_bonus():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    bladeguard = _make_unit(
        "Bladeguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(bladeguard)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, bladeguard, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.5, 10.0)
    game.rebuild_entity_registry()

    bladeguard.can_declare_charge_against = lambda target, _game, out_of_turn=False: bool(out_of_turn) and target is enemy
    game.map.is_path_blocked = lambda *_args, **_kwargs: False

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert _pending_by_name(sm_player.stratagems, "PERFERVID INTERVENTION") is not None

    game.attempt_charge = Mock(return_value=True)
    ok = sm_player.stratagems.use(
        "PERFERVID INTERVENTION",
        unit=bladeguard,
        enemy_unit=enemy,
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 8
    game.attempt_charge.assert_called_once_with(bladeguard, enemy, out_of_turn=True, count_as_charged=False)


def test_refusal_to_yield_returns_destroyed_ancient_at_phase_end_and_is_once_per_battle():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    ancient = _make_unit(
        "Ancient",
        keywords=["INFANTRY", "ANCIENT"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(ancient)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, ancient, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    model = ancient.models[0]
    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    _publish_model_destroyed(game, attacker_unit=enemy, target_unit=ancient, target_model=model)
    assert _pending_by_name(sm_player.stratagems, "REFUSAL TO YIELD") is not None

    ok = sm_player.stratagems.use(
        "REFUSAL TO YIELD",
        destroyed_unit=ancient,
        destroyed_model=model,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    ancient.models.remove(model)
    ancient.models_lost.append(model)
    ancient.deployed = False
    ancient.reserve_status = "destroyed"
    model.wounds = 0
    if ancient in list(getattr(game.map, "units", []) or []):
        game.map.units.remove(ancient)

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)

    assert model in list(ancient.models or [])
    assert model not in list(ancient.models_lost or [])
    assert int(getattr(model, "wounds", 0) or 0) == 4
    assert ancient in list(getattr(game.map, "units", []) or [])
    assert bool(model.has_used_once_per_battle("space_marines_vindication_refusal_to_yield")) is True

    sm_player.stratagems.get_pending_reactions(clear=True)
    game.turn = 2
    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    _publish_model_destroyed(game, attacker_unit=enemy, target_unit=ancient, target_model=model)
    assert _pending_by_name(sm_player.stratagems, "REFUSAL TO YIELD") is None


def test_reclaim_our_honour_marks_enemy_and_grants_armywide_hit_bonus():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    ancient = _make_unit(
        "Ancient",
        keywords=["INFANTRY", "ANCIENT"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sternguard = _make_unit(
        "Sternguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sternguard.models[0].wargear = [_ranged_wargear("Bolt Rifle", skill="3+")]
    enemy._has_line_of_sight_to_target = lambda *_args, **_kwargs: True
    sm_army.add_unit(ancient)
    sm_army.add_unit(intercessors)
    sm_army.add_unit(sternguard)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, ancient, 10.0, 10.0)
    _deploy_unit(game, intercessors, 12.0, 10.0)
    _deploy_unit(game, sternguard, 14.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    _publish_model_destroyed(game, attacker_unit=enemy, target_unit=ancient)
    assert _pending_by_name(sm_player.stratagems, "RECLAIM OUR HONOUR!") is not None

    ok = sm_player.stratagems.use(
        "RECLAIM OUR HONOUR!",
        unit=intercessors,
        enemy_unit=enemy,
        destroyed_unit=ancient,
        destroyed_model=ancient.models[0],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert bool(getattr(enemy, "special_rules", {}).get("space_marines_vindication_reclaim_our_honour_active", False)) is True

    attacker_model = sternguard.models[0]
    profile = _first_profile(attacker_model.wargear[0])
    hit = profile._hit_target_with_tracking(
        enemy,
        attacker_model,
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit.get("hit")) is True
    assert any("RECLAIM OUR HONOUR" in str(modifier or "").upper() for modifier in list(hit.get("modifiers", []) or []))


def test_reclaim_our_honour_blocks_refusal_to_yield_for_same_model_this_phase():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    ancient = _make_unit(
        "Ancient",
        keywords=["INFANTRY", "ANCIENT"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(ancient)
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    enemy._has_line_of_sight_to_target = lambda *_args, **_kwargs: True
    _deploy_unit(game, ancient, 10.0, 10.0)
    _deploy_unit(game, intercessors, 12.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    _publish_model_destroyed(game, attacker_unit=enemy, target_unit=ancient)

    assert sm_player.stratagems.use(
        "RECLAIM OUR HONOUR!",
        unit=intercessors,
        enemy_unit=enemy,
        destroyed_unit=ancient,
        destroyed_model=ancient.models[0],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert (
        sm_player.stratagems.use(
            "REFUSAL TO YIELD",
            destroyed_unit=ancient,
            destroyed_model=ancient.models[0],
            phase_name="Fight phase",
        )
        is False
    )


def test_refusal_to_yield_blocks_reclaim_our_honour_for_same_model_this_phase():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    ancient = _make_unit(
        "Ancient",
        keywords=["INFANTRY", "ANCIENT"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(ancient)
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    enemy._has_line_of_sight_to_target = lambda *_args, **_kwargs: True
    _deploy_unit(game, ancient, 10.0, 10.0)
    _deploy_unit(game, intercessors, 12.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    _publish_model_destroyed(game, attacker_unit=enemy, target_unit=ancient)

    assert sm_player.stratagems.use(
        "REFUSAL TO YIELD",
        destroyed_unit=ancient,
        destroyed_model=ancient.models[0],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert (
        sm_player.stratagems.use(
            "RECLAIM OUR HONOUR!",
            unit=intercessors,
            enemy_unit=enemy,
            destroyed_unit=ancient,
            destroyed_model=ancient.models[0],
            phase_name="Fight phase",
        )
        is False
    )
