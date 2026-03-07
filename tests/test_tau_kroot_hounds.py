from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        ds_id: str = "",
        abilities=None,
        faction_name: str = "T'au Empire",
        keywords=None,
        faction_keywords=None,
        objective_control: str = "2",
    ):
        self.id = ds_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [faction_name.upper()])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": str(objective_control),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(name: str, *, abilities=None, keywords=None, objective_control: int = 2):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        objective_control=str(objective_control),
    )
    return Unit(datasheet)


def test_hunting_hounds_sets_oc_to_one_near_friendly_kroot_character():
    hunting_hounds = {
        "name": "Hunting Hounds",
        "description": (
            'While this unit is within 12" of one or more friendly Kroot Character models, '
            "the Objective Control characteristic of models in this unit is 1."
        ),
        "type": "Datasheet",
        "parameter": "",
    }

    hounds = _make_unit("Kroot Hounds", abilities=[hunting_hounds], keywords=["KROOT"], objective_control=2)
    character = _make_unit("Kroot War Shaper", keywords=["KROOT", "CHARACTER"], objective_control=1)

    class _MapNoCharacter:
        def get_enemy_units(self, _unit):
            return []

        def get_friendly_units(self, unit):
            if unit is hounds:
                return [hounds]
            return [unit]

        def is_within_engagement_range(self, _unit_a, _unit_b):
            return False

    class _MapWithCharacter:
        def get_enemy_units(self, _unit):
            return []

        def get_friendly_units(self, unit):
            if unit is hounds:
                return [hounds, character]
            return [unit]

        def is_within_engagement_range(self, _unit_a, _unit_b):
            return False

    with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=False):
        baseline = int(hounds.get_effective_model_characteristic(hounds.models[0], "objective_control", game_map=_MapNoCharacter()))
    with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
        boosted = int(hounds.get_effective_model_characteristic(hounds.models[0], "objective_control", game_map=_MapWithCharacter()))

    assert baseline == 2
    assert boosted == 1
