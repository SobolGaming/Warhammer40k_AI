from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
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
            {"name": str(entry), "description": "", "type": "Abilities", "parameter": None}
            for entry in list(abilities or [])
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
    ik_army = Army.with_detachment("Imperial Knights", detachment_type="Spearhead-At-Arms")
    ik_army.faction_id = "QI"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    ik_player = Player("IK", PlayerControl.REMOTE, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    return game, ik_army, enemy_army, ik_player, enemy_player


def _place_unit(unit: Unit, x: float, y: float):
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _bondsman_request_for_source(game: Game, source_unit: Unit):
    source_id = str(get_entity_id(source_unit) or "")
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "bondsman":
            continue
        if str(ctx.get("source_unit_id", "") or "") == source_id:
            return request
    return None


def _option_selected_ids(option) -> list[str]:
    payload = dict(getattr(option, "payload", {}) or {})
    selected_ids = [str(value or "").strip() for value in list(payload.get("selected_unit_ids", []) or []) if str(value or "").strip()]
    if selected_ids:
        deduped: list[str] = []
        for unit_id in selected_ids:
            if unit_id not in deduped:
                deduped.append(unit_id)
        return deduped
    unit_id = str(payload.get("target_unit_id", "") or payload.get("unit_id", "") or "").strip()
    if unit_id:
        return [unit_id]
    return []


def _find_option_by_selected_ids(request, selected_unit_ids: list[str]):
    expected = sorted(str(unit_id) for unit_id in list(selected_unit_ids or []))
    for option in list(getattr(request, "options", []) or []):
        selected = sorted(_option_selected_ids(option))
        if selected == expected:
            return option
    return None


def _find_option_by_target_count(request, count: int, *, exclude_unit_ids: set[str] | None = None):
    excluded = {str(unit_id) for unit_id in list(exclude_unit_ids or set())}
    for option in list(getattr(request, "options", []) or []):
        selected_ids = _option_selected_ids(option)
        if len(selected_ids) != int(count):
            continue
        if excluded and any(unit_id in excluded for unit_id in selected_ids):
            continue
        return option
    return None


def test_spearhead_armigers_gain_battleline_keyword_on_add():
    _game, ik_army, _enemy_army, _ik_player, _enemy_player = _build_game()
    armiger = _make_unit(
        "Armiger Warglaive",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    knight = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    ik_army.add_unit(armiger)
    ik_army.add_unit(knight)

    assert any(str(keyword).strip().upper() == "BATTLELINE" for keyword in list(getattr(armiger, "keywords", []) or []))
    assert not any(str(keyword).strip().upper() == "BATTLELINE" for keyword in list(getattr(knight, "keywords", []) or []))


def test_knightly_teachings_uses_12_range_while_not_honoured():
    game, ik_army, _enemy_army, _ik_player, _enemy_player = _build_game()
    source = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Paladin's Duty (Bondsman)"],
    )
    near_a = _make_unit(
        "Armiger A",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    near_b = _make_unit(
        "Armiger B",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    far_c = _make_unit(
        "Armiger C",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    for unit in (source, near_a, near_b, far_c):
        ik_army.add_unit(unit)
    game.map.units = [source, near_a, near_b, far_c]
    _place_unit(source, 0.0, 0.0)
    _place_unit(near_a, 10.0, 0.0)
    _place_unit(near_b, 12.0, 0.0)
    _place_unit(far_c, 18.0, 0.0)
    game.rebuild_entity_registry()

    game.start_command_phase()
    request = _bondsman_request_for_source(game, source)
    assert request is not None

    near_option = _find_option_by_selected_ids(
        request,
        [str(get_entity_id(near_a) or ""), str(get_entity_id(near_b) or "")],
    )
    assert near_option is not None

    far_combo = _find_option_by_selected_ids(
        request,
        [str(get_entity_id(near_a) or ""), str(get_entity_id(near_b) or ""), str(get_entity_id(far_c) or "")],
    )
    assert far_combo is None


def test_knightly_teachings_honoured_range_and_multi_target_apply():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    source = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Paladin's Duty (Bondsman)"],
    )
    armigers = [
        _make_unit(
            f"Armiger {idx}",
            faction_name="Imperial Knights",
            keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
            faction_keywords=["IMPERIAL KNIGHTS"],
        )
        for idx in ("A", "B", "C")
    ]
    for unit in [source, *armigers]:
        ik_army.add_unit(unit)
    game.map.units = [source, *armigers]
    _place_unit(source, 0.0, 0.0)
    _place_unit(armigers[0], 10.0, 0.0)
    _place_unit(armigers[1], 12.0, 0.0)
    _place_unit(armigers[2], 18.0, 0.0)
    ik_army.code_chivalric.honoured = True
    ik_army.code_chivalric_honoured = True
    game.rebuild_entity_registry()

    game.start_command_phase()
    request = _bondsman_request_for_source(game, source)
    assert request is not None

    selected_ids = [str(get_entity_id(unit) or "") for unit in list(armigers)]
    option = _find_option_by_selected_ids(request, selected_ids)
    assert option is not None

    outcome = resolve_decision_command(game, request, option.option_id, player_id=ik_player.id)
    assert bool(getattr(outcome, "ok", False))
    for unit in armigers:
        assert bool(getattr(unit, "special_rules", {}).get("bondsman_active"))


def test_knightly_teachings_same_ability_second_source_cannot_multi_target_after_first_use():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    source_a = _make_unit(
        "Knight Paladin Alpha",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Paladin's Duty (Bondsman)"],
    )
    source_b = _make_unit(
        "Knight Paladin Beta",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Paladin's Duty (Bondsman)"],
    )
    armigers = [
        _make_unit(
            f"Armiger {idx}",
            faction_name="Imperial Knights",
            keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
            faction_keywords=["IMPERIAL KNIGHTS"],
        )
        for idx in range(1, 6)
    ]
    for unit in [source_a, source_b, *armigers]:
        ik_army.add_unit(unit)
    game.map.units = [source_a, source_b, *armigers]
    _place_unit(source_a, 0.0, 0.0)
    _place_unit(source_b, 2.0, 0.0)
    for idx, unit in enumerate(armigers):
        _place_unit(unit, 8.0 + float(idx), 0.0)
    game.rebuild_entity_registry()

    game.start_command_phase()
    request_a = _bondsman_request_for_source(game, source_a)
    request_b = _bondsman_request_for_source(game, source_b)
    assert request_a is not None
    assert request_b is not None

    first_pick = _find_option_by_target_count(request_a, 1)
    assert first_pick is not None
    first_outcome = resolve_decision_command(game, request_a, first_pick.option_id, player_id=ik_player.id)
    assert bool(getattr(first_outcome, "ok", False))
    selected_first_ids = set(_option_selected_ids(first_pick))

    second_multi = _find_option_by_target_count(request_b, 2, exclude_unit_ids=selected_first_ids)
    assert second_multi is not None
    second_outcome = resolve_decision_command(game, request_b, second_multi.option_id, player_id=ik_player.id)
    assert not bool(getattr(second_outcome, "ok", False))

    valid_second = _find_option_by_target_count(request_b, 1, exclude_unit_ids=selected_first_ids)
    assert valid_second is not None
    valid_outcome = resolve_decision_command(game, request_b, valid_second.option_id, player_id=ik_player.id)
    assert bool(getattr(valid_outcome, "ok", False))


def test_knightly_teachings_different_bondsman_abilities_track_first_use_separately():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    source_paladin = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Paladin's Duty (Bondsman)"],
    )
    source_errant = _make_unit(
        "Knight Errant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        abilities=["Errant's Duty (Bondsman)"],
    )
    armigers = [
        _make_unit(
            f"Armiger {idx}",
            faction_name="Imperial Knights",
            keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
            faction_keywords=["IMPERIAL KNIGHTS"],
        )
        for idx in range(1, 6)
    ]
    for unit in [source_paladin, source_errant, *armigers]:
        ik_army.add_unit(unit)
    game.map.units = [source_paladin, source_errant, *armigers]
    _place_unit(source_paladin, 0.0, 0.0)
    _place_unit(source_errant, 2.0, 0.0)
    for idx, unit in enumerate(armigers):
        _place_unit(unit, 8.0 + float(idx), 0.0)
    game.rebuild_entity_registry()

    game.start_command_phase()
    paladin_request = _bondsman_request_for_source(game, source_paladin)
    errant_request = _bondsman_request_for_source(game, source_errant)
    assert paladin_request is not None
    assert errant_request is not None

    paladin_pick = _find_option_by_target_count(paladin_request, 1)
    assert paladin_pick is not None
    paladin_outcome = resolve_decision_command(game, paladin_request, paladin_pick.option_id, player_id=ik_player.id)
    assert bool(getattr(paladin_outcome, "ok", False))
    selected_first_ids = set(_option_selected_ids(paladin_pick))

    errant_multi = _find_option_by_target_count(errant_request, 2, exclude_unit_ids=selected_first_ids)
    assert errant_multi is not None
    errant_outcome = resolve_decision_command(game, errant_request, errant_multi.option_id, player_id=ik_player.id)
    assert bool(getattr(errant_outcome, "ok", False))
