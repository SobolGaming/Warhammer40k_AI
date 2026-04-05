from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch25_infernus_squad_incendiary_terror_support_matrix_case():
    status, notes = _classify_ability(
        "Incendiary Terror",
        "In your Shooting phase, after this unit has shot, you can select one enemy INFANTRY unit hit by one or more of those attacks made with a pyreblaster. That enemy unit must take a Battle-shock test, subtracting 1 from that test.",
        faction_id="SM",
        datasheet_id="000000126",
    )

    assert status == "Supported"
    assert "INFANTRY" in notes
    assert "-1" in notes
