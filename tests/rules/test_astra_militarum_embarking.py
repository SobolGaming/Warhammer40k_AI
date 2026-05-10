from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.shooting import _apply_firing_deck, _validate_firing_deck
from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_FIRING_DECK
from warhammer40k_ai.engine.decision_requests import build_declare_firing_deck_request, firing_deck_selection_entries
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.model_base import Base, BaseType


class _DatasheetStub:
    def __init__(self, name: str, *, abilities=None, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ASTRA MILITARUM", "IMPERIUM"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "5",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "25mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


class _RegistryStub:
    def __init__(self, *, units, models, wargear):
        self._units = {str(getattr(u, "_id", "")): u for u in units}
        self._models = {str(getattr(m, "_id", "")): m for m in models}
        self._wargear = {str(getattr(w, "_id", "")): w for w in wargear}

    def get(self, entity_id: str, *, kind: str):
        if kind == "unit":
            return self._units.get(str(entity_id))
        if kind == "model":
            return self._models.get(str(entity_id))
        if kind == "wargear":
            return self._wargear.get(str(entity_id))
        return None


def _mk_model(name: str) -> Model:
    return Model(
        name=name,
        movement=6,
        toughness=3,
        save=5,
        wounds=1,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )


def _mk_ranged_weapon(name: str, weapon_id: str, *, description: str = "", damage: str = "1") -> Wargear:
    wargear = Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "3",
            "AP": "0",
            "D": damage,
            "description": description,
        }
    )
    wargear._id = weapon_id
    return wargear


def _mk_unit(name: str, *, abilities, keywords=None) -> Unit:
    ds = _DatasheetStub(name, abilities=abilities, keywords=keywords or ["Infantry"])
    unit = Unit(ds)
    unit._id = f"UNIT_{name.replace(' ', '_')}"
    return unit


def _set_models(unit: Unit, model_defs: list[tuple[str, str]]) -> list[Model]:
    models = []
    for idx, (model_name, weapon_name) in enumerate(model_defs):
        model = _mk_model(model_name)
        model._id = f"{unit._id}_M{idx}"
        model.set_parent_unit(unit)
        weapon = _mk_ranged_weapon(weapon_name, f"{model._id}_W0")
        model.wargear = [weapon]
        models.append(model)
    unit.models = models
    return models


def test_embarking_all_models_double_transport_slots():
    unit = _mk_unit(
        "Heavy Squad",
        abilities=[
            {
                "name": "EMBARKING",
                "description": "While embarked within a Transport, each model takes up the space of 2 models, and each weapon equipped by these models is considered to be 2 models' weapons for the purposes of the Firing Deck ability.",
                "type": "",
                "parameter": "",
            }
        ],
    )
    _set_models(unit, [("Trooper", "Lasgun"), ("Trooper", "Lasgun"), ("Trooper", "Lasgun")])
    assert unit.get_transport_slots_required() == 6


def test_embarking_heavy_weapons_gunner_double_transport_slots_only_for_gunners():
    unit = _mk_unit(
        "Heavy Weapons Squad",
        abilities=[
            {
                "name": "EMBARKING",
                "description": "While embarked within a Transport, each Heavy Weapons Gunner model takes up the space of 2 models, and each weapon equipped by these models is considered to be 2 models' weapons for the purposes of the Firing Deck ability.",
                "type": "",
                "parameter": "",
            }
        ],
    )
    _set_models(
        unit,
        [
            ("Heavy Weapons Gunner", "Mortar"),
            ("Heavy Weapons Gunner", "Lascannon"),
            ("Trooper", "Lasgun"),
        ],
    )
    assert unit.get_transport_slots_required() == 5


def test_embarking_heavy_weapons_gunner_firing_deck_cost():
    unit = _mk_unit(
        "Heavy Weapons Squad",
        abilities=[
            {
                "name": "EMBARKING",
                "description": "While embarked within a Transport, each Heavy Weapons Gunner model takes up the space of 2 models, and each weapon equipped by these models is considered to be 2 models' weapons for the purposes of the Firing Deck ability.",
                "type": "",
                "parameter": "",
            }
        ],
    )
    models = _set_models(
        unit,
        [
            ("Heavy Weapons Gunner", "Mortar"),
            ("Trooper", "Lasgun"),
        ],
    )
    assert unit.get_firing_deck_weapon_slots_for_model(models[0]) == 2
    assert unit.get_firing_deck_weapon_slots_for_model(models[1]) == 1


