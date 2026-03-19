from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile


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
                "M": "6",
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

    sm_army = Army("Space Marines", "Emperor's Shield")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
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
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
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


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="",
        conditions=lambda _game: False,
        location=point,
    )


def _make_profile(*, is_melee: bool, skill: str = "4+", strength: str = "4", damage: str = "1") -> WargearProfile:
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


def test_emperors_shield_stratagem_descriptors_registered():
    expected = {
        "000010461006": ("Disciplined Extermination", "ranged_ignores_cover_and_ap_bonus"),
        "000010461007": ("Dropship Extraction", "enter_strategic_reserves"),
        "000010461003": ("Fury of the First", "hit_bonus_and_conditional_wound_bonus"),
        "000010461004": ("Obdurate Vengeance", "fight_on_death_after_attacks"),
        "000010461005": ("Wrathful Conquerors", "sticky_objective"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_wrathful_conquerors_reaction_applies_sticky_objective_control():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    veterans = _make_unit(
        "Bladeguard Veteran Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    objective = _make_objective("Home Objective", 10.0, 10.0)
    objective.location.controlling_player = sm_player
    sm_army.add_unit(veterans)
    _deploy_unit(game, veterans, 10.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "WRATHFUL CONQUERORS")
    assert pending is not None

    ok = sm_player.stratagems.use("WRATHFUL CONQUERORS", objective=objective, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert objective.location.sticky_controller is sm_player
    assert objective.location.controlling_player is sm_player


def test_disciplined_extermination_applies_ignores_cover_and_ap_bonus_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    sternguard = _make_unit(
        "Sternguard Veteran Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sternguard.models[0].wargear = [_ranged_wargear()]
    sm_army.add_unit(sternguard)
    _deploy_unit(game, sternguard, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "DISCIPLINED EXTERMINATION")
    assert pending is not None

    ok = sm_player.stratagems.use("DISCIPLINED EXTERMINATION", unit=sternguard, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    bonuses = sternguard.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "IGNORES COVER"
        and str(item.get("attack_type", "") or "").strip().lower() == "ranged"
        for item in list(bonuses or [])
    )
    ap_bonus, ap_reasons = sternguard.models[0].get_temporary_weapon_ap_bonus("Bolt Rifle")
    assert int(ap_bonus or 0) == 1
    assert any("DISCIPLINED EXTERMINATION" in str(reason).upper() for reason in list(ap_reasons or []))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert sternguard.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") == []
    assert sternguard.models[0].get_temporary_weapon_ap_bonus("Bolt Rifle")[0] == 0


def test_disciplined_extermination_not_available_after_unit_already_shot():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    sternguard = _make_unit(
        "Sternguard Veteran Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sternguard.round_state.shot_this_round = True
    sm_army.add_unit(sternguard)
    _deploy_unit(game, sternguard, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "DISCIPLINED EXTERMINATION") is None


def test_fury_of_the_first_applies_hit_bonus_and_conditional_wound_bonus_then_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=4,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    sm_army.add_unit(terminators)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "FURY OF THE FIRST")
    assert pending is not None

    ok = sm_player.stratagems.use("FURY OF THE FIRST", dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    profile = _make_profile(is_melee=False, skill="4+", strength="4")
    attacker = terminators.models[0]
    hit_result = profile._hit_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("FURY OF THE FIRST" in str(modifier).upper() for modifier in list(hit_result.get("modifiers", []) or []))

    wound_before = profile._wound_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("FURY OF THE FIRST" in str(modifier).upper() for modifier in list(wound_before.get("modifiers", []) or []))

    attacker.take_damage(3, game_map=game.map)
    assert bool(terminators.is_below_half_strength())

    wound_after = profile._wound_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("FURY OF THE FIRST" in str(modifier).upper() for modifier in list(wound_after.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    hit_after_cleanup = profile._hit_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("FURY OF THE FIRST" in str(modifier).upper() for modifier in list(hit_after_cleanup.get("modifiers", []) or []))

    terminators.round_state.fought_this_phase = False
    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert _pending_by_name(sm_player.stratagems, "FURY OF THE FIRST") is not None


def test_dropship_extraction_reaction_enters_strategic_reserves_without_temp_deep_strike():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(terminators)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    game.map.is_within_engagement_range = lambda _first, _second: False
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(sm_player.stratagems, "DROPSHIP EXTRACTION")
    assert pending is not None

    ok = sm_player.stratagems.use("DROPSHIP EXTRACTION", unit=terminators, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert bool(terminators.is_in_strategic_reserves())
    sr = dict(getattr(terminators, "special_rules", {}) or {})
    assert not bool(sr.get("midgame_temp_deep_strike"))


def test_obdurate_vengeance_reaction_grants_melee_fight_on_death_and_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    target = _make_unit(
        "Bladeguard Veteran Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
        wounds=4,
    )
    enemy = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=2,
        wounds=4,
    )
    sm_army.add_unit(target)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[target])
    pending = _pending_by_name(sm_player.stratagems, "OBDURATE VENGEANCE")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "OBDURATE VENGEANCE",
        unit=target,
        attacking_unit=enemy,
        target_units=[target],
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    model = target.models[0]
    rule = target.get_melee_fight_on_death_after_attacks_rule(model=model)
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 3
    assert "OBDURATE VENGEANCE" in str(rule.get("source", "")).upper()

    target.round_state.fought_this_phase = False
    target._last_destroyed_by_weapon_profile = _make_profile(is_melee=True, skill="3+", strength="6", damage="2")
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=3):
        model._wounds = 0
        target._handle_model_destroyed(model, game.map)
    pending_models = list(getattr(target, "_melee_fight_on_death_pending_models", []) or [])
    assert model in pending_models

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert target.get_melee_fight_on_death_after_attacks_rule(model=model) is None
