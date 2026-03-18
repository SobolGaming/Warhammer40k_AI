from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        keywords=None,
        faction_keywords=None,
        model_count: int = 5,
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ADEPTUS ASTARTES"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(
    name: str,
    *,
    datasheet_id: str,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_request(game: Game, *, ability: str, ability_name: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != ability:
            continue
        if str(ctx.get("ability_name", "") or "") != ability_name:
            continue
        return req
    return None


def _option_for_unit(request, unit: Unit):
    target_id = str(get_entity_id(unit) or "")
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        selected_unit_id = str(
            payload.get("selected_unit_id", "")
            or payload.get("target_unit_id", "")
            or payload.get("unit_id", "")
            or ""
        )
        if selected_unit_id == target_id:
            return opt
    return None


def test_uriel_ventris_master_of_the_fleet_queues_selection_and_grants_deep_strike():
    game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
    uriel = _actual_unit("Uriel Ventris", datasheet_id="000000121")
    phobos = _mock_unit(
        "Infiltrator Squad",
        datasheet_id="sm-phobos",
        keywords=["PHOBOS", "INFANTRY"],
    )
    gravis = _mock_unit(
        "Aggressor Squad",
        datasheet_id="sm-gravis",
        keywords=["GRAVIS", "INFANTRY"],
    )
    tacticus = _mock_unit(
        "Intercessor Squad",
        datasheet_id="sm-tacticus",
        keywords=["TACTICUS", "INFANTRY"],
    )
    plain_infantry = _mock_unit(
        "Tactical Squad",
        datasheet_id="sm-plain",
        keywords=["INFANTRY"],
    )
    vehicle = _mock_unit(
        "Ballistus Dreadnought",
        datasheet_id="sm-vehicle",
        keywords=["VEHICLE"],
    )

    for unit in (uriel, phobos, gravis, tacticus, plain_infantry, vehicle):
        sm_army.add_unit(unit)
    _register_units(game, uriel, phobos, gravis, tacticus, plain_infantry, vehicle)

    game.execute_declare_battle_formations_phase()

    request = _find_request(
        game,
        ability="declare_selected_unit_gain_deep_strike",
        ability_name="Master of the Fleet",
    )
    assert request is not None
    assert str(getattr(request, "player_id", "") or "") == str(sm_player.id or "")

    candidate_ids = {
        str(v or "").strip()
        for v in list((getattr(request, "context", {}) or {}).get("candidate_unit_ids", []) or [])
        if str(v or "").strip()
    }
    assert str(get_entity_id(phobos) or "") in candidate_ids
    assert str(get_entity_id(gravis) or "") in candidate_ids
    assert str(get_entity_id(tacticus) or "") in candidate_ids
    assert str(get_entity_id(plain_infantry) or "") not in candidate_ids
    assert str(get_entity_id(vehicle) or "") not in candidate_ids

    assert _option_for_unit(request, phobos) is not None
    assert _option_for_unit(request, plain_infantry) is None
    assert _option_for_unit(request, vehicle) is None

    option = _option_for_unit(request, phobos)
    result = resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    assert bool(phobos.has_deep_strike()) is True
    assert bool(gravis.has_deep_strike()) is False
    assert bool(tacticus.has_deep_strike()) is False
    assert bool(plain_infantry.has_deep_strike()) is False
    assert bool(vehicle.has_deep_strike()) is False
