from scripts.generate_ability_support_matrix import _classify_ability


def test_space_marines_batch24_ezekiel_engulfing_fear_support_matrix_case():
    status, notes = _classify_ability(
        "Engulfing Fear (Psychic)",
        'In your Shooting phase, you can select one enemy unit within 18" of this model. That enemy unit must take a Battle-shock test.',
        faction_id="SM",
        datasheet_id="000000226",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "shooting phase" in notes_l
    assert "18" in notes_l
    assert "battle-shock" in notes_l


def test_space_marines_batch24_ezekiel_book_of_salvation_support_matrix_case():
    description = (
        "While this model is leading a unit, add 1 to the Attacks characteristic of melee weapons equipped by "
        "models in that unit. When this model is destroyed, each friendly ADEPTUS ASTARTES unit within 6\" of this "
        "model must take a Battle-shock test."
    )

    status, notes = _classify_ability(
        "Book of Salvation",
        description,
        faction_id="SM",
        datasheet_id="000000226",
    )

    assert status == "Supported"
    notes_l = str(notes or "").lower()
    assert "+1a" in notes_l
    assert "friendly adeptus astartes" in notes_l
    assert "battle-shock" in notes_l
