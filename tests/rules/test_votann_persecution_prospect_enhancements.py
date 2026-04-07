from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None, toughness: int = 4):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["LEAGUES OF VOTANN"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": "3",
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


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4):
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army = Army.with_detachment("Leagues of Votann", "Persecution Prospect")
    army.faction_id = "LOV"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    player = Player("P1", control=PlayerControl.REMOTE, army=army)
    enemy_player = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(player)
    game.add_player(enemy_player)
    return game, army, enemy_army, player, enemy_player


def _set_unit_position(unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _find_pending_request(game, *, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return req
    return None


def _first_option_with(request, predicate):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if predicate(payload):
            return opt
    return None


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="LOV",
        detachment="Persecution Prospect",
        points=0,
        description="",
    ).apply_to_unit(unit)


def _ranged_profile(*, strength: str = "4") -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_persecution_descriptors_registered():
    expected = {
        "000010439002": ("Eye for Weakness", "wound_bonus_vs_assailed_targets"),
        "000010439003": ("Writ of Acquisition", "post_shoot_gain_yp_for_hit_assailed_units"),
        "000010439004": ("Surgical Saboteur", "post_shoot_select_hit_monster_or_vehicle_to_pin"),
        (
            "000010439005"
        ): (
            "Nomad Strategist",
            "once_per_battle_end_of_opponent_fight_phase_select_hernkyn_units_to_enter_strategic_reserves",
        ),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_eye_for_weakness_adds_wound_bonus_vs_assailed_target():
    from warhammer40k_ai.units import wargear as wargear_mod

    game, army, enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    attacker = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
    target = _make_unit("Enemy Unit", faction_keywords=["ENEMY"], keywords=["INFANTRY"], toughness=4)
    army.add_unit(attacker)
    enemy_army.add_unit(target)
    _apply_enhancement(attacker, enhancement_id="000010439002", enhancement_name="Eye for Weakness")
    target.special_rules["persecution_prospect_assailed_active"] = True
    target.special_rules["persecution_prospect_assailed_owner"] = str(player.id)

    profile = _ranged_profile(strength="4")
    original_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _expr: 3
    try:
        wound = profile._wound_target_with_tracking(target, attacker.models[0], {})
    finally:
        wargear_mod.get_roll = original_roll

    assert bool(wound.get("wound")) is True
    assert "+1 to wound from Eye for Weakness" in list(wound.get("modifiers", []) or [])


def test_writ_of_acquisition_gains_up_to_three_yp_for_assailed_units_hit():
    game, army, enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    attacker = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
    assailed_a = _make_unit("Enemy A", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    assailed_b = _make_unit("Enemy B", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    assailed_c = _make_unit("Enemy C", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    other = _make_unit("Enemy D", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    army.add_unit(attacker)
    for target in (assailed_a, assailed_b, assailed_c, other):
        enemy_army.add_unit(target)
        target.special_rules["persecution_prospect_assailed_active"] = target is not other
        target.special_rules["persecution_prospect_assailed_owner"] = str(player.id)
    _apply_enhancement(attacker, enhancement_id="000010439003", enhancement_name="Writ of Acquisition")

    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None

    game._on_unit_shooting_resolved_writ_of_acquisition(
        attacker_unit=attacker,
        hits_by_target={assailed_a: 1, assailed_b: 1, assailed_c: 1, other: 1},
    )

    assert int(getattr(pe, "yield_points", 0) or 0) == 3


def test_surgical_saboteur_queues_post_shoot_pinned_for_hit_monster_or_vehicle_only():
    game, army, enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0
    game.turn = 2

    attacker = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
    vehicle = _make_unit("Enemy Vehicle", faction_keywords=["ENEMY"], keywords=["VEHICLE"])
    infantry = _make_unit("Enemy Infantry", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    army.add_unit(attacker)
    enemy_army.add_unit(vehicle)
    enemy_army.add_unit(infantry)
    _apply_enhancement(attacker, enhancement_id="000010439004", enhancement_name="Surgical Saboteur")

    game._on_unit_shooting_resolved_surgical_saboteur(
        attacker_unit=attacker,
        hits_by_target={vehicle: 1, infantry: 1},
    )
    request = _find_pending_request(game, ability="post_shoot_pinned")
    assert request is not None
    assert str((request.context or {}).get("ability_name", "") or "") == "Surgical Saboteur"
    options = [dict(getattr(opt, "payload", {}) or {}) for opt in list(request.options or [])]
    candidate_ids = {str(opt.get("target_unit_id", "") or "") for opt in options}
    assert str(get_entity_id(vehicle) or "") in candidate_ids
    assert str(get_entity_id(infantry) or "") not in candidate_ids

    chosen = _first_option_with(
        request,
        lambda payload: str(payload.get("target_unit_id", "") or "") == str(get_entity_id(vehicle) or ""),
    )
    assert chosen is not None
    resolve_decision_command(game, request, chosen.option_id, player_id=player.id)

    assert bool(vehicle.special_rules.get("pinned_active")) is True
    assert str(vehicle.special_rules.get("pinned_expires_phase", "") or "") == "SHOOTING_PHASE"
    assert bool(infantry.special_rules.get("pinned_active")) is False


def test_nomad_strategist_queues_engagement_filtered_choice_and_spends_yp_once():
    game, army, enemy_army, player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 1
    game.turn = 2

    bearer_unit = _make_unit("Kahl", keywords=["CHARACTER", "INFANTRY"])
    scout_a = _make_unit("Hernkyn A", keywords=["MOUNTED", "HERNKYN"], faction_keywords=["LEAGUES OF VOTANN"])
    scout_b = _make_unit("Hernkyn B", keywords=["INFANTRY", "HERNKYN"], faction_keywords=["LEAGUES OF VOTANN"])
    scout_c = _make_unit("Hernkyn C", keywords=["INFANTRY", "HERNKYN"], faction_keywords=["LEAGUES OF VOTANN"])
    assailed_enemy = _make_unit("Assailed Enemy", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    blocking_enemy = _make_unit("Blocking Enemy", faction_keywords=["ENEMY"], keywords=["INFANTRY"])
    army.add_unit(bearer_unit)
    army.add_unit(scout_a)
    army.add_unit(scout_b)
    army.add_unit(scout_c)
    enemy_army.add_unit(assailed_enemy)
    enemy_army.add_unit(blocking_enemy)
    _apply_enhancement(bearer_unit, enhancement_id="000010439005", enhancement_name="Nomad Strategist")

    _set_unit_position(bearer_unit, 20.0, 20.0)
    _set_unit_position(scout_a, 0.0, 0.0)
    _set_unit_position(assailed_enemy, 0.5, 0.0)
    _set_unit_position(scout_b, 5.0, 0.0)
    _set_unit_position(scout_c, 10.0, 0.0)
    _set_unit_position(blocking_enemy, 10.5, 0.0)
    game.map.units = [bearer_unit, scout_a, scout_b, scout_c, assailed_enemy, blocking_enemy]
    game.rebuild_entity_registry()

    assailed_enemy.special_rules["persecution_prospect_assailed_active"] = True
    assailed_enemy.special_rules["persecution_prospect_assailed_owner"] = str(player.id)

    pe = getattr(army, "prioritised_efficiency", None)
    assert pe is not None
    pe.add_yield_points(2, game=game)

    game._on_phase_end_nomad_strategist(player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    request = _find_pending_request(game, ability="nomad_strategist")
    assert request is not None

    candidate_ids = {
        str(value or "").strip()
        for value in list((request.context or {}).get("candidate_unit_ids", []) or [])
        if str(value or "").strip()
    }
    assert str(get_entity_id(scout_a) or "") in candidate_ids
    assert str(get_entity_id(scout_b) or "") in candidate_ids
    assert str(get_entity_id(scout_c) or "") not in candidate_ids

    chosen = _first_option_with(
        request,
        lambda payload: int(payload.get("yp_spend", 0) or 0) == 2
        and set(str(v or "") for v in list(payload.get("selected_unit_ids", []) or []))
        == {str(get_entity_id(scout_a) or ""), str(get_entity_id(scout_b) or "")},
    )
    assert chosen is not None
    resolve_decision_command(game, request, chosen.option_id, player_id=player.id)

    assert str(getattr(scout_a, "reserve_status", "") or "") == "strategic_reserves"
    assert str(getattr(scout_b, "reserve_status", "") or "") == "strategic_reserves"
    assert scout_a not in list(game.map.units or [])
    assert scout_b not in list(game.map.units or [])
    assert int(getattr(pe, "yield_points", 0) or 0) == 0
    assert bool(getattr(bearer_unit, "has_used_unit_once_per_battle", lambda _k: False)("nomad_strategist")) is True

    game._on_phase_end_nomad_strategist(player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    assert _find_pending_request(game, ability="nomad_strategist") is None
