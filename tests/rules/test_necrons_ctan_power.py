from __future__ import annotations

from warhammer40k_ai.engine.decision_handlers.shooting import _validate_declare_shots
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_id: str = "NEC",
        abilities: list[dict] | None = None,
        wounds: int = 24,
        damaged_w: str = "",
        damaged_description: str = "",
    ) -> None:
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_id = faction_id
        self.source_id = "mock"
        self.faction_data = {"name": "Necrons"}
        self.keywords = ["MONSTER"]
        self.faction_keywords = ["NECRONS"]
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "11",
                "Sv": "2",
                "W": str(int(wounds)),
                "Ld": "6",
                "OC": "8",
                "base_size": "160mm",
                "inv_sv": "4",
                "inv_sv_descr": "4+",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []
        self.damaged_w = str(damaged_w or "")
        self.damaged_description = str(damaged_description or "")


def _make_unit(
    name: str,
    *,
    abilities: list[dict] | None = None,
    wounds: int = 24,
    damaged_w: str = "",
    damaged_description: str = "",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            wounds=wounds,
            damaged_w=damaged_w,
            damaged_description=damaged_description,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army.with_detachment("P1", "Det")
    army1.faction_id = "NEC"
    army2 = Army.with_detachment("P2", "Det")
    army2.faction_id = "SM"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _make_ranged_weapon(name: str, *, keywords: str = ""):
    wargear = Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "9",
            "AP": "-3",
            "D": "D6",
            "description": keywords,
        }
    )
    return wargear, wargear.profiles["default"]


def _build_declare_shots_request(game: Game, unit: Unit, *, player_id: str):
    options = [
        DecisionOption.create("Execute shooting", payload={"unit_id": get_entity_id(unit), "action": "confirm"}),
        DecisionOption.create("Skip shooting", payload={"unit_id": get_entity_id(unit), "action": "skip"}),
    ]
    return DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        f"Declare shots for {unit.name}",
        player_id=player_id,
        options=options,
        context={"unit_id": get_entity_id(unit), "out_of_phase": False},
    )


def _resolve_validation(game: Game, request: DecisionRequest, *, declarations: list[dict], player_id: str):
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player_id,
        option_id=request.options[0].option_id,
        payload={"declarations": list(declarations)},
    )
    return list(_validate_declare_shots(game, request, result) or [])


