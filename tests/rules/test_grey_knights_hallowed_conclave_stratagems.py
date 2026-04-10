from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
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
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count: int = 1,
        wounds: int = 4,
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


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count: int = 1,
    wounds: int = 4,
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


def _ranged_wargear(name: str = "Storm Bolter", *, strength: str = "4") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def _melee_wargear(
    name: str = "Nemesis Force Weapon",
    *,
    attacks: str = "2",
    strength: str = "6",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "-2",
            "D": "2",
            "description": "",
        }
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    army_gk = Army.with_detachment("Grey Knights", "Hallowed Conclave")
    army_gk.faction_id = "GK"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("GK", control=PlayerControl.LOCAL, army=army_gk)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 6
    p2.command_points = 6
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


def _first_request(game: Game, decision_type: str, *, kind: str = ""):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        request_kind = str(ctx.get("kind", "") or ctx.get("reactive_move_kind", "") or "")
        if kind and request_kind != str(kind):
            continue
        return request
    return None


def test_hallowed_conclave_stratagem_descriptors_registered():
    expected = {
        "000010353002": ("Giants of the Battlefield", "melee_attacks_bonus"),
        "000010353003": ("Unending Fidelity", "fight_or_shoot_on_death_after_attacks"),
        "000010353004": ("Point-blank Purgation", "grant_storm_bolter_keywords"),
        "000010353005": ("Grind Them Underfoot", "charge_end_mortal_wounds_per_engaged_model"),
        "000010353006": ("Precognitive Strategies", "reactive_move_d6"),
        "000010353007": ("Shining Resolve", "wound_roll_penalty_if_strength_gt_toughness"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_hallowed_conclave_phase_start_reactions_queue_point_blank_and_giants():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    shooters = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
    )
    terminators = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["GREY KNIGHTS"],
    )
    army_gk.add_unit(shooters)
    army_gk.add_unit(terminators)
    _deploy_unit(game, shooters, 10.0, 10.0)
    _deploy_unit(game, terminators, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    assert _pending_names(p1.stratagems, clear=True) == {"POINT-BLANK PURGATION"}

    _set_phase(game, p1, "FIGHT_PHASE", 0)
    assert _pending_names(p1.stratagems, clear=True) == {"GIANTS OF THE BATTLEFIELD"}


def test_giants_of_the_battlefield_grants_melee_attacks_bonus_until_phase_end():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    terminators = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["GREY KNIGHTS"],
    )
    terminators.models[0].wargear = [_melee_wargear(), _ranged_wargear()]
    army_gk.add_unit(terminators)
    _deploy_unit(game, terminators, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "FIGHT_PHASE", 0)
    pending = _pending_by_name(p1.stratagems, "GIANTS OF THE BATTLEFIELD")
    assert pending is not None

    ok = p1.stratagems.use(
        "GIANTS OF THE BATTLEFIELD",
        unit=terminators,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok

    bonus, reasons = terminators.models[0].get_temporary_weapon_attacks_bonus("Nemesis Force Weapon")
    assert int(bonus or 0) == 1
    assert any("GIANTS OF THE BATTLEFIELD" in str(reason).upper() for reason in list(reasons or []))
    ranged_bonus, _ranged_reasons = terminators.models[0].get_temporary_weapon_attacks_bonus("Storm Bolter")
    assert int(ranged_bonus or 0) == 0

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
    bonus_after, _reasons_after = terminators.models[0].get_temporary_weapon_attacks_bonus("Nemesis Force Weapon")
    assert int(bonus_after or 0) == 0


def test_point_blank_purgation_grants_storm_bolter_keywords_until_phase_end():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    infantry = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
    )
    infantry.models[0].wargear = [_ranged_wargear("Storm Bolter"), _ranged_wargear("Incinerator")]
    army_gk.add_unit(infantry)
    _deploy_unit(game, infantry, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(p1.stratagems, "POINT-BLANK PURGATION")
    assert pending is not None

    ok = p1.stratagems.use(
        "POINT-BLANK PURGATION",
        unit=infantry,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok

    bonuses = list(infantry.models[0].get_temporary_weapon_keyword_bonuses("Storm Bolter") or [])
    assert {str(item.get("keyword", "") or "") for item in bonuses} == {"PISTOL", "TWIN-LINKED"}
    assert list(infantry.models[0].get_temporary_weapon_keyword_bonuses("Incinerator") or []) == []

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(infantry.models[0].get_temporary_weapon_keyword_bonuses("Storm Bolter") or []) == []


def test_precognitive_strategies_queues_on_enemy_move_and_creates_reactive_move_request():
    game, p1, p2, army_gk, army_enemy = _build_game()
    target = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Movers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_gk.add_unit(target)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 14.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=enemy, action="advance")
    pending = _pending_by_name(p1.stratagems, "PRECOGNITIVE STRATEGIES")
    assert pending is not None
    assert target in list(pending.get("candidates") or [])

    with patch("warhammer40k_ai.rules.stratagems_grey_knights.dice_module.get_roll", return_value=5):
        ok = p1.stratagems.use(
            "PRECOGNITIVE STRATEGIES",
            unit=target,
            enemy_unit=enemy,
            action="advance",
            phase_name="Movement phase",
            dequeue=True,
        )
    assert ok

    request = _first_request(game, DECISION_MOVE_UNIT, kind="hallowed_conclave_precognitive_strategies")
    assert request is not None
    ctx = dict(getattr(request, "context", {}) or {})
    assert int(ctx.get("max_distance", 0) or 0) == 5
    assert str(ctx.get("kind", "") or ctx.get("reactive_move_kind", "") or "") == (
        "hallowed_conclave_precognitive_strategies"
    )


def test_shining_resolve_applies_strength_greater_than_toughness_wound_penalty_until_phase_end():
    game, p1, p2, army_gk, army_enemy = _build_game()
    target = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    strong_weapon = _ranged_wargear("Enemy Rifle", strength="5")
    equal_weapon = _ranged_wargear("Enemy Carbine", strength="4")
    enemy.models[0].wargear = [strong_weapon, equal_weapon]
    army_gk.add_unit(target)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
    pending = _pending_by_name(p1.stratagems, "SHINING RESOLVE")
    assert pending is not None

    ok = p1.stratagems.use(
        "SHINING RESOLVE",
        unit=target,
        attacking_unit=enemy,
        target_units=[target],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok

    strong_result = strong_weapon.profiles["default"]._wound_target_with_tracking(
        target,
        enemy.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("SHINING RESOLVE" in str(item).upper() for item in list(strong_result.get("modifiers", []) or []))

    equal_result = equal_weapon.profiles["default"]._wound_target_with_tracking(
        target,
        enemy.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("SHINING RESOLVE" in str(item).upper() for item in list(equal_result.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    strong_after = strong_weapon.profiles["default"]._wound_target_with_tracking(
        target,
        enemy.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("SHINING RESOLVE" in str(item).upper() for item in list(strong_after.get("modifiers", []) or []))


def test_unending_fidelity_shooting_phase_grants_shoot_on_death_and_cleans_up():
    game, p1, p2, army_gk, army_enemy = _build_game()
    target = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
        model_count=2,
    )
    enemy = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    target.models[0].wargear = [_ranged_wargear()]
    enemy.models[0].wargear = [_ranged_wargear("Enemy Rifle", strength="5")]
    army_gk.add_unit(target)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
    pending = _pending_by_name(p1.stratagems, "UNENDING FIDELITY")
    assert pending is not None

    ok = p1.stratagems.use(
        "UNENDING FIDELITY",
        unit=target,
        attacking_unit=enemy,
        target_units=[target],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok

    model = target.models[0]
    rule = target.get_shoot_on_death_after_attacks_rule(model=model)
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 4
    assert str(rule.get("attack_type", "") or "") == "any"
    assert "UNENDING FIDELITY" in str(rule.get("source", "") or "").upper()

    target.begin_attack_resolution()
    model._last_damage_source_kind = "attack"
    model._last_damage_weapon_profile = enemy.models[0].wargear[0].profiles["default"]
    model._wounds = 0
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=4):
        target._handle_model_destroyed(model, game.map)
    assert model in list(getattr(target, "_shoot_on_death_pending_models", []) or [])

    with patch.object(target, "_try_shoot_on_death") as mocked:
        target.end_attack_resolution(game_map=game.map)
    assert mocked.call_count == 1

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert target.get_shoot_on_death_after_attacks_rule(model=model) is None


def test_unending_fidelity_fight_phase_grants_fight_on_death_and_cleans_up():
    game, p1, p2, army_gk, army_enemy = _build_game()
    target = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
        model_count=1,
    )
    enemy = _make_unit(
        "Enemy Fighters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=1,
    )
    target.models[0].wargear = [_melee_wargear()]
    enemy.models[0].wargear = [_melee_wargear("Enemy Blade")]
    army_gk.add_unit(target)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[target])
    pending = _pending_by_name(p1.stratagems, "UNENDING FIDELITY")
    assert pending is not None

    ok = p1.stratagems.use(
        "UNENDING FIDELITY",
        unit=target,
        attacking_unit=enemy,
        target_units=[target],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok

    model = target.models[0]
    rule = target.get_melee_fight_on_death_after_attacks_rule(model=model)
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 4
    assert bool(rule.get("allow_any_fight_phase_destruction", False)) is True
    assert "UNENDING FIDELITY" in str(rule.get("source", "") or "").upper()

    target.round_state.fought_this_phase = False
    target._last_destroyed_by_weapon_profile = enemy.models[0].wargear[0].profiles["default"]
    model._wounds = 0
    with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=4):
        target._handle_model_destroyed(model, game.map)
    assert model in list(getattr(target, "_melee_fight_on_death_pending_models", []) or [])

    with patch.object(target, "_try_fight_on_death") as mocked:
        target.end_attack_resolution(game_map=game.map)
    assert mocked.call_count == 1

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert target.get_melee_fight_on_death_after_attacks_rule(model=model) is None


def test_grind_them_underfoot_queues_after_charge_and_inflicts_mortal_wounds():
    game, p1, _p2, army_gk, army_enemy = _build_game()
    target = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["GREY KNIGHTS"],
        model_count=1,
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=1,
        wounds=3,
    )
    army_gk.add_unit(target)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "CHARGE_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=target, action="charge")
    pending = _pending_by_name(p1.stratagems, "GRIND THEM UNDERFOOT")
    assert pending is not None
    assert enemy in list(
        (pending.get("enemy_candidates_by_unit_id") or {}).get(str(getattr(target, "id", target._id)), [])
        or pending.get("enemy_candidates")
        or []
    ) or enemy in list(next(iter(dict(pending.get("enemy_candidates_by_unit_id") or {}).values()), []) or [])

    starting_wounds = int(enemy.models[0].wounds or 0)
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        ok = p1.stratagems.use(
            "GRIND THEM UNDERFOOT",
            unit=target,
            enemy_unit=enemy,
            action="charge",
            phase_name="Charge phase",
            dequeue=True,
        )
    assert ok
    assert int(enemy.models[0].wounds or 0) == starting_wounds - 1
