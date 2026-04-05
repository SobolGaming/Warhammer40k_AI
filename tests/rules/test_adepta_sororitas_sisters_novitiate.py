from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.units.unit import Unit


IMPETUOUS_FERVOUR_TEXT = (
    "Each time a model in this unit makes an attack, re-roll a Hit roll of 1. "
    "If the target of that attack is an enemy unit within range of an objective marker, "
    "you can re-roll the Hit roll instead."
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


def test_impetuous_fervour_reroll_upgrades_on_objective_target():
    novitiates = _make_unit(
        "Sisters Novitiate Squad",
        abilities=[
            {
                "name": "Impetuous Fervour",
                "description": IMPETUOUS_FERVOUR_TEXT,
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
    attacker = novitiates.models[0]

    baseline = novitiates.get_unit_hit_reroll_modifiers(
        "melee",
        target=enemy,
        attacker_model=attacker,
    )
    assert bool(baseline.get("reroll_hit_ones", False))
    assert not bool(baseline.get("reroll_hit_full", False))

    with patch.object(novitiates, "_target_within_objective_range", return_value=True):
        objective_target = novitiates.get_unit_hit_reroll_modifiers(
            "melee",
            target=enemy,
            attacker_model=attacker,
        )
    assert bool(objective_target.get("reroll_hit_full", False))
