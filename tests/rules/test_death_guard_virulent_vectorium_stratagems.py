from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        movement: str = "5",
        toughness: str = "5",
        wounds: str = "4",
        abilities=None,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Death Guard" if "DEATH GUARD" in {str(k).upper() for k in (faction_keywords or [])} else "Enemy"}
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
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        for ability in list(abilities or []):
            if isinstance(ability, dict):
                self.datasheets_abilities.append(ability)
            else:
                text = str(ability)
                self.datasheets_abilities.append(
                    {
                        "name": text,
                        "description": text,
                        "type": "",
                        "parameter": "",
                    }
                )
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None, wounds: str = "4", abilities=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            abilities=abilities,
        )
    )


def _build_game():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    dg_army = Army.with_detachment("Death Guard", "Virulent Vectorium")
    dg_army.faction_id = "DG"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)

    dg_player.command_points = 10
    enemy_player.command_points = 10
    dg_army.configure_rule_managers(force=True)
    dg_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, dg_player, enemy_player, dg_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _set_phase(game: Game, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)


def _make_ranged_d6_profile() -> WargearProfile:
    parent = SimpleNamespace(
        name="Blight Bolter",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "24",
            "A": "D6",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _blank_attack_result(attacker_name: str, target_name: str) -> AttackResult:
    return AttackResult(
        weapon_name="Blight Bolter",
        attacker_name=str(attacker_name),
        target_unit_name=str(target_name),
        attacks_rolled=0,
        attacks_dice_expression="D6",
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


def test_plaguesurge_extends_contagion_range_until_next_command_phase():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    warlord = _make_unit(
        "Lord of Contagion",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(warlord)
    dg_army.warlord = warlord
    _deploy_unit(game, warlord, 10.0, 10.0)

    game.turn = 1
    _set_phase(game, "COMMAND_PHASE", 0)
    assert dg_player.stratagems.use("PLAGUESURGE", unit=warlord, phase_name="Command phase")
    assert float(dg_army.nurgles_gift.get_contagion_range(1)) == 6.0

    game.turn = 2
    _set_phase(game, "COMMAND_PHASE", 0)
    game.event_system.publish("phase_start", player=dg_player, phase=SimpleNamespace(name="COMMAND_PHASE"))
    assert float(dg_army.nurgles_gift.get_contagion_range(2)) == 6.0


def test_leechspore_eruption_deals_mortals_and_heals():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    source = _make_unit(
        "Plague Marine",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
        wounds="4",
    )
    enemy = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
    )
    dg_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)

    source_model = source.models[0]
    enemy_model = enemy.models[0]
    source_model.wounds = 1

    game.turn = 1
    _set_phase(game, "COMMAND_PHASE", 0)
    with patch("warhammer40k_ai.rules.stratagems.dice_module.get_roll", side_effect=[5, 5, 2]):
        ok = dg_player.stratagems.use(
            "LEECHSPORE ERUPTION",
            model=source_model,
            enemy_unit=enemy,
            phase_name="Command phase",
        )
    assert ok
    assert int(source_model.wounds) == 3
    assert int(enemy_model.wounds) == 2


def test_overwhelming_generosity_marks_enemy_and_rerolls_attack_count():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    source = _make_unit(
        "Lord of Virulence",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["DEATH GUARD"],
    )
    attacker = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    enemy = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(source)
    dg_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, attacker, 11.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)

    source._attacking_unit_has_any_los_to_target_unit = lambda _target, _game_map: True

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use(
        "OVERWHELMING GENEROSITY",
        unit=source,
        enemy_unit=enemy,
        phase_name="Shooting phase",
    )
    assert bool(enemy.special_rules.get("overwhelming_generosity_active"))

    profile = _make_ranged_d6_profile()
    attack_result = _blank_attack_result(attacker.name, enemy.name)
    with patch.object(profile.attacks, "resolve_detailed", side_effect=[(1, [1]), (5, [5])]):
        info = profile._resolve_attack_count(enemy, attacker.models[0], attack_result, publish_roll_event=False)

    assert int(info.num_attacks) == 5
    assert any("OVERWHELMING GENEROSITY" in str(reason or "").upper() for reason in list(info.special_modifiers or []))


