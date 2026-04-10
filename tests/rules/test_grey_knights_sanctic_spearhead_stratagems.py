from __future__ import annotations

from types import SimpleNamespace

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
        faction_name: str = "Grey Knights",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        move: int = 6,
        toughness: int = 4,
        save: int = 3,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["GREY KNIGHTS"] if faction_name == "Grey Knights" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "60mm" if "VEHICLE" in list(keywords or []) else "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
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
    faction_name: str = "Grey Knights",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    move: int = 6,
    toughness: int = 4,
    save: int = 3,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            move=move,
            toughness=toughness,
            save=save,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _ranged_wargear(name: str = "Storm Bolter", *, strength: str = "4", damage: str = "1") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        }
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    army_gk = Army.with_detachment("Grey Knights", "Sanctic Spearhead")
    army_gk.faction_id = "GK"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("GK", control=PlayerControl.LOCAL, army=army_gk)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 10
    p2.command_points = 10
    army_gk.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, army_gk, army_enemy


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


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


def _pending_names(stratagems, *, clear: bool = False) -> set[str]:
    return {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in list(stratagems.get_pending_reactions(clear=clear) or [])
    }


def test_sanctic_spearhead_stratagem_descriptors_registered():
    expected = {
        "000010361002": ("Truesilver Will", "fnp_vs_mortal_wounds"),
        "000010361003": ("Abominus-class Targets", "conditional_wound_bonus_vs_monster_or_vehicle"),
        "000010361004": ("Armoured Aegis", "heal_model_in_unit"),
        "000010361005": ("Redoubled Assault", "shoot_and_charge_after_fall_back"),
        "000010361006": ("Force Wave", "move_through_terrain"),
        "000010361007": ("Argent Wrath", "charge_end_force_battle_shock"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_sanctic_phase_start_reactions_queue_expected_stratagems():
    game, p1, p2, army_gk, _army_enemy = _build_game()
    vehicle = _make_unit(
        "Nemesis Dreadknight",
        keywords=["VEHICLE", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        wounds=12,
        toughness=8,
        save=2,
    )
    infantry = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
    )
    vehicle.models[0].wounds = 9
    army_gk.add_unit(vehicle)
    army_gk.add_unit(infantry)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _deploy_unit(game, infantry, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "COMMAND_PHASE", 0)
    assert _pending_names(p1.stratagems, clear=True) == {"ARMOURED AEGIS"}

    _set_phase(game, p1, "MOVEMENT_PHASE", 0)
    assert _pending_names(p1.stratagems, clear=True) == {"FORCE WAVE"}

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    assert _pending_names(p1.stratagems, clear=True) == {"ABOMINUS-CLASS TARGETS"}

    _set_phase(game, p1, "CHARGE_PHASE", 0)
    assert _pending_names(p1.stratagems, clear=True) == {"FORCE WAVE"}

    _set_phase(game, p2, "FIGHT_PHASE", 1)
    assert _pending_names(p1.stratagems, clear=True) == {"ABOMINUS-CLASS TARGETS"}


def test_truesilver_will_queues_on_mortal_wound_and_applies_fnp_vs_mortal():
    game, p1, p2, army_gk, army_enemy = _build_game()
    target = _make_unit(
        "Nemesis Dreadknight",
        keywords=["VEHICLE", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        wounds=12,
        toughness=8,
        save=2,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_gk.add_unit(target)
    army_enemy.add_unit(attacker)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "mortal_wound_allocated",
        attacker_unit=attacker,
        target_unit=target,
        target_model=target.models[0],
        phase_name="Shooting phase",
    )
    assert _pending_by_name(p1.stratagems, "TRUESILVER WILL") is not None

    ok = p1.stratagems.use(
        "TRUESILVER WILL",
        unit=target,
        phase_name="Shooting phase",
        dequeue=True,
    )

    assert ok
    fnp_entries = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
    assert any(int(value) == 4 and "mortal" in str(condition or "").lower() for value, condition in fnp_entries)

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    fnp_after = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
    assert not any(int(value) == 4 and "mortal" in str(condition or "").lower() for value, condition in fnp_after)


def test_abominus_class_targets_grants_wound_bonus_only_vs_monster_vehicle_until_phase_end():
    game, p1, _p2, army_gk, army_enemy = _build_game()
    shooter = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
    )
    shooter.models[0].wargear = [_ranged_wargear("Storm Bolter", strength="4")]
    vehicle_target = _make_unit(
        "Enemy Tank",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        toughness=5,
        wounds=10,
    )
    infantry_target = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=5,
        wounds=5,
    )
    army_gk.add_unit(shooter)
    army_enemy.add_unit(vehicle_target)
    army_enemy.add_unit(infantry_target)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, vehicle_target, 18.0, 10.0)
    _deploy_unit(game, infantry_target, 22.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    assert _pending_by_name(p1.stratagems, "ABOMINUS-CLASS TARGETS") is not None

    ok = p1.stratagems.use(
        "ABOMINUS-CLASS TARGETS",
        unit=shooter,
        phase_name="Shooting phase",
        dequeue=True,
    )

    assert ok
    vehicle_bonus, vehicle_reasons = shooter.models[0].get_temporary_weapon_wound_bonus("Storm Bolter", target=vehicle_target)
    infantry_bonus, _infantry_reasons = shooter.models[0].get_temporary_weapon_wound_bonus("Storm Bolter", target=infantry_target)
    assert int(vehicle_bonus or 0) == 1
    assert any("ABOMINUS-CLASS TARGETS" in str(reason).upper() for reason in list(vehicle_reasons or []))
    assert int(infantry_bonus or 0) == 0

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    bonus_after, _reasons_after = shooter.models[0].get_temporary_weapon_wound_bonus("Storm Bolter", target=vehicle_target)
    assert int(bonus_after or 0) == 0


def test_armoured_aegis_heals_up_to_three_lost_wounds():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    vehicle = _make_unit(
        "Nemesis Dreadknight",
        keywords=["VEHICLE", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        wounds=12,
        toughness=8,
        save=2,
    )
    vehicle.models[0].wounds = 8
    army_gk.add_unit(vehicle)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "COMMAND_PHASE", 0)
    assert _pending_by_name(p1.stratagems, "ARMOURED AEGIS") is not None

    ok = p1.stratagems.use(
        "ARMOURED AEGIS",
        unit=vehicle,
        phase_name="Command phase",
        dequeue=True,
    )

    assert ok
    assert int(vehicle.models[0].wounds or 0) == 11


def test_redoubled_assault_queues_after_fall_back_and_enables_shoot_and_charge_until_turn_end():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    vehicle = _make_unit(
        "Grey Knights Walker",
        keywords=["VEHICLE"],
        faction_keywords=["GREY KNIGHTS"],
        wounds=10,
        toughness=8,
        save=2,
    )
    army_gk.add_unit(vehicle)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    game.rebuild_entity_registry()
    vehicle.round_state.fell_back_this_round = True

    _set_phase(game, p1, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=vehicle, action="fall_back")
    assert _pending_by_name(p1.stratagems, "REDOUBLED ASSAULT") is not None
    assert vehicle.has_fell_back_and_shoot() is False
    assert vehicle.can_charge_after_fall_back() is False

    ok = p1.stratagems.use(
        "REDOUBLED ASSAULT",
        unit=vehicle,
        phase_name="Movement phase",
        dequeue=True,
    )

    assert ok
    assert vehicle.has_fell_back_and_shoot() is True
    assert vehicle.can_charge_after_fall_back() is True

    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    game.current_player_index = 0
    game.event_system.publish("phase_end", player=p1, phase=game.phase)
    assert vehicle.has_fell_back_and_shoot() is False
    assert vehicle.can_charge_after_fall_back() is False


def test_force_wave_grants_phase_move_through_terrain_and_cleans_up():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    vehicle = _make_unit(
        "Grey Knights Transport",
        keywords=["VEHICLE"],
        faction_keywords=["GREY KNIGHTS"],
        wounds=10,
        toughness=8,
        save=2,
    )
    army_gk.add_unit(vehicle)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "MOVEMENT_PHASE", 0)
    assert _pending_by_name(p1.stratagems, "FORCE WAVE") is not None

    ok = p1.stratagems.use(
        "FORCE WAVE",
        unit=vehicle,
        phase_name="Movement phase",
        dequeue=True,
    )

    assert ok
    rules = dict(getattr(vehicle, "special_rules", {}) or {})
    assert set(rules.get("bearer_unit_phase_move_terrain_only_types") or []) == {"advance", "move"}

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    rules_after = dict(getattr(vehicle, "special_rules", {}) or {})
    assert list(rules_after.get("bearer_unit_phase_move_terrain_only_types") or []) == []


