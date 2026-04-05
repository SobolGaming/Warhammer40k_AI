from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

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
        toughness: int = 4,
        move: int = 6,
        wounds: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
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
    toughness: int = 4,
    move: int = 6,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            move=move,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "Lion's Blade Task Force")
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
        model.set_location(float(x) + float(index), float(y), 0.0, 0.0)
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


def _make_profile(*, is_melee: bool, strength: str = "4", skill: str = "3+") -> WargearProfile:
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
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_lions_blade_task_force_stratagem_descriptors_registered():
    expected = {
        "000009734006": ("Illuminating Fire", "mark_enemy_for_deathwing_wound_bonus"),
        "000009734007": ("Inescapable Wrath", "out_of_turn_charge"),
        "000009734005": ("Knights of Iron", "move_through_terrain"),
        "000009734002": ("Overpowering Exaction", "force_battleshock_test_with_conditional_deathwing_or_ravenwing_modifier"),
        "000009734004": ("Strength in Unity", "enemy_melee_hit_and_conditional_wound_penalty"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_lions_blade_phase_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    ravenwing = _make_unit(
        "Ravenwing Knights",
        keywords=["RAVENWING", "MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    deathwing = _make_unit(
        "Deathwing Knights",
        keywords=["DEATHWING", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(ravenwing)
    sm_army.add_unit(deathwing)
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, ravenwing, 20.0, 20.0)
    _deploy_unit(game, deathwing, 40.0, 10.0)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 54.0, 10.0)
    game.rebuild_entity_registry()

    intercessors.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(10.5, 10.0, 0.0, 0.0)
    ravenwing.models[0].set_location(11.0, 10.0, 0.0, 0.0)
    deathwing.models[0].set_location(40.0, 10.0, 0.0, 0.0)

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "OVERPOWERING EXACTION") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "KNIGHTS OF IRON") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    ravenwing.models[0].set_location(20.0, 20.0, 0.0, 0.0)
    enemy.models[0].set_location(28.0, 20.0, 0.0, 0.0)
    game.event_system.publish("shooting_targets_selected", attacking_unit=ravenwing, target_units=[enemy])
    assert _pending_by_name(sm_player.stratagems, "ILLUMINATING FIRE") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ravenwing.models[0].set_location(11.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(10.5, 10.0, 0.0, 0.0)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[intercessors])
    assert _pending_by_name(sm_player.stratagems, "STRENGTH IN UNITY") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    deathwing.models[0].set_location(40.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(45.0, 10.0, 0.0, 0.0)
    deathwing.can_declare_charge_against = lambda enemy_unit, game_obj, out_of_turn=False: True
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    assert _pending_by_name(sm_player.stratagems, "INESCAPABLE WRATH") is not None


def test_illuminating_fire_applies_deathwing_wound_bonus_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    ravenwing = _make_unit(
        "Ravenwing Knights",
        keywords=["RAVENWING", "MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    deathwing = _make_unit(
        "Deathwing Terminators",
        keywords=["DEATHWING", "INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(ravenwing)
    sm_army.add_unit(deathwing)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, ravenwing, 10.0, 10.0)
    _deploy_unit(game, deathwing, 5.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    game.event_system.publish("shooting_targets_selected", attacking_unit=ravenwing, target_units=[enemy])
    assert _pending_by_name(sm_player.stratagems, "ILLUMINATING FIRE") is not None

    ok = sm_player.stratagems.use(
        "ILLUMINATING FIRE",
        unit=ravenwing,
        enemy_unit=enemy,
        target_units=[enemy],
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    profile = _make_profile(is_melee=False, strength="4")
    wound_result = profile._wound_target_with_tracking(
        enemy,
        deathwing.models[0],
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("ILLUMINATING FIRE" in str(modifier).upper() for modifier in list(wound_result.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    wound_after = profile._wound_target_with_tracking(
        enemy,
        deathwing.models[0],
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("ILLUMINATING FIRE" in str(modifier).upper() for modifier in list(wound_after.get("modifiers", []) or []))


def test_knights_of_iron_applies_phase_move_through_terrain_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    ravenwing = _make_unit(
        "Ravenwing Black Knights",
        keywords=["RAVENWING", "MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    sm_army.add_unit(ravenwing)
    _deploy_unit(game, ravenwing, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    ok = sm_player.stratagems.use("KNIGHTS OF IRON", unit=ravenwing, dequeue=False)
    assert ok
    sr = dict(getattr(ravenwing, "special_rules", {}) or {})
    assert sorted(list(sr.get("bearer_unit_phase_move_terrain_only_types", []) or [])) == ["advance", "move"]
    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    sr = dict(getattr(ravenwing, "special_rules", {}) or {})
    assert not list(sr.get("bearer_unit_phase_move_terrain_only_types", []) or [])

    _set_phase(game, sm_player, "CHARGE_PHASE", 0)
    ok = sm_player.stratagems.use("KNIGHTS OF IRON", unit=ravenwing, dequeue=False)
    assert ok
    sr = dict(getattr(ravenwing, "special_rules", {}) or {})
    assert list(sr.get("bearer_unit_phase_move_terrain_only_types", []) or []) == ["charge"]


def test_overpowering_exaction_forces_battleshock_with_ravenwing_modifier():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    ravenwing = _make_unit(
        "Ravenwing Bike Squad",
        keywords=["RAVENWING", "MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
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
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    ravenwing.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(10.5, 10.0, 0.0, 0.0)

    called = {}

    def _record(current_turn, *, modifier=0, source=None):
        called["turn"] = int(current_turn)
        called["modifier"] = int(modifier)
        called["source"] = str(source or "")
        return True

    enemy.force_battle_shock_test = _record

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert _pending_by_name(sm_player.stratagems, "OVERPOWERING EXACTION") is not None

    ok = sm_player.stratagems.use("OVERPOWERING EXACTION", unit=ravenwing, enemy_unit=enemy, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert called == {"turn": 1, "modifier": -1, "source": "OVERPOWERING EXACTION"}


def test_strength_in_unity_applies_hit_and_wound_penalties_and_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    target = _make_unit(
        "Intercessor Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        toughness=4,
    )
    ravenwing = _make_unit(
        "Ravenwing Knights",
        keywords=["RAVENWING", "MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    deathwing = _make_unit(
        "Deathwing Knights",
        keywords=["DEATHWING", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        toughness=5,
    )
    enemy = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=4,
    )

    sm_army.add_unit(target)
    sm_army.add_unit(ravenwing)
    sm_army.add_unit(deathwing)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, ravenwing, 30.0, 10.0)
    _deploy_unit(game, deathwing, 40.0, 10.0)
    _deploy_unit(game, enemy, 52.0, 10.0)
    game.rebuild_entity_registry()

    target.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    ravenwing.models[0].set_location(11.0, 10.0, 0.0, 0.0)
    deathwing.models[0].set_location(9.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(10.5, 10.0, 0.0, 0.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[target])
    assert _pending_by_name(sm_player.stratagems, "STRENGTH IN UNITY") is not None

    ok = sm_player.stratagems.use(
        "STRENGTH IN UNITY",
        unit=target,
        attacking_unit=enemy,
        target_units=[target],
        dequeue=True,
    )
    assert ok
    assert int(sm_player.command_points or 0) == 9

    profile = _make_profile(is_melee=True, strength="6", skill="3+")
    hit_result = profile._hit_target_with_tracking(
        target,
        enemy.models[0],
        {"distance_to_target": 0.5},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("STRENGTH IN UNITY" in str(modifier).upper() for modifier in list(hit_result.get("modifiers", []) or []))

    wound_result = profile._wound_target_with_tracking(
        target,
        enemy.models[0],
        {"distance_to_target": 0.5},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("STRENGTH IN UNITY" in str(modifier).upper() for modifier in list(wound_result.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    hit_after = profile._hit_target_with_tracking(
        target,
        enemy.models[0],
        {"distance_to_target": 0.5},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    wound_after = profile._wound_target_with_tracking(
        target,
        enemy.models[0],
        {"distance_to_target": 0.5},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("STRENGTH IN UNITY" in str(modifier).upper() for modifier in list(hit_after.get("modifiers", []) or []))
    assert not any("STRENGTH IN UNITY" in str(modifier).upper() for modifier in list(wound_after.get("modifiers", []) or []))


def test_inescapable_wrath_queues_and_attempts_out_of_turn_charge():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    deathwing = _make_unit(
        "Deathwing Knights",
        keywords=["DEATHWING", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Chargers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(deathwing)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, deathwing, 10.0, 10.0)
    _deploy_unit(game, enemy, 15.0, 10.0)
    game.rebuild_entity_registry()

    deathwing.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(15.0, 10.0, 0.0, 0.0)
    deathwing.can_declare_charge_against = lambda enemy_unit, game_obj, out_of_turn=False: True

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="CHARGE_PHASE"))
    assert _pending_by_name(sm_player.stratagems, "INESCAPABLE WRATH") is not None

    with patch.object(game, "attempt_charge", return_value=True) as mock_charge:
        ok = sm_player.stratagems.use(
            "INESCAPABLE WRATH",
            unit=deathwing,
            enemy_unit=enemy,
            dequeue=True,
        )
    assert ok
    assert int(sm_player.command_points or 0) == 8
    mock_charge.assert_called_once_with(deathwing, enemy, out_of_turn=True)
