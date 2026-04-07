from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
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

    sm_army = Army.with_detachment("Space Marines", "Hammer of Avernii")
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


def _melee_wargear(name: str = "Power Fist") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "4",
            "BS_WS": "3+",
            "S": "8",
            "AP": "-2",
            "D": "2",
            "description": "",
        }
    )


def test_hammer_of_avernii_stratagem_descriptors_registered():
    expected = {
        "000010624006": ("Augmetic Fortitude", "defensive_damage_reduction"),
        "000010624005": ("Cogitated Ferocity", "choose_lethal_hits_or_sustained_hits_1_for_weapons"),
        "000010624004": ("Dominator Beacon", "sticky_objective"),
        "000010624007": ("Dropship Extraction", "enter_strategic_reserves"),
        "000010624003": ("Ruthless Butchery", "hit_bonus_and_conditional_wound_bonus"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_dominator_beacon_reaction_applies_sticky_objective_control_for_dreadnought():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    dreadnought = _make_unit(
        "Redemptor Dreadnought",
        keywords=["VEHICLE", "DREADNOUGHT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=12,
    )
    objective = _make_objective("Midfield Objective", 10.0, 10.0)
    objective.location.controlling_player = sm_player
    sm_army.add_unit(dreadnought)
    _deploy_unit(game, dreadnought, 10.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "DOMINATOR BEACON")
    assert pending is not None

    ok = sm_player.stratagems.use("DOMINATOR BEACON", unit=dreadnought, objective=objective, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert objective.location.sticky_controller is sm_player
    assert objective.location.controlling_player is sm_player


def test_ruthless_butchery_applies_hit_bonus_and_below_starting_wound_bonus_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    dreadnought = _make_unit(
        "Ballistus Dreadnought",
        keywords=["VEHICLE", "DREADNOUGHT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=12,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    sm_army.add_unit(dreadnought)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, dreadnought, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "RUTHLESS BUTCHERY")
    assert pending is not None

    ok = sm_player.stratagems.use("RUTHLESS BUTCHERY", unit=dreadnought, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    profile = _make_profile(is_melee=False, skill="4+", strength="4")
    attacker = dreadnought.models[0]
    hit_result = profile._hit_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("RUTHLESS BUTCHERY" in str(modifier).upper() for modifier in list(hit_result.get("modifiers", []) or []))

    wound_before = profile._wound_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("RUTHLESS BUTCHERY" in str(modifier).upper() for modifier in list(wound_before.get("modifiers", []) or []))

    attacker.take_damage(1, game_map=game.map)
    assert bool(dreadnought.is_below_starting_strength())
    assert not bool(dreadnought.is_below_half_strength())

    wound_after = profile._wound_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("RUTHLESS BUTCHERY" in str(modifier).upper() for modifier in list(wound_after.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))

    hit_after_cleanup = profile._hit_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    wound_after_cleanup = profile._wound_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("RUTHLESS BUTCHERY" in str(modifier).upper() for modifier in list(hit_after_cleanup.get("modifiers", []) or []))
    assert not any("RUTHLESS BUTCHERY" in str(modifier).upper() for modifier in list(wound_after_cleanup.get("modifiers", []) or []))


def test_augmetic_fortitude_reaction_reduces_incoming_melee_damage():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    defenders = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=4,
    )
    charger = _make_unit(
        "Enemy Chargers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    sm_army.add_unit(defenders)
    enemy_army.add_unit(charger)
    _deploy_unit(game, defenders, 10.0, 10.0)
    _deploy_unit(game, charger, 12.0, 10.0)
    game.map.is_within_engagement_range = lambda first, second: {first, second} == {defenders, charger}
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=charger, action="charge")
    pending = _pending_by_name(sm_player.stratagems, "AUGMETIC FORTITUDE")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "AUGMETIC FORTITUDE",
        unit=defenders,
        attacking_unit=charger,
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    game.phase = BattleRoundPhases.FIGHT_PHASE
    profile = _make_profile(is_melee=True, skill="3+", strength="6", damage="2")
    damage_result = profile._damage_target_with_tracking(
        defenders.models[0],
        charger.models[0],
        {"mortal_wound": False, "mortal_wound_in_addition": False},
    )
    assert int(damage_result.get("damage_applied", 0) or 0) == 1


def test_cogitated_ferocity_applies_selected_melee_keyword_then_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    dreadnought = _make_unit(
        "Brutalis Dreadnought",
        keywords=["VEHICLE", "DREADNOUGHT"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=12,
    )
    dreadnought.models[0].wargear = [_melee_wargear()]
    sm_army.add_unit(dreadnought)
    _deploy_unit(game, dreadnought, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "COGITATED FEROCITY")
    assert pending is not None

    ok = sm_player.stratagems.use("COGITATED FEROCITY", unit=dreadnought, choice="LETHAL_HITS", dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    bonuses = dreadnought.models[0].get_temporary_weapon_keyword_bonuses("Power Fist")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "LETHAL HITS"
        and str(item.get("attack_type", "") or "").strip().lower() == "melee"
        for item in list(bonuses or [])
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(dreadnought.models[0].get_temporary_weapon_keyword_bonuses("Power Fist") or []) == []


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
