from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, *, datasheet_id: str, model_name: str = "Test Model", models_cost=None):
        self.id = datasheet_id
        self.name = "Cached Unit"
        self.faction_data = {"name": "Test Faction"}
        self.faction_id = "test-faction"
        self.keywords = ["INFANTRY"]
        self.faction_keywords = ["TEST"]
        self.datasheets_unit_composition = [{"description": f"1 {model_name}"}]
        self.datasheets_models_cost = models_cost or [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [{
            "name": model_name,
            "M": "6",
            "T": "4",
            "Sv": "3",
            "W": "1",
            "Ld": "7",
            "OC": "1",
            "base_size": "32mm",
            "inv_sv": "7",
            "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def test_unit_reuses_cached_parsed_datasheet_record(monkeypatch):
    datasheet = MockDatasheet(datasheet_id="cache-test-1")
    first = Unit(datasheet)
    assert first.unit_composition == {"Test Model": (1, 1)}
    assert first.wargear_options == {}

    def _should_not_run(_self, _datasheet):
        raise AssertionError("Unexpected reparsing call for cached datasheet.")

    monkeypatch.setattr(Unit, "_parse_abilities", _should_not_run)

    second = Unit(datasheet)
    assert second.unit_composition == {"Test Model": (1, 1)}
    assert second.wargear_options == {}


def test_cached_parsed_datasheet_record_does_not_share_mutable_unit_state():
    datasheet = MockDatasheet(datasheet_id="cache-test-mutable")
    first = Unit(datasheet)
    first.unit_composition["Test Model"] = (9, 9)
    first.keywords.append("MUTATED")

    second = Unit(datasheet)

    assert second.unit_composition == {"Test Model": (1, 1)}
    assert second.keywords == ["INFANTRY"]


def test_cached_parsed_datasheet_key_includes_static_payload_for_reused_ids():
    first_datasheet = MockDatasheet(datasheet_id="cache-test-reused-id", model_name="First Model")
    second_datasheet = MockDatasheet(datasheet_id="cache-test-reused-id", model_name="Second Model")

    first = Unit(first_datasheet)
    second = Unit(second_datasheet)

    assert first.unit_composition == {"First Model": (1, 1)}
    assert second.unit_composition == {"Second Model": (1, 1)}


def test_cached_parsed_datasheet_record_preserves_model_cost_addons(monkeypatch):
    datasheet = MockDatasheet(
        datasheet_id="cache-test-addon-cost",
        model_name="Attack Bike",
        models_cost=[
            {"description": "1 models", "cost": "100"},
            {"description": "Attack Bike", "cost": "+55"},
        ],
    )
    first = Unit(datasheet)
    assert first.get_unit_cost() == 155

    def _should_not_run(_self, _models_cost):
        raise AssertionError("Unexpected model-cost reparsing call for cached datasheet.")

    monkeypatch.setattr(Unit, "_parse_models_cost", _should_not_run)

    second = Unit(datasheet)
    assert second.models_cost_addons == {"attack bike": 55}
    assert second.get_unit_cost() == 155
