import pytest


CASES = [
    (
        "Ballistus Strike",
        "Each time this model makes a ranged attack that targets a unit that is not Below Half-strength, you can re-roll the Hit roll.",
        "000000091",
        ("not below half-strength", "re-roll the hit roll"),
    ),
    (
        "Grand Master of the Deathwing",
        "While this model is leading a unit, each time a model in that unit makes an attack, if a Critical Hit is scored, that attack has the [PRECISION] ability.",
        "000000219",
        ("precision", "critical hits"),
    ),
    (
        "Strikes of Retribution",
        "Each time a melee attack is allocated to this model, after the attacking model’s unit has finished making its attacks, roll one D6 (to a maximum of six D6 per attacking unit): for each 4+, the attacking unit suffers 1 mortal wound.",
        "000000219",
        ("max 6", "mortal wound"),
    ),
    (
        "Bladeguard",
        "At the start of the Fight phase, you can select one of the following abilities to apply to models in this unit until the end of the phase: Swords of the Chapter: Each time a model in this unit makes a melee attack, re-roll a Hit roll of 1. Shields of the Chapter: Each time an invulnerable saving throw is made for a model in this unit, re-roll a saving throw of 1.",
        "000000071",
        ("swords of the chapter", "shields of the chapter"),
    ),
    (
        "Deeds of Heroism",
        "Once per battle, when this model is selected to fight, it can use this ability. If it does, until the end of the phase, add 1 to the Attacks characteristic of melee weapons equipped by models in this model’s unit.",
        "000001165",
        ("once per battle", "melee weapons"),
    ),
    (
        "Brutalis Charge",
        "Each time this model ends a Charge move, select one enemy unit within Engagement Range of it and roll one D6: on a 2-3, that enemy unit suffers D3 mortal wounds; on a 4-5, that enemy unit suffers 3 mortal wounds; on a 6, that enemy unit suffers D3+3 mortal wounds.",
        "000000136",
        ("2-3=d3", "6=d3+3"),
    ),
]


@pytest.mark.parametrize(("name", "description", "datasheet_id", "fragments"), CASES)
def test_support_matrix_space_marines_batch2_datasheet_abilities(
    name: str,
    description: str,
    datasheet_id: str,
    fragments: tuple[str, str],
):
    from scripts.generate_ability_support_matrix import _classify_ability

    status, notes = _classify_ability(name, description, faction_id="SM", datasheet_id=datasheet_id)

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    for fragment in fragments:
        assert fragment in notes_l
