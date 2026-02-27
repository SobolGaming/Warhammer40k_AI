from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        movement: int = 6,
        leadership: int = 7,
        save: int = 3,
        wounds: int = 2,
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": "4",
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _create_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    movement: int = 6,
    leadership: int = 7,
    save: int = 3,
    wounds: int = 2,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            leadership=leadership,
            save=save,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, sororitas_units: list[Unit], enemy_units: list[Unit]):
    sororitas_army = Army("Adepta Sororitas", "Army of Faith")
    sororitas_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(sororitas_units or []):
        sororitas_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"

    sororitas_player = Player("Sororitas Player", control=PlayerControl.LOCAL, army=sororitas_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(sororitas_player)
    game.add_player(enemy_player)
    return game, sororitas_player, sororitas_army


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str):
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="AS",
        detachment="Army of Faith",
        detachment_id="army-of-faith",
        points=0,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _make_melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Melee Weapon", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Melee Profile",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Boltgun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Ranged Profile",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _find_divine_aspect_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "divine_aspect_target":
            continue
        return req
    return None


def test_apply_army_of_faith_enhancements_sets_expected_flags():
    unit = _create_unit(
        "Canoness",
        keywords=["INFANTRY", "CHARACTER", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    _build_game(sororitas_units=[unit], enemy_units=[])

    _apply_enhancement(unit, enhancement_id="000009037002", name="Litanies of Faith")
    sr = dict(getattr(unit, "special_rules", {}) or {})
    assert bool(sr.get("enhancement_litanies_of_faith", False))

    _apply_enhancement(unit, enhancement_id="000009037003", name="Blade of Saint Ellynor")
    sr = dict(getattr(unit, "special_rules", {}) or {})
    assert bool(sr.get("enhancement_blade_of_saint_ellynor", False))
    assert int(sr.get("enhancement_bearer_melee_strength_bonus", 0) or 0) >= 1
    assert int(sr.get("enhancement_bearer_melee_ap_bonus", 0) or 0) >= 1
    assert bool(sr.get("enhancement_bearer_melee_precision", False))

    _apply_enhancement(unit, enhancement_id="000009037004", name="Divine Aspect")
    sr = dict(getattr(unit, "special_rules", {}) or {})
    assert bool(sr.get("enhancement_divine_aspect", False))
    assert float(sr.get("enhancement_divine_aspect_range", 0.0) or 0.0) == 12.0

    _apply_enhancement(unit, enhancement_id="000009037005", name="Triptych of the Macharian Crusade")
    sr = dict(getattr(unit, "special_rules", {}) or {})
    assert bool(sr.get("enhancement_triptych_of_macharian_crusade", False))


def test_litanies_of_faith_gains_miracle_die_on_passed_command_phase_test():
    from warhammer40k_ai.rules import acts_of_faith as aof

    source_unit = _create_unit(
        "Canoness",
        keywords=["INFANTRY", "CHARACTER", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    game, player, army = _build_game(sororitas_units=[source_unit], enemy_units=[])
    _apply_enhancement(source_unit, enhancement_id="000009037002", name="Litanies of Faith")

    source_unit.pass_leadership_check_for_model = lambda _model: True
    game.phase = BattleRoundPhases.COMMAND_PHASE

    old_get_roll = aof.get_roll
    aof.get_roll = lambda _expr="D6": 5
    try:
        army.acts_of_faith.on_command_phase_start(game=game, player=player)
    finally:
        aof.get_roll = old_get_roll

    assert list(army.acts_of_faith.miracle_dice) == [5]


def test_blade_of_saint_ellynor_awards_once_per_fight_selection():
    source_unit = _create_unit(
        "Palatine",
        keywords=["INFANTRY", "CHARACTER", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    enemy_unit = _create_unit("Enemy Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    game, player, army = _build_game(sororitas_units=[source_unit], enemy_units=[enemy_unit])
    _apply_enhancement(source_unit, enhancement_id="000009037003", name="Blade of Saint Ellynor")
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.turn = 1

    melee_profile = _make_melee_profile()
    bearer = source_unit.models[0]
    game.event_system.publish("fight_unit_selected", unit=source_unit, selecting_player=player)
    game.event_system.publish(
        "unit_destroyed",
        unit=enemy_unit,
        destroyed_by_unit=source_unit,
        destroyed_by_model=bearer,
        destroyed_by_weapon_profile=melee_profile,
        last_model=enemy_unit.models[0],
    )
    assert len(list(army.acts_of_faith.miracle_dice)) == 1

    game.event_system.publish(
        "unit_destroyed",
        unit=enemy_unit,
        destroyed_by_unit=source_unit,
        destroyed_by_model=bearer,
        destroyed_by_weapon_profile=melee_profile,
        last_model=enemy_unit.models[0],
    )
    assert len(list(army.acts_of_faith.miracle_dice)) == 1

    game.event_system.publish("fight_unit_selected", unit=source_unit, selecting_player=player)
    game.event_system.publish(
        "unit_destroyed",
        unit=enemy_unit,
        destroyed_by_unit=source_unit,
        destroyed_by_model=bearer,
        destroyed_by_weapon_profile=melee_profile,
        last_model=enemy_unit.models[0],
    )
    assert len(list(army.acts_of_faith.miracle_dice)) == 2


def test_divine_aspect_queues_and_gains_miracle_die_on_failed_test():
    source_unit = _create_unit(
        "Canoness",
        keywords=["INFANTRY", "CHARACTER", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    enemy_unit = _create_unit("Enemy Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    game, player, army = _build_game(sororitas_units=[source_unit], enemy_units=[enemy_unit])
    _apply_enhancement(source_unit, enhancement_id="000009037004", name="Divine Aspect")

    source_unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy_unit.models[0].set_location(6.0, 0.0, 0.0, 0.0)

    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 1
    game._on_phase_start_adepta_sororitas_enhancements(player=player, phase=game.phase)
    request = _find_divine_aspect_request(game)
    assert request is not None

    enemy_id = str(get_entity_id(enemy_unit) or "")
    option_id = ""
    for option in list(request.options or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == enemy_id:
            option_id = str(getattr(option, "option_id", "") or "")
            break
    assert option_id

    enemy_unit.take_battle_shock_test = lambda _turn: game.event_system.publish(
        "battle_shock_test_resolved",
        unit=enemy_unit,
        passed=False,
    )

    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(player, "id", None),
        option_id=option_id,
        payload={},
    )
    apply_result = dispatch_decision(game, request, result)
    assert bool(apply_result.ok)
    assert len(list(army.acts_of_faith.miracle_dice)) == 1
    sr = dict(getattr(enemy_unit, "special_rules", {}) or {})
    assert "enhancement_divine_aspect_pending" not in sr


def test_triptych_of_the_macharian_crusade_auto_succeeds_miracle_save():
    source_unit = _create_unit(
        "Palatine",
        keywords=["INFANTRY", "CHARACTER", "ADEPTA SORORITAS"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    game, player, army = _build_game(sororitas_units=[source_unit], enemy_units=[])
    _apply_enhancement(source_unit, enhancement_id="000009037005", name="Triptych of the Macharian Crusade")

    mgr = army.acts_of_faith
    mgr.can_use_act_of_faith = lambda _unit, game=None: True
    mgr.resolve_roll = lambda _unit, **_kwargs: (1, [1], True)
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    bearer = source_unit.models[0]
    profile = _make_ranged_profile()
    result = profile._save_with_tracking(
        bearer,
        attack_instance={},
        ap=0,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(result.get("saved", False))
    effects = [str(v) for v in list(result.get("special_effects", []) or [])]
    assert any("Triptych of the Macharian Crusade" in effect for effect in effects)
