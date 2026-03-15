import pytest

from scripts.generate_ability_support_matrix import _classify_ability


@pytest.mark.parametrize(
    ("name", "description", "note_fragment"),
    [
        (
            "Distraction Grot",
            "Once per battle, in your opponent's Shooting phase, before making a saving throw for a model in this unit, it can deploy the distraction grot. If it does, until the end of the phase, models in this unit have a 5+ invulnerable save.",
            "before a saving throw",
        ),
        (
            "Rivetin' Dakka",
            "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those attacks made with a rivet kannon. Until the start of your next turn, that enemy unit is suppressed. While a unit is suppressed, each time a model in that unit makes a ranged attack, subtract 1 from the Hit roll.",
            "ranged attacks",
        ),
        (
            "Drill Through",
            "Each time this model ends a Charge move, select one enemy unit within Engagement Range of it and roll one D6: on a 2-5, that enemy unit suffers D3 mortal wounds; on a 6, that enemy unit suffers 3 mortal wounds.",
            "6=3",
        ),
        (
            "One Last Kill",
            "While this model is leading a unit, each time a model in that unit is destroyed by a melee attack, if it has not fought this phase, roll one D6: on a 4+, do not remove it from play. The destroyed model can fight after the attacking unit has finished making its attacks, and is then removed from play.",
            "roll 4+",
        ),
        (
            "Da Bigger Dey iz...",
            "Each time this model makes a melee attack that targets a MONSTER or VEHICLE unit, add 1 to the Damage characteristic of that attack. Each time this model makes a melee attack that targets a TITANIC unit, add 2 to the Damage characteristic of that attack instead.",
            "titanic",
        ),
        (
            "Hold Still and Say 'Aargh!'",
            "Each time an attack made by this model with its 'urty syringe scores a Critical Wound against a unit (excluding VEHICLE units), that unit suffers D6 mortal wounds.",
            "non-vehicle",
        ),
    ],
)
def test_orks_datasheet_batch5_support_matrix_cases(name: str, description: str, note_fragment: str):
    status, notes = _classify_ability(name, description, faction_id="ORK")
    assert status == "Supported"
    assert note_fragment.lower() in str(notes).lower()
