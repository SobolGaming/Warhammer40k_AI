from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: str = "4",
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {
            "name": "Chaos Space Marines"
            if "HERETIC ASTARTES" in {str(k).upper() for k in list(faction_keywords or []) + list(keywords or [])}
            else "Enemy"
        }
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
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
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None, wounds: str = "4", model_count: int = 1) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            model_count=model_count,
        )
    )


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    csm_army = Army("Chaos Space Marines", "Cabal of Chaos")
    csm_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    csm_player = Player("CSM", control=PlayerControl.LOCAL, army=csm_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)

    csm_player.command_points = 10
    enemy_player.command_points = 10
    csm_army.configure_rule_managers(force=True)
    csm_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, csm_player, enemy_player, csm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _ranged_profile():
    weapon = Wargear(
        {
            "name": "Test Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def test_shroud_of_chaos_queues_and_grants_stealth_aura_until_end_phase():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    source = _make_unit(
        "Sorcerer",
        keywords=["INFANTRY", "PSYKER", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    nearby = _make_unit(
        "Legionaries",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(source)
    csm_army.add_unit(nearby)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, nearby, 14.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    pending = csm_player.stratagems.get_pending_reactions()
    assert any(str(r.get("stratagem", "")).upper() == "SHROUD OF CHAOS" for r in pending)

    ok = csm_player.stratagems.use("SHROUD OF CHAOS", unit=source, phase_name="Shooting phase", dequeue=True)
    assert ok
    assert nearby.has_stealth()

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    assert not nearby.has_stealth()


def test_baleful_blessing_queues_on_mortal_wound_event_and_applies_fnp_vs_mortal():
    game, csm_player, enemy_player, csm_army, enemy_army = _build_game()
    target = _make_unit(
        "Legionaries",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    attacker = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, attacker, 16.0, 10.0)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "mortal_wound_allocated",
        attacker_unit=attacker,
        target_unit=target,
        target_model=target.models[0],
        phase_name="Shooting phase",
    )
    pending = csm_player.stratagems.get_pending_reactions()
    assert any(str(r.get("stratagem", "")).upper() == "BALEFUL BLESSING" for r in pending)

    ok = csm_player.stratagems.use("BALEFUL BLESSING", unit=target, phase_name="Shooting phase", dequeue=True)
    assert ok
    fnp_entries = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
    assert any(int(val) == 5 and "mortal" in str(cond or "").lower() for val, cond in fnp_entries)

    game.event_system.publish("phase_end", player=enemy_player, phase=game.phase)
    fnp_after = list(target.has_feel_no_pain(target_model=target.models[0]) or [])
    assert not any(int(val) == 5 and "mortal" in str(cond or "").lower() for val, cond in fnp_after)


def test_soulseekers_grants_ignore_cover_and_cleans_up():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Legionaries",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(shooter)
    enemy_army.add_unit(target)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, target, 16.0, 10.0)

    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    ok = csm_player.stratagems.use("SOULSEEKERS", unit=shooter, phase_name="Shooting phase")
    assert ok

    profile = _ranged_profile()
    attack_instance = {}
    profile._hit_target_with_tracking(
        target,
        shooter.models[0],
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert attack_instance.get("ignores_cover") is True

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    assert not bool(shooter.special_rules.get("warp_vision_ignores_cover_active"))


def test_unholy_haste_allows_charge_after_advance_until_charge_phase_end():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Legionaries",
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)

    unit.round_state.advanced_this_round = True
    assert not unit.can_charge_after_advance()

    _set_phase(game, csm_player, "CHARGE_PHASE", 0)
    ok = csm_player.stratagems.use("UNHOLY HASTE", unit=unit, phase_name="Charge phase")
    assert ok
    assert unit.can_charge_after_advance()

    game.event_system.publish("phase_end", player=csm_player, phase=game.phase)
    assert not unit.can_charge_after_advance()


def test_no_rest_in_death_returns_battleline_models_when_selected():
    game, csm_player, _enemy_player, csm_army, _enemy_army = _build_game()
    support = _make_unit(
        "Sorcerer",
        keywords=["INFANTRY", "PSYKER", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    battleline = _make_unit(
        "Legionaries",
        keywords=["INFANTRY", "BATTLELINE", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=3,
    )
    csm_army.add_unit(support)
    csm_army.add_unit(battleline)
    _deploy_unit(game, support, 10.0, 10.0)
    _deploy_unit(game, battleline, 18.0, 10.0)

    destroyed_model = battleline.models.pop()
    destroyed_model.wounds = 0
    battleline.models_lost.append(destroyed_model)

    _set_phase(game, csm_player, "MOVEMENT_PHASE", 0)
    with patch("warhammer40k_ai.rules.stratagems_chaos_space_marines.dice_module.get_roll", return_value=2):
        ok = csm_player.stratagems.use(
            "NO REST IN DEATH",
            unit=battleline,
            phase_name="Movement phase",
            mode="return",
        )
    assert ok
    assert destroyed_model in list(battleline.models or [])
    assert destroyed_model not in list(battleline.models_lost or [])


def test_mutations_curse_requires_valid_enemy_and_deals_mortal_wounds():
    game, csm_player, _enemy_player, csm_army, enemy_army = _build_game()
    source = _make_unit(
        "Sorcerer",
        keywords=["INFANTRY", "PSYKER", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy_near = _make_unit("Enemy Near", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds="10")
    enemy_far = _make_unit("Enemy Far", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds="10")
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy_near)
    enemy_army.add_unit(enemy_far)
    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, enemy_near, 18.0, 10.0)
    _deploy_unit(game, enemy_far, 40.0, 10.0)

    source._attacking_unit_has_any_los_to_target_unit = lambda _target, _map: True

    _set_phase(game, csm_player, "SHOOTING_PHASE", 0)
    assert not csm_player.stratagems.use(
        "MUTATION'S CURSE",
        unit=source,
        enemy_unit=enemy_far,
        phase_name="Shooting phase",
    )

    near_before = int(enemy_near.models[0].wounds)
    with patch("warhammer40k_ai.rules.stratagems_chaos_space_marines.dice_module.get_roll", side_effect=[5, 2, 3]):
        ok = csm_player.stratagems.use(
            "MUTATION'S CURSE",
            unit=source,
            enemy_unit=enemy_near,
            phase_name="Shooting phase",
        )
    assert ok
    assert int(enemy_near.models[0].wounds) == near_before - 5
