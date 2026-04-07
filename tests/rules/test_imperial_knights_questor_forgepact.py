from __future__ import annotations

import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
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
        cost: int = 100,
        wounds: int = 12,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": str(int(wounds)),
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
    cost: int = 100,
    wounds: int = 12,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            cost=cost,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, points_limit: int = 2000):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ik_army = Army.with_detachment("Imperial Knights", detachment_type="Questor Forgepact")
    ik_army.faction_id = "QI"
    ik_army.points_limit = int(points_limit)
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    ik_player = Player("IK", PlayerControl.REMOTE, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    return game, ik_army, enemy_army, ik_player, enemy_player


def _make_ranged_profile(*, strength: str = "4") -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Test Carbine",
            "is_melee": staticmethod(lambda: False),
            "is_ranged": staticmethod(lambda: True),
        },
    )()
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "3+",
        "S": str(strength),
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Test Carbine", wargear_data=data, parent_wargear=parent)


def _apply_enhancement(unit: Unit, *, enh_id: str, name: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enh_id),
        name=str(name),
        faction_id="QI",
        detachment="Questor Forgepact",
        detachment_id="000000988",
        points=0,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _find_choose_quarry_request(game: Game, ability_key: str):
    for req in list(game.decision_queue.list() or []):
        ctx = dict(getattr(req, "context", {}) or {})
        if req.decision_type != DECISION_CHOOSE_QUARRY:
            continue
        if str(ctx.get("ability", "") or "") != str(ability_key):
            continue
        return req
    return None


def _find_option_id_for_unit(request, unit) -> str:
    unit_id = str(get_entity_id(unit) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == unit_id:
            return str(option.option_id)
    return ""


def test_questor_forgepact_sacristan_pledge_heals_one_lost_wound():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        wounds=12,
    )
    ik_army.add_unit(knight)
    game.map.units = [knight]
    knight.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    knight.models[0].wounds = 9

    mgr = ik_army.imperial_knights_detachments
    mgr.on_command_phase_start(game=game, player=ik_player)

    assert int(knight.models[0].wounds or 0) == 10


def test_questor_forgepact_sacristan_pledge_uses_d3_with_tech_priest_support(monkeypatch):
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Errant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        wounds=12,
    )
    dominus = _make_unit(
        "Tech-priest Dominus",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "TECH-PRIEST", "CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=5,
    )
    ik_army.add_unit(knight)
    ik_army.add_unit(dominus)
    game.map.units = [knight, dominus]
    knight.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    dominus.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    knight.models[0].wounds = 7

    monkeypatch.setattr(
        "warhammer40k_ai.rules.imperial_knights_detachments.get_roll",
        lambda _expr: 3,
    )
    mgr = ik_army.imperial_knights_detachments
    mgr.on_command_phase_start(game=game, player=ik_player)

    assert int(knight.models[0].wounds or 0) == 10


