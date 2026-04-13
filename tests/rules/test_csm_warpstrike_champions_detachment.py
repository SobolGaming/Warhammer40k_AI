from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None, model_count: int = 1):
        count = max(1, int(model_count or 1))
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Chaos Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{count} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "5",
                "T": "5",
                "Sv": "2",
                "W": "3",
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
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
    unit.embarked_in = None
    return unit


def _set_model_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game(*, size: BattlefieldSize = BattlefieldSize.STRIKE_FORCE):
    csm_army = Army.with_detachment("Chaos Space Marines", "Warpstrike Champions")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    csm_player = Player("CSM", control=PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size), players=[csm_player, enemy_player])
    return game, csm_army, enemy_army, csm_player, enemy_player


def _warp_portals_requests(game: Game):
    return [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_SELECT_REALM_OF_CHAOS_UNITS
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "").strip().lower()
        == "warp_portals_end_of_opponent_turn"
    ]


def test_warp_portals_queues_single_multiselect_request_with_correct_filters():
    game, csm_army, enemy_army, _csm_player, enemy_player = _build_game(size=BattlefieldSize.STRIKE_FORCE)
    terminators = _make_unit(
        "Chaos Terminator Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    obliterators = _make_unit(
        "Obliterators",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    engaged_mutilators = _make_unit(
        "Mutilators",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    _set_model_location(terminators, x=4.0, y=4.0)
    _set_model_location(obliterators, x=10.0, y=4.0)
    _set_model_location(legionaries, x=16.0, y=4.0)
    _set_model_location(engaged_mutilators, x=22.0, y=4.0)
    _set_model_location(enemy, x=22.0, y=4.0)

    for unit in (terminators, obliterators, legionaries, engaged_mutilators):
        csm_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    game.map.units = [terminators, obliterators, legionaries, engaged_mutilators, enemy]
    game.rebuild_entity_registry()

    game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)

    requests = _warp_portals_requests(game)
    assert len(requests) == 1
    ctx = dict(getattr(requests[0], "context", {}) or {})
    allowed_ids = set(str(v) for v in list(ctx.get("allowed_unit_ids") or []))

    assert int(ctx.get("max_units", 0) or 0) == 2
    assert str(get_entity_id(terminators)) in allowed_ids
    assert str(get_entity_id(obliterators)) in allowed_ids
    assert str(get_entity_id(legionaries)) not in allowed_ids
    assert str(get_entity_id(engaged_mutilators)) not in allowed_ids
    assert str(ctx.get("skip_label", "")) == "None (do not use this ability)"


def test_warp_portals_selection_moves_units_and_prevents_repeat_prompt_same_turn():
    game, csm_army, enemy_army, csm_player, enemy_player = _build_game()
    terminators = _make_unit(
        "Chaos Terminator Squad",
        keywords=["HERETIC ASTARTES", "INFANTRY", "TERMINATOR"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    obliterators = _make_unit(
        "Obliterators",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    _set_model_location(terminators, x=6.0, y=6.0)
    _set_model_location(obliterators, x=12.0, y=6.0)
    _set_model_location(enemy, x=30.0, y=30.0)

    csm_army.add_unit(terminators)
    csm_army.add_unit(obliterators)
    enemy_army.add_unit(enemy)
    game.map.units = [terminators, obliterators, enemy]
    game.rebuild_entity_registry()

    game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
    request = _warp_portals_requests(game)[0]
    confirm_option = next(
        opt for opt in list(request.options or []) if str((opt.payload or {}).get("action", "")) == "confirm"
    )
    resolve_decision_command(
        game,
        request,
        confirm_option.option_id,
        result_payload={"unit_ids": [str(get_entity_id(terminators))]},
        player_id=csm_player.id,
    )

    assert terminators.is_in_strategic_reserves()
    assert not obliterators.is_in_strategic_reserves()

    game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
    assert len(_warp_portals_requests(game)) == 0


def test_warp_portals_support_matrix_classifies_supported():
    import scripts.generate_ability_support_matrix as gsm

    status, notes = gsm._classify_ability(
        "Warp Portals",
        (
            "At the end of your opponent's turn, you can select a number of Heretic Astartes Terminator, "
            "Obliterators and Mutilators units from your army (excluding units that are within Engagement Range "
            "of one or more enemy units). The maximum number of units you can select depends on the battle size, "
            "as follows: Incursion up to 1 unit, Strike Force up to 2 units, Onslaught up to 3 units. Once you "
            "have made your selections, remove those units from the battlefield and place them into Strategic Reserves."
        ),
        ability_id="000010738",
        faction_id="CSM",
    )

    assert status == "Supported"
    assert "Strategic Reserves" in notes
