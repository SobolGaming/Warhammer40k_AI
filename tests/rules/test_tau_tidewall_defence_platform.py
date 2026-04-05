class _MockDatasheet:
    def __init__(self, *, include_ability: bool) -> None:
        self.id = "tau_test_shieldline"
        self.name = "Tidewall Shieldline"
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = ["FORTIFICATION", "TRANSPORT"]
        self.faction_keywords = ["T'AU EMPIRE"]
        self.datasheets_unit_composition = [{"description": "1 Tidewall Shieldline"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": "85"}]
        self.datasheets_models = [
            {
                "M": "4",
                "T": "8",
                "Sv": "3",
                "W": "10",
                "Ld": "7",
                "OC": "0",
                "base_size": "Use model",
                "inv_sv": "5",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "This model can be equipped with 1 Tidewall defence platform."}]
        self.datasheets_abilities = []
        if include_ability:
            self.datasheets_abilities.append(
                {
                    "name": "Tidewall Defence Platform",
                    "description": (
                        "If equipped with a Tidewall defence platform, this FORTIFICATION has a Wounds "
                        "characteristic of 15."
                    ),
                    "type": "Datasheet",
                    "parameter": "",
                }
            )
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _make_unit(*, include_ability: bool):
    from warhammer40k_ai.units.unit import Unit

    return Unit(_MockDatasheet(include_ability=include_ability))


def test_tidewall_defence_platform_sets_wounds_when_equipped():
    unit = _make_unit(include_ability=True)
    model = unit.models[0]
    assert model._base_wounds == 10
    assert model.wounds == 10

    model.optional_wargear.append("Tidewall defence platform")
    unit._refresh_bearer_unit_common_modifiers()

    assert model._base_wounds == 15
    assert model.wounds == 15
    assert unit.starting_total_wounds == 15


def test_tidewall_defence_platform_does_not_apply_when_not_equipped():
    unit = _make_unit(include_ability=True)
    model = unit.models[0]

    unit._refresh_bearer_unit_common_modifiers()

    assert model._base_wounds == 10
    assert model.wounds == 10
    assert unit.starting_total_wounds == 10


def test_tidewall_defence_platform_requires_matching_ability():
    unit = _make_unit(include_ability=False)
    model = unit.models[0]
    model.optional_wargear.append("Tidewall defence platform")

    unit._refresh_bearer_unit_common_modifiers()

    assert model._base_wounds == 10
    assert model.wounds == 10
    assert unit.starting_total_wounds == 10
