from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch18_ravenwing_black_knights_support_matrix_cases():
    status, notes = _classify_ability(
        "Knights of Caliban",
        "Each time this unit is selected to fight, if it made a Charge move this turn, until the end of the phase, melee weapons equipped by models in this unit have the [ANTI-MONSTER 4+] and [ANTI-VEHICLE 4+] abilities.",
        faction_id="SM",
        datasheet_id="000000241",
    )
    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "charging" in lowered or "charge" in lowered
    assert "anti monster 4" in lowered
    assert "anti vehicle 4" in lowered
