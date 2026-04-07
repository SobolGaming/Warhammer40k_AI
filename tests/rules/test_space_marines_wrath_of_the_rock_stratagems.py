from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


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

    sm_army = Army.with_detachment("Space Marines", "Wrath of the Rock")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
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


def _first_profile(wargear: Wargear):
    return next(iter(dict(getattr(wargear, "profiles", {}) or {}).values()))


def test_wrath_of_the_rock_stratagem_descriptors_registered():
    expected = {
        "000010161002": ("Inescapable Justice", "reassign_oath_of_moment_target_from_visible_character"),
        "000010161003": ("Lion's Will", "objective_control_until_next_command_phase_and_conditional_hit_bonus_until_end_of_turn"),
        "000010161005": ("Tactical Mastery", "shoot_and_charge_after_advance_with_ravenwing_fallback_extension"),
        "000010161006": ("Relics of the Dark Age", "ranged_weapons_gain_plus_two_strength"),
        "000010161007": ("Leonine Aggression", "out_of_turn_charge"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_wrath_of_the_rock_phase_and_destroyed_unit_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    outriders = _make_unit(
        "Outriders",
        keywords=["RAVENWING", "MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    chaplain = _make_unit(
        "Chaplain",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    deathwing = _make_unit(
        "Deathwing Knights",
        keywords=["DEATHWING", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    oath_target = _make_unit(
        "Enemy Oath Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    visible_enemy = _make_unit(
        "Enemy Visible",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    charge_enemy = _make_unit(
        "Enemy Charger",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    for unit in (intercessors, outriders, chaplain, deathwing):
        sm_army.add_unit(unit)
    for unit in (oath_target, visible_enemy, charge_enemy):
        enemy_army.add_unit(unit)

    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, outriders, 20.0, 10.0)
    _deploy_unit(game, chaplain, 30.0, 10.0)
    _deploy_unit(game, deathwing, 40.0, 10.0)
    _deploy_unit(game, oath_target, 12.0, 10.0)
    _deploy_unit(game, visible_enemy, 35.0, 10.0)
    _deploy_unit(game, charge_enemy, 45.0, 10.0)
    game.rebuild_entity_registry()

    sm_army.oath_of_moment.set_target(oath_target, game=game, player=sm_player, source="test", queue_followups=False)
    deathwing.can_declare_charge_against = lambda target, _game, out_of_turn=False: bool(out_of_turn) and target is charge_enemy

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"LION'S WILL"}

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"TACTICAL MASTERY"}

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"RELICS OF THE DARK AGE"}

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("unit_destroyed", unit=oath_target, destroyed_by_unit=visible_enemy)
    assert _pending_by_name(sm_player.stratagems, "INESCAPABLE JUSTICE") is not None
    sm_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert _pending_by_name(sm_player.stratagems, "LEONINE AGGRESSION") is not None


def test_lions_will_applies_objective_control_and_hit_bonus_until_expiry():
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
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    bolt_rifle = _ranged_wargear()
    intercessors.models[0].wargear.append(bolt_rifle)
    profile = _first_profile(bolt_rifle)

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    assert sm_player.stratagems.use("LION'S WILL", unit=intercessors, dequeue=True)

    model = intercessors.models[0]
    assert intercessors.get_effective_model_characteristic(model, "objective_control") == 2

    preview = profile._hit_target_with_tracking(enemy, model, {}, preview_modifiers=True)
    assert sum(int(value) for value, _reasons in list(preview.get("hit_mods", []) or [])) == 1

    game.turn = 2
    game.current_player_index = 0
    game.phase = SimpleNamespace(name="COMMAND_PHASE")
    assert intercessors.get_effective_model_characteristic(model, "objective_control") == 1


def test_tactical_mastery_enables_advance_actions_and_ravenwing_fall_back_actions():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    outriders = _make_unit(
        "Outriders",
        keywords=["RAVENWING", "MOUNTED"],
        faction_keywords=["ADEPTUS ASTARTES"],
        move=12,
    )
    sm_army.add_unit(intercessors)
    sm_army.add_unit(outriders)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    _deploy_unit(game, outriders, 20.0, 10.0)
    game.rebuild_entity_registry()

    bolt_rifle = _ranged_wargear()
    outrider_gun = _ranged_wargear("Twin Bolt Rifle")
    intercessors.models[0].wargear.append(bolt_rifle)
    outriders.models[0].wargear.append(outrider_gun)
    bolt_profile = _first_profile(bolt_rifle)
    outrider_profile = _first_profile(outrider_gun)

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    assert sm_player.stratagems.use("TACTICAL MASTERY", unit=intercessors, dequeue=True)
    intercessors.round_state.advanced_this_round = True
    assert intercessors.can_shoot_after_advance(bolt_profile)
    assert intercessors.can_charge_after_advance()
    intercessors.round_state.advanced_this_round = False
    intercessors.round_state.fell_back_this_round = True
    assert not intercessors.can_shoot_after_fall_back(bolt_profile)
    assert not intercessors.can_charge_after_fall_back()

    _set_phase(game, _enemy_player, "MOVEMENT_PHASE", 1)
    game.turn = 2
    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    assert sm_player.stratagems.use("TACTICAL MASTERY", unit=outriders, dequeue=True)
    outriders.round_state.fell_back_this_round = True
    assert outriders.can_shoot_after_fall_back(outrider_profile)
    assert outriders.can_charge_after_fall_back()


def test_relics_of_the_dark_age_adds_temporary_ranged_strength_bonus():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(intercessors)
    _deploy_unit(game, intercessors, 10.0, 10.0)
    game.rebuild_entity_registry()

    bolt_rifle = _ranged_wargear()
    intercessors.models[0].wargear.append(bolt_rifle)
    profile = _first_profile(bolt_rifle)

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    assert sm_player.stratagems.use("RELICS OF THE DARK AGE", unit=intercessors, dequeue=True)

    bonus, reasons = intercessors.models[0].get_temporary_weapon_strength_bonus("Bolt Rifle")
    assert bonus == 2
    assert any("relics of the dark age" in str(reason).lower() for reason in reasons)

    enemy = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_army = game.players[1].army
    enemy_army.add_unit(enemy)
    _deploy_unit(game, enemy, 20.0, 10.0)
    wound_preview = profile._wound_target_with_tracking(enemy, intercessors.models[0], {}, roll_value=4, allow_rerolls=False)
    assert any("relics of the dark age" in str(reason).lower() for reason in list(wound_preview.get("modifiers", []) or []))


def test_inescapable_justice_reassigns_oath_target():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    chaplain = _make_unit(
        "Chaplain",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    oath_target = _make_unit(
        "Enemy Oath Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    new_target = _make_unit(
        "Enemy New Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(chaplain)
    enemy_army.add_unit(oath_target)
    enemy_army.add_unit(new_target)
    _deploy_unit(game, chaplain, 10.0, 10.0)
    _deploy_unit(game, oath_target, 12.0, 10.0)
    _deploy_unit(game, new_target, 18.0, 13.0)
    game.rebuild_entity_registry()

    sm_army.oath_of_moment.set_target(oath_target, game=game, player=sm_player, source="test", queue_followups=False)
    assert sm_army.oath_of_moment.is_oath_target(oath_target)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("unit_destroyed", unit=oath_target, destroyed_by_unit=new_target)
    assert _pending_by_name(sm_player.stratagems, "INESCAPABLE JUSTICE") is not None

    assert sm_player.stratagems.use(
        "INESCAPABLE JUSTICE",
        unit=chaplain,
        enemy_unit=new_target,
        dequeue=True,
        phase_name="Shooting phase",
    )
    assert sm_army.oath_of_moment.is_oath_target(new_target)
    assert not sm_army.oath_of_moment.is_oath_target(oath_target)


def test_leonine_aggression_attempts_out_of_turn_charge():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    deathwing = _make_unit(
        "Deathwing Knights",
        keywords=["DEATHWING", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(deathwing)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, deathwing, 10.0, 10.0)
    _deploy_unit(game, enemy, 15.0, 10.0)
    game.rebuild_entity_registry()

    deathwing.can_declare_charge_against = lambda target, _game, out_of_turn=False: bool(out_of_turn) and target is enemy
    game.attempt_charge = Mock(return_value=True)

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert _pending_by_name(sm_player.stratagems, "LEONINE AGGRESSION") is not None

    assert sm_player.stratagems.use(
        "LEONINE AGGRESSION",
        unit=deathwing,
        enemy_unit=enemy,
        dequeue=True,
        phase_name="Charge phase",
    )
    game.attempt_charge.assert_called_once_with(deathwing, enemy, out_of_turn=True)
