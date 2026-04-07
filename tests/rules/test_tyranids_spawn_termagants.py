from __future__ import annotations

from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        model_count: int = 1,
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "6",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: claws."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    datasheet_id: str,
    model_count: int = 1,
    quantity: int = 1,
    abilities=None,
    keywords=None,
    faction_keywords=None,
):
    from warhammer40k_ai.units.unit import Unit

    ds = _MockDatasheet(
        name=name,
        datasheet_id=datasheet_id,
        model_count=model_count,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    unit = Unit(ds, quantity=quantity)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def test_spawn_termagants_parses_command_phase_targeted_return():
    ability = {
        "name": "Spawn Termagants",
        "description": (
            "In your Command phase, you can select one friendly Termagants unit within 6\" of this model and return "
            "up to D3+3 destroyed models to that unit. A TERMAGANTS unit cannot be selected for this ability more than once per phase."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    tervigon = _make_unit(
        "Tervigon",
        datasheet_id="tervigon_spawn_parse",
        abilities=[ability],
        keywords=["MONSTER", "TYRANIDS", "TERVIGON"],
        faction_keywords=["TYRANIDS"],
    )
    specs = tervigon.model_spawn_termagants_specs(tervigon.models[0])
    assert len(specs) == 1
    spec = specs[0]
    assert str(spec.get("target_keyword", "")) == "termagants"
    assert int(spec.get("range", 0) or 0) == 6
    assert int(spec.get("max_return", 0) or 0) == 6
    assert str(spec.get("amount_roll", "") or "") == "D3+3"
    assert bool(spec.get("once_per_phase_per_target", False))


def test_spawn_termagants_queues_target_and_bodyguard_return():
    from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl
    from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE, DECISION_CHOOSE_QUARRY
    from warhammer40k_ai.engine.decisions import DecisionResult
    from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability = {
        "name": "Spawn Termagants",
        "description": (
            "In your Command phase, you can select one friendly Termagants unit within 6\" of this model and return "
            "up to D3+3 destroyed models to that unit. A TERMAGANTS unit cannot be selected for this ability more than once per phase."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    tervigon = _make_unit(
        "Tervigon",
        datasheet_id="tervigon_spawn_queue",
        abilities=[ability],
        keywords=["MONSTER", "TYRANIDS", "TERVIGON"],
        faction_keywords=["TYRANIDS"],
    )
    termagants = _make_unit(
        "Termagants",
        datasheet_id="termagants_spawn_queue",
        model_count=4,
        quantity=4,
        keywords=["INFANTRY", "TERMAGANTS", "TYRANIDS"],
        faction_keywords=["TYRANIDS"],
    )
    enemy = _make_unit("Enemy Unit", datasheet_id="enemy_spawn_queue")

    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    army_one = Army.with_detachment("Tyranids", detachment_type="Test")
    army_two = Army.with_detachment("Enemy", detachment_type="Test")
    player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
    player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
    game.add_player(player_one)
    game.add_player(player_two)

    army_one.add_unit(tervigon)
    army_one.add_unit(termagants)
    army_two.add_unit(enemy)

    removed = termagants.models[0]
    termagants.remove_model(removed)
    assert removed in termagants.models_lost

    for unit in (tervigon, termagants, enemy):
        unit.deployed = True
        unit.reserve_status = "deployed"

    game.map.units = [tervigon, termagants, enemy]
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    with patch.object(game, "_unit_within_range_of_model", return_value=True):
        game._on_phase_start_spawn_termagants(player=player_one, phase=game.phase)

    pending = list(game.decision_queue.list() or [])
    choose_req = None
    for req in pending:
        if req.decision_type != DECISION_CHOOSE_QUARRY:
            continue
        if str((req.context or {}).get("ability", "") or "") == "spawn_termagants_target":
            choose_req = req
            break
    assert choose_req is not None

    termagants_id = str(get_entity_id(termagants) or "")
    target_option = None
    for opt in list(choose_req.options or []):
        if str((opt.payload or {}).get("target_unit_id", "") or "") == termagants_id:
            target_option = opt
            break
    assert target_option is not None

    result = DecisionResult(
        decision_id=choose_req.decision_id,
        player_id=player_one.id,
        option_id=target_option.option_id,
    )
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=5):
        _apply_choose_quarry(game, choose_req, result)

    pending_after = list(game.decision_queue.list() or [])
    bodyguard_req = None
    for req in pending_after:
        if req.decision_type != DECISION_ALLOCATE_DAMAGE:
            continue
        req_ctx = dict(req.context or {})
        if str(req_ctx.get("selection_kind", "") or "") != "bodyguard_return":
            continue
        if str(req_ctx.get("leader_unit_id", "") or "") != str(get_entity_id(tervigon) or ""):
            continue
        if str(req_ctx.get("bodyguard_unit_id", "") or "") != termagants_id:
            continue
        bodyguard_req = req
        break
    assert bodyguard_req is not None
    bodyguard_ctx = dict(bodyguard_req.context or {})
    assert int(bodyguard_ctx.get("remaining", 0) or 0) == 5
    assert bool(bodyguard_ctx.get("allow_skip", False))
