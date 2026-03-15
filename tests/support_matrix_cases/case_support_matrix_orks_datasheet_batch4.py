import pytest

from scripts.generate_ability_support_matrix import _classify_ability


@pytest.mark.parametrize(
    ("name", "description", "note_fragment"),
    [
        (
            "Big an' Stompy",
            "Each time this model makes a melee attack, if the Waaagh! is active for your army, add 1 to the Hit roll.",
            "while the waaagh! is active",
        ),
        (
            "Clankin' Forward",
            "Each time this model makes a Normal, Advance or Fall Back move, it can move over enemy models (excluding MONSTER and VEHICLE models) and terrain features that are 4\" or less in height as if they were not there.",
            "except monster/vehicle",
        ),
        (
            "Prophet of Da Great Waaagh!",
            "While this unit is leading a unit, each time a model in that unit makes a melee attack, add 1 to the Hit roll and add 1 to the Wound roll and if the Waaagh! is active for your army, a Critical Hit is scored on a successful unmodified Hit roll of 5+.",
            "critical hits",
        ),
        (
            "Ghazghkull's Waaagh! Banner (Aura)",
            "While a friendly ORKS unit is within 12\" of Makari, if the Waaagh! is active for your army, melee weapons equipped by models in that unit have the [LETHAL HITS] ability.",
            "makari",
        ),
        (
            "Runtherd",
            "While this unit contains one or more Gretchin models, each time an attack targets this unit, Runtherd models in this unit have a Toughness characteristic of 2.",
            "toughness resolves as 2",
        ),
        (
            "Thievin' Scavengers",
            "At the start of your Movement phase, roll one D6 for each objective marker you control that has one or more units from your army with this ability within range of it (excluding Battle-shocked units). If one or more of those rolls is a 4+, you gain 1CP.",
            "movement phase start",
        ),
        (
            "On Da Hunt",
            "Add 1 to the Attacks characteristic of this model's butcha boyz weapon for every model embarked within this Transport (to a maximum of 6).",
            "maximum of +6",
        ),
        (
            "Spirit of Gork (Psychic)",
            "At the start of the Fight phase, you can select one friendly Orks unit within 12\" of this model and roll one D6: on a 1, this model suffers D3 mortal wounds; on a 2-5, until the end of the phase, add 1 to the Strength characteristic of melee weapons equipped by models in that unit; on a 6, until the end of the phase, add 1 to the Strength characteristic of melee weapons equipped by models in that unit and those weapons have the [LETHAL HITS] ability.",
            "fight phase start",
        ),
    ],
)
def test_orks_datasheet_batch4_support_matrix_cases(name: str, description: str, note_fragment: str):
    status, notes = _classify_ability(name, description, faction_id="ORK")
    assert status == "Supported"
    assert note_fragment.lower() in str(notes).lower()
