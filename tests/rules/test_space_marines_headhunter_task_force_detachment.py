from __future__ import annotations

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: str = "10",
    ):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ADEPTUS ASTARTES"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "9",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "3",
                "base_size": "90mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _unit(name: str, *, keywords=None, faction_keywords=None, wounds: str = "10") -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, detachment: str = "Headhunter Task Force"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    marine_army = Army.with_detachment("Space Marines", detachment)
    marine_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    marine_player = Player("Marine Player", control=PlayerControl.REMOTE, army=marine_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(marine_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, marine_player, marine_army, enemy_army


def _selection_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == "headhunter_tank_ace_character_selection":
            return request
    return None


def _confirm_option(request):
    for option in list(getattr(request, "options", []) or []):
        if str((getattr(option, "payload", {}) or {}).get("action", "") or "") == "confirm":
            return option
    return None


def test_target_sighted_marks_only_eligible_adeptus_astartes_vehicles_as_tank_ace():
    game, _player, army, _enemy = _build_game()
    gladiator = _unit("Gladiator Lancer", keywords=["VEHICLE"], faction_keywords=["ADEPTUS ASTARTES"])
    bunker = _unit("Hammerfall Bunker", keywords=["VEHICLE", "FORTIFICATION"], faction_keywords=["ADEPTUS ASTARTES"])
    drop_pod = _unit("Drop Pod", keywords=["VEHICLE", "DROP POD"], faction_keywords=["ADEPTUS ASTARTES"])
    dreadnought = _unit("Redemptor Dreadnought", keywords=["VEHICLE", "WALKER"], faction_keywords=["ADEPTUS ASTARTES"])
    speeder = _unit("Storm Speeder", keywords=["VEHICLE", "FLY"], faction_keywords=["ADEPTUS ASTARTES"])
    infantry = _unit("Intercessor Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    for unit in (gladiator, bunker, drop_pod, dreadnought, speeder, infantry):
        army.add_unit(unit)
    game.rebuild_entity_registry()

    assert gladiator.has_keyword("TANK ACE") is True
    assert bunker.has_keyword("TANK ACE") is False
    assert drop_pod.has_keyword("TANK ACE") is False
    assert dreadnought.has_keyword("TANK ACE") is False
    assert speeder.has_keyword("TANK ACE") is False
    assert infantry.has_keyword("TANK ACE") is False


def test_target_sighted_tank_ace_advance_replaces_roll_with_six_inch_move_bonus():
    _game, _player, army, _enemy = _build_game()
    predator = _unit("Predator Destructor", keywords=["VEHICLE"], faction_keywords=["ADEPTUS ASTARTES"])
    infantry = _unit("Intercessor Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    army.add_unit(predator)
    army.add_unit(infantry)

    effect = predator._get_advance_no_roll_effect()
    assert effect["distance"] == 6
    assert effect["source"] == "Target Sighted"
    assert infantry._get_advance_no_roll_effect() is None


def test_target_sighted_grants_damage_reroll_when_tank_ace_shoots_without_advancing():
    game, _player, army, _enemy = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    predator = _unit("Predator Destructor", keywords=["VEHICLE"], faction_keywords=["ADEPTUS ASTARTES"])
    army.add_unit(predator)
    game.rebuild_entity_registry()

    model = predator.models[0]
    predator.grant_selected_to_shoot_rerolls_for_models([model])
    assert model.can_use_selected_to_shoot_reroll("damage") is True
    assert model.get_selected_to_shoot_reroll_source() == "Target Sighted"

    model.clear_selected_to_shoot_rerolls()
    predator.round_state.advanced_this_round = True
    predator.grant_selected_to_shoot_rerolls_for_models([model])
    assert model.can_use_selected_to_shoot_reroll("damage") is False


def test_target_sighted_tank_ace_character_selection_valid_path_applies_character_keyword():
    game, player, army, _enemy = _build_game()
    predator = _unit("Predator Destructor", keywords=["VEHICLE"], faction_keywords=["ADEPTUS ASTARTES"])
    gladiator = _unit("Gladiator Lancer", keywords=["VEHICLE"], faction_keywords=["ADEPTUS ASTARTES"])
    army.add_unit(predator)
    army.add_unit(gladiator)
    game.rebuild_entity_registry()

    army.space_marines_detachments.queue_headhunter_tank_ace_character_selection_request(game=game, player=player)
    request = _selection_request(game)
    assert request is not None
    context = dict(request.context or {})
    assert context["max_units"] == 3
    assert set(context["allowed_unit_ids"]) == {
        str(get_entity_id(predator) or ""),
        str(get_entity_id(gladiator) or ""),
    }

    option = _confirm_option(request)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=option.option_id,
        payload={"unit_ids": [str(get_entity_id(predator) or "")]},
    )
    applied = dispatch_decision(game, request, result)
    assert applied.ok is True
    assert predator.has_keyword("CHARACTER") is True
    assert predator.models[0].has_keyword("CHARACTER") is True
    assert getattr(army, "headhunter_tank_ace_character_unit_ids") == [str(get_entity_id(predator) or "")]
    assert gladiator.has_keyword("CHARACTER") is False


def test_target_sighted_tank_ace_character_selection_rejects_ineligible_unit():
    game, player, army, _enemy = _build_game()
    predator = _unit("Predator Destructor", keywords=["VEHICLE"], faction_keywords=["ADEPTUS ASTARTES"])
    infantry = _unit("Intercessor Squad", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    army.add_unit(predator)
    army.add_unit(infantry)
    game.rebuild_entity_registry()

    army.space_marines_detachments.queue_headhunter_tank_ace_character_selection_request(game=game, player=player)
    request = _selection_request(game)
    option = _confirm_option(request)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=option.option_id,
        payload={"unit_ids": [str(get_entity_id(infantry) or "")]},
    )

    applied = dispatch_decision(game, request, result)
    assert applied.ok is False
    assert infantry.has_keyword("CHARACTER") is False

