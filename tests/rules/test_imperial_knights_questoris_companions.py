from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_CHIVALRIC_OATH
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.code_chivalric import DEED_TALLY, QUALITY_EAGER, QUALITY_LEGACY
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        abilities=None,
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
        self.datasheets_abilities = [
            {"name": str(name), "description": "", "type": "Abilities", "parameter": None}
            for name in list(abilities or [])
        ]
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
    abilities=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ik_army = Army.with_detachment("Imperial Knights", detachment_type="Questoris Companions")
    ik_army.faction_id = "QI"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    ik_player = Player("IK", PlayerControl.REMOTE, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    return game, ik_army, enemy_army, ik_player, enemy_player


def _find_chivalric_request(game: Game, oath_kind: str):
    kind = str(oath_kind or "").strip().lower()
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_CHIVALRIC_OATH:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("oath_kind", "") or "").strip().lower() == kind:
            return req
    return None


def test_heroes_of_legend_queues_additional_oath_and_keeps_fulfilled_qualities_active():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Code Chivalric"],
    )
    ik_army.add_unit(knight)
    game.map.units = [knight]
    game.rebuild_entity_registry()

    code_mgr = ik_army.code_chivalric
    code_mgr.select_deed("LAY_LOW", game=game, player=ik_player)
    code_mgr.select_quality(QUALITY_EAGER)
    code_mgr._grant_honoured(player=ik_player)

    ik_mgr = ik_army.imperial_knights_detachments
    ik_mgr.on_command_phase_start(game=game, player=ik_player)

    deed_request = _find_chivalric_request(game, "deed")
    assert deed_request is not None
    deed_keys = {
        str((getattr(opt, "payload", {}) or {}).get("choice_key", "") or "").strip().upper()
        for opt in list(deed_request.options or [])
    }
    assert "LAY_LOW" not in deed_keys
    assert "RECLAIM" in deed_keys
    assert "TALLY" in deed_keys

    deed_option = next(
        opt for opt in list(deed_request.options or [])
        if str((getattr(opt, "payload", {}) or {}).get("choice_key", "") or "").strip().upper() == "RECLAIM"
    )
    deed_result = resolve_decision_command(game, deed_request, deed_option.option_id, player_id=ik_player.id)
    assert bool(getattr(deed_result, "ok", False))

    quality_request = _find_chivalric_request(game, "quality")
    assert quality_request is not None
    quality_option = next(
        opt for opt in list(quality_request.options or [])
        if str((getattr(opt, "payload", {}) or {}).get("choice_key", "") or "").strip().upper() == QUALITY_LEGACY.key
    )
    quality_result = resolve_decision_command(game, quality_request, quality_option.option_id, player_id=ik_player.id)
    assert bool(getattr(quality_result, "ok", False))

    assert code_mgr.selected_quality_key == QUALITY_LEGACY.key
    active_quality_keys = set(code_mgr.get_active_quality_keys())
    assert QUALITY_EAGER.key in active_quality_keys
    assert QUALITY_LEGACY.key in active_quality_keys
    assert int(knight.get_effective_model_characteristic(knight.models[0], "movement")) == 12
    assert int(knight.get_effective_model_characteristic(knight.models[0], "objective_control")) == 10


def test_heroes_of_legend_additional_oath_completion_grants_one_command_point():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Errant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Code Chivalric"],
    )
    ik_army.add_unit(knight)
    game.map.units = [knight]

    code_mgr = ik_army.code_chivalric
    code_mgr.select_deed("LAY_LOW", game=game, player=ik_player)
    code_mgr.select_quality(QUALITY_EAGER)
    code_mgr._grant_honoured(player=ik_player)

    code_mgr.select_deed(DEED_TALLY.key, game=game, player=ik_player)
    code_mgr.select_quality(QUALITY_LEGACY)
    code_mgr.selected_deed_random = True
    code_mgr.selected_quality_random = True
    code_mgr.deed_completed = False
    code_mgr.enemy_units_destroyed_this_round = 3
    cp_before = int(getattr(ik_player, "command_points", 0) or 0)

    code_mgr.check_end_of_battle_round(game=game, battle_round=2)

    assert int(getattr(ik_player, "command_points", 0) or 0) == cp_before + 1
    assert bool(code_mgr.deed_completed)


def test_heroes_of_legend_random_duplicate_roll_selects_unused_oath_result(monkeypatch):
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Gallant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Code Chivalric"],
    )
    ik_army.add_unit(knight)

    code_mgr = ik_army.code_chivalric
    code_mgr.select_deed("LAY_LOW", game=game, player=ik_player)
    code_mgr.select_quality(QUALITY_EAGER)
    code_mgr._grant_honoured(player=ik_player)
    assert code_mgr.prepare_next_oath_selection(game=game, player=ik_player)

    monkeypatch.setattr("warhammer40k_ai.rules.code_chivalric.get_roll", lambda _expr: 1)
    rolled = code_mgr.roll_deed(game=game, player=ik_player)

    assert str((rolled or {}).get("deed").key) != "LAY_LOW"
    assert str(code_mgr.selected_deed_key or "") != "LAY_LOW"


def test_valours_reward_expended_enhancements_clear_when_oath_is_fulfilled():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Crusader",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Code Chivalric"],
    )
    knight.enhancement = SimpleNamespace(name="Herald of Triumph")
    ik_army.add_unit(knight)
    game.map.units = [knight]

    ik_mgr = ik_army.imperial_knights_detachments
    assert ik_mgr.mark_questoris_companions_enhancement_expended(knight)
    assert ik_mgr.is_questoris_companions_enhancement_expended(knight)

    code_mgr = ik_army.code_chivalric
    code_mgr.select_deed("LAY_LOW", game=game, player=ik_player)
    code_mgr.select_quality(QUALITY_EAGER)
    code_mgr._grant_honoured(player=ik_player)

    assert not ik_mgr.is_questoris_companions_enhancement_expended(knight)
