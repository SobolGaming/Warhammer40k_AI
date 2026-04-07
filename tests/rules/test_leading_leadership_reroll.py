import types

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        model_count: int = 1,
        attached_to=None,
        attached_to_names=None,
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "4", "W": "2",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = list(attached_to or [])
        self.attached_to_names = list(attached_to_names or [])
        self.transport = ""
        self.damaged_w = ""
        self.damaged_description = ""


def test_leading_leadership_reroll_applies_to_attached_unit(monkeypatch):
    bodyguard_ds = MockDatasheet("Bodyguard", datasheet_id="BG1")
    leader_ds = MockDatasheet("Leader", datasheet_id="L1", attached_to=["BG1"])

    bodyguard = Unit(bodyguard_ds)
    leader = Unit(leader_ds)

    army = Army.with_detachment(faction="Test", detachment_type="Test", points_limit=2000)
    army.player = types.SimpleNamespace(name="P1", game=None)
    army.add_unit(bodyguard)
    army.add_unit(leader)

    leader.attach_to_unit(bodyguard)

    leader.possible_abilities.append(
        Ability(
            name="Steadfast Example",
            faction_id="",
            description="While this model is leading a unit, you can re-roll Leadership tests taken for that unit.",
            type="Datasheet",
            parameter="",
        )
    )
    leader._invalidate_ability_cache()
    bodyguard._invalidate_ability_cache()

    rolls = iter([12, 5])

    import warhammer40k_ai.units.unit as unit_mod

    monkeypatch.setattr(unit_mod, "get_roll", lambda _expr: next(rolls))

    assert bodyguard.pass_leadership_check() is True
