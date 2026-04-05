from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.shadow_in_the_warp import ShadowInTheWarpManager
from warhammer40k_ai.rules.synapse import SynapseManager
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


_NEUROLOIDS_DESCRIPTION = (
    "In your Command phase, you can select up to two friendly TYRANIDS units within 18\" of this model's unit. "
    "Until the start of your next Command phase, the selected units are always considered to be within Synapse Range of your army. "
    "Designer's Note: Place a Neuroloid token next to each selected unit to remind you."
)

_PSYCHIC_TERROR_DESCRIPTION = (
    "If one or more models from your army with this ability are on the battlefield when you unleash the Shadow in the Warp, "
    "subtract 1 from the Battle-shock test each enemy unit on the battlefield must take as a result."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Tyranids",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
    ) -> None:
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "5",
                "Sv": "4",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Tyranids",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyr", control=PlayerControl.REMOTE, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_army, enemy_army, tyr_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.1 * idx), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def test_neuroloids_parses_command_phase_synapse_selection_spec():
    neurotyrant = _make_unit(
        "Neurotyrant",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    ability = Ability("Neuroloids", "TYR", _NEUROLOIDS_DESCRIPTION, "Datasheet", "")
    model = neurotyrant.models[0]
    model.abilities = {"Neuroloids": ability}

    specs = neurotyrant.model_command_phase_select_friendly_synapse_units_specs(model)
    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("range", 0) or 0) == 18
    assert int(spec.get("max_targets", 0) or 0) == 2
    assert str(spec.get("friendly_keyword_phrase", "") or "").strip().upper() == "TYRANIDS"
    assert str(spec.get("context_ability", "") or "") == "neuroloids"


