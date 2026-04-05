from scripts import generate_ability_support_matrix as gsm


def test_ravenwing_darkshroud_icon_of_old_caliban_support_matrix_case() -> None:
    description = (
        'While a friendly ADEPTUS ASTARTES unit is within 6" of this model, models in that unit have the '
        "Stealth ability and each time a ranged attack targets that unit, that unit has the Benefit of Cover "
        "against that attack."
    )

    status, notes = gsm._classify_ability("Icon of Old Caliban (Aura)", description, faction_id="SM")

    assert status == "Supported"
    assert "Stealth" in str(notes or "")
    assert "Benefit of Cover" in str(notes or "")
