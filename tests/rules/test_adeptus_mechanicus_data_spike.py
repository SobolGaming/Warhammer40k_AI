from types import SimpleNamespace
from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


DATA_SPIKE_TEXT = (
    "At the start of the Fight phase, you can select one enemy VEHICLE unit within Engagement Range of this model's unit "
    "and roll one D6: on a 4+, that enemy unit suffers D6 mortal wounds and, until the end of the phase, the Weapon Skill "
    "characteristic of melee weapons equipped by that enemy unit is worsened by 1."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
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


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
) -> Unit:
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


def _make_data_spike_ability():
    return {
        "name": "Data-spike",
        "description": DATA_SPIKE_TEXT,
        "type": "Datasheet",
        "parameter": "",
    }


def _find_data_spike_request(game: Game):
    return next(
        req
        for req in list(game.decision_queue.list() or [])
        if str((getattr(req, "context", {}) or {}).get("ability", "")) == "data_spike"
    )


def test_data_spike_spec_parsing():
    source = _make_unit(
        "Tech-priest Dominus",
        abilities=[_make_data_spike_ability()],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    specs = source.model_start_fight_phase_data_spike_specs(source.models[0])
    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("threshold", 0) or 0) == 4
    assert str(spec.get("mortal_wounds", "")).upper() == "D6"
    assert int(spec.get("ws_penalty", 0) or 0) == 1


def test_data_spike_queues_and_applies_mortals_and_ws_penalty():
    source = _make_unit(
        "Tech-priest Dominus",
        abilities=[_make_data_spike_ability()],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy_vehicle = _make_unit("Enemy Tank", keywords=["VEHICLE"])

    game, admech_army, enemy_army, p1, _p2 = _build_game()
    admech_army.add_unit(source)
    enemy_army.add_unit(enemy_vehicle)
    game.map.units = [source, enemy_vehicle]
    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy_vehicle.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    source._apply_mortal_wounds_to_unit = Mock()

    game._on_phase_start_data_spike(player=p1, phase=game.phase)
    req = _find_data_spike_request(game)
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert str((req.options or [])[0].label) == "None"

    target_id = str(get_entity_id(enemy_vehicle))
    option_id = None
    for opt in list(req.options or []):
        if str((opt.payload or {}).get("target_unit_id", "")) == target_id:
            option_id = opt.option_id
            break
    assert option_id is not None

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4, 5]):
        result = resolve_decision_command(game, req, option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    source._apply_mortal_wounds_to_unit.assert_called_once()
    call_args = source._apply_mortal_wounds_to_unit.call_args
    assert call_args.args[0] is enemy_vehicle
    assert int(call_args.args[1]) == 5

    sr = enemy_vehicle.special_rules
    assert bool(sr.get("data_spike_ws_penalty_active")) is True
    assert int(sr.get("data_spike_ws_penalty", 0) or 0) == 1
    assert str(sr.get("data_spike_ws_penalty_expires_phase", "")).upper() == "FIGHT_PHASE"

    melee_profile = WargearProfile(
        "default",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Tank Treads", is_ranged=lambda: False, is_melee=lambda: True),
    )
    hit_result = melee_profile._hit_target_with_tracking(
        source,
        enemy_vehicle.models[0],
        {"target_model": source.models[0]},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit_result.get("base_skill", 0) or 0) == 5
    assert any("Data-spike" in str(effect) for effect in list(hit_result.get("special_effects", []) or []))

    game._on_phase_end_cleanup(player=p1, phase=game.phase)
    assert "data_spike_ws_penalty_active" not in enemy_vehicle.special_rules


def test_data_spike_roll_fail_applies_no_effect():
    source = _make_unit(
        "Tech-priest Dominus",
        abilities=[_make_data_spike_ability()],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy_vehicle = _make_unit("Enemy Tank", keywords=["VEHICLE"])

    game, admech_army, enemy_army, p1, _p2 = _build_game()
    admech_army.add_unit(source)
    enemy_army.add_unit(enemy_vehicle)
    game.map.units = [source, enemy_vehicle]
    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy_vehicle.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    source._apply_mortal_wounds_to_unit = Mock()

    game._on_phase_start_data_spike(player=p1, phase=game.phase)
    req = _find_data_spike_request(game)
    target_option = next(
        opt
        for opt in list(req.options or [])
        if str((opt.payload or {}).get("target_unit_id", "")) == str(get_entity_id(enemy_vehicle))
    )

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
        result = resolve_decision_command(game, req, target_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True
    source._apply_mortal_wounds_to_unit.assert_not_called()
    assert bool(enemy_vehicle.special_rules.get("data_spike_ws_penalty_active", False)) is False


def test_data_spike_invalid_non_vehicle_choice_is_rejected():
    source = _make_unit(
        "Tech-priest Dominus",
        abilities=[_make_data_spike_ability()],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy_vehicle = _make_unit("Enemy Tank", keywords=["VEHICLE"])
    enemy_infantry = _make_unit("Enemy Infantry", keywords=["INFANTRY"])

    game, admech_army, enemy_army, p1, _p2 = _build_game()
    admech_army.add_unit(source)
    enemy_army.add_unit(enemy_vehicle)
    enemy_army.add_unit(enemy_infantry)
    game.map.units = [source, enemy_vehicle, enemy_infantry]
    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy_vehicle.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    enemy_infantry.models[0].set_location(1.2, 0.0, 0.0, 0.0)

    game._on_phase_start_data_spike(player=p1, phase=game.phase)
    req = _find_data_spike_request(game)
    vehicle_option = next(
        opt
        for opt in list(req.options or [])
        if str((opt.payload or {}).get("target_unit_id", "")) == str(get_entity_id(enemy_vehicle))
    )
    vehicle_option.payload["target_unit_id"] = str(get_entity_id(enemy_infantry))

    result = resolve_decision_command(game, req, vehicle_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is False
