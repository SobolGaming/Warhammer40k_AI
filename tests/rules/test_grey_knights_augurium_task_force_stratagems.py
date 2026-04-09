from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count: int = 1,
        wounds: int = 3,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Grey Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
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
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _deep_strike_ability() -> dict:
    return {
        "name": "Deep Strike",
        "description": "Deep Strike",
        "type": "Core",
        "parameter": "",
    }


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count: int = 1,
    wounds: int = 3,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            model_count=model_count,
            wounds=wounds,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _ranged_wargear(name: str = "Storm Bolter") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _melee_wargear(name: str = "Nemesis Force Weapon") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-1",
            "D": "2",
            "description": "",
        }
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    army_gk = Army.with_detachment("Grey Knights", "Augurium Task Force")
    army_gk.faction_id = "GK"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("GK", control=PlayerControl.LOCAL, army=army_gk)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 5
    p2.command_points = 5
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


def test_augurium_stratagem_descriptors_registered():
    expected = {
        "000010365002": ("Aggressive Anticipation", "ignore_skill_hit_modifiers"),
        "000010365003": ("Appointed Hour", "critical_hits_on_5plus"),
        "000010365005": ("Necessary End", "fight_on_death_after_attacks"),
        "000010365006": ("Redirected Strike", "enter_strategic_reserves_if_deep_strike"),
        "000010365007": ("Mirage of Echoes", "enter_strategic_reserves_if_deep_strike"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_augurium_phase_start_reactions_queue_offensive_stratagems():
    game, p1, p2, army_gk, army_enemy = _build_game()
    psyker = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    psyker.models[0].wargear = [_ranged_wargear(), _melee_wargear()]
    army_gk.add_unit(psyker)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, psyker, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    assert _pending_names(p1.stratagems, clear=True) == {"AGGRESSIVE ANTICIPATION", "APPOINTED HOUR"}

    _set_phase(game, p2, "FIGHT_PHASE", 1)
    assert _pending_names(p1.stratagems, clear=True) == {"AGGRESSIVE ANTICIPATION", "APPOINTED HOUR"}


def test_aggressive_anticipation_grants_ignore_modifier_rule_until_phase_end():
    game, p1, _p2, army_gk, army_enemy = _build_game()
    psyker = _make_unit(
        "Purifier Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    weapon = _ranged_wargear()
    psyker.models[0].wargear = [weapon]
    army_gk.add_unit(psyker)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, psyker, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(p1.stratagems, "AGGRESSIVE ANTICIPATION")
    assert pending is not None

    ok = p1.stratagems.use(
        "AGGRESSIVE ANTICIPATION",
        unit=psyker,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4

    mgr = getattr(army_gk, "grey_knights_detachments", None)
    rule = mgr.augurium_aggressive_anticipation_ignore_hit_modifiers_rule(psyker.models[0], game=game)
    assert isinstance(rule, dict)
    assert set(rule.get("skill_kinds") or set()) == {"ballistic", "weapon"}
    assert bool(rule.get("allow_hit")) is True

    profile = weapon.profiles["default"]
    hit = profile._hit_target_with_tracking(
        enemy,
        psyker.models[0],
        {
            "_aura_attack_mods": SimpleNamespace(crit_hit_threshold=None),
            "hit_roll_modifiers": [(-1, "Test penalty")],
            "hit_modifier_choice": CHOICE_IGNORE_NEGATIVE,
        },
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit.get("hit")) is True

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert mgr.augurium_aggressive_anticipation_ignore_hit_modifiers_rule(psyker.models[0], game=game) is None


def test_appointed_hour_grants_critical_hits_on_five_plus_until_phase_end():
    game, p1, _p2, army_gk, army_enemy = _build_game()
    psyker = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    weapon = _ranged_wargear()
    psyker.models[0].wargear = [weapon]
    army_gk.add_unit(psyker)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, psyker, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(p1.stratagems, "APPOINTED HOUR")
    assert pending is not None

    ok = p1.stratagems.use(
        "APPOINTED HOUR",
        unit=psyker,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4

    profile = weapon.profiles["default"]
    hit = profile._hit_target_with_tracking(
        enemy,
        psyker.models[0],
        {"_aura_attack_mods": SimpleNamespace(crit_hit_threshold=None)},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit.get("hit")) is True
    assert int(hit.get("crit_threshold", 0) or 0) == 5

    mgr = getattr(army_gk, "grey_knights_detachments", None)
    threshold, source = mgr.augurium_appointed_hour_crit_hit_threshold(psyker.models[0], weapon_profile=profile, game=game)
    assert int(threshold or 0) == 5
    assert str(source or "").strip().upper() == "APPOINTED HOUR"

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    threshold_after, _source_after = mgr.augurium_appointed_hour_crit_hit_threshold(
        psyker.models[0],
        weapon_profile=profile,
        game=game,
    )
    assert int(threshold_after or 0) == 0


def test_necessary_end_queues_and_uses_battle_round_based_fight_on_death():
    game, p1, p2, army_gk, army_enemy = _build_game()
    game.turn = 3
    target = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        model_count=2,
        wounds=3,
    )
    enemy = _make_unit(
        "Enemy Fighters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=2,
        wounds=3,
    )
    target.models[0].wargear = [_melee_wargear()]
    army_gk.add_unit(target)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[target])
    pending = _pending_by_name(p1.stratagems, "NECESSARY END")
    assert pending is not None
    assert target in list(pending.get("candidates") or [])

    ok = p1.stratagems.use(
        "NECESSARY END",
        unit=target,
        attacking_unit=enemy,
        target_units=[target],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4

    rule = target.get_melee_fight_on_death_after_attacks_rule(model=target.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 4
    assert "NECESSARY END" in str(rule.get("source", "") or "").upper()

    target.round_state.fought_this_phase = False
    model = target.models[0]
    model._wounds = 0
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=4):
        target._handle_model_destroyed(model, game.map)
    pending_models = list(getattr(target, "_melee_fight_on_death_pending_models", []) or [])
    assert model in pending_models

    with patch.object(target, "_try_fight_on_death") as mocked:
        target.end_attack_resolution(game_map=game.map)
    assert mocked.call_count == 1
    assert not list(getattr(target, "_melee_fight_on_death_pending_models", []) or [])

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert target.get_melee_fight_on_death_after_attacks_rule(model=target.models[0]) is None


def test_redirected_strike_queues_at_command_phase_end_and_enters_strategic_reserves():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    psyker = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        abilities=[_deep_strike_ability()],
    )
    army_gk.add_unit(psyker)
    _deploy_unit(game, psyker, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "COMMAND_PHASE", 0)
    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="COMMAND_PHASE"))
    pending = _pending_by_name(p1.stratagems, "REDIRECTED STRIKE")
    assert pending is not None

    ok = p1.stratagems.use(
        "REDIRECTED STRIKE",
        unit=psyker,
        phase_name="Command phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4
    assert str(getattr(psyker, "reserve_status", "") or "") == "strategic_reserves"
    assert psyker not in list(getattr(game.map, "units", []) or [])


def test_mirage_of_echoes_queues_on_enemy_reinforcement_setup_and_enters_strategic_reserves():
    game, p1, p2, army_gk, army_enemy = _build_game()
    psyker = _make_unit(
        "Purifier Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        abilities=[_deep_strike_ability()],
    )
    enemy = _make_unit(
        "Enemy Reinforcements",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_gk.add_unit(psyker)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, psyker, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_set_up", unit=enemy, set_up_as_reinforcements=True)
    pending = _pending_by_name(p1.stratagems, "MIRAGE OF ECHOES")
    assert pending is not None

    ok = p1.stratagems.use(
        "MIRAGE OF ECHOES",
        unit=psyker,
        enemy_unit=enemy,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok
    assert int(p1.command_points or 0) == 4
    assert str(getattr(psyker, "reserve_status", "") or "") == "strategic_reserves"
    assert psyker not in list(getattr(game.map, "units", []) or [])
