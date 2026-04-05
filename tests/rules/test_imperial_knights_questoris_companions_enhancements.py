from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
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
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "6",
                "OC": "8",
                "base_size": "100mm",
                "inv_sv": "5",
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
    faction_name: str,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    ik_army = Army("Imperial Knights", detachment_type="Questoris Companions")
    ik_army.faction_id = "QI"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    ik_player = Player("IK", PlayerControl.REMOTE, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, ik_army, enemy_army, ik_player, enemy_player


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="QI",
        detachment="Questoris Companions",
        points=0,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _find_request(game: Game, *, decision_type: str, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != str(ability):
            continue
        return req
    return None


def _resolve_option(game: Game, request, *, player_id: str, label: str | None = None, target_unit_id: str | None = None):
    option = None
    for candidate in list(getattr(request, "options", []) or []):
        payload = dict(getattr(candidate, "payload", {}) or {})
        if label is not None and str(getattr(candidate, "label", "") or "") == str(label):
            option = candidate
            break
        if target_unit_id is not None and str(payload.get("target_unit_id", "") or "") == str(target_unit_id):
            option = candidate
            break
    assert option is not None
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))
    return result


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Cannon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        "Test Cannon",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "-2",
            "D": "3",
            "description": "",
        },
        parent_wargear=parent,
    )