def test_argent_wrath_queues_after_charge_and_forces_nearby_enemy_battleshock_at_minus_one():
    game, p1, _p2, army_gk, army_enemy = _build_game()
    vehicle = _make_unit(
        "Grey Knights Dreadnought",
        keywords=["VEHICLE"],
        faction_keywords=["GREY KNIGHTS"],
        wounds=10,
        toughness=8,
        save=2,
    )
    enemy_a = _make_unit(
        "Enemy A",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_b = _make_unit(
        "Enemy B",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_far = _make_unit(
        "Enemy Far",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_gk.add_unit(vehicle)
    army_enemy.add_unit(enemy_a)
    army_enemy.add_unit(enemy_b)
    army_enemy.add_unit(enemy_far)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _deploy_unit(game, enemy_a, 13.0, 10.0)
    _deploy_unit(game, enemy_b, 14.5, 10.0)
    _deploy_unit(game, enemy_far, 20.0, 10.0)
    game.rebuild_entity_registry()

    calls: list[tuple[str, int, int, str]] = []
    enemy_a.force_battle_shock_test = lambda turn, modifier=0, source="": calls.append(("Enemy A", int(turn), int(modifier), str(source)))
    enemy_b.force_battle_shock_test = lambda turn, modifier=0, source="": calls.append(("Enemy B", int(turn), int(modifier), str(source)))
    enemy_far.force_battle_shock_test = lambda turn, modifier=0, source="": calls.append(("Enemy Far", int(turn), int(modifier), str(source)))

    _set_phase(game, p1, "CHARGE_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=vehicle, action="charge")
    assert _pending_by_name(p1.stratagems, "ARGENT WRATH") is not None

    ok = p1.stratagems.use(
        "ARGENT WRATH",
        unit=vehicle,
        phase_name="Charge phase",
        dequeue=True,
    )

    assert ok
    assert ("Enemy A", 2, -1, "ARGENT WRATH") in calls
    assert ("Enemy B", 2, -1, "ARGENT WRATH") in calls
    assert not any(name == "Enemy Far" for name, _turn, _modifier, _source in calls)
