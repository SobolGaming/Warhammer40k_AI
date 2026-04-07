from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


OMNISSIAHS_BLESSING_TEXT = (
    "In your Command phase, select one friendly ADEPTUS MECHANICUS model within 3\" of this model. "
    "That model regains up to D3 lost wounds and, if it is a VEHICLE model, until the start of your next Command phase, "
    "that model has the Feel No Pain 5+ ability. Each model can only be selected for this ability once per Command phase."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Adeptus Mechanicus"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Other")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", PlayerControl.REMOTE, army=admech_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, admech_army, enemy_army, p1, p2


def _find_master_of_mechanisms_request(game: Game):
    return next(
        req
        for req in list(game.decision_queue.list() or [])
        if str((getattr(req, "context", {}) or {}).get("ability", "")) == "master_of_mechanisms"
    )


def _option_for_unit(request, unit: Unit):
    uid = str(get_entity_id(unit))
    return next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "")) == uid
    )


def _build_omnissiahs_blessing_ability():
    return {
        "name": "Omnissiah's Blessing",
        "description": OMNISSIAHS_BLESSING_TEXT,
        "type": "Datasheet",
        "parameter": "",
    }


def test_omnissiahs_blessing_heals_and_grants_vehicle_fnp_until_next_command_phase():
    enginseer = _make_unit(
        "Tech-priest Enginseer",
        abilities=[_build_omnissiahs_blessing_ability()],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    vehicle = _make_unit(
        "Onager Dunecrawler",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    infantry = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )

    game, admech_army, enemy_army, p1, _p2 = _build_game()
    admech_army.add_unit(enginseer)
    admech_army.add_unit(vehicle)
    admech_army.add_unit(infantry)
    enemy_army.units = []
    game.map.units = [enginseer, vehicle, infantry]
    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    enginseer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    vehicle.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    infantry.models[0].set_location(2.5, 0.0, 0.0, 0.0)
    vehicle.models[0].wounds = int(vehicle.models[0].wounds) - 3

    game._on_phase_start_master_of_mechanisms(player=p1, phase=game.phase)
    req = _find_master_of_mechanisms_request(game)
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert str((req.context or {}).get("ability", "")) == "master_of_mechanisms"
    assert int((req.context or {}).get("fnp_value", 0) or 0) == 5
    assert bool((req.context or {}).get("target_requires_vehicle", True)) is False

    vehicle_option = _option_for_unit(req, vehicle)
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        result = resolve_decision_command(game, req, vehicle_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    assert int(vehicle.models[0].wounds) == 3
    sr = getattr(vehicle, "special_rules", {}) or {}
    assert bool(sr.get("master_of_mechanisms_fnp_active", False)) is True
    assert int(sr.get("master_of_mechanisms_fnp_value", 0) or 0) == 5
    assert bool(sr.get("master_of_mechanisms_hit_bonus_active", False)) is False
    fnp_entries = list(vehicle.models[0].get_temporary_fnp_entries() or [])
    assert (5, None) in fnp_entries

    game.turn = 3
    game._on_phase_start_master_of_mechanisms_cleanup(player=p1, phase=BattleRoundPhases.COMMAND_PHASE)
    sr_after = getattr(vehicle, "special_rules", {}) or {}
    assert bool(sr_after.get("master_of_mechanisms_fnp_active", False)) is False
    assert list(vehicle.models[0].get_temporary_fnp_entries() or []) == []


def test_omnissiahs_blessing_non_vehicle_target_heals_only():
    enginseer = _make_unit(
        "Tech-priest Enginseer",
        abilities=[_build_omnissiahs_blessing_ability()],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    infantry = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )

    game, admech_army, enemy_army, p1, _p2 = _build_game()
    admech_army.add_unit(enginseer)
    admech_army.add_unit(infantry)
    enemy_army.units = []
    game.map.units = [enginseer, infantry]
    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    enginseer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    infantry.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    infantry.models[0].wounds = int(infantry.models[0].wounds) - 2

    game._on_phase_start_master_of_mechanisms(player=p1, phase=game.phase)
    req = _find_master_of_mechanisms_request(game)
    infantry_option = _option_for_unit(req, infantry)
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=1):
        result = resolve_decision_command(game, req, infantry_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    assert int(infantry.models[0].wounds) == 3
    assert list(infantry.models[0].get_temporary_fnp_entries() or []) == []


def test_omnissiahs_blessing_rejects_invalid_enemy_target():
    enginseer = _make_unit(
        "Tech-priest Enginseer",
        abilities=[_build_omnissiahs_blessing_ability()],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    friendly_vehicle = _make_unit(
        "Skorpius Disintegrator",
        keywords=["VEHICLE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    game, admech_army, enemy_army, p1, _p2 = _build_game()
    admech_army.add_unit(enginseer)
    admech_army.add_unit(friendly_vehicle)
    enemy_army.add_unit(enemy_unit)
    game.map.units = [enginseer, friendly_vehicle, enemy_unit]
    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    enginseer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    friendly_vehicle.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    enemy_unit.models[0].set_location(2.5, 0.0, 0.0, 0.0)

    game._on_phase_start_master_of_mechanisms(player=p1, phase=game.phase)
    req = _find_master_of_mechanisms_request(game)
    valid_option = _option_for_unit(req, friendly_vehicle)
    valid_option.payload["target_unit_id"] = str(get_entity_id(enemy_unit))

    result = resolve_decision_command(game, req, valid_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is False
