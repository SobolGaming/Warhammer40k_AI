from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch18_ravenwing_command_squad_support_matrix_cases():
    status, notes = _classify_ability(
        "Honour or Death",
        "While this unit contains a Ravenwing Champion, add 1 to Advance and Charge rolls made for this unit and you can target this unit with the Heroic Intervention Stratagem for 0CP.",
        faction_id="SM",
        datasheet_id="000002748",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "ravenwing champion" in lowered
    assert "advance and charge" in lowered
    assert "heroic intervention" in lowered
