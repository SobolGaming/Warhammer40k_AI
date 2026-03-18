from scripts import generate_ability_support_matrix as gsm


def test_reiver_squad_fearsome_assault_support_matrix_case() -> None:
    description = (
        "At the start of the Fight phase, each enemy unit within Engagement Range of one or more units with this "
        "ability must take a Battle-shock test, subtracting 1 from that test."
    )

    status, notes = gsm._classify_ability("Fearsome Assault", description, faction_id="SM")

    assert status == "Supported"
    assert "Battle-shock test at -1" in str(notes or "")


def test_reiver_squad_reiver_grav_chute_support_matrix_case() -> None:
    status, notes = gsm._classify_ability("Reiver Grav-chute", "The bearer has the Deep Strike ability.", faction_id="SM")

    assert status == "Supported"
    assert "Deep Strike" in str(notes or "")
