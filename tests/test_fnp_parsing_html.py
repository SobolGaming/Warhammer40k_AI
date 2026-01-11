from warhammer40k_ai.classes.unit import Unit


class MockDatasheet:
    def __init__(self):
        self.name = "Karanak"
        self.faction_data = {"name": "Chaos Daemons"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "6",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [{
            "name": "Brass Collar of Bloody Vengeance",
            "description": (
                "The bearer has the <span class=\"tooltip00008\" data-tooltip-content=\"#tooltip_content00008\">"
                "<span class=\"tt kwbu\">Feel</span> <span class=\"tt kwbu\">No</span> "
                "<span class=\"tt kwbu\">Pain</span> <span class=\"tt kwbu\">3+</span></span> "
                "ability against Psychic Attacks and mortal wounds."
            ),
            "type": "Wargear",
            "parameter": "",
        }]
        self.loadout = "This model is equipped with: nothing"


def test_fnp_parses_html_description():
    unit = Unit(MockDatasheet())
    # Wargear abilities only apply when the wargear is equipped.
    for model in unit.models:
        model.optional_wargear.append("Brass Collar of Bloody Vengeance")
    fnps = unit.has_feel_no_pain()
    assert fnps
    assert any(
        value == 3 and condition and "psychic" in condition and "mortal" in condition
        for value, condition in fnps
    )
