from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
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
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army("Adeptus Mechanicus", detachment_type="Haloscreed Battle Clade")
    admech_army.faction_id = "ADM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    admech_player = Player("P1", PlayerControl.REMOTE, army=admech_army)
    enemy_player = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)

    unit_a = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    unit_b = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    unit_c = _make_unit(
        "Kataphron Destroyers",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(unit_a)
    admech_army.add_unit(unit_b)
    admech_army.add_unit(unit_c)
    game.map.units = [unit_a, unit_b, unit_c]
    game.rebuild_entity_registry()
    return game, admech_army, admech_player, unit_a, unit_b, unit_c


def _find_requests(game: Game, ability_key: str):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == str(ability_key or "")
    ]


def _choose_units(game: Game, request, *, player_id: str, unit_ids: list[str]) -> None:
    wanted = tuple(sorted(str(v or "").strip() for v in list(unit_ids or []) if str(v or "").strip()))
    option = next(
        opt
        for opt in list(request.options or [])
        if tuple(
            sorted(
                str(v or "").strip()
                for v in list((opt.payload or {}).get("selected_unit_ids", []) or [])
                if str(v or "").strip()
            )
        )
        == wanted
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def _choose_override(game: Game, request, *, player_id: str, choice_key: str) -> None:
    wanted = str(choice_key or "").strip().upper()
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("choice_key", "") or "").strip().upper() == wanted
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def test_noospheric_transference_queues_unit_and_override_selection_requests():
    game, admech_army, admech_player, unit_a, unit_b, _unit_c = _build_game()
    game.turn = 1
    mgr = admech_army.adeptus_mechanicus_detachments
    mgr.on_command_phase_start(game=game, player=admech_player)

    unit_requests = _find_requests(game, "noospheric_transference_units")
    assert len(unit_requests) == 1
    request = unit_requests[0]
    assert request.player_id == admech_player.id
    counts = {
        len(list((opt.payload or {}).get("selected_unit_ids", []) or []))
        for opt in list(request.options or [])
    }
    assert counts == {1, 2}

    _choose_units(
        game,
        request,
        player_id=admech_player.id,
        unit_ids=[str(get_entity_id(unit_a) or ""), str(get_entity_id(unit_b) or "")],
    )
    override_requests = _find_requests(game, "noospheric_transference_override")
    assert len(override_requests) == 1
    override_keys = {
        str((opt.payload or {}).get("choice_key", "") or "").strip().upper()
        for opt in list(override_requests[0].options or [])
    }
    assert override_keys == {
        "ELECTROMOTIVE_ENERGISATION",
        "MICROACTUATOR_BRACING",
        "PREDATION_PROTOCOLS",
        "MUTED_SERVOMOTORS",
    }


def test_electromotive_energisation_applies_movement_bonus_to_selected_units():
    game, admech_army, admech_player, unit_a, unit_b, _unit_c = _build_game()
    game.turn = 1
    mgr = admech_army.adeptus_mechanicus_detachments
    mgr.on_command_phase_start(game=game, player=admech_player)
    units_request = _find_requests(game, "noospheric_transference_units")[0]
    _choose_units(game, units_request, player_id=admech_player.id, unit_ids=[str(get_entity_id(unit_a) or "")])
    override_request = _find_requests(game, "noospheric_transference_override")[0]
    _choose_override(game, override_request, player_id=admech_player.id, choice_key="ELECTROMOTIVE_ENERGISATION")

    assert unit_a.get_effective_model_characteristic(unit_a.models[0], "movement") == 8
    assert unit_b.get_effective_model_characteristic(unit_b.models[0], "movement") == 6


def test_microactuator_bracing_applies_toughness_bonus_to_selected_units():
    game, admech_army, admech_player, unit_a, unit_b, _unit_c = _build_game()
    game.turn = 1
    mgr = admech_army.adeptus_mechanicus_detachments
    mgr.on_command_phase_start(game=game, player=admech_player)
    units_request = _find_requests(game, "noospheric_transference_units")[0]
    _choose_units(game, units_request, player_id=admech_player.id, unit_ids=[str(get_entity_id(unit_a) or "")])
    override_request = _find_requests(game, "noospheric_transference_override")[0]
    _choose_override(game, override_request, player_id=admech_player.id, choice_key="MICROACTUATOR_BRACING")

    assert unit_a.get_effective_model_characteristic(unit_a.models[0], "toughness") == 5
    assert unit_b.get_effective_model_characteristic(unit_b.models[0], "toughness") == 4


def test_predation_protocols_and_muted_servomotors_apply_to_selected_units():
    game, admech_army, admech_player, unit_a, unit_b, _unit_c = _build_game()
    game.turn = 1
    mgr = admech_army.adeptus_mechanicus_detachments
    mgr.on_command_phase_start(game=game, player=admech_player)
    units_request = _find_requests(game, "noospheric_transference_units")[0]
    _choose_units(game, units_request, player_id=admech_player.id, unit_ids=[str(get_entity_id(unit_a) or "")])
    override_request = _find_requests(game, "noospheric_transference_override")[0]
    _choose_override(game, override_request, player_id=admech_player.id, choice_key="PREDATION_PROTOCOLS")

    unit_a.round_state.advanced_this_round = True
    unit_b.round_state.advanced_this_round = True
    assert unit_a.can_charge_after_advance() is True
    assert unit_b.can_charge_after_advance() is False

    game.turn = 2
    mgr.on_command_phase_start(game=game, player=admech_player)
    units_request_round_2 = _find_requests(game, "noospheric_transference_units")[0]
    _choose_units(game, units_request_round_2, player_id=admech_player.id, unit_ids=[str(get_entity_id(unit_a) or "")])
    override_request_round_2 = _find_requests(game, "noospheric_transference_override")[0]
    _choose_override(game, override_request_round_2, player_id=admech_player.id, choice_key="MUTED_SERVOMOTORS")

    assert unit_a.has_stealth() is True
    assert unit_b.has_stealth() is False


def test_noospheric_transference_effects_expire_next_command_phase_start():
    game, admech_army, admech_player, unit_a, _unit_b, _unit_c = _build_game()
    game.turn = 1
    mgr = admech_army.adeptus_mechanicus_detachments
    mgr.on_command_phase_start(game=game, player=admech_player)
    units_request = _find_requests(game, "noospheric_transference_units")[0]
    _choose_units(game, units_request, player_id=admech_player.id, unit_ids=[str(get_entity_id(unit_a) or "")])
    override_request = _find_requests(game, "noospheric_transference_override")[0]
    _choose_override(game, override_request, player_id=admech_player.id, choice_key="ELECTROMOTIVE_ENERGISATION")
    assert unit_a.get_effective_model_characteristic(unit_a.models[0], "movement") == 8

    game.turn = 2
    mgr.on_command_phase_start(game=game, player=admech_player)
    assert unit_a.get_effective_model_characteristic(unit_a.models[0], "movement") == 6
