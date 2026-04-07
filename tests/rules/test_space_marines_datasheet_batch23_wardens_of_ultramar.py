from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
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
        self.attached_to_names = []


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(name: str, *, datasheet_id: str, faction_name: str = "Space Marines", keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.attacker_index = 0
    game.defender_index = 1
    game.current_player_index = 0
    return game, sm_army, enemy_army, sm_player, enemy_player


def _set_unit_position(unit: Unit, x: float, y: float, *, spacing: float = 1.0) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * float(spacing), float(y), 0.0, 0.0)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    for unit in (leader, bodyguard):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()
        else:
            unit._ability_cache = {}


def _find_model(unit: Unit, fragment: str):
    fragment_l = str(fragment or "").strip().lower()
    return next(model for model in list(unit.models or []) if fragment_l in str(getattr(model, "name", "") or "").lower())


def _find_redeploy_request(game: Game, *, player_id: str, ability_name: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str(getattr(req, "player_id", "") or "") != str(player_id):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability_name", "") or "") != str(ability_name):
            continue
        return req
    return None


def test_wardens_of_ultramar_second_company_banner_grants_oc_and_titus_conditional_leadership_bonus() -> None:
    game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()

    wardens = _actual_unit("Wardens of Ultramar", datasheet_id="000004188")
    titus = _actual_unit("Captain Titus", datasheet_id="000004187")
    sm_army.add_unit(wardens)
    sm_army.add_unit(titus)
    game.map.units = [wardens, titus]
    game.rebuild_entity_registry()

    beneficiary = _find_model(wardens, "Lucia Vestha")
    ancient = _find_model(wardens, "Ancient Gadriel")
    oc_with_ancient = wardens.get_effective_model_characteristic(beneficiary, "objective_control", game_map=game.map)
    ld_without_titus = wardens.get_effective_model_characteristic(beneficiary, "leadership", game_map=game.map)

    _attach_leader(wardens, titus)
    oc_with_ancient_and_titus = wardens.get_effective_model_characteristic(beneficiary, "objective_control", game_map=game.map)
    ld_with_titus = wardens.get_effective_model_characteristic(beneficiary, "leadership", game_map=game.map)

    ancient.wounds = 0
    oc_without_ancient = wardens.get_effective_model_characteristic(beneficiary, "objective_control", game_map=game.map)
    ld_without_ancient = wardens.get_effective_model_characteristic(beneficiary, "leadership", game_map=game.map)

    assert oc_with_ancient == oc_without_ancient + 1
    assert oc_with_ancient_and_titus == oc_without_ancient + 1
    assert ld_without_titus == ld_without_ancient
    assert ld_with_titus == ld_without_ancient - 1


def test_wardens_of_ultramar_strategium_command_redeploy_filters_to_adeptus_astartes_and_allows_reserves() -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()

    wardens = _actual_unit("Wardens of Ultramar", datasheet_id="000004188")
    intercessors = _actual_unit("Intercessor Squad", datasheet_id="000001157")
    allied_unit = _mock_unit(
        "Allied Unit",
        datasheet_id="allied-unit",
        faction_name="Agents",
        keywords=["INFANTRY"],
        faction_keywords=["AGENTS OF THE IMPERIUM"],
    )
    enemy = _mock_unit(
        "Enemy Unit",
        datasheet_id="enemy-unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    for unit in (wardens, intercessors, allied_unit):
        sm_army.add_unit(unit)
        _set_unit_position(unit, 0.0, 0.0)
    enemy_army.add_unit(enemy)
    _set_unit_position(enemy, 24.0, 0.0)
    game.map.units = [wardens, intercessors, allied_unit, enemy]
    game.rebuild_entity_registry()

    has_redeploy, count, can_place_in_reserves = wardens.has_redeploy()
    assert bool(has_redeploy) is True
    assert int(count) == 3
    assert bool(can_place_in_reserves) is True

    cache = dict(getattr(wardens, "_ability_cache", {}) or {})
    assert list(cache.get("redeploy_filters", []) or []) == ["ADEPTUS ASTARTES"]
    assert bool(cache.get("redeploy_requires_source_on_battlefield", False)) is True
    assert bool(cache.get("redeploy_allow_embarked_transport_on_battlefield", False)) is True

    game.execute_redeploy_units_phase()
    request = _find_redeploy_request(game, player_id=sm_player.id, ability_name="Strategium Command")
    assert request is not None

    target_ids = {
        str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        for opt in list(getattr(request, "options", []) or [])
        if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
    }
    assert str(get_entity_id(intercessors.get_attached_unit_root()) or "") in target_ids
    assert str(get_entity_id(allied_unit.get_attached_unit_root()) or "") not in target_ids

    assert any(
        str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")) == str(get_entity_id(intercessors) or "")
        and str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "")).lower() == "strategic_reserves"
        for opt in list(getattr(request, "options", []) or [])
    )


def test_wardens_of_ultramar_strategium_command_triggers_when_embarked_transport_is_on_battlefield() -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()

    wardens = _actual_unit("Wardens of Ultramar", datasheet_id="000004188")
    transport = _actual_unit("Rhino", datasheet_id="000002723")
    intercessors = _actual_unit("Intercessor Squad", datasheet_id="000001157")
    enemy = _mock_unit(
        "Enemy Unit",
        datasheet_id="enemy-unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    for unit in (wardens, transport, intercessors):
        sm_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    game.map.units = [transport, intercessors, enemy]
    game.rebuild_entity_registry()

    wardens.embarked_in = transport
    transport.transport_passengers = [wardens]
    wardens.deployed = True
    wardens.reserve_status = "deployed"
    transport.deployed = True
    transport.reserve_status = "deployed"
    intercessors.deployed = True
    intercessors.reserve_status = "deployed"
    enemy.deployed = True
    enemy.reserve_status = "deployed"

    game.execute_redeploy_units_phase()
    request = _find_redeploy_request(game, player_id=sm_player.id, ability_name="Strategium Command")
    assert request is not None

    target_ids = {
        str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        for opt in list(getattr(request, "options", []) or [])
    }
    assert str(get_entity_id(intercessors) or "") in target_ids