def test_neuroloids_queues_selection_applies_synapse_marker_and_cleans_up_next_command_phase():
    game, tyr_army, enemy_army, tyr_player, _enemy_player = _build_game()
    neurotyrant = _make_unit(
        "Neurotyrant",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    ability = Ability("Neuroloids", "TYR", _NEUROLOIDS_DESCRIPTION, "Datasheet", "")
    model = neurotyrant.models[0]
    model.abilities = {"Neuroloids": ability}

    ally_one = _make_unit("Ally One", faction_keywords=["TYRANIDS"], model_count=3)
    ally_two = _make_unit("Ally Two", faction_keywords=["TYRANIDS"], model_count=3)
    ally_out = _make_unit("Ally Out", faction_keywords=["TYRANIDS"], model_count=3)

    tyr_army.add_unit(neurotyrant)
    tyr_army.add_unit(ally_one)
    tyr_army.add_unit(ally_two)
    tyr_army.add_unit(ally_out)

    _deploy_unit(game, neurotyrant, 10.0, 10.0)
    _deploy_unit(game, ally_one, 25.0, 10.0)
    _deploy_unit(game, ally_two, 27.0, 10.0)
    _deploy_unit(game, ally_out, 40.0, 10.0)
    game.rebuild_entity_registry()

    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.event_system.publish("phase_start", player=tyr_player, phase=game.phase)

    requests = [
        req
        for req in list(game.decision_queue.list() or [])
        if str((getattr(req, "context", {}) or {}).get("ability", "")).strip().lower() == "neuroloids"
    ]
    assert len(requests) == 1
    request = requests[0]
    assert str(request.decision_type) == DECISION_CHOOSE_QUARRY

    target_ids = {str(ally_one._id), str(ally_two._id)}
    selected_option = next(
        option
        for option in list(request.options or [])
        if {str(v) for v in list((option.payload or {}).get("selected_unit_ids", []) or [])} == target_ids
    )
    outcome = resolve_decision_command(game, request, selected_option.option_id, player_id=tyr_player.id)
    assert bool(getattr(outcome, "ok", False))

    synapse_mgr = getattr(tyr_army, "synapse", None)
    if synapse_mgr is None:
        synapse_mgr = SynapseManager(tyr_army)
        tyr_army.synapse = synapse_mgr
    assert synapse_mgr.unit_in_synapse_range(ally_one)
    assert synapse_mgr.unit_in_synapse_range(ally_two)
    assert not synapse_mgr.unit_in_synapse_range(ally_out)

    game.turn = 3
    game.event_system.publish("phase_start", player=tyr_player, phase=game.phase)
    assert not bool((getattr(ally_one, "special_rules", {}) or {}).get("neuroloids_synapse_active", False))
    assert not bool((getattr(ally_two, "special_rules", {}) or {}).get("neuroloids_synapse_active", False))


def test_neuroloids_does_not_grant_synapse_keyword_to_neurogaunts():
    game, tyr_army, _enemy_army, tyr_player, _enemy_player = _build_game()
    neurotyrant = _make_unit(
        "Neurotyrant",
        keywords=["INFANTRY", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    ability = Ability("Neuroloids", "TYR", _NEUROLOIDS_DESCRIPTION, "Datasheet", "")
    neurotyrant.models[0].abilities = {"Neuroloids": ability}

    neurogaunts = _make_unit(
        "Neurogaunts",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        model_count=3,
    )

    tyr_army.add_unit(neurotyrant)
    tyr_army.add_unit(neurogaunts)
    _deploy_unit(game, neurotyrant, 10.0, 10.0)
    _deploy_unit(game, neurogaunts, 20.0, 10.0)
    game.rebuild_entity_registry()

    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.event_system.publish("phase_start", player=tyr_player, phase=game.phase)

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str((getattr(req, "context", {}) or {}).get("ability", "")).strip().lower() == "neuroloids"
    )
    neurogaunts_id = str(neurogaunts._id)
    selected_option = next(
        option
        for option in list(request.options or [])
        if {str(v) for v in list((option.payload or {}).get("selected_unit_ids", []) or [])} == {neurogaunts_id}
    )
    outcome = resolve_decision_command(game, request, selected_option.option_id, player_id=tyr_player.id)
    assert bool(getattr(outcome, "ok", False))

    synapse_mgr = getattr(tyr_army, "synapse", None) or SynapseManager(tyr_army)
    tyr_army.synapse = synapse_mgr
    assert synapse_mgr.unit_in_synapse_range(neurogaunts)
    assert not neurogaunts.has_any_keyword("SYNAPSE")
    assert all(not model.has_any_keyword("SYNAPSE") for model in list(neurogaunts.models or []))


def test_psychic_terror_applies_additional_shadow_in_the_warp_battleshock_penalty():
    game, tyr_army, enemy_army, tyr_player, _enemy_player = _build_game()
    shadow_source = _make_unit(
        "Synapse Source",
        keywords=["SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    shadow_source.possible_abilities = [Ability("Shadow in the Warp", "TYR", "", "Datasheet", "")]
    psychic_terror_source = _make_unit(
        "Neurotyrant",
        keywords=["SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    psychic_terror_source.possible_abilities = [
        Ability("Psychic Terror (Psychic)", "TYR", _PSYCHIC_TERROR_DESCRIPTION, "Datasheet", "")
    ]
    enemy_close = _make_unit("Enemy Close", faction_name="Enemy", faction_keywords=["ENEMY"])
    enemy_far = _make_unit("Enemy Far", faction_name="Enemy", faction_keywords=["ENEMY"])

    close_tests = []
    far_tests = []
    enemy_close.take_battle_shock_test = lambda current_turn=1: close_tests.append(dict(enemy_close.special_rules))
    enemy_far.take_battle_shock_test = lambda current_turn=1: far_tests.append(dict(enemy_far.special_rules))

    tyr_army.add_unit(shadow_source)
    tyr_army.add_unit(psychic_terror_source)
    enemy_army.add_unit(enemy_close)
    enemy_army.add_unit(enemy_far)
    _deploy_unit(game, shadow_source, 10.0, 10.0)
    _deploy_unit(game, psychic_terror_source, 25.0, 10.0)
    _deploy_unit(game, enemy_close, 15.0, 10.0)
    _deploy_unit(game, enemy_far, 25.0, 30.0)
    game.rebuild_entity_registry()

    tyr_army.synapse = SynapseManager(tyr_army)
    tyr_army.shadow_in_the_warp = ShadowInTheWarpManager(tyr_army)
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    mgr = tyr_army.shadow_in_the_warp
    assert mgr.activate(game=game, player=tyr_player)
    assert len(close_tests) == 1
    assert len(far_tests) == 1
    assert int(close_tests[0].get("battle_shock_test_modifier", 0) or 0) == -2
    assert int(far_tests[0].get("battle_shock_test_modifier", 0) or 0) == -1
