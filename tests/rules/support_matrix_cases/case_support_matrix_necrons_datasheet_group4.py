import pytest


@pytest.mark.parametrize(
    "name,description",
    [
        (
            "Ancient Cover",
            (
                "Each time a ranged attack is allocated to a model, if that model is not fully visible to every model "
                "in the attacking unit because of this FORTIFICATION, that model has the Benefit of Cover against that attack."
            ),
        ),
        (
            "Fabricator Claw Array (Aura)",
            "While a friendly Necrons Vehicle unit is within 6\" of the bearer, that unit has the Feel No Pain 6+ ability.",
        ),
        (
            "Gloom Prism (Aura)",
            (
                "While a friendly NECRONS unit is within 6\" of the bearer, models in that unit have the Feel No Pain 5+ "
                "ability against mortal wounds and Psychic Attacks."
            ),
        ),
        (
            "Nullstone Field Generator (Aura)",
            (
                "While a friendly NECRONS unit is within 6\" of the bearer, models in that unit have the Feel No Pain 5+ "
                "ability against mortal wounds and Psychic Attacks."
            ),
        ),
        (
            "Reanimation Nodes (Aura)",
            "While a friendly Necrons Infantry unit is within 6\" of this Fortification, models in that unit have Feel No Pain 6+ ability.",
        ),
        (
            "Relentless March (Aura)",
            (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, add 2\" to the Move "
                "characteristic of models in that unit."
            ),
        ),
        (
            "The Silent King",
            (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, improve that unit's "
                "Leadership characteristic by 1."
            ),
        ),
        (
            "Phaeron of the Stars (Aura)",
            (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, each time a model in that unit "
                "makes an attack, re-roll a Hit roll of 1 and re-roll a Wound roll of 1."
            ),
        ),
        (
            "Phaeron of the Blades (Aura)",
            (
                "While a friendly NECRONS unit is within 6\" of this unit's Szarekh model, you can re-roll Charge rolls "
                "made for that unit and each time a model in that unit makes a melee attack, add 1 to the Strength "
                "characteristic of that attack."
            ),
        ),
    ],
)
def test_support_matrix_necrons_group4_datasheet_abilities_supported(name, description):
    import scripts.generate_ability_support_matrix as gsm

    gsm._seed_ability_support_maps([], [])
    status, _notes = gsm._classify_ability(name, description, faction_id="NEC")
    assert status == "Supported"
