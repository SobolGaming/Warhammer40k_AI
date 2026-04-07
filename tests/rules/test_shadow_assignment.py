from warhammer40k_ai.engine.decision_kinds import DECISION_ASSIGN_TRANSPORT, DECISION_SHADOW_ASSIGNMENT
from warhammer40k_ai.engine.decision_requests import build_shadow_assignment_requests
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.imperial_agents_shadow_assignment import get_shadow_assignment_catalog
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        cost: int,
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}-id"
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def _shadow_assignment_entry():
    return {
        "ability_data": {
            "name": "SHADOW ASSIGNMENT",
            "faction_id": "AOI",
            "description": "Optional assassin replacement.",
            "legend": "",
        },
        "type": "Faction",
        "parameter": "",
    }


def _make_unit(name: str, *, cost: int, with_shadow_assignment: bool = False) -> Unit:
    abilities = [_shadow_assignment_entry()] if with_shadow_assignment else []
    datasheet = MockDatasheet(
        name,
        cost=cost,
        keywords=["OFFICIO ASSASSINORUM"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
        abilities=abilities,
    )
    return Unit(datasheet)


def _make_game_with_imperial_agents_army():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    player_one = Player("P1", PlayerControl.LOCAL, None)
    player_two = Player("P2", PlayerControl.REMOTE, None)
    game.add_player(player_one)
    game.add_player(player_two)

    army_one = Army.with_detachment("Imperial Agents", "Imperialis Fleet")
    army_two = Army.with_detachment("Space Marines", "Gladius")
    army_one.faction_id = "AOI"
    army_two.faction_id = "SM"
    player_one.set_army(army_one)
    player_two.set_army(army_two)

    return game, player_one, army_one


def _refresh_registry(game) -> None:
    rebuild = getattr(game, "rebuild_entity_registry", None)
    if callable(rebuild):
        rebuild()


def _first_replace_option(request):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == "replace":
            return option
    return None


def test_build_shadow_assignment_requests_for_aoi_army():
    game, player, army = _make_game_with_imperial_agents_army()
    source = _make_unit("Callidus Assassin", cost=500, with_shadow_assignment=True)
    army.add_unit(source)
    _refresh_registry(game)

    requests = build_shadow_assignment_requests(game, army.units, queue_requests=False)

    assert len(requests) == 1
    request = requests[0]
    assert request.decision_type == DECISION_SHADOW_ASSIGNMENT
    assert request.player_id == player.id
    assert str(getattr(request, "context", {}).get("unit_id", "") or "") == get_entity_id(source)

    options = list(getattr(request, "options", []) or [])
    assert options
    assert options[0].label == "None"
    assert _first_replace_option(request) is not None

    replacement_names = {
        str(dict(getattr(option, "payload", {}) or {}).get("replacement_name", "") or "")
        for option in options
        if str(dict(getattr(option, "payload", {}) or {}).get("action", "") or "").strip().lower() == "replace"
    }
    assert "Callidus Assassin" not in replacement_names


def test_shadow_assignment_replace_applies_selected_assassin():
    game, player, army = _make_game_with_imperial_agents_army()
    source = _make_unit("Callidus Assassin", cost=500, with_shadow_assignment=True)
    army.add_unit(source)
    _refresh_registry(game)

    requests = build_shadow_assignment_requests(game, army.units, queue_requests=True)
    assert len(requests) == 1
    request = requests[0]

    replace_option = _first_replace_option(request)
    assert replace_option is not None
    expected_name = str(dict(getattr(replace_option, "payload", {}) or {}).get("replacement_name", "") or "")

    source_id = get_entity_id(source)
    result = resolve_decision_command(game, request, replace_option.option_id, player_id=player.id)

    assert result.ok is True
    army_unit_ids = {get_entity_id(unit) for unit in list(getattr(army, "units", []) or [])}
    assert source_id not in army_unit_ids
    assert expected_name in {str(getattr(unit, "name", "") or "") for unit in list(getattr(army, "units", []) or [])}


def test_shadow_assignment_invalid_replacement_is_rejected():
    game, player, army = _make_game_with_imperial_agents_army()
    source = _make_unit("Callidus Assassin", cost=1, with_shadow_assignment=True)
    army.add_unit(source)
    _refresh_registry(game)

    candidate = get_shadow_assignment_catalog()[0]
    source_id = get_entity_id(source)
    illegal_option = DecisionOption.create(
        "Illegal replacement",
        payload={
            "action": "replace",
            "unit_id": source_id,
            "replacement_name": candidate.name,
            "replacement_datasheet_id": candidate.datasheet_id,
            "replacement_points": int(candidate.points),
        },
    )
    request = DecisionRequest.create(
        DECISION_SHADOW_ASSIGNMENT,
        "Shadow Assignment",
        player_id=player.id,
        options=[illegal_option],
        context={"ability": "shadow_assignment", "unit_id": source_id},
    )
    game.request_decision(request)

    result = resolve_decision_command(game, request, illegal_option.option_id, player_id=player.id)

    assert result.ok is False
    assert any("not legal" in str(err or "").lower() for err in list(getattr(result, "errors", ()) or ()))
    assert game.decision_queue.get(request.decision_id) is not None


def test_shadow_assignment_rewrites_pending_unit_ids_after_replacement():
    game, player, army = _make_game_with_imperial_agents_army()
    source = _make_unit("Callidus Assassin", cost=500, with_shadow_assignment=True)
    army.add_unit(source)
    _refresh_registry(game)

    source_id = get_entity_id(source)
    requests = build_shadow_assignment_requests(game, army.units, queue_requests=True)
    assert len(requests) == 1
    shadow_request = requests[0]

    dependent_option = DecisionOption.create(
        "No transport",
        payload={
            "unit_id": source_id,
            "transport_id": None,
            "nested": {"unit_ids": [source_id]},
        },
    )
    dependent_request = DecisionRequest.create(
        DECISION_ASSIGN_TRANSPORT,
        "Dependent formation request",
        player_id=player.id,
        options=[dependent_option],
        context={"unit_id": source_id, "related": [source_id]},
    )
    game.request_decision(dependent_request)

    replace_option = _first_replace_option(shadow_request)
    assert replace_option is not None
    result = resolve_decision_command(game, shadow_request, replace_option.option_id, player_id=player.id)

    assert result.ok is True
    pending = game.decision_queue.get(dependent_request.decision_id)
    assert pending is not None

    rewritten_id = str(getattr(pending, "context", {}).get("unit_id", "") or "")
    assert rewritten_id
    assert rewritten_id != source_id
    assert game.entity_registry.get(rewritten_id, kind="unit") is not None

    related = list(getattr(pending, "context", {}).get("related", []) or [])
    assert related and str(related[0]) == rewritten_id

    payload_after = dict(getattr(pending.options[0], "payload", {}) or {})
    assert str(payload_after.get("unit_id", "") or "") == rewritten_id
    nested_ids = list(dict(payload_after.get("nested", {}) or {}).get("unit_ids", []) or [])
    assert nested_ids and str(nested_ids[0]) == rewritten_id
