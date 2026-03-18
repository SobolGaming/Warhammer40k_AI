from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch24_impulsor_orbital_comms_array_support_matrix_case():
    status, notes = _classify_ability(
        "Orbital Comms Array (Aura)",
        'While a friendly ADEPTUS ASTARTES unit is within 6" of the bearer, each time you target that unit with a Stratagem, roll one D6: on a 5+, you gain 1CP.',
        faction_id="SM",
        datasheet_id="000002568",
    )

    assert status == "Supported"
    assert "ADEPTUS ASTARTES" in notes
    assert "6" in notes
    assert "gain 1 CP on 5+" in notes
