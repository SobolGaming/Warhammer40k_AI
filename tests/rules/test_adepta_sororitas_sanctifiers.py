from __future__ import annotations

from warhammer40k_ai.units.unit import Unit


MINISTORUM_SERMON_TEXT = (
    "While this unit contains a MINISTORUM PRIEST, melee weapons equipped by models in this unit "
    "have the [SUSTAINED HITS 1] ability."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adepta Sororitas",
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTA SORORITAS"] if faction_name == "Adepta Sororitas" else [str(faction_name).upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": name,
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Adepta Sororitas",
    abilities=None,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def test_ministorum_sermon_grants_sustained_hits_when_priest_present():
    sanctifiers = _make_unit(
        "Sanctifiers",
        abilities=[
            {
                "name": "Ministorum Sermon",
                "description": MINISTORUM_SERMON_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
    )
    priest = _make_unit(
        "Ministorum Priest",
        keywords=["INFANTRY", "CHARACTER", "MINISTORUM PRIEST", "ADEPTA SORORITAS"],
    )
    enemy = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sanctifiers.attached_leaders = [priest]
    priest.attached_to = sanctifiers
    priest.can_be_attached_to = [sanctifiers.name]
    sanctifiers._invalidate_ability_cache()

    melee_bonuses = sanctifiers.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="melee",
        model=sanctifiers.models[0],
    )
    assert int(melee_bonuses.get("sustained_hits_value", 0) or 0) == 1

    ranged_bonuses = sanctifiers.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=sanctifiers.models[0],
    )
    assert int(ranged_bonuses.get("sustained_hits_value", 0) or 0) == 0


def test_ministorum_sermon_does_not_apply_without_priest():
    sanctifiers = _make_unit(
        "Sanctifiers",
        abilities=[
            {
                "name": "Ministorum Sermon",
                "description": MINISTORUM_SERMON_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "ADEPTA SORORITAS"],
    )
    enemy = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    melee_bonuses = sanctifiers.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="melee",
        model=sanctifiers.models[0],
    )
    assert int(melee_bonuses.get("sustained_hits_value", 0) or 0) == 0