def _ctan_ability_rows():
    return [
        {
            "name": "Powers of the C'tan",
            "description": (
                "In your Shooting phase, when this model is selected to shoot, first select up to two different "
                "C'tan Powers weapons. Until the end of the phase, this model is equipped with those weapons."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
    ]


def test_ctan_power_keyword_detection_on_profile():
    _weapon, profile = _make_ranged_weapon("Cosmic Fire", keywords="Torrent, C'Tan Power")
    assert profile.is_ctan_power() is True


def test_powers_of_ctan_allows_up_to_two_weapons_when_healthy():
    game, army1, army2, p1, _p2 = _build_game()
    attacker = _make_unit("Tesseract Vault", abilities=_ctan_ability_rows(), wounds=24, damaged_w="1-8")
    target = _make_unit("Target Unit", abilities=[], wounds=3)
    army1.add_unit(attacker)
    army2.add_unit(target)

    w1, p1_weapon = _make_ranged_weapon("Antimatter Meteor", keywords="Blast, C'Tan Power")
    w2, p2_weapon = _make_ranged_weapon("Cosmic Fire", keywords="Torrent, C'Tan Power")
    w3, _ = _make_ranged_weapon("Tesla Spheres", keywords="Sustained Hits 2")
    attacker.models[0].wargear = [w1, w2, w3]

    game.map.units = [attacker, target]
    game.rebuild_entity_registry()

    request = _build_declare_shots_request(game, attacker, player_id=p1.id)
    model_id = get_entity_id(attacker.models[0])
    target_id = get_entity_id(target)
    declarations = [
        {"wargear_id": get_entity_id(w1), "profile_name": "default", "model_ids": [model_id], "target_unit_id": target_id},
        {"wargear_id": get_entity_id(w2), "profile_name": "default", "model_ids": [model_id], "target_unit_id": target_id},
        {"wargear_id": get_entity_id(w3), "profile_name": "default", "model_ids": [model_id], "target_unit_id": target_id},
    ]
    errors = _resolve_validation(game, request, declarations=declarations, player_id=p1.id)
    assert errors == []
    assert attacker._is_ctan_power_profile(p1_weapon) is True
    assert attacker._is_ctan_power_profile(p2_weapon) is True
    assert attacker.get_ctan_power_selection_limit() == 2


def test_powers_of_ctan_rejects_three_distinct_ctan_weapons():
    game, army1, army2, p1, _p2 = _build_game()
    attacker = _make_unit("Tesseract Vault", abilities=_ctan_ability_rows(), wounds=24, damaged_w="1-8")
    target = _make_unit("Target Unit", abilities=[], wounds=3)
    army1.add_unit(attacker)
    army2.add_unit(target)

    w1, _ = _make_ranged_weapon("Antimatter Meteor", keywords="Blast, C'Tan Power")
    w2, _ = _make_ranged_weapon("Cosmic Fire", keywords="Torrent, C'Tan Power")
    w3, _ = _make_ranged_weapon("Time's Arrow", keywords="Precision, C'Tan Power")
    attacker.models[0].wargear = [w1, w2, w3]

    game.map.units = [attacker, target]
    game.rebuild_entity_registry()

    request = _build_declare_shots_request(game, attacker, player_id=p1.id)
    model_id = get_entity_id(attacker.models[0])
    target_id = get_entity_id(target)
    declarations = [
        {"wargear_id": get_entity_id(w1), "profile_name": "default", "model_ids": [model_id], "target_unit_id": target_id},
        {"wargear_id": get_entity_id(w2), "profile_name": "default", "model_ids": [model_id], "target_unit_id": target_id},
        {"wargear_id": get_entity_id(w3), "profile_name": "default", "model_ids": [model_id], "target_unit_id": target_id},
    ]
    errors = _resolve_validation(game, request, declarations=declarations, player_id=p1.id)
    assert errors
    assert "Powers of the C'tan" in errors[0]


def test_powers_of_ctan_damaged_bracket_caps_to_one_weapon():
    game, army1, army2, p1, _p2 = _build_game()
    attacker = _make_unit(
        "Tesseract Vault",
        abilities=_ctan_ability_rows(),
        wounds=24,
        damaged_w="1-8",
        damaged_description=(
            "While this model has 1-8 wounds remaining, subtract 4 from its Objective Control characteristic "
            "and you can only select one of the C'tan Powers weapons in your Shooting phase, instead of two."
        ),
    )
    attacker.models[0].wounds = 8
    target = _make_unit("Target Unit", abilities=[], wounds=3)
    army1.add_unit(attacker)
    army2.add_unit(target)

    w1, _ = _make_ranged_weapon("Antimatter Meteor", keywords="Blast, C'Tan Power")
    w2, _ = _make_ranged_weapon("Cosmic Fire", keywords="Torrent, C'Tan Power")
    attacker.models[0].wargear = [w1, w2]

    game.map.units = [attacker, target]
    game.rebuild_entity_registry()
    assert attacker.get_ctan_power_selection_limit() == 1

    request = _build_declare_shots_request(game, attacker, player_id=p1.id)
    model_id = get_entity_id(attacker.models[0])
    target_id = get_entity_id(target)
    declarations = [
        {"wargear_id": get_entity_id(w1), "profile_name": "default", "model_ids": [model_id], "target_unit_id": target_id},
        {"wargear_id": get_entity_id(w2), "profile_name": "default", "model_ids": [model_id], "target_unit_id": target_id},
    ]
    errors = _resolve_validation(game, request, declarations=declarations, player_id=p1.id)
    assert errors
    assert "up to 1 different C'tan Powers weapons" in errors[0]