def test_creeping_blight_grants_ranged_hit_and_wound_rerolls_vs_afflicted():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    target = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(shooter)
    enemy_army.add_unit(target)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, target, 16.0, 10.0)

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    assert dg_player.stratagems.use("CREEPING BLIGHT", unit=shooter, phase_name="Shooting phase")

    target.special_rules["post_shoot_afflicted_active"] = True
    target.special_rules["post_shoot_afflicted_owner"] = str(dg_player.id)
    target.special_rules["post_shoot_afflicted_turn"] = int(game.turn)
    target.special_rules["post_shoot_afflicted_source"] = "Putrid Detonation"

    hit_mods = shooter.get_unit_hit_reroll_modifiers("ranged", target=target, attacker_model=shooter.models[0])
    wound_mods = shooter.get_unit_wound_reroll_modifiers("ranged", target=target)
    assert bool(hit_mods.get("reroll_hit_full"))
    assert bool(wound_mods.get("reroll_wound_full"))
    assert any("CREEPING BLIGHT" in str(reason or "").upper() for reason in list(hit_mods.get("reroll_hit_full_reasons") or []))
    assert any("CREEPING BLIGHT" in str(reason or "").upper() for reason in list(wound_mods.get("reroll_wound_full_reasons") or []))


def test_creeping_blight_rejects_unit_already_selected_to_shoot():
    game, dg_player, _enemy_player, dg_army, _enemy_army = _build_game()
    shooter = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_army.add_unit(shooter)
    _deploy_unit(game, shooter, 10.0, 10.0)
    shooter.round_state.shot_this_round = True

    _set_phase(game, "SHOOTING_PHASE", 0)
    assert not dg_player.stratagems.use("CREEPING BLIGHT", unit=shooter, phase_name="Shooting phase")


def test_putrid_detonation_auto_triggers_deadly_demise_and_afflicts_enemy():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    vehicle = _make_unit(
        "Plagueburst Crawler",
        keywords=["VEHICLE"],
        faction_keywords=["DEATH GUARD"],
        wounds="6",
        abilities=[
            {
                "name": "Deadly Demise",
                "description": "Deadly Demise 1",
                "type": "Ability",
                "parameter": "1",
            }
        ],
    )
    enemy = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
    )
    dg_army.add_unit(vehicle)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, vehicle, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    from warhammer40k_ai.utility.dice import DiceCollection
    vehicle.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))

    destroyed_model = vehicle.models[0]
    destroyed_model.wounds = 0

    game.turn = 1
    _set_phase(game, "SHOOTING_PHASE", 0)
    dg_player.stratagems._current_phase_name = "Shooting phase"
    dg_player.stratagems._on_model_destroyed_before_removal(unit=vehicle, model=destroyed_model)
    pending = dg_player.stratagems.get_pending_reactions()
    assert any(str(r.get("stratagem", "")).upper() == "PUTRID DETONATION" for r in pending)

    enemy_wounds_before = int(enemy.models[0].wounds)
    with patch("warhammer40k_ai.units.unit.get_roll", return_value=1):
        assert dg_player.stratagems.use("PUTRID DETONATION", phase_name="Shooting phase", dequeue=True)

    assert bool(enemy.special_rules.get("post_shoot_afflicted_active"))
    assert str(enemy.special_rules.get("post_shoot_afflicted_owner", "")) == str(dg_player.id)
    assert int(enemy.models[0].wounds) < enemy_wounds_before


def test_disgustingly_resilient_still_applies_damage_reduction():
    game, dg_player, _enemy_player, dg_army, enemy_army = _build_game()
    target = _make_unit(
        "Plague Marines",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    attacker = _make_unit(
        "Enemy Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    dg_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, attacker, 16.0, 10.0)

    _set_phase(game, "SHOOTING_PHASE", 1)
    assert dg_player.stratagems.use(
        "DISGUSTINGLY RESILIENT",
        unit=target,
        attacking_unit=attacker,
        phase_name="Shooting phase",
    )
    entries = list(target.special_rules.get("defensive_damage_reductions", []) or [])
    assert any(str(e.get("source", "")).upper() == "DISGUSTINGLY RESILIENT" for e in entries)