def _melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        "Test Blade",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "-2",
            "D": "3",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_questoris_companions_descriptors_registered():
    expected = {
        "000010502002": ("Herald of Triumph", "optional_bearer_charge_end_battleshock_aura"),
        "000010502003": ("Wyrmslayer Divination", "optional_bearer_ranged_attacks_reroll_hits_vs_fly"),
        "000010502004": ("Pennant of Silvered Fury", "optional_grant_weapon_keywords"),
        "000010502005": ("Crushing Condemnation", "optional_select_enemy_and_roll_six_d6_for_mortal_wounds"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_herald_of_triumph_queues_on_charge_and_applies_battleshock_modifier():
    game, ik_army, enemy_army, ik_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.CHARGE_PHASE

    knight = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_far = _make_unit("Enemy Far", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ik_army.add_unit(knight)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)
    enemy_army.add_unit(enemy_far)
    _apply_enhancement(knight, enhancement_id="000010502002", enhancement_name="Herald of Triumph")

    _set_unit_position(knight, 0.0, 0.0)
    _set_unit_position(enemy_a, 4.5, 0.0)
    _set_unit_position(enemy_b, 0.0, 4.5)
    _set_unit_position(enemy_far, 14.0, 0.0)
    game.map.units = [knight, enemy_a, enemy_b, enemy_far]
    game.rebuild_entity_registry()

    captured = {}

    def _capture(target):
        def _take_battle_shock_test(current_turn: int = 1):
            captured[str(get_entity_id(target) or "")] = {
                "turn": int(current_turn),
                "modifier": int(getattr(target, "special_rules", {}).get("battle_shock_test_modifier", 0) or 0),
                "reasons": list(getattr(target, "special_rules", {}).get("battle_shock_test_modifier_reasons", []) or []),
            }
            target.special_rules.pop("battle_shock_test_modifier", None)
            target.special_rules.pop("battle_shock_test_modifier_reasons", None)
        return _take_battle_shock_test

    enemy_a.take_battle_shock_test = _capture(enemy_a)
    enemy_b.take_battle_shock_test = _capture(enemy_b)
    enemy_far.take_battle_shock_test = _capture(enemy_far)

    game._on_unit_move_ended_imperial_knights_questoris_companions(unit=knight, action="charge")
    request = _find_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="imperial_knights_herald_of_triumph")
    assert request is not None
    _resolve_option(game, request, player_id=ik_player.id, label="Use")

    enemy_a_capture = captured[str(get_entity_id(enemy_a) or "")]
    enemy_b_capture = captured[str(get_entity_id(enemy_b) or "")]
    assert enemy_a_capture["modifier"] == -1
    assert enemy_b_capture["modifier"] == -1
    assert any("Herald of Triumph" in str(reason or "") for reason in enemy_a_capture["reasons"])
    assert str(get_entity_id(enemy_far) or "") not in captured
    assert bool(ik_army.imperial_knights_detachments.is_questoris_companions_enhancement_expended(knight))


def test_wyrmslayer_divination_queues_in_shooting_and_rerolls_hits_vs_fly():
    game, ik_army, enemy_army, ik_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    knight = _make_unit(
        "Knight Crusader",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    fly_target = _make_unit("Fly Target", faction_name="Enemy", keywords=["FLY", "VEHICLE"], faction_keywords=["ENEMY"])
    ground_target = _make_unit("Ground Target", faction_name="Enemy", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    ik_army.add_unit(knight)
    enemy_army.add_unit(fly_target)
    enemy_army.add_unit(ground_target)
    _apply_enhancement(knight, enhancement_id="000010502003", enhancement_name="Wyrmslayer Divination")

    game.map.units = [knight, fly_target, ground_target]
    game.rebuild_entity_registry()

    game._on_shooting_targets_selected_imperial_knights_questoris_companions(
        attacking_unit=knight,
        target_units=[fly_target, ground_target],
    )
    request = _find_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="imperial_knights_wyrmslayer_divination")
    assert request is not None
    _resolve_option(game, request, player_id=ik_player.id, label="Use")

    profile = _ranged_profile()
    fly_result = profile._hit_target_with_tracking(fly_target, knight.models[0], {}, roll_value=1, allow_rerolls=False, log_roll=False)
    ground_result = profile._hit_target_with_tracking(ground_target, knight.models[0], {}, roll_value=1, allow_rerolls=False, log_roll=False)

    assert any("Wyrmslayer Divination" in str(reason or "") for reason in list(fly_result.get("reroll_full_reasons", []) or []))
    assert not any("Wyrmslayer Divination" in str(reason or "") for reason in list(ground_result.get("reroll_full_reasons", []) or []))
    assert bool(ik_army.imperial_knights_detachments.is_questoris_companions_enhancement_expended(knight))


def test_pennant_of_silvered_fury_queues_in_fight_and_grants_sustained_hits_two():
    game, ik_army, enemy_army, ik_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    knight = _make_unit(
        "Knight Gallant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    target = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ik_army.add_unit(knight)
    enemy_army.add_unit(target)
    _apply_enhancement(knight, enhancement_id="000010502004", enhancement_name="Pennant of Silvered Fury")

    game.map.units = [knight, target]
    game.rebuild_entity_registry()

    game._on_fight_unit_selected_imperial_knights_questoris_companions(unit=knight, selecting_player=ik_player)
    request = _find_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="imperial_knights_pennant_of_silvered_fury")
    assert request is not None
    _resolve_option(game, request, player_id=ik_player.id, label="Use")

    profile = _melee_profile()
    attack_instance = {}
    profile._hit_target_with_tracking(target, knight.models[0], attack_instance, roll_value=6, allow_rerolls=False, log_roll=False)

    assert int(attack_instance.get("sustained_hit", 0) or 0) == 2
    assert bool(ik_army.imperial_knights_detachments.is_questoris_companions_enhancement_expended(knight))


def test_crushing_condemnation_queues_choose_quarry_with_none_and_applies_mortals(monkeypatch):
    game, ik_army, enemy_army, ik_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    knight = _make_unit(
        "Knight Gallant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    destroyed_enemy = _make_unit("Destroyed Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    live_candidate = _make_unit("Live Candidate", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    engaged_enemy = _make_unit("Engaged Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    ik_army.add_unit(knight)
    enemy_army.add_unit(destroyed_enemy)
    enemy_army.add_unit(live_candidate)
    enemy_army.add_unit(engaged_enemy)
    _apply_enhancement(knight, enhancement_id="000010502005", enhancement_name="Crushing Condemnation")

    _set_unit_position(knight, 0.0, 0.0)
    _set_unit_position(destroyed_enemy, 4.5, 0.0)
    _set_unit_position(live_candidate, 8.0, 0.0)
    _set_unit_position(engaged_enemy, 0.0, 4.5)
    destroyed_enemy.models[0].wounds = 0
    destroyed_enemy.is_alive = lambda: False
    game.map.units = [knight, destroyed_enemy, live_candidate, engaged_enemy]
    game.rebuild_entity_registry()

    game._on_fight_attacks_resolved_imperial_knights_questoris_companions(
        attacker_unit=knight,
        killing_models_by_target={destroyed_enemy: [knight.models[0]]},
    )
    request = _find_request(game, decision_type=DECISION_CHOOSE_QUARRY, ability="imperial_knights_crushing_condemnation")
    assert request is not None
    option_payloads = [dict(getattr(option, "payload", {}) or {}) for option in list(request.options or [])]
    assert any(str(payload.get("action", "") or "") == "skip" for payload in option_payloads)
    candidate_ids = {str(payload.get("target_unit_id", "") or "") for payload in option_payloads}
    assert str(get_entity_id(live_candidate) or "") in candidate_ids
    assert str(get_entity_id(engaged_enemy) or "") not in candidate_ids

    rolls = iter([4, 4, 1, 2, 6, 3])
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _expr: next(rolls))
    starting_wounds = int(live_candidate.models[0].wounds or 0)
    _resolve_option(
        game,
        request,
        player_id=ik_player.id,
        target_unit_id=str(get_entity_id(live_candidate) or ""),
    )

    assert int(live_candidate.models[0].wounds or 0) == starting_wounds - 3
    assert bool(ik_army.imperial_knights_detachments.is_questoris_companions_enhancement_expended(knight))
