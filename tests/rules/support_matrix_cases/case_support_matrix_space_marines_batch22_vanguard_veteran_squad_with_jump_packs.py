from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch22_vanguard_veteran_squad_with_jump_packs_vanguard_assault_support_matrix_case():
    description = (
        "Each time this unit ends a Charge move, until the end of the turn, melee weapons equipped by models "
        "in this unit have the [LETHAL HITS] ability."
    )

    status, notes = _classify_ability(
        "Vanguard Assault",
        description,
        faction_id="SM",
        datasheet_id="000000147",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "charge" in notes_l
    assert "melee" in notes_l
    assert "lethal hits" in notes_l
