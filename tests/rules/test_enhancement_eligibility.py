import json

import pytest

from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.rules.enhancement import Enhancement


class _DummyUnit:
    def __init__(self, name, *, keywords=None, faction_keywords=None):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.special_rules = {}
        self.enhancement = None
        self._parent_army = None

    @property
    def is_character(self) -> bool:
        return any(str(k).strip().lower() == "character" for k in (self.keywords or []))

    @property
    def is_epic_hero(self) -> bool:
        return any(str(k).strip().lower() == "epic hero" for k in (self.keywords or []))

    def get_effective_keywords(self):
        return list(self.keywords or [])

    def get_effective_faction_keywords(self):
        return list(self.faction_keywords or [])

    def set_parent_army(self, army):
        self._parent_army = army

    def get_parent_army(self):
        return self._parent_army


def _load_enhancement(name: str) -> Enhancement:
    with open("wahapedia_data/Enhancements.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    row = next(r for r in data if r.get("name") == name)
    return Enhancement.from_waha_dict(row)


def test_disciple_of_khorne_eligibility_enforced():
    army = Army.with_detachment("World Eaters", "Khorne Daemonkin")
    army.faction_id = "WE"
    enhancement = _load_enhancement("Disciple of Khorne")

    invalid = _DummyUnit(
        "Master of Executions",
        keywords=["Character"],
        faction_keywords=["WORLD EATERS"],
    )
    army.add_unit(invalid)
    with pytest.raises(ArmyValidationError):
        army.add_enhancement(enhancement, invalid)

    valid = _DummyUnit(
        "Lord on Juggernaut",
        keywords=["Character", "Lord on Juggernaut"],
        faction_keywords=["WORLD EATERS"],
    )
    army.add_unit(valid)
    army.add_enhancement(enhancement, valid)


def test_dread_majesty_eligibility_enforced():
    army = Army.with_detachment("Necrons", "Starshatter Arsenal")
    army.faction_id = "NEC"
    enhancement = _load_enhancement("Dread Majesty (Aura)")

    invalid = _DummyUnit(
        "Chronomancer",
        keywords=["Character"],
        faction_keywords=["NECRONS"],
    )
    army.add_unit(invalid)
    with pytest.raises(ArmyValidationError):
        army.add_enhancement(enhancement, invalid)

    valid = _DummyUnit(
        "Overlord",
        keywords=["Character", "Overlord"],
        faction_keywords=["NECRONS"],
    )
    army.add_unit(valid)
    army.add_enhancement(enhancement, valid)


def test_rise_to_the_challenge_requires_infantry():
    army = Army.with_detachment("Emperor's Children", "Peerless Bladesmen")
    army.faction_id = "EC"
    enhancement = _load_enhancement("Rise to the Challenge")

    invalid = _DummyUnit(
        "Lord Exultant",
        keywords=["Character"],
        faction_keywords=["Emperor's Children"],
    )
    army.add_unit(invalid)
    with pytest.raises(ArmyValidationError):
        army.add_enhancement(enhancement, invalid)

    valid = _DummyUnit(
        "Lord Exultant",
        keywords=["Character", "Infantry"],
        faction_keywords=["Emperor's Children"],
    )
    army.add_unit(valid)
    army.add_enhancement(enhancement, valid)