def test_firing_deck_validation_enforces_embarking_weighted_limit():
    transport = _mk_unit(
        "Chimera",
        abilities=[{"name": "Firing Deck 3", "description": "", "type": "", "parameter": ""}],
        keywords=["Vehicle", "Transport"],
    )
    transport._id = "TRANSPORT_1"
    transport.transport_passengers = []

    passenger = _mk_unit(
        "Heavy Squad",
        abilities=[
            {
                "name": "EMBARKING",
                "description": "While embarked within a Transport, each model takes up the space of 2 models, and each weapon equipped by these models is considered to be 2 models' weapons for the purposes of the Firing Deck ability.",
                "type": "",
                "parameter": "",
            }
        ],
    )
    passenger._id = "PASSENGER_1"
    models = _set_models(
        passenger,
        [
            ("Trooper", "Lasgun"),
            ("Trooper", "Lasgun"),
        ],
    )
    passenger.embarked_in = transport
    transport.transport_passengers = [passenger]

    all_weapons = [models[0].wargear[0], models[1].wargear[0]]
    game = SimpleNamespace(
        entity_registry=_RegistryStub(units=[transport, passenger], models=models, wargear=all_weapons),
    )

    options = [
        DecisionOption.create(
            "Confirm firing deck",
            payload={"transport_id": transport._id, "action": "confirm"},
        ),
    ]
    request = DecisionRequest.create(
        DECISION_DECLARE_FIRING_DECK,
        "Declare firing deck",
        player_id="P1",
        options=options,
        context={"transport_id": transport._id},
    )

    invalid_result = DecisionResult(
        decision_id=request.decision_id,
        player_id="P1",
        option_id=options[0].option_id,
        payload={
            "selected_entries": [
                {
                    "model_id": models[0]._id,
                    "wargear_id": all_weapons[0]._id,
                    "profile_name": "default",
                },
                {
                    "model_id": models[1]._id,
                    "wargear_id": all_weapons[1]._id,
                    "profile_name": "default",
                },
            ]
        },
    )
    errors = _validate_firing_deck(game, request, invalid_result)
    assert errors
    assert "exceed Firing Deck 3" in errors[0]

    valid_result = DecisionResult(
        decision_id=request.decision_id,
        player_id="P1",
        option_id=options[0].option_id,
        payload={
            "selected_entries": [
                {
                    "model_id": models[0]._id,
                    "wargear_id": all_weapons[0]._id,
                    "profile_name": "default",
                }
            ]
        },
    )
    assert _validate_firing_deck(game, request, valid_result) == ()


def test_firing_deck_validation_rejects_one_shot_and_already_shot_source_units():
    transport = _mk_unit(
        "Chimera",
        abilities=[{"name": "Firing Deck 2", "description": "", "type": "", "parameter": ""}],
        keywords=["Vehicle", "Transport"],
    )
    transport._id = "TRANSPORT_ONE_SHOT"
    passenger = _mk_unit("Veterans", abilities=[])
    passenger._id = "PASSENGER_ONE_SHOT"
    models = _set_models(passenger, [("Specialist", "Hunter-killer missile")])
    missile = _mk_ranged_weapon("Hunter-killer missile", f"{models[0]._id}_HK", description="[ONE SHOT]")
    models[0].wargear = [missile]
    assert missile.profiles["default"].is_one_shot()
    passenger.embarked_in = transport
    transport.transport_passengers = [passenger]
    game = SimpleNamespace(
        entity_registry=_RegistryStub(units=[transport, passenger], models=models, wargear=[missile]),
    )
    request = build_declare_firing_deck_request(transport, player_id="P1")
    assert request is None

    lasgun = _mk_ranged_weapon("Lasgun", f"{models[0]._id}_LG")
    models[0].wargear = [lasgun]
    game.entity_registry = _RegistryStub(units=[transport, passenger], models=models, wargear=[lasgun])
    request = build_declare_firing_deck_request(transport, player_id="P1")
    assert request is not None
    option = request.options[0]
    passenger.round_state.shot_this_round = True
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="P1",
        option_id=option.option_id,
        payload={
            "selected_entries": [
                {
                    "model_id": models[0]._id,
                    "wargear_id": lasgun._id,
                    "profile_name": "default",
                }
            ]
        },
    )
    errors = _validate_firing_deck(game, request, result)
    assert errors
    assert "already shot" in errors[0]


