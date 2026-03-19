from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


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
                "M": "12" if "MOUNTED" in list(keywords or []) else "6",
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

    sm_army = Army("Space Marines", "Company of Hunters")
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
        model.set_location(float(x) + float(index) * 2.0, float(y), 0.0, 0.0)
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


def _make_profile(*, is_melee: bool, strength: str = "4") -> WargearProfile:
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
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_company_of_hunters_stratagem_descriptors_registered():
    expected = {
        "000008779005": ("Death on the Wind", "force_battleshock_test_with_conditional_ravenwing_modifier"),
        "000008779002": ("Hunters' Trail", "sticky_objective"),
        "000008779007": ("Rapid Reappraisal", "enter_strategic_reserves"),
        "000008779004": ("Talon Strike", "conditional_wound_bonus_vs_character_infantry_or_mounted"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_company_of_hunters_phase_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    ravenwing = _make_unit(
        "Ravenwing Outriders",
        keywords=["MOUNTED", "RAVENWING"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    objective = _make_objective("Midfield", 10.0, 10.0)
    objective.location.controlling_player = sm_player

    sm_army.add_unit(ravenwing)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, ravenwing, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    command_names = {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in sm_player.stratagems.get_pending_reactions(clear=True)
    }
    assert command_names == {"HUNTERS' TRAIL"}

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    shooting_names = {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in sm_player.stratagems.get_pending_reactions(clear=True)
    }
    assert shooting_names == {"TALON STRIKE"}

    ravenwing.round_state.shot_this_round = True
    game.event_system.publish("unit_shooting_resolved", attacker_unit=ravenwing, hits_by_target={enemy: 1})
    reaction = _pending_by_name(sm_player.stratagems, "DEATH ON THE WIND")
    assert reaction is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    ravenwing.round_state.fought_this_phase = False
    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    fight_names = {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in sm_player.stratagems.get_pending_reactions(clear=True)
    }
    assert fight_names == {"TALON STRIKE"}

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    sm_player.stratagems.get_pending_reactions(clear=True)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    end_fight_names = {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in sm_player.stratagems.get_pending_reactions(clear=True)
    }
    assert end_fight_names == {"RAPID REAPPRAISAL"}


def test_hunters_trail_applies_sticky_objective_control():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    ravenwing = _make_unit(
        "Ravenwing Outriders",
        keywords=["MOUNTED", "RAVENWING"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    objective = _make_objective("Home Objective", 10.0, 10.0)
    objective.location.controlling_player = sm_player

    sm_army.add_unit(ravenwing)
    _deploy_unit(game, ravenwing, 10.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "HUNTERS' TRAIL") is not None

    ok = sm_player.stratagems.use("HUNTERS' TRAIL", unit=ravenwing, objective=objective, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert objective.location.sticky_controller is sm_player
    assert objective.location.controlling_player is sm_player


def test_hunters_trail_rejects_non_ravenwing_mounted_unit():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    ravenwing = _make_unit(
        "Ravenwing Outriders",
        keywords=["MOUNTED", "RAVENWING"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    objective = _make_objective("Home Objective", 10.0, 10.0)
    objective.location.controlling_player = sm_player

    sm_army.add_unit(ravenwing)
    sm_army.add_unit(intercessors)
    _deploy_unit(game, ravenwing, 10.0, 10.0)
    _deploy_unit(game, intercessors, 10.0, 14.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "HUNTERS' TRAIL") is not None

    ok = sm_player.stratagems.use("HUNTERS' TRAIL", unit=intercessors, objective=objective, dequeue=True)
    assert ok is False
    assert int(sm_player.command_points or 0) == 10


def test_death_on_the_wind_forces_battleshock_with_ravenwing_modifier():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Ravenwing Bike Squad",
        keywords=["MOUNTED", "RAVENWING"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    nearby_ravenwing = _make_unit(
        "Ravenwing Knights",
        keywords=["MOUNTED", "RAVENWING"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(shooter)
    sm_army.add_unit(nearby_ravenwing)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, nearby_ravenwing, 15.0, 10.0)
    _deploy_unit(game, enemy, 19.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    sm_player.stratagems.get_pending_reactions(clear=True)
    shooter.round_state.shot_this_round = True
    game.event_system.publish("unit_shooting_resolved", attacker_unit=shooter, hits_by_target={enemy: 1})
    assert _pending_by_name(sm_player.stratagems, "DEATH ON THE WIND") is not None

    calls: list[tuple[int, int, str]] = []

    def _record_force_battleshock(current_turn, modifier=0, source=""):
        calls.append((int(current_turn), int(modifier), str(source)))

    enemy.force_battle_shock_test = _record_force_battleshock

    ok = sm_player.stratagems.use(
        "DEATH ON THE WIND",
        unit=shooter,
        enemy_unit=enemy,
        hits_by_target={enemy: 1},
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert len(calls) == 1
    assert calls[0][0] == 1
    assert calls[0][1] == -1
    assert "DEATH ON THE WIND" in calls[0][2].upper()


def test_death_on_the_wind_rejects_enemy_unit_that_was_not_hit():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Ravenwing Bike Squad",
        keywords=["MOUNTED", "RAVENWING"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    hit_enemy = _make_unit(
        "Enemy Infantry Alpha",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    missed_enemy = _make_unit(
        "Enemy Infantry Beta",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(shooter)
    enemy_army.add_unit(hit_enemy)
    enemy_army.add_unit(missed_enemy)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, hit_enemy, 18.0, 10.0)
    _deploy_unit(game, missed_enemy, 24.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    sm_player.stratagems.get_pending_reactions(clear=True)
    shooter.round_state.shot_this_round = True
    game.event_system.publish("unit_shooting_resolved", attacker_unit=shooter, hits_by_target={hit_enemy: 1})
    assert _pending_by_name(sm_player.stratagems, "DEATH ON THE WIND") is not None

    ok = sm_player.stratagems.use(
        "DEATH ON THE WIND",
        unit=shooter,
        enemy_unit=missed_enemy,
        hits_by_target={hit_enemy: 1},
        dequeue=True,
    )
    assert ok is False
    assert int(sm_player.command_points or 0) == 10


def test_talon_strike_applies_wound_bonus_and_cleans_up_at_phase_end():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    ravenwing = _make_unit(
        "Ravenwing Outriders",
        keywords=["MOUNTED", "RAVENWING"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy_character = _make_unit(
        "Enemy Commander",
        faction_name="Enemy",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(ravenwing)
    enemy_army.add_unit(enemy_character)
    _deploy_unit(game, ravenwing, 10.0, 10.0)
    _deploy_unit(game, enemy_character, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "TALON STRIKE") is not None

    ok = sm_player.stratagems.use("TALON STRIKE", unit=ravenwing, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    profile = _make_profile(is_melee=False, strength="4")
    wound_result = profile._wound_target_with_tracking(
        enemy_character,
        ravenwing.models[0],
        {"distance_to_target": 8.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("TALON STRIKE" in str(modifier).upper() for modifier in list(wound_result.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    after_cleanup = profile._wound_target_with_tracking(
        enemy_character,
        ravenwing.models[0],
        {"distance_to_target": 8.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("TALON STRIKE" in str(modifier).upper() for modifier in list(after_cleanup.get("modifiers", []) or []))


def test_talon_strike_rejects_unit_already_selected_to_shoot():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    ravenwing = _make_unit(
        "Ravenwing Outriders",
        keywords=["MOUNTED", "RAVENWING"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )

    sm_army.add_unit(ravenwing)
    _deploy_unit(game, ravenwing, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ravenwing.round_state.shot_this_round = True

    ok = sm_player.stratagems.use("TALON STRIKE", unit=ravenwing, phase_name="Shooting phase")
    assert ok is False
    assert int(sm_player.command_points or 0) == 10


def test_rapid_reappraisal_enters_strategic_reserves():
    game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
    ravenwing = _make_unit(
        "Ravenwing Black Knights",
        keywords=["MOUNTED", "RAVENWING"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )

    sm_army.add_unit(ravenwing)
    _deploy_unit(game, ravenwing, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert _pending_by_name(sm_player.stratagems, "RAPID REAPPRAISAL") is not None

    ok = sm_player.stratagems.use("RAPID REAPPRAISAL", unit=ravenwing, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert str(getattr(ravenwing, "reserve_status", "") or "") == "strategic_reserves"
    assert ravenwing not in list(getattr(game.map, "units", []) or [])


def test_rapid_reappraisal_rejects_engaged_unit():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    ravenwing = _make_unit(
        "Ravenwing Black Knights",
        keywords=["MOUNTED", "RAVENWING"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(ravenwing)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, ravenwing, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.map.is_within_engagement_range = lambda first, second: {first, second} == {ravenwing, enemy}
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = sm_player.stratagems.use("RAPID REAPPRAISAL", unit=ravenwing, phase_name="Fight phase")
    assert ok is False
    assert int(sm_player.command_points or 0) == 10