def test_questor_forgepact_divine_inspiration_rerolls_hit_and_wound_ones_within_6_of_knight():
    game, ik_army, enemy_army, _ik_player, _enemy_player = _build_game()
    skitarii = _make_unit(
        "Skitarii Rangers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=10,
    )
    knight = _make_unit(
        "Knight Warden",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        wounds=12,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=10,
    )
    ik_army.add_unit(skitarii)
    ik_army.add_unit(knight)
    enemy_army.add_unit(enemy)
    game.map.units = [skitarii, knight, enemy]
    skitarii.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    knight.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)

    profile = _make_ranged_profile(strength="5")
    hit_result = profile._hit_target_with_tracking(
        enemy,
        skitarii.models[0],
        {"distance_to_target": 10.0},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    wound_result = profile._wound_target_with_tracking(
        enemy,
        skitarii.models[0],
        {"distance_to_target": 10.0},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )

    assert 1 in list(hit_result.get("reroll_values", []) or [])
    assert any("Divine Inspiration" in str(reason) for reason in list(hit_result.get("reroll_value_reasons", []) or []))
    assert 1 in list(wound_result.get("reroll_values", []) or [])
    assert any("Divine Inspiration" in str(reason) for reason in list(wound_result.get("reroll_value_reasons", []) or []))


def test_questor_forgepact_knight_of_the_opus_machina_rerolls_hit_ones_when_near_admech():
    game, ik_army, enemy_army, _ik_player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Knight Gallant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "CHARACTER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        wounds=12,
    )
    skitarii = _make_unit(
        "Skitarii Rangers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=10,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=10,
    )
    ik_army.add_unit(bearer)
    ik_army.add_unit(skitarii)
    enemy_army.add_unit(enemy)
    _apply_enhancement(bearer, enh_id="000009761003", name="Knight of the Opus Machina")
    game.map.units = [bearer, skitarii, enemy]
    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    skitarii.models[0].set_location(4.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(12.0, 0.0, 0.0, 0.0)

    profile = _make_ranged_profile(strength="5")
    hit_result = profile._hit_target_with_tracking(
        enemy,
        bearer.models[0],
        {"distance_to_target": 12.0},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )

    assert 1 in list(hit_result.get("reroll_values", []) or [])
    assert any("Knight of the Opus Machina" in str(reason) for reason in list(hit_result.get("reroll_value_reasons", []) or []))


def test_questor_forgepact_magos_questoris_grants_lone_operative_and_queues_heal_target():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Tech-priest Dominus",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "TECH-PRIEST", "CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=5,
    )
    knight = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        wounds=12,
    )
    other_knight = _make_unit(
        "Knight Errant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        wounds=12,
    )
    ik_army.add_unit(bearer)
    ik_army.add_unit(knight)
    ik_army.add_unit(other_knight)
    _apply_enhancement(bearer, enh_id="000009761004", name="Magos Questoris")
    game.map.units = [bearer, knight, other_knight]
    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    knight.models[0].set_location(2.5, 0.0, 0.0, 0.0)
    other_knight.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    knight.models[0].wounds = 8
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.rebuild_entity_registry()

    assert bearer.has_lone_operative()

    game._on_phase_start_imperial_knights_enhancements(player=ik_player, phase=BattleRoundPhases.COMMAND_PHASE)
    req = _find_choose_quarry_request(game, "imperial_knights_magos_questoris")
    assert req is not None
    option_id = _find_option_id_for_unit(req, knight)
    assert bool(option_id)

    invalid = resolve_decision_command(game, req, "invalid-option-id", player_id=ik_player.id)
    assert not bool(getattr(invalid, "ok", False))

    applied = resolve_decision_command(game, req, option_id, player_id=ik_player.id)
    assert bool(getattr(applied, "ok", False))
    assert int(knight.models[0].wounds or 0) == 10


def test_questor_forgepact_vocifer_magnificat_applies_friendly_and_enemy_leadership_aura():
    game, ik_army, enemy_army, _ik_player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Knight Warden",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "CHARACTER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        wounds=12,
    )
    skitarii = _make_unit(
        "Skitarii Rangers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=10,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=10,
    )
    ik_army.add_unit(bearer)
    ik_army.add_unit(skitarii)
    enemy_army.add_unit(enemy)
    _apply_enhancement(bearer, enh_id="000009761005", name="Vocifer Magnificat (Aura)")
    game.map.units = [bearer, skitarii, enemy]
    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    skitarii.models[0].set_location(4.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(5.0, 0.0, 0.0, 0.0)

    assert int(skitarii.models[0].leadership or 0) == 5
    assert int(enemy.models[0].leadership or 0) == 7


def test_questor_forgepact_validate_detachment_rules_rejects_non_allowed_admech_unit():
    _game, ik_army, _enemy_army, _ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Gallant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    illegal_admech = _make_unit(
        "Kataphron Breachers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    ik_army.add_unit(knight)
    ik_army.add_unit(illegal_admech)

    with pytest.raises(ArmyValidationError):
        ik_army.validate_detachment_rules()


def test_questor_forgepact_validate_detachment_rules_rejects_admech_warlord():
    _game, ik_army, _enemy_army, _ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Castellan",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    admech = _make_unit(
        "Skitarii Marshal",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    ik_army.add_unit(knight)
    ik_army.add_unit(admech)
    admech.is_warlord = True
    ik_army.warlord = admech

    with pytest.raises(ArmyValidationError):
        ik_army.validate_detachment_rules()


def test_questor_forgepact_validate_detachment_rules_rejects_allied_points_cap():
    _game, ik_army, _enemy_army, _ik_player, _enemy_player = _build_game(points_limit=1000)
    knight = _make_unit(
        "Knight Crusader",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        cost=400,
    )
    admech_a = _make_unit(
        "Skitarii Rangers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        cost=150,
    )
    admech_b = _make_unit(
        "Skitarii Vanguard",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        cost=150,
    )
    ik_army.add_unit(knight)
    ik_army.add_unit(admech_a)
    ik_army.add_unit(admech_b)

    with pytest.raises(ArmyValidationError):
        ik_army.validate_detachment_rules()
