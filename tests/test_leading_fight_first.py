from __future__ import annotations

import unittest


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None, attached_to=None) -> None:
        self.id = f"ds-{name.lower()}"
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = []
        self.faction_keywords = ["TEST"]
        self.attached_to = list(attached_to or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name: str, *, abilities=None, attached_to=None):
    from warhammer40k_ai.units.unit import Unit

    return Unit(_MockDatasheet(name, abilities=abilities, attached_to=attached_to))


def _attach(leader, bodyguard) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = [bodyguard.name]


class TestLeadingFightFirst(unittest.TestCase):
    def test_leading_unit_grants_fight_first_to_bodyguard(self):
        ability = {
            "name": "Tactical Perception",
            "description": (
                "ADEPTUS CUSTODES model only. While this model is leading a unit, models in that unit "
                "have the Fights First ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability], attached_to=["Bodyguard"])
        bodyguard = _make_unit("Bodyguard")
        _attach(leader, bodyguard)

        self.assertTrue(bodyguard.has_fight_first())

    def test_leading_rule_not_active_when_unattached(self):
        ability = {
            "name": "Tactical Perception",
            "description": "While this model is leading a unit, models in that unit have the Fights First ability.",
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability], attached_to=["Bodyguard"])
        bodyguard = _make_unit("Bodyguard")

        self.assertFalse(leader.has_fight_first())
        self.assertFalse(bodyguard.has_fight_first())

    def test_leader_only_fight_first_does_not_propagate(self):
        ability = {
            "name": "Swift Killer",
            "description": "While this model is leading a unit, it has the Fights First ability.",
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability], attached_to=["Bodyguard"])
        bodyguard = _make_unit("Bodyguard")
        _attach(leader, bodyguard)

        self.assertFalse(bodyguard.has_fight_first())


if __name__ == "__main__":
    unittest.main(verbosity=2)

