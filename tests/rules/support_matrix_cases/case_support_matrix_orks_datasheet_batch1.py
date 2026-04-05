import pytest


@pytest.mark.parametrize(
    "name,description",
    [
        (
            "Trophy Hunters",
            "Each time this unit declares a charge, you can re-roll the Charge roll.",
        ),
        (
            "Wild Ride",
            "You can ignore any or all modifiers to this unit's Move characteristic and to Advance and Charge rolls made for this unit.",
        ),
        (
            "Ramshackle but Rugged",
            "Each time an attack is allocated to this model, worsen the Armour Penetration characteristic of that attack by 1.",
        ),
        (
            "Dakkastorm",
            "Each time this model makes a ranged attack, every successful Hit roll scores a Critical Hit.",
        ),
        (
            "Ramshackle Cover",
            "Each time a ranged attack is allocated to a model, if that model is not fully visible to every model in the attacking unit because of this FORTIFICATION, that model has the Benefit of Cover against that attack.",
        ),
        (
            "Shoutin' Pole (Aura)",
            "While a friendly ORKS unit is within 6\" of this FORTIFICATION, improve the Leadership characteristic of models in that unit by 1.",
        ),
    ],
)
def test_support_matrix_orks_batch1_datasheet_abilities_supported(name, description):
    import scripts.generate_ability_support_matrix as gsm

    gsm._seed_ability_support_maps([], [])
    status, _notes = gsm._classify_ability(name, description, faction_id="ORK")
    assert status == "Supported"
