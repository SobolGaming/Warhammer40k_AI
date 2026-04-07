from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
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
        self.loadout = "This model is equipped with: nothing"


def _create_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_profile(*, range_val: str = "24", is_ranged: bool = True) -> WargearProfile:
    parent = SimpleNamespace(
        name="Slugga" if is_ranged else "Choppa",
        is_melee=lambda: not is_ranged,
        is_ranged=lambda: is_ranged,
    )
    data = {
        "range": str(range_val),
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_game(*, ork_units: list[Unit], enemy_units: list[Unit]):
    ork_army = Army.with_detachment("Orks", "Da Big Hunt")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"

    ork_player = Player("Ork Player", control=PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(ork_player)
    game.add_player(enemy_player)
    return game, ork_player, ork_army, enemy_army


def _find_da_big_hunt_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str((getattr(req, "context", {}) or {}).get("ability", "") or "") != "da_big_hunt_prey":
            continue
        return req
    return None


def test_da_big_hunt_queues_prey_selection_at_command_phase_start():
    beast_snagga = _create_unit(
        "Beast Snagga Boyz",
        keywords=["INFANTRY", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    enemy_vehicle = _create_unit("Enemy Tank", keywords=["VEHICLE"])
    enemy_character = _create_unit("Enemy Captain", keywords=["CHARACTER"])
    enemy_infantry = _create_unit("Enemy Troops", keywords=["INFANTRY"])
    game, _player, _ork_army, _enemy_army = _build_game(
        ork_units=[beast_snagga],
        enemy_units=[enemy_vehicle, enemy_character, enemy_infantry],
    )

    game.start_command_phase()

    request = _find_da_big_hunt_request(game)
    assert request is not None
    assert str(request.context.get("ability", "") or "") == "da_big_hunt_prey"

    option_targets = [
        str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")
        for opt in list(request.options or [])
    ]
    assert option_targets == [
        str(get_entity_id(enemy_character)),
        str(get_entity_id(enemy_vehicle)),
    ]


def test_da_big_hunt_applies_charge_reroll_and_ap_bonus_vs_selected_prey():
    beast_snagga = _create_unit(
        "Squighog Boyz",
        keywords=["MOUNTED", "BEAST SNAGGA"],
        faction_keywords=["ORKS"],
    )
    boyz = _create_unit(
        "Boyz",
        keywords=["INFANTRY"],
        faction_keywords=["ORKS"],
    )
    prey_unit = _create_unit("Enemy Battle Tank", keywords=["VEHICLE"])
    other_unit = _create_unit("Enemy Walker", keywords=["VEHICLE"])
    game, ork_player, ork_army, _enemy_army = _build_game(
        ork_units=[beast_snagga, boyz],
        enemy_units=[prey_unit, other_unit],
    )

    game.start_command_phase()
    request = _find_da_big_hunt_request(game)
    assert request is not None

    option_id = None
    for opt in list(request.options or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == str(get_entity_id(prey_unit)):
            option_id = str(getattr(opt, "option_id", "") or "")
            break
    assert option_id

    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(ork_player, "id", None),
        option_id=option_id,
        payload={},
    )
    apply_result = dispatch_decision(game, request, result)
    assert bool(apply_result.ok)

    mgr = getattr(ork_army, "orks_detachments", None)
    assert mgr is not None
    assert str(mgr.da_big_hunt_prey_unit_id or "") == str(get_entity_id(prey_unit))

    assert beast_snagga.can_reroll_charge_roll(target_unit=prey_unit, game_map=game.map, game=game) is True
    assert beast_snagga.can_reroll_charge_roll(target_unit=other_unit, game_map=game.map, game=game) is False
    assert boyz.can_reroll_charge_roll(target_unit=prey_unit, game_map=game.map, game=game) is False

    profile = _make_profile(range_val="24", is_ranged=True)
    beast_model = beast_snagga.models[0]
    boy_model = boyz.models[0]
    beast_keywords = list(getattr(beast_model, "keywords", []) or [])
    if "BEAST SNAGGA" not in [str(k).strip().upper() for k in beast_keywords]:
        beast_keywords.append("BEAST SNAGGA")
        beast_model.keywords = beast_keywords

    assert int(profile.get_effective_ap(beast_model, prey_unit)) == -1
    assert int(profile.get_effective_ap(beast_model, other_unit)) == 0
    assert int(profile.get_effective_ap(boy_model, prey_unit)) == 0
