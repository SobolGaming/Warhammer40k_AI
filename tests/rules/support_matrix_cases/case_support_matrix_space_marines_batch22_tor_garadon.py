from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch22_tor_garadon_support_matrix_case():
    description = (
        "Each time this model makes an attack that targets a MONSTER, VEHICLE, or FORTIFICATION unit, "
        "improve the Strength, Armour Penetration and Damage characteristics of that attack by 2."
    )

    status, notes = _classify_ability(
        "Siege Captain",
        description,
        faction_id="SM",
        datasheet_id="000002473",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "monster/vehicle/fortification" in notes_l
    assert "strength" in notes_l
    assert "ap" in notes_l
    assert "damage" in notes_l
    assert "by 2" in notes_l