def test_apply_firing_deck_marks_selected_passenger_unit_shot_before_transport_shoots():
    transport = _mk_unit(
        "Chimera",
        abilities=[{"name": "Firing Deck 1", "description": "", "type": "", "parameter": ""}],
        keywords=["Vehicle", "Transport"],
    )
    transport._id = "TRANSPORT_APPLY"
    transport_model = _mk_model("Chimera hull")
    transport_model._id = "TRANSPORT_APPLY_M0"
    transport_model.set_parent_unit(transport)
    transport_model.wargear = []
    transport.models = [transport_model]
    passenger = _mk_unit("Infantry Squad", abilities=[])
    passenger._id = "PASSENGER_APPLY"
    models = _set_models(passenger, [("Trooper", "Lasgun")])
    passenger.embarked_in = transport
    transport.transport_passengers = [passenger]
    wargear = models[0].wargear[0]
    game = SimpleNamespace(
        entity_registry=_RegistryStub(units=[transport, passenger], models=[transport_model] + models, wargear=[wargear]),
    )
    request = build_declare_firing_deck_request(transport, player_id="P1")
    assert request is not None
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="P1",
        option_id=request.options[0].option_id,
        payload={
            "selected_entries": [
                {
                    "model_id": models[0]._id,
                    "wargear_id": wargear._id,
                    "profile_name": "default",
                }
            ]
        },
    )

    _apply_firing_deck(game, request, result)

    assert passenger.round_state.shot_this_round is True
    assert getattr(models[0], "_shot_via_firing_deck_this_round") is True
    assert getattr(transport, "_firing_deck_declared_this_phase") is True
    assert getattr(transport, "_firing_deck_virtual_wargear")


def test_headless_firing_deck_default_selects_model_specific_weapons_up_to_limit():
    transport = _mk_unit(
        "Chimera",
        abilities=[{"name": "Firing Deck 2", "description": "", "type": "", "parameter": ""}],
        keywords=["Vehicle", "Transport"],
    )
    transport._id = "TRANSPORT_HEADLESS"
    passenger = _mk_unit("Infantry Squad", abilities=[])
    passenger._id = "PASSENGER_HEADLESS"
    models = _set_models(
        passenger,
        [
            ("Guardsman", "Lasgun"),
            ("Gunner", "Plasma gun"),
            ("Missile team", "Hunter-killer missile"),
        ],
    )
    one_shot = _mk_ranged_weapon("Hunter-killer missile", f"{models[2]._id}_HK", description="[ONE SHOT]")
    models[2].wargear = [one_shot]
    passenger.embarked_in = transport
    transport.transport_passengers = [passenger]
    all_wargear = [models[0].wargear[0], models[1].wargear[0], one_shot]
    game = SimpleNamespace(
        entity_registry=_RegistryStub(units=[transport, passenger], models=models, wargear=all_wargear),
    )
    request = build_declare_firing_deck_request(transport, player_id="P1")
    assert request is not None
    assert len(firing_deck_selection_entries(transport)) == 2

    selected = HeadlessPolicyDecisionController._default_firing_deck_entries(
        game,
        request,
        {"transport_id": transport._id},
    )

    assert len(selected) == 2
    selected_by_model = {entry["model_id"]: entry["wargear_id"] for entry in selected}
    assert selected_by_model == {
        models[0]._id: models[0].wargear[0]._id,
        models[1]._id: models[1].wargear[0]._id,
    }
